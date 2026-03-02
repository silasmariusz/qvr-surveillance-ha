#!/usr/bin/env python3
"""
QVR Surveillance API probe – reconnaissance tool.
Probes all known and candidate endpoints, saves raw responses for analysis.

Usage:
  QVR_PASS=xxx python tools/qvr_api_probe.py
  QVR_PASS=xxx QVR_HOST=10.0.0.1 python tools/qvr_api_probe.py --output probe_output

Saves responses to probe_output/ (or --output dir). Use findings to build
QVR_API_REFERENCE.md and determine real timeline event sources.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

import xml.etree.ElementTree as ET

# Add project root for client import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from custom_components.qvr_surveillance.client import QVRClient
except ImportError:
    QVRClient = None


def auth_direct(host: str, port: int, user: str, password: str, protocol: str = "http"):
    """Direct auth to get SID for manual probes."""
    auth_url = f"{protocol}://{host}:{port}/cgi-bin/authLogin.cgi"
    pwd_b64 = base64.b64encode(password.encode("ascii")).decode("ascii")
    params = {"user": user, "pwd": pwd_b64, "serviceKey": 1, "verify": 0}
    r = requests.get(auth_url, params=params, timeout=10, verify=False)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    sid = root.find(".//authSid")
    if sid is None or not sid.text:
        raise ValueError("No authSid in response")
    return sid.text


def get_qvrentry(host: str, port: int, protocol: str = "http"):
    """Discover API path (qvrpro, qvrelite, qvrsurveillance)."""
    url = f"{protocol}://{host}:{port}/qvrentry"
    r = requests.get(url, timeout=10, verify=False)
    r.raise_for_status()
    data = r.json()
    prefix = data.get("fw_web_ui_prefix", "").strip("/")
    if data.get("is_qvp") == "yes":
        return "/qvrpro"
    if prefix:
        return f"/{prefix}"
    return "/qvrelite"


def probe_get(
    base_url: str,
    path: str,
    sid: str,
    params: dict | None = None,
) -> tuple[bool, dict | list | str, int]:
    """Probe GET endpoint. Returns (ok, data, status_code)."""
    url = f"{base_url}{path}"
    p = (params or {}) | {"sid": sid, "ver": "1.1.0"}
    try:
        r = requests.get(url, params=p, timeout=30, verify=False)
        ct = r.headers.get("content-type", "")
        if "application/json" in ct:
            return r.ok, r.json(), r.status_code
        return r.ok, r.text[:500] if r.text else "", r.status_code
    except Exception as e:
        return False, {"error": str(e)}, 0


def run_probes(host: str, port: int, user: str, password: str, protocol: str, out_dir: Path):
    """Run all probes and save outputs."""
    base_url = f"{protocol}://{host}:{port}"
    sid = auth_direct(host, port, user, password, protocol)
    qvr_path = get_qvrentry(host, port, protocol)
    print(f"Auth OK, qvr_path={qvr_path}")

    # Get first channel for recording probes
    ch_resp = probe_get(base_url, f"{qvr_path}/qshare/StreamingOutput/channels", sid)
    channels = []
    if ch_resp[0] and isinstance(ch_resp[1], dict):
        ch_list = ch_resp[1].get("channelList") or ch_resp[1].get("channels") or []
        if isinstance(ch_list, list):
            for ch in ch_list[:3]:
                g = ch.get("guid") if isinstance(ch, dict) else None
                if g:
                    channels.append(g)

    guid = channels[0] if channels else "UNKNOWN"
    now_sec = int(time.time())
    now_ms = now_sec * 1000

    probes = [
        ("channels", f"{qvr_path}/qshare/StreamingOutput/channels", None),
        ("channel_streams", f"{qvr_path}/qshare/StreamingOutput/channel/{guid}/streams", None),
        ("camera_list", f"{qvr_path}/camera/list", None),
        ("camera_list_guid", f"{qvr_path}/camera/list", {"guid": guid}),
        ("camera_capability", f"{qvr_path}/camera/capability", None),
        ("camera_capability_ptz", f"{qvr_path}/camera/capability", {"ptz": 1}),
        ("camera_event_capability", f"{qvr_path}/camera/capability", {"act": "get_event_capability"}),
        ("logs_type1", f"{qvr_path}/logs/logs", {"log_type": 1, "max_results": 5}),
        ("logs_type2", f"{qvr_path}/logs/logs", {"log_type": 2, "max_results": 5}),
        ("logs_type3", f"{qvr_path}/logs/logs", {"log_type": 3, "max_results": 5, "global_channel_id": guid}),
        ("logs_type4", f"{qvr_path}/logs/logs", {"log_type": 4, "max_results": 5}),
        ("logs_type5", f"{qvr_path}/logs/logs", {"log_type": 5, "max_results": 5}),
        ("camera_search", f"{qvr_path}/camera/search", None),
        # Recording – various URIs and params
        ("recordingfile_time", f"{qvr_path}/camera/recordingfile/{guid}/0",
         {"time": now_sec - 3600, "pre_period": 10000, "post_period": 5000}),
        ("recordingfile_time_ms", f"{qvr_path}/camera/recordingfile/{guid}/0",
         {"time": now_ms - 3600000, "pre_period": 10000, "post_period": 5000}),
        ("recordingfile_start_end", f"{qvr_path}/camera/recordingfile/{guid}/0",
         {"start_time": now_sec - 3600, "end_time": now_sec}),
        # Possible recording list/search paths (may 404)
        ("camera_recording", f"{qvr_path}/camera/recording/{guid}", None),
        ("camera_recordingfile_list", f"{qvr_path}/camera/recordingfile/{guid}", None),
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for name, path, params in probes:
        ok, data, status = probe_get(base_url, path, sid, params)
        safe_name = name.replace("/", "_")
        fpath = out_dir / f"{safe_name}_{int(time.time())}.json"
        to_save = {"ok": ok, "status": status, "params": params, "data": data}
        if isinstance(data, (dict, list)):
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(to_save, f, indent=2, ensure_ascii=False, default=str)
        else:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(json.dumps({"ok": ok, "status": status, "data_preview": str(data)[:2000]}))
        keys = list(data.keys()) if isinstance(data, dict) else (f"list[{len(data)}]" if isinstance(data, list) else "n/a")
        results.append((name, ok, status, keys))
        print(f"  {name}: ok={ok} status={status}")

    return results


def main():
    ap = argparse.ArgumentParser(description="QVR API probe – reconnaissance")
    ap.add_argument("--output", "-o", default="probe_output", help="Output directory")
    ap.add_argument("--host", default=os.environ.get("QVR_HOST", "10.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("QVR_PORT", "8080")))
    ap.add_argument("--user", default=os.environ.get("QVR_USER", "admin"))
    ap.add_argument("--protocol", default="http")
    args = ap.parse_args()
    password = os.environ.get("QVR_PASS")
    if not password:
        print("Set QVR_PASS env var")
        sys.exit(1)
    out_dir = Path(args.output)
    results = run_probes(args.host, args.port, args.user, password, args.protocol, out_dir)
    print(f"\nSaved to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

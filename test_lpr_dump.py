#!/usr/bin/env python3
"""
Pełny zrzut API QVR – event capability + logi (wszystkie log_type).
Do weryfikacji LPR (tablice) i struktury eventów.

Uruchom: QVR_PASS=xxx python test_lpr_dump.py [--dir OUTPUT_DIR]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

HOST = os.environ.get("QVR_HOST", "10.100.200.10")
PORT = int(os.environ.get("QVR_PORT", "38080"))
USER = os.environ.get("QVR_USER", "admin")
PASS = os.environ.get("QVR_PASS", "")
PROTOCOL = os.environ.get("QVR_PROTOCOL", "http")
VERIFY_SSL = False
BASE = f"{PROTOCOL}://{HOST}:{PORT}"


def auth() -> tuple[str, str]:
    """Auth + discover qvr_uri."""
    url = f"{BASE}/cgi-bin/authLogin.cgi"
    pwd_b64 = base64.b64encode(PASS.encode("ascii")).decode("ascii")
    params = {"user": USER, "pwd": pwd_b64, "serviceKey": 1, "verify": 0}
    r = requests.get(url, params=params, timeout=15, verify=VERIFY_SSL)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    if int(root.find(".//authPassed").text or 0) != 1:
        raise RuntimeError("Authentication failed")
    sid = root.find(".//authSid").text or ""

    qvr_uri = "/qvrsurveillance"
    try:
        re = requests.get(f"{BASE}/qvrentry", timeout=10, verify=VERIFY_SSL)
        data = re.json() if re.ok and "json" in re.headers.get("content-type", "") else {}
        if data.get("fw_web_ui_prefix"):
            p = data["fw_web_ui_prefix"].strip("/") or "qvrpro"
            qvr_uri = f"/{p}"
        elif data.get("is_qvp") == "yes":
            qvr_uri = "/qvrpro"
    except Exception:
        pass
    return sid, qvr_uri


def qvr_get(sid: str, path: str, params: dict | None = None) -> dict | list:
    url = f"{BASE}{path}"
    p = dict(params) if params else {}
    p["sid"] = sid
    p["ver"] = "1.1.0"
    r = requests.get(url, params=p, timeout=30, verify=VERIFY_SSL)
    if "application/json" in r.headers.get("content-type", ""):
        return r.json()
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=".", help="Output directory for JSON dumps")
    args = parser.parse_args()
    out_dir = args.dir
    os.makedirs(out_dir, exist_ok=True)
    ts = int(time.time())

    if not PASS:
        print("Set QVR_PASS")
        return 1

    print(f"QVR LPR/Events dump -> {out_dir}")
    sid, qvr_uri = auth()
    print(f"Auth OK, path={qvr_uri}")

    # 1. Event capability
    cap = qvr_get(sid, f"{qvr_uri}/camera/capability", {"act": "get_event_capability"})
    path_cap = os.path.join(out_dir, f"event_capability_{ts}.json")
    with open(path_cap, "w", encoding="utf-8") as f:
        json.dump(cap, f, indent=2, ensure_ascii=False)
    print(f"Saved: {path_cap}")
    keys = sorted(cap.keys()) if isinstance(cap, dict) else []
    for k in keys:
        if "lpr" in k.lower() or "plate" in k.lower() or "license" in k.lower():
            print(f"  *** LPR-related key: {k}")

    # 2. Channels
    ch_resp = qvr_get(sid, f"{qvr_uri}/qshare/StreamingOutput/channels")
    ch_raw = ch_resp.get("channels") or ch_resp.get("channel") or []
    if isinstance(ch_raw, dict):
        ch_raw = list(ch_raw.values()) if ch_raw else []
    cameras = [(c.get("guid", ""), c.get("channel_name") or c.get("name", "")) for c in ch_raw if c.get("guid")]
    print(f"Cameras: {len(cameras)}")

    since_ts = int(time.time()) - 86400  # 24h

    # 3. Logs per log_type
    for log_type in (1, 2, 3, 4, 5):
        logs = qvr_get(
            sid,
            f"{qvr_uri}/logs/logs",
            {"log_type": log_type, "start_time": since_ts, "max_results": 100, "sort_field": "time", "dir": "DESC"},
        )
        raw = logs.get("logs") or logs.get("log") or logs.get("items") or logs.get("data") or []
        if isinstance(raw, dict):
            raw = list(raw.values()) if raw else []
        path_log = os.path.join(out_dir, f"logs_type{log_type}_{ts}.json")
        with open(path_log, "w", encoding="utf-8") as f:
            json.dump({"log_type": log_type, "count": len(raw), "entries": raw}, f, indent=2, ensure_ascii=False)
        print(f"  log_type={log_type}: {len(raw)} entries -> {path_log}")
        for entry in raw[:3]:
            if isinstance(entry, dict):
                msg = str(entry.get("message") or entry.get("content") or "")
                meta = entry.get("metadata") or {}
                if any(x in msg.lower() for x in ("plate", "license", "lpr", "tablic", "rejestr")):
                    print(f"    *** LPR-like message: {msg[:80]}")
                if any(k for k in meta if "lpr" in k.lower() or "plate" in k.lower()):
                    print(f"    *** LPR metadata: {meta}")

    # 4. Logs per camera (log_type=3)
    for idx, (guid, name) in enumerate(cameras[:5]):
        logs = qvr_get(
            sid,
            f"{qvr_uri}/logs/logs",
            {
                "log_type": 3,
                "start_time": since_ts,
                "max_results": 50,
                "sort_field": "time",
                "dir": "DESC",
                "global_channel_id": guid,
            },
        )
        raw = logs.get("logs") or logs.get("log") or logs.get("items") or []
        if isinstance(raw, dict):
            raw = list(raw.values()) if raw else []
        path_ch = os.path.join(out_dir, f"logs_type3_ch{idx}_{ts}.json")
        with open(path_ch, "w", encoding="utf-8") as f:
            json.dump({"channel": name, "guid": guid, "count": len(raw), "entries": raw}, f, indent=2, ensure_ascii=False)
        print(f"  Ch{idx} {name[:20]}: {len(raw)} entries")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

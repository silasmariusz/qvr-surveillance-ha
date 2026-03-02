#!/usr/bin/env python3
"""
QVR Surveillance API probe – full reconnaissance.

Probes all known and candidate endpoints, multiple param variants,
multi-step flows. Saves raw responses for analysis and infographic.

Usage:
  QVR_PASS=xxx python tools/qvr_api_probe.py
  QVR_PASS=xxx QVR_HOST=10.0.0.1 QVR_PORT=8080 python tools/qvr_api_probe.py
  QVR_PASS=xxx python tools/qvr_api_probe.py --output probe_output --verbose
  QVR_PASS=xxx python tools/qvr_api_probe.py --use-library  # use qvr_api wrapper

Output: probe_output/*.json, probe_output/summary.txt, probe_output/meta.json
"""

from __future__ import annotations

import argparse
from typing import Callable
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

# Add integration package for qvr_api import (qvr_api lives inside custom_components/qvr_surveillance/)
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "custom_components" / "qvr_surveillance"))


def auth_direct(host: str, port: int, user: str, password: str, protocol: str = "http"):
    """Direct auth to get SID."""
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
    """Discover API path."""
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
    timeout: int = 30,
) -> tuple[bool, dict | list | str, int]:
    """Probe GET. Returns (ok, data, status)."""
    url = f"{base_url}{path}"
    p = (params or {}) | {"sid": sid, "ver": "1.1.0"}
    try:
        r = requests.get(url, params=p, timeout=timeout, verify=False)
        ct = r.headers.get("content-type", "")
        if "application/json" in ct:
            return r.ok, r.json(), r.status_code
        return r.ok, (r.text[:2000] if r.text else ""), r.status_code
    except Exception as e:
        return False, {"error": str(e)}, 0


def probe_post(
    base_url: str,
    path: str,
    sid: str,
    body: dict,
    timeout: int = 30,
) -> tuple[bool, dict | list | str, int]:
    """Probe POST. Returns (ok, data, status)."""
    url = f"{base_url}{path}"
    params = {"sid": sid, "ver": "1.1.0"}
    try:
        r = requests.post(url, params=params, json=body, timeout=timeout, verify=False)
        ct = r.headers.get("content-type", "")
        if "application/json" in ct:
            return r.ok, r.json(), r.status_code
        return r.ok, (r.text[:2000] if r.text else ""), r.status_code
    except Exception as e:
        return False, {"error": str(e)}, 0


def save_result(out_dir: Path, name: str, ok: bool, status: int, params: dict | None, data, verbose: bool):
    """Save probe result to JSON."""
    safe = name.replace("/", "_").replace(" ", "_")
    ts = int(time.time())
    fpath = out_dir / f"{safe}_{ts}.json"
    to_save = {"ok": ok, "status": status, "params": params, "data": data}
    if isinstance(data, (dict, list)):
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2, ensure_ascii=False, default=str)
    else:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump({"ok": ok, "status": status, "params": params, "data_preview": str(data)[:3000]}, f)
    return safe, ok, status


def run_probes_via_library(
    host: str, port: int, user: str, password: str, protocol: str, out_dir: Path, verbose: bool
):
    """Run probe suite using qvr_api library."""
    try:
        from qvr_api import QVRApi
    except ImportError as e:
        print(f"Cannot import qvr_api: {e}. Run from project root: python tools/qvr_api_probe.py")
        raise

    api = QVRApi(host=host, user=user, password=password, port=port, protocol=protocol)
    res = api.ensure_qvr_path()
    if not res.ok:
        print(f"Auth/path failed: {res.error}")
        raise SystemExit(1)

    qvr_path = api._qvr_path  # type: ignore[attr-defined]
    meta = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": host,
        "port": port,
        "qvr_path": qvr_path,
        "protocol": protocol,
        "source": "qvr_api",
    }
    with open(out_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Auth OK (qvr_api), qvr_path={qvr_path}\n")

    ch_res = api.get_channels()
    ch_ok = ch_res.ok
    ch_data = ch_res.data if isinstance(ch_res.data, dict) else {}
    channels = []
    if ch_ok:
        ch_list = ch_data.get("channelList") or ch_data.get("channels") or []
        if isinstance(ch_list, list):
            for ch in ch_list[:5]:
                g = ch.get("guid") if isinstance(ch, dict) else None
                if g:
                    channels.append(g)

    guid = channels[0] if channels else "UNKNOWN"
    now_sec = int(time.time())
    now_ms = now_sec * 1000
    results: list[tuple[str, bool, int]] = []

    # Probes via QVRApi
    probes: list[tuple[str, Callable[[], object], dict | None]] = [
        ("channels", lambda: api.get_channels(), None),
        ("channel_streams", lambda: api.get_channel_streams(guid), None),
        ("camera_list", lambda: api.get_camera_list(None), None),
        ("camera_list_guid", lambda: api.get_camera_list(guid), {"guid": guid}),
        # Capability: all variants (some may 404)
        ("camera_capability", lambda: api.get_camera_capability(None, 0), None),
        ("camera_capability_ptz", lambda: api.get_camera_capability(None, 1), {"ptz": 1}),
        ("camera_event_capability", lambda: api.get_event_capability(), {"act": "get_event_capability"}),
        ("camera_capability_act_get_camera", lambda: api.get_capability_act("get_camera_capability"), {"act": "get_camera_capability"}),
        ("camera_capability_act_list", lambda: api.get_capability_act("list"), {"act": "list"}),
        ("camera_capability_act_get_features", lambda: api.get_capability_act("get_features"), {"act": "get_features"}),
        ("camera_capability_act_get_ptz", lambda: api.get_capability_act("get_ptz"), {"act": "get_ptz"}),
        ("camera_search", lambda: api.get_camera_search(), None),
        ("logs_type1", lambda: api.get_logs(1, max_results=5), {"log_type": 1}),
        ("logs_type2", lambda: api.get_logs(2, max_results=5), {"log_type": 2}),
        ("logs_type3", lambda: api.get_logs(3, max_results=5, global_channel_id=guid), {"log_type": 3}),
        ("logs_type4", lambda: api.get_logs(4, max_results=5), {"log_type": 4}),
        ("logs_type5", lambda: api.get_logs(5, max_results=5), {"log_type": 5}),
        ("logs_type3_time", lambda: api.get_logs(
            3, max_results=10, global_channel_id=guid,
            start_time=now_sec - 86400, end_time=now_sec
        ), None),
        ("recordingfile_time_sec", lambda: api.get_recording(
            guid, time_sec=now_sec - 3600, pre_period=10000, post_period=5000, uri_variant="recordingfile/0"
        ), {"time": now_sec - 3600}),
        ("recordingfile_time_ms", lambda: api.get_recording(
            guid, time_ms=now_ms - 3600000, pre_period=10000, post_period=5000, uri_variant="recordingfile/0"
        ), {"time": now_ms - 3600000}),
        ("recordingfile_start_end", lambda: api.get_recording(
            guid, start_time=now_sec - 3600, end_time=now_sec, uri_variant="recordingfile/0"
        ), {"start_time": now_sec - 3600, "end_time": now_sec}),
        ("recordingfile_start_end_alt", lambda: api.get_recording(
            guid, start=now_sec - 3600, end=now_sec, uri_variant="recordingfile/0"
        ), {"start": now_sec - 3600, "end": now_sec}),
        ("recordingfile_ch1", lambda: api.get_recording(
            guid, time_sec=now_sec - 3600, pre_period=10000, post_period=5000, uri_variant="recordingfile/1"
        ), None),
        ("camera_recording_guid", lambda: api.get_recording_list(guid), None),
        ("camera_recordingfile_noch", lambda: api.get_recordingfile_noch(guid), None),
        ("camera_recordings", lambda: api.get_recordings(), None),
        ("camera_events", lambda: api.get_events(), None),
        # Candidate paths (may 404)
        ("event_root", lambda: api.get_event_path(), None),
        ("metadata_root", lambda: api.get_metadata_path(), None),
        ("qshare_RecordingOutput", lambda: api.get_qshare_path("RecordingOutput"), None),
        ("qshare_RecordingOutput_channels", lambda: api.get_qshare_path("RecordingOutput/channels"), None),
        ("camera_search_with_time", lambda: api.get_camera_search_params(
            start_time=now_sec - 86400, end_time=now_sec
        ), {"start_time": now_sec - 86400, "end_time": now_sec}),
        # Recording variant: channel 2
        ("recordingfile_ch2", lambda: api.get_recording(
            guid, time_sec=now_sec - 3600, pre_period=10000, post_period=5000, uri_variant="recordingfile/2"
        ), None),
        # Logs with level
        ("logs_type3_level_info", lambda: api.get_logs(3, max_results=5, level="info"), {"level": "info"}),
    ]

    for name, fn, params in probes:
        res = fn()
        status = 200 if res.ok else 0
        save_result(out_dir, name, res.ok, status, params, res.data, verbose)
        results.append((name, res.ok, status))
        print(f"  GET {name}: ok={res.ok} status={status}")

    # Capability per-guid (all variants for first channel)
    cap_variants = api.get_capability_all_variants(guid)
    for vname, vparams, vres in cap_variants:
        name = f"capability_per_guid_{vname}"
        status = 200 if vres.ok else 0
        save_result(out_dir, name, vres.ok, status, vparams, vres.data, verbose)
        results.append((name, vres.ok, status))
        print(f"  GET {name}: ok={vres.ok} status={status}")

    # livestream: stream 0,1,2 × protocols rtsp, rtmp, onvif, hls
    for stream_idx in [0, 1, 2]:
        for protocol in ["rtsp", "rtmp", "onvif", "hls"]:
            res = api.get_live_stream(guid, stream=stream_idx, protocol=protocol)
            status = 200 if res.ok else 0
            name = f"post_livestream_{stream_idx}_{protocol}"
            save_result(out_dir, name, res.ok, status, {"protocol": protocol}, res.data, verbose)
            results.append((name, res.ok, status))
            print(f"  POST {name}: ok={res.ok} status={status}")

    # Recording control (PUT) – probe start then stop to restore state
    start_res = api.start_recording(guid)
    save_result(out_dir, "put_mrec_start", start_res.ok, 200 if start_res.ok else 0, None, start_res.data, verbose)
    results.append(("put_mrec_start", start_res.ok, 200 if start_res.ok else 0))
    print(f"  PUT mrec/start: ok={start_res.ok}")
    stop_res = api.stop_recording(guid)
    save_result(out_dir, "put_mrec_stop", stop_res.ok, 200 if stop_res.ok else 0, None, stop_res.data, verbose)
    results.append(("put_mrec_stop", stop_res.ok, 200 if stop_res.ok else 0))
    print(f"  PUT mrec/stop: ok={stop_res.ok}")

    if ch_ok and isinstance(ch_data, dict):
        cam_res = api.get_camera_list(guid)
        if cam_res.ok and isinstance(cam_res.data, dict):
            cams = cam_res.data.get("cameraList") or cam_res.data.get("cameras") or []
            if isinstance(cams, list) and cams:
                cam0 = cams[0] if isinstance(cams[0], dict) else {}
                ch_id = cam0.get("channel_id") or cam0.get("channelId") or 0
                rec_res = api.get_recording(
                    guid, channel_id=ch_id, time_sec=now_sec - 3600,
                    pre_period=10000, post_period=5000,
                    uri_variant=f"recordingfile/{ch_id}",
                )
                status = 200 if rec_res.ok else 0
                save_result(out_dir, "recordingfile_from_camlist", rec_res.ok, status, {"channel_id": ch_id}, rec_res.data, verbose)
                results.append(("recordingfile_from_camlist", rec_res.ok, status))
                print(f"  GET recordingfile_from_camlist (ch={ch_id}): ok={rec_res.ok} status={status}")

    with open(out_dir / "summary.txt", "w") as f:
        f.write("QVR API Probe Summary (via qvr_api)\n")
        f.write("====================================\n\n")
        for name, ok, status in results:
            f.write(f"  {name}: {'OK' if ok else 'FAIL'} (HTTP {status})\n")
        f.write(f"\nTotal: {len(results)} probes\n")

    return results


def run_probes(host: str, port: int, user: str, password: str, protocol: str, out_dir: Path, verbose: bool):
    """Run full probe suite (direct HTTP)."""
    base_url = f"{protocol}://{host}:{port}"
    sid = auth_direct(host, port, user, password, protocol)
    qvr_path = get_qvrentry(host, port, protocol)

    meta = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": host,
        "port": port,
        "qvr_path": qvr_path,
        "protocol": protocol,
    }
    with open(out_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Auth OK, qvr_path={qvr_path}\n")

    # Step 1: get channels
    ch_ok, ch_data, _ = probe_get(base_url, f"{qvr_path}/qshare/StreamingOutput/channels", sid)
    channels = []
    if ch_ok and isinstance(ch_data, dict):
        ch_list = ch_data.get("channelList") or ch_data.get("channels") or []
        if isinstance(ch_list, list):
            for ch in ch_list[:5]:
                g = ch.get("guid") if isinstance(ch, dict) else None
                if g:
                    channels.append(g)

    guid = channels[0] if channels else "UNKNOWN"
    now_sec = int(time.time())
    now_ms = now_sec * 1000

    results: list[tuple[str, bool, int]] = []

    # --- GET probes ---
    get_probes = [
        ("channels", f"{qvr_path}/qshare/StreamingOutput/channels", None),
        ("channel_streams", f"{qvr_path}/qshare/StreamingOutput/channel/{guid}/streams", None),
        ("camera_list", f"{qvr_path}/camera/list", None),
        ("camera_list_guid", f"{qvr_path}/camera/list", {"guid": guid}),
        ("camera_capability", f"{qvr_path}/camera/capability", None),
        ("camera_capability_ptz", f"{qvr_path}/camera/capability", {"ptz": 1}),
        ("camera_event_capability", f"{qvr_path}/camera/capability", {"act": "get_event_capability"}),
        ("camera_capability_act_get_camera", f"{qvr_path}/camera/capability", {"act": "get_camera_capability"}),
        ("camera_capability_act_list", f"{qvr_path}/camera/capability", {"act": "list"}),
        ("camera_capability_act_get_features", f"{qvr_path}/camera/capability", {"act": "get_features"}),
        ("camera_capability_act_get_ptz", f"{qvr_path}/camera/capability", {"act": "get_ptz"}),
        ("camera_search", f"{qvr_path}/camera/search", None),
        ("logs_type1", f"{qvr_path}/logs/logs", {"log_type": 1, "max_results": 5}),
        ("logs_type2", f"{qvr_path}/logs/logs", {"log_type": 2, "max_results": 5}),
        ("logs_type3", f"{qvr_path}/logs/logs", {"log_type": 3, "max_results": 5, "global_channel_id": guid}),
        ("logs_type4", f"{qvr_path}/logs/logs", {"log_type": 4, "max_results": 5}),
        ("logs_type5", f"{qvr_path}/logs/logs", {"log_type": 5, "max_results": 5}),
        ("logs_type3_time", f"{qvr_path}/logs/logs", {
            "log_type": 3, "max_results": 10, "global_channel_id": guid,
            "start_time": now_sec - 86400, "end_time": now_sec
        }),
        # Recording variants
        ("recordingfile_time_sec", f"{qvr_path}/camera/recordingfile/{guid}/0", {
            "time": now_sec - 3600, "pre_period": 10000, "post_period": 5000
        }),
        ("recordingfile_time_ms", f"{qvr_path}/camera/recordingfile/{guid}/0", {
            "time": now_ms - 3600000, "pre_period": 10000, "post_period": 5000
        }),
        ("recordingfile_start_end", f"{qvr_path}/camera/recordingfile/{guid}/0", {
            "start_time": now_sec - 3600, "end_time": now_sec
        }),
        ("recordingfile_start_end_alt", f"{qvr_path}/camera/recordingfile/{guid}/0", {
            "start": now_sec - 3600, "end": now_sec
        }),
        ("recordingfile_ch1", f"{qvr_path}/camera/recordingfile/{guid}/1", {
            "time": now_sec - 3600, "pre_period": 10000, "post_period": 5000
        }),
        # Candidate paths (may 404)
        ("camera_recording_guid", f"{qvr_path}/camera/recording/{guid}", None),
        ("camera_recordingfile_noch", f"{qvr_path}/camera/recordingfile/{guid}", None),
        ("camera_recordings", f"{qvr_path}/camera/recordings", None),
        ("camera_events", f"{qvr_path}/camera/events", None),
        ("event_root", f"{qvr_path}/event", None),
        ("metadata_root", f"{qvr_path}/metadata", None),
        ("qshare_RecordingOutput", f"{qvr_path}/qshare/RecordingOutput", None),
        ("qshare_RecordingOutput_channels", f"{qvr_path}/qshare/RecordingOutput/channels", None),
        ("camera_search_with_time", f"{qvr_path}/camera/search", {
            "start_time": now_sec - 86400, "end_time": now_sec
        }),
        ("recordingfile_ch2", f"{qvr_path}/camera/recordingfile/{guid}/2", {
            "time": now_sec - 3600, "pre_period": 10000, "post_period": 5000
        }),
        ("logs_type3_level_info", f"{qvr_path}/logs/logs", {
            "log_type": 3, "max_results": 5, "level": "info",
            "global_channel_id": guid,
        }),
    ]

    for name, path, params in get_probes:
        ok, data, status = probe_get(base_url, path, sid, params)
        save_result(out_dir, name, ok, status, params, data, verbose)
        results.append((name, ok, status))
        print(f"  GET {name}: ok={ok} status={status}")

    # --- Capability per-guid (all variants) ---
    cap_path = f"{qvr_path}/camera/capability"
    for vname, vparams in [
        ("default", {}),
        ("ptz_0", {"ptz": 0}),
        ("ptz_1", {"ptz": 1}),
        ("act_get_camera_capability", {"act": "get_camera_capability"}),
        ("act_get_event_capability", {"act": "get_event_capability"}),
        ("act_list", {"act": "list"}),
        ("act_get_features", {"act": "get_features"}),
        ("act_get_ptz", {"act": "get_ptz"}),
    ]:
        p = dict(vparams)
        p["guid"] = guid
        ok, data, status = probe_get(base_url, cap_path, sid, p)
        name = f"capability_per_guid_{vname}"
        save_result(out_dir, name, ok, status, p, data, verbose)
        results.append((name, ok, status))
        print(f"  GET {name}: ok={ok} status={status}")

    # --- POST: liveStream (stream 0,1,2 × protocols rtsp, rtmp, onvif, hls) ---
    for stream_idx in [0, 1, 2]:
        for protocol in ["rtsp", "rtmp", "onvif", "hls"]:
            ok, data, status = probe_post(
                base_url,
                f"{qvr_path}/qshare/StreamingOutput/channel/{guid}/stream/{stream_idx}/liveStream",
                sid,
                {"protocol": protocol},
            )
            name = f"post_livestream_{stream_idx}_{protocol}"
            save_result(out_dir, name, ok, status, {"protocol": protocol}, data, verbose)
            results.append((name, ok, status))
            print(f"  POST {name}: ok={ok} status={status}")

    # --- PUT: mrec start/stop ---
    def probe_put(path: str, params: dict | None = None) -> tuple[bool, object, int]:
        url = f"{base_url}{path}"
        p = (params or {}) | {"sid": sid, "ver": "1.1.0"}
        try:
            r = requests.put(url, params=p, timeout=30, verify=False)
            ct = r.headers.get("content-type", "")
            if "application/json" in ct and r.text:
                return r.ok, r.json(), r.status_code
            return r.ok, (r.text[:500] if r.text else ""), r.status_code
        except Exception as e:
            return False, {"error": str(e)}, 0

    for put_name, put_path in [
        ("put_mrec_start", f"{qvr_path}/camera/mrec/{guid}/start"),
        ("put_mrec_stop", f"{qvr_path}/camera/mrec/{guid}/stop"),
    ]:
        ok, data, status = probe_put(put_path)
        save_result(out_dir, put_name, ok, status, None, data, verbose)
        results.append((put_name, ok, status))
        print(f"  PUT {put_name}: ok={ok} status={status}")

    # --- Multi-step: extract channel_id from camera_list ---
    if ch_ok and isinstance(ch_data, dict):
        cam_list_ok, cam_data, _ = probe_get(base_url, f"{qvr_path}/camera/list", sid, {"guid": guid})
        if cam_list_ok and isinstance(cam_data, dict):
            # Try recordingfile with channel_id from camera_list if available
            cams = cam_data.get("cameraList") or cam_data.get("cameras") or []
            if isinstance(cams, list) and cams:
                cam0 = cams[0] if isinstance(cams[0], dict) else {}
                ch_id = cam0.get("channel_id") or cam0.get("channelId") or 0
                ok, data, status = probe_get(
                    base_url,
                    f"{qvr_path}/camera/recordingfile/{guid}/{ch_id}",
                    sid,
                    {"time": now_sec - 3600, "pre_period": 10000, "post_period": 5000},
                    timeout=120,
                )
                save_result(out_dir, "recordingfile_from_camlist", ok, status, {"channel_id": ch_id}, data, verbose)
                results.append(("recordingfile_from_camlist", ok, status))
                print(f"  GET recordingfile_from_camlist (ch={ch_id}): ok={ok} status={status}")

    # --- Summary ---
    with open(out_dir / "summary.txt", "w") as f:
        f.write("QVR API Probe Summary\n")
        f.write("====================\n\n")
        for name, ok, status in results:
            f.write(f"  {name}: {'OK' if ok else 'FAIL'} (HTTP {status})\n")
        f.write(f"\nTotal: {len(results)} probes\n")

    return results


def main():
    ap = argparse.ArgumentParser(description="QVR API full probe")
    ap.add_argument("--output", "-o", default="probe_output", help="Output directory")
    ap.add_argument("--host", default=os.environ.get("QVR_HOST", "10.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("QVR_PORT", "8080")))
    ap.add_argument("--user", default=os.environ.get("QVR_USER", "admin"))
    ap.add_argument("--protocol", default="http")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--use-library", action="store_true", help="Use qvr_api wrapper instead of direct HTTP")
    args = ap.parse_args()
    password = os.environ.get("QVR_PASS")
    if not password:
        print("Set QVR_PASS env var")
        sys.exit(1)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.use_library:
        run_probes_via_library(args.host, args.port, args.user, password, args.protocol, out_dir, args.verbose)
    else:
        run_probes(args.host, args.port, args.user, password, args.protocol, out_dir, args.verbose)
    print(f"\nSaved to {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

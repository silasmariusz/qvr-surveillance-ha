#!/usr/bin/env python3
"""Test eventow dla timeline ACC. Weryfikuje format get_logs -> _map_logs_to_events.
Uruchom: QVR_PASS=xxx python test_timeline_events.py
Opcje: --camera GUID, --dump-events (zapis JSON)
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

EVENT_TYPES = (
    "alarm_input", "alarm_input_manual", "alarm_pir", "alarm_pir_manual",
    "alarm_output", "iva_crossline_manual", "iva_audio_detected_manual",
    "iva_tampering_detected_manual", "iva_intrusion_detected",
    "iva_intrusion_detected_manual", "iva_digital_autotrack_manual",
    "camera_motion", "motion_manual",
)


def auth():
    url = f"{BASE}/cgi-bin/authLogin.cgi"
    pwd_b64 = base64.b64encode(PASS.encode("ascii")).decode("ascii")
    r = requests.get(url, params={"user": USER, "pwd": pwd_b64, "serviceKey": 1, "verify": 0}, timeout=15, verify=VERIFY_SSL)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    if int(root.find(".//authPassed").text or 0) != 1:
        raise RuntimeError("Authentication failed")
    sid = root.find(".//authSid").text or ""
    qvr_uri = "/qvrsurveillance"
    try:
        re = requests.get(f"{BASE}/qvrentry", timeout=10, verify=VERIFY_SSL)
        data = re.json() if re.ok else {}
        if data.get("fw_web_ui_prefix"):
            qvr_uri = f"/{data['fw_web_ui_prefix'].strip('/') or 'qvrpro'}"
        elif data.get("is_qvp") == "yes":
            qvr_uri = "/qvrpro"
    except Exception:
        pass
    return sid, qvr_uri


def qvr_get(sid, path, params=None):
    p = dict(params) if params else {}
    p["sid"] = sid
    p["ver"] = "1.1.0"
    r = requests.get(f"{BASE}{path}", params=p, timeout=30, verify=VERIFY_SSL)
    return r.json() if "application/json" in r.headers.get("content-type", "") else {}


def map_logs_to_events(raw_logs, camera_guid):
    events = []
    for i, entry in enumerate(raw_logs):
        if not isinstance(entry, dict):
            continue
        meta = entry.get("metadata") or {}
        event_type = meta.get("event_name") or entry.get("type") or entry.get("event_type") or "surveillance"
        if isinstance(event_type, str):
            event_type = event_type.strip().lower()
        ts = entry.get("time") or entry.get("timestamp")
        if ts is None:
            utc = entry.get("UTC_time") or entry.get("UTC_time_s")
            if utc is not None:
                u = int(utc)
                ts = u // 1000 if u > 1e12 else u
            else:
                ts = 0
        ts = int(ts) if isinstance(ts, (int, float)) else 0
        if ts > 1e12:
            ts = ts // 1000
        events.append({
            "id": entry.get("id") or entry.get("log_id") or f"{camera_guid}_{i}_{ts}",
            "time": ts,
            "message": entry.get("message") or entry.get("content") or "",
            "type": str(event_type),
        })
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", default=None)
    ap.add_argument("--dump-events", action="store_true")
    ap.add_argument("--max", type=int, default=50)
    args = ap.parse_args()

    if not PASS:
        print("Ustaw QVR_PASS (env)")
        return 1

    sid, qvr_uri = auth()
    print(f"Auth OK, qvr_uri={qvr_uri}")

    ch_resp = qvr_get(sid, f"{qvr_uri}/qshare/StreamingOutput/channels")
    ch_raw = ch_resp.get("channels") or ch_resp.get("channel") or []
    if isinstance(ch_raw, dict):
        ch_raw = list(ch_raw.values()) if ch_raw else []
    cameras = [(c.get("guid", ""), c.get("name", "") or f"Ch{c.get('channel_index', 0)}") for c in ch_raw if c.get("guid")]

    if not cameras:
        print("Brak kamer")
        return 1

    guid = args.camera or cameras[0][0]
    since = int(time.time()) - 86400

    logs = qvr_get(sid, f"{qvr_uri}/logs/logs", {
        "log_type": 3, "start_time": since, "max_results": args.max,
        "sort_field": "time", "dir": "DESC", "global_channel_id": guid,
    })
    raw = logs.get("logs") or logs.get("log") or logs.get("items") or []
    if isinstance(raw, dict):
        raw = list(raw.values()) if raw else []

    events = map_logs_to_events(raw, guid)
    print(f"raw_logs={len(raw)} events={len(events)}")
    if events:
        for i, ev in enumerate(events[:5]):
            ts_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(ev["time"])) if ev["time"] else "?"
            print(f"  [{i}] id={ev.get('id','')[:20]}... time={ev['time']} ({ts_str}) type={ev.get('type')}")
        if args.dump_events:
            with open(f"timeline_events_{int(time.time())}.json", "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
            print("Zapisano JSON")
    print("\nTimeline ACC: events_media_type = all lub snapshots (nie clips)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

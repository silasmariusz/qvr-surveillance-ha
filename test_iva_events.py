#!/usr/bin/env python3
"""
Diagnostyka IVA/eventów QVR – sprawdza co raportują sensory i timeline.

Uruchom: QVR_PASS=xxx python test_iva_events.py
         Opcjonalnie: QVR_HOST, QVR_PORT (domyślnie 10.100.200.10:38080)
"""
from __future__ import annotations

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
    """Auth + discover qvr_uri (qvrsurveillance/qvrpro)."""
    url = f"{BASE}/cgi-bin/authLogin.cgi"
    pwd_b64 = base64.b64encode(PASS.encode("ascii")).decode("ascii")
    params = {"user": USER, "pwd": pwd_b64, "serviceKey": 1, "verify": 0}
    r = requests.get(url, params=params, timeout=15, verify=VERIFY_SSL)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    auth_passed = root.find(".//authPassed")
    auth_sid = root.find(".//authSid")
    if auth_passed is None or auth_sid is None or int(auth_passed.text or 0) != 1:
        raise RuntimeError("Authentication failed")
    sid = auth_sid.text or ""

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


def qvr_get(sid: str, path: str, params: dict | None = None) -> dict | bytes:
    url = f"{BASE}{path}"
    p = dict(params) if params else {}
    p["sid"] = sid
    p["ver"] = "1.1.0"
    r = requests.get(url, params=p, timeout=30, verify=VERIFY_SSL)
    ct = r.headers.get("content-type", "")
    if "application/json" in ct:
        return r.json()
    return r.content


def main() -> int:
    if not PASS:
        print("Ustaw QVR_PASS (np. QVR_PASS=xxx python test_iva_events.py)")
        return 1

    print("=" * 70)
    print(f"QVR IVA Events Diagnostic: {HOST}:{PORT}")
    print("=" * 70)

    try:
        sid, qvr_uri = auth()
        print(f"\n1. Auth OK, path={qvr_uri}")
    except Exception as e:
        print(f"\n1. Auth FAILED: {e}")
        return 1

    # Channels
    ch_resp = qvr_get(sid, f"{qvr_uri}/qshare/StreamingOutput/channels")
    if not isinstance(ch_resp, dict):
        print("\n2. Channel list: nie JSON")
        return 1

    ch_raw = ch_resp.get("channels") or ch_resp.get("channel") or []
    if isinstance(ch_raw, dict):
        ch_raw = list(ch_raw.values()) if ch_raw else []
    if not ch_raw:
        print("\n2. Brak kanałów")
        return 1

    cameras = [(c.get("guid", ""), c.get("channel_name") or c.get("name") or f"Ch{c.get('channel_index', 0)}") for c in ch_raw if c.get("guid")]
    print(f"\n2. Kamery ({len(cameras)}):")
    for i, (guid, name) in enumerate(cameras):
        print(f"   [{i}] {name[:30]:30} guid={guid[:24]}...")

    # Event capability (IVAs włączone)
    print("\n3. Event capability (IVAs/Alarm na kamerach):")
    try:
        cap = qvr_get(sid, f"{qvr_uri}/camera/capability", {"act": "get_event_capability"})
        if isinstance(cap, dict):
            for key, val in sorted(cap.items()):
                if isinstance(val, dict):
                    guids = val.get("guids", [])
                    name = val.get("name", key)
                    print(f"   {key}: {name} – guids={len(guids) if guids else 0}")
                elif isinstance(val, list):
                    total = sum(1 for x in val if isinstance(x, dict) and x.get("guids")) if val else 0
                    print(f"   {key}: list[{len(val)}], items z guids: {total}")
        else:
            print("   (brak lub nie JSON)")
    except Exception as e:
        print(f"   Błąd: {e}")

    # Logi Surveillance (log_type=3)
    since_ts = int(time.time()) - 86400  # ostatnie 24h
    print(f"\n4. Logi Surveillance (log_type=3, od ts={since_ts}):")

    for guid, name in cameras[:2]:  # max 2 kamery
        try:
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
            if isinstance(logs, dict):
                raw = logs.get("logs") or logs.get("log") or logs.get("items") or logs.get("data") or []
                if isinstance(raw, dict):
                    raw = list(raw.values()) if raw else []
                print(f"\n   Kamera: {name}")
                print(f"   Zdarzenia: {len(raw)}")
                for j, entry in enumerate(raw[:5]):
                    if isinstance(entry, dict):
                        ts = entry.get("time") or entry.get("timestamp") or entry.get("UTC_time") or "-"
                        evt = entry.get("metadata", {}).get("event_name") or entry.get("type") or entry.get("event_type") or "?"
                        msg = (entry.get("message") or entry.get("content") or "")[:60]
                        print(f"      [{j}] ts={ts} type={evt} msg={msg!r}")
                if len(raw) > 5:
                    print(f"      ... +{len(raw)-5} więcej")
            else:
                print(f"   {name}: odpowiedź nie JSON")
        except Exception as e:
            print(f"   {name}: błąd {e}")

    # Bez global_channel_id (wszystkie eventy)
    print("\n5. Logi łącznie (bez filtra kamery, max 20):")
    try:
        logs_all = qvr_get(
            sid,
            f"{qvr_uri}/logs/logs",
            {
                "log_type": 3,
                "start_time": since_ts,
                "max_results": 20,
                "sort_field": "time",
                "dir": "DESC",
            },
        )
        if isinstance(logs_all, dict):
            raw = logs_all.get("logs") or logs_all.get("log") or logs_all.get("items") or []
            if isinstance(raw, dict):
                raw = list(raw.values()) if raw else []
            print(f"   Łącznie zdarzeń: {len(raw)}")
            for j, entry in enumerate(raw[:8]):
                if isinstance(entry, dict):
                    gcid = entry.get("global_channel_id") or entry.get("channel_id") or "?"
                    evt = (entry.get("metadata") or {}).get("event_name") or entry.get("type") or "?"
                    ts = entry.get("time") or entry.get("timestamp") or "-"
                    print(f"      [{j}] channel={str(gcid)[:20]}... type={evt} ts={ts}")
        else:
            print("   Odpowiedź nie JSON")
    except Exception as e:
        print(f"   Błąd: {e}")

    print("\n" + "=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

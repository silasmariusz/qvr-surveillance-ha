#!/usr/bin/env python3
"""
Probe nagrań QVR – przedział ciągły vs detekcja ruchu.

Na podstawie timeline z QVR Client (np. 2026-03-02):
- Niebieski pasek 00:00–04:30 = nagrywanie ciągłe
- Czerwone linie od ~12:00 = nagrywanie z detekcji ruchu

Wykonuje różne zapytania API (time, start/end, start_time/end_time, rec_type?)
aby uzyskać nagrania dla obu przedziałów.

Uruchom: QVR_PASS=xxx python tools/probe_recording_intervals.py
         QVR_PASS=xxx QVR_DATE=2026-03-02 python tools/probe_recording_intervals.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

import xml.etree.ElementTree as ET

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "custom_components" / "qvr_surveillance"))

# === CONFIG ===
HOST = os.environ.get("QVR_HOST", "10.100.200.10")
PORT = int(os.environ.get("QVR_PORT", "38080"))
USER = os.environ.get("QVR_USER", "admin")
PASS = os.environ.get("QVR_PASS", "")
PROTOCOL = os.environ.get("QVR_PROTOCOL", "http")
VERIFY_SSL = False
# Data z timeline (2026-03-02)
TEST_DATE = os.environ.get("QVR_DATE", "2026-03-02")

# Przedziały z timeline (opis z załączonego screenshot)
INTERVAL_CONTINUOUS = {"name": "continuous", "start": "00:00", "end": "04:30"}
INTERVAL_MOTION = {"name": "motion", "start": "12:00", "end": "14:00"}

BASE = f"{PROTOCOL}://{HOST}:{PORT}"


def auth(sid_cache: list) -> str:
    """QNAP auth. sid_cache[0] = last sid."""
    url = f"{BASE}/cgi-bin/authLogin.cgi"
    pwd_b64 = base64.b64encode(PASS.encode("ascii")).decode("ascii")
    for verify_param in (0, 1):
        params = {"user": USER, "pwd": pwd_b64, "serviceKey": 1, "verify": verify_param}
        r = requests.get(url, params=params, timeout=15, verify=VERIFY_SSL)
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "").lower()
        raw = r.text or r.content.decode("utf-8", errors="replace")
        if "application/json" in ct or raw.strip().startswith("{"):
            try:
                data = r.json()
                sid = data.get("sid") or data.get("authSid") or ""
                if data.get("status") == 1 and sid:
                    sid_cache[0] = sid
                    return sid
            except Exception:
                pass
        try:
            root = ET.fromstring(r.content)
            for tag in ("authSid", "sid"):
                el = root.find(f".//{tag}")
                if el is not None and el.text and el.text.strip():
                    passed = root.find(".//authPassed")
                    if passed is not None and int(passed.text or 0) == 1:
                        sid_cache[0] = el.text.strip()
                        return el.text.strip()
        except ET.ParseError:
            pass
    raise RuntimeError("Auth failed")


def qvr_get(sid: str, path: str, params: dict | None = None, timeout: int = 120) -> dict | bytes | str:
    """GET na API QVR."""
    url = f"{BASE}{path}"
    p = dict(params) if params else {}
    p["sid"] = sid
    p["ver"] = "1.1.0"
    r = requests.get(url, params=p, timeout=timeout, verify=VERIFY_SSL)
    ct = r.headers.get("content-type", "")
    if "application/json" in ct:
        return r.json()
    if "image/" in ct or "video/" in ct:
        return r.content
    return r.text or ""


def parse_interval(date_str: str, start_hhmm: str, end_hhmm: str) -> tuple[int, int]:
    """Parse date and time to Unix timestamps."""
    parts = date_str.split("-")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    sh, sm = map(int, start_hhmm.split(":"))
    eh, em = map(int, end_hhmm.split(":"))
    dt_start = datetime(y, m, d, sh, sm, 0, tzinfo=timezone.utc)
    dt_end = datetime(y, m, d, eh, em, 0, tzinfo=timezone.utc)
    return int(dt_start.timestamp()), int(dt_end.timestamp())


def probe_recording(
    sid: str, qvr_uri: str, guid: str,
    start_ts: int, end_ts: int,
    params_extra: dict | None = None,
) -> list[tuple[str, dict, str, int | None]]:
    """Probe różne warianty zapytania. Zwraca [(variant_name, params, result_type, size)]."""
    duration_sec = end_ts - start_ts
    duration_ms = duration_sec * 1000
    pre_ms = duration_ms // 2
    post_ms = duration_ms - pre_ms
    mid_ts = start_ts + duration_sec // 2

    param_sets = [
        ("time_sec+pre_post", {"time": start_ts, "pre_period": duration_ms, "post_period": 0}),
        ("time_sec_center", {"time": mid_ts, "pre_period": pre_ms, "post_period": post_ms}),
        ("time_ms_center", {"time": mid_ts * 1000, "pre_period": pre_ms, "post_period": post_ms}),
        ("start_end", {"start": start_ts, "end": end_ts}),
        ("start_time_end_time", {"start_time": start_ts, "end_time": end_ts}),
    ]

    uris = [
        f"{qvr_uri}/camera/recordingfile/{guid}/0",
        f"{qvr_uri}/camera/recordingfile/{guid}/1",
        f"{qvr_uri}/camera/recording/{guid}",
    ]

    results = []
    extra = params_extra or {}
    for uri in uris:
        for pname, p in param_sets:
            params = dict(p)
            params.update(extra)
            try:
                resp = qvr_get(sid, uri, params=params, timeout=180)
                rtype = "bytes" if isinstance(resp, bytes) else "dict" if isinstance(resp, dict) else "str"
                size = len(resp) if isinstance(resp, (bytes, str)) else None
                if isinstance(resp, dict):
                    size = None
                    if resp.get("resourceUris") or resp.get("url"):
                        ru = resp.get("resourceUris") or resp.get("url")
                        if isinstance(ru, (list, tuple)) and ru:
                            size = len(str(ru[0]))
                        else:
                            size = len(str(ru)) if ru else 0
                results.append((f"{uri.split('/')[-1]} {pname}", params, rtype, size))
            except Exception as e:
                results.append((f"{uri.split('/')[-1]} {pname}", params, f"err:{e}", None))
    return results


def main() -> int:
    if not PASS:
        print("Ustaw QVR_PASS")
        return 1

    sid_cache = [""]
    out_dir = Path("probe_intervals_output")
    out_dir.mkdir(exist_ok=True)

    print("=" * 70)
    print("QVR Probe: nagrywanie ciągłe vs detekcja ruchu")
    print(f"Host: {HOST}:{PORT}, Data: {TEST_DATE}")
    print("=" * 70)

    # qvrentry
    qvr_uri = "/qvrpro"
    try:
        r = requests.get(f"{BASE}/qvrentry", timeout=10, verify=VERIFY_SSL)
        data = r.json() if r.ok and "json" in (r.headers.get("content-type") or "") else {}
        if data.get("fw_web_ui_prefix"):
            p = data["fw_web_ui_prefix"].strip("/") or "qvrpro"
            qvr_uri = f"/{p}"
        elif data.get("is_qvp") == "yes":
            qvr_uri = "/qvrpro"
        print(f"\nqvr_uri: {qvr_uri}")
    except Exception as e:
        print(f"qvrentry err: {e}")

    # Auth
    try:
        sid = auth(sid_cache)
        print(f"Auth OK sid={sid[:12]}...")
    except Exception as e:
        print(f"Auth FAILED: {e}")
        return 1

    # Channels
    ch_resp = qvr_get(sid, f"{qvr_uri}/qshare/StreamingOutput/channels")
    if not isinstance(ch_resp, dict):
        print("Channels: not JSON")
        return 1
    ch_raw = ch_resp.get("channels") or ch_resp.get("channelList") or ch_resp.get("channel") or []
    if isinstance(ch_raw, dict):
        ch_raw = list(ch_raw.values()) if ch_raw else []
    if not ch_raw:
        print("Channels: empty")
        return 1
    guid = ch_raw[0].get("guid", "")
    print(f"Camera[0] guid: {guid[:24]}...")

    # Przedziały
    intervals = [
        (INTERVAL_CONTINUOUS["name"], *parse_interval(
            TEST_DATE, INTERVAL_CONTINUOUS["start"], INTERVAL_CONTINUOUS["end"]
        )),
        (INTERVAL_MOTION["name"], *parse_interval(
            TEST_DATE, INTERVAL_MOTION["start"], INTERVAL_MOTION["end"]
        )),
    ]

    all_results = {}
    for name, start_ts, end_ts in intervals:
        iv = INTERVAL_CONTINUOUS if name == "continuous" else INTERVAL_MOTION
        print(f"\n--- {name.upper()} ({iv['start']} - {iv['end']}) ---")
        print(f"   {start_ts} .. {end_ts} ({end_ts - start_ts}s)")
        results = probe_recording(sid, qvr_uri, guid, start_ts, end_ts)
        all_results[name] = results
        for rname, params, rtype, size in results:
            status = f"{rtype}"
            if size is not None and size > 100:
                status += f" {size} bytes"
            print(f"   {rname}: {status}")

    # Probe rec_type / recording_type (może 404)
    print("\n--- PARAMETRY rec_type / recording_type (candidate) ---")
    for name, start_ts, end_ts in intervals:
        for param_name, param_val in [("rec_type", "continuous"), ("rec_type", "motion"), ("recording_type", 0), ("recording_type", 1)]:
            try:
                r = qvr_get(sid, f"{qvr_uri}/camera/recordingfile/{guid}/0", {
                    "start_time": start_ts, "end_time": end_ts,
                    param_name: param_val,
                }, timeout=60)
                ok = isinstance(r, bytes) and len(r) > 100 or (
                    isinstance(r, dict) and (r.get("resourceUris") or r.get("url"))
                )
                print(f"   {name} {param_name}={param_val}: {'OK' if ok else type(r).__name__}")
            except Exception as e:
                print(f"   {name} {param_name}={param_val}: err {e}")

    # Zapisz wyniki
    ts = int(time.time())
    summary = {
        "date": TEST_DATE,
        "intervals": {
            "continuous": {"start": INTERVAL_CONTINUOUS["start"], "end": INTERVAL_CONTINUOUS["end"]},
            "motion": {"start": INTERVAL_MOTION["start"], "end": INTERVAL_MOTION["end"]},
        },
        "results": {
            k: [(r[0], r[2], r[3]) for r in v]
            for k, v in all_results.items()
        },
    }
    with open(out_dir / f"summary_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nZapisano: {out_dir}/summary_{ts}.json")

    print("\n" + "=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

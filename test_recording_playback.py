#!/usr/bin/env python3
"""
Test symulacji odtwarzania nagrań QVR – sprawdza czy można dostać się do pliku.

Przepływ: API get_recording -> jeśli resourceUris: pobierz URL -> zapisz do pliku.

Uruchom: QVR_PASS=xxx python test_recording_playback.py
         Opcjonalnie: QVR_HOST, QVR_PORT, QVR_USER, QVR_DATE (YYYY-MM-DD)
"""
from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

# === CONFIG ===
HOST = os.environ.get("QVR_HOST", "10.100.200.10")
PORT = int(os.environ.get("QVR_PORT", "38080"))
USER = os.environ.get("QVR_USER", "admin")
PASS = os.environ.get("QVR_PASS", "")
PROTOCOL = os.environ.get("QVR_PROTOCOL", "http")
VERIFY_SSL = False
# Data nagrania do testu (domyślnie 2026-03-02 00:00 UTC)
TEST_DATE = os.environ.get("QVR_DATE", "2026-03-02")
TEST_HOUR = int(os.environ.get("QVR_HOUR", "0"))
OUTPUT_FILE = os.environ.get("QVR_OUTPUT", "recording_test_output.mp4")

BASE = f"{PROTOCOL}://{HOST}:{PORT}"


def auth() -> str:
    """QNAP auth, zwraca session id."""
    url = f"{BASE}/cgi-bin/authLogin.cgi"
    pwd_b64 = base64.b64encode(PASS.encode("ascii")).decode("ascii")
    params = {"user": USER, "pwd": pwd_b64, "serviceKey": 1, "verify": 0}
    r = requests.get(url, params=params, timeout=15, verify=VERIFY_SSL)
    r.raise_for_status()
    import xml.etree.ElementTree as ET
    root = ET.fromstring(r.content)
    auth_passed = root.find(".//authPassed")
    auth_sid = root.find(".//authSid")
    if auth_passed is None or auth_sid is None:
        raise RuntimeError(f"No auth response. Raw: {r.text[:300]}")
    if int(auth_passed.text or 0) != 1:
        raise RuntimeError("Authentication failed")
    return auth_sid.text or ""


def qvr_get(sid: str, path: str, params: dict | None = None) -> dict | bytes:
    """GET na API QVR."""
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
        print("Ustaw QVR_PASS (np. QVR_PASS=xxx python test_recording_playback.py)")
        return 1

    # Timestamp dla TEST_DATE TEST_HOUR:00 UTC
    parts = TEST_DATE.split("-")
    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    dt = datetime(year, month, day, TEST_HOUR, 0, 0, tzinfo=timezone.utc)
    start_ts = int(dt.timestamp())
    end_ts = start_ts + 3600  # 1h
    duration_ms = 3600 * 1000
    pre_period = duration_ms // 2
    post_period = duration_ms - pre_period

    print("=" * 60)
    print(f"QVR Recording Playback Test: {HOST}:{PORT}")
    print(f"Data: {TEST_DATE} {TEST_HOUR:02d}:00 UTC (ts={start_ts})")
    print("=" * 60)

    # 1. qvrentry – discover path
    print("\n1. /qvrentry")
    qvr_uri = "/qvrpro"
    try:
        r = requests.get(f"{BASE}/qvrentry", timeout=10, verify=VERIFY_SSL)
        data = r.json() if r.ok and "json" in r.headers.get("content-type", "") else {}
        if data.get("fw_web_ui_prefix"):
            p = data["fw_web_ui_prefix"].strip("/") or "qvrpro"
            qvr_uri = f"/{p}"
        elif data.get("is_qvp") == "yes":
            qvr_uri = "/qvrpro"
        print(f"   Path: {qvr_uri}")
    except Exception as e:
        print(f"   Default /qvrpro, err: {e}")

    # 2. Auth
    print("\n2. Auth")
    try:
        sid = auth()
        print(f"   OK sid={sid[:16]}...")
    except Exception as e:
        print(f"   FAILED: {e}")
        return 1

    # 3. Channel list
    print("\n3. Channel list")
    ch_resp = qvr_get(sid, f"{qvr_uri}/qshare/StreamingOutput/channels")
    if not isinstance(ch_resp, dict):
        print("   Nie JSON")
        return 1
    ch_raw = ch_resp.get("channels") or ch_resp.get("channel") or []
    if isinstance(ch_raw, dict):
        ch_raw = list(ch_raw.values()) if ch_raw else []
    if not ch_raw:
        print("   Brak kanałów")
        return 1
    guid = ch_raw[0].get("guid", "")
    print(f"   Kanały: {len(ch_raw)}, GUID[0]: {guid[:20]}...")

    # 4. get_recording – próbujemy kilka wariantów
    params_sets = [
        {"time": start_ts, "pre_period": pre_period, "post_period": post_period},
        {"time": start_ts * 1000, "pre_period": pre_period, "post_period": post_period},
        {"start": start_ts, "end": end_ts},
        {"start_time": start_ts, "end_time": end_ts},
    ]
    uris = [
        f"{qvr_uri}/camera/recordingfile/{guid}/0",
        f"{qvr_uri}/camera/recordingfile/{guid}/1",
        f"{qvr_uri}/camera/recording/{guid}",
        f"/qvrsurveillance/camera/recordingfile/{guid}/0",
        f"/qvrsurveillance/camera/recording/{guid}",
    ]

    response = None
    used_uri, used_params = None, None

    print("\n4. get_recording (próby URI × parametry)")
    for uri in uris:
        for params in params_sets:
            try:
                resp = qvr_get(sid, uri, params=params)
                if isinstance(resp, bytes) and len(resp) > 100:
                    response = resp
                    used_uri, used_params = uri, params
                    print(f"   OK! BINARY {uri} -> {len(resp)} bytes")
                    break
                if isinstance(resp, dict) and (resp.get("resourceUris") or resp.get("url")):
                    response = resp
                    used_uri, used_params = uri, params
                    ru = resp.get("resourceUris") or resp.get("url")
                    if isinstance(ru, (list, tuple)):
                        ru = ru[0] if ru else ""
                    print(f"   OK! resourceUris {uri} -> {str(ru)[:80]}...")
                    break
            except Exception as e:
                print(f"   {uri} {list(params.keys())} -> {e}")
        if response is not None:
            break

    if response is None:
        print("\n   Wszystkie próby failed. API recording nie zwraca danych.")
        return 1

    # 5. Jeśli response to dict z resourceUris – pobierz plik
    body = None
    if isinstance(response, bytes):
        body = response
        print(f"\n5. Odpowiedź była binarna, len={len(body)}")
    elif isinstance(response, dict):
        resource_uri = response.get("resourceUris") or response.get("url")
        if isinstance(resource_uri, (list, tuple)) and resource_uri:
            resource_uri = resource_uri[0]
        if resource_uri:
            print(f"\n5. Pobieranie resourceUris: {resource_uri[:100]}...")
            if not resource_uri.startswith("http"):
                url = f"{BASE}{resource_uri}" if resource_uri.startswith("/") else f"{BASE}/{resource_uri}"
            else:
                url = resource_uri
            parsed = urlparse(url)
            auth_str = f"{USER}:{PASS}"
            if auth_str and "@" not in parsed.netloc:
                url = f"{parsed.scheme}://{auth_str}@{parsed.netloc}{parsed.path or '/'}"
                if parsed.query:
                    url += f"?{parsed.query}"
            sep = "&" if "?" in url else "?"
            url += f"{sep}sid={sid}&ver=1.1.0"
            try:
                r = requests.get(url, timeout=120, verify=VERIFY_SSL)
                print(f"   Fetch status: {r.status_code}, len={len(r.content)}")
                if r.status_code == 200 and len(r.content) > 100:
                    body = r.content
                else:
                    print(f"   Treść (początek): {r.text[:400] if r.text else r.content[:200]}")
            except Exception as e:
                print(f"   FAILED fetch: {e}")
        else:
            print("\n5. Brak resourceUris w odpowiedzi")
            return 1
    else:
        print("\n5. Nieobsługiwany typ odpowiedzi")
        return 1

    # 6. Zapis do pliku i walidacja
    if not body or len(body) < 100:
        print(f"\n6. Brak danych do zapisu (len={len(body) if body else 0})")
        return 1

    with open(OUTPUT_FILE, "wb") as f:
        f.write(body)

    # MP4 magic: ftyp (bytes 4–8) lub moov
    is_video = body[:12].find(b"ftyp") >= 0 or body[:20].find(b"moov") >= 0
    print(f"\n6. Zapisano: {OUTPUT_FILE} ({len(body)} bytes)")
    print(f"   Wygląda na wideo (ftyp/moov): {is_video}")
    if not is_video and body[:50]:
        print(f"   Początek hex: {body[:32].hex()}")

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

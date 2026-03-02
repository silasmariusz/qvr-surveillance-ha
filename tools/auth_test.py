#!/usr/bin/env python3
"""Quick auth test - run: QVR_PASS=xxx python tools/auth_test.py"""
import base64
import os
import sys
import xml.etree.ElementTree as ET
import requests

pwd = os.environ.get("QVR_PASS", "")
if not pwd:
    print("Set QVR_PASS"); sys.exit(2)
b64 = base64.b64encode(pwd.encode()).decode()
url = "http://10.100.200.10:38080/cgi-bin/authLogin.cgi"
params = {"user": "admin", "pwd": b64, "serviceKey": 1, "verify": 0}

r = requests.get(url, params=params, timeout=10, verify=False)
print("Status:", r.status_code)
print("Raw (first 600):", r.text[:600] if r.text else "")

root = ET.fromstring(r.content)
ap = root.find(".//authPassed")
am = root.find(".//authMessage")
asid = root.find(".//authSid")
print("\nParsed: authPassed=%s authMessage=%s authSid=%s" % (
    ap.text if ap is not None else "None",
    am.text if am is not None else "None",
    (asid.text[:24] + "...") if asid is not None and asid.text else "None"
))
sys.exit(0 if (ap is not None and ap.text == "1" and asid is not None) else 1)

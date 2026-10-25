#!/usr/bin/env python3
"""Supply a local boot document for the unchanged captured account application."""
import base64
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REVISION = "d964d4f8766900778d7282f4b26521146f6d2785"
base = "/cdn/web/account/" + REVISION + "/"
source = (ROOT / "capture/login.html").read_text()
flags = json.loads(re.search(r"var featureFlagsJson = (\{.*?\})\s*var experimentsJson", source, re.S)[1])
for key in flags:
    if any(part in key for part in ("datadog", "enable-sid", "enable-sitm", "enable-tm", "risk-signal", "conversion-tracking", "one-trust", "wait-for-sid")):
        flags[key] = {"sessionSampleRateOverride": 0} if "config" in key else False
flags.update({
    "cash-web-account-address-autocomplete": False,
    "cash-web-get-profile-migration": False,
    "cash-web-account-sam": "DISABLED",
    "cash-web-account-paychecks": "DISABLED",
    "cash-web-account-genie-scenes": False,
    "cash-web-account-savings-nux": False,
    "cash-web-account-settings-show-devices": False,
    "cash-web-device-details-endpoint": False,
    "cash-web-account-webmcp": False,
    "cash-web-account-janus-contact-aliases": False,
    "cash-web-account-show-restricted-balance": False,
})
styles = "\n".join(re.findall(r"<style[^>]*>.*?</style>", source, re.S)).replace("https://cash-f.squarecdn.com", "/cdn")
scripts = []
for name in ("runtime.a1ea354b43d18d7c.js", "main.fa6baaec96a82623.js"):
    data = (ROOT / "capture/cdn/web/account" / REVISION / name).read_bytes()
    integrity = "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()
    scripts.append('<script defer src="' + base + name + '" integrity="' + integrity + '" crossorigin="anonymous"></script>')
html = """<!doctype html><html lang="en-US"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cashlarp</title>
<meta name="public-path" content="__PUBLIC_PATH__">
""" + styles + """
<script>
var cdn=""" + json.dumps({"url":"/cdn", "imageUrl":"/cdn/images", "version":REVISION, "translationVersion":""}) + """;
var countryGuess="US",regionGuess="USA",locale="en-US",environment="",bugsnagEnvironment="",
accessToken="sandbox-only",csrfToken="__SANDBOX_CSRF__",nsid="sandbox",atid="sandbox",context="",contextPayload="";
var featureFlagsJson=""" + json.dumps(flags) + """;
var experimentsJson={};
var templateVariables={customerToken:"__SANDBOX_CUSTOMER__",worm:{countryCode:"US",region:"USA"}};
</script>
<script defer src="/local/preferences.js"></script><script defer src="/local/branding.js"></script><script defer src="/local/account-bridge.js"></script>
""" + "\n".join(scripts) + """
</head><body data-cashlarp="true">
<div id="root"></div><div id="modal-root"></div>
</body></html>"""
(ROOT / "local/account.html").write_text(html.replace("__PUBLIC_PATH__", base))
print("Built original-account boot document; captured JavaScript unchanged")

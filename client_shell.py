"""Boot the captured applications from their original captured document.

No page markup or forms are supplied here. Both applications keep the captured
document, stylesheet and loading artwork; only boot data, local URLs and the
account entrypoint's mount id differ.
"""
import base64
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
REVISION = "d964d4f8766900778d7282f4b26521146f6d2785"
ACCOUNT_FLAGS = {
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
}


@lru_cache(maxsize=2)
def document(application):
    if application not in ("login", "account"):
        raise ValueError("Unknown captured application")
    source = (ROOT / "capture/login.html").read_text()
    source = re.sub(r'<script[^>]+src="https://www.google.com/recaptcha/enterprise.js[^\"]*"[^>]*></script>', "", source)
    source = source.replace("https://cash-f.squarecdn.com", "/cdn")
    source = source.replace("https://cash-images-f.squarecdn.com", "/cdn/images")
    source = re.sub(r'<link[^>]+rel="canonical"[^>]*>', "", source)
    source = re.sub(r'<title>.*?</title>', '<title>Cashlarp</title>', source)
    source = source.replace("Sign in to your Cash App account.", "Sign in to your Cashlarp account.")
    source = re.sub(r'recaptchaKeyId="[^\"]*"', 'recaptchaKeyId=""', source)
    bridge = "bridge.js"
    if application == "account":
        flags = json.loads(re.search(r"var featureFlagsJson = (\{.*?\})\s*var experimentsJson", source, re.S)[1])
        for key in flags:
            if any(part in key for part in ("datadog", "enable-sid", "enable-sitm", "enable-tm", "risk-signal", "conversion-tracking", "one-trust", "wait-for-sid")):
                flags[key] = {"sessionSampleRateOverride": 0} if "config" in key else False
        flags.update(ACCOUNT_FLAGS)
        source = re.sub(r"(var featureFlagsJson = )\{.*?\}(\s*var experimentsJson)", lambda m: m[1] + json.dumps(flags) + m[2], source, count=1, flags=re.S)
        source = source.replace('csrfToken=""', 'csrfToken="__SANDBOX_CSRF__"', 1)
        source = source.replace('id="app-root"', 'id="root"', 1)
        source = source.replace("/web/login/", "/web/account/")
        for old, new in (("runtime.1973b48deea66eb9.js", "runtime.a1ea354b43d18d7c.js"), ("main.1973b48deea66eb9.js", "main.fa6baaec96a82623.js")):
            data = (ROOT / "capture/cdn/web/account" / REVISION / new).read_bytes()
            integrity = "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()
            pattern = r'<script\b[^>]*src="[^\"]*/' + re.escape(old) + r'"[^>]*></script>'
            def replace_script(match, old=old, new=new, integrity=integrity):
                return re.sub(r'integrity="[^\"]*"', 'integrity="' + integrity + '"', match[0].replace(old, new))
            source, count = re.subn(pattern, replace_script, source, count=1)
            if count != 1:
                raise ValueError("Captured entrypoint not found: " + old)
        source = source.replace("</head>", '<script>var templateVariables={customerToken:"__SANDBOX_CUSTOMER__",worm:{countryCode:"US",region:"USA"}};</script></head>', 1)
        bridge = "account-bridge.js"
    adapters = ('<script defer src="/local/preferences.js"></script>'
                '<script defer src="/local/branding.js"></script>'
                '<script defer src="/local/' + bridge + '"></script>')
    source = re.sub(r'(?=<script defer="defer" src="[^\"]*/runtime)', lambda _: adapters, source, count=1)
    return source


def login_document():
    return document("login")


def account_document(session):
    return document("account").replace("__SANDBOX_CSRF__", session["csrf"]).replace("__SANDBOX_CUSTOMER__", session["user_id"])

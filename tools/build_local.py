#!/usr/bin/env python3
"""Patch the captured shell; original JS/CSS chunks remain byte-for-byte intact."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "capture/login.html").read_text()
source = re.sub(r'<script[^>]+src="https://www.google.com/recaptcha/enterprise.js[^"]*"[^>]*></script>', "", source)
source = source.replace("https://cash-f.squarecdn.com", "/cdn")
source = source.replace("https://cash-images-f.squarecdn.com", "/cdn/images")
source = re.sub(r'<link[^>]+rel="canonical"[^>]*>', "", source)
source = re.sub(r'recaptchaKeyId="[^"]*"', 'recaptchaKeyId=""', source)
source = re.sub(r'<title>.*?</title>', "<title>Cashlarp</title>", source)
source = source.replace("Sign in to your Cash App account.","Sign in to your Cashlarp account.")
source = re.sub(r'(<script defer="defer" src="[^"]+/runtime[^"]*")',
                '<script src="/local/preferences.js" defer></script><script src="/local/branding.js" defer></script><script src="/local/bridge.js" defer></script>\\n' + r'\1', source, count=1)
source = source.replace("<body", '<body data-cashlarp="true"', 1)
target = ROOT / "local/login.html"
target.parent.mkdir(exist_ok=True)
target.write_text(source)
print(json.dumps({"output": str(target), "original_chunks_modified": 0}))

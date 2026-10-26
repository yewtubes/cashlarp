#!/usr/bin/env python3
"""Extract only public static CDN URLs from a LOCAL saved HTML or HAR.

Run this on the machine that owns the capture. Share only the output JSON.
Cookies, headers, account pages, API payloads and response bodies are not emitted.
"""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def extract_urls(text):
    try:
        payload = json.loads(text)
        candidates = [entry.get("request", {}).get("url", "")
                      for entry in payload.get("log", {}).get("entries", [])]
    except (json.JSONDecodeError, AttributeError):
        candidates = re.findall(r'https://cash-f\.squarecdn\.com/[^\s"\'<>\\]+', text)
    result = set()
    for candidate in candidates:
        try:
            url = urlsplit(candidate)
            if (url.scheme != "https" or url.netloc != "cash-f.squarecdn.com"
                    or url.query or url.fragment or url.username or url.password):
                continue
            if not re.fullmatch(r"/(?:web/(?:account|login)/[a-f0-9]{40}/[A-Za-z0-9_./-]+\.(?:js|css|woff2|otf|json|svg|png|jpg|webp|glb)|static/[A-Za-z0-9_./-]+\.(?:woff2|otf|svg|png|jpg|webp))", url.path):
                continue
            if ".." in url.path.split("/"):
                continue
            result.add("https://cash-f.squarecdn.com" + url.path)
        except (ValueError, TypeError):
            continue
    return sorted(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path, help="Local saved account HTML or local HAR")
    parser.add_argument("--output", type=Path, default=Path("public-client-assets.json"))
    args = parser.parse_args()
    urls = extract_urls(args.capture.read_text(encoding="utf-8"))
    args.output.write_text(json.dumps({"public_static_asset_urls": urls}, indent=2) + "\n")
    print("Wrote " + str(len(urls)) + " public static URLs to " + str(args.output))

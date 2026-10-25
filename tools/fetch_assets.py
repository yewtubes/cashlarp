#!/usr/bin/env python3
"""Fetch the approved public static URLs from extract_asset_urls.py output."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

from extract_asset_urls import extract_urls

ROOT = Path(__file__).resolve().parents[1]


def fetch(url):
    relative = url.split(".com/", 1)[1]
    target = ROOT / "capture/cdn" / relative
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"url": url, "path": str(target.relative_to(ROOT / "capture")),
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


if __name__ == "__main__":
    payload = json.loads(Path(sys.argv[1]).read_text())
    requested = payload["public_static_asset_urls"]
    approved = extract_urls("\n".join(requested))
    if sorted(set(requested)) != approved:
        raise SystemExit("Input contains URLs outside the public static asset allowlist")
    manifest_path = ROOT / "capture/manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    by_url = {entry["url"]: entry for entry in previous}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for entry in pool.map(fetch, approved):
            by_url[entry["url"]] = entry
    manifest_path.write_text(json.dumps(list(by_url.values()), indent=2) + "\n")
    print("Fetched and checksummed " + str(len(approved)) + " public assets")

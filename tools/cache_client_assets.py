#!/usr/bin/env python3
"""Cache original static images, card textures/models and fonts used by the client."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = (".glb", ".png", ".webp", ".jpg", ".svg", ".woff2", ".otf")
STATIC = ("savings-keys.svg", "savings-propagation.svg", "savings-rake.svg",
          "savings-cash-app-card.svg", "fonts/shantell_sans_normal_medium.otf")


def referenced_assets():
    result = {}
    for app in ("account", "login"):
        for chunk in (ROOT / "capture/cdn/web" / app).rglob("*.js"):
            for name in re.findall(r'\b[A-Za-z_$][\w$]*\.p\+"([^"\n]+)"', chunk.read_text()):
                if name.endswith(EXTENSIONS) and ".." not in Path(name).parts:
                    relative = str((chunk.parent / name).relative_to(ROOT / "capture"))
                    result[relative] = "https://cash-f.squarecdn.com/" + relative.removeprefix("cdn/")
    for name in STATIC:
        result["cdn/static/" + name] = "https://cash-f.squarecdn.com/static/" + name
    return result


def valid_asset(path, data):
    return {".svg": b"<svg" in data[:1000], ".png": data.startswith(b"\x89PNG\r\n\x1a\n"),
            ".webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP",
            ".glb": data.startswith(b"glTF"), ".jpg": data.startswith(b"\xff\xd8"),
            ".otf": data[:4] in (b"OTTO", b"\x00\x01\x00\x00"),
            ".woff2": data.startswith(b"wOF2")}.get(path.suffix, False)


def fetch(item):
    relative, url = item
    target = ROOT / "capture" / relative
    if target.exists():
        data = target.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
    if not valid_asset(target, data):
        raise ValueError("Invalid original asset: " + url)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"url": url, "path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


if __name__ == "__main__":
    manifest = ROOT / "capture/manifest.json"
    entries = {entry["path"]: entry for entry in json.loads(manifest.read_text())}
    requested = referenced_assets()
    with ThreadPoolExecutor(max_workers=6) as pool:
        for index, entry in enumerate(pool.map(fetch, requested.items()), 1):
            entries[entry["path"]] = entry
            if index % 20 == 0:
                print(f"Cached {index}/{len(requested)} original static assets", flush=True)
    temporary = manifest.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(list(entries.values()), indent=2) + "\n")
    temporary.replace(manifest)
    print(f"Cached and checksummed {len(requested)} original static assets", flush=True)

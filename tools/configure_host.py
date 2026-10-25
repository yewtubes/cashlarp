#!/usr/bin/env python3
"""Create private host configuration once; never overwrite credentials."""
import argparse
import os
from pathlib import Path
import re
import secrets
ROOT = Path(__file__).resolve().parents[1]

def configure(domain, destination):
    domain = domain.lower().rstrip(".")
    labels = domain.split(".")
    if len(domain) > 253 or len(labels) < 2 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
        raise ValueError("Use a hostname without https:// or a path")
    text = (f"DOMAIN={domain}\nCASHLARP_ACCESS_USER=cashlarp\n"
            f"CASHLARP_ACCESS_PASSWORD={secrets.token_urlsafe(32)}\nCASHLARP_SECURE_COOKIES=1\n")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(text)
    return domain

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain")
    args = parser.parse_args()
    try:
        domain = configure(args.domain, ROOT / ".env")
    except (ValueError, FileExistsError) as error:
        parser.exit(1, f"Configuration not created: {error}\n")
    print(f"Configured https://{domain}. Hosting credentials are in .env (owner-readable).")
    print("Run: docker compose -f compose.yaml -f compose.host.yaml up -d --build")

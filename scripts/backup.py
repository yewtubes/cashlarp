#!/usr/bin/env python3
"""Create a consistent SQLite snapshot, including committed WAL changes."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

def backup(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb"):
        pass
    try:
        with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as db:
            with sqlite3.connect(destination) as target:
                db.backup(target)
                if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise RuntimeError("SQLite integrity check failed")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, nargs="?", default=Path("backups") / ("cashlarp-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".sqlite3"))
    args = parser.parse_args()
    print(backup(args.source, args.destination))

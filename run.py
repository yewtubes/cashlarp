#!/usr/bin/env python3
"""Build the local client harness and start Cashlarp without extra packages."""
import runpy
import sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
if __name__ == "__main__":
    for name in ("build_local.py", "build_account.py"):
        runpy.run_path(str(ROOT / "tools" / name), run_name="__main__")
    from server import main
    main()

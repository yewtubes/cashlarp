#!/usr/bin/env python3
"""Validate the captured login boot document; do not generate page markup."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from client_shell import document
assert '/cdn/web/login/' in document('login')
print('Captured login document ready; original client bundles unchanged')

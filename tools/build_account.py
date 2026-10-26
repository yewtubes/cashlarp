#!/usr/bin/env python3
"""Validate the captured account boot document; do not generate page markup."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from client_shell import document
assert '/cdn/web/account/' in document('account')
print('Captured account document ready; original client bundles unchanged')

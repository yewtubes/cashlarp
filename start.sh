#!/bin/sh
set -eu
cd "$(dirname "$0")"
printf '%s\n' 'Open http://127.0.0.1:3000/login'
exec python3 -B run.py "$@"

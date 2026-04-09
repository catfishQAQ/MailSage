#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -x "backend/.venv/bin/python" ]; then
  exec "backend/.venv/bin/python" "scripts/stop_mailsage.py"
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 "scripts/stop_mailsage.py"
fi

exec python "scripts/stop_mailsage.py"

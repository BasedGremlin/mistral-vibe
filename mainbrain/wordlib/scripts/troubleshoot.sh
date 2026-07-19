#!/usr/bin/env bash
# WORDLIB -- Troubleshooter
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON=""
command -v python3 >/dev/null 2>&1 && PYTHON="python3"
[ -z "$PYTHON" ] && command -v python >/dev/null 2>&1 && PYTHON="python"
if [ -z "$PYTHON" ]; then echo "Python 3 not found."; read -rp "Enter..."; exit 1; fi
"$PYTHON" "$ROOT/src/troubleshoot.py"
read -rp "Press Enter to close..."

#!/usr/bin/env bash
# WORDLIB Deployment Check -- verify USB readiness without launching anything
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON=""
command -v python3 >/dev/null 2>&1 && PYTHON="python3"
[ -z "$PYTHON" ] && command -v python >/dev/null 2>&1 && PYTHON="python"
if [ -z "$PYTHON" ]; then
    echo "Python 3 not found. Install: sudo apt install python3"
    read -rp "Press Enter..."
    exit 1
fi
"$PYTHON" "$ROOT/deploy_check.py"
read -rp "Press Enter to close..."

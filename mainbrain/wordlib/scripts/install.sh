#!/usr/bin/env bash
# ================================================================
# WORDLIB -- ONE-HIT INSTALL  (Linux)
# First time? Run:  chmod +x install.sh && ./install.sh
# ================================================================
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON=""
command -v python3 >/dev/null 2>&1 && PYTHON="python3"
[ -z "$PYTHON" ] && command -v python >/dev/null 2>&1 && PYTHON="python"
if [ -z "$PYTHON" ]; then
    echo "  Python 3 not found. Install it first:"
    echo "    sudo apt install python3 python3-venv python3-pip"
    read -rp "  Press Enter to exit..."
    exit 1
fi
"$PYTHON" "$ROOT/launcher.py" install
echo
echo "  Install finished. Next time, just run ./run_me.sh"
read -rp "  Press Enter to close..."

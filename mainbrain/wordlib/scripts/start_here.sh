#!/usr/bin/env bash
# WORDLIB -- START HERE (Linux). Run: chmod +x start_here.sh && ./start_here.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PYTHON=""
command -v python3 >/dev/null 2>&1 && PYTHON="python3"
[ -z "$PYTHON" ] && command -v python >/dev/null 2>&1 && PYTHON="python"
if [ -z "$PYTHON" ]; then
    echo "  Python 3 not found: sudo apt install python3 python3-venv python3-pip"
    read -rp "  Press Enter to exit..."; exit 1
fi
"$PYTHON" "$ROOT/start_here.py"
read -rp "  Press Enter to close..."

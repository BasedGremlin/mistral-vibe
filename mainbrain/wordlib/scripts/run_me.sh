#!/usr/bin/env bash
# ================================================================
# WORDLIB -- Linux Entry Point
# Thin door: finds Python, runs launcher.py. All logic is in Python.
# First time:  chmod +x run_me.sh   then   ./run_me.sh
# ================================================================
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    echo
    echo "  ERROR: Python 3 not found."
    echo "  Linux Mint:  sudo apt install python3 python3-venv python3-pip"
    echo
    read -rp "  Press Enter to exit..."
    exit 1
fi

"$PYTHON" "$ROOT/launcher.py"

#!/usr/bin/env bash
# ================================================================
# WORDLIB -- Linux Mint One-Time Setup
# Run this ONCE after booting into Linux Mint (via Ventoy).
# Installs everything the Linux side needs, then you use run_me.sh.
#
#   chmod +x setup_linux.sh
#   ./setup_linux.sh
# ================================================================
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo
echo "  ====================================================="
echo "    WORDLIB -- Linux Mint Setup (one time)"
echo "  ====================================================="
echo

# ── 1. System packages ───────────────────────────────────────
echo "  [1/4] Installing system packages (needs sudo)..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip curl
echo "  [OK] System packages ready."
echo

# ── 2. Ollama ────────────────────────────────────────────────
echo "  [2/4] Installing Ollama..."
if command -v ollama >/dev/null 2>&1; then
    echo "  [OK] Ollama already installed."
else
    curl -fsSL https://ollama.com/install.sh | sh
    echo "  [OK] Ollama installed."
fi

# Point Ollama at the USB model folder so models travel with the stick
export OLLAMA_MODELS="$ROOT/core/ollama/models"
mkdir -p "$OLLAMA_MODELS"
echo "  Ollama models dir: $OLLAMA_MODELS"
echo

# ── 3. Pull models ───────────────────────────────────────────
echo "  [3/4] Pulling models (large -- only if not already present)..."
echo "        Starting Ollama temporarily..."
OLLAMA_MODELS="$OLLAMA_MODELS" ollama serve >/dev/null 2>&1 &
OLLAMA_PID=$!
sleep 6

pull_if_missing() {
    if ollama list 2>/dev/null | grep -q "${1%%:*}"; then
        echo "  [OK] $1 already present."
    else
        echo "  Pulling $1 ..."
        ollama pull "$1"
    fi
}

pull_if_missing "qwen2.5-coder:7b-instruct-q4_K_M"
pull_if_missing "dolphin3:8b-llama3.1-q4_K_M"
pull_if_missing "nomic-embed-text"

kill $OLLAMA_PID 2>/dev/null || true
echo "  [OK] Models ready."
echo

# ── 4. Python venv + packages ────────────────────────────────
echo "  [4/4] Setting up Python environment..."
# launcher.py handles venv + package install itself on first run,
# but we trigger it here so the first real run is instant.
python3 "$ROOT/launcher.py" status >/dev/null 2>&1 || true
echo "  [OK] Python environment prepared."
echo

# ── Godot (optional reminder) ────────────────────────────────
GODOT_LINUX="$ROOT/Godot/Godot_v4.7-stable_linux.x86_64"
if [ ! -f "$GODOT_LINUX" ]; then
    echo "  NOTE: Godot Linux binary not found."
    echo "        Download Godot 4.7 for Linux from godotengine.org"
    echo "        and place it at: $GODOT_LINUX"
    echo "        Then run: chmod +x \"$GODOT_LINUX\""
    echo
fi

echo "  ====================================================="
echo "   Linux setup complete."
echo
echo "   Now run:  ./run_me.sh"
echo "  ====================================================="
echo

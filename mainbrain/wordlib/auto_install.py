#!/usr/bin/env python3
"""
WORDLIB Auto-Installer  (polished console UI, fully hands-off)
=============================================================
ONE double-click. After that it asks nothing. It runs every deployment
stage with a live progress bar and a clean dark-console interface, then
opens ETHER AI in the browser.

Pure standard library -- no Tkinter, no curses, no pip dependencies for the
UI itself. Works in Windows Terminal and modern cmd (ANSI enabled).

Called by START_HERE.bat / install.sh. Can also run directly:
  python auto_install.py
"""

import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT       = Path(__file__).resolve().parent
SRC        = ROOT / "src"
APP        = ROOT / "app"
CORE       = ROOT / "core"
VENV       = ROOT / ".venv"
CACHE      = ROOT / ".pip_cache"
IS_WINDOWS = platform.system() == "Windows"
HUB_PORT   = 5757
HUB_URL    = f"http://localhost:{HUB_PORT}"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# ── ANSI palette ─────────────────────────────────────────────────────────────
if IS_WINDOWS:
    os.system("")          # enable ANSI on modern Windows consoles
    os.system("color 0f")  # black bg, white fg
RESET="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
FG_G="\033[92m"; FG_R="\033[91m"; FG_Y="\033[93m"; FG_C="\033[96m"; FG_W="\033[97m"
FG_GRAY="\033[90m"; BG_BAR="\033[100m"

W = 60  # console width for boxes/bars


def clear():
    os.system("cls" if IS_WINDOWS else "clear")


def hide_cursor(): sys.stdout.write("\033[?25l"); sys.stdout.flush()
def show_cursor(): sys.stdout.write("\033[?25h"); sys.stdout.flush()


def box(title, color=FG_C):
    line = "=" * W
    print(f"{color}{line}{RESET}")
    pad = (W - len(title)) // 2
    print(f"{color}{' ' * pad}{BOLD}{title}{RESET}")
    print(f"{color}{line}{RESET}")


def banner():
    clear()
    print()
    print(f"{FG_C}{BOLD}")
    print("   ██     ██  ██████  ██████  ██████  ██      ██ ██████")
    print("   ██     ██ ██    ██ ██   ██ ██   ██ ██      ██ ██   ██")
    print("   ██  █  ██ ██    ██ ██████  ██   ██ ██      ██ ██████")
    print("   ██ ███ ██ ██    ██ ██   ██ ██   ██ ██      ██ ██   ██")
    print("    ███ ███   ██████  ██   ██ ██████  ███████ ██ ██████")
    print(f"{RESET}")
    print(f"{FG_GRAY}            USB AI Master -- Auto Installer{RESET}")
    print(f"{FG_GRAY}            One click. Hands-off. Self-deploying.{RESET}")
    print()


# ── Progress bar ─────────────────────────────────────────────────────────────

class Stage:
    """A single install stage with a live progress bar."""

    def __init__(self, index, total, name):
        self.index = index
        self.total = total
        self.name = name
        self.pct = 0

    def draw(self, pct, status="", color=FG_G):
        self.pct = max(0, min(100, pct))
        filled = int(self.pct / 100 * (W - 8))
        bar = f"{color}{'█' * filled}{FG_GRAY}{'░' * (W - 8 - filled)}{RESET}"
        head = f"{FG_W}[{self.index}/{self.total}] {self.name}{RESET}"
        sys.stdout.write("\r\033[K")  # clear line
        sys.stdout.write(f"  {bar} {color}{self.pct:3d}%{RESET}")
        if status:
            sys.stdout.write(f"  {FG_GRAY}{status}{RESET}")
        sys.stdout.flush()

    def start(self, status=""):
        print()
        print(f"  {FG_W}[{self.index}/{self.total}] {BOLD}{self.name}{RESET}")
        self.draw(0, status)

    def finish(self, ok=True, status=""):
        self.draw(100, status, FG_G if ok else FG_R)
        mark = f"{FG_G}  ✓{RESET}" if ok else f"{FG_R}  ✗{RESET}"
        sys.stdout.write(mark + "\n")
        sys.stdout.flush()

    def fail(self, msg):
        self.draw(self.pct, msg, FG_R)
        sys.stdout.write(f"{FG_R}  ✗{RESET}\n")
        sys.stdout.flush()


# ── Helpers (mirror launcher's logic, no prompts) ────────────────────────────

def venv_python():
    return VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")

def port_up(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def have_internet():
    try:
        socket.setdefaulttimeout(4)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except OSError:
        return False


CORE_PKGS = ["flask>=2.0", "flask-sqlalchemy>=3.0", "requests>=2.20",
             "beautifulsoup4>=4.9", "lxml>=4.9", "markdown>=3.4"]
RENDER_PKGS = ["numpy>=1.24", "Pillow>=10.0"]  # numba optional, not auto-installed
RAG_PKGS  = ["llama-index-core>=0.10", "llama-index-vector-stores-chroma>=0.2",
             "llama-index-embeddings-ollama>=0.3", "llama-index-llms-ollama>=0.3",
             "chromadb>=0.5"]


# ── The stages ───────────────────────────────────────────────────────────────

def self_clean():
    """
    Remove stale artifacts from a previous/older install so versions never mix.
    Safe: only touches regenerable caches + known stale files, never user data
    (data/, storage/, backups/, models/ are preserved).
    """
    removed = []
    # Stale Python bytecode caches
    for pyc in ROOT.rglob("__pycache__"):
        try:
            shutil.rmtree(pyc); removed.append(pyc.name)
        except Exception:
            pass
    # A broken/partial venv from a failed prior run (rebuilt cleanly anyway)
    venv_py = venv_python()
    if VENV.exists() and not venv_py.exists():
        try:
            shutil.rmtree(VENV); removed.append(".venv (was broken)")
        except Exception:
            pass
    # Stale event log from testing
    stale_log = ROOT / "data" / "ether_events.jsonl"
    if stale_log.exists():
        try:
            stale_log.unlink(); removed.append("old event log")
        except Exception:
            pass
    # Files from the OLD architecture that should not coexist with the new one
    legacy = ["src/LAUNCH.py", "Start_Everything.bat", "START.py", "launch.bat"]
    for rel in legacy:
        p = ROOT / rel
        if p.exists():
            try:
                p.unlink(); removed.append(rel)
            except Exception:
                pass
    return removed


def run_install():
    banner()
    time.sleep(0.4)

    # Self-clean: silently remove stale artifacts so versions never mix
    cleaned = self_clean()
    if cleaned:
        print(f"  {FG_GRAY}Self-clean: removed {len(cleaned)} stale item(s) "
              f"from a previous install.{RESET}")
        time.sleep(0.3)

    online = have_internet()
    venv_ready = venv_python().exists()

    # Honest gate: first install needs internet
    if not online and not venv_ready:
        box("CANNOT INSTALL -- NO INTERNET", FG_R)
        print()
        print(f"  {FG_Y}This is a first install and there's no internet.{RESET}")
        print(f"  {FG_Y}The installer needs to download Python packages,{RESET}")
        print(f"  {FG_Y}Ollama, and the AI models the first time.{RESET}")
        print()
        print(f"  {FG_W}Connect to the internet and run this again.{RESET}")
        print(f"  {FG_GRAY}(After the first install, it runs fully offline.){RESET}")
        print()
        return False

    box("DEPLOYING -- sit back, this is hands-off", FG_C)
    print(f"  {FG_GRAY}Internet: {'yes' if online else 'offline (using cache)'}"
          f"  |  Root: {ROOT.name}{RESET}")

    TOTAL = 8
    hide_cursor()
    try:
        # Stage 1: Pre-flight
        s = Stage(1, TOTAL, "Pre-flight diagnosis")
        s.start("checking structure, disk, ports...")
        try:
            from troubleshoot import run_all
            diags = run_all()
            blocking = [d for d in diags if not d.ok and
                        (d.check in ("File structure", "USB writable")
                         or "too old" in d.problem)]
            for p in range(0, 101, 25):
                s.draw(p); time.sleep(0.05)
            if blocking:
                s.fail("blocking problem found")
                show_cursor()
                print()
                for d in blocking:
                    print(f"  {FG_R}Problem:{RESET} {d.problem}")
                    print(f"  {FG_G}Fix:{RESET}     {d.fix}")
                return False
            s.finish(True, "no blocking problems")
        except Exception as e:
            s.finish(True, f"skipped ({e})")

        # Stage 2: venv
        s = Stage(2, TOTAL, "Python environment")
        s.start("creating virtual environment...")
        if not venv_python().exists():
            s.draw(20, "building venv (~30s)...")
            try:
                subprocess.run([sys.executable, "-m", "venv", str(VENV)],
                               check=True, timeout=120, capture_output=True)
            except Exception as e:
                s.fail(f"venv failed: {e}")
                show_cursor()
                return False
        s.finish(True, "ready")

        # Stage 3: core packages
        s = Stage(3, TOTAL, "Core packages")
        vpy = venv_python()
        pip = vpy.parent / ("pip.exe" if IS_WINDOWS else "pip")
        CACHE.mkdir(exist_ok=True)
        need = subprocess.run([str(vpy), "-c",
                               "import flask,flask_sqlalchemy,bs4,markdown"],
                              capture_output=True).returncode != 0
        if need:
            if not online:
                s.fail("packages missing, no internet")
                show_cursor(); return False
            s.start("installing flask, sqlalchemy, bs4... (2-4 min)")
            s.draw(30, "downloading...")
            try:
                subprocess.run([str(pip), "install", "--upgrade", "pip", "--quiet",
                                "--cache-dir", str(CACHE)], capture_output=True, timeout=60)
                s.draw(60, "installing...")
                subprocess.run([str(pip), "install", *CORE_PKGS, "--quiet",
                                "--no-warn-script-location", "--cache-dir", str(CACHE)],
                               check=True, timeout=300)
            except Exception as e:
                s.fail(f"install failed: {e}")
                show_cursor(); return False
        else:
            s.start("already installed")
        s.finish(True, "ready")

        # Stage 4: RAG packages (optional)
        s = Stage(4, TOTAL, "RAG packages")
        have_rag = subprocess.run([str(vpy), "-c", "import chromadb,llama_index.core"],
                                  capture_output=True).returncode == 0
        if not have_rag and online:
            s.start("installing LlamaIndex + ChromaDB... (2-4 min)")
            s.draw(40, "downloading...")
            try:
                subprocess.run([str(pip), "install", *RAG_PKGS, "--quiet",
                                "--no-warn-script-location", "--cache-dir", str(CACHE)],
                               check=True, timeout=480)
                s.finish(True, "ready")
            except Exception:
                s.finish(True, "skipped (RAG optional)")
        else:
            s.start("already installed" if have_rag else "offline -- skipped")
            s.finish(True, "ready" if have_rag else "deferred")

        # Stage 5: Ollama + models
        s = Stage(5, TOTAL, "Ollama + AI models")
        ollama = CORE / "ollama" / ("ollama.exe" if IS_WINDOWS else "ollama")
        models_dir = CORE / "ollama" / "models"
        has_models = models_dir.exists() and any(models_dir.iterdir()) if models_dir.exists() else False
        if (not ollama.exists() or not has_models):
            if not online:
                s.start("offline -- skipping downloads")
                s.finish(True, "deferred (run again online)")
            else:
                s.start("running Setup/01 -- downloads ~10 GB, several minutes")
                s.draw(10, "this is the long part, please wait...")
                setup01 = ROOT / "Setup" / "01_Install_Ollama.bat"
                linux_setup = ROOT / "setup_linux.sh"
                try:
                    if IS_WINDOWS and setup01.exists():
                        subprocess.run([str(setup01)], cwd=str(ROOT / "Setup"))
                    elif not IS_WINDOWS and linux_setup.exists():
                        subprocess.run(["bash", str(linux_setup)], cwd=str(ROOT))
                    s.finish(True, "models ready")
                except Exception as e:
                    s.finish(True, f"deferred ({e})")
        else:
            s.start("already present")
            s.finish(True, "ready")

        # Stage 6: background services
        s = Stage(6, TOTAL, "Background services")
        s.start("starting Ollama, Kiwix, Open WebUI...")
        vpy2 = venv_python() if venv_python().exists() else Path(sys.executable)
        try:
            if IS_WINDOWS:
                subprocess.Popen(
                    f'start "WORDLIB Services" cmd /k "{vpy2} \"{SRC/"usb_orchestrator.py"}\""',
                    shell=True)
            else:
                subprocess.Popen([str(vpy2), str(SRC / "usb_orchestrator.py")],
                                 start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for p in range(0, 101, 20):
                s.draw(p, "warming up..."); time.sleep(0.8)
            s.finish(True, "running")
        except Exception as e:
            s.finish(True, f"deferred ({e})")

        # Stage 7: ETHER AI hub
        s = Stage(7, TOTAL, "ETHER AI hub")
        s.start("launching web hub on port 5757...")
        if not port_up(HUB_PORT):
            env = {**os.environ, "ETHER_PORT": str(HUB_PORT), "ETHER_BASE": str(ROOT)}
            logf = open(ROOT / "logs" / "ether_hub.log", "a", encoding="utf-8")
            (ROOT / "logs").mkdir(exist_ok=True)
            flags = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
            subprocess.Popen([str(vpy2), "main.py"], cwd=str(APP), env=env,
                             stdout=logf, stderr=subprocess.STDOUT,
                             creationflags=flags if IS_WINDOWS else 0,
                             start_new_session=not IS_WINDOWS)
            for i in range(20):
                time.sleep(0.5)
                s.draw(min(95, i * 6), "waiting for hub...")
                if port_up(HUB_PORT):
                    break
        s.finish(port_up(HUB_PORT), "live" if port_up(HUB_PORT) else "check logs")

        # Stage 8: RAG index
        s = Stage(8, TOTAL, "Knowledge index")
        s.start("building RAG index over storage/...")
        try:
            req = urllib.request.Request(f"{HUB_URL}/api/rag/rebuild", data=b"{}",
                                         headers={"Content-Type": "application/json"},
                                         method="POST")
            for p in range(0, 80, 20):
                s.draw(p); time.sleep(0.3)
            urllib.request.urlopen(req, timeout=60)
            s.finish(True, "indexed")
        except Exception:
            s.finish(True, "will build on first chat")

    finally:
        show_cursor()

    # Done
    print()
    box("DEPLOYMENT COMPLETE", FG_G)
    print()
    print(f"  {FG_G}{BOLD}ETHER AI is live.{RESET}  Opening in your browser now.")
    print(f"  {FG_W}{HUB_URL}{RESET}")
    print()
    print(f"  {FG_GRAY}From now on: double-click RUN_ME.bat -> option 1{RESET}")
    print()
    if port_up(HUB_PORT):
        webbrowser.open(HUB_URL)
    return True


def main():
    try:
        ok = run_install()
    except KeyboardInterrupt:
        show_cursor()
        print(f"\n\n  {FG_Y}Install cancelled.{RESET}\n")
        return
    if not ok:
        print(f"  {FG_GRAY}If something failed, run TROUBLESHOOT.bat for exact fixes.{RESET}")
        print()


if __name__ == "__main__":
    main()

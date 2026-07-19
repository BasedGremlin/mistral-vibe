#!/usr/bin/env python3
"""
WORDLIB -- Single Entry Point
=============================
One Python brain for the whole system, on Windows and Linux alike.

  RUN_ME.bat (Windows) and run_me.sh (Linux) are thin doors that just
  find Python and run this file. All real logic lives here.

Architecture:
  ETHER AI (Flask) is the HUB. RAG lives there. Godot and OpenClaw are
  clients that query the hub over HTTP. When a creative tool needs RAG,
  the launcher auto-starts the hub if it isn't already up.

Responsibilities (absorbed from the old LAUNCH.py + orchestrator glue):
  - first-run setup: venv, packages
  - start/stop background services (Ollama, Kiwix, Open WebUI) via orchestrator
  - start the ETHER AI hub (Flask)
  - launch creative tools (Godot, OpenClaw) with hub auto-start
  - LM Studio GUI on Windows only (honest: it can't be cross-platform)
  - the menu
"""

import os
import sys
import time
import socket
import shutil
import platform
import subprocess
import threading
import webbrowser
import urllib.request
from pathlib import Path

# ── Paths (single source of truth: core.paths, with guarded fallback) ───────
try:
    from core.paths import PATHS
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core.paths import PATHS

ROOT     = PATHS.root
SRC      = PATHS.src
APP      = PATHS.app
DATA     = PATHS.data
LOGS     = PATHS.logs
VENV     = ROOT / ".venv"
CACHE    = ROOT / ".pip_cache"
CORE     = ROOT / "core"

IS_WINDOWS = platform.system() == "Windows"
HUB_PORT   = 5757
HUB_URL    = f"http://localhost:{HUB_PORT}"

LOGS.mkdir(parents=True, exist_ok=True)

# ── Colours ─────────────────────────────────────────────────────────────────
if IS_WINDOWS:
    os.system("color")
R="\033[91m"; G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[0m"; B="\033[1m"

def cprint(msg, col=W):
    print(f"{col}{msg}{W}", flush=True)

def ok(m):   cprint(f"  [OK]  {m}", G)
def warn(m): cprint(f"  [WARN] {m}", Y)
def err(m):  cprint(f"  [ERR]  {m}", R)
def info(m): cprint(f"  [-->] {m}", C)

# ── Helpers ─────────────────────────────────────────────────────────────────
def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")

def port_up(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def have_internet() -> bool:
    try:
        socket.setdefaulttimeout(4)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except OSError:
        return False

# ═══════════════════════════════════════════════════════════════════════════
#  SETUP (first run only)
# ═══════════════════════════════════════════════════════════════════════════

CORE_PKGS = [
    "flask>=2.0", "flask-sqlalchemy>=3.0",
    "requests>=2.20", "beautifulsoup4>=4.9",
    "lxml>=4.9", "markdown>=3.4",
]
RAG_PKGS = [
    "llama-index-core>=0.10",
    "llama-index-vector-stores-chroma>=0.2",
    "llama-index-embeddings-ollama>=0.3",
    "llama-index-llms-ollama>=0.3",
    "chromadb>=0.5",
]

def ensure_setup() -> bool:
    """Create venv + install packages if needed. Returns True if hub can run."""
    cprint(f"\n{B}{C}  WORDLIB Setup{W}")

    if sys.version_info < (3, 8):
        err(f"Python {sys.version.split()[0]} too old -- need 3.8+")
        return False
    ok(f"Python {sys.version.split()[0]}")

    online = have_internet()
    info("Internet: " + ("yes" if online else "no (cached packages only)"))

    # Windows long-path fix (non-fatal)
    if IS_WINDOWS:
        try:
            subprocess.run(["reg","add",
                r"HKLM\SYSTEM\CurrentControlSet\Control\FileSystem",
                "/v","LongPathsEnabled","/t","REG_DWORD","/d","1","/f"],
                capture_output=True)
        except Exception:
            pass

    vpy = venv_python()
    if not vpy.exists():
        info("Creating virtual environment (first run, ~30s)...")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(VENV)],
                           check=True, timeout=120, capture_output=True)
            ok("Venv created")
        except subprocess.CalledProcessError:
            err("Venv creation failed -- try Run as Administrator")
            return False

    pip = vpy.parent / ("pip.exe" if IS_WINDOWS else "pip")
    CACHE.mkdir(exist_ok=True)

    # Core packages (required for the hub)
    test = subprocess.run([str(vpy),"-c","import flask,flask_sqlalchemy,bs4,markdown"],
                          capture_output=True)
    if test.returncode != 0:
        if not online:
            err("Core packages missing and no internet.")
            return False
        info("Installing core packages (2-4 min first run)...")
        try:
            subprocess.run([str(pip),"install","--upgrade","pip","--quiet",
                            "--cache-dir",str(CACHE)], capture_output=True, timeout=60)
            subprocess.run([str(pip),"install",*CORE_PKGS,"--quiet",
                            "--no-warn-script-location","--cache-dir",str(CACHE)],
                           check=True, timeout=300)
            ok("Core packages installed")
        except subprocess.CalledProcessError:
            err("Core package install failed -- check internet")
            return False
    else:
        ok("Core packages ready")

    # RAG packages (optional -- hub works without them, just no RAG)
    test = subprocess.run([str(vpy),"-c","import chromadb,llama_index.core"],
                          capture_output=True)
    if test.returncode != 0 and online:
        info("Installing RAG packages (LlamaIndex + ChromaDB, 2-4 min)...")
        try:
            subprocess.run([str(pip),"install",*RAG_PKGS,"--quiet",
                            "--no-warn-script-location","--cache-dir",str(CACHE)],
                           check=True, timeout=480)
            ok("RAG packages installed")
        except subprocess.CalledProcessError:
            warn("RAG install failed -- hub works, RAG disabled")
    elif test.returncode == 0:
        ok("RAG packages ready")
    else:
        warn("Offline -- RAG packages skipped")

    return True

# ═══════════════════════════════════════════════════════════════════════════
#  SELF-HEALING (runs on every launch)
# ═══════════════════════════════════════════════════════════════════════════

def self_heal() -> None:
    """
    Detect and fix common issues automatically. Non-fatal -- always continues.
    Runs before the menu on every launch. Fast checks only.
    """
    healed = []

    # 1. Disk space warning
    try:
        free_gb = shutil.disk_usage(str(ROOT)).free / 1_073_741_824
        if free_gb < 0.5:
            warn(f"Only {free_gb:.1f} GB free on USB -- models may not load")
        elif free_gb < 2.0:
            warn(f"{free_gb:.1f} GB free -- sufficient for now")
    except Exception:
        pass

    # 2. Storage/ folder structure
    for folder in ("strategy", "recovery", "research", "kb", "rag_index"):
        p = ROOT / "storage" / folder
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            healed.append(f"storage/{folder}/ recreated")

    # 3. Config file validation
    for cfg_name in ("creative.json", "model_manifest.json", "usb_paths.json"):
        cfg = ROOT / "config" / cfg_name
        if cfg.exists():
            try:
                import json as _json
                _json.loads(cfg.read_text(encoding="utf-8"))
            except Exception as e:
                warn(f"config/{cfg_name} is corrupt: {e}")
                # Rename the corrupt file so it doesn't block startup
                corrupt = cfg.with_suffix(".corrupt")
                cfg.rename(corrupt)
                healed.append(f"config/{cfg_name} quarantined (was corrupt)")

    # 4. Database integrity check (SQLite)
    db_path = ROOT / "data" / "ether.db"
    if db_path.exists():
        try:
            import sqlite3
            con = sqlite3.connect(str(db_path))
            result = con.execute("PRAGMA integrity_check").fetchone()
            con.close()
            if result and result[0] != "ok":
                warn(f"Database integrity issue: {result[0]}")
                # Backup and let Flask recreate on next boot
                import shutil as _sh
                ts = __import__('time').strftime("%Y%m%d_%H%M%S")
                _sh.copy2(db_path, db_path.with_name(f"ether.db.{ts}.corrupt"))
                db_path.unlink()
                healed.append("Corrupt database quarantined -- will recreate on boot")
        except Exception as e:
            warn(f"Could not check database: {e}")

    # 5. Port conflict detection
    for port, name in ((5757, "ETHER AI"), (11434, "Ollama"),
                       (8080, "Kiwix"), (3000, "Open WebUI")):
        if port_up(port):
            info(f"{name} already running on :{port}")

    # 6. Model check
    models_dir = ROOT / "models"
    gguf_files = list(models_dir.glob("*.gguf")) if models_dir.exists() else []
    ollama_models = ROOT / "core" / "ollama" / "models"
    has_ollama_model = ollama_models.exists() and any(ollama_models.iterdir()) if ollama_models.exists() else False
    if not gguf_files and not has_ollama_model:
        warn("No AI model found. Chat will run in template mode.")
        info("Run Setup/01_Install_Ollama.bat to pull models.")
    elif gguf_files:
        ok(f"Model: {gguf_files[0].name}")

    if healed:
        for fix in healed:
            ok(f"[HEALED] {fix}")


# ═══════════════════════════════════════════════════════════════════════════
#  HUB (ETHER AI Flask server)
# ═══════════════════════════════════════════════════════════════════════════

def start_hub(open_browser: bool = True) -> bool:
    """Start the ETHER AI Flask hub if not already running."""
    if port_up(HUB_PORT):
        ok(f"ETHER AI hub already running ({HUB_URL})")
        if open_browser:
            webbrowser.open(HUB_URL)
        return True

    vpy = venv_python()
    if not vpy.exists():
        err("Venv missing -- run setup first.")
        return False

    info("Starting ETHER AI hub...")
    env = {**os.environ, "ETHER_PORT": str(HUB_PORT), "ETHER_BASE": str(ROOT)}
    logf = open(LOGS / "ether_hub.log", "a", encoding="utf-8")

    flags = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
    subprocess.Popen([str(vpy), "main.py"], cwd=str(APP), env=env,
                     stdout=logf, stderr=subprocess.STDOUT,
                     creationflags=flags if IS_WINDOWS else 0,
                     start_new_session=not IS_WINDOWS)

    # Wait for it to come up
    for _ in range(20):
        time.sleep(0.5)
        if port_up(HUB_PORT):
            ok(f"ETHER AI hub up ({HUB_URL})")
            if open_browser:
                webbrowser.open(HUB_URL)
            return True
    warn("Hub did not respond in time -- check logs/ether_hub.log")
    return False

def ensure_hub() -> bool:
    """Auto-start the hub if down. Used before launching RAG-dependent tools."""
    if port_up(HUB_PORT):
        return True
    info("Hub not running -- auto-starting it for RAG access...")
    return start_hub(open_browser=False)

# ═══════════════════════════════════════════════════════════════════════════
#  SERVICES (Ollama, Kiwix, Open WebUI) via orchestrator module
# ═══════════════════════════════════════════════════════════════════════════

def start_services_background():
    """Run the orchestrator in a separate process (it has its own monitor loop)."""
    vpy = venv_python() if venv_python().exists() else Path(sys.executable)
    info("Starting background services (Ollama, Kiwix, Open WebUI, RAG)...")
    if IS_WINDOWS:
        subprocess.Popen(f'start "WORDLIB Services" cmd /k "{vpy} \"{SRC/"usb_orchestrator.py"}\""',
                         shell=True)
    else:
        _open_linux_terminal(f'{vpy} "{SRC/"usb_orchestrator.py"}"')

def stop_services():
    info("Stopping services...")
    if IS_WINDOWS:
        for name in ("ollama.exe", "kiwix-serve.exe"):
            subprocess.run(["taskkill","/F","/IM",name], capture_output=True)
        for title in ("WORDLIB Services*", "ETHER AI*"):
            subprocess.run(["taskkill","/F","/FI",f"WINDOWTITLE eq {title}"],
                           capture_output=True)
    else:
        for patt in ("ollama serve","kiwix-serve","usb_orchestrator.py","main.py"):
            subprocess.run(["pkill","-f",patt], capture_output=True)
    ok("Services stopped (Godot/OpenClaw windows close manually)")

def start_lmstudio_gui():
    """Windows-only LM Studio setup GUI. Honest: cannot be cross-platform."""
    if not IS_WINDOWS:
        warn("LM Studio GUI is Windows-only. On Linux, Ollama handles models.")
        return
    ps1 = SRC / "USB_Launcher.ps1"
    if ps1.exists():
        subprocess.Popen(["powershell.exe","-ExecutionPolicy","Bypass",
                          "-WindowStyle","Hidden","-File",str(ps1)])
        ok("LM Studio setup GUI launched")
    else:
        warn("USB_Launcher.ps1 not found")

# ═══════════════════════════════════════════════════════════════════════════
#  CREATIVE TOOLS (Godot, OpenClaw) -- auto-start hub for RAG
# ═══════════════════════════════════════════════════════════════════════════

def launch_godot():
    sys.path.insert(0, str(SRC))
    from creative_bridge import CreativeBridge
    ensure_hub()  # seamless RAG access
    bridge = CreativeBridge()
    if bridge.launch_godot():
        ok("Godot launching")
    else:
        warn("Godot not available -- run the Godot setup step")

def launch_openclaw(profile="code"):
    sys.path.insert(0, str(SRC))
    from openclaw_bridge import OpenClawBridge
    ensure_hub()  # seamless RAG access
    bridge = OpenClawBridge()
    if not bridge.is_ollama_up():
        warn("Ollama not running. Start the AI stack (option 2) first.")
        return
    if bridge.launch(profile=profile):
        ok(f"OpenClaw launching (profile: {profile})")

def start_kiwix_only():
    kiwix = CORE / "kiwix" / ("kiwix-serve.exe" if IS_WINDOWS else "kiwix-serve")
    if not kiwix.exists():
        warn("Kiwix not installed. Run the Kiwix setup step.")
        return
    zims = list((CORE/"kiwix").glob("*.zim"))
    if not zims:
        warn("No ZIM files. Run the Kiwix setup step to download them.")
        return
    cmd = [str(kiwix), "--port=8080"] + [str(z) for z in zims]
    subprocess.Popen(cmd, start_new_session=not IS_WINDOWS)
    time.sleep(2)
    webbrowser.open("http://localhost:8080")
    ok("Kiwix running at http://localhost:8080")

# ── Linux terminal helper ───────────────────────────────────────────────────
def _open_linux_terminal(command: str):
    inner = f'{command}; exec bash'
    for term in (["gnome-terminal","--"],["konsole","-e"],
                 ["xterm","-e"],["x-terminal-emulator","-e"]):
        try:
            subprocess.Popen(term + ["bash","-c",inner], start_new_session=True)
            return
        except FileNotFoundError:
            continue
    warn("No supported terminal found.")

# ═══════════════════════════════════════════════════════════════════════════
#  COMPOSITE ACTIONS
# ═══════════════════════════════════════════════════════════════════════════

def start_everything():
    cprint(f"\n{B}{C}  Starting EVERYTHING{W}")
    start_services_background()
    start_lmstudio_gui()
    start_hub(open_browser=True)
    info("Waiting for services to settle...")
    time.sleep(10)
    launch_godot()
    launch_openclaw("code")
    ok("Everything launched")

def start_ai_stack():
    cprint(f"\n{B}{C}  Starting AI stack{W}")
    start_services_background()
    start_lmstudio_gui()
    start_hub(open_browser=True)
    ok("AI stack starting -- ETHER AI opens in your browser")

def status_report():
    sys.path.insert(0, str(SRC))
    from creative_bridge import CreativeBridge
    from openclaw_bridge import OpenClawBridge
    import json
    # Blob brain status
    try:
        from ether_core import get_core
        core = get_core()
        cs = core.status()
        cprint("\n" + B + "  -- Ether Core (blob brain) --" + W)
        cprint("  Capabilities: %d/%d available" % (
            cs["capabilities_available"], cs["capabilities_total"]))
        cprint("  Events logged: %d | Evolution rounds: %d" % (
            cs["events_logged"], cs["evolution_rounds"]))
    except Exception as _e:
        warn("Ether core not available: %s" % _e)
    cprint(f"\n{B}  ===== STATUS ====={W}")
    cprint(f"\n  Hub (ETHER AI): {'UP' if port_up(HUB_PORT) else 'down'}")
    cprint(f"  Ollama:         {'UP' if port_up(11434) else 'down'}")
    cprint(f"  Kiwix:          {'UP' if port_up(8080) else 'down'}")
    cprint(f"  Open WebUI:     {'UP' if port_up(3000) else 'down'}")
    cprint(f"\n  -- Godot --")
    print(json.dumps(CreativeBridge().get_status(), indent=2))
    cprint(f"\n  -- OpenClaw --")
    print(json.dumps(OpenClawBridge().get_status(), indent=2))

# ═══════════════════════════════════════════════════════════════════════════
#  MENU
# ═══════════════════════════════════════════════════════════════════════════

MENU = f"""
{C}  ========================================================
{B}     W O R D L I B   |   USB AI Master{W}{C}
     All-in-one: AI + Knowledge + Dev Environment
  ========================================================{W}

     [1] Start Everything   (AI + services + creative)
     [2] AI Stack only      (Ollama + RAG + ETHER AI + WebUI)
     [3] Kiwix Library only (offline Grokipedia)
     [4] Godot              (game dev: Dialogic + Phantom Cam)
     [5] OpenClaw           (AI coding agent - Qwen2.5-Coder)
     [6] Stop all services
     [7] Status report
     [8] Content Manager    (sync library, expand topics, rebuild RAG)
     [9] System Editor      (read/write/rollback source files)
     [I] ONE-HIT INSTALL    (first time? press I -- sets up everything)
     [0] Deploy Check       (verify USB readiness + pathfinding)
     [T] Troubleshoot       (diagnose problems + get exact fixes)
     [D] Dashboard          (reasoning + agent swarm status)
     [X] Run Tests          (verify all systems work)
     [Q] Quit
{C}  ========================================================{W}"""

def content_manager_menu():
    sys.path.insert(0, str(SRC))
    from content_manager import ContentManager
    mgr = ContentManager()
    while True:
        print("\n" + C + "  -- Content Manager --" + W)
        print("  [1] Sync ETHER AI library -> storage/ + rebuild RAG")
        print("  [2] Expand topic with AI  (generate new knowledge file)")
        print("  [3] Rebuild RAG index only")
        print("  [4] Status report")
        print("  [5] Seed built-in knowledge  (Godot, game design, AI ref)")
        print("  [6] Seed Gutenberg books     (needs internet, cached after)")
        print("  [7] Seed EVERYTHING          (built-in + books)")
        print("  [B] Back")
        choice = input("  Choice: ").strip().lower()
        if choice == "1":
            stats = mgr.sync_and_rebuild()
            ok("Sync: %s  RAG: %s" % (stats["sync"], stats["rag_rebuild"].get("ok", "?")))
        elif choice == "2":
            topic  = input("  Topic to expand: ").strip()
            folder = input("  Folder [research/kb/strategy/recovery]: ").strip() or "research"
            if not topic:
                warn("No topic entered.")
            else:
                info("Generating '%s' -> storage/%s/ ..." % (topic, folder))
                result = mgr.expand_topic(topic, folder)
                if result["ok"]:
                    ok("Written: %s (%s chars)" % (result["path"], result["chars"]))
                    mgr.trigger_rag_rebuild()
                else:
                    err(result["error"])
        elif choice == "3":
            result = mgr.trigger_rag_rebuild()
            ok("RAG rebuild triggered") if result.get("ok") else warn(str(result))
        elif choice == "4":
            import json as _j
            print(_j.dumps(mgr.status(), indent=2))
        elif choice in ("5", "6", "7"):
            _run_seeder(choice)
        elif choice == "b":
            break
        input("\n  Press Enter to continue...")


def _run_seeder(choice):
    """Run content_seeder.py for built-in, gutenberg, or all."""
    seeder = ROOT / "content_seeder.py"
    if not seeder.exists():
        err("content_seeder.py not found")
        return
    vpy = venv_python() if venv_python().exists() else Path(sys.executable)
    flag = {"5": "--builtin", "6": "--gutenberg", "7": "--seed-all"}[choice]
    info("Running content seeder %s ..." % flag)
    try:
        subprocess.run([str(vpy), str(seeder), flag], cwd=str(ROOT))
        ok("Seeding complete. Run Content Manager option 3 to rebuild RAG.")
    except Exception as e:
        err("Seeder failed: %s" % e)


def system_editor_menu():
    sys.path.insert(0, str(SRC))
    from self_editor import SelfEditor
    import json as _j
    ed = SelfEditor()
    while True:
        print("\n" + C + "  -- System Editor (Self-Modification) --" + W)
        print("  [1] List all source files")
        print("  [2] Read a file")
        print("  [3] Write a file  (backup auto-created)")
        print("  [4] Patch a file  (find+replace, backup auto-created)")
        print("  [5] List backups")
        print("  [6] Rollback a file")
        print("  [7] System summary")
        print("  [B] Back")
        choice = input("  Choice: ").strip().lower()
        if choice == "1":
            r = ed.list_files()
            for f in r.get("files", []):
                print("  %s  (%s B)" % (f["path"], f["size"]))
        elif choice == "2":
            p = input("  File path: ").strip()
            r = ed.read_file(p)
            if r["ok"]:
                print(r["content"][:2000])
                if len(r["content"]) > 2000:
                    info("...truncated (%s lines total)" % r["lines"])
            else:
                err(r["error"])
        elif choice == "3":
            p = input("  File path to write: ").strip()
            info("Enter content (type END on a new line to finish):")
            lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            r = ed.write_file(p, "\n".join(lines))
            (ok("Written. Backup: %s" % r.get("backup")) if r["ok"] else err(r["error"]))
        elif choice == "4":
            p   = input("  File path: ").strip()
            old = input("  Exact text to find: ").strip()
            new = input("  Replace with: ").strip()
            r   = ed.patch_file(p, old, new)
            (ok("Patched. Backup: %s" % r.get("backup")) if r["ok"] else err(r["error"]))
        elif choice == "5":
            p = input("  Filter to file (Enter=all): ").strip()
            r = ed.list_backups(p or None)
            for b in r.get("backups", []):
                print("  %s  (%s)" % (b["backup_file"], b["created"]))
        elif choice == "6":
            p = input("  File path to restore: ").strip()
            r = ed.rollback(p)
            (ok("Restored from: %s" % r.get("restored_from")) if r["ok"] else err(r["error"]))
        elif choice == "7":
            print(_j.dumps(ed.get_system_summary(), indent=2))
        elif choice == "b":
            break
        input("\n  Press Enter to continue...")


def first_run_deploy():
    """
    ONE-HIT INSTALL. Chains the entire deployment in order, running each
    Setup step automatically only if it is not already done. Idempotent:
    safe to run repeatedly -- skips anything already complete.
    """
    cprint("\n" + B + C + "  ============================================" + W)
    cprint(B + C + "    WORDLIB ONE-HIT INSTALL" + W)
    cprint(B + C + "    Sit back -- this sets up everything." + W)
    cprint(B + C + "  ============================================" + W)

    online = have_internet()

    # A one-hit FIRST install fundamentally needs internet (packages + models).
    # If the venv already exists, we can re-run offline. Otherwise, stop clearly.
    venv_exists = venv_python().exists()
    if not online and not venv_exists:
        err("No internet, and this is a first install.")
        cprint("    The one-hit install needs internet the FIRST time to download", Y)
        cprint("    Python packages, Ollama, and the AI models.", Y)
        cprint("    Connect to the internet and run INSTALL again.", Y)
        cprint("    (After the first successful install, it runs fully offline.)", Y)
        return
    if not online:
        warn("No internet -- will use what's already installed, skip downloads.")

    # Pre-flight diagnosis -- catch blocking problems before we start
    info("[0/6] Pre-flight diagnosis...")
    try:
        sys.path.insert(0, str(SRC))
        from troubleshoot import run_all
        diags = run_all()
        blocking = [d for d in diags if not d.ok and
                    (d.check in ("File structure", "USB writable")
                     or "too old" in d.problem)]
        if blocking:
            err("Blocking problems found -- cannot install:")
            for d in blocking:
                cprint("    %s: %s" % (d.problem, d.fix), Y)
            cprint("\n  Run TROUBLESHOOT.bat for the full diagnosis.")
            return
        ok("Pre-flight passed (no blocking problems)")
    except Exception as _e:
        warn("Troubleshooter unavailable: %s" % _e)

    # Step 1: venv + packages (ensure_setup already ran in main, but confirm)
    info("[1/6] Python environment...")
    if not venv_python().exists():
        if not ensure_setup():
            err("Environment setup failed. Cannot continue.")
            return
    ok("Python environment ready")

    # Step 2: structure + heal
    info("[2/6] Verifying structure + self-heal...")
    self_heal()
    ok("Structure verified")

    # Step 3: Ollama (run Setup/01 if missing and online)
    info("[3/6] Ollama runtime + models...")
    ollama_bin = CORE / "ollama" / ("ollama.exe" if IS_WINDOWS else "ollama")
    models_dir = CORE / "ollama" / "models"
    has_models = models_dir.exists() and any(models_dir.iterdir()) if models_dir.exists() else False

    if not ollama_bin.exists() or not has_models:
        if not online:
            warn("Ollama/models missing and offline -- skipping. "
                 "Connect to internet and re-run install.")
        else:
            setup01 = ROOT / "Setup" / ("01_Install_Ollama.bat" if IS_WINDOWS else None)
            if IS_WINDOWS and setup01 and setup01.exists():
                info("Running Setup/01 (downloads Ollama + pulls models, several minutes)...")
                subprocess.run([str(setup01)], cwd=str(ROOT / "Setup"))
            elif not IS_WINDOWS:
                linux_setup = ROOT / "setup_linux.sh"
                if linux_setup.exists():
                    info("Running setup_linux.sh (installs Ollama + pulls models)...")
                    subprocess.run(["bash", str(linux_setup)], cwd=str(ROOT))
            else:
                warn("Setup script not found -- install Ollama manually via Setup/01")
    else:
        ok("Ollama + models already present")

    # Step 4: start background services
    info("[4/6] Starting background services...")
    start_services_background()
    time.sleep(8)
    ok("Services starting")

    # Step 5: start the hub (also builds RAG lazily)
    info("[5/6] Starting ETHER AI hub...")
    start_hub(open_browser=False)

    # Step 6: build/repair RAG index via the hub
    info("[6/6] Building RAG index...")
    try:
        import urllib.request
        req = urllib.request.Request(f"{HUB_URL}/api/rag/rebuild", data=b"{}",
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        urllib.request.urlopen(req, timeout=60)
        ok("RAG index built")
    except Exception as e:
        warn(f"RAG build deferred (will build on first chat): {e}")

    # Open the browser to the hub now that it's up
    import webbrowser
    webbrowser.open(HUB_URL)

    cprint("\n" + B + G + "  ============================================" + W)
    cprint(B + G + "    INSTALL COMPLETE -- ETHER AI is live" + W)
    cprint(B + G + "    Opening in your browser now." + W)
    cprint(B + G + "  ============================================" + W)
    cprint("\n  From now on, just double-click RUN_ME and pick option 1.")


def run_tests():
    """Run the WORDLIB test suite (no pytest needed)."""
    runner = ROOT / "tests" / "run_tests.py"
    if not runner.exists():
        err("Test runner not found.")
        return
    import subprocess
    subprocess.run([sys.executable, str(runner)])


def run_dashboard():
    """Show the reasoning + agent dashboard (rich if available, else ANSI)."""
    try:
        sys.path.insert(0, str(SRC))
        from agents.dashboard import show_dashboard
        show_dashboard(ROOT)
    except Exception as e:
        err("Dashboard unavailable: %s" % e)


def run_troubleshoot():
    """Run the troubleshooter -- diagnose problems with exact fixes."""
    ts = SRC / "troubleshoot.py"
    if not ts.exists():
        err("troubleshoot.py not found")
        return
    vpy = venv_python() if venv_python().exists() else Path(sys.executable)
    subprocess.run([str(vpy), str(ts)], cwd=str(ROOT))


def run_deploy_check():
    """Run deploy_check.py -- pathfinding + readiness report."""
    checker = ROOT / "deploy_check.py"
    if not checker.exists():
        err("deploy_check.py not found")
        return
    vpy = venv_python() if venv_python().exists() else Path(sys.executable)
    subprocess.run([str(vpy), str(checker)], cwd=str(ROOT))


def menu_loop():
    while True:
        print(MENU)
        choice = input("  Choose an option:  ").strip().lower()
        if   choice == "1": start_everything()
        elif choice == "2": start_ai_stack()
        elif choice == "3": start_kiwix_only()
        elif choice == "4": launch_godot()
        elif choice == "5": launch_openclaw("code")
        elif choice == "6": stop_services()
        elif choice == "7": status_report()
        elif choice == "8": content_manager_menu()
        elif choice == "9": system_editor_menu()
        elif choice == "0": run_deploy_check()
        elif choice == "t": run_troubleshoot()
        elif choice == "d": run_dashboard()
        elif choice == "x": run_tests()
        elif choice == "i": first_run_deploy()
        elif choice == "q":
            cprint("\n  Goodbye. Services you started keep running.\n")
            break
        else:
            continue
        input("\n  Press Enter to return to menu...")

# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════

BANNER = f"""
{C}{'='*56}
{B}        W O R D L I B  --  USB AI Master
        All-in-one portable AI + dev environment{W}
{C}{'='*56}{W}"""

if __name__ == "__main__":
    print(BANNER)

    # Allow direct actions: python launcher.py [all|ai|godot|openclaw|status]
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""

    if not ensure_setup():
        input("\n  Setup failed. Press Enter to exit...")
        sys.exit(1)

    self_heal()  # detect + fix issues silently every launch

    if   arg == "install":  first_run_deploy()
    elif arg == "all":      start_everything()
    elif arg == "ai":       start_ai_stack()
    elif arg == "godot":    launch_godot()
    elif arg == "openclaw": launch_openclaw("code")
    elif arg == "status":   status_report()
    else:
        menu_loop()

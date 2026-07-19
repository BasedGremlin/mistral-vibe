#!/usr/bin/env python3
"""
WORDLIB -- start_here.py
========================
The sophisticated, production-grade deployment entry point.

Uses the deployment package (state machine + stage engine + repair + JSON
logging) to run a resumable, self-healing, dependency-ordered install with
the polished ANSI console UI from auto_install.

One double-click (START_HERE.bat) runs this. It is:
  - idempotent       (re-running skips completed stages)
  - resumable        (persistent state in data/deployment_state.json)
  - self-healing     (repair pass before install)
  - dependency-aware (stages declare depends_on)
  - retry-capable    (recoverable failures back off and retry)
  - auditable        (structured JSON log in logs/deployment.log)

Flags:
  python start_here.py            normal hands-off install
  python start_here.py --reset    forget prior state, full clean re-run
  python start_here.py --quiet    minimal output (for background runs)
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC  = ROOT / "src"
APP  = ROOT / "app"
CORE = ROOT / "core"
VENV = ROOT / ".venv"
CACHE = ROOT / ".pip_cache"
IS_WINDOWS = sys.platform.startswith("win")
HUB_PORT = 5757
HUB_URL = f"http://localhost:{HUB_PORT}"

for p in (str(SRC), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Reuse the polished UI primitives + helpers from auto_install
import auto_install as ui_mod
from auto_install import (Stage as _UIStage, banner, box, hide_cursor,
                          show_cursor, venv_python, port_up, have_internet,
                          self_clean, CORE_PKGS, RAG_PKGS,
                          FG_G, FG_R, FG_Y, FG_C, FG_W, FG_GRAY, RESET, BOLD)

from deployment import (DeploymentState, Stage, StageEngine, Repairer,
                        get_deployment_logger, RecoverableError, FatalError,
                        UserActionRequired)
from deployment.absorption import (AbsorptionScanner, EnvironmentIntelligence,
                                   DeploymentMutator)


QUIET   = "--quiet" in sys.argv
ABSORB  = "--absorb" in sys.argv
MINIMAL = "--minimal" in sys.argv
ENABLE_ADVANCED = "--enable-advanced" in sys.argv or not MINIMAL  # advanced ON by default
DRY_RUN = "--dry-run" in sys.argv
USE_AGENTS = "--use-agents" in sys.argv or "--use-reasoning-agents" in sys.argv


# ── UI adapter: lets the StageEngine drive the existing ANSI progress bars ──
class ConsoleUI:
    def __init__(self, total: int):
        self.total = total
        self._stage = None

    def stage_start(self, index, total, name):
        self._stage = _UIStage(index, total, name)
        if not QUIET:
            self._stage.start()

    def progress(self, pct, status=""):
        if self._stage and not QUIET:
            self._stage.draw(pct, status)

    def stage_done(self, ok, detail=""):
        if self._stage and not QUIET:
            self._stage.finish(ok, detail)


# ── Stage action functions (each receives a progress callback) ──────────────

def _pip():
    return venv_python().parent / ("pip.exe" if IS_WINDOWS else "pip")


def act_preflight(progress):
    progress(10, "checking structure, disk, ports...")
    try:
        from troubleshoot import run_all
        diags = run_all()
        blocking = [d for d in diags if not d.ok and
                    (d.check in ("File structure", "USB writable")
                     or "too old" in d.problem)]
        progress(60, "running repair pass...")
        rep = Repairer(ROOT).run_all()
        fixes = [f"{n}: {detail}" for n, fixed, detail in rep if fixed]
        progress(100, "ready")
        if blocking:
            d = blocking[0]
            raise FatalError(d.problem, d.fix)
        return f"clean ({len(fixes)} repairs)" if fixes else "clean"
    except (FatalError, UserActionRequired):
        raise
    except Exception as e:
        return f"preflight partial ({e})"


def act_venv(progress):
    if venv_python().exists():
        progress(100, "already present")
        return "exists"
    progress(20, "creating virtual environment (~30s)...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV)],
                       check=True, timeout=120, capture_output=True)
    except subprocess.TimeoutExpired:
        raise RecoverableError("venv creation timed out",
                               "Slow USB -- it will retry.")
    except Exception as e:
        raise FatalError(f"venv creation failed: {e}",
                         "Antivirus may be blocking. Whitelist the USB or run as admin.")
    progress(100, "created")
    return "created"


def act_core_packages(progress):
    vpy = venv_python()
    have = subprocess.run([str(vpy), "-c", "import flask,flask_sqlalchemy,bs4,markdown"],
                          capture_output=True).returncode == 0
    if have:
        progress(100, "already installed")
        return "present"
    if not have_internet():
        raise UserActionRequired("Core packages missing and no internet.",
                                 "Connect to the internet and run again.")
    CACHE.mkdir(exist_ok=True)
    progress(30, "downloading flask, sqlalchemy, bs4...")
    try:
        subprocess.run([str(_pip()), "install", "--upgrade", "pip", "--quiet",
                        "--cache-dir", str(CACHE)], capture_output=True, timeout=120)
        progress(60, "installing...")
        subprocess.run([str(_pip()), "install", *CORE_PKGS, "--quiet",
                        "--no-warn-script-location", "--cache-dir", str(CACHE)],
                       check=True, timeout=300)
    except subprocess.TimeoutExpired:
        raise RecoverableError("package download timed out", "Will retry.")
    except Exception as e:
        raise FatalError(f"core package install failed: {e}",
                         "Check internet / antivirus, then re-run.")
    progress(100, "installed")
    return "installed"


def act_rag_packages(progress):
    vpy = venv_python()
    have = subprocess.run([str(vpy), "-c", "import chromadb,llama_index.core"],
                          capture_output=True).returncode == 0
    if have:
        progress(100, "already installed")
        return "present"
    if not have_internet():
        progress(100, "deferred (offline)")
        return "deferred"
    progress(40, "installing LlamaIndex + ChromaDB (2-4 min)...")
    try:
        subprocess.run([str(_pip()), "install", *RAG_PKGS, "--quiet",
                        "--no-warn-script-location", "--cache-dir", str(CACHE)],
                       check=True, timeout=480)
    except subprocess.TimeoutExpired:
        raise RecoverableError("RAG package download timed out", "Will retry.")
    except Exception:
        progress(100, "skipped (RAG optional)")
        return "skipped"
    progress(100, "installed")
    return "installed"


def act_ollama(progress):
    ollama = CORE / "ollama" / ("ollama.exe" if IS_WINDOWS else "ollama")
    models_dir = CORE / "ollama" / "models"
    has_models = models_dir.exists() and any(models_dir.iterdir()) if models_dir.exists() else False
    if (ollama.exists() or _which("ollama")) and has_models:
        progress(100, "already present")
        return "present"
    if not have_internet():
        progress(100, "deferred (offline)")
        return "deferred"
    progress(10, "downloading Ollama + models (~10 GB, long)...")
    setup01 = ROOT / "Setup" / "01_Install_Ollama.bat"
    linux_setup = ROOT / "setup_linux.sh"
    try:
        if IS_WINDOWS and setup01.exists():
            subprocess.run([str(setup01)], cwd=str(ROOT / "Setup"))
        elif not IS_WINDOWS and linux_setup.exists():
            subprocess.run(["bash", str(linux_setup)], cwd=str(ROOT))
        else:
            progress(100, "setup script missing -- deferred")
            return "deferred"
    except Exception as e:
        raise RecoverableError(f"model pull interrupted: {e}",
                               "Re-run -- Ollama resumes where it stopped.")
    progress(100, "models ready")
    return "installed"


def act_services(progress):
    vpy = venv_python() if venv_python().exists() else Path(sys.executable)
    progress(20, "starting Ollama, Kiwix, Open WebUI...")
    try:
        if IS_WINDOWS:
            subprocess.Popen(
                f'start "WORDLIB Services" cmd /k "{vpy} \"{SRC/"usb_orchestrator.py"}\""',
                shell=True)
        else:
            subprocess.Popen([str(vpy), str(SRC / "usb_orchestrator.py")],
                             start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return f"deferred ({e})"
    for p in range(40, 101, 20):
        progress(p, "warming up..."); time.sleep(0.6)
    return "running"


def act_hub(progress):
    if port_up(HUB_PORT):
        progress(100, "already live")
        return "live"
    vpy = venv_python() if venv_python().exists() else Path(sys.executable)
    (ROOT / "logs").mkdir(exist_ok=True)
    env = {**os.environ, "ETHER_PORT": str(HUB_PORT), "ETHER_BASE": str(ROOT)}
    logf = open(ROOT / "logs" / "ether_hub.log", "a", encoding="utf-8")
    flags = 0x08000000 if IS_WINDOWS else 0  # CREATE_NO_WINDOW
    progress(20, "launching hub on port 5757...")
    subprocess.Popen([str(vpy), "main.py"], cwd=str(APP), env=env,
                     stdout=logf, stderr=subprocess.STDOUT,
                     creationflags=flags if IS_WINDOWS else 0,
                     start_new_session=not IS_WINDOWS)
    for i in range(20):
        time.sleep(0.5)
        progress(min(95, 20 + i * 5), "waiting for hub...")
        if port_up(HUB_PORT):
            progress(100, "live")
            return "live"
    raise RecoverableError("hub did not come up in time",
                           "It may still be starting. Re-run if needed.")


def act_rag_index(progress):
    progress(20, "building knowledge index over storage/...")
    try:
        req = urllib.request.Request(f"{HUB_URL}/api/rag/rebuild", data=b"{}",
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        for p in range(40, 90, 15):
            progress(p); time.sleep(0.3)
        urllib.request.urlopen(req, timeout=90)
        progress(100, "indexed")
        return "indexed"
    except Exception:
        progress(100, "will build on first chat")
        return "deferred"


def _which(name):
    from shutil import which
    return which(name)


# ── Build the stage graph ────────────────────────────────────────────────────

def act_absorption(progress):
    """
    Final-stage absorption pass: scan capabilities, read hardware, apply safe
    deployment mutations. Real facts only -- activates what genuinely exists.
    """
    progress(15, "scanning capabilities...")
    scanner = AbsorptionScanner(ROOT)
    caps = scanner.scan_capabilities()

    progress(45, "reading hardware profile...")
    env = EnvironmentIntelligence(ROOT).profile()

    progress(70, "applying deployment mutations...")
    applied = []
    if ENABLE_ADVANCED and not DRY_RUN:
        mut = DeploymentMutator(ROOT)
        m1 = mut.apply_rag_chunk_tuning(env.recommended_rag_chunk)
        m2 = mut.apply_logging_defaults()
        applied = [m for m in (m1, m2) if m]

    # Stash results for the summary
    act_absorption.caps = caps
    act_absorption.env = env
    act_absorption.mutations = applied
    progress(100, "absorption complete")
    active = sum(1 for c in caps if c.available)
    return f"{active}/{len(caps)} capabilities active"


# Storage for the summary
act_absorption.caps = []
act_absorption.env = None
act_absorption.mutations = []


def act_agent_selfcheck(progress):
    """Optional: bring up the agent swarm and run a real self-check."""
    progress(20, "initializing agent swarm...")
    try:
        from agents import get_orchestrator, Task
    except Exception as e:
        return f"agents unavailable ({e})"
    orch = get_orchestrator(ROOT)
    st = orch.status()
    progress(60, "running swarm self-test...")
    # Real test: parse-check via TestAgent + power via AbsorptionAgent
    t = orch.route(Task("test", {}))
    p = orch.route(Task("power", {}))
    progress(100, "swarm ready")
    act_agent_selfcheck.summary = {
        "agents": f"{st['available_count']}/{st['agent_count']}",
        "test": t.detail, "power": p.detail,
    }
    return f"swarm {st['available_count']}/{st['agent_count']} agents ready"


act_agent_selfcheck.summary = {}


def build_stages():
    base = [
        Stage("preflight",     act_preflight),
        Stage("venv",          act_venv,          depends_on=["preflight"]),
        Stage("core_packages", act_core_packages, depends_on=["venv"]),
        Stage("rag_packages",  act_rag_packages,  depends_on=["venv"], optional=True),
        Stage("ollama",        act_ollama,        depends_on=["core_packages"], optional=True),
        Stage("services",      act_services,      depends_on=["core_packages"], optional=True),
        Stage("hub",           act_hub,           depends_on=["services"]),
        Stage("rag_index",     act_rag_index,     depends_on=["hub"], optional=True),
        Stage("absorption",    act_absorption,    depends_on=["hub"], optional=True),
    ]
    if USE_AGENTS:
        base.append(Stage("agent_swarm", act_agent_selfcheck,
                          depends_on=["hub"], optional=True))
    return base


def _print_power_summary():
    """Beautiful final summary showing the deployed system's power level."""
    caps = act_absorption.caps
    env = act_absorption.env
    muts = act_absorption.mutations
    if not caps:
        return

    active = [c for c in caps if c.available]
    premium = [c for c in active if c.tier == "premium"]
    print()
    box("SYSTEM POWER LEVEL", FG_C)
    # Power bar from real active-capability ratio
    ratio = len(active) / max(1, len(caps))
    bar_w = 40
    filled = int(ratio * bar_w)
    bar = f"{FG_G}{'█' * filled}{FG_GRAY}{'░' * (bar_w - filled)}{RESET}"
    print(f"\n  {bar} {FG_W}{int(ratio*100)}%{RESET}")
    print(f"  {FG_W}{len(active)}/{len(caps)} capabilities active "
          f"({len(premium)} premium){RESET}\n")

    for c in caps:
        if c.available:
            tag = f"{FG_Y}[PREMIUM]{RESET}" if c.tier == "premium" else f"{FG_G}[active]{RESET}"
            print(f"  {tag} {c.name}")
        else:
            print(f"  {FG_GRAY}[ later ] {c.name} -- {c.detail}{RESET}")

    # Deployment mode (scaling)
    try:
        from deployment.scaling import get_profile
        prof = get_profile(ROOT)
        print(f"\n  {FG_C}Deployment mode:{RESET} {prof.mode.value.upper()} "
              f"({prof.reason})")
        print(f"  {FG_C}Scaling:{RESET}    up to {prof.max_model_params_b}B models, "
              f"{prof.max_parallel_agents} parallel agents, "
              f"heavy-optional={'yes' if prof.allow_heavy_optional else 'no'}")
    except Exception:
        pass

    if env:
        print(f"\n  {FG_C}Environment:{RESET} {env.cpu_count} cores, "
              f"{env.ram_gb or '?'} GB RAM, {env.disk_free_gb} GB free")
        print(f"  {FG_C}Tuned for:{RESET}  {env.recommended_model_tier}")
        print(f"  {FG_C}RAG chunk:{RESET}  {env.recommended_rag_chunk}")
    if muts:
        print(f"\n  {FG_C}Deployment mutations applied:{RESET}")
        for m in muts:
            print(f"    {FG_G}+{RESET} {m}")


def main():
    log = get_deployment_logger(ROOT)
    state = DeploymentState(ROOT)

    if "--reset" in sys.argv:
        state.reset()
        try:
            from deployment.absorption import DeploymentMutator
            DeploymentMutator(ROOT).rollback_all()
        except Exception:
            pass
        log.info("deployment state + mutations reset by user")

    if not QUIET:
        banner()
        time.sleep(0.3)
        cleaned = self_clean()
        if cleaned:
            print(f"  {FG_GRAY}Self-clean: removed {len(cleaned)} stale item(s).{RESET}")

    online = have_internet()
    if not online and not venv_python().exists():
        if not QUIET:
            box("CANNOT INSTALL -- NO INTERNET", FG_R)
            print(f"\n  {FG_Y}First install needs internet (packages + models).{RESET}")
            print(f"  {FG_W}Connect and run again.{RESET}\n")
        log.error("first install attempted offline")
        return 1

    if not QUIET:
        box("DEPLOYING -- resumable, self-healing, hands-off", FG_C)
        done = state.completed_count()
        if done:
            print(f"  {FG_GRAY}Resuming -- {done} stage(s) already complete.{RESET}")

    stages = build_stages()
    ui = ConsoleUI(len(stages))
    engine = StageEngine(state, ui=ui)

    hide_cursor()
    try:
        success = engine.run_all(stages)
    finally:
        show_cursor()

    # Report
    for r in engine.results:
        status = "DONE" if r.ok else "FAIL"
        log.info(f"stage {r.name}: {status}",
                 extra={"ctx_stage": r.name, "ctx_ok": r.ok, "ctx_detail": r.detail})

    if success:
        if not QUIET:
            _print_power_summary()
            print()
            box("DEPLOYMENT COMPLETE", FG_G)
            print(f"\n  {FG_G}{BOLD}ETHER AI is live.{RESET}  Opening in your browser.")
            print(f"  {FG_W}{HUB_URL}{RESET}")
            print(f"\n  {FG_GRAY}From now on: double-click RUN_ME.bat -> option 1{RESET}\n")
        if port_up(HUB_PORT) and not DRY_RUN:
            webbrowser.open(HUB_URL)
        return 0
    else:
        # Find the failing stage and print its fix
        failed = next((r for r in engine.results if not r.ok), None)
        if not QUIET and failed and failed.error:
            print()
            box("DEPLOYMENT PAUSED", FG_Y)
            print(f"\n  {FG_R}Stage '{failed.name}' could not complete.{RESET}")
            print(f"  {FG_R}Problem:{RESET} {failed.error.message}")
            print(f"  {FG_G}Fix:{RESET}     {failed.error.fix}")
            print(f"\n  {FG_GRAY}Fix it and run START_HERE again -- it resumes from here.{RESET}")
            print(f"  {FG_GRAY}Or run TROUBLESHOOT.bat for a full diagnosis.{RESET}\n")
        log.error(f"deployment paused at {failed.name if failed else '?'}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

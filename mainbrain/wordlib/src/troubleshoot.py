"""
WORDLIB Troubleshooter
======================
Diagnoses the real failure modes a deployment hits and offers concrete,
actionable fixes. Called by the install chain when a step fails, and
available standalone: python src/troubleshoot.py

Every check returns a Diagnosis: what's wrong, why, and the exact fix.
No vague "something went wrong" -- each result is actionable.
"""

import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_SRC_DIR  = Path(__file__).resolve().parent
_USB_ROOT = _SRC_DIR.parent
IS_WINDOWS = platform.system() == "Windows"


@dataclass
class Diagnosis:
    check: str
    ok: bool
    problem: str = ""
    fix: str = ""

    def render(self) -> str:
        if self.ok:
            return f"  [OK]  {self.check}"
        return (f"  [!!]  {self.check}\n"
                f"        Problem: {self.problem}\n"
                f"        Fix:     {self.fix}")


# ── Individual diagnostics ───────────────────────────────────────────────────

def diag_python() -> Diagnosis:
    v = sys.version_info
    if v < (3, 8):
        return Diagnosis("Python version", False,
                         f"Python {v.major}.{v.minor} is too old (need 3.8+).",
                         "Install Python 3.8 or newer from python.org, "
                         "tick 'Add to PATH', then re-run INSTALL.")
    return Diagnosis(f"Python {v.major}.{v.minor}.{v.micro}", True)


def diag_disk_space() -> Diagnosis:
    try:
        free_gb = shutil.disk_usage(str(_USB_ROOT)).free / 1_073_741_824
    except Exception as e:
        return Diagnosis("Disk space", False, f"Could not read disk: {e}",
                         "Check the USB is properly connected.")
    if free_gb < 2.0:
        return Diagnosis("Disk space", False,
                         f"Only {free_gb:.1f} GB free -- not enough for models.",
                         "Free up space or use a larger USB. Full install needs ~18 GB. "
                         "You can still run a minimal setup; skip the Wikipedia ZIM.")
    if free_gb < 15.0:
        return Diagnosis("Disk space", True)  # enough for partial install
    return Diagnosis(f"Disk space ({free_gb:.0f} GB free)", True)


def diag_internet() -> Diagnosis:
    try:
        socket.setdefaulttimeout(4)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return Diagnosis("Internet", True)
    except OSError:
        return Diagnosis("Internet", False,
                         "No internet connection detected.",
                         "Connect to the internet for first-time install "
                         "(downloads Ollama + models). Not needed after setup.")


def diag_ports() -> List[Diagnosis]:
    results = []
    for port, name in ((5757, "ETHER AI hub"), (11434, "Ollama"),
                       (8080, "Kiwix"), (3000, "Open WebUI")):
        in_use = _port_in_use(port)
        if in_use:
            # Port in use is only a problem if it's NOT our own service
            results.append(Diagnosis(
                f"Port {port} ({name})", False,
                f"Port {port} is already in use by another program.",
                f"If WORDLIB isn't already running, find and close whatever uses "
                f"port {port}. On Windows: netstat -ano | findstr {port}, then "
                f"taskkill /PID <pid> /F. Or change the port in config."))
        else:
            results.append(Diagnosis(f"Port {port} ({name}) free", True))
    return results


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def diag_venv() -> Diagnosis:
    venv = _USB_ROOT / ".venv" / ("Scripts" if IS_WINDOWS else "bin") / \
           ("python.exe" if IS_WINDOWS else "python")
    if venv.exists():
        return Diagnosis("Python venv", True)
    return Diagnosis("Python venv", False,
                     "Virtual environment not built yet.",
                     "This builds automatically on first launch. If it keeps "
                     "failing: your antivirus may be blocking it -- whitelist "
                     "the USB drive, or run RUN_ME.bat as Administrator once.")


def diag_ollama() -> Diagnosis:
    ollama = _USB_ROOT / "core" / "ollama" / ("ollama.exe" if IS_WINDOWS else "ollama")
    on_path = shutil.which("ollama")
    if ollama.exists() or on_path:
        # Installed -- can it actually run?
        binary = str(ollama) if ollama.exists() else on_path
        try:
            r = subprocess.run([binary, "--version"], capture_output=True,
                               text=True, timeout=10)
            if r.returncode == 0:
                return Diagnosis("Ollama runtime", True)
            return Diagnosis("Ollama runtime", False,
                             "Ollama is present but won't run.",
                             "On Windows it may need the Visual C++ runtime. "
                             "Re-run Setup/01, or download Ollama from ollama.com directly.")
        except Exception as e:
            return Diagnosis("Ollama runtime", False,
                             f"Ollama present but failed to start: {e}",
                             "Re-run Setup/01_Install_Ollama.bat.")
    return Diagnosis("Ollama runtime", False,
                     "Ollama not installed.",
                     "Run Setup/01_Install_Ollama.bat (Windows) or "
                     "setup_linux.sh (Linux). Needs internet (~60 MB).")


def diag_models() -> Diagnosis:
    models_dir = _USB_ROOT / "core" / "ollama" / "models"
    gguf = list((_USB_ROOT / "models").glob("*.gguf")) if (_USB_ROOT / "models").exists() else []
    has_ollama_models = (models_dir.exists() and any(models_dir.iterdir())
                         if models_dir.exists() else False)
    if has_ollama_models or gguf:
        return Diagnosis("AI models", True)
    return Diagnosis("AI models", False,
                     "No AI models found.",
                     "Run Setup/01 to pull qwen2.5-coder, dolphin3, nomic-embed-text "
                     "(~10 GB total). If a pull times out on slow internet, just "
                     "re-run Setup/01 -- Ollama resumes where it left off.")


def diag_structure() -> Diagnosis:
    critical = ["launcher.py", "app/main.py", "src/ether_core.py",
                "src/rag_manager.py", "config/creative.json"]
    missing = [f for f in critical if not (_USB_ROOT / f).exists()]
    if missing:
        return Diagnosis("File structure", False,
                         f"Critical files missing: {', '.join(missing)}",
                         "Re-extract the wordlib zip to the USB. The copy was "
                         "incomplete or interrupted.")
    return Diagnosis("File structure", True)


def diag_write_permission() -> Diagnosis:
    """USB must be writable (not read-only / write-protected)."""
    test_file = _USB_ROOT / ".write_test"
    try:
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        return Diagnosis("USB writable", True)
    except Exception as e:
        return Diagnosis("USB writable", False,
                         f"Cannot write to USB: {e}",
                         "The USB may be write-protected (check the physical "
                         "lock switch if it has one), or you lack permissions. "
                         "WORDLIB needs to write models, data, and backups.")


# ── Runner ───────────────────────────────────────────────────────────────────

def run_all() -> List[Diagnosis]:
    """Run every diagnostic and return the full list."""
    results: List[Diagnosis] = []
    results.append(diag_structure())
    results.append(diag_write_permission())
    results.append(diag_python())
    results.append(diag_disk_space())
    results.append(diag_internet())
    results.append(diag_venv())
    results.append(diag_ollama())
    results.append(diag_models())
    results.extend(diag_ports())
    return results


def diagnose_and_report() -> bool:
    """Run all checks, print a report, return True if no blocking problems."""
    print()
    print("=" * 60)
    print("  WORDLIB Troubleshooter -- diagnosing deployment")
    print("=" * 60)
    print()

    results = run_all()
    problems = [r for r in results if not r.ok]

    for r in results:
        print(r.render())

    print()
    print("=" * 60)
    if not problems:
        print("  No problems found. System is healthy.")
    else:
        # Separate blocking from non-blocking
        blocking = [r for r in problems if r.check in (
            "File structure", "USB writable") or "too old" in r.problem]
        print(f"  {len(problems)} issue(s) found "
              f"({len(blocking)} blocking, {len(problems)-len(blocking)} fixable).")
        print("  See the [!!] items above for the exact fix for each.")
    print("=" * 60)
    print()
    return len(problems) == 0


# ── Targeted helpers (called by the install chain on specific failures) ──────

def explain_failure(step: str) -> str:
    """Given a failed install step name, return the most likely cause + fix."""
    explanations = {
        "venv": diag_venv(),
        "packages": Diagnosis("Package install", False,
            "pip could not install required packages.",
            "Usually a network or antivirus block. Check internet, temporarily "
            "disable real-time antivirus scanning of the USB, and re-run. "
            "Packages cache in .pip_cache/ so retries are faster."),
        "ollama": diag_ollama(),
        "models": diag_models(),
        "disk": diag_disk_space(),
        "internet": diag_internet(),
    }
    diag = explanations.get(step)
    if diag and not diag.ok:
        return f"{diag.problem}\n  Fix: {diag.fix}"
    return "Unknown step. Run 'python src/troubleshoot.py' for a full diagnosis."


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Explain a specific step
        print(explain_failure(sys.argv[1]))
    else:
        healthy = diagnose_and_report()
        sys.exit(0 if healthy else 1)

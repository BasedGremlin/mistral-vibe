"""
WORDLIB USB Orchestrator
========================
Manages background services: Ollama, Kiwix, Open WebUI.
Also initialises the RAG index after Ollama is confirmed running.

Run directly:   python src/usb_orchestrator.py
Or import:      from usb_orchestrator import USBServiceOrchestrator

Folder layout assumed:
  wordlib/                     <- USB_ROOT
    src/
      usb_orchestrator.py      <- this file
      rag_manager.py           <- imported below
    core/
      ollama/
        ollama.exe             <- Windows binary
        models/                <- Ollama model storage (stays on USB)
      kiwix/
        kiwix-serve.exe        <- Windows binary
        library.xml            <- Kiwix library manifest
      open-webui/
        data/                  <- Open WebUI persistent data
      venv/                    <- Python venv for orchestrator deps
    logs/
      usb_orchestrator.log
      ollama.log
      kiwix.log
      open-webui.log

Services managed:
  ollama      port 11434
  kiwix       port 8080
  open-webui  port 3000

ETHER AI Flask app (main.py) is NOT managed here -- it is started
by launcher.py which runs venv setup first.
"""

import os
import sys
import time
import socket
import logging
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, IO, List, Optional

# ── Platform detection ─────────────────────────────────────────────────────
IS_WINDOWS   = platform.system() == "Windows"
EXE_EXT      = ".exe" if IS_WINDOWS else ""
VENV_BIN_DIR = "Scripts" if IS_WINDOWS else "bin"

# ── Paths (all relative to this file -- USB-portable) ─────────────────────
_SRC_DIR  = Path(__file__).resolve().parent    # wordlib/src/
_USB_ROOT = _SRC_DIR.parent                     # wordlib/
_CORE_DIR = _USB_ROOT / "core"                  # wordlib/core/
_LOGS_DIR = _USB_ROOT / "logs"

_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            _LOGS_DIR / "usb_orchestrator.log",
            encoding="utf-8",
            mode="a",
        ),
    ],
)
logger = logging.getLogger("orchestrator")

# ── RAG import (optional -- orchestrator still works without it) ───────────
try:
    # Both files live in the same src/ directory, so a plain import works
    # when running as: python src/usb_orchestrator.py
    # If imported from elsewhere, sys.path may need adjusting.
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))
    from rag_manager import USBRAGManager
    _RAG_AVAILABLE = True
except ImportError:
    logger.warning("rag_manager.py not importable. RAG disabled.")
    _RAG_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────
#  SERVICE CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class ServiceConfig:
    name:          str
    binary_path:   str          # Absolute path to executable (or python interpreter)
    args:          List[str]    # Arguments passed to the binary
    port:          int          # Port to health-check after startup
    env_updates:   Dict[str, str] = field(default_factory=dict)
    startup_delay: int = 3      # Seconds to wait before port check


def _build_configs() -> Dict[str, ServiceConfig]:
    """
    Build service configs using paths relative to USB_ROOT.
    All paths resolve correctly regardless of which drive letter Windows assigns.
    """
    # Python interpreter: prefer the venv inside core/, fallback to system Python
    venv_python = _CORE_DIR / "venv" / VENV_BIN_DIR / f"python{EXE_EXT}"
    python_cmd  = str(venv_python) if venv_python.exists() else sys.executable

    return {
        "ollama": ServiceConfig(
            name="Ollama",
            binary_path=str(_CORE_DIR / "ollama" / f"ollama{EXE_EXT}"),
            args=["serve"],
            port=11434,
            env_updates={
                # Keep models on USB so they travel with the stick
                "OLLAMA_MODELS": str(_CORE_DIR / "ollama" / "models"),
                "OLLAMA_HOST":   "127.0.0.1:11434",
            },
            startup_delay=6,
        ),

        "kiwix": ServiceConfig(
            name="Kiwix Grokipedia",
            binary_path=str(_CORE_DIR / "kiwix" / f"kiwix-serve{EXE_EXT}"),
            args=[
                "--port",    "8080",
                "--library", str(_CORE_DIR / "kiwix" / "library.xml"),
            ],
            port=8080,
            startup_delay=3,
        ),

        "open-webui": ServiceConfig(
            name="Open WebUI",
            binary_path=python_cmd,
            # open-webui >= 0.3 exposes `open_webui serve --port N`
            args=["-m", "open_webui", "serve", "--port", "3000"],
            port=3000,
            env_updates={
                # Persist chats/settings on USB
                "DATA_DIR":         str(_CORE_DIR / "open-webui" / "data"),
                "OLLAMA_BASE_URL":  "http://127.0.0.1:11434",
                # Disable signup prompt on first launch
                "WEBUI_AUTH":       "False",
            },
            startup_delay=8,
        ),
    }


# ─────────────────────────────────────────────────────────────────────────
#  ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────

class USBServiceOrchestrator:
    """
    Starts, monitors, and cleanly stops all WORDLIB background services.

    Typical usage:
        orch = USBServiceOrchestrator()
        orch.start_all()
        orch.monitor()          # blocks until Ctrl+C
    """

    def __init__(self) -> None:
        self.configs:    Dict[str, ServiceConfig]           = _build_configs()
        self.processes:  Dict[str, Optional[subprocess.Popen]] = {}
        self.log_files:  Dict[str, IO]                      = {}
        self.rag:        Optional[USBRAGManager]            = None
        self._running    = False

    # ── Helpers ────────────────────────────────────────────────────────────

    def _port_active(self, port: int) -> bool:
        """Return True if something is already listening on the port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0

    def _open_log(self, key: str) -> IO:
        """Open (or reopen) a per-service log file."""
        path = _LOGS_DIR / f"{key}.log"
        f    = open(path, "a", encoding="utf-8", buffering=1)
        self.log_files[key] = f
        return f

    # ── Service lifecycle ──────────────────────────────────────────────────

    def launch_service(self, key: str) -> bool:
        """
        Launch a single service by key.
        Returns True if the service is healthy (or was already running).
        Returns False if the binary is missing or the port never came up.
        """
        cfg = self.configs.get(key)
        if cfg is None:
            logger.error(f"Unknown service key: {key!r}")
            return False

        # Already running?
        if self._port_active(cfg.port):
            logger.info(f"{cfg.name}: already running on port {cfg.port}")
            return True

        # Binary present?
        binary = Path(cfg.binary_path)
        if not binary.exists() and cfg.binary_path != sys.executable:
            logger.error(
                f"{cfg.name}: binary not found at {cfg.binary_path}. "
                "Run the matching setup script in Setup/ first."
            )
            return False

        logger.info(f"{cfg.name}: starting...")

        env = os.environ.copy()
        env.update(cfg.env_updates)

        try:
            log_fh = self._open_log(key)
            creation_flags = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0

            proc = subprocess.Popen(
                [cfg.binary_path] + cfg.args,
                env=env,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            self.processes[key] = proc
        except Exception as e:
            logger.error(f"{cfg.name}: failed to start process -- {e}")
            return False

        # Wait and verify
        time.sleep(cfg.startup_delay)
        if proc.poll() is not None:
            logger.error(
                f"{cfg.name}: process exited immediately (code {proc.returncode}). "
                f"Check logs/{key}.log for details."
            )
            return False

        if self._port_active(cfg.port):
            logger.info(f"{cfg.name}: [OK] running on port {cfg.port}")
            return True

        logger.warning(
            f"{cfg.name}: process alive but port {cfg.port} not responding yet. "
            "May still be starting -- monitoring will retry."
        )
        return False

    def stop_service(self, key: str) -> None:
        """Terminate a single service gracefully."""
        proc = self.processes.get(key)
        if proc and proc.poll() is None:
            try:
                if IS_WINDOWS:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True,
                        timeout=5,
                    )
                else:
                    proc.terminate()
                    proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            logger.info(f"{self.configs[key].name}: stopped.")

        fh = self.log_files.pop(key, None)
        if fh:
            try:
                fh.close()
            except Exception:
                pass
        self.processes.pop(key, None)

    # ── RAG ────────────────────────────────────────────────────────────────

    def _init_rag(self) -> None:
        """Initialise RAG after Ollama is confirmed healthy."""
        if not _RAG_AVAILABLE:
            logger.info("RAG packages not available -- skipping.")
            return
        if not self._port_active(11434):
            logger.warning("Ollama not reachable -- RAG init skipped.")
            return

        logger.info("Initialising RAG index...")
        try:
            self.rag = USBRAGManager()
            success  = self.rag.build_index()
            if success:
                stats = self.rag.get_stats()
                logger.info(
                    f"RAG ready -- {stats.get('total_chunks', '?')} chunks "
                    f"across {len(stats.get('folders', []))} folders."
                )
            else:
                logger.warning("RAG build returned False -- running without RAG.")
                self.rag = None
        except Exception as e:
            logger.error(f"RAG init raised: {e}")
            self.rag = None

    # ── Orchestration ──────────────────────────────────────────────────────

    def start_all(self) -> None:
        """Start all services in dependency order, then init RAG."""
        self._running = True
        logger.info("=" * 50)
        logger.info("WORDLIB orchestrator starting...")
        logger.info(f"USB root: {_USB_ROOT}")
        logger.info("=" * 50)

        # Start order matters: Ollama first (RAG + Open WebUI depend on it)
        for key in ["ollama", "kiwix", "open-webui"]:
            if not self._running:
                break
            self.launch_service(key)

        # RAG only after Ollama is healthy
        if self._running:
            self._init_rag()

        logger.info("All services launched.")
        logger.info(f"  Ollama    : http://localhost:11434")
        logger.info(f"  Kiwix     : http://localhost:8080")
        logger.info(f"  Open WebUI: http://localhost:3000")
        logger.info(f"  ETHER AI  : http://localhost:5757  (started by launcher.py)")

    def stop_all(self) -> None:
        """Stop all managed services cleanly."""
        self._running = False
        for key in list(self.processes.keys()):
            self.stop_service(key)
        self.rag = None
        logger.info("All services stopped.")

    def monitor(self, interval: int = 15) -> None:
        """
        Blocking monitor loop. Checks each service port every `interval` seconds.
        Restarts crashed services automatically.
        Press Ctrl+C to stop everything.
        """
        logger.info(f"Monitoring services every {interval}s. Press Ctrl+C to stop.")
        try:
            while self._running:
                time.sleep(interval)
                for key, cfg in self.configs.items():
                    if not self._running:
                        break
                    if not self._port_active(cfg.port):
                        logger.warning(f"{cfg.name}: down. Attempting restart...")
                        self.stop_service(key)          # Clean up stale process
                        if self.launch_service(key):
                            # If Ollama recovered, re-init RAG
                            if key == "ollama":
                                self._init_rag()
                        else:
                            logger.error(f"{cfg.name}: restart failed.")

        except KeyboardInterrupt:
            logger.info("Ctrl+C received -- shutting down.")
        finally:
            self.stop_all()

    # ── Convenience ────────────────────────────────────────────────────────

    def rag_query(self, text: str, top_k: int = 5):
        """
        Run a RAG query and return results.
        Returns [] if RAG is not initialised.
        Intended to be called by main.py via a shared orchestrator instance.
        """
        if self.rag is None:
            return []
        return self.rag.query(text, top_k=top_k)

    def rag_stats(self) -> Dict:
        if self.rag is None:
            return {"status": "not_initialised"}
        return self.rag.get_stats()

    def status_report(self) -> Dict:
        """Return a dict summarising all service health."""
        return {
            key: {
                "name":    cfg.name,
                "port":    cfg.port,
                "running": self._port_active(cfg.port),
            }
            for key, cfg in self.configs.items()
        }


# ─────────────────────────────────────────────────────────────────────────
#  ENTRY POINT (run directly: python src/usb_orchestrator.py)
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    orch = USBServiceOrchestrator()
    try:
        orch.start_all()
        orch.monitor()
    except Exception as e:
        logger.critical(f"Fatal orchestrator error: {e}", exc_info=True)
        orch.stop_all()
        sys.exit(1)

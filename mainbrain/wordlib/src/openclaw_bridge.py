"""
WORDLIB OpenClaw Bridge -- Ollama coding agent launcher.

Optional. Nothing else breaks if OpenClaw isn't installed.
Depends only on Ollama (port 11434). Does not manage Ollama itself.

Default model: qwen2.5-coder:7b-instruct-q4_K_M (best for code / GDScript).
RAG access goes through the ETHER AI hub over HTTP, so coding sessions can
pull relevant context from your knowledge base.
"""

import json
import logging
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

# An Ollama model reference: optional registry/namespace path, name, optional
# :tag and optional @digest. Deliberately excludes shell metacharacters, quotes
# and whitespace -- see the guard in launch() for why that matters.
_VALID_MODEL_TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-/]*(:[A-Za-z0-9._\-]+)?(@sha256:[a-f0-9]+)?")

logger = logging.getLogger("openclaw_bridge")

# Path resolution via the single source of truth (core.paths), guarded fallback.
try:
    from core.paths import PATHS
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.paths import PATHS

_SRC_DIR   = PATHS.src
_USB_ROOT  = PATHS.root
_CONFIG    = PATHS.config / "creative.json"
IS_WINDOWS = platform.system() == "Windows"

# sibling-import requirement (hub_client etc.), not path discovery
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
try:
    from hub_client import HubClient
except ImportError:
    HubClient = None


def _load_config() -> Dict[str, Any]:
    try:
        with open(_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("creative.json not found -- using defaults.")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"creative.json invalid: {e}")
        return {}
    except Exception as e:
        logger.error(f"creative.json load error: {e}")
        return {}


class OpenClawBridge:
    """Launches the OpenClaw coding agent against a local Ollama model."""

    def __init__(self) -> None:
        self.config        = _load_config()
        self.oc_cfg        = self.config.get("openclaw", {})
        self.ollama_url    = self.oc_cfg.get("ollama_url", "http://127.0.0.1:11434")
        self.default_model = self.oc_cfg.get(
            "default_model", "qwen2.5-coder:7b-instruct-q4_K_M")
        self.fallback_model = self.oc_cfg.get(
            "fallback_model", "dolphin3:8b-llama3.1-q4_K_M")
        self.profiles = self.oc_cfg.get("profiles", {})
        self.work_dir = (_USB_ROOT / self.oc_cfg.get(
            "work_dir", "GodotProjects")).resolve()
        self.hub = HubClient() if HubClient else None

    def is_ollama_up(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Could not list Ollama models: {e}")
            return []

    def is_model_available(self, tag: str) -> bool:
        models = self.list_models()
        base = tag.split(":")[0]
        return any(m == tag or m.startswith(base) for m in models)

    def resolve_model(self, profile: str = "code") -> str:
        """profile model -> default -> fallback, preferring what's pulled."""
        candidates = []
        prof = self.profiles.get(profile, {})
        if prof.get("model"):
            candidates.append(prof["model"])
        candidates.append(self.default_model)
        candidates.append(self.fallback_model)

        for tag in candidates:
            if self.is_model_available(tag):
                return tag

        logger.warning(f"No configured model pulled. Run: ollama pull {candidates[0]}")
        return candidates[0]

    def rag_query(self, query: str, top_k: int = 4) -> list:
        """Pull coding-relevant context from the RAG hub. [] if hub down."""
        if not self.hub:
            return []
        return self.hub.rag_query(query, top_k=top_k)

    def _find_ollama_binary(self) -> Optional[str]:
        ext = ".exe" if IS_WINDOWS else ""
        usb_ollama = _USB_ROOT / "core" / "ollama" / f"ollama{ext}"
        if usb_ollama.exists():
            return str(usb_ollama)
        return shutil.which("ollama")

    def launch(self, profile: str = "code",
               work_dir: Optional[str] = None) -> bool:
        """Launch OpenClaw in a terminal with the chosen profile's model."""
        if not self.is_ollama_up():
            logger.error("Ollama not running. Start the AI stack first.")
            return False

        model = self.resolve_model(profile)
        target_dir = Path(work_dir) if work_dir else self.work_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        ollama_bin = self._find_ollama_binary()
        if not ollama_bin:
            logger.error("ollama binary not found. Run the Ollama setup step first.")
            return False

        # `model` is interpolated into a shell=True command line below, so it is
        # an injection point. It comes from the profiles config rather than from
        # the network, which lowers the severity -- but the self-editing system
        # can write config, so "the config is trusted" is an assumption this
        # module should not have to make. A real Ollama tag is name[:tag] with
        # optional registry path, so anything outside that charset is not a
        # usable model name in the first place and refusing it costs nothing.
        if not _VALID_MODEL_TAG.fullmatch(model):
            logger.error(
                "Refusing to launch: model tag %r contains characters that are "
                "not valid in an Ollama tag and would be interpolated into a "
                "shell command.", model)
            return False

        logger.info(f"Launching OpenClaw -- profile={profile}, model={model}")
        oc_cmd = f'"{ollama_bin}" launch openclaw --model {model}'

        try:
            if IS_WINDOWS:
                full = (f'start "OpenClaw [{profile}]" cmd /k '
                        f'"cd /d ""{target_dir}"" && {oc_cmd}"')
                subprocess.Popen(full, shell=True)
            else:
                inner = f'cd "{target_dir}" && {oc_cmd}; exec bash'
                for term in (["gnome-terminal", "--"], ["konsole", "-e"],
                             ["xterm", "-e"], ["x-terminal-emulator", "-e"]):
                    try:
                        subprocess.Popen(term + ["bash", "-c", inner],
                                         start_new_session=True)
                        break
                    except FileNotFoundError:
                        continue
                else:
                    logger.error("No supported terminal found on Linux.")
                    return False
            return True
        except Exception as e:
            logger.error(f"Failed to launch OpenClaw: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        ollama_up = self.is_ollama_up()
        return {
            "enabled":        self.oc_cfg.get("enabled", True),
            "ollama_up":      ollama_up,
            "default_model":  self.default_model,
            "fallback_model": self.fallback_model,
            "models_pulled":  self.list_models() if ollama_up else [],
            "profiles":       list(self.profiles.keys()),
            "work_dir":       str(self.work_dir),
            "ollama_binary":  self._find_ollama_binary(),
            "hub_up":         self.hub.is_up() if self.hub else False,
            "platform":       platform.system(),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    bridge = OpenClawBridge()
    arg = sys.argv[1] if len(sys.argv) > 1 else "code"

    if arg == "status":
        print(json.dumps(bridge.get_status(), indent=2))
    else:
        profile = arg if arg in bridge.profiles else "code"
        if not bridge.is_ollama_up():
            print("Ollama is not running. Start the AI stack first.")
            sys.exit(1)
        print(f"Launching OpenClaw (profile: {profile})...")
        bridge.launch(profile=profile)

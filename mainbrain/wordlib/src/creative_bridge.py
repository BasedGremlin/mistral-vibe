"""
WORDLIB Creative Bridge -- Godot launcher.

Optional. The system works fine without Godot installed.
Godot is a foreground app, not a background service, so it is launched
on demand rather than managed by the service loop.

RAG access goes through the ETHER AI hub (HTTP), not direct file access.
Godot's own AI plugins can also hit http://localhost:5757/api/rag/query.
"""

import json
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("creative_bridge")

_SRC_DIR   = Path(__file__).resolve().parent
_USB_ROOT  = _SRC_DIR.parent
_CONFIG    = _USB_ROOT / "config" / "creative.json"
IS_WINDOWS = platform.system() == "Windows"

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


class CreativeBridge:
    """Launches Godot self-contained and bridges it to the RAG hub over HTTP."""

    def __init__(self) -> None:
        self.config    = _load_config()
        self.godot_cfg = self.config.get("godot", {})
        self.hub       = HubClient() if HubClient else None
        self._resolve_paths()

    def _resolve_paths(self) -> None:
        exe_key = "exe_windows" if IS_WINDOWS else "exe_linux"
        exe_rel = self.godot_cfg.get(exe_key, "")
        self.godot_exe = (_USB_ROOT / exe_rel).resolve() if exe_rel else None

        self.sc_marker = (_USB_ROOT / self.godot_cfg.get(
            "self_contained_marker", "Godot/_sc_")).resolve()
        self.template_project = (_USB_ROOT / self.godot_cfg.get(
            "template_project", "GodotProjects/Template")).resolve()
        self.ai_model = self.godot_cfg.get(
            "ai_assist_model", "qwen2.5-coder:7b-instruct-q4_K_M")

    def is_available(self) -> bool:
        if not self.godot_cfg.get("enabled", True):
            return False
        return bool(self.godot_exe and self.godot_exe.exists())

    def ensure_self_contained(self) -> bool:
        """Create the _sc_ marker so Godot keeps settings on the USB."""
        try:
            self.sc_marker.parent.mkdir(parents=True, exist_ok=True)
            if not self.sc_marker.exists():
                self.sc_marker.touch()
                logger.info("Self-contained marker created.")
            return True
        except Exception as e:
            logger.error(f"Could not create _sc_ marker: {e}")
            return False

    def launch_godot(self, project_path: Optional[str] = None,
                     editor: bool = True) -> bool:
        """Launch Godot self-contained. Detached so it survives the launcher."""
        if not self.is_available():
            logger.error("Godot not installed. Run the Godot setup step first.")
            return False

        self.ensure_self_contained()

        target = None
        if project_path:
            p = Path(project_path)
            target = p if p.is_absolute() else (_USB_ROOT / p)
        elif self.template_project.exists():
            target = self.template_project

        cmd = [str(self.godot_exe)]
        if target and (target / "project.godot").exists():
            cmd += (["--editor"] if editor else []) + ["--path", str(target)]
            logger.info(f"Launching Godot: {target}")
        else:
            logger.info("Opening Godot project manager.")

        try:
            if IS_WINDOWS:
                subprocess.Popen(cmd, creationflags=0x00000008)  # DETACHED
            else:
                subprocess.Popen(cmd, start_new_session=True,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            logger.error(f"Failed to launch Godot: {e}")
            return False

    def rag_query(self, query: str, top_k: int = 4) -> list:
        """Query the RAG hub. Returns [] if the hub is down."""
        if not self.hub:
            return []
        return self.hub.rag_query(query, top_k=top_k)

    def get_status(self) -> Dict[str, Any]:
        addons_status = {}
        if self.template_project.exists():
            addons_dir = self.template_project / "addons"
            for addon in self.godot_cfg.get("addons_expected", []):
                addons_status[addon] = (addons_dir / addon / "plugin.cfg").exists()

        return {
            "godot_available":  self.is_available(),
            "godot_exe":        str(self.godot_exe) if self.godot_exe else None,
            "self_contained":   self.sc_marker.exists(),
            "template_exists":  (self.template_project / "project.godot").exists(),
            "addons":           addons_status,
            "ai_assist_model":  self.ai_model,
            "hub_up":           self.hub.is_up() if self.hub else False,
            "platform":         platform.system(),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    bridge = CreativeBridge()
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(bridge.get_status(), indent=2))
    elif bridge.is_available():
        print("Godot found. Launching...")
        bridge.launch_godot()
    else:
        print("Godot not installed. Run the Godot setup step first.")
        print(json.dumps(bridge.get_status(), indent=2))

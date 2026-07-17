"""
gremlin_coordinator.py -- Gremlin Coordinator.
=============================================
Reads gremlin_premium_features.xml and exposes the features that map to REAL,
implementable behaviors. Honest by construction:

  - It parses the XML for feature definitions (real XML, real parsing).
  - It ONLY exposes features that have a real handler behind them. Features that
    are pure vocabulary (e.g. "comet_killer_ui_surface" as a vibe) are listed as
    "descriptive_only" -- never presented as an executable capability.
  - Every activation is consent-gated (disabled by default) and logged with the
    reason + any risk.
  - It does NOT modify production files or state. It SUGGESTS; humans decide.

The "premium/hidden/supergrok" labels in the XML are treated as flavor, not as a
capability tier. A feature is real here only if code does something observable.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional


@dataclass
class GremlinFeature:
    fid: str
    name: str
    description: str
    has_handler: bool            # True only if a real behavior backs it
    kind: str                    # "executable" | "descriptive_only"


class GremlinCoordinator:
    def __init__(self, root: Path, xml_path: Optional[Path] = None) -> None:
        self.root = Path(root)
        self.xml_path = xml_path or (self.root / "config" / "gremlin_premium_features.xml")
        self.enabled = False     # consent-gated: OFF by default
        self.log_path = self.root / "data" / "gremlin_coordinator.jsonl"
        self._handlers: Dict[str, Callable] = self._build_handlers()
        self.features: List[GremlinFeature] = self._load_features()

    # ── Real behaviors. A feature is "executable" only if it appears here. ──
    def _build_handlers(self) -> Dict[str, Callable]:
        return {
            "phantom_file_detector":  self._phantom_file_detector,
            "test_gap_finder":        self._test_gap_finder,
            "rollback_guardian":      self._rollback_guardian,
            "assumption_challenger":  self._assumption_challenger,
            "reflection_amplifier":   self._reflection_amplifier,
            "contrast_and_focus_whisperer": self._contrast_whisperer,
            # NOTE: elegant_hack_finder, delight_injector, comet_killer_ui_surface
            # are NOT here -- they're model/judgment behaviors or pure vibe, so
            # they're surfaced as descriptive_only, never as fake executables.
        }

    def _load_features(self) -> List[GremlinFeature]:
        feats: List[GremlinFeature] = []
        if not self.xml_path.exists():
            return feats
        try:
            tree = ET.parse(self.xml_path)
        except Exception:
            return feats
        for fel in tree.getroot().iter("feature"):
            fid = fel.get("id", "")
            name_el = fel.find("name")
            desc_el = fel.find("description")
            has = fid in self._handlers
            feats.append(GremlinFeature(
                fid=fid,
                name=(name_el.text if name_el is not None else fid),
                description=(desc_el.text.strip() if desc_el is not None and desc_el.text else ""),
                has_handler=has,
                kind="executable" if has else "descriptive_only"))
        return feats

    # ── Consent + logging ───────────────────────────────────────────────────
    def enable(self, consent: bool = True) -> Dict:
        self.enabled = bool(consent)
        self._log("coordinator_enabled" if consent else "coordinator_disabled", {})
        return {"enabled": self.enabled}

    def _log(self, event: str, detail: Dict) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                                    "event": event, "detail": detail}) + "\n")
        except Exception:
            pass

    def list_features(self) -> List[Dict]:
        return [{"id": f.fid, "name": f.name, "kind": f.kind,
                 "executable": f.has_handler} for f in self.features]

    def activate(self, feature_id: str, context: Optional[Dict] = None) -> Dict:
        """Run a feature -- only if enabled (consent) AND it has a real handler."""
        if not self.enabled:
            return {"ok": False, "reason": "coordinator disabled -- enable with consent first"}
        handler = self._handlers.get(feature_id)
        if not handler:
            # Honest: this feature is descriptive only, not executable
            return {"ok": False, "reason": f"'{feature_id}' is descriptive-only "
                    "(no real handler) -- not presented as an executable capability"}
        self._log("feature_activated", {"feature": feature_id})
        result = handler(context or {})
        result["feature"] = feature_id
        result["logged"] = True
        return result

    # ── The real handlers (each does something observable, no state changes) ─
    def _phantom_file_detector(self, ctx: Dict) -> Dict:
        """Scan a list of referenced paths; report which don't exist."""
        refs = ctx.get("paths", [])
        missing = [p for p in refs if not (self.root / p).exists()]
        return {"ok": True, "checked": len(refs), "missing": missing,
                "note": "References to files that do not exist -- do not build on these."}

    def _test_gap_finder(self, ctx: Dict) -> Dict:
        """Find src modules that have no matching test_*.py mentioning them."""
        src = self.root / "src"
        tests_dir = self.root / "tests"
        tested_text = ""
        if tests_dir.exists():
            for t in tests_dir.glob("test_*.py"):
                tested_text += t.read_text(encoding="utf-8", errors="ignore")
        gaps = []
        if src.exists():
            for mod in src.rglob("*.py"):
                stem = mod.stem
                if stem in ("__init__",):
                    continue
                if stem not in tested_text:
                    gaps.append(str(mod.relative_to(self.root)))
        return {"ok": True, "untested_modules": gaps[:20], "count": len(gaps),
                "note": "Highest-value next tests target these modules."}

    def _rollback_guardian(self, ctx: Dict) -> Dict:
        """
        Verify the rollback safety rail is REAL for a given file: the most recent
        backup must exist AND differ from current content (else rollback is a
        silent no-op -- the exact bug that bit this project before). Read-only.
        """
        rel = ctx.get("path", "")
        if not rel:
            return {"ok": False, "reason": "provide 'path' to check"}
        target = self.root / rel
        backups_dir = self.root / "backups" / "self_editor"
        if not backups_dir.exists():
            return {"ok": True, "verdict": "no backups yet",
                    "note": "No edits made through self_editor for this file."}
        safe = rel.replace("/", "__").replace("\\", "__")
        candidates = sorted(backups_dir.glob(f"{safe}.*.bak"), reverse=True)
        if not candidates:
            return {"ok": True, "verdict": "no backup for this file",
                    "note": "Nothing to roll back to."}
        latest = candidates[0]
        try:
            backup_content = latest.read_bytes()
            current = target.read_bytes() if target.exists() else b""
        except Exception as e:
            return {"ok": False, "reason": f"could not read: {e}"}
        differs = backup_content != current
        return {"ok": True,
                "verdict": "rollback is REAL" if differs else "WARNING: rollback would be a no-op",
                "backup": latest.name,
                "differs_from_current": differs,
                "note": ("Restoring this backup would change the file (good)."
                         if differs else
                         "Backup matches current content -- rollback would do nothing. "
                         "Check the backup ordering (the bug that bit us before).")}

    def _assumption_challenger(self, ctx: Dict) -> Dict:
        """Surface unstated assumptions in a supplied plan (heuristic prompts)."""
        plan = ctx.get("plan", "")
        prompts = []
        low = plan.lower()
        if "deploy" in low and "rollback" not in low:
            prompts.append("Plan mentions deploy but not rollback -- what's the recovery path?")
        if "all" in low or "every" in low:
            prompts.append("Plan uses 'all/every' -- is the edge-case set really exhaustive?")
        if "fast" in low or "quick" in low:
            prompts.append("'Fast/quick' -- measured against what baseline?")
        if not prompts:
            prompts.append("State the top 3 things that must be true for this plan to work.")
        return {"ok": True, "challenges": prompts}

    def _reflection_amplifier(self, ctx: Dict) -> Dict:
        """Turn raw session facts into concrete, honest improvement suggestions."""
        facts = ctx.get("facts", {})
        suggestions = []
        if facts.get("untested_modules"):
            suggestions.append("Close the largest test gap next (modules with no tests).")
        if not facts.get("ci"):
            suggestions.append("Add CI so the test suite runs automatically on change.")
        if facts.get("ui_unverified_by_screenreader"):
            suggestions.append("Get a real screen-reader pass on the accessible pages.")
        if not suggestions:
            suggestions.append("System is in good shape -- pick the highest-user-value feature next.")
        return {"ok": True, "suggestions": suggestions}

    def _contrast_whisperer(self, ctx: Dict) -> Dict:
        """Compute WCAG contrast for supplied fg/bg pairs -- real math."""
        def lum(hexc):
            h = hexc.lstrip("#")
            r, g, b = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
            f = lambda c: c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
            return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b)
        pairs = ctx.get("pairs", [])
        out = []
        for fg, bg in pairs:
            l1, l2 = lum(fg), lum(bg)
            ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
            out.append({"fg": fg, "bg": bg, "ratio": round(ratio, 2),
                        "passes_AA": ratio >= 4.5, "passes_AAA": ratio >= 7.0})
        return {"ok": True, "results": out}

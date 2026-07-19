"""
WORDLIB Content Manager
=======================
Three jobs:
  1. Sync: export ETHER AI's notes/KB/strategy/recovery from SQLite into
     storage/ as Markdown, so the RAG index automatically reflects the library
  2. Expand: ask the local Ollama model to generate new knowledge files on
     any topic and write them directly into storage/
  3. Index: trigger a RAG rebuild after any content change

This is the system teaching itself. It runs from the launcher menu
or can be called directly: python src/content_manager.py sync|expand|status
"""

import json
import logging
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("content_manager")

_SRC_DIR  = Path(__file__).resolve().parent
_USB_ROOT = _SRC_DIR.parent
_STORAGE  = _USB_ROOT / "storage"
_DB_PATH  = _USB_ROOT / "data" / "ether.db"
_OLLAMA   = "http://127.0.0.1:11434"
_HUB      = "http://127.0.0.1:5757"

# Where each DB table exports to
_EXPORT_MAP = {
    "notes":     _STORAGE / "kb",
    "kb_entries": _STORAGE / "kb",
    "strategy":  _STORAGE / "strategy",   # SpecialNote slug=strategy
    "recovery":  _STORAGE / "recovery",   # SpecialNote slug=recovery
}


class ContentManager:

    def __init__(self) -> None:
        for folder in _STORAGE.iterdir() if _STORAGE.exists() else []:
            pass  # folders guaranteed by self_heal

    # ── 1. Sync from ETHER AI database → storage/ Markdown ─────────────────

    def sync_from_db(self) -> Dict[str, int]:
        """
        Export ETHER AI's SQLite content into storage/ as Markdown files.
        Returns {"exported": N, "skipped": N, "errors": N}
        """
        if not _DB_PATH.exists():
            logger.warning("ether.db not found -- nothing to sync")
            return {"exported": 0, "skipped": 0, "errors": 0}

        stats = {"exported": 0, "skipped": 0, "errors": 0}
        con = sqlite3.connect(str(_DB_PATH))
        con.row_factory = sqlite3.Row

        # Export Notes
        try:
            rows = con.execute(
                "SELECT title, content, category, tags, updated_at FROM notes"
            ).fetchall()
            dest = _STORAGE / "kb"
            dest.mkdir(parents=True, exist_ok=True)
            for row in rows:
                if not row["content"] or len(row["content"].strip()) < 20:
                    stats["skipped"] += 1
                    continue
                fname = self._safe_filename(row["title"]) + ".md"
                md = self._note_to_markdown(row["title"], row["content"],
                                            row["category"], row["tags"])
                (dest / fname).write_text(md, encoding="utf-8")
                stats["exported"] += 1
        except Exception as e:
            logger.error(f"Note sync error: {e}")
            stats["errors"] += 1

        # Export KB Entries
        try:
            rows = con.execute(
                "SELECT title, content, category, tags FROM kb_entries"
            ).fetchall()
            dest = _STORAGE / "kb"
            for row in rows:
                if not row["content"] or len(row["content"].strip()) < 20:
                    stats["skipped"] += 1
                    continue
                fname = "kb_" + self._safe_filename(row["title"]) + ".md"
                md = self._note_to_markdown(row["title"], row["content"],
                                            row["category"], row["tags"])
                (dest / fname).write_text(md, encoding="utf-8")
                stats["exported"] += 1
        except Exception as e:
            logger.error(f"KB sync error: {e}")
            stats["errors"] += 1

        # Export SpecialNotes (strategy + recovery)
        try:
            rows = con.execute(
                "SELECT slug, content FROM special_notes"
            ).fetchall()
            for row in rows:
                slug = row["slug"]
                content = row["content"]
                if not content or len(content.strip()) < 20:
                    continue
                if slug == "strategy":
                    dest = _STORAGE / "strategy" / "strategy_notes.md"
                elif slug == "recovery":
                    dest = _STORAGE / "recovery" / "recovery_notes.md"
                else:
                    dest = _STORAGE / "kb" / f"{slug}.md"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(f"# {slug.title()} Notes\n\n{content}", encoding="utf-8")
                stats["exported"] += 1
        except Exception as e:
            logger.warning(f"SpecialNote sync skipped: {e}")

        con.close()
        logger.info(f"Sync complete: {stats}")
        return stats

    def _safe_filename(self, title: str) -> str:
        """Convert a title to a safe filename."""
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
        return safe.strip().replace(" ", "_")[:60]

    def _note_to_markdown(self, title: str, content: str,
                           category: str = "", tags: str = "") -> str:
        """Format a note as Markdown with frontmatter."""
        lines = [f"# {title}", ""]
        if category:
            lines.append(f"**Category**: {category}")
        if tags:
            lines.append(f"**Tags**: {tags}")
        if category or tags:
            lines.append("")
        lines.append(content)
        return "\n".join(lines)

    # ── 2. AI Content Expansion ──────────────────────────────────────────────

    def _ollama_up(self) -> bool:
        try:
            req = urllib.request.Request(f"{_OLLAMA}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    def _ollama_generate(self, prompt: str, model: str = "dolphin3",
                          temperature: float = 0.4) -> Optional[str]:
        """Call Ollama and return the response text."""
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 4096},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{_OLLAMA}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"Ollama generate error: {e}")
            return None

    def expand_topic(self, topic: str, folder: str = "research",
                     model: str = "dolphin3") -> Dict[str, Any]:
        """
        Use the local Ollama model to generate a comprehensive knowledge file
        on any topic, and write it to storage/<folder>/.

        folder: "research" | "kb" | "strategy" | "recovery"
        """
        if not self._ollama_up():
            return {"ok": False, "error": "Ollama not running. Start the AI stack first."}

        valid_folders = ("research", "kb", "strategy", "recovery")
        if folder not in valid_folders:
            return {"ok": False, "error": f"Invalid folder. Choose from: {valid_folders}"}

        logger.info(f"Expanding topic: '{topic}' -> storage/{folder}/")

        prompt = f"""Write a comprehensive, dense reference document on the topic: "{topic}"

Requirements:
- Markdown format with clear headers (## and ###)
- Include practical examples, patterns, or code where relevant
- Be specific and factual; no filler content
- Aim for 400-600 words of high-signal content
- Structure: Overview → Key Concepts → Practical Patterns → Common Pitfalls
- Do not include meta-commentary about the document itself

Start directly with the content:"""

        content = self._ollama_generate(prompt, model=model, temperature=0.4)
        if not content:
            return {"ok": False, "error": "No response from Ollama."}

        # Write to storage
        dest_dir = _STORAGE / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        fname = self._safe_filename(topic) + ".md"
        dest = dest_dir / fname
        dest.write_text(f"# {topic}\n\n{content}", encoding="utf-8")

        logger.info(f"Wrote {len(content)} chars to storage/{folder}/{fname}")
        return {
            "ok": True,
            "path": f"storage/{folder}/{fname}",
            "chars": len(content),
            "topic": topic,
        }

    def expand_batch(self, topics: List[Dict[str, str]],
                     model: str = "dolphin3") -> List[Dict[str, Any]]:
        """
        Generate multiple knowledge files.
        topics: [{"topic": "X", "folder": "research"}, ...]
        """
        results = []
        for item in topics:
            result = self.expand_topic(
                topic=item.get("topic", ""),
                folder=item.get("folder", "research"),
                model=model,
            )
            results.append(result)
            if result["ok"]:
                time.sleep(1)  # Brief pause between generations
        return results

    # ── 3. Trigger RAG rebuild ───────────────────────────────────────────────

    def trigger_rag_rebuild(self) -> Dict[str, Any]:
        """Ask the ETHER AI hub to rebuild the RAG index."""
        try:
            req = urllib.request.Request(
                f"{_HUB}/api/rag/rebuild",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"RAG rebuild trigger failed (hub may not be running): {e}")
            return {"ok": False, "error": str(e)}

    # ── 4. Status ────────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return content statistics across all storage folders."""
        result: Dict[str, Any] = {
            "storage_root": str(_STORAGE),
            "db_exists": _DB_PATH.exists(),
            "ollama_up": self._ollama_up(),
            "folders": {},
            "total_files": 0,
            "total_size_kb": 0,
        }
        for folder in ("strategy", "recovery", "research", "kb"):
            p = _STORAGE / folder
            if p.exists():
                files = list(p.glob("**/*.md")) + list(p.glob("**/*.txt"))
                size_kb = sum(f.stat().st_size for f in files) // 1024
                result["folders"][folder] = {
                    "files": len(files),
                    "size_kb": size_kb,
                    "names": [f.name for f in files[:10]],
                }
                result["total_files"] += len(files)
                result["total_size_kb"] += size_kb
            else:
                result["folders"][folder] = {"files": 0, "size_kb": 0, "names": []}
        return result

    def sync_and_rebuild(self) -> Dict[str, Any]:
        """Full pipeline: sync DB → expand (optional) → rebuild RAG."""
        sync_stats = self.sync_from_db()
        rag = self.trigger_rag_rebuild()
        return {"sync": sync_stats, "rag_rebuild": rag}


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    mgr = ContentManager()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        print(json.dumps(mgr.status(), indent=2))
    elif cmd == "sync":
        stats = mgr.sync_from_db()
        print(f"Synced: {stats}")
        mgr.trigger_rag_rebuild()
        print("RAG rebuild triggered.")
    elif cmd == "expand" and len(sys.argv) >= 3:
        topic  = sys.argv[2]
        folder = sys.argv[3] if len(sys.argv) > 3 else "research"
        result = mgr.expand_topic(topic, folder)
        print(json.dumps(result, indent=2))
    elif cmd == "rebuild":
        result = mgr.trigger_rag_rebuild()
        print(json.dumps(result, indent=2))
    else:
        print("Usage: content_manager.py [status|sync|expand <topic> [folder]|rebuild]")

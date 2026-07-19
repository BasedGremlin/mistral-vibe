"""
WORDLIB Memory Semantic Hook v1
===============================
Tiny optional read-only bridge from existing memory surfaces to SemanticAdapter.

This module deliberately does not write memory, ingest graph facts, start agents,
start RAG, or import SemanticKnowledgeGraph internals. It reads local memory files
and asks SemanticAdapter for ontology/semantic context.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_SRC_DIR = Path(__file__).resolve().parent
_ROOT = _SRC_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def semantic_context_for_memory_query(query_text: str, as_prompt: bool = True,
                                      storage_path: Optional[str] = None,
                                      memory_root: Optional[str] = None,
                                      max_items: int = 8) -> Dict[str, Any]:
    """
    Optional read-only memory hook for prompt building and diagnostics.

    Returns a stable dict and never raises for normal caller errors. Callers can
    use this from RAG, agents, or main boot checks without depending on graph
    internals or optional vector/database services.
    """
    try:
        from semantic_adapter import create_default_adapter
        adapter = create_default_adapter(auto_load=True, auto_save=False, storage_path=storage_path)
        result = adapter.memory_context_for_query(
            query=query_text,
            as_prompt=as_prompt,
            memory_root=memory_root,
            max_items=max_items,
        )
        data = result.to_dict()
        data["hook"] = "memory_semantic_hook.semantic_context_for_memory_query"
        data["read_only"] = True
        return data
    except Exception as exc:
        return {
            "ok": False,
            "operation": "semantic_context_for_memory_query",
            "data": {},
            "warnings": [],
            "error": f"{type(exc).__name__}: {exc}",
            "hook": "memory_semantic_hook.semantic_context_for_memory_query",
            "read_only": True,
        }


def semantic_memory_status(memory_root: Optional[str] = None) -> Dict[str, Any]:
    """Boot/deploy-safe status helper for the memory semantic hook."""
    root = Path(memory_root) if memory_root else (_ROOT / "data")
    if not root.is_absolute():
        root = (_ROOT / root).resolve()
    gremlin = root / "gremlin_memory.json"
    events = root / "ether_events.jsonl"
    result = semantic_context_for_memory_query("WORDLIB memory semantic hook", as_prompt=False, memory_root=str(root), max_items=3)
    return {
        "ok": bool(result.get("ok")),
        "hook": "memory_semantic_hook.semantic_memory_status",
        "read_only": True,
        "memory_root": str(root.resolve()),
        "sources": {
            "gremlin_memory_exists": gremlin.exists(),
            "ether_events_exists": events.exists(),
        },
        "summary": result.get("data", {}).get("summary", {}),
        "error": result.get("error"),
        "warnings": result.get("warnings", []),
    }


def self_check() -> bool:
    result = semantic_context_for_memory_query("WORDLIB memory SemanticAdapter", as_prompt=True, max_items=3)
    assert result.get("read_only") is True, result
    assert result.get("ok") is True, result
    prompt = result.get("data", {}).get("prompt_context", "")
    assert "WORDLIB memory context" in prompt, prompt
    assert "semantic graph context" in prompt or "Local ontology context" in prompt, prompt
    status = semantic_memory_status()
    assert status.get("ok") is True, status
    return True


if __name__ == "__main__":
    ok = self_check()
    print(json.dumps({"memory_semantic_hook_self_check": ok, "status": semantic_memory_status()}, indent=2, sort_keys=True))

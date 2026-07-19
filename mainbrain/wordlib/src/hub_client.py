"""
WORDLIB Hub Client
==================
Tiny shared client for talking to the ETHER AI hub (the Flask server).
Both creative_bridge and openclaw_bridge use this so RAG access goes
through ONE place: ETHER AI's /api/rag endpoints.

ETHER AI is the hub. RAG lives there. Everything else is a client.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hub_client")

DEFAULT_HUB_URL = "http://localhost:5757"


class HubClient:
    """Minimal HTTP client for the ETHER AI hub. No external dependencies."""

    def __init__(self, base_url: str = DEFAULT_HUB_URL, timeout: int = 8) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

    def is_up(self) -> bool:
        """True if the ETHER AI hub responds."""
        try:
            req = urllib.request.Request(f"{self.base_url}/status")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def rag_query(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Query the shared RAG index via the hub.
        Returns a list of {text, score, source, folder} dicts, or [] on failure.
        """
        payload = json.dumps({"query": query, "top_k": top_k}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/rag/query",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("results", []) if data.get("ok") else []
        except urllib.error.HTTPError as e:
            logger.warning(f"RAG query HTTP {e.code} -- hub may lack RAG.")
            return []
        except Exception as e:
            logger.warning(f"RAG query failed: {e}")
            return []

    def rag_stats(self) -> Dict[str, Any]:
        """Return RAG stats from the hub, or a not-available marker."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/rag/stats")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return {"status": "hub_unreachable"}

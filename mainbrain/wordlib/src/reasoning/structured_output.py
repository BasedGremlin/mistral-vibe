"""
Structured Output Engine.
=========================
Honest version of the "supercharged JSON engine".

What it really does:
  - defines schemas (Pydantic v2 if available, dataclass+manual validation if not)
  - parses LLM text into a schema, tolerating common LLM mistakes
    (markdown fences, leading prose, trailing commas, single quotes)
  - validates against the schema and returns typed objects or clear errors
  - caches parsed results by content hash to avoid re-parsing identical text

What it does NOT do:
  - it does not make the LLM "faster" -- we don't control model decoding.
    The speed win that's REAL: caching identical parses + cheap repair instead
    of a second model round-trip. We claim only that.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type

try:
    from pydantic import BaseModel, ValidationError
    _HAVE_PYDANTIC = True
except Exception:
    _HAVE_PYDANTIC = False
    BaseModel = object  # type: ignore


@dataclass
class ParseResult:
    ok: bool
    data: Optional[Dict] = None
    error: str = ""
    from_cache: bool = False
    repaired: bool = False


class StructuredOutputEngine:
    def __init__(self) -> None:
        self._cache: Dict[str, Dict] = {}
        self.have_pydantic = _HAVE_PYDANTIC

    # ── Repair common LLM JSON mistakes ──────────────────────────────────────
    def _extract_json(self, text: str) -> str:
        t = text.strip()
        # strip markdown fences
        fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
        if fence:
            t = fence.group(1).strip()
        # grab the outermost {...} or [...]
        first = min((t.find("{"), t.find("[")), key=lambda x: x if x >= 0 else 1e9)
        if first > 0:
            t = t[first:]
        # trim trailing prose after the last closing brace/bracket
        last = max(t.rfind("}"), t.rfind("]"))
        if last >= 0:
            t = t[:last + 1]
        return t

    def _repair(self, text: str) -> str:
        t = text
        t = re.sub(r",\s*([}\]])", r"\1", t)        # trailing commas
        t = re.sub(r"'", '"', t)                      # single -> double quotes
        t = re.sub(r"(\w+)\s*:", r'"\1":', t) if False else t  # (kept conservative)
        return t

    def parse(self, text: str) -> ParseResult:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key in self._cache:
            return ParseResult(True, self._cache[key], from_cache=True)

        extracted = self._extract_json(text)
        # First attempt: straight parse
        try:
            data = json.loads(extracted)
            self._cache[key] = data
            return ParseResult(True, data)
        except json.JSONDecodeError:
            pass
        # Second attempt: repaired
        try:
            data = json.loads(self._repair(extracted))
            self._cache[key] = data
            return ParseResult(True, data, repaired=True)
        except json.JSONDecodeError as e:
            return ParseResult(False, error=f"JSON parse failed: {e}")

    def parse_into(self, text: str, schema: Type) -> ParseResult:
        """Parse + validate against a Pydantic model (or dataclass) schema."""
        base = self.parse(text)
        if not base.ok:
            return base
        if _HAVE_PYDANTIC and isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                obj = schema(**base.data)
                return ParseResult(True, obj.model_dump(), from_cache=base.from_cache,
                                   repaired=base.repaired)
            except ValidationError as e:
                return ParseResult(False, error=f"schema validation failed: {e}")
        # Dataclass fallback: shallow field presence check
        if hasattr(schema, "__dataclass_fields__"):
            required = [f for f, v in schema.__dataclass_fields__.items()]
            missing = [f for f in required if f not in base.data]
            if missing:
                return ParseResult(False, error=f"missing fields: {missing}")
        return base

    def clear_cache(self) -> int:
        n = len(self._cache)
        self._cache.clear()
        return n

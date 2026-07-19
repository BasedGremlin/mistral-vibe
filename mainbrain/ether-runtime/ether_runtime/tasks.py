"""Allowlisted task handlers.

The v11 record removed the proposed /execute_verified arbitrary-shell endpoint
as unsafe; this runtime keeps that boundary. Exactly two validated task types
exist, and unknown kinds are rejected at submit time -- there is no generic
execution path to smuggle work through.

- absorb_text:     store sourced text into the content-hashed absorption
                   store. A source is REQUIRED (anonymous evidence is
                   rejected, same rule as wordlib's MarketIntelAnalyst).
- verify_artifact: compute SHA-256 of files under a configured root and
                   compare against an expected manifest. Paths outside the
                   root are rejected (no traversal).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .store import TaskStore


class PayloadError(ValueError):
    """Invalid payload for an allowlisted task type."""


def _require_str(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PayloadError(f"payload field {key!r} must be a non-empty string")
    return value


def validate_payload(kind: str, payload: dict) -> None:
    """Validate at submit time so malformed work never enters the journal."""
    if kind == "absorb_text":
        _require_str(payload, "source")
        _require_str(payload, "text")
    elif kind == "verify_artifact":
        files = payload.get("files")
        if not isinstance(files, dict) or not files:
            raise PayloadError(
                "payload field 'files' must be a non-empty mapping of"
                " relative path -> expected sha256 hex"
            )
        for rel, digest in files.items():
            if not isinstance(rel, str) or not rel.strip():
                raise PayloadError("manifest keys must be relative path strings")
            if Path(rel).is_absolute() or ".." in Path(rel).parts:
                raise PayloadError(f"manifest path {rel!r} escapes the artifact root")
            if not isinstance(digest, str) or len(digest) != 64:
                raise PayloadError(f"expected sha256 hex for {rel!r}")
    else:
        raise PayloadError(f"unknown task kind {kind!r}; allowlist: {sorted(ALLOWED_KINDS)}")


def run_absorb_text(store: TaskStore, payload: dict, artifact_root: Path) -> dict:
    source = _require_str(payload, "source")
    text = _require_str(payload, "text")
    content_hash, created = store.absorb(source, text)
    return {"content_hash": content_hash, "created": created, "source": source}


def run_verify_artifact(store: TaskStore, payload: dict, artifact_root: Path) -> dict:
    root = artifact_root.resolve()
    results: dict[str, dict] = {}
    all_ok = True
    for rel, expected in payload["files"].items():
        target = (root / rel).resolve()
        if root not in target.parents and target != root:
            raise PayloadError(f"path {rel!r} resolves outside the artifact root")
        entry: dict = {"expected": expected.lower()}
        if not target.is_file():
            entry.update(status="missing", actual=None)
            all_ok = False
        else:
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            entry["actual"] = actual
            if actual == expected.lower():
                entry["status"] = "verified"
            else:
                entry["status"] = "mismatch"
                all_ok = False
        results[rel] = entry
    return {"ok": all_ok, "files": results}


HANDLERS = {
    "absorb_text": run_absorb_text,
    "verify_artifact": run_verify_artifact,
}
ALLOWED_KINDS = frozenset(HANDLERS)

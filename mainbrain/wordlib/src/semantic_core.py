"""
WORDLIB Semantic Core v2
========================
Compact, dependency-light semantic knowledge graph for WORDLIB foundation use.

Design rules:
- no heavy dependencies
- deterministic IDs
- JSON persistence with schema versioning
- every graph fact must be backed by evidence
- path-safe storage through core.paths when available
- safe to import from other WORDLIB modules
"""
from __future__ import annotations

import json
import re
import sys
import hashlib
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

SCHEMA_VERSION = "wordlib.semantic_core.v2"
SUPPORTED_SCHEMAS = {"wordlib.semantic_core.v1", SCHEMA_VERSION}

# Guarded bootstrap only so src/semantic_core.py can be executed directly.
_SRC_DIR = Path(__file__).resolve().parent
_ROOT = _SRC_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _project_root() -> Path:
    try:
        from core.paths import get_project_root
        return get_project_root()
    except Exception:
        return _ROOT


def resolve_semantic_storage_path(path: Optional[Path | str] = None) -> Path:
    """Resolve semantic storage safely and project-locally by default."""
    if path:
        return Path(path)
    try:
        from core.paths import get_data_dir
        base = get_data_dir() / "semantic_core"
    except Exception:
        base = _project_root() / "data" / "semantic_core"
    return base / "semantic_graph.json"


def _default_storage_path() -> Path:
    return resolve_semantic_storage_path()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean_text(value)).casefold()


def _canonical_key(name: Any, entity_type: str = "concept", metadata: Optional[Dict[str, Any]] = None) -> str:
    text = _clean_text(name).replace("\\", "/")
    text = re.sub(r"^\./", "", text)
    text = re.sub(r"\s+", " ", text).strip().casefold()
    text = text.replace("motherether/wordlib", "wordlib")
    text = text.replace("motherether", "motherether")
    if text.endswith("/semantic_core.py") or text == "semantic_core.py":
        text = "src/semantic_core.py"
    if text.endswith("/deploy_check.py") or text == "deploy_check.py":
        text = "deploy_check.py"
    if metadata:
        explicit = metadata.get("canonical_key") or metadata.get("normalized_key")
        if explicit:
            text = _clean_text(explicit).replace("\\", "/").casefold()
    return f"{_clean_text(entity_type) or 'concept'}:{text}"


def _slug(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", _clean_text(value)).strip("_").upper()
    return text or "ITEM"


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_normalize(p) for p in parts if p is not None)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    hint = _slug(parts[0] if parts else prefix)[:28]
    return f"{prefix}_{hint}_{digest}"


def _dedupe(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for value in values:
        text = _clean_text(value)
        key = _normalize(text)
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _clamped_confidence(value: Any) -> float:
    number = float(value)
    return max(0.0, min(1.0, number))


def _require_confidence(value: Any) -> float:
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")
    return number


def _json_safe(value: Any) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except TypeError as exc:
        raise ValueError(f"metadata must be JSON-serializable: {exc}") from exc


@dataclass
class Evidence:
    id: str
    source_type: str
    source_path: Optional[str] = None
    source_id: Optional[str] = None
    text_excerpt: str = ""
    created_at: str = field(default_factory=_utc_now)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Entity:
    id: str
    name: str
    type: str = "concept"
    aliases: List[str] = field(default_factory=list)
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
    evidence_ids: List[str] = field(default_factory=list)


@dataclass
class Relationship:
    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    confidence: float = 0.5
    evidence_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    id: str
    title: str
    timestamp: Optional[str] = None
    event_type: str = "event"
    involved_entity_ids: List[str] = field(default_factory=list)
    confidence: float = 0.5
    evidence_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SemanticKnowledgeGraph:
    """Small provenance-aware graph with JSON persistence, audit, compaction and pathfinding."""

    EDGE_WEIGHTS = {
        "relationship": 1.00,
        "event": 0.82,
        "metadata": 0.72,
        "shared_evidence": 0.46,
        "alias": 0.25,
    }

    def __init__(self, storage_path: Optional[Path | str] = None) -> None:
        self.storage_path = resolve_semantic_storage_path(storage_path)
        self.entities: Dict[str, Entity] = {}
        self.relationships: Dict[str, Relationship] = {}
        self.events: Dict[str, Event] = {}
        self.evidence: Dict[str, Evidence] = {}

    # ── validation ──────────────────────────────────────────────────────
    def _require_evidence(self, evidence_ids: Iterable[str]) -> List[str]:
        ids = _dedupe(evidence_ids)
        if not ids:
            raise ValueError("Semantic graph facts require at least one evidence_id.")
        missing = [eid for eid in ids if eid not in self.evidence]
        if missing:
            raise ValueError(f"Unknown evidence_id(s): {', '.join(missing)}")
        return ids

    def _require_entity(self, entity_id: str) -> None:
        if entity_id not in self.entities:
            raise ValueError(f"Unknown entity_id: {entity_id}")

    def _entity_canonical_key(self, name: str, entity_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        return _canonical_key(name, entity_type, metadata)

    def _find_entity_by_canonical_key(self, canonical_key: str) -> Optional[Entity]:
        for entity in self.entities.values():
            if entity.metadata.get("canonical_key") == canonical_key:
                return entity
        return None

    def _merge_entity(self, current: Entity, name: str, aliases: Iterable[str], confidence: float,
                      metadata: Optional[Dict[str, Any]], evidence_ids: Iterable[str]) -> Entity:
        old_name = current.name
        current.aliases = _dedupe([*current.aliases, *aliases, name, old_name])
        current.aliases = [alias for alias in current.aliases if _normalize(alias) != _normalize(current.name)]
        current.evidence_ids = _dedupe([*current.evidence_ids, *evidence_ids])
        current.confidence = max(current.confidence, confidence)
        incoming = dict(metadata or {})
        current.metadata.update(incoming)
        current.metadata.setdefault("canonical_key", self._entity_canonical_key(current.name, current.type, current.metadata))
        current.metadata["merged_count"] = int(current.metadata.get("merged_count", 1)) + 1
        return current

    # ── creation ────────────────────────────────────────────────────────
    def add_evidence(
        self,
        source_type: str,
        text_excerpt: str,
        source_path: Optional[str] = None,
        source_id: Optional[str] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        evidence_id: Optional[str] = None,
    ) -> Evidence:
        source_type = _clean_text(source_type) or "unknown"
        allowed = {"file", "inline_text", "test", "self_check", "deploy_check", "document", "manual", "unknown"}
        if source_type not in allowed and not re.match(r"^[a-zA-Z0-9_\-.]+$", source_type):
            raise ValueError("Evidence source_type must be a simple label.")
        text_excerpt = _clean_text(text_excerpt)
        if not text_excerpt:
            raise ValueError("Evidence requires a non-empty text_excerpt.")
        metadata = dict(metadata or {})
        _json_safe(metadata)
        confidence_value = _require_confidence(confidence)
        created_at = metadata.pop("created_at", None) or _utc_now()
        if created_at:
            try:
                datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("created_at must be ISO-8601 when supplied") from exc
        eid = evidence_id or _stable_id("EVID", source_type, source_path or source_id or "inline", text_excerpt[:180])
        evidence = Evidence(
            id=eid,
            source_type=source_type,
            source_path=_clean_text(source_path) or None,
            source_id=_clean_text(source_id) or None,
            text_excerpt=text_excerpt[:1000],
            created_at=str(created_at),
            confidence=confidence_value,
            metadata=metadata,
        )
        self.evidence[eid] = evidence
        return evidence

    def add_entity(
        self,
        name: str,
        entity_type: str = "concept",
        aliases: Optional[Iterable[str]] = None,
        confidence: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        evidence_ids: Optional[Iterable[str]] = None,
        entity_id: Optional[str] = None,
    ) -> Entity:
        evidence = self._require_evidence(evidence_ids or [])
        name = _clean_text(name)
        if not name:
            raise ValueError("Entity requires a name.")
        metadata = dict(metadata or {})
        _json_safe(metadata)
        confidence_value = _require_confidence(confidence)
        entity_type = _clean_text(entity_type) or "concept"
        canonical_key = self._entity_canonical_key(name, entity_type, metadata)
        metadata.setdefault("canonical_key", canonical_key)
        metadata.setdefault("normalized_key", canonical_key.split(":", 1)[-1])
        incoming_aliases = _dedupe(aliases or [])
        existing = self._find_entity_by_canonical_key(canonical_key)
        if existing:
            return self._merge_entity(existing, name, incoming_aliases, confidence_value, metadata, evidence)
        eid = entity_id or _stable_id("ENT", canonical_key)
        if eid in self.entities:
            return self._merge_entity(self.entities[eid], name, incoming_aliases, confidence_value, metadata, evidence)
        entity = Entity(
            id=eid,
            name=name,
            type=entity_type,
            aliases=incoming_aliases,
            confidence=confidence_value,
            metadata=metadata,
            evidence_ids=evidence,
        )
        self.entities[eid] = entity
        return entity

    def add_relationship(
        self,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: str,
        confidence: float = 0.5,
        evidence_ids: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        relationship_id: Optional[str] = None,
    ) -> Relationship:
        self._require_entity(source_entity_id)
        self._require_entity(target_entity_id)
        metadata = dict(metadata or {})
        if source_entity_id == target_entity_id and not metadata.get("allow_self_relation"):
            raise ValueError("Self-relationships are blocked unless metadata.allow_self_relation=true.")
        _json_safe(metadata)
        evidence = self._require_evidence(evidence_ids or [])
        relation_type = _clean_text(relation_type) or "related_to"
        confidence_value = _require_confidence(confidence)
        rid = relationship_id or _stable_id("REL", source_entity_id, relation_type, target_entity_id, ",".join(sorted(evidence)))
        if rid in self.relationships:
            rel = self.relationships[rid]
            rel.evidence_ids = _dedupe([*rel.evidence_ids, *evidence])
            rel.confidence = max(rel.confidence, confidence_value)
            rel.metadata.update(metadata)
            return rel
        rel = Relationship(rid, source_entity_id, target_entity_id, relation_type, confidence_value, evidence, metadata)
        self.relationships[rid] = rel
        return rel

    def add_event(
        self,
        title: str,
        event_type: str = "event",
        involved_entity_ids: Optional[Iterable[str]] = None,
        timestamp: Optional[str] = None,
        confidence: float = 0.5,
        evidence_ids: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
    ) -> Event:
        involved = _dedupe(involved_entity_ids or [])
        for entity_id in involved:
            self._require_entity(entity_id)
        evidence = self._require_evidence(evidence_ids or [])
        title = _clean_text(title)
        if not title:
            raise ValueError("Event requires a title.")
        metadata = dict(metadata or {})
        _json_safe(metadata)
        confidence_value = _require_confidence(confidence)
        eid = event_id or _stable_id("EVT", title, timestamp or "", event_type, ",".join(sorted(evidence)))
        if eid in self.events:
            event = self.events[eid]
            event.involved_entity_ids = _dedupe([*event.involved_entity_ids, *involved])
            event.evidence_ids = _dedupe([*event.evidence_ids, *evidence])
            event.confidence = max(event.confidence, confidence_value)
            event.metadata.update(metadata)
            return event
        event = Event(eid, title, _clean_text(timestamp) or None, _clean_text(event_type) or "event", involved, confidence_value, evidence, metadata)
        self.events[eid] = event
        return event

    # ── retrieval ───────────────────────────────────────────────────────
    def find_entity(self, name_or_id: str) -> Optional[Entity]:
        if name_or_id in self.entities:
            return self.entities[name_or_id]
        needle = _normalize(name_or_id)
        for entity in self.entities.values():
            keys = {_normalize(entity.name), _normalize(entity.metadata.get("canonical_key", "")), _normalize(entity.metadata.get("normalized_key", ""))}
            keys.update(_normalize(alias) for alias in entity.aliases)
            if needle in keys:
                return entity
        for entity in self.entities.values():
            if needle and (needle in _normalize(entity.name) or any(needle in _normalize(a) for a in entity.aliases)):
                return entity
        return None

    def search_entities(self, query: str, limit: int = 10) -> List[Entity]:
        terms = [_normalize(t) for t in re.findall(r"[\w.\-/]+", query) if len(t) > 1]
        if not terms:
            return []
        scored: List[Tuple[float, Entity]] = []
        for entity in self.entities.values():
            haystack = " ".join([entity.name, entity.type, *entity.aliases, json.dumps(entity.metadata, sort_keys=True)]).casefold()
            matches = sum(1 for term in terms if term in haystack)
            if matches:
                scored.append((matches + entity.confidence, entity))
        scored.sort(key=lambda item: (-item[0], item[1].name.casefold()))
        return [entity for _, entity in scored[:limit]]

    def get_related_entities(self, entity_id: str) -> List[Entity]:
        entity = self.find_entity(entity_id)
        if not entity:
            return []
        ids = {edge.target for edge in self._semantic_edges(entity.id)}
        return [self.entities[eid] for eid in sorted(ids) if eid in self.entities]

    def get_entity_context(self, name_or_id: str) -> Dict[str, Any]:
        entity = self.find_entity(name_or_id)
        if not entity:
            return {"found": False, "query": name_or_id}
        relationships = [asdict(rel) for rel in self.relationships.values()
                         if rel.source_entity_id == entity.id or rel.target_entity_id == entity.id]
        events = [asdict(event) for event in self.events.values() if entity.id in event.involved_entity_ids]
        evidence = [asdict(self.evidence[eid]) for eid in entity.evidence_ids if eid in self.evidence]
        return {
            "found": True,
            "entity": asdict(entity),
            "relationships": relationships,
            "events": events,
            "evidence": evidence,
            "neighbors": [asdict(e) for e in self.get_related_entities(entity.id)],
        }

    # ── pathfinding ─────────────────────────────────────────────────────
    @dataclass(frozen=True)
    class _Edge:
        target: str
        label: str
        confidence: float
        evidence_ids: Tuple[str, ...] = ()
        via: str = "relationship"

    def _metadata_links(self, entity: Entity) -> Set[str]:
        raw = entity.metadata.get("links") or entity.metadata.get("related_entity_ids") or []
        if isinstance(raw, str):
            raw = [raw]
        return {str(item) for item in raw if str(item) in self.entities}

    def _semantic_edges(self, entity_id: str) -> List[_Edge]:
        if entity_id not in self.entities:
            return []
        entity = self.entities[entity_id]
        edges: List[SemanticKnowledgeGraph._Edge] = []
        for rel in self.relationships.values():
            if rel.source_entity_id == entity_id:
                edges.append(self._Edge(rel.target_entity_id, rel.relation_type, rel.confidence, tuple(rel.evidence_ids), "relationship"))
            elif rel.target_entity_id == entity_id:
                edges.append(self._Edge(rel.source_entity_id, f"reverse:{rel.relation_type}", rel.confidence, tuple(rel.evidence_ids), "relationship"))
        my_evidence = set(entity.evidence_ids)
        my_aliases = {_normalize(a) for a in entity.aliases}
        for other in self.entities.values():
            if other.id == entity_id:
                continue
            shared_evidence = my_evidence.intersection(other.evidence_ids)
            if shared_evidence:
                edges.append(self._Edge(other.id, "shares evidence with", min(entity.confidence, other.confidence) * 0.72, tuple(sorted(shared_evidence)), "shared_evidence"))
            if my_aliases and my_aliases.intersection({_normalize(a) for a in other.aliases} | {_normalize(other.name)}):
                edges.append(self._Edge(other.id, "alias overlaps with", min(entity.confidence, other.confidence) * 0.5, tuple(shared_evidence), "alias"))
        for event in self.events.values():
            if entity_id in event.involved_entity_ids:
                for other_id in event.involved_entity_ids:
                    if other_id != entity_id:
                        edges.append(self._Edge(other_id, f"co-occurs in event {event.title}", event.confidence, tuple(event.evidence_ids), "event"))
        for target_id in self._metadata_links(entity):
            edges.append(self._Edge(target_id, "metadata links to", entity.confidence, tuple(entity.evidence_ids), "metadata"))
        best: Dict[Tuple[str, str], SemanticKnowledgeGraph._Edge] = {}
        for edge in edges:
            key = (edge.target, edge.label)
            if key not in best or self._edge_score(edge) > self._edge_score(best[key]):
                best[key] = edge
        return sorted(best.values(), key=lambda e: (-self._edge_score(e), e.target, e.label))

    def _edge_score(self, edge: _Edge) -> float:
        evidence_bonus = min(0.12, 0.03 * len(edge.evidence_ids))
        return edge.confidence * self.EDGE_WEIGHTS.get(edge.via, 0.5) + evidence_bonus

    def semantic_neighbors(self, entity_id: str) -> List[Dict[str, Any]]:
        entity = self.find_entity(entity_id)
        if not entity:
            return []
        return [{"entity_id": edge.target, "entity_name": self.entities[edge.target].name, "relation": edge.label,
                 "confidence": edge.confidence, "edge_score": round(self._edge_score(edge), 4),
                 "evidence_ids": list(edge.evidence_ids), "via": edge.via}
                for edge in self._semantic_edges(entity.id) if edge.target in self.entities]

    def _resolve_entity_id(self, value: str) -> Optional[str]:
        entity = self.find_entity(value)
        return entity.id if entity else None

    def find_paths_between_entities(self, source: str, target: str, max_depth: int = 3) -> List[List[Dict[str, Any]]]:
        source_id = self._resolve_entity_id(source)
        target_id = self._resolve_entity_id(target)
        if not source_id or not target_id:
            return []
        queue = deque([(source_id, [])])
        paths: List[List[Dict[str, Any]]] = []
        while queue:
            current_id, steps = queue.popleft()
            if len(steps) >= max_depth:
                continue
            visited = {source_id, *[step["to_id"] for step in steps]}
            for edge in self._semantic_edges(current_id):
                if edge.target in visited:
                    continue
                step = {"from_id": current_id, "from_name": self.entities[current_id].name, "relation": edge.label,
                        "to_id": edge.target, "to_name": self.entities[edge.target].name,
                        "confidence": edge.confidence, "edge_score": round(self._edge_score(edge), 4),
                        "evidence_ids": list(edge.evidence_ids), "via": edge.via}
                new_steps = [*steps, step]
                if edge.target == target_id:
                    paths.append(new_steps)
                else:
                    queue.append((edge.target, new_steps))
        return self.rank_paths_by_confidence(paths)

    def shortest_semantic_path(self, source: str, target: str) -> List[Dict[str, Any]]:
        paths = self.find_paths_between_entities(source, target, max_depth=6)
        if not paths:
            return []
        paths.sort(key=lambda path: (len(path), -self._path_score(path), self.explain_path(path)))
        return paths[0]

    def _path_confidence(self, path: List[Dict[str, Any]]) -> float:
        if not path:
            return 0.0
        score = 1.0
        for step in path:
            score *= float(step.get("confidence", 0.0))
        return score

    def _path_score(self, path: List[Dict[str, Any]]) -> float:
        if not path:
            return 0.0
        total = sum(float(step.get("edge_score", step.get("confidence", 0.0))) for step in path)
        length_penalty = max(1, len(path))
        evidence_bonus = min(0.15, 0.02 * len({eid for step in path for eid in step.get("evidence_ids", [])}))
        return total / length_penalty + evidence_bonus

    def rank_paths_by_confidence(self, paths: List[List[Dict[str, Any]]]) -> List[List[Dict[str, Any]]]:
        return sorted(paths, key=lambda path: (-self._path_score(path), len(path), self.explain_path(path)))

    def explain_path_structured(self, path: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"text": self.explain_path(path), "length": len(path), "path_score": round(self._path_score(path), 4),
                "path_confidence": round(self._path_confidence(path), 4), "steps": path}

    def explain_path(self, path: List[Dict[str, Any]]) -> str:
        if not path:
            return "No semantic path found."
        parts = [path[0]["from_name"]]
        evidence_seen: List[str] = []
        for step in path:
            parts.append(f"{step['relation']} {step['to_name']}")
            evidence_seen.extend(step.get("evidence_ids", []))
        if evidence_seen:
            parts.append(f"supported by evidence {', '.join(_dedupe(evidence_seen))}")
        return " -> ".join(parts)

    def trace_evidence_path(self, entity_id: str) -> List[Dict[str, Any]]:
        entity = self.find_entity(entity_id)
        if not entity:
            return []
        trace: List[Dict[str, Any]] = []
        for eid in entity.evidence_ids:
            if eid in self.evidence:
                trace.append({"entity_id": entity.id, "entity_name": entity.name, "evidence": asdict(self.evidence[eid])})
        for rel in self.relationships.values():
            if entity.id in (rel.source_entity_id, rel.target_entity_id):
                for eid in rel.evidence_ids:
                    if eid in self.evidence:
                        trace.append({"relationship_id": rel.id, "relation_type": rel.relation_type, "evidence": asdict(self.evidence[eid])})
        for event in self.events.values():
            if entity.id in event.involved_entity_ids:
                for eid in event.evidence_ids:
                    if eid in self.evidence:
                        trace.append({"event_id": event.id, "event_title": event.title, "evidence": asdict(self.evidence[eid])})
        return trace

    # ── audit, compaction, persistence ───────────────────────────────────
    def audit_integrity(self) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []
        used_evidence: Set[str] = set()
        canonical_seen: Dict[str, str] = {}
        duplicates: List[Tuple[str, str, str]] = []
        for eid, ev in self.evidence.items():
            try:
                _require_confidence(ev.confidence); _json_safe(ev.metadata)
                if not _clean_text(ev.text_excerpt): errors.append(f"evidence {eid} has empty text_excerpt")
                if not _clean_text(ev.source_type): errors.append(f"evidence {eid} has empty source_type")
            except ValueError as exc:
                errors.append(f"evidence {eid}: {exc}")
        for ent in self.entities.values():
            ck = ent.metadata.get("canonical_key") or self._entity_canonical_key(ent.name, ent.type, ent.metadata)
            if ck in canonical_seen and canonical_seen[ck] != ent.id:
                duplicates.append((ck, canonical_seen[ck], ent.id))
            canonical_seen[ck] = ent.id
            try: _require_confidence(ent.confidence); _json_safe(ent.metadata)
            except ValueError as exc: errors.append(f"entity {ent.id}: {exc}")
            if not ent.evidence_ids: errors.append(f"entity {ent.id} has no evidence")
            for eid in ent.evidence_ids:
                if eid not in self.evidence: errors.append(f"entity {ent.id} references missing evidence {eid}")
                used_evidence.add(eid)
        for rel in self.relationships.values():
            if rel.source_entity_id not in self.entities: errors.append(f"relationship {rel.id} missing source {rel.source_entity_id}")
            if rel.target_entity_id not in self.entities: errors.append(f"relationship {rel.id} missing target {rel.target_entity_id}")
            if rel.source_entity_id == rel.target_entity_id and not rel.metadata.get("allow_self_relation"):
                errors.append(f"relationship {rel.id} is an unapproved self-relationship")
            try: _require_confidence(rel.confidence); _json_safe(rel.metadata)
            except ValueError as exc: errors.append(f"relationship {rel.id}: {exc}")
            if not rel.evidence_ids: errors.append(f"relationship {rel.id} has no evidence")
            for eid in rel.evidence_ids:
                if eid not in self.evidence: errors.append(f"relationship {rel.id} references missing evidence {eid}")
                used_evidence.add(eid)
        for event in self.events.values():
            try: _require_confidence(event.confidence); _json_safe(event.metadata)
            except ValueError as exc: errors.append(f"event {event.id}: {exc}")
            if not event.evidence_ids: errors.append(f"event {event.id} has no evidence")
            for entity_id in event.involved_entity_ids:
                if entity_id not in self.entities: errors.append(f"event {event.id} references missing entity {entity_id}")
            for eid in event.evidence_ids:
                if eid not in self.evidence: errors.append(f"event {event.id} references missing evidence {eid}")
                used_evidence.add(eid)
        orphaned = sorted(set(self.evidence) - used_evidence)
        if orphaned:
            warnings.append(f"orphaned evidence records: {len(orphaned)}")
        if duplicates:
            warnings.append(f"duplicate canonical entities: {len(duplicates)}")
        storage_parent = self.storage_path.parent
        return {"healthy": not errors, "errors": errors, "warnings": warnings,
                "error_count": len(errors), "warning_count": len(warnings),
                "orphaned_evidence": orphaned, "duplicate_canonical_entities": duplicates,
                "storage_path": str(self.storage_path), "storage_parent_exists": storage_parent.exists()}

    def compact(self) -> Dict[str, Any]:
        canonical_owner: Dict[str, str] = {}
        replacements: Dict[str, str] = {}
        merged = 0
        for ent in sorted(list(self.entities.values()), key=lambda e: e.id):
            ck = ent.metadata.get("canonical_key") or self._entity_canonical_key(ent.name, ent.type, ent.metadata)
            ent.metadata["canonical_key"] = ck
            if ck not in canonical_owner:
                canonical_owner[ck] = ent.id
                continue
            owner = self.entities[canonical_owner[ck]]
            self._merge_entity(owner, ent.name, ent.aliases, ent.confidence, ent.metadata, ent.evidence_ids)
            replacements[ent.id] = owner.id
            del self.entities[ent.id]
            merged += 1
        for rel in self.relationships.values():
            rel.source_entity_id = replacements.get(rel.source_entity_id, rel.source_entity_id)
            rel.target_entity_id = replacements.get(rel.target_entity_id, rel.target_entity_id)
        for event in self.events.values():
            event.involved_entity_ids = _dedupe([replacements.get(eid, eid) for eid in event.involved_entity_ids])
        old_rel_count = len(self.relationships)
        deduped: Dict[str, Relationship] = {}
        for rel in self.relationships.values():
            key = _stable_id("REL", rel.source_entity_id, rel.relation_type, rel.target_entity_id, ",".join(sorted(rel.evidence_ids)))
            rel.id = key
            if key in deduped:
                deduped[key].evidence_ids = _dedupe([*deduped[key].evidence_ids, *rel.evidence_ids])
                deduped[key].confidence = max(deduped[key].confidence, rel.confidence)
                deduped[key].metadata.update(rel.metadata)
            else:
                deduped[key] = rel
        self.relationships = deduped
        return {"merged_entities": merged, "deduped_relationships": old_rel_count - len(self.relationships), "replacements": replacements}

    def export_json(self) -> str:
        payload = {"schema": SCHEMA_VERSION,
                   "entities": [asdict(v) for v in sorted(self.entities.values(), key=lambda x: x.id)],
                   "relationships": [asdict(v) for v in sorted(self.relationships.values(), key=lambda x: x.id)],
                   "events": [asdict(v) for v in sorted(self.events.values(), key=lambda x: x.id)],
                   "evidence": [asdict(v) for v in sorted(self.evidence.values(), key=lambda x: x.id)]}
        return json.dumps(payload, indent=2, sort_keys=True)

    def import_json(self, data: str | Dict[str, Any]) -> None:
        payload = json.loads(data) if isinstance(data, str) else data
        schema = payload.get("schema")
        if schema not in SUPPORTED_SCHEMAS:
            raise ValueError(f"Unsupported semantic graph schema: {schema}")
        self.evidence = {item["id"]: Evidence(**item) for item in payload.get("evidence", [])}
        self.entities = {item["id"]: Entity(**item) for item in payload.get("entities", [])}
        self.relationships = {item["id"]: Relationship(**item) for item in payload.get("relationships", [])}
        self.events = {item["id"]: Event(**item) for item in payload.get("events", [])}
        for entity in self.entities.values():
            entity.metadata.setdefault("canonical_key", self._entity_canonical_key(entity.name, entity.type, entity.metadata))
            entity.metadata.setdefault("normalized_key", entity.metadata["canonical_key"].split(":", 1)[-1])
        self._validate_integrity()

    def _validate_integrity(self) -> None:
        audit = self.audit_integrity()
        if not audit["healthy"]:
            raise ValueError("Semantic graph integrity failed: " + "; ".join(audit["errors"][:5]))

    def save(self, path: Optional[Path | str] = None) -> Path:
        target = Path(path) if path else self.storage_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.export_json(), encoding="utf-8")
        return target

    def load(self, path: Optional[Path | str] = None) -> "SemanticKnowledgeGraph":
        target = Path(path) if path else self.storage_path
        self.import_json(target.read_text(encoding="utf-8"))
        return self

    def summary(self) -> Dict[str, Any]:
        audit = self.audit_integrity()
        return {"schema": SCHEMA_VERSION, "entities": len(self.entities), "relationships": len(self.relationships),
                "events": len(self.events), "evidence": len(self.evidence), "storage_path": str(self.storage_path),
                "healthy": audit["healthy"], "warnings": audit["warning_count"], "errors": audit["error_count"]}


class EntityExtractor:
    """Deterministic rule-based extractor for small local semantic seeding."""

    FILE_PATTERN = re.compile(r"\b[\w\-.]+\.(?:py|json|xml|md|txt|bat|sh|ps1|html)\b")
    MODULE_PATTERN = re.compile(r"\b(?:src|core|app|tests|storage|config|scripts|docs)/[\w/\-.]+\b")
    CODE_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)+\b|\b[a-z_][a-z0-9_]+\(\)")
    CAPS_PATTERN = re.compile(r"\b(?:[A-Z][A-Za-z0-9_\-]*(?:\s+[A-Z][A-Za-z0-9_\-]*){0,4})\b")
    PROJECT_PATTERN = re.compile(r"\b(?:WORDLIB|MotherEther|Gotham|Semantic Core|RAG|GPT-5|Claude|CloudRun|deploy_check\.py)\b", re.I)
    STOP_CAPS = {"the", "this", "it", "and", "or", "before", "after", "current", "existing", "include", "add", "do", "not", "no", "if", "when", "then"}

    def __init__(self, entity_hints: Optional[Dict[str, str]] = None) -> None:
        self.entity_hints = dict(entity_hints or {})

    def extract(self, text: str) -> List[Dict[str, Any]]:
        candidates: Dict[str, Dict[str, Any]] = {}
        def add(name: str, entity_type: str, confidence: float, reason: str, factors: Optional[List[str]] = None) -> None:
            name = _clean_text(name).strip(".,:;()[]{}<>\"'")
            if len(name) < 2:
                return
            metadata = {"extractor_reason": reason, "confidence_factors": factors or [reason],
                        "normalized_key": _canonical_key(name, entity_type).split(":", 1)[-1],
                        "canonical_key": _canonical_key(name, entity_type)}
            key = metadata["canonical_key"]
            item = {"name": name, "type": entity_type, "confidence": _clamped_confidence(confidence), "metadata": metadata}
            current = candidates.get(key)
            if not current or item["confidence"] > current["confidence"]:
                candidates[key] = item
        for name, entity_type in self.entity_hints.items():
            if re.search(rf"\b{re.escape(name)}\b", text, re.I):
                add(name, entity_type, 0.95, "configured_hint", ["configured_hint", "exact_text_match"])
        for match in self.MODULE_PATTERN.findall(text):
            etype = "module_path" if match.endswith(".py") else "path"
            add(match, etype, 0.91, "module_or_project_path", ["path_pattern", "project_relative"])
        for match in self.FILE_PATTERN.findall(text):
            add(match, "file", 0.86, "file_name", ["file_extension", "code_artifact"])
        for match in self.PROJECT_PATTERN.findall(text):
            label = "project" if match.casefold() in {"wordlib", "motherether", "gotham"} else "concept"
            add(match, label, 0.84, "known_project_or_concept", ["known_term"])
        for match in self.CODE_PATTERN.findall(text):
            label = "function" if match.endswith("()") else "class"
            add(match, label, 0.80, "code_symbol", ["code_naming_pattern"])
        for match in self.CAPS_PATTERN.findall(text):
            lowered = match.casefold()
            if lowered in self.STOP_CAPS or len(match.split()) == 1 and lowered in self.STOP_CAPS:
                continue
            if len(match) < 4 and not match.isupper():
                continue
            words = match.split()
            conf = 0.56 + min(0.18, 0.03 * len(words))
            add(match, "concept", conf, "capitalized_phrase", ["capitalization", f"word_count={len(words)}"])
        return sorted(candidates.values(), key=lambda item: (-item["confidence"], item["name"].casefold()))


class SemanticRAGBridge:
    """Minimal bridge for document text ingestion and prompt context generation."""

    def __init__(self, graph: Optional[SemanticKnowledgeGraph] = None, entity_hints: Optional[Dict[str, str]] = None) -> None:
        self.graph = graph or SemanticKnowledgeGraph()
        self.extractor = EntityExtractor(entity_hints=entity_hints)

    def ingest_document_text(self, text: str, source_path: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None,
                             source_id: Optional[str] = None, document_id: Optional[str] = None,
                             max_entities_per_document: int = 24, max_relationships_per_document: int = 16,
                             min_confidence: float = 0.55) -> Dict[str, Any]:
        if not _clean_text(text):
            raise ValueError("Cannot ingest empty document text.")
        _require_confidence(min_confidence)
        doc_metadata = dict(metadata or {})
        if document_id:
            doc_metadata["document_id"] = document_id
        source_type = "file" if source_path else "inline_text"
        evidence = self.graph.add_evidence(source_type=source_type, source_path=source_path, source_id=source_id,
                                           text_excerpt=text[:1000], metadata=doc_metadata, confidence=1.0)
        extracted = self.extractor.extract(text)
        accepted = [item for item in extracted if item["confidence"] >= min_confidence][:max_entities_per_document]
        skipped = [{"name": item["name"], "reason": "below_min_confidence" if item["confidence"] < min_confidence else "max_entities_limit",
                    "confidence": item["confidence"]} for item in extracted if item not in accepted]
        entities: List[Entity] = []
        for item in accepted:
            entity = self.graph.add_entity(item["name"], item["type"], confidence=item["confidence"],
                                           metadata={**item.get("metadata", {}), **({"source_path": source_path} if source_path else {}), **({"document_id": document_id} if document_id else {})},
                                           evidence_ids=[evidence.id])
            entities.append(entity)
        rel_count = 0
        anchors = entities[:max_relationships_per_document + 1]
        for left, right in zip(anchors, anchors[1:]):
            if left.id != right.id and rel_count < max_relationships_per_document:
                self.graph.add_relationship(left.id, right.id, "co_occurs_in_document",
                                            confidence=min(left.confidence, right.confidence, 0.75), evidence_ids=[evidence.id],
                                            metadata={"source_path": source_path, "document_id": document_id})
                rel_count += 1
        return {"evidence_id": evidence.id, "entities": [asdict(e) for e in entities], "entity_count": len(entities),
                "relationship_count": rel_count, "skipped_candidates": skipped, "skipped_count": len(skipped)}

    def semantic_context_for_query(self, query: str) -> Dict[str, Any]:
        matches = self.graph.search_entities(query, limit=5)
        contexts = [self.graph.get_entity_context(entity.id) for entity in matches]
        paths: List[Dict[str, Any]] = []
        if len(matches) >= 2:
            path = self.graph.shortest_semantic_path(matches[0].id, matches[1].id)
            if path:
                paths.append(self.graph.explain_path_structured(path))
        top_evidence: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for entity in matches:
            for eid in entity.evidence_ids:
                if eid in self.graph.evidence and eid not in seen:
                    ev = self.graph.evidence[eid]
                    top_evidence.append({"id": eid, "source_type": ev.source_type, "source_path": ev.source_path,
                                         "text_excerpt": ev.text_excerpt[:240], "confidence": ev.confidence})
                    seen.add(eid)
        warnings = []
        if not matches:
            warnings.append("No matching semantic entities found for query.")
        if self.graph.summary()["entities"] < 3:
            warnings.append("Semantic graph is sparse; context may be weak.")
        return {"query": query, "matches": [asdict(e) for e in matches], "contexts": contexts, "paths": paths,
                "top_evidence": top_evidence[:5], "warnings": warnings, "summary": self.graph.summary()}

    def graph_summary_for_prompt(self, query: str) -> str:
        context = self.semantic_context_for_query(query)
        lines = ["WORDLIB semantic graph context:"]
        lines.append(f"Summary: {context['summary']['entities']} entities, {context['summary']['relationships']} relationships, {context['summary']['evidence']} evidence records, healthy={context['summary']['healthy']}.")
        for warning in context["warnings"]:
            lines.append(f"Warning: {warning}")
        for entity in context["matches"]:
            ev = ", ".join(entity.get("evidence_ids", [])) or "no evidence"
            reason = entity.get("metadata", {}).get("extractor_reason", "manual_or_imported")
            lines.append(f"- {entity['name']} ({entity['type']}, confidence={entity['confidence']:.2f}, reason={reason}) evidence={ev}")
        for evidence in context["top_evidence"]:
            src = evidence.get("source_path") or evidence.get("source_type")
            lines.append(f"Evidence {evidence['id']} from {src}: {evidence['text_excerpt']}")
        for path in context["paths"]:
            lines.append(f"Path: {path['text']} [score={path['path_score']}]")
        return "\n".join(lines)


def self_check() -> bool:
    graph = SemanticKnowledgeGraph()
    ev = graph.add_evidence("self_check", "WORDLIB Semantic Core self-check evidence.")
    a = graph.add_entity("WORDLIB", "project", confidence=0.9, evidence_ids=[ev.id])
    b = graph.add_entity("semantic_core.py", "file", confidence=0.9, evidence_ids=[ev.id])
    graph.add_relationship(a.id, b.id, "contains module", confidence=0.9, evidence_ids=[ev.id])
    bridge = SemanticRAGBridge(graph)
    bridge.ingest_document_text("WORDLIB uses src/semantic_core.py for Entity provenance.", source_path="self_check.md")
    graph.compact()
    assert graph.summary()["entities"] >= 2
    assert graph.shortest_semantic_path("WORDLIB", "semantic_core.py")
    assert "semantic graph context" in bridge.graph_summary_for_prompt("WORDLIB semantic_core.py")
    clone = SemanticKnowledgeGraph()
    clone.import_json(graph.export_json())
    assert clone.audit_integrity()["healthy"]
    return True


if __name__ == "__main__":
    ok = self_check()
    print(json.dumps({"semantic_core_self_check": ok, "schema": SCHEMA_VERSION, "storage_path": str(_default_storage_path())}, indent=2))

"""
WORDLIB Semantic Adapter v2
===========================
Stable boundary layer between WORDLIB subsystems and semantic_core.py.

Purpose:
- keep RAG/memory/reasoning modules from depending on graph internals
- provide safe, provenance-aware ingestion and context methods
- preserve path safety and deployment-testable behavior
- stay dependency-light and deterministic
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_SRC_DIR = Path(__file__).resolve().parent
_ROOT = _SRC_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from semantic_core import (  # noqa: E402
    SCHEMA_VERSION,
    SemanticKnowledgeGraph,
    SemanticRAGBridge,
    resolve_semantic_storage_path,
)

try:  # noqa: E402
    from local_ontology import LocalOntologyLayer, create_default_ontology, ONTOLOGY_SCHEMA_VERSION
except Exception:  # pragma: no cover - deployment gate reports failures explicitly
    LocalOntologyLayer = None
    create_default_ontology = None
    ONTOLOGY_SCHEMA_VERSION = "unavailable"

try:  # noqa: E402
    from reasoning.output_quality import OutputQualityChecker
except Exception:  # pragma: no cover - fallback keeps adapter import-safe
    OutputQualityChecker = None

try:  # noqa: E402
    from core.paths import migration_report, health_report
except Exception:  # pragma: no cover - status reports degraded centralization explicitly
    migration_report = None
    health_report = None


@dataclass(frozen=True)
class SemanticAdapterConfig:
    """Small immutable config for safe semantic subsystem access."""

    storage_path: Optional[str] = None
    auto_load: bool = True
    auto_save: bool = False
    max_entities_per_document: int = 24
    max_relationships_per_document: int = 16
    min_confidence: float = 0.55
    entity_hints: Dict[str, str] = field(default_factory=dict)
    component_name: str = "semantic_adapter"
    enable_local_ontology: bool = True
    memory_root: Optional[str] = None
    max_memory_items: int = 8
    code_root: Optional[str] = None
    max_code_files: int = 160
    max_code_items: int = 12


@dataclass
class SemanticAdapterResult:
    """Stable result object so callers do not depend on internal graph classes."""

    ok: bool
    operation: str
    data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "operation": self.operation,
            "data": self.data,
            "warnings": list(self.warnings),
            "error": self.error,
        }


@dataclass
class NexusSnapshot:
    """
    Exportable, read-only NEXUS context snapshot.

    This is the central intelligence handoff object: it normalizes semantic graph,
    ontology, memory/event, code-structure, and RAG-style context into one stable
    shape without writing to any backing store.
    """

    contract: str
    query: Optional[str]
    generated_at: str
    read_only: bool
    summary: Dict[str, Any]
    sections: Dict[str, Dict[str, Any]]
    health: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    causal_links: List[Dict[str, Any]] = field(default_factory=list)
    temporal_links: List[Dict[str, Any]] = field(default_factory=list)
    retrieval_reasoning: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "query": self.query,
            "generated_at": self.generated_at,
            "read_only": self.read_only,
            "summary": self.summary,
            "sections": self.sections,
            "health": self.health,
            "warnings": list(self.warnings),
            "causal_links": list(self.causal_links),
            "temporal_links": list(self.temporal_links),
            "retrieval_reasoning": list(self.retrieval_reasoning),
            "metadata": self.metadata,
        }

    def export_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)


@dataclass
class ReflectionResult:
    """
    Read-only self-critique over a NexusSnapshot.

    The result is deliberately simple and JSON-safe: it scores snapshot quality,
    identifies sparse or weak sections, and proposes additional context to
    improve retrieval without mutating memory, code, ontology, RAG, or graph
    state.
    """

    overall_relevance_score: float
    section_scores: Dict[str, float]
    missing_or_weak_sections: List[str]
    retrieval_weaknesses: List[str]
    suggested_improvements: List[str]
    critique_summary: str
    generated_at: str
    query: Optional[str] = None
    contract: str = "wordlib.nexus_reflection.v1"
    read_only: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "read_only": self.read_only,
            "overall_relevance_score": float(self.overall_relevance_score),
            "section_scores": dict(self.section_scores),
            "missing_or_weak_sections": list(self.missing_or_weak_sections),
            "retrieval_weaknesses": list(self.retrieval_weaknesses),
            "suggested_improvements": list(self.suggested_improvements),
            "critique_summary": self.critique_summary,
            "generated_at": self.generated_at,
            "query": self.query,
            "metadata": self.metadata,
        }

    def export_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)




@dataclass
class IntelligentContextPackage:
    """
    Read-only, goal-aware NEXUS bridge package for Cloud and future agents.

    This object is intentionally not a storage engine. It curates and audits
    existing NEXUS context using v30-style single-source-of-truth, guarded
    mutation proposal, and honest quality-heuristic principles.
    """

    goal: str
    curated_context: Dict[str, Any]
    selection_reasoning: str
    context_health: Dict[str, Any]
    quality_audit: Dict[str, Any]
    overall_quality_score: float
    token_estimate: int
    warnings: List[str]
    proposed_mutations: List[Dict[str, Any]]
    generated_at: str
    strictness: str = "production"
    max_tokens: int = 12000
    contract: str = "wordlib.nexus_intelligent_context.v1"
    read_only: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "read_only": self.read_only,
            "goal": self.goal,
            "strictness": self.strictness,
            "max_tokens": self.max_tokens,
            "curated_context": self.curated_context,
            "selection_reasoning": self.selection_reasoning,
            "context_health": self.context_health,
            "quality_audit": self.quality_audit,
            "overall_quality_score": float(self.overall_quality_score),
            "token_estimate": int(self.token_estimate),
            "warnings": list(self.warnings),
            "proposed_mutations": list(self.proposed_mutations),
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }

    def export_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)


@dataclass
class CausalTemporalProposal:
    """
    Read-only temporal/causal candidate proposal over NEXUS context.

    This is scaffolding, not truth storage: every link is explicitly a
    candidate with evidence and confidence, and nothing is persisted.
    """

    candidates: List[Dict[str, Any]]
    summary: str
    warnings: List[str]
    future_integration_notes: List[str]
    generated_at: str
    query: Optional[str] = None
    max_candidates: int = 12
    contract: str = "wordlib.nexus_causal_temporal.v1"
    read_only: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    scaffolding_entry: Dict[str, Any] = field(default_factory=dict)
    pathfinder_routes: List[Dict[str, Any]] = field(default_factory=list)
    self_reorganization_bridge: Dict[str, Any] = field(default_factory=dict)
    merge_guidance: Dict[str, Any] = field(default_factory=dict)
    reorganization_pathways: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "read_only": self.read_only,
            "query": self.query,
            "max_candidates": int(self.max_candidates),
            "candidates": list(self.candidates),
            "summary": self.summary,
            "warnings": list(self.warnings),
            "future_integration_notes": list(self.future_integration_notes),
            "scaffolding_entry": self.scaffolding_entry,
            "pathfinder_routes": list(self.pathfinder_routes),
            "self_reorganization_bridge": self.self_reorganization_bridge,
            "merge_guidance": self.merge_guidance,
            "reorganization_pathways": list(self.reorganization_pathways),
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }

    def export_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)




@dataclass
class CommanderPathwayPackage:
    """
    Single-call, read-only NEXUS Commander package.

    This is not an executor. It forges sequenced troubleshooting pathways
    from IntelligentContextPackage + causal pathfinder routes so Cloud can
    consume one cohesive central-nervous-system surface.
    """

    goal: str
    commander_summary: str
    public_surface: Dict[str, Any]
    troubleshooting_pathways: List[Dict[str, Any]]
    sequenced_steps: List[Dict[str, Any]]
    invalidation_map: List[Dict[str, Any]]
    failure_predictions: List[Dict[str, Any]]
    evidence_routes: List[Dict[str, Any]]
    causal_bridge_summary: Dict[str, Any]
    merge_capabilities: Dict[str, Any]
    warnings: List[str]
    generated_at: str
    strictness: str = "production"
    max_steps: int = 8
    contract: str = "wordlib.nexus_commander_pathway.v1"
    read_only: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "read_only": self.read_only,
            "goal": self.goal,
            "strictness": self.strictness,
            "max_steps": int(self.max_steps),
            "commander_summary": self.commander_summary,
            "public_surface": self.public_surface,
            "troubleshooting_pathways": list(self.troubleshooting_pathways),
            "sequenced_steps": list(self.sequenced_steps),
            "invalidation_map": list(self.invalidation_map),
            "failure_predictions": list(self.failure_predictions),
            "evidence_routes": list(self.evidence_routes),
            "causal_bridge_summary": self.causal_bridge_summary,
            "merge_capabilities": self.merge_capabilities,
            "warnings": list(self.warnings),
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }

    def export_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)


class SemanticAdapter:
    """
    High-grade, low-coupling adapter for semantic_core.py.

    Callers should use this class instead of reaching into graph internals. It
    exposes conservative operations for ingestion, context generation, evidence-
    backed fact creation, status, audit, and persistence.
    """

    CONTRACT_VERSION = "wordlib.semantic_adapter.v2"

    def __init__(self, config: Optional[SemanticAdapterConfig] = None,
                 graph: Optional[SemanticKnowledgeGraph] = None) -> None:
        self.config = config or SemanticAdapterConfig()
        storage = self.config.storage_path or None
        self.graph = graph or SemanticKnowledgeGraph(storage_path=storage)
        self.ontology = create_default_ontology() if (self.config.enable_local_ontology and create_default_ontology) else None
        self.bridge = SemanticRAGBridge(self.graph, entity_hints=self._merged_entity_hints())
        self.last_audit: Dict[str, Any] = {}
        if self.config.auto_load and self.graph.storage_path.exists():
            try:
                self.graph.load()
            except Exception:
                # Do not crash imports because of a broken persisted graph.
                # health_check() will expose the exact problem.
                pass

    @property
    def storage_path(self) -> Path:
        return self.graph.storage_path

    def _merged_entity_hints(self) -> Dict[str, str]:
        hints: Dict[str, str] = {}
        if self.ontology is not None:
            hints.update(self.ontology.entity_hints())
        hints.update(self.config.entity_hints)
        return hints

    def _save_if_configured(self) -> None:
        if self.config.auto_save:
            self.graph.save()

    def _result(self, operation: str, data: Optional[Dict[str, Any]] = None,
                warnings: Optional[Iterable[str]] = None) -> SemanticAdapterResult:
        return SemanticAdapterResult(True, operation, data or {}, list(warnings or []))

    def _error(self, operation: str, exc: Exception) -> SemanticAdapterResult:
        return SemanticAdapterResult(False, operation, {}, [], f"{type(exc).__name__}: {exc}")

    def health_check(self) -> SemanticAdapterResult:
        """Return import/storage/audit status without requiring external tools."""
        try:
            audit = self.graph.audit_integrity()
            self.last_audit = audit
            storage = self.graph.storage_path.resolve()
            root = _ROOT.resolve()
            project_local = str(storage).startswith(str(root))
            data = {
                "contract": self.CONTRACT_VERSION,
                "schema": SCHEMA_VERSION,
                "storage_path": str(storage),
                "project_local_storage": project_local,
                "summary": self.graph.summary(),
                "audit": audit,
                "local_ontology": self.local_ontology_summary().data if self.ontology is not None else {"available": False},
            }
            warnings = []
            if not project_local:
                warnings.append("semantic storage path is outside the WORDLIB project root")
            if not audit.get("healthy", False):
                warnings.append("semantic graph audit is unhealthy")
            return self._result("health_check", data, warnings)
        except Exception as exc:
            return self._error("health_check", exc)

    def ingest_text(self, text: str, source_path: Optional[str] = None,
                    source_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None,
                    document_id: Optional[str] = None, min_confidence: Optional[float] = None,
                    max_entities: Optional[int] = None,
                    max_relationships: Optional[int] = None) -> SemanticAdapterResult:
        """Ingest document text through SemanticRAGBridge with bounded growth controls."""
        try:
            result = self.bridge.ingest_document_text(
                text=text,
                source_path=source_path,
                source_id=source_id,
                metadata={**(metadata or {}), "adapter_component": self.config.component_name},
                document_id=document_id,
                min_confidence=self.config.min_confidence if min_confidence is None else min_confidence,
                max_entities_per_document=self.config.max_entities_per_document if max_entities is None else max_entities,
                max_relationships_per_document=self.config.max_relationships_per_document if max_relationships is None else max_relationships,
            )
            self._save_if_configured()
            warnings = []
            if result.get("skipped_count", 0):
                warnings.append(f"{result['skipped_count']} candidate(s) skipped by ingestion controls")
            return self._result("ingest_text", result, warnings)
        except Exception as exc:
            return self._error("ingest_text", exc)

    def add_evidence_backed_fact(self, subject: str, predicate: str, object_name: str,
                                 evidence_text: str, subject_type: str = "concept",
                                 object_type: str = "concept", source_type: str = "manual",
                                 source_path: Optional[str] = None,
                                 source_id: Optional[str] = None,
                                 confidence: float = 0.75,
                                 metadata: Optional[Dict[str, Any]] = None) -> SemanticAdapterResult:
        """Create a tiny evidence-backed triple without exposing graph internals."""
        try:
            meta = {**(metadata or {}), "adapter_component": self.config.component_name}
            ev = self.graph.add_evidence(source_type=source_type, source_path=source_path,
                                         source_id=source_id, text_excerpt=evidence_text,
                                         confidence=confidence, metadata=meta)
            left = self.graph.add_entity(subject, subject_type, confidence=confidence,
                                         evidence_ids=[ev.id], metadata={"created_by": self.config.component_name})
            right = self.graph.add_entity(object_name, object_type, confidence=confidence,
                                          evidence_ids=[ev.id], metadata={"created_by": self.config.component_name})
            rel = self.graph.add_relationship(left.id, right.id, predicate, confidence=confidence,
                                              evidence_ids=[ev.id], metadata=meta)
            self._save_if_configured()
            return self._result("add_evidence_backed_fact", {
                "evidence_id": ev.id,
                "source_entity_id": left.id,
                "target_entity_id": right.id,
                "relationship_id": rel.id,
            })
        except Exception as exc:
            return self._error("add_evidence_backed_fact", exc)

    def context_for_query(self, query: str, as_prompt: bool = False) -> SemanticAdapterResult:
        """Return structured semantic context or compact prompt text."""
        try:
            ontology_context = self.ontology.context_for_query(query) if self.ontology is not None else {"matches": [], "warnings": ["local ontology unavailable"]}
            if as_prompt:
                ontology_prompt = self.ontology.prompt_context(query) if self.ontology is not None else "Local ontology context: unavailable."
                semantic_prompt = self.bridge.graph_summary_for_prompt(query)
                return self._result("context_for_query", {
                    "prompt_context": f"{ontology_prompt}\n\n{semantic_prompt}",
                    "local_ontology": ontology_context,
                })
            data = self.bridge.semantic_context_for_query(query)
            data["local_ontology"] = ontology_context
            return self._result("context_for_query", data, ontology_context.get("warnings", []))
        except Exception as exc:
            return self._error("context_for_query", exc)

    def shortest_path(self, source: str, target: str) -> SemanticAdapterResult:
        """Return shortest semantic path in stable text + structured forms."""
        try:
            path = self.graph.shortest_semantic_path(source, target)
            if not path:
                return self._result("shortest_path", {"found": False, "source": source, "target": target},
                                    ["no semantic path found"])
            return self._result("shortest_path", {
                "found": True,
                "text": self.graph.explain_path(path),
                "structured": self.graph.explain_path_structured(path),
            })
        except Exception as exc:
            return self._error("shortest_path", exc)

    def compact_and_audit(self) -> SemanticAdapterResult:
        """Normalize graph, preserve evidence, and return post-compaction audit."""
        try:
            compact_result = self.graph.compact()
            audit = self.graph.audit_integrity()
            self.last_audit = audit
            self._save_if_configured()
            return self._result("compact_and_audit", {"compact": compact_result, "audit": audit},
                                [] if audit.get("healthy") else ["post-compaction audit is unhealthy"])
        except Exception as exc:
            return self._error("compact_and_audit", exc)


    def local_ontology_summary(self) -> SemanticAdapterResult:
        """Return read-only local ontology status and term counts."""
        try:
            if self.ontology is None:
                return self._result("local_ontology_summary", {"available": False, "schema": ONTOLOGY_SCHEMA_VERSION}, ["local ontology unavailable"])
            audit = self.ontology.audit()
            data = {"available": True, "schema": ONTOLOGY_SCHEMA_VERSION, "summary": self.ontology.summary(), "audit": audit}
            return self._result("local_ontology_summary", data, [] if audit.get("healthy") else ["local ontology audit is unhealthy"])
        except Exception as exc:
            return self._error("local_ontology_summary", exc)

    def ontology_context_for_query(self, query: str, as_prompt: bool = False) -> SemanticAdapterResult:
        """Return read-only local ontology context without writing to semantic graph."""
        try:
            if self.ontology is None:
                return self._result("ontology_context_for_query", {"matches": [], "prompt_context": "Local ontology context: unavailable."}, ["local ontology unavailable"])
            if as_prompt:
                return self._result("ontology_context_for_query", {"prompt_context": self.ontology.prompt_context(query)})
            return self._result("ontology_context_for_query", self.ontology.context_for_query(query))
        except Exception as exc:
            return self._error("ontology_context_for_query", exc)


    def _memory_root(self, memory_root: Optional[str] = None) -> Path:
        """Resolve memory root without allowing accidental path escape by default."""
        base = Path(memory_root or self.config.memory_root or (_ROOT / "data"))
        if not base.is_absolute():
            base = (_ROOT / base).resolve()
        return base.resolve()

    @staticmethod
    def _query_terms(query: str) -> List[str]:
        terms = []
        for raw in str(query or "").replace("_", " ").replace("-", " ").split():
            cleaned = "".join(ch for ch in raw.lower() if ch.isalnum())
            if len(cleaned) >= 3 and cleaned not in {"the", "and", "for", "with", "from", "this", "that"}:
                terms.append(cleaned)
        return sorted(set(terms))

    @staticmethod
    def _safe_json_load(path: Path) -> Any:
        if not path.exists() or not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _safe_jsonl_tail(path: Path, limit: int = 20) -> List[Dict[str, Any]]:
        if not path.exists() or not path.is_file():
            return []
        rows: List[Dict[str, Any]] = []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, limit):]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
            except Exception:
                rows.append({"unparsed": line[:240]})
        return rows

    @staticmethod
    def _matches_query(value: Any, terms: List[str]) -> bool:
        if not terms:
            return False
        text = json.dumps(value, sort_keys=True, default=str).lower()
        return any(term in text for term in terms)

    def memory_context_for_query(self, query: str, as_prompt: bool = False,
                                 memory_root: Optional[str] = None,
                                 max_items: Optional[int] = None) -> SemanticAdapterResult:
        """
        Return read-only context from existing WORDLIB memory surfaces.

        This does not write semantic facts, mutate memory, start agents, or import
        graph internals. It is intentionally a reader over gremlin_memory.json and
        ether_events.jsonl, enriched through this adapter's ontology/semantic query
        context.
        """
        try:
            root = self._memory_root(memory_root)
            project_local = str(root).startswith(str(_ROOT.resolve()))
            limit = max(1, int(max_items or self.config.max_memory_items))
            terms = self._query_terms(query)
            warnings: List[str] = []
            if not project_local:
                warnings.append("memory root is outside WORDLIB project root; read-only access only")

            gremlin_path = root / "gremlin_memory.json"
            events_path = root / "ether_events.jsonl"
            gremlin = self._safe_json_load(gremlin_path) or {"cycles": [], "uncertainty_history": []}
            events = self._safe_jsonl_tail(events_path, limit=max(20, limit * 3))

            cycles = list(gremlin.get("cycles", [])) if isinstance(gremlin, dict) else []
            uncertainty = list(gremlin.get("uncertainty_history", [])) if isinstance(gremlin, dict) else []
            matched_cycles = [c for c in cycles if self._matches_query(c, terms)] if terms else []
            matched_events = [e for e in events if self._matches_query(e, terms)] if terms else []
            recent_cycles = cycles[-limit:]
            recent_events = events[-limit:]

            weakness_kinds: Dict[str, int] = {}
            proposal_targets: Dict[str, int] = {}
            for cycle in cycles:
                for weakness in cycle.get("weaknesses", []) if isinstance(cycle, dict) else []:
                    kind = str(weakness.get("kind", "unknown"))
                    weakness_kinds[kind] = weakness_kinds.get(kind, 0) + 1
                for proposal in cycle.get("proposals", []) if isinstance(cycle, dict) else []:
                    target = str(proposal.get("target", "unknown"))
                    proposal_targets[target] = proposal_targets.get(target, 0) + 1

            event_types: Dict[str, int] = {}
            for event in events:
                event_type = str(event.get("event", event.get("event_type", "unknown")))
                event_types[event_type] = event_types.get(event_type, 0) + 1

            semantic = self.context_for_query(query, as_prompt=as_prompt)
            data: Dict[str, Any] = {
                "read_only": True,
                "query": query,
                "memory_root": str(root),
                "project_local_memory": project_local,
                "sources": {
                    "gremlin_memory": {"path": str(gremlin_path), "exists": gremlin_path.exists(), "cycles": len(cycles), "uncertainty_samples": len(uncertainty)},
                    "ether_events": {"path": str(events_path), "exists": events_path.exists(), "events_sampled": len(events)},
                },
                "summary": {
                    "cycles": len(cycles),
                    "events_sampled": len(events),
                    "matched_cycles": len(matched_cycles),
                    "matched_events": len(matched_events),
                    "weakness_kinds": weakness_kinds,
                    "proposal_targets": proposal_targets,
                    "event_types": event_types,
                },
                "matches": {
                    "cycles": matched_cycles[-limit:],
                    "events": matched_events[-limit:],
                    "recent_cycles": recent_cycles,
                    "recent_events": recent_events,
                },
                "semantic_context": semantic.data if semantic.ok else {},
                "semantic_error": semantic.error,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            if as_prompt:
                lines = [
                    "WORDLIB memory context (read-only):",
                    f"- Sources: gremlin cycles={len(cycles)}, event samples={len(events)}.",
                    f"- Query matches: cycles={len(matched_cycles)}, events={len(matched_events)}.",
                ]
                if weakness_kinds:
                    top_weaknesses = ", ".join(f"{k}:{v}" for k, v in sorted(weakness_kinds.items())[:5])
                    lines.append(f"- Recurring weakness kinds: {top_weaknesses}.")
                if proposal_targets:
                    top_targets = ", ".join(f"{k}:{v}" for k, v in sorted(proposal_targets.items())[:5])
                    lines.append(f"- Recurring proposal targets: {top_targets}.")
                if matched_cycles[-1:] or recent_cycles[-1:]:
                    latest = (matched_cycles[-1:] or recent_cycles[-1:])[0]
                    lines.append(f"- Latest relevant cycle: {json.dumps(latest, sort_keys=True, default=str)[:500]}")
                if matched_events[-1:] or recent_events[-1:]:
                    latest_event = (matched_events[-1:] or recent_events[-1:])[0]
                    lines.append(f"- Latest relevant event: {json.dumps(latest_event, sort_keys=True, default=str)[:500]}")
                if semantic.ok:
                    prompt = semantic.data.get("prompt_context") or json.dumps(semantic.data, sort_keys=True, default=str)[:800]
                    lines.append("")
                    lines.append(str(prompt))
                data["prompt_context"] = "\n".join(lines)
            return self._result("memory_context_for_query", data, warnings)
        except Exception as exc:
            return self._error("memory_context_for_query", exc)


    def code_structure_context_for_query(self, query: str, as_prompt: bool = False,
                                         root: Optional[str] = None,
                                         max_files: Optional[int] = None,
                                         max_items: Optional[int] = None) -> SemanticAdapterResult:
        """
        Return read-only AST code-structure context through the adapter boundary.

        This is the first NEXUS-style code awareness surface: modules, classes,
        functions, imports, signatures, docstrings, and basic call sites are
        exposed as structured context without writing graph/memory/code and
        without importing SemanticKnowledgeGraph internals into callers.
        """
        try:
            from code_structure_hook import CodeStructureHook
            hook = CodeStructureHook(
                root=root or self.config.code_root,
                max_files=self.config.max_code_files if max_files is None else max_files,
                max_items=self.config.max_code_items if max_items is None else max_items,
            )
            code_data = hook.context_for_query(query, as_prompt=as_prompt)
            semantic = self.context_for_query(query, as_prompt=as_prompt)
            data: Dict[str, Any] = {
                "read_only": True,
                "query": query,
                "code_structure": code_data,
                "summary": code_data.get("summary", {}),
                "sources": code_data.get("sources", {}),
                "matches": code_data.get("matches", {}),
                "semantic_context": semantic.data if semantic.ok else {},
                "semantic_error": semantic.error,
                "nexus_role": "code_structure_context",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            warnings = list(code_data.get("warnings", []))
            if semantic.warnings:
                warnings.extend(semantic.warnings)
            if as_prompt:
                prompt_parts = [code_data.get("prompt_context", "WORDLIB code structure context (read-only AST): unavailable.")]
                if semantic.ok:
                    prompt_parts.append(semantic.data.get("prompt_context") or json.dumps(semantic.data, sort_keys=True, default=str)[:800])
                data["prompt_context"] = "\n\n".join(str(part) for part in prompt_parts if part)
            return self._result("code_structure_context_for_query", data, warnings)
        except Exception as exc:
            return self._error("code_structure_context_for_query", exc)


    @staticmethod
    def _section_from_result(name: str, result: SemanticAdapterResult) -> Dict[str, Any]:
        """Normalize adapter results into a NEXUS source section."""
        return {
            "name": name,
            "ok": bool(result.ok),
            "operation": result.operation,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "warnings": list(result.warnings),
            "error": result.error,
            "data": result.data,
        }

    def get_unified_nexus_snapshot(self, query: Optional[str] = None) -> NexusSnapshot:
        """
        Build one clean, exportable, read-only NEXUS context snapshot.

        The snapshot combines memory/event context, AST code-structure context,
        local ontology context, and semantic/RAG graph context behind the
        SemanticAdapter boundary. It performs no writes and introduces no heavy
        dependencies.
        """
        q = query or "WORDLIB NEXUS SemanticAdapter memory code ontology RAG"
        generated_at = datetime.now(timezone.utc).isoformat()
        warnings: List[str] = []
        retrieval_reasoning = [
            "memory section selected through memory_context_for_query() to expose Gremlin cycles and ether events read-only",
            "code section selected through code_structure_context_for_query() to expose AST module/class/function/import context read-only",
            "ontology section selected through ontology_context_for_query() to ground WORDLIB-local vocabulary and constraints",
            "rag section selected through context_for_query() to expose semantic graph and prompt-ready RAG context",
        ]

        memory = self.memory_context_for_query(q, as_prompt=False)
        code = self.code_structure_context_for_query(q, as_prompt=False)
        ontology = self.ontology_context_for_query(q, as_prompt=False)
        rag = self.context_for_query(q, as_prompt=False)
        adapter_health = self.health_check()

        sections = {
            "memory": self._section_from_result("memory", memory),
            "code": self._section_from_result("code", code),
            "ontology": self._section_from_result("ontology", ontology),
            "rag": self._section_from_result("rag", rag),
        }
        for section in sections.values():
            warnings.extend(section.get("warnings", []))
            if section.get("error"):
                warnings.append(f"{section['name']} section error: {section['error']}")

        section_health = {name: {"ok": sec["ok"], "warnings": len(sec.get("warnings", [])), "error": sec.get("error")} for name, sec in sections.items()}
        available = [name for name, health in section_health.items() if health.get("ok")]
        missing = [name for name, health in section_health.items() if not health.get("ok")]
        overall_healthy = not missing and adapter_health.ok
        if missing:
            warnings.append("missing or unhealthy NEXUS sections: " + ", ".join(missing))
        if adapter_health.warnings:
            warnings.extend(adapter_health.warnings)

        memory_summary = memory.data.get("summary", {}) if memory.ok else {}
        code_summary = code.data.get("summary", {}) if code.ok else {}
        ontology_matches = ontology.data.get("matches", []) if ontology.ok else []
        rag_summary = rag.data.get("summary", {}) if rag.ok else {}
        if not rag_summary and rag.ok:
            rag_summary = rag.data.get("graph_summary", {}) or rag.data.get("semantic_context", {}).get("summary", {})

        summary = {
            "nexus_role": "unified_context_snapshot",
            "query": q,
            "healthy": overall_healthy,
            "sections_available": available,
            "sections_missing": missing,
            "agent_summary": (
                "NEXUS unified context snapshot combines read-only memory/events, AST code structure, local ontology, "
                "and semantic/RAG graph context behind SemanticAdapter. Future causal and temporal links are reserved "
                "but intentionally empty until the causal layer is implemented."
            ),
            "memory": {
                "cycles": memory_summary.get("cycles", 0),
                "events_sampled": memory_summary.get("events_sampled", 0),
                "matched_cycles": memory_summary.get("matched_cycles", 0),
                "matched_events": memory_summary.get("matched_events", 0),
            },
            "code": {
                "modules": code_summary.get("modules", 0),
                "classes": code_summary.get("classes", 0),
                "functions": code_summary.get("functions", 0),
                "imports": code_summary.get("imports", 0),
            },
            "ontology": {"matches": len(ontology_matches)},
            "rag": rag_summary,
            "warning_count": len(warnings),
        }

        health = {
            "overall": overall_healthy,
            "adapter": {"ok": adapter_health.ok, "warnings": len(adapter_health.warnings), "error": adapter_health.error},
            "sections": section_health,
        }
        return NexusSnapshot(
            contract="wordlib.nexus_snapshot.v1",
            query=q,
            generated_at=generated_at,
            read_only=True,
            summary=summary,
            sections=sections,
            health=health,
            warnings=warnings,
            causal_links=[],
            temporal_links=[],
            retrieval_reasoning=retrieval_reasoning,
            metadata={
                "adapter_contract": self.CONTRACT_VERSION,
                "schema": SCHEMA_VERSION,
                "storage_path": str(self.graph.storage_path),
                "heavy_dependencies": [],
                "future_layers": ["reflection_self_critique", "temporal_causal_tracking", "meta_retrieval_awareness"],
            },
        )

    def nexus_snapshot_for_prompt(self, query: Optional[str] = None) -> SemanticAdapterResult:
        """Return compact prompt-ready NEXUS snapshot context."""
        try:
            snapshot = self.get_unified_nexus_snapshot(query)
            d = snapshot.to_dict()
            lines = [
                "WORDLIB NEXUS unified context snapshot (read-only):",
                f"- Query: {d.get('query')}",
                f"- Healthy: {d.get('health', {}).get('overall')}; sections={', '.join(d.get('summary', {}).get('sections_available', []))}",
                f"- Memory: cycles={d['summary']['memory'].get('cycles', 0)}, sampled events={d['summary']['memory'].get('events_sampled', 0)}.",
                f"- Code: modules={d['summary']['code'].get('modules', 0)}, classes={d['summary']['code'].get('classes', 0)}, functions={d['summary']['code'].get('functions', 0)}.",
                f"- Ontology matches: {d['summary']['ontology'].get('matches', 0)}.",
                f"- Causal placeholders: {len(d.get('causal_links', []))}; temporal placeholders: {len(d.get('temporal_links', []))}.",
                f"- Agent summary: {d['summary'].get('agent_summary')}",
            ]
            if d.get("warnings"):
                lines.append("- Warnings: " + "; ".join(str(w) for w in d["warnings"][:5]))
            lines.append("- Retrieval reasoning: " + "; ".join(d.get("retrieval_reasoning", [])[:4]))
            return self._result("nexus_snapshot_for_prompt", {"snapshot": d, "prompt_context": "\n".join(lines)}, d.get("warnings", []))
        except Exception as exc:
            return self._error("nexus_snapshot_for_prompt", exc)


    @staticmethod
    def _clamp_score(value: float) -> float:
        return max(0.0, min(1.0, round(float(value), 3)))

    def _score_snapshot_section(self, name: str, section: Dict[str, Any], query_terms: List[str]) -> Dict[str, Any]:
        """Return deterministic quality score + reasons for one NEXUS section."""
        score = 0.0
        reasons: List[str] = []
        weaknesses: List[str] = []
        data = section.get("data") if isinstance(section, dict) else {}
        data = data if isinstance(data, dict) else {}

        if section.get("ok"):
            score += 0.25
            reasons.append("section reports ok=True")
        else:
            weaknesses.append(f"{name} section is unhealthy or unavailable")

        if section.get("generated_at"):
            score += 0.10
        else:
            weaknesses.append(f"{name} section is missing generated_at timestamp")

        if not section.get("error"):
            score += 0.10
        else:
            weaknesses.append(f"{name} section error: {section.get('error')}")

        warning_count = len(section.get("warnings", []) or [])
        if warning_count == 0:
            score += 0.10
        elif warning_count <= 2:
            score += 0.04
            weaknesses.append(f"{name} section has {warning_count} warning(s)")
        else:
            weaknesses.append(f"{name} section has {warning_count} warning(s), which may weaken context quality")

        serialized = json.dumps(data, sort_keys=True, default=str).lower()
        query_hits = sum(1 for term in query_terms if term in serialized)
        if query_terms:
            coverage = query_hits / max(1, len(query_terms))
            score += min(0.20, 0.20 * coverage)
            if query_hits == 0:
                weaknesses.append(f"{name} section has no direct lexical match for the query terms")
        else:
            score += 0.08
            reasons.append("no query terms supplied; neutral query coverage applied")

        # Section-specific richness checks. These are intentionally transparent,
        # not ML-like, so Cloud can audit every score.
        if name == "memory":
            summary = data.get("summary", {}) if isinstance(data.get("summary", {}), dict) else {}
            cycles = int(summary.get("cycles", 0) or 0)
            events = int(summary.get("events_sampled", 0) or 0)
            matched = int(summary.get("matched_cycles", 0) or 0) + int(summary.get("matched_events", 0) or 0)
            if cycles or events:
                score += 0.18
                reasons.append(f"memory has cycles={cycles}, events_sampled={events}")
            else:
                weaknesses.append("memory section is sparse: no cycles or sampled events")
            if matched:
                score += 0.07
            elif query_terms:
                weaknesses.append("memory section contains no query-matched cycles/events")
        elif name == "code":
            summary = data.get("summary", {}) if isinstance(data.get("summary", {}), dict) else {}
            modules = int(summary.get("modules", 0) or 0)
            functions = int(summary.get("functions", 0) or 0)
            classes = int(summary.get("classes", 0) or 0)
            if modules and functions:
                score += 0.20
                reasons.append(f"code structure is populated: modules={modules}, functions={functions}, classes={classes}")
            else:
                weaknesses.append("code section is sparse: missing module/function coverage")
            matches = data.get("matches", {}) if isinstance(data.get("matches", {}), dict) else {}
            if any(matches.get(k) for k in ("modules", "classes", "functions", "call_sites")):
                score += 0.05
            elif query_terms:
                weaknesses.append("code section has no matched modules/classes/functions/call sites for this query")
        elif name == "ontology":
            matches = data.get("matches", [])
            if matches:
                score += 0.23
                reasons.append(f"ontology returned {len(matches)} local term match(es)")
            else:
                weaknesses.append("ontology section has no local term matches")
        elif name == "rag":
            if data:
                score += 0.12
            summary = data.get("summary", {}) if isinstance(data.get("summary", {}), dict) else {}
            entities = int(summary.get("entities", 0) or summary.get("entity_count", 0) or 0)
            evidence = int(summary.get("evidence", 0) or summary.get("evidence_count", 0) or 0)
            matches = data.get("matched_entities") or data.get("entities") or []
            if entities or evidence or matches:
                score += 0.13
                reasons.append("semantic/RAG graph contains structured context")
            else:
                weaknesses.append("RAG/semantic graph section is sparse or has no matched entities/evidence")

        final_score = self._clamp_score(score)
        if final_score < 0.55 and f"{name} section scored below promotion-quality threshold" not in weaknesses:
            weaknesses.append(f"{name} section scored below promotion-quality threshold")
        return {"score": final_score, "reasons": reasons, "weaknesses": weaknesses}

    def reflect_on_snapshot(self, snapshot: NexusSnapshot, query: Optional[str] = None) -> ReflectionResult:
        """
        Critique a NEXUS snapshot without mutating any WORDLIB state.

        This is the first lightweight self-critique layer. It judges context
        relevance, sparse sections, retrieval weaknesses, and suggested next
        retrieval steps using transparent deterministic heuristics only.
        """
        if not isinstance(snapshot, NexusSnapshot):
            raise TypeError("reflect_on_snapshot requires a NexusSnapshot")
        data = snapshot.to_dict()
        q = query if query is not None else data.get("query")
        query_terms = self._query_terms(q or "")
        generated_at = datetime.now(timezone.utc).isoformat()
        sections = data.get("sections", {}) if isinstance(data.get("sections", {}), dict) else {}
        required = ("memory", "code", "ontology", "rag")

        section_scores: Dict[str, float] = {}
        missing_or_weak: List[str] = []
        retrieval_weaknesses: List[str] = []
        scoring_details: Dict[str, Any] = {}

        for name in required:
            section = sections.get(name)
            if not isinstance(section, dict):
                section_scores[name] = 0.0
                missing_or_weak.append(name)
                retrieval_weaknesses.append(f"{name} section is missing from the NEXUS snapshot")
                scoring_details[name] = {"score": 0.0, "reasons": [], "weaknesses": ["missing section"]}
                continue
            scored = self._score_snapshot_section(name, section, query_terms)
            section_scores[name] = scored["score"]
            scoring_details[name] = scored
            if scored["score"] < 0.55:
                missing_or_weak.append(name)
            retrieval_weaknesses.extend(scored["weaknesses"])

        if data.get("read_only") is not True:
            retrieval_weaknesses.append("snapshot is not marked read-only")
        if not data.get("generated_at"):
            retrieval_weaknesses.append("snapshot is missing a top-level generated_at timestamp")
        if "causal_links" not in data or "temporal_links" not in data:
            retrieval_weaknesses.append("snapshot lacks causal/temporal placeholder fields")
        if not data.get("retrieval_reasoning"):
            retrieval_weaknesses.append("snapshot has no retrieval reasoning notes")

        base_scores = list(section_scores.values()) or [0.0]
        overall = sum(base_scores) / len(base_scores)
        if retrieval_weaknesses:
            overall -= min(0.12, 0.015 * len(retrieval_weaknesses))
        overall_score = self._clamp_score(overall)

        suggested: List[str] = []
        if "memory" in missing_or_weak:
            suggested.append("Review or seed recent gremlin_memory.json / ether_events.jsonl entries before relying on memory context.")
        if "code" in missing_or_weak:
            suggested.append("Run the AST code-structure hook with a narrower code query or inspect parse warnings for structural coverage gaps.")
        if "ontology" in missing_or_weak:
            suggested.append("Add or revise local ontology terms for this query if the concept should be part of WORDLIB vocabulary.")
        if "rag" in missing_or_weak:
            suggested.append("Ingest evidence-backed semantic facts for this topic before expecting strong RAG/graph context.")
        if query_terms and all(score < 0.70 for score in section_scores.values()):
            suggested.append("Broaden or rephrase the query because all sections show weak direct query coverage.")
        if not suggested:
            suggested.append("Snapshot quality is adequate; next improvement should be temporal/causal scaffolding, not a new storage engine.")

        strongest = max(section_scores, key=section_scores.get) if section_scores else "none"
        weakest = min(section_scores, key=section_scores.get) if section_scores else "none"
        critique_summary = (
            f"NEXUS reflection scored snapshot relevance at {overall_score:.2f}. "
            f"Strongest section: {strongest} ({section_scores.get(strongest, 0.0):.2f}); "
            f"weakest section: {weakest} ({section_scores.get(weakest, 0.0):.2f}). "
            f"Weak/missing sections: {', '.join(missing_or_weak) if missing_or_weak else 'none'}."
        )
        return ReflectionResult(
            overall_relevance_score=overall_score,
            section_scores=section_scores,
            missing_or_weak_sections=missing_or_weak,
            retrieval_weaknesses=retrieval_weaknesses,
            suggested_improvements=suggested,
            critique_summary=critique_summary,
            generated_at=generated_at,
            query=q,
            metadata={
                "snapshot_contract": data.get("contract"),
                "snapshot_generated_at": data.get("generated_at"),
                "query_terms": query_terms,
                "scoring_details": scoring_details,
                "read_only_verified": data.get("read_only") is True,
                "future_consumers": ["Cloud", "MotherEther", "Gremlin", "orchestrator"],
            },
        )

    def reflection_for_prompt(self, snapshot: NexusSnapshot, query: Optional[str] = None) -> SemanticAdapterResult:
        """Return compact prompt-ready reflection context over a NEXUS snapshot."""
        try:
            reflection = self.reflect_on_snapshot(snapshot, query=query)
            d = reflection.to_dict()
            lines = [
                "WORDLIB NEXUS reflection/self-critique (read-only):",
                f"- Query: {d.get('query')}",
                f"- Overall relevance score: {d.get('overall_relevance_score')}",
                "- Section scores: " + ", ".join(f"{k}={v}" for k, v in sorted(d.get("section_scores", {}).items())),
                "- Weak/missing sections: " + (", ".join(d.get("missing_or_weak_sections", [])) or "none"),
                "- Critique: " + d.get("critique_summary", ""),
            ]
            if d.get("retrieval_weaknesses"):
                lines.append("- Retrieval weaknesses: " + "; ".join(d["retrieval_weaknesses"][:5]))
            if d.get("suggested_improvements"):
                lines.append("- Suggested improvements: " + "; ".join(d["suggested_improvements"][:5]))
            return self._result("reflection_for_prompt", {"reflection": d, "prompt_context": "\n".join(lines)}, [])
        except Exception as exc:
            return self._error("reflection_for_prompt", exc)

    @staticmethod
    def _estimate_tokens(payload: Any) -> int:
        """Very small deterministic token estimate for pruning decisions."""
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return max(1, int(len(serialized) / 4))

    @staticmethod
    def _goal_terms(goal: str) -> List[str]:
        raw = (goal or "").lower().replace("_", " ").replace("-", " ")
        stop = {"the", "and", "for", "with", "from", "this", "that", "into", "wordlib", "nexus"}
        return [w for w in raw.split() if len(w) >= 3 and w not in stop][:18]

    def _run_quality_audit(self, text: str, strictness: str) -> Dict[str, Any]:
        """Run v30-style honest surface heuristics; never claim truth detection."""
        threshold = 0.72 if strictness == "production" else 0.62 if strictness == "research" else 0.52
        if OutputQualityChecker is not None:
            result = OutputQualityChecker(threshold=threshold).check(text)
            data = result.as_dict()
            data["threshold"] = threshold
            data["source"] = "reasoning.output_quality.OutputQualityChecker"
            return data
        lower = text.lower()
        flags: List[str] = []
        overconf = sum(lower.count(x) for x in ("guaranteed", "100%", "always works", "never fails", "perfect"))
        hedges = sum(lower.count(x) for x in ("maybe", "probably", "i think", "possibly"))
        if overconf:
            flags.append(f"{overconf} overconfidence marker(s)")
        if hedges > 3:
            flags.append(f"{hedges} hedge marker(s)")
        score = self._clamp_score(1.0 - 0.12 * overconf - 0.04 * max(0, hedges - 3))
        return {
            "score": score,
            "passed": score >= threshold,
            "flags": flags,
            "breakdown": {"overconfidence": overconf, "hedges": hedges},
            "threshold": threshold,
            "source": "semantic_adapter.fallback_surface_heuristics",
            "note": "Surface heuristic only; not truth verification.",
        }

    def _centralization_status(self) -> Dict[str, Any]:
        """Reflect v30 core.paths centralization health without writing."""
        status: Dict[str, Any] = {
            "single_source_of_truth": "core.paths",
            "migration_report_available": migration_report is not None,
            "health_report_available": health_report is not None,
            "pending_count": None,
            "centralized": None,
            "overall_health": None,
            "warnings": [],
        }
        if migration_report is not None:
            try:
                mig = migration_report()
                status["pending_count"] = mig.get("pending_count")
                status["migrated_count"] = mig.get("migrated_count")
                status["centralized"] = mig.get("pending_count", 1) == 0
                if mig.get("pending_count", 0):
                    status["warnings"].append(f"{mig.get('pending_count')} path centralization item(s) still pending")
            except Exception as exc:
                status["warnings"].append(f"migration_report failed: {type(exc).__name__}: {exc}")
        if health_report is not None:
            try:
                health = health_report()
                status["overall_health"] = health.get("overall")
                status["filesystem"] = health.get("filesystem", {})
                status["critical_files"] = health.get("critical_files", {})
                if health.get("overall") != "OK":
                    status["warnings"].append(f"core.paths health_report overall={health.get('overall')}")
            except Exception as exc:
                status["warnings"].append(f"health_report failed: {type(exc).__name__}: {exc}")
        return status

    def _curate_snapshot_section(self, name: str, section: Dict[str, Any], goal_terms: List[str], strictness: str) -> Dict[str, Any]:
        """Prune one snapshot section into high-signal, Cloud-consumable context."""
        data = section.get("data", {}) if isinstance(section, dict) else {}
        data = data if isinstance(data, dict) else {}
        serialized = json.dumps(data, sort_keys=True, default=str).lower()
        hit_terms = [term for term in goal_terms if term in serialized]
        base = {
            "ok": bool(section.get("ok")),
            "operation": section.get("operation"),
            "generated_at": section.get("generated_at"),
            "warnings": list(section.get("warnings", []) or [])[:6],
            "error": section.get("error"),
            "goal_term_hits": hit_terms,
            "selection_priority": 0.0,
            "selected_reason": "",
        }
        priority = 0.35 if base["ok"] else 0.0
        priority += min(0.25, 0.05 * len(hit_terms))
        if not base["error"]:
            priority += 0.10
        if not base["warnings"]:
            priority += 0.10

        if name == "memory":
            summary = data.get("summary", {}) if isinstance(data.get("summary", {}), dict) else {}
            base["summary"] = {
                "cycles": summary.get("cycles", 0),
                "events_sampled": summary.get("events_sampled", 0),
                "matched_cycles": summary.get("matched_cycles", 0),
                "matched_events": summary.get("matched_events", 0),
            }
            items = data.get("matched_items") or data.get("recent_matches") or []
            base["high_signal_items"] = items[:5] if isinstance(items, list) else []
            base["selected_reason"] = "Selected for historical Gremlin/EventLog context and troubleshooting memory."
            priority += 0.10 if (summary.get("matched_cycles", 0) or summary.get("matched_events", 0)) else 0.0
        elif name == "code":
            summary = data.get("summary", {}) if isinstance(data.get("summary", {}), dict) else {}
            base["summary"] = {
                "modules": summary.get("modules", 0),
                "classes": summary.get("classes", 0),
                "functions": summary.get("functions", 0),
                "imports": summary.get("imports", 0),
            }
            items = data.get("matches") or data.get("items") or []
            base["high_signal_items"] = items[:8] if isinstance(items, list) else []
            base["selected_reason"] = "Selected for AST module/class/function/import structure and safe code navigation."
            priority += 0.12 if summary.get("functions", 0) else 0.0
        elif name == "ontology":
            matches = data.get("matches", []) if isinstance(data.get("matches", []), list) else []
            base["summary"] = {"matches": len(matches), "schema": data.get("schema") or data.get("contract")}
            base["high_signal_items"] = matches[:8]
            base["selected_reason"] = "Selected for WORDLIB-local vocabulary, constraints, and integration semantics."
            priority += 0.12 if matches else 0.0
        elif name == "rag":
            base["summary"] = data.get("summary") or data.get("graph_summary") or data.get("semantic_context", {}).get("summary", {})
            items = data.get("matched_entities") or data.get("entities") or data.get("related_entities") or []
            base["high_signal_items"] = items[:8] if isinstance(items, list) else []
            base["prompt_context_excerpt"] = str(data.get("prompt_context", ""))[:1000]
            base["selected_reason"] = "Selected for semantic graph/RAG context and evidence-backed entity relationships."
            priority += 0.10 if base.get("summary") else 0.0
        else:
            base["summary"] = data.get("summary", {})
            base["high_signal_items"] = []
            base["selected_reason"] = "Selected as a NEXUS source section."

        if strictness == "production" and base["warnings"]:
            priority -= 0.04
        base["selection_priority"] = self._clamp_score(priority)
        return base

    def build_intelligent_context(self, goal: str, max_tokens: int = 12000,
                                  strictness: str = "production") -> IntelligentContextPackage:
        """
        Build a guarded, goal-aware, read-only NEXUS context package.

        This is the bridge from aggregator-style snapshots to production-style
        central intelligence: context is curated, quality-audited, health-checked,
        and mutation proposals remain proposals only.
        """
        if strictness not in {"production", "research", "creative"}:
            raise ValueError("strictness must be one of: production, research, creative")
        if not goal or not str(goal).strip():
            raise ValueError("goal is required for build_intelligent_context")
        max_tokens = max(1200, int(max_tokens or 12000))
        generated_at = datetime.now(timezone.utc).isoformat()
        goal = str(goal).strip()
        goal_terms = self._goal_terms(goal)

        snapshot = self.get_unified_nexus_snapshot(goal)
        reflection = self.reflect_on_snapshot(snapshot, query=goal)
        snapshot_data = snapshot.to_dict()
        reflection_data = reflection.to_dict()
        sections = snapshot_data.get("sections", {})
        curated_sections = {
            name: self._curate_snapshot_section(name, section, goal_terms, strictness)
            for name, section in sections.items()
        }
        ranked_sections = sorted(
            curated_sections.items(),
            key=lambda item: item[1].get("selection_priority", 0.0),
            reverse=True,
        )

        coverage_gaps: List[str] = []
        for name, score in reflection_data.get("section_scores", {}).items():
            if float(score) < 0.55:
                coverage_gaps.append(f"{name} section scored below usable threshold ({score})")
        if not goal_terms:
            coverage_gaps.append("goal produced no strong query terms for pruning")

        centralization = self._centralization_status()
        quality_text = "\n".join([
            f"Goal: {goal}",
            snapshot_data.get("summary", {}).get("agent_summary", ""),
            reflection_data.get("critique_summary", ""),
            " ".join(snapshot_data.get("retrieval_reasoning", [])),
        ])
        quality_audit = self._run_quality_audit(quality_text, strictness)
        quality_flags = list(quality_audit.get("flags", []))
        quality_flags.extend(reflection_data.get("retrieval_weaknesses", [])[:6])

        warnings: List[str] = []
        warnings.extend(snapshot_data.get("warnings", [])[:8])
        warnings.extend(reflection_data.get("retrieval_weaknesses", [])[:8])
        warnings.extend(centralization.get("warnings", [])[:6])
        if not quality_audit.get("passed", False):
            warnings.append("quality audit did not pass v30 surface-heuristic threshold")

        curated_context = {
            "goal": goal,
            "mode": strictness,
            "source_of_truth": "SemanticAdapter.build_intelligent_context",
            "ranked_sections": [name for name, _ in ranked_sections],
            "sections": {name: section for name, section in ranked_sections},
            "snapshot_summary": snapshot_data.get("summary", {}),
            "reflection_summary": {
                "overall_relevance_score": reflection_data.get("overall_relevance_score"),
                "weak_sections": reflection_data.get("missing_or_weak_sections", []),
                "suggested_improvements": reflection_data.get("suggested_improvements", [])[:8],
            },
        }
        token_estimate = self._estimate_tokens(curated_context)
        if token_estimate > max_tokens:
            # Last-resort deterministic compaction. Keep summaries and priorities,
            # trim item payloads without mutating any backing data source.
            for section in curated_context["sections"].values():
                items = section.get("high_signal_items", [])
                if isinstance(items, list) and len(items) > 3:
                    section["high_signal_items"] = items[:3]
                if "prompt_context_excerpt" in section:
                    section["prompt_context_excerpt"] = str(section["prompt_context_excerpt"])[:500]
            warnings.append("curated context compacted to respect max_tokens budget")
            token_estimate = self._estimate_tokens(curated_context)

        section_scores = reflection_data.get("section_scores", {})
        centralization_ok = centralization.get("centralized") is True or centralization.get("pending_count") == 0
        health_score_parts = [float(quality_audit.get("score", 0.0)), float(reflection_data.get("overall_relevance_score", 0.0))]
        if centralization_ok:
            health_score_parts.append(1.0)
        elif centralization.get("pending_count") is not None:
            health_score_parts.append(0.65)
        overall_quality_score = self._clamp_score(sum(health_score_parts) / max(1, len(health_score_parts)))

        context_health = {
            "mode": strictness,
            "freshness": {
                "snapshot_generated_at": snapshot_data.get("generated_at"),
                "reflection_generated_at": reflection_data.get("generated_at"),
                "section_timestamps": {name: sec.get("generated_at") for name, sec in sections.items()},
            },
            "coverage": {
                "goal_terms": goal_terms,
                "section_scores": section_scores,
                "coverage_gaps": coverage_gaps,
                "ranked_sections": curated_context["ranked_sections"],
            },
            "quality_flags": quality_flags,
            "centralization_status": centralization,
            "safety_contract": {
                "read_only": True,
                "actual_writes": False,
                "mutation_policy": "propose_only_self_editor_guarded_future",
                "proposed_mutations_schema": "wordlib.nexus.proposed_mutation.v1",
            },
        }

        proposed_mutations: List[Dict[str, Any]] = []
        for weakness in reflection_data.get("missing_or_weak_sections", [])[:4]:
            proposed_mutations.append({
                "schema": "wordlib.nexus.proposed_mutation.v1",
                "type": "context_quality_review",
                "target": weakness,
                "reason": "Reflection marked this section as weak; Cloud/SelfEditor may later decide whether a guarded change is appropriate.",
                "guard_required": "SelfEditor whitelist + backup + syntax validation + deploy_check",
                "read_only_now": True,
            })
        if not centralization_ok and centralization.get("pending_count"):
            proposed_mutations.append({
                "schema": "wordlib.nexus.proposed_mutation.v1",
                "type": "path_centralization_review",
                "target": "core.paths migration_report pending_migration",
                "reason": "v30 single-source-of-truth health reports pending path migration debt.",
                "guard_required": "SelfEditor whitelist + backup + syntax validation + deploy_check",
                "read_only_now": True,
            })

        selection_reasoning = (
            "NEXUS selected context through SemanticAdapter as the single public boundary. "
            f"Goal terms {goal_terms or ['<none>']} were matched against memory, code, ontology, and RAG sections. "
            "Sections were ranked by health, direct goal-term coverage, warnings, errors, and section-specific richness. "
            "v30-style safeguards were applied: core.paths centralization was checked, quality was audited with honest surface heuristics, "
            "and every mutation is represented only as a proposed mutation requiring future SelfEditor guards."
        )

        return IntelligentContextPackage(
            goal=goal,
            curated_context=curated_context,
            selection_reasoning=selection_reasoning,
            context_health=context_health,
            quality_audit=quality_audit,
            overall_quality_score=overall_quality_score,
            token_estimate=token_estimate,
            warnings=warnings,
            proposed_mutations=proposed_mutations,
            generated_at=generated_at,
            strictness=strictness,
            max_tokens=max_tokens,
            metadata={
                "snapshot_contract": snapshot_data.get("contract"),
                "reflection_contract": reflection_data.get("contract"),
                "adapter_contract": self.CONTRACT_VERSION,
                "bridge_principles": [
                    "single_source_of_truth_via_semantic_adapter",
                    "core_paths_centralization_awareness",
                    "self_editor_propose_only_safety_contract",
                    "reasoning_guard_style_surface_quality_heuristics",
                    "layered_health_report_shape",
                ],
                "heavy_dependencies": [],
                "future_layers": ["temporal_causal_candidates", "meta_retrieval_awareness", "guarded_self_reorganization_proposals"],
            },
        )

    @staticmethod
    def _flatten_terms_from_payload(payload: Any, limit: int = 40) -> List[str]:
        """Extract deterministic lowercase terms from nested payloads for weak matching."""
        text = json.dumps(payload, sort_keys=True, default=str).lower()
        cleaned = []
        token = []
        for ch in text:
            if ch.isalnum() or ch in {"_", ".", "/", "-"}:
                token.append(ch)
            else:
                if token:
                    cleaned.append("".join(token))
                    token = []
        if token:
            cleaned.append("".join(token))
        stop = {"null", "true", "false", "none", "the", "and", "for", "with", "from", "this", "that"}
        out: List[str] = []
        for item in cleaned:
            if len(item) >= 4 and item not in stop and item not in out:
                out.append(item)
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _parse_iso_timestamp(value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            text = str(value)
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None

    @staticmethod
    def _stable_short_id(prefix: str, payload: Any) -> str:
        """Build a deterministic short identifier for proposal-only records."""
        raw = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}_{digest}"

    @staticmethod
    def _source_sections_from_evidence(source_evidence: List[Dict[str, Any]]) -> List[str]:
        sections: List[str] = []
        for item in source_evidence:
            if isinstance(item, dict):
                section = str(item.get("section") or item.get("source") or "unknown")
                if section not in sections:
                    sections.append(section)
        return sections

    def _candidate_evidence_path(self, relation_type: str, source_evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create a RAG/Cloud-readable path through the evidence supporting a candidate."""
        path: List[Dict[str, Any]] = []
        for idx, evidence in enumerate(source_evidence[:6], start=1):
            if not isinstance(evidence, dict):
                continue
            label_bits = [str(evidence.get("section", "unknown")), str(evidence.get("kind", "evidence"))]
            if evidence.get("event"):
                label_bits.append(str(evidence.get("event")))
            if evidence.get("time"):
                label_bits.append(str(evidence.get("time")))
            if evidence.get("target"):
                label_bits.append(str(evidence.get("target")))
            path.append({
                "step": idx,
                "node_type": "evidence",
                "section": evidence.get("section", "unknown"),
                "kind": evidence.get("kind", "evidence"),
                "label": " -> ".join(label_bits),
            })
        path.append({
            "step": len(path) + 1,
            "node_type": "candidate_relation",
            "relation_type": relation_type,
            "label": f"proposal-only {relation_type} relation",
        })
        path.append({
            "step": len(path) + 1,
            "node_type": "guard",
            "label": "SelfEditor-style guarded review required before any write or fact promotion",
        })
        return path

    @staticmethod
    def _explain_candidate_path(label: str, evidence_path: List[Dict[str, Any]]) -> str:
        fragments = [str(step.get("label")) for step in evidence_path if step.get("label")]
        if not fragments:
            return f"{label}: no usable path evidence was found; keep as low-confidence candidate."
        return f"{label}: " + " => ".join(fragments)

    def _make_causal_candidate(self, relation_type: str, label: str, source_evidence: List[Dict[str, Any]],
                               confidence: float, explanation: str, warnings: Optional[List[str]] = None,
                               invalidates: Optional[List[str]] = None,
                               proposed_next_check: Optional[str] = None) -> Dict[str, Any]:
        """Build one guarded, proposal-only causal/temporal candidate with a path trace."""
        confidence = self._clamp_score(confidence)
        source_evidence = list(source_evidence)
        affected_sections = self._source_sections_from_evidence(source_evidence)
        evidence_path = self._candidate_evidence_path(relation_type, source_evidence)
        candidate_seed = {
            "type": relation_type,
            "label": label,
            "evidence": source_evidence,
            "confidence": confidence,
        }
        candidate_id = self._stable_short_id("CTP", candidate_seed)
        path_explanation = self._explain_candidate_path(label, evidence_path)
        return {
            "id": candidate_id,
            "type": relation_type,
            "status": "candidate",
            "label": label,
            "confidence": confidence,
            "confidence_reason": explanation,
            "source_evidence": source_evidence,
            "affected_sections": affected_sections,
            "invalidates": list(invalidates or []),
            "evidence_path": evidence_path,
            "path_explanation": path_explanation,
            "path_score": confidence,
            "proposed_next_check": proposed_next_check or "Review source evidence, refresh NEXUS snapshot, then pass any mutation through SelfEditor guard rails.",
            "self_reorganization_signal": {
                "eligible": confidence >= 0.68 and relation_type in {"causal", "invalidation", "contradiction"},
                "mode": "proposal_only",
                "reason": "Candidate is strong enough to inform a future reorganization proposal, but not strong enough to mutate or persist as fact.",
            },
            "warnings": list(warnings or []),
            "guard_required_before_fact": "Guarded evidence review + deploy_check + future causal store adapter + SelfEditor whitelist/backup/syntax validation; never auto-promote from candidate to fact.",
        }

    def _candidate_path_health(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Score whether a candidate has enough path evidence to be useful for Cloud review."""
        evidence_path = candidate.get("evidence_path", []) if isinstance(candidate.get("evidence_path", []), list) else []
        source_evidence = candidate.get("source_evidence", []) if isinstance(candidate.get("source_evidence", []), list) else []
        affected_sections = candidate.get("affected_sections", []) if isinstance(candidate.get("affected_sections", []), list) else []
        confidence = float(candidate.get("confidence", 0.0) or 0.0)
        score = confidence
        weak_points: List[str] = []
        if len(source_evidence) < 2:
            score -= 0.12
            weak_points.append("candidate has fewer than two source evidence entries")
        if len(affected_sections) < 2:
            score -= 0.08
            weak_points.append("candidate touches only one source section, so cross-source support is weak")
        if len(evidence_path) < 3:
            score -= 0.08
            weak_points.append("candidate evidence path is short")
        if candidate.get("type") in {"invalidation", "contradiction"} and not candidate.get("invalidates"):
            score -= 0.10
            weak_points.append("invalidation/contradiction candidate does not name what it invalidates")
        if not candidate.get("proposed_next_check"):
            score -= 0.05
            weak_points.append("candidate lacks a next review check")
        score = self._clamp_score(score)
        if score >= 0.72:
            grade = "strong_review_candidate"
        elif score >= 0.55:
            grade = "review_candidate"
        else:
            grade = "weak_candidate"
        return {
            "score": score,
            "grade": grade,
            "weak_points": weak_points,
            "evidence_count": len(source_evidence),
            "path_steps": len(evidence_path),
            "section_count": len(affected_sections),
        }

    def _build_causal_pathfinder_routes(self, candidates: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
        """Expose candidate routes as Cloud-readable pathfinder entries."""
        routes: List[Dict[str, Any]] = []
        for candidate in candidates[: max(0, int(limit))]:
            health = self._candidate_path_health(candidate)
            route_id = self._stable_short_id("CTR", {"candidate_id": candidate.get("id"), "path": candidate.get("evidence_path", [])})
            routes.append({
                "route_id": route_id,
                "candidate_id": candidate.get("id"),
                "type": candidate.get("type"),
                "confidence": candidate.get("confidence"),
                "route_health_score": health["score"],
                "route_grade": health["grade"],
                "weak_points": health["weak_points"],
                "evidence_count": health["evidence_count"],
                "path_steps": health["path_steps"],
                "affected_sections": candidate.get("affected_sections", []),
                "path": candidate.get("evidence_path", []),
                "path_explanation": candidate.get("path_explanation"),
                "next_review_step": candidate.get("proposed_next_check"),
                "merge_note": "Merge-safe: route is derived data only; no source files, memory, ontology, or graph facts are modified.",
                "guard_chain": ["candidate-only", "Cloud review", "SelfEditor whitelist", "mandatory backup", "syntax validation", "deploy_check"],
                "guard_required_before_fact": candidate.get("guard_required_before_fact"),
            })
        return routes

    def _build_reorganization_pathways(self, candidates: List[Dict[str, Any]], routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group candidates into future self-reorganization pathways without enabling mutation."""
        pathways: List[Dict[str, Any]] = []
        strong_ids = {r.get("candidate_id") for r in routes if float(r.get("route_health_score", 0.0) or 0.0) >= 0.68}
        invalidation_ids = [c.get("id") for c in candidates if c.get("type") == "invalidation"]
        contradiction_ids = [c.get("id") for c in candidates if c.get("type") == "contradiction"]
        causal_ids = [c.get("id") for c in candidates if c.get("type") == "causal"]
        temporal_ids = [c.get("id") for c in candidates if c.get("type") == "temporal"]
        if invalidation_ids or contradiction_ids:
            pathways.append({
                "pathway_id": self._stable_short_id("REORG_PATH", {"kind": "assumption_review", "ids": invalidation_ids + contradiction_ids}),
                "name": "assumption_review",
                "purpose": "Review assumptions that may be outdated, contradicted, or invalidated by later evidence.",
                "candidate_ids": invalidation_ids + contradiction_ids,
                "strong_candidate_ids": [cid for cid in invalidation_ids + contradiction_ids if cid in strong_ids],
                "allowed_now": "review_only",
                "forbidden_now": ["write memory", "edit code", "promote causal fact", "rewrite ontology"],
                "next_gate": "meta-retrieval awareness should request fresher evidence before any reorganization proposal.",
            })
        if causal_ids:
            pathways.append({
                "pathway_id": self._stable_short_id("REORG_PATH", {"kind": "quality_repair", "ids": causal_ids}),
                "name": "quality_repair",
                "purpose": "Use causal quality signals to decide which context section should be refreshed or audited next.",
                "candidate_ids": causal_ids,
                "strong_candidate_ids": [cid for cid in causal_ids if cid in strong_ids],
                "allowed_now": "planning_only",
                "forbidden_now": ["auto-ingest", "auto-refactor", "auto-run SelfEditor"],
                "next_gate": "Cloud reviews proposed next checks, then a future guarded plan can be drafted.",
            })
        if temporal_ids:
            pathways.append({
                "pathway_id": self._stable_short_id("REORG_PATH", {"kind": "timeline_review", "ids": temporal_ids}),
                "name": "timeline_review",
                "purpose": "Preserve ordering clues so later causal storage can distinguish sequence from causation.",
                "candidate_ids": temporal_ids,
                "strong_candidate_ids": [cid for cid in temporal_ids if cid in strong_ids],
                "allowed_now": "timeline_annotation_only",
                "forbidden_now": ["claim causality from order alone"],
                "next_gate": "Require independent evidence before any temporal candidate becomes causal.",
            })
        return pathways

    def _build_causal_merge_guidance(self, candidates: List[Dict[str, Any]], routes: List[Dict[str, Any]],
                                     warnings: List[str], bridge: Dict[str, Any]) -> Dict[str, Any]:
        """Tell Cloud exactly how merge-safe this causal layer is."""
        route_scores = [float(r.get("route_health_score", 0.0) or 0.0) for r in routes]
        avg_route_score = sum(route_scores) / len(route_scores) if route_scores else 0.0
        strong_count = len([s for s in route_scores if s >= 0.68])
        readiness_score = self._clamp_score(0.45 + (0.25 if candidates else 0.0) + min(0.2, strong_count * 0.04) + min(0.1, avg_route_score * 0.1) - min(0.2, len(warnings) * 0.03))
        safe_to_merge = readiness_score >= 0.62 and bridge.get("can_execute_reorganization") is False
        return {
            "safe_to_merge": bool(safe_to_merge),
            "readiness_score": readiness_score,
            "merge_mode": "surgical_single_surface_patch",
            "minimal_touch_files": ["src/semantic_adapter.py", "deploy_check.py", "main.py", "tests/test_causal_temporal_proposals.py"],
            "no_split_required": True,
            "new_dependencies": [],
            "public_contracts": ["wordlib.nexus_causal_temporal.v1"],
            "merge_blockers": list(warnings[:6]),
            "cloud_review_checklist": [
                "Confirm candidates remain status=candidate",
                "Confirm can_execute_reorganization is false",
                "Run python deploy_check.py --json",
                "Run pytest -q and python tests/run_tests.py",
                "Review pathfinder_routes before trusting self-reorganization suggestions",
            ],
            "next_runs": [
                "Add meta-retrieval awareness over why routes were selected/rejected",
                "Add a proposal-only reorganization plan object that consumes pathfinder routes",
                "Only then consider SelfEditor guard integration; no direct mutation",
            ],
        }

    def _build_causal_scaffolding_entry(self, query: str, candidates: List[Dict[str, Any]],
                                        type_counts: Dict[str, int], warnings: List[str]) -> Dict[str, Any]:
        """One stable entry point Cloud can use to inspect this scaffolding layer."""
        strong = [c for c in candidates if float(c.get("confidence", 0.0)) >= 0.68]
        blockers: List[str] = []
        if not strong:
            blockers.append("no strong causal/invalidation/contradiction candidates yet")
        if warnings:
            blockers.append("warnings must be reviewed before any future promotion")
        readiness_score = self._clamp_score(0.50 + min(0.25, len(strong) * 0.05) + (0.10 if candidates else 0.0) - min(0.20, len(warnings) * 0.03))
        return {
            "entry_id": self._stable_short_id("CTS_ENTRY", {"query": query, "types": type_counts, "count": len(candidates)}),
            "goal": query,
            "source_of_truth": "SemanticAdapter -> IntelligentContextPackage -> NexusSnapshot/Reflection",
            "upstream_contracts": [
                "wordlib.nexus_snapshot.v1",
                "wordlib.nexus_reflection.v1",
                "wordlib.nexus_intelligent_context.v1",
            ],
            "read_only": True,
            "candidate_count": len(candidates),
            "candidate_type_counts": dict(type_counts),
            "pathfinder_summary": f"{len(candidates)} proposal-only candidate route(s), {len(strong)} strong enough for future reorganization review.",
            "scaffolding_readiness_score": readiness_score,
            "merge_surface": {
                "merge_friendly": True,
                "reason": "No file split, no dependency addition, no storage mutation; existing adapter/deploy/main/test surfaces only.",
                "expected_touch_files": ["src/semantic_adapter.py", "deploy_check.py", "main.py", "tests/test_causal_temporal_proposals.py"],
            },
            "self_reorganization_readiness": {
                "ready_for_guarded_proposal_planning": bool(strong),
                "ready_for_mutation": False,
                "blockers": blockers,
            },
            "guard_contract": {
                "policy": "propose_only",
                "future_execution_requires": ["SelfEditor whitelist", "mandatory backup", "syntax validation", "deploy_check", "human/Cloud review"],
            },
        }

    def propose_causal_temporal_links(
        self,
        snapshot: NexusSnapshot,
        reflection: Optional[ReflectionResult] = None,
        max_candidates: int = 12,
    ) -> CausalTemporalProposal:
        """
        Propose read-only temporal/causal candidate links over NEXUS context.

        This consumes the IntelligentContextPackage as the guarded context surface,
        then uses the supplied snapshot/reflection as evidence. It does not write,
        persist, ingest, mutate graph facts, or declare candidates as truth.
        """
        if not isinstance(snapshot, NexusSnapshot):
            raise TypeError("snapshot must be a NexusSnapshot")
        if reflection is not None and not isinstance(reflection, ReflectionResult):
            raise TypeError("reflection must be a ReflectionResult when provided")
        max_candidates = max(1, min(64, int(max_candidates or 12)))
        snapshot_data = snapshot.to_dict()
        query = snapshot_data.get("query") or "WORDLIB NEXUS causal temporal scaffolding"
        if reflection is None:
            reflection = self.reflect_on_snapshot(snapshot, query=query)
        reflection_data = reflection.to_dict()
        package = self.build_intelligent_context(str(query), max_tokens=8000, strictness="production")
        package_data = package.to_dict()
        generated_at = datetime.now(timezone.utc).isoformat()
        candidates: List[Dict[str, Any]] = []
        warnings: List[str] = []

        sections = snapshot_data.get("sections", {}) if isinstance(snapshot_data.get("sections", {}), dict) else {}
        memory = sections.get("memory", {}) if isinstance(sections.get("memory", {}), dict) else {}
        code = sections.get("code", {}) if isinstance(sections.get("code", {}), dict) else {}
        rag = sections.get("rag", {}) if isinstance(sections.get("rag", {}), dict) else {}
        ontology = sections.get("ontology", {}) if isinstance(sections.get("ontology", {}), dict) else {}

        if snapshot_data.get("read_only") is not True or package_data.get("read_only") is not True:
            warnings.append("source snapshot or intelligent context package is not explicitly read-only")
        for name, section in sections.items():
            if isinstance(section, dict) and section.get("ok") is not True:
                warnings.append(f"{name} section is unhealthy; causal candidates using it should be treated as low confidence")

        memory_data = memory.get("data", {}) if isinstance(memory.get("data", {}), dict) else {}
        matches = memory_data.get("matches", {}) if isinstance(memory_data.get("matches", {}), dict) else {}
        events = matches.get("events", []) if isinstance(matches.get("events", []), list) else []
        cycles = matches.get("cycles", []) if isinstance(matches.get("cycles", []), list) else []
        event_markers: List[Dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            payload = event.get("payload", {}) if isinstance(event.get("payload", {}), dict) else {}
            event_markers.append({
                "kind": "event",
                "time": event.get("time"),
                "parsed_time": self._parse_iso_timestamp(event.get("time")),
                "event": event.get("event") or event.get("type") or "unknown_event",
                "target": payload.get("target") or payload.get("file") or payload.get("path"),
                "payload": payload,
            })
        cycle_markers: List[Dict[str, Any]] = []
        for cycle in cycles:
            if not isinstance(cycle, dict):
                continue
            cycle_markers.append({
                "kind": "cycle",
                "time": cycle.get("time"),
                "parsed_time": self._parse_iso_timestamp(cycle.get("time")),
                "quip": cycle.get("quip"),
                "applied": cycle.get("applied"),
                "theater_mode": cycle.get("theater_mode"),
                "weaknesses": cycle.get("weaknesses", []),
                "proposals": cycle.get("proposals", []),
            })
        ordered_events = sorted([e for e in event_markers if e.get("parsed_time")], key=lambda e: e["parsed_time"])
        if len(ordered_events) >= 2:
            for left, right in zip(ordered_events, ordered_events[1:]):
                delta = (right["parsed_time"] - left["parsed_time"]).total_seconds()
                if delta < 0:
                    continue
                relation_type = "temporal"
                confidence = 0.62
                if any(word in str(left.get("event", "")).lower() + str(right.get("event", "")).lower() for word in ("deploy", "reject", "fix", "heal")):
                    confidence += 0.13
                candidates.append(self._make_causal_candidate(
                    relation_type,
                    f"{left.get('event')} preceded {right.get('event')}",
                    [
                        {"section": "memory", "kind": "event", "time": left.get("time"), "event": left.get("event"), "target": left.get("target")},
                        {"section": "memory", "kind": "event", "time": right.get("time"), "event": right.get("event"), "target": right.get("target")},
                    ],
                    confidence,
                    "Timestamp ordering from memory/event context supports a temporal candidate; deploy/reject/fix terms raise confidence but do not prove causality.",
                    proposed_next_check="Compare the two memory events against code/RAG sections and verify whether the later event changed the earlier assumption.",
                ))
                if len(candidates) >= max_candidates:
                    break
        elif not ordered_events:
            warnings.append("memory section has no timestamped events, so temporal ordering is weak")

        rejected_events = [e for e in event_markers if "reject" in str(e.get("event", "")).lower()]
        deployed_events = [e for e in event_markers if "deploy" in str(e.get("event", "")).lower()]
        for rejected in rejected_events[:3]:
            candidates.append(self._make_causal_candidate(
                "invalidation",
                f"{rejected.get('event')} may invalidate an earlier proposed change or assumption",
                [{"section": "memory", "kind": "event", "time": rejected.get("time"), "event": rejected.get("event"), "payload": rejected.get("payload", {})}],
                0.72,
                "A rejection event is a strong candidate signal that a prior proposal/assumption did not satisfy safety or quality gates.",
                invalidates=["prior unvalidated proposal", "unsafe assumption before rejection event"],
                proposed_next_check="Find the rejected proposal, inspect deploy_check output, and only create a guarded mutation proposal if evidence agrees.",
            ))
        for deployed in deployed_events[:3]:
            target = str(deployed.get("target") or "unknown target")
            code_terms = set(self._flatten_terms_from_payload(code.get("data", {}), limit=120))
            target_terms = set(self._flatten_terms_from_payload(target, limit=12))
            overlap = sorted(code_terms.intersection(target_terms))[:8]
            conf = 0.60 + (0.10 if overlap else 0.0)
            candidates.append(self._make_causal_candidate(
                "causal",
                f"{deployed.get('event')} may explain later context around {target}",
                [
                    {"section": "memory", "kind": "event", "time": deployed.get("time"), "event": deployed.get("event"), "target": target},
                    {"section": "code", "kind": "structure_match", "overlap_terms": overlap},
                ],
                conf,
                "Deployment-style memory event plus code-context overlap suggests a candidate cause/effect path; overlap is lexical and must be reviewed before becoming fact.",
                [] if overlap else ["no direct code-structure overlap found for deployed target"],
                proposed_next_check="Trace the deployed target through code structure and deploy logs before promoting any cause/effect claim.",
            ))

        weak_sections = reflection_data.get("missing_or_weak_sections", []) if isinstance(reflection_data.get("missing_or_weak_sections", []), list) else []
        retrieval_weaknesses = reflection_data.get("retrieval_weaknesses", []) if isinstance(reflection_data.get("retrieval_weaknesses", []), list) else []
        suggestions = reflection_data.get("suggested_improvements", []) if isinstance(reflection_data.get("suggested_improvements", []), list) else []
        for weakness in weak_sections[:4]:
            candidates.append(self._make_causal_candidate(
                "causal",
                f"weak {weakness} section caused a context-improvement proposal",
                [
                    {"section": "reflection", "kind": "weak_section", "value": weakness},
                    {"section": "reflection", "kind": "suggested_improvements", "items": suggestions[:3]},
                ],
                0.70,
                "Reflection explicitly marked this section weak and produced improvement guidance; this is a causal candidate for future retrieval planning.",
                invalidates=[f"unqualified trust in {weakness} section"],
                proposed_next_check="Refresh or enrich the weak section, then rerun snapshot and reflection before planning reorganization.",
            ))
        for weakness in retrieval_weaknesses[:4]:
            relation_type = "contradiction" if "contradict" in str(weakness).lower() else "causal"
            candidates.append(self._make_causal_candidate(
                relation_type,
                "reflection weakness affects intelligent context reliability",
                [
                    {"section": "reflection", "kind": "retrieval_weakness", "value": weakness},
                    {"section": "intelligent_context", "kind": "quality_audit", "score": package_data.get("overall_quality_score")},
                ],
                0.66,
                "Reflection weakness and intelligent-context quality audit are linked as proposal-only context quality signals.",
                invalidates=["unqualified intelligent-context confidence"],
                proposed_next_check="Use quality-audit details to decide whether more evidence, code context, or memory events are needed.",
            ))

        centralization = package_data.get("context_health", {}).get("centralization_status", {}) if isinstance(package_data.get("context_health", {}), dict) else {}
        if centralization.get("pending_count"):
            candidates.append(self._make_causal_candidate(
                "causal",
                "path centralization debt affects Cloud integration confidence",
                [
                    {"section": "intelligent_context", "kind": "centralization_status", "pending_count": centralization.get("pending_count"), "single_source_of_truth": centralization.get("single_source_of_truth")},
                    {"section": "intelligent_context", "kind": "safety_contract", "value": package_data.get("context_health", {}).get("safety_contract", {})},
                ],
                0.74,
                "core.paths migration_report surfaced pending path debt; this does not prove failure, but it causally affects integration confidence and review priority.",
                invalidates=["assumption that all path references are fully centralized"],
                proposed_next_check="Review migration_report pending items before Cloud promotes deeper integration or mutation pathways.",
            ))

        if not candidates:
            candidates.append(self._make_causal_candidate(
                "temporal",
                "snapshot and reflection were generated in sequence but no stronger causal evidence was found",
                [
                    {"section": "snapshot", "kind": "generated_at", "time": snapshot_data.get("generated_at")},
                    {"section": "reflection", "kind": "generated_at", "time": reflection_data.get("generated_at")},
                ],
                0.45,
                "Only generation order is available; this is intentionally low confidence.",
                ["no memory events, code targets, or reflection weaknesses were strong enough for higher-confidence candidates"],
            ))

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for candidate in sorted(candidates, key=lambda c: (c.get("confidence", 0.0), c.get("type", "")), reverse=True):
            key = (candidate.get("type"), candidate.get("label"), json.dumps(candidate.get("source_evidence", []), sort_keys=True, default=str)[:300])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
            if len(deduped) >= max_candidates:
                break
        type_counts: Dict[str, int] = {}
        for candidate in deduped:
            type_counts[candidate.get("type", "unknown")] = type_counts.get(candidate.get("type", "unknown"), 0) + 1
        if rag.get("data", {}).get("summary", {}).get("entities", 0) == 0:
            warnings.append("semantic graph is sparse; causal proposals rely mostly on memory/reflection/code context")
        pathfinder_routes = self._build_causal_pathfinder_routes(deduped, limit=max_candidates)
        scaffolding_entry = self._build_causal_scaffolding_entry(str(query), deduped, type_counts, warnings)
        strong_candidate_ids = [c.get("id") for c in deduped if c.get("self_reorganization_signal", {}).get("eligible")]
        reorganization_pathways = self._build_reorganization_pathways(deduped, pathfinder_routes)
        self_reorganization_bridge = {
            "mode": "candidate_analysis_only",
            "can_suggest_reorganization": bool(strong_candidate_ids),
            "can_execute_reorganization": False,
            "strong_candidate_ids": strong_candidate_ids,
            "pathway_count": len(reorganization_pathways),
            "pathway_ids": [p.get("pathway_id") for p in reorganization_pathways],
            "next_gate": "meta_retrieval_awareness_or_guarded_reorganization_planning",
            "denied_actions": ["edit code", "write memory", "persist causal fact", "trigger SelfEditor", "modify ontology"],
            "mutation_preconditions": ["Cloud review", "SelfEditor whitelist", "mandatory backup", "syntax validation", "deploy_check", "human approval for promotion"],
            "hard_stop": "No mutation, persistence, or SelfEditor execution is allowed from this layer.",
        }
        merge_guidance = self._build_causal_merge_guidance(deduped, pathfinder_routes, warnings, self_reorganization_bridge)
        summary = (
            f"NEXUS proposed {len(deduped)} temporal/causal candidate link(s) from IntelligentContextPackage, "
            f"snapshot, and reflection. Types: {type_counts}. All links remain candidates, not facts. "
            f"Pathfinder routes expose why weak sections may be outdated or invalidated by later evidence."
        )
        return CausalTemporalProposal(
            candidates=deduped,
            summary=summary,
            warnings=warnings,
            future_integration_notes=[
                "Do not persist these candidates until a causal store adapter and SelfEditor-style guard contract exist.",
                "Future causal storage should keep status=candidate until evidence review promotes a link.",
                "Use IntelligentContextPackage as the upstream source; do not let causal code bypass SemanticAdapter.",
                "Later meta-retrieval can compare these candidates against fresh snapshots to detect invalidated assumptions.",
            ],
            generated_at=generated_at,
            query=str(query) if query is not None else None,
            max_candidates=max_candidates,
            scaffolding_entry=scaffolding_entry,
            pathfinder_routes=pathfinder_routes,
            self_reorganization_bridge=self_reorganization_bridge,
            merge_guidance=merge_guidance,
            reorganization_pathways=reorganization_pathways,
            metadata={
                "snapshot_contract": snapshot_data.get("contract"),
                "reflection_contract": reflection_data.get("contract"),
                "intelligent_context_contract": package_data.get("contract"),
                "candidate_type_counts": type_counts,
                "consumes_intelligent_context_package": True,
                "read_only_verified": True,
                "heavy_dependencies": [],
            },
        )

    def _route_to_commander_step(self, route: Dict[str, Any], candidate: Dict[str, Any], sequence: int) -> Dict[str, Any]:
        """Convert a causal pathfinder route into a sequenced troubleshooting step."""
        candidate_id = str(candidate.get("id") or route.get("candidate_id") or f"unknown_{sequence}")
        step_id = self._stable_short_id("CMD_STEP", {"candidate_id": candidate_id, "sequence": sequence, "path": route.get("path", [])})
        ctype = str(candidate.get("type", "causal"))
        title_by_type = {
            "invalidation": "Review possibly invalidated assumption",
            "contradiction": "Resolve contradictory evidence path",
            "causal": "Inspect likely cause of weak context",
            "temporal": "Verify event ordering before causal promotion",
        }
        prevented_by_type = {
            "invalidation": "prevents Cloud from trusting an outdated assumption before reviewing later evidence",
            "contradiction": "prevents divergent context sections from producing an unsafe merge decision",
            "causal": "prevents weak or sparse context from being treated as enough evidence for a reorganization",
            "temporal": "prevents sequence-only evidence from being mistaken for causality",
        }
        return {
            "step_id": step_id,
            "sequence": sequence,
            "title": title_by_type.get(ctype, "Review causal route"),
            "candidate_id": candidate_id,
            "candidate_type": ctype,
            "route_id": route.get("route_id"),
            "route_grade": route.get("route_grade"),
            "route_health_score": route.get("route_health_score"),
            "purpose": candidate.get("label") or route.get("path_explanation") or "Review causal candidate route.",
            "why_now": candidate.get("path_explanation") or route.get("path_explanation"),
            "evidence_path": route.get("path", candidate.get("evidence_path", [])),
            "affected_sections": candidate.get("affected_sections", route.get("affected_sections", [])),
            "invalidates": candidate.get("invalidates", []),
            "action_mode": "read_only_review",
            "allowed_now": ["inspect evidence path", "refresh snapshot", "ask targeted follow-up query", "prepare guarded proposal draft"],
            "forbidden_now": ["edit code", "write memory", "persist causal fact", "trigger SelfEditor", "modify ontology"],
            "next_gate": candidate.get("proposed_next_check") or route.get("next_review_step"),
            "expected_failure_prevented": prevented_by_type.get(ctype, "prevents unguarded causal promotion"),
            "guard_chain": route.get("guard_chain", ["candidate-only", "Cloud review", "SelfEditor whitelist", "mandatory backup", "syntax validation", "deploy_check"]),
        }

    def _build_commander_invalidation_map(self, candidates: List[Dict[str, Any]], routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create explicit weak-section -> later-evidence invalidation mappings."""
        by_route = {r.get("candidate_id"): r for r in routes}
        mappings: List[Dict[str, Any]] = []
        for candidate in candidates:
            invalidates = candidate.get("invalidates", []) if isinstance(candidate.get("invalidates", []), list) else []
            affected = candidate.get("affected_sections", []) if isinstance(candidate.get("affected_sections", []), list) else []
            if not invalidates and candidate.get("type") not in {"invalidation", "contradiction"}:
                continue
            route = by_route.get(candidate.get("id"), {})
            mappings.append({
                "map_id": self._stable_short_id("INV_MAP", {"candidate_id": candidate.get("id"), "invalidates": invalidates, "affected": affected}),
                "candidate_id": candidate.get("id"),
                "weak_or_at_risk_sections": affected or ["unknown"],
                "may_invalidate": invalidates or ["implicit assumption in weak context section"],
                "because_evidence": candidate.get("source_evidence", []),
                "later_evidence_path": candidate.get("evidence_path", route.get("path", [])),
                "plain_language": candidate.get("path_explanation") or route.get("path_explanation") or "Later evidence may weaken an earlier assumption.",
                "confidence": candidate.get("confidence", 0.0),
                "status": "candidate_mapping",
            })
        return mappings

    def _predict_commander_failures(self, package: IntelligentContextPackage, proposal: CausalTemporalProposal) -> List[Dict[str, Any]]:
        """Predict likely failure paths from context health + route weak points."""
        pdata = package.to_dict()
        cdata = proposal.to_dict()
        predictions: List[Dict[str, Any]] = []
        coverage = pdata.get("context_health", {}).get("coverage", {}) if isinstance(pdata.get("context_health"), dict) else {}
        gaps = coverage.get("coverage_gaps", []) if isinstance(coverage, dict) else []
        quality_flags = pdata.get("context_health", {}).get("quality_flags", []) if isinstance(pdata.get("context_health"), dict) else []
        centralization = pdata.get("context_health", {}).get("centralization_status", {}) if isinstance(pdata.get("context_health"), dict) else {}
        if gaps:
            predictions.append({
                "prediction_id": self._stable_short_id("FAIL_PATH", {"kind": "coverage", "gaps": gaps[:4]}),
                "risk": "coverage_gap_blocks_confident_reorganization",
                "why": "The intelligent context package reports missing or thin sections before causal review.",
                "evidence": gaps[:6],
                "likely_failure_mode": "Cloud may receive a plausible pathway that lacks enough source coverage to trust.",
                "preventive_step": "Run a targeted query or refresh the weak source section before drafting any reorganization proposal.",
                "severity": "medium",
            })
        if quality_flags:
            predictions.append({
                "prediction_id": self._stable_short_id("FAIL_PATH", {"kind": "quality", "flags": quality_flags[:4]}),
                "risk": "quality_flags_reduce_commander_confidence",
                "why": "v30-style surface heuristics detected quality or evidence weaknesses.",
                "evidence": quality_flags[:6],
                "likely_failure_mode": "The pathway could overfit to weak language, sparse evidence, or unsupported context.",
                "preventive_step": "Prefer candidates with stronger evidence paths and run deploy_check before any mutation planning.",
                "severity": "medium",
            })
        if isinstance(centralization, dict) and centralization.get("centralized") is False:
            predictions.append({
                "prediction_id": self._stable_short_id("FAIL_PATH", {"kind": "centralization", "pending": centralization.get("pending_count")}),
                "risk": "path_centralization_debt_can_break_merge_assumptions",
                "why": "core.paths centralization status reports pending debt.",
                "evidence": [centralization],
                "likely_failure_mode": "A reorganization plan could reference inconsistent paths or stale launcher assumptions.",
                "preventive_step": "Keep all proposals path-safe and require deploy_check path gate before promotion.",
                "severity": "high" if int(centralization.get("pending_count", 0) or 0) > 50 else "medium",
            })
        for route in cdata.get("pathfinder_routes", [])[:6]:
            weak_points = route.get("weak_points", []) if isinstance(route.get("weak_points", []), list) else []
            if weak_points:
                predictions.append({
                    "prediction_id": self._stable_short_id("FAIL_PATH", {"kind": "route", "route_id": route.get("route_id"), "weak": weak_points}),
                    "risk": "causal_route_has_weak_points",
                    "why": f"Route {route.get('route_id')} is graded {route.get('route_grade')} with explicit weak points.",
                    "evidence": weak_points,
                    "likely_failure_mode": "The system may mistake a weak causal route for a reorganization trigger.",
                    "preventive_step": route.get("next_review_step") or "Refresh evidence and rerun causal pathfinder.",
                    "severity": "low" if float(route.get("route_health_score", 0.0) or 0.0) >= 0.55 else "medium",
                })
        return predictions[:8]

    def build_commander_troubleshooting_pathway(self, goal: str, max_steps: int = 8,
                                                strictness: str = "production") -> CommanderPathwayPackage:
        """Build the single-call NEXUS Commander troubleshooting pathway package.

        This is the cohesive public surface Cloud can consume when it needs the
        current NEXUS central-nervous-system view. It remains strictly read-only:
        snapshot, reflection, intelligent context, and causal proposals are used
        to forge sequenced review pathways, not to mutate anything.
        """
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("goal must be a non-empty string")
        if strictness not in {"production", "research", "creative"}:
            raise ValueError("strictness must be production, research, or creative")
        max_steps = max(1, min(24, int(max_steps)))
        generated_at = datetime.now(timezone.utc).isoformat()
        snapshot = self.get_unified_nexus_snapshot(goal)
        reflection = self.reflect_on_snapshot(snapshot, goal)
        package = self.build_intelligent_context(goal=goal, max_tokens=12000, strictness=strictness)
        causal = self.propose_causal_temporal_links(snapshot, reflection=reflection, max_candidates=max_steps)
        cdata = causal.to_dict()
        candidates = cdata.get("candidates", []) if isinstance(cdata.get("candidates", []), list) else []
        routes = cdata.get("pathfinder_routes", []) if isinstance(cdata.get("pathfinder_routes", []), list) else []
        candidate_by_id = {c.get("id"): c for c in candidates if isinstance(c, dict)}
        sorted_routes = sorted(routes, key=lambda r: (float(r.get("route_health_score", 0.0) or 0.0), float(r.get("confidence", 0.0) or 0.0)), reverse=True)
        sequenced_steps: List[Dict[str, Any]] = []
        for idx, route in enumerate(sorted_routes[:max_steps], start=1):
            candidate = candidate_by_id.get(route.get("candidate_id"), {})
            sequenced_steps.append(self._route_to_commander_step(route, candidate, idx))
        if not sequenced_steps:
            sequenced_steps.append({
                "step_id": self._stable_short_id("CMD_STEP", {"goal": goal, "fallback": True}),
                "sequence": 1,
                "title": "Refresh NEXUS context before troubleshooting",
                "candidate_id": None,
                "candidate_type": "none",
                "route_id": None,
                "route_grade": "weak_candidate",
                "route_health_score": 0.0,
                "purpose": "No causal route was strong enough to sequence.",
                "why_now": "The current snapshot lacks enough causal evidence for a Commander pathway.",
                "evidence_path": [],
                "affected_sections": [],
                "invalidates": [],
                "action_mode": "read_only_review",
                "allowed_now": ["refresh snapshot", "run targeted query", "inspect deploy_check output"],
                "forbidden_now": ["edit code", "write memory", "persist causal fact", "trigger SelfEditor"],
                "next_gate": "Collect stronger evidence, then rerun build_commander_troubleshooting_pathway.",
                "expected_failure_prevented": "prevents hallucinated troubleshooting from sparse evidence",
                "guard_chain": ["candidate-only", "Cloud review", "deploy_check"],
            })
        invalidation_map = self._build_commander_invalidation_map(candidates, routes)
        failure_predictions = self._predict_commander_failures(package, causal)
        pathways = cdata.get("reorganization_pathways", []) if isinstance(cdata.get("reorganization_pathways", []), list) else []
        bridge = cdata.get("self_reorganization_bridge", {}) if isinstance(cdata.get("self_reorganization_bridge", {}), dict) else {}
        merge = cdata.get("merge_guidance", {}) if isinstance(cdata.get("merge_guidance", {}), dict) else {}
        route_scores = [float(r.get("route_health_score", 0.0) or 0.0) for r in routes]
        avg_route = round(sum(route_scores) / len(route_scores), 3) if route_scores else 0.0
        warnings = list(dict.fromkeys(list(cdata.get("warnings", [])) + list(package.warnings) + [p.get("risk") for p in failure_predictions if p.get("severity") in {"medium", "high"}]))
        commander_summary = (
            f"NEXUS Commander forged {len(sequenced_steps)} sequenced troubleshooting step(s) for goal '{goal}'. "
            f"It used IntelligentContextPackage + causal pathfinder routes as the guarded source of truth. "
            f"Average route health={avg_route}; execution remains forbidden until SelfEditor guard review."
        )
        return CommanderPathwayPackage(
            goal=goal,
            commander_summary=commander_summary,
            public_surface={
                "single_entrypoint": "SemanticAdapter.build_commander_troubleshooting_pathway",
                "inputs": {"goal": "str", "max_steps": "int", "strictness": "production|research|creative"},
                "output_contract": "wordlib.nexus_commander_pathway.v1",
                "replaces_external_stitching_of": ["get_unified_nexus_snapshot", "reflect_on_snapshot", "build_intelligent_context", "propose_causal_temporal_links"],
                "cloud_consumption_mode": "consume this package first; call lower-level methods only for drilldown",
            },
            troubleshooting_pathways=pathways,
            sequenced_steps=sequenced_steps,
            invalidation_map=invalidation_map,
            failure_predictions=failure_predictions,
            evidence_routes=routes,
            causal_bridge_summary={
                "candidate_count": len(candidates),
                "route_count": len(routes),
                "pathway_count": len(pathways),
                "average_route_health": avg_route,
                "can_suggest_reorganization": bridge.get("can_suggest_reorganization", False),
                "can_execute_reorganization": False,
                "strong_candidate_ids": bridge.get("strong_candidate_ids", []),
            },
            merge_capabilities={
                "merge_safe": bool(merge.get("safe_to_merge", False)),
                "merge_readiness_score": merge.get("readiness_score", 0.0),
                "minimal_touch_files": ["src/semantic_adapter.py", "deploy_check.py", "main.py", "tests/test_commander_pathway.py", "tests/test_causal_temporal_proposals.py"],
                "no_new_dependencies": True,
                "no_file_split": True,
                "read_only": True,
                "cloud_review_checklist": list(merge.get("cloud_review_checklist", [])) + ["Verify commander steps are proposal-only", "Run deploy_check.py --json", "Run pytest -q"],
            },
            warnings=warnings,
            generated_at=generated_at,
            strictness=strictness,
            max_steps=max_steps,
            metadata={
                "snapshot_contract": snapshot.contract,
                "reflection_contract": reflection.contract,
                "intelligent_context_contract": package.contract,
                "causal_contract": causal.contract,
                "uses_intelligent_context_package": True,
                "uses_causal_pathfinder_routes": True,
                "commander_capability": "sequenced_troubleshooting_pathways_not_execution",
                "forbidden_actions": ["edit code", "write memory", "persist causal fact", "trigger SelfEditor", "modify ontology"],
            },
        )

    def commander_pathway_for_prompt(self, goal: str, max_steps: int = 8,
                                     strictness: str = "production") -> SemanticAdapterResult:
        """Return compact prompt-ready Commander troubleshooting pathway context."""
        try:
            package = self.build_commander_troubleshooting_pathway(goal=goal, max_steps=max_steps, strictness=strictness)
            d = package.to_dict()
            lines = [
                "WORDLIB NEXUS Commander pathway (read-only):",
                f"- Goal: {d.get('goal')}",
                f"- Contract: {d.get('contract')}; steps={len(d.get('sequenced_steps', []))}; routes={len(d.get('evidence_routes', []))}",
                "- Summary: " + d.get("commander_summary", ""),
                "- Public surface: " + d.get("public_surface", {}).get("single_entrypoint", "SemanticAdapter"),
            ]
            for step in d.get("sequenced_steps", [])[:5]:
                lines.append(f"- Step {step.get('sequence')}: {step.get('title')} [{step.get('action_mode')}] -- {step.get('purpose')}")
                if step.get("why_now"):
                    lines.append(f"  why: {step.get('why_now')}")
            if d.get("failure_predictions"):
                lines.append("- Failure predictions: " + "; ".join(str(p.get("risk")) for p in d.get("failure_predictions", [])[:4]))
            lines.append("- Execution: forbidden; this package is for Cloud review and guarded planning only.")
            return self._result("commander_pathway_for_prompt", {"package": d, "prompt_context": "\n".join(lines)}, d.get("warnings", []))
        except Exception as exc:
            return self._error("commander_pathway_for_prompt", exc)

    def causal_temporal_for_prompt(self, snapshot: NexusSnapshot, reflection: Optional[ReflectionResult] = None,
                                   max_candidates: int = 12) -> SemanticAdapterResult:
        """Return compact prompt-ready causal/temporal candidate context."""
        try:
            proposal = self.propose_causal_temporal_links(snapshot, reflection=reflection, max_candidates=max_candidates)
            d = proposal.to_dict()
            lines = [
                "WORDLIB NEXUS causal/temporal proposal layer (read-only):",
                f"- Query: {d.get('query')}",
                f"- Candidates: {len(d.get('candidates', []))}; contract={d.get('contract')}",
                "- Summary: " + d.get("summary", ""),
            ]
            for candidate in d.get("candidates", [])[:5]:
                lines.append(
                    f"- {candidate.get('type')} candidate ({candidate.get('confidence')}): {candidate.get('label')} -- {candidate.get('confidence_reason')}"
                )
                if candidate.get("path_explanation"):
                    lines.append(f"  path: {candidate.get('path_explanation')}")
            routes = d.get("pathfinder_routes", [])
            if routes:
                lines.append(f"- Pathfinder routes: {len(routes)} route(s), first={routes[0].get('candidate_id')}")
            bridge = d.get("self_reorganization_bridge", {})
            if bridge:
                lines.append(f"- Self-reorganization bridge: suggest={bridge.get('can_suggest_reorganization')}, execute={bridge.get('can_execute_reorganization')}, pathways={bridge.get('pathway_count')}")
            merge = d.get("merge_guidance", {})
            if merge:
                lines.append(f"- Merge guidance: safe={merge.get('safe_to_merge')}, readiness={merge.get('readiness_score')}, mode={merge.get('merge_mode')}")
            if d.get("warnings"):
                lines.append("- Warnings: " + "; ".join(str(w) for w in d["warnings"][:6]))
            return self._result("causal_temporal_for_prompt", {"proposal": d, "prompt_context": "\n".join(lines)}, d.get("warnings", []))
        except Exception as exc:
            return self._error("causal_temporal_for_prompt", exc)

    def intelligent_context_for_prompt(self, goal: str, max_tokens: int = 12000,
                                       strictness: str = "production") -> SemanticAdapterResult:
        """Return compact prompt-ready intelligent context for Cloud/agents."""
        try:
            package = self.build_intelligent_context(goal=goal, max_tokens=max_tokens, strictness=strictness)
            d = package.to_dict()
            lines = [
                "WORDLIB NEXUS intelligent context package (read-only):",
                f"- Goal: {d.get('goal')}",
                f"- Strictness: {d.get('strictness')}; quality={d.get('overall_quality_score')}; tokens≈{d.get('token_estimate')}",
                "- Ranked sections: " + ", ".join(d.get("curated_context", {}).get("ranked_sections", [])),
                "- Selection reasoning: " + d.get("selection_reasoning", ""),
                "- Quality flags: " + ("; ".join(d.get("context_health", {}).get("quality_flags", [])[:5]) or "none"),
                "- Coverage gaps: " + ("; ".join(d.get("context_health", {}).get("coverage", {}).get("coverage_gaps", [])[:5]) or "none"),
                "- Proposed mutations: " + str(len(d.get("proposed_mutations", []))) + " proposal(s), all read-only and guard-required.",
            ]
            if d.get("warnings"):
                lines.append("- Warnings: " + "; ".join(str(w) for w in d["warnings"][:6]))
            return self._result("intelligent_context_for_prompt", {"package": d, "prompt_context": "\n".join(lines)}, d.get("warnings", []))
        except Exception as exc:
            return self._error("intelligent_context_for_prompt", exc)

    def save(self) -> SemanticAdapterResult:
        try:
            path = self.graph.save()
            return self._result("save", {"storage_path": str(path)})
        except Exception as exc:
            return self._error("save", exc)

    def load(self) -> SemanticAdapterResult:
        try:
            self.graph.load()
            self.bridge = SemanticRAGBridge(self.graph, entity_hints=self._merged_entity_hints())
            return self._result("load", {"summary": self.graph.summary()})
        except Exception as exc:
            return self._error("load", exc)

    def export_snapshot(self) -> SemanticAdapterResult:
        """Return JSON-safe snapshot for diagnostics or handoff."""
        try:
            return self._result("export_snapshot", {"graph": json.loads(self.graph.export_json())})
        except Exception as exc:
            return self._error("export_snapshot", exc)


def create_default_adapter(auto_load: bool = True, auto_save: bool = False,
                           storage_path: Optional[str] = None,
                           entity_hints: Optional[Dict[str, str]] = None) -> SemanticAdapter:
    """Factory used by future RAG/memory hooks to avoid constructor coupling."""
    return SemanticAdapter(SemanticAdapterConfig(
        storage_path=storage_path,
        auto_load=auto_load,
        auto_save=auto_save,
        entity_hints=dict(entity_hints or {"WORDLIB": "project", "MotherEther": "project"}),
        enable_local_ontology=True,
    ))


def semantic_adapter_status() -> Dict[str, Any]:
    """Tiny status helper safe for main.py/deploy_check.py."""
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    return adapter.health_check().to_dict()


def nexus_snapshot_status(query: Optional[str] = None) -> Dict[str, Any]:
    """Boot/deploy-safe status helper for the read-only NEXUS snapshot."""
    try:
        adapter = create_default_adapter(auto_load=True, auto_save=False)
        snapshot = adapter.get_unified_nexus_snapshot(query)
        d = snapshot.to_dict()
        return {
            "ok": bool(d.get("health", {}).get("overall")),
            "read_only": d.get("read_only") is True,
            "contract": d.get("contract"),
            "summary": d.get("summary", {}),
            "sections": list(d.get("sections", {}).keys()),
            "warnings": d.get("warnings", []),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "read_only": True,
            "contract": "wordlib.nexus_snapshot.v1",
            "summary": {},
            "sections": [],
            "warnings": [],
            "error": f"{type(exc).__name__}: {exc}",
        }



def reflection_status(query: Optional[str] = None) -> Dict[str, Any]:
    """Boot/deploy-safe status helper for NEXUS reflection/self-critique."""
    try:
        adapter = create_default_adapter(auto_load=True, auto_save=False)
        snapshot = adapter.get_unified_nexus_snapshot(query or "WORDLIB NEXUS reflection SemanticAdapter")
        reflection = adapter.reflect_on_snapshot(snapshot, query=query)
        d = reflection.to_dict()
        return {
            "ok": isinstance(reflection, ReflectionResult) and d.get("read_only") is True,
            "read_only": d.get("read_only") is True,
            "contract": d.get("contract"),
            "overall_relevance_score": d.get("overall_relevance_score"),
            "section_scores": d.get("section_scores", {}),
            "missing_or_weak_sections": d.get("missing_or_weak_sections", []),
            "warnings": d.get("retrieval_weaknesses", []),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "read_only": True,
            "contract": "wordlib.nexus_reflection.v1",
            "overall_relevance_score": 0.0,
            "section_scores": {},
            "missing_or_weak_sections": [],
            "warnings": [],
            "error": f"{type(exc).__name__}: {exc}",
        }



def intelligent_context_status(goal: Optional[str] = None) -> Dict[str, Any]:
    """Boot/deploy-safe status helper for guarded NEXUS intelligent context."""
    try:
        adapter = create_default_adapter(auto_load=True, auto_save=False)
        package = adapter.build_intelligent_context(
            goal or "WORDLIB NEXUS intelligent context SemanticAdapter Cloud integration",
            max_tokens=6000,
            strictness="production",
        )
        d = package.to_dict()
        return {
            "ok": isinstance(package, IntelligentContextPackage) and d.get("read_only") is True,
            "read_only": d.get("read_only") is True,
            "contract": d.get("contract"),
            "overall_quality_score": d.get("overall_quality_score"),
            "token_estimate": d.get("token_estimate"),
            "ranked_sections": d.get("curated_context", {}).get("ranked_sections", []),
            "warnings": d.get("warnings", []),
            "proposed_mutations": len(d.get("proposed_mutations", [])),
            "centralized": d.get("context_health", {}).get("centralization_status", {}).get("centralized"),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "read_only": True,
            "contract": "wordlib.nexus_intelligent_context.v1",
            "overall_quality_score": 0.0,
            "token_estimate": 0,
            "ranked_sections": [],
            "warnings": [],
            "proposed_mutations": 0,
            "centralized": None,
            "error": f"{type(exc).__name__}: {exc}",
        }



def causal_temporal_status(query: Optional[str] = None) -> Dict[str, Any]:
    """Boot/deploy-safe status helper for NEXUS causal/temporal proposals."""
    try:
        adapter = create_default_adapter(auto_load=True, auto_save=False)
        snapshot = adapter.get_unified_nexus_snapshot(query or "WORDLIB NEXUS causal temporal Cloud bridge")
        reflection = adapter.reflect_on_snapshot(snapshot, query=query)
        proposal = adapter.propose_causal_temporal_links(snapshot, reflection=reflection, max_candidates=8)
        d = proposal.to_dict()
        type_counts = d.get("metadata", {}).get("candidate_type_counts", {})
        return {
            "ok": isinstance(proposal, CausalTemporalProposal) and d.get("read_only") is True,
            "read_only": d.get("read_only") is True,
            "contract": d.get("contract"),
            "candidate_count": len(d.get("candidates", [])),
            "candidate_type_counts": type_counts,
            "pathfinder_routes": len(d.get("pathfinder_routes", [])),
            "pathway_count": d.get("self_reorganization_bridge", {}).get("pathway_count", 0),
            "merge_safe": d.get("merge_guidance", {}).get("safe_to_merge", False),
            "strong_candidate_ids": d.get("self_reorganization_bridge", {}).get("strong_candidate_ids", []),
            "can_suggest_reorganization": d.get("self_reorganization_bridge", {}).get("can_suggest_reorganization", False),
            "warnings": d.get("warnings", []),
            "summary": d.get("summary"),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "read_only": True,
            "contract": "wordlib.nexus_causal_temporal.v1",
            "candidate_count": 0,
            "candidate_type_counts": {},
            "pathfinder_routes": 0,
            "pathway_count": 0,
            "merge_safe": False,
            "strong_candidate_ids": [],
            "can_suggest_reorganization": False,
            "warnings": [],
            "summary": "",
            "error": f"{type(exc).__name__}: {exc}",
        }



def commander_pathway_status(query: Optional[str] = None) -> Dict[str, Any]:
    """Boot/deploy-safe status helper for the NEXUS Commander pathway."""
    try:
        adapter = create_default_adapter(auto_load=True, auto_save=False)
        package = adapter.build_commander_troubleshooting_pathway(query or "WORDLIB NEXUS Commander Cloud troubleshooting", max_steps=6)
        d = package.to_dict()
        return {
            "ok": isinstance(package, CommanderPathwayPackage) and d.get("read_only") is True,
            "read_only": d.get("read_only") is True,
            "contract": d.get("contract"),
            "step_count": len(d.get("sequenced_steps", [])),
            "route_count": len(d.get("evidence_routes", [])),
            "pathway_count": len(d.get("troubleshooting_pathways", [])),
            "failure_prediction_count": len(d.get("failure_predictions", [])),
            "merge_safe": d.get("merge_capabilities", {}).get("merge_safe", False),
            "single_entrypoint": d.get("public_surface", {}).get("single_entrypoint"),
            "can_execute_reorganization": d.get("causal_bridge_summary", {}).get("can_execute_reorganization"),
            "warnings": d.get("warnings", []),
            "summary": d.get("commander_summary"),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "read_only": True,
            "contract": "wordlib.nexus_commander_pathway.v1",
            "step_count": 0,
            "route_count": 0,
            "pathway_count": 0,
            "failure_prediction_count": 0,
            "merge_safe": False,
            "single_entrypoint": "SemanticAdapter.build_commander_troubleshooting_pathway",
            "can_execute_reorganization": False,
            "warnings": [],
            "summary": "",
            "error": f"{type(exc).__name__}: {exc}",
        }

def self_check() -> bool:
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    fact = adapter.add_evidence_backed_fact(
        "WORDLIB", "contains adapter", "semantic_adapter.py",
        "WORDLIB contains src/semantic_adapter.py as a safe boundary over semantic_core.py.",
        subject_type="project", object_type="file", source_type="self_check", confidence=0.9,
    )
    assert fact.ok, fact.error
    ingest = adapter.ingest_text(
        "SemanticAdapter exposes context_for_query and shortest_path without circular imports.",
        source_path="src/semantic_adapter.py", max_entities=8,
    )
    assert ingest.ok, ingest.error
    path = adapter.shortest_path("WORDLIB", "semantic_adapter.py")
    assert path.ok and path.data.get("found"), path.to_dict()
    context = adapter.context_for_query("WORDLIB semantic adapter", as_prompt=True)
    assert context.ok and "semantic graph context" in context.data["prompt_context"]
    assert "Local ontology context" in context.data["prompt_context"]
    ontology = adapter.ontology_context_for_query("RAG Semantic Adapter")
    assert ontology.ok and ontology.data.get("matches")
    memory = adapter.memory_context_for_query("WORDLIB memory semantic hook", as_prompt=True)
    assert memory.ok and memory.data.get("read_only") is True, memory.to_dict()
    code = adapter.code_structure_context_for_query("SemanticAdapter code_structure_hook", as_prompt=True, max_items=5)
    assert code.ok and code.data.get("read_only") is True, code.to_dict()
    assert "WORDLIB code structure context" in code.data.get("prompt_context", ""), code.to_dict()
    snapshot = adapter.get_unified_nexus_snapshot("SemanticAdapter NEXUS code memory ontology")
    assert snapshot.read_only is True, snapshot.to_dict()
    exported = snapshot.to_dict()
    assert all(name in exported["sections"] for name in ("memory", "code", "ontology", "rag")), exported
    prompt_snapshot = adapter.nexus_snapshot_for_prompt("SemanticAdapter NEXUS")
    assert prompt_snapshot.ok and "NEXUS unified context snapshot" in prompt_snapshot.data.get("prompt_context", ""), prompt_snapshot.to_dict()
    reflection = adapter.reflect_on_snapshot(snapshot, "SemanticAdapter NEXUS code memory ontology")
    assert isinstance(reflection, ReflectionResult) and reflection.read_only is True, reflection.to_dict()
    assert 0.0 <= reflection.overall_relevance_score <= 1.0, reflection.to_dict()
    prompt_reflection = adapter.reflection_for_prompt(snapshot, "SemanticAdapter NEXUS")
    assert prompt_reflection.ok and "NEXUS reflection/self-critique" in prompt_reflection.data.get("prompt_context", ""), prompt_reflection.to_dict()
    intelligent = adapter.build_intelligent_context("SemanticAdapter NEXUS Cloud integration", max_tokens=6000)
    assert isinstance(intelligent, IntelligentContextPackage) and intelligent.read_only is True, intelligent.to_dict()
    assert intelligent.contract == "wordlib.nexus_intelligent_context.v1", intelligent.to_dict()
    prompt_intelligent = adapter.intelligent_context_for_prompt("SemanticAdapter NEXUS Cloud integration")
    assert prompt_intelligent.ok and "NEXUS intelligent context package" in prompt_intelligent.data.get("prompt_context", ""), prompt_intelligent.to_dict()
    causal = adapter.propose_causal_temporal_links(snapshot, reflection=reflection, max_candidates=6)
    assert isinstance(causal, CausalTemporalProposal) and causal.read_only is True, causal.to_dict()
    assert causal.candidates and all(c.get("status") == "candidate" for c in causal.candidates), causal.to_dict()
    prompt_causal = adapter.causal_temporal_for_prompt(snapshot, reflection=reflection, max_candidates=6)
    assert prompt_causal.ok and "causal/temporal proposal layer" in prompt_causal.data.get("prompt_context", ""), prompt_causal.to_dict()
    commander = adapter.build_commander_troubleshooting_pathway("SemanticAdapter NEXUS Cloud guarded troubleshooting", max_steps=4)
    assert isinstance(commander, CommanderPathwayPackage) and commander.read_only is True, commander.to_dict()
    assert commander.sequenced_steps and commander.public_surface.get("single_entrypoint") == "SemanticAdapter.build_commander_troubleshooting_pathway", commander.to_dict()
    prompt_commander = adapter.commander_pathway_for_prompt("SemanticAdapter NEXUS Cloud guarded troubleshooting", max_steps=4)
    assert prompt_commander.ok and "NEXUS Commander pathway" in prompt_commander.data.get("prompt_context", ""), prompt_commander.to_dict()
    audit = adapter.compact_and_audit()
    assert audit.ok and audit.data["audit"].get("healthy"), audit.to_dict()
    return True


if __name__ == "__main__":
    ok = self_check()
    status = semantic_adapter_status()
    print(json.dumps({"semantic_adapter_self_check": ok, "status": status}, indent=2))

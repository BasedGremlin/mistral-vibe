"""
WORDLIB Local Ontology Layer v1
===============================
Small deterministic ontology vocabulary for WORDLIB semantic adapters.

Purpose:
- provide local type/relation vocabulary without a database
- classify project terms before heavy RAG/vector integration
- keep ontology read-only and dependency-light
- expose entity hints and prompt context for SemanticAdapter/RAG hooks
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_SRC_DIR = Path(__file__).resolve().parent
_ROOT = _SRC_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

ONTOLOGY_SCHEMA_VERSION = "wordlib.local_ontology.v1"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean(value).replace("\\", "/")).casefold()


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        text = _clean(value)
        key = _norm(text)
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


@dataclass(frozen=True)
class OntologyTerm:
    id: str
    name: str
    kind: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    parent_id: Optional[str] = None
    allowed_relations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, query: str) -> bool:
        q = _norm(query)
        if not q:
            return False
        names = [self.name, *self.aliases, self.id]
        return any(_norm(name) == q or _norm(name) in q or q in _norm(name) for name in names)


class LocalOntologyLayer:
    """Read-only local vocabulary for semantic classification and context."""

    CONTRACT_VERSION = ONTOLOGY_SCHEMA_VERSION

    def __init__(self, terms: Optional[Iterable[OntologyTerm]] = None) -> None:
        base_terms = list(terms) if terms is not None else self._default_terms()
        self.terms: Dict[str, OntologyTerm] = {term.id: term for term in base_terms}
        self._alias_index: Dict[str, str] = {}
        for term in self.terms.values():
            for alias in [term.name, term.id, *term.aliases]:
                self._alias_index[_norm(alias)] = term.id

    @staticmethod
    def _default_terms() -> List[OntologyTerm]:
        return [
            OntologyTerm(
                id="ONT_PROJECT_WORDLIB", name="WORDLIB", kind="project",
                aliases=["MotherEther", "WORDLIB / MotherEther", "MotherEther v30"],
                description="Portable local AI/library project with path-safe storage, deployment gates, RAG, memory, and semantic provenance.",
                allowed_relations=["contains module", "uses component", "validates", "stores evidence"],
                metadata={"priority": "foundation"},
            ),
            OntologyTerm(
                id="ONT_COMPONENT_SEMANTIC_CORE", name="Semantic Core", kind="component",
                aliases=["semantic_core.py", "src/semantic_core.py", "SemanticKnowledgeGraph"],
                description="Compact provenance-aware entity graph with evidence-backed facts, JSON persistence, audit, compaction, and semantic pathfinding.",
                parent_id="ONT_PROJECT_WORDLIB",
                allowed_relations=["defines schema", "stores entity", "stores relationship", "stores event", "requires evidence"],
                metadata={"source_file": "src/semantic_core.py"},
            ),
            OntologyTerm(
                id="ONT_COMPONENT_SEMANTIC_ADAPTER", name="Semantic Adapter", kind="component",
                aliases=["semantic_adapter.py", "src/semantic_adapter.py", "SemanticAdapter"],
                description="Stable adapter boundary used by RAG, memory, and reasoning modules instead of direct graph internals.",
                parent_id="ONT_PROJECT_WORDLIB",
                allowed_relations=["exposes context", "ingests text", "adds evidence-backed fact", "checks health"],
                metadata={"source_file": "src/semantic_adapter.py"},
            ),
            OntologyTerm(
                id="ONT_COMPONENT_LOCAL_ONTOLOGY", name="Local Ontology Layer", kind="component",
                aliases=["local_ontology.py", "src/local_ontology.py", "LocalOntologyLayer"],
                description="Lightweight read-only vocabulary that classifies WORDLIB concepts, components, schemas, and allowed relations.",
                parent_id="ONT_PROJECT_WORDLIB",
                allowed_relations=["classifies term", "provides entity hints", "provides prompt context"],
                metadata={"source_file": "src/local_ontology.py"},
            ),
            OntologyTerm(
                id="ONT_SUBSYSTEM_RAG", name="RAG", kind="subsystem",
                aliases=["rag_manager.py", "src/rag_manager.py", "USBRAGManager", "retrieval augmented generation"],
                description="Existing retrieval subsystem. It may read semantic context through SemanticAdapter but must not be replaced in this phase.",
                parent_id="ONT_PROJECT_WORDLIB",
                allowed_relations=["reads semantic context", "queries index", "uses adapter"],
                metadata={"source_file": "src/rag_manager.py", "integration_mode": "optional_read_only"},
            ),
            OntologyTerm(
                id="ONT_SUBSYSTEM_MEMORY", name="Memory", kind="subsystem",
                aliases=["shared_memory", "EventLog", "gremlin_memory.json", "ether_events.jsonl", "memory graph"],
                description="Existing local memory/logging surfaces. They may read context through SemanticAdapter but must not write semantic facts during this phase.",
                parent_id="ONT_PROJECT_WORDLIB",
                allowed_relations=["reads semantic context", "stores operational state", "uses adapter"],
                metadata={"integration_mode": "optional_read_only", "source_files": ["data/gremlin_memory.json", "data/ether_events.jsonl"]},
            ),
            OntologyTerm(
                id="ONT_COMPONENT_MEMORY_SEMANTIC_HOOK", name="Memory Semantic Hook", kind="component",
                aliases=["memory_semantic_hook.py", "src/memory_semantic_hook.py", "semantic_context_for_memory_query", "semantic memory hook"],
                description="Tiny read-only bridge that lets WORDLIB memory surfaces request SemanticAdapter context without importing graph internals or writing memory.",
                parent_id="ONT_SUBSYSTEM_MEMORY",
                allowed_relations=["reads memory", "uses adapter", "provides prompt context"],
                metadata={"source_file": "src/memory_semantic_hook.py", "integration_mode": "optional_read_only"},
            ),
            OntologyTerm(
                id="ONT_SUBSYSTEM_CODE_STRUCTURE", name="Code Structure", kind="subsystem",
                aliases=["AST", "Python ast", "modules", "classes", "functions", "imports", "call sites"],
                description="Read-only structural view of the WORDLIB Python codebase using the standard-library ast module.",
                parent_id="ONT_PROJECT_WORDLIB",
                allowed_relations=["scans module", "contains class", "contains function", "imports module", "calls function", "uses adapter"],
                metadata={"integration_mode": "optional_read_only", "dependency_policy": "standard_library_only"},
            ),
            OntologyTerm(
                id="ONT_COMPONENT_CODE_STRUCTURE_HOOK", name="Code Structure Hook", kind="component",
                aliases=["code_structure_hook.py", "src/code_structure_hook.py", "CodeStructureHook", "semantic_context_for_code_query", "AST code hook"],
                description="Tiny read-only AST bridge that lets SemanticAdapter expose modules, classes, functions, imports, signatures, docstrings, and basic call sites.",
                parent_id="ONT_SUBSYSTEM_CODE_STRUCTURE",
                allowed_relations=["reads code", "uses adapter", "provides prompt context", "supports NEXUS"],
                metadata={"source_file": "src/code_structure_hook.py", "integration_mode": "optional_read_only"},
            ),
            OntologyTerm(
                id="ONT_ARCH_NEXUS", name="NEXUS", kind="architecture",
                aliases=["central intelligence layer", "SemanticAdapter as NEXUS", "NEXUS layer"],
                description="Emerging central intelligence boundary where semantic, memory, RAG, ontology, and code-structure contexts are unified without breaking read-only contracts.",
                parent_id="ONT_COMPONENT_SEMANTIC_ADAPTER",
                allowed_relations=["unifies context", "exports snapshot", "suggests reorganization", "preserves read-only mode"],
                metadata={"status": "emerging", "do_not_add_heavy_deps_yet": True},
            ),
            OntologyTerm(
                id="ONT_COMPONENT_NEXUS_REFLECTION", name="NEXUS Reflection", kind="component",
                aliases=["ReflectionResult", "reflect_on_snapshot", "snapshot critique", "self-critique layer"],
                description="Read-only self-critique layer that scores NEXUS snapshots, detects weak sections, and suggests context improvements without writing state.",
                parent_id="ONT_ARCH_NEXUS",
                allowed_relations=["critiques snapshot", "scores section", "suggests retrieval", "preserves read-only mode"],
                metadata={"source_file": "src/semantic_adapter.py", "contract": "wordlib.nexus_reflection.v1"},
            ),
            OntologyTerm(
                id="ONT_COMPONENT_INTELLIGENT_CONTEXT", name="NEXUS Intelligent Context", kind="component",
                aliases=["IntelligentContextPackage", "build_intelligent_context", "guarded context package", "Cloud bridge"],
                description="Goal-aware guarded context package that curates NEXUS sources with v30-style health, quality, centralization, and propose-only safety signals.",
                parent_id="ONT_ARCH_NEXUS",
                allowed_relations=["curates context", "audits quality", "reports health", "proposes guarded mutation"],
                metadata={"source_file": "src/semantic_adapter.py", "contract": "wordlib.nexus_intelligent_context.v1"},
            ),
            OntologyTerm(
                id="ONT_COMPONENT_CAUSAL_TEMPORAL", name="Causal Temporal Proposal Layer", kind="component",
                aliases=["CausalTemporalProposal", "propose_causal_temporal_links", "temporal causal scaffolding", "causal candidates"],
                description="Read-only proposal layer that analyzes IntelligentContextPackage, NexusSnapshot, and ReflectionResult to emit evidence-linked candidate temporal, causal, invalidation, and contradiction relationships.",
                parent_id="ONT_ARCH_NEXUS",
                allowed_relations=["proposes candidate", "links evidence", "requires future guard", "does not persist fact"],
                metadata={"source_file": "src/semantic_adapter.py", "contract": "wordlib.nexus_causal_temporal.v1", "status": "candidate_only"},
            ),
            OntologyTerm(
                id="ONT_SCHEMA_ENTITY", name="Entity", kind="schema",
                aliases=["semantic entity", "entities"],
                description="Evidence-backed semantic object with name, type, aliases, confidence, metadata, and evidence_ids.",
                parent_id="ONT_COMPONENT_SEMANTIC_CORE",
                allowed_relations=["supported by evidence", "participates in relationship", "participates in event"],
            ),
            OntologyTerm(
                id="ONT_SCHEMA_RELATIONSHIP", name="Relationship", kind="schema",
                aliases=["semantic relationship", "edge"],
                description="Evidence-backed typed edge between two entities.",
                parent_id="ONT_COMPONENT_SEMANTIC_CORE",
                allowed_relations=["links entity", "supported by evidence"],
            ),
            OntologyTerm(
                id="ONT_SCHEMA_EVENT", name="Event", kind="schema",
                aliases=["semantic event", "timeline event"],
                description="Evidence-backed event involving one or more entities with optional timestamp.",
                parent_id="ONT_COMPONENT_SEMANTIC_CORE",
                allowed_relations=["involves entity", "supported by evidence"],
            ),
            OntologyTerm(
                id="ONT_SCHEMA_EVIDENCE", name="Evidence", kind="schema",
                aliases=["provenance", "evidence_ids", "source excerpt"],
                description="Source record supporting semantic facts. Every semantic fact must trace back to evidence.",
                parent_id="ONT_COMPONENT_SEMANTIC_CORE",
                allowed_relations=["supports fact", "comes from source"],
            ),
            OntologyTerm(
                id="ONT_GATE_DEPLOY_CHECK", name="Deployment Gate", kind="gate",
                aliases=["deploy_check.py", "semantic gate", "promotion gate"],
                description="Deployment validation layer that blocks promotion when semantic core, adapter, ontology, or path safety is broken.",
                parent_id="ONT_PROJECT_WORDLIB",
                allowed_relations=["validates component", "blocks broken deployment"],
                metadata={"source_file": "deploy_check.py"},
            ),
            OntologyTerm(
                id="ONT_CONSTRAINT_PATH_SAFE", name="Path Safe Storage", kind="constraint",
                aliases=["path-safe", "path utilities", "core.paths", "project-local storage"],
                description="Storage must resolve through existing path utilities or project-local fallbacks without absolute device paths.",
                parent_id="ONT_PROJECT_WORDLIB",
                allowed_relations=["constrains storage", "validates path"],
            ),
            OntologyTerm(
                id="ONT_CONSTRAINT_NO_HEAVY_DEPS", name="No Heavy Dependencies", kind="constraint",
                aliases=["no SQLite", "no FAISS", "no Qdrant", "no graph database", "no networkx", "no LanceDB", "no FalkorDB", "no tree-sitter yet"],
                description="Current foundation phase forbids heavy database/vector/graph tools until adapter and semantic integrity gates are proven.",
                parent_id="ONT_PROJECT_WORDLIB",
                allowed_relations=["constrains integration", "delays tool swap"],
            ),
        ]

    def summary(self) -> Dict[str, Any]:
        kinds: Dict[str, int] = {}
        for term in self.terms.values():
            kinds[term.kind] = kinds.get(term.kind, 0) + 1
        return {"schema": self.CONTRACT_VERSION, "terms": len(self.terms), "kinds": kinds, "healthy": self.audit()["healthy"]}

    def audit(self) -> Dict[str, Any]:
        errors: List[str] = []
        seen_names: Dict[str, str] = {}
        for term in self.terms.values():
            if not _clean(term.id):
                errors.append("ontology term has empty id")
            if not _clean(term.name):
                errors.append(f"ontology term {term.id} has empty name")
            if term.parent_id and term.parent_id not in self.terms:
                errors.append(f"ontology term {term.id} references missing parent {term.parent_id}")
            key = _norm(term.name)
            if key in seen_names and seen_names[key] != term.id:
                errors.append(f"duplicate ontology name {term.name}: {seen_names[key]} and {term.id}")
            seen_names[key] = term.id
            try:
                json.dumps(asdict(term), sort_keys=True)
            except TypeError as exc:
                errors.append(f"ontology term {term.id} is not JSON-safe: {exc}")
        return {"healthy": not errors, "errors": errors, "error_count": len(errors)}

    def classify(self, value: str) -> Optional[OntologyTerm]:
        key = _norm(value)
        term_id = self._alias_index.get(key)
        if term_id:
            return self.terms[term_id]
        for alias_key, indexed_id in self._alias_index.items():
            if alias_key and (alias_key in key or key in alias_key):
                return self.terms[indexed_id]
        return None

    def find_terms(self, query: str, limit: int = 8) -> List[OntologyTerm]:
        matches: List[OntologyTerm] = []
        for term in self.terms.values():
            if term.matches(query):
                matches.append(term)
        matches.sort(key=lambda term: (term.kind, term.name))
        return matches[:max(0, limit)]

    def allowed_relation(self, source: str, relation: str) -> bool:
        term = self.classify(source)
        if not term:
            return False
        rel = _norm(relation)
        return any(_norm(item) == rel for item in term.allowed_relations)

    def entity_hints(self) -> Dict[str, str]:
        hints: Dict[str, str] = {}
        for term in self.terms.values():
            names = [term.name, *term.aliases]
            for name in names:
                clean = _clean(name)
                if clean and "/" not in clean and not clean.endswith(".py"):
                    hints[clean] = term.kind if term.kind in {"project", "component", "subsystem", "schema", "gate", "constraint"} else "concept"
        return hints

    def context_for_query(self, query: str, limit: int = 5) -> Dict[str, Any]:
        terms = self.find_terms(query, limit=limit)
        return {
            "schema": self.CONTRACT_VERSION,
            "query": query,
            "matches": [asdict(term) for term in terms],
            "summary": self.summary(),
            "warnings": [] if terms else ["no local ontology term matched the query"],
        }

    def prompt_context(self, query: str, limit: int = 5) -> str:
        context = self.context_for_query(query, limit=limit)
        if not context["matches"]:
            return "Local ontology context: no matching ontology terms."
        lines = ["Local ontology context:"]
        for item in context["matches"]:
            aliases = ", ".join(item.get("aliases", [])[:3]) or "none"
            lines.append(f"- {item['name']} [{item['kind']}]: {item['description']} Aliases: {aliases}.")
        return "\n".join(lines)

    def export_json(self) -> str:
        payload = {"schema": self.CONTRACT_VERSION, "terms": [asdict(term) for term in sorted(self.terms.values(), key=lambda t: t.id)]}
        return json.dumps(payload, indent=2, sort_keys=True)


def create_default_ontology() -> LocalOntologyLayer:
    return LocalOntologyLayer()


def ontology_status() -> Dict[str, Any]:
    ontology = create_default_ontology()
    return {"ok": ontology.audit()["healthy"], "data": ontology.summary(), "error": None if ontology.audit()["healthy"] else ontology.audit()["errors"][:3]}


def self_check() -> bool:
    ontology = create_default_ontology()
    audit = ontology.audit()
    assert audit["healthy"], audit
    assert ontology.classify("semantic_core.py") is not None
    assert ontology.classify("RAG").id == "ONT_SUBSYSTEM_RAG"
    assert ontology.entity_hints().get("WORDLIB") == "project"
    assert ontology.classify("propose_causal_temporal_links").id == "ONT_COMPONENT_CAUSAL_TEMPORAL"
    assert "Local ontology context" in ontology.prompt_context("WORDLIB Semantic Adapter RAG")
    return True


if __name__ == "__main__":
    ok = self_check()
    print(json.dumps({"local_ontology_self_check": ok, "status": ontology_status()}, indent=2))

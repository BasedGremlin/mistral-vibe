# Canonical Source Map

## Tier A - active executable candidate

### OKComputer Swarm Integrated v1
Path: `10_CANONICAL_WORKING_TREES/OKComputer_Swarm_Integrated_v1/OKComputer_Swarm_Integrated/`

Role: user interface, authenticated swarm runs, OpenAI Agents SDK orchestration, optional Claude critique, local Hugging Face routing, Supabase control-plane integration.

Canonicality: newest active software candidate from this conversation.

Do not overwrite it with the original swarm archive. Compare or cherry-pick only.

## Tier B - preserved foundation baseline

### WORDLIB v29
Path: `10_CANONICAL_WORKING_TREES/WORDLIB_v29_BASELINE/wordlib/`

Role: offline knowledge system, agents, reasoning modules, RAG management, deployment stages, self-editing/evolution infrastructure, launchers, and UI.

Canonicality: historical baseline. Valuable, but not assumed production-safe. The newer semantic-core note describes future work that is not present in this archive.

Highest-value candidate modules for later selective integration:

- `src/reasoning/reasoning_guard.py`
- `src/reasoning/uncertainty_quantifier.py`
- `src/reasoning/output_quality.py`
- `src/reasoning/math_validator.py`
- `src/agents/orchestrator.py`
- `src/deployment/stages.py`
- `src/deployment/state.py`
- `src/deployment/repair.py`
- `src/rag_manager.py`
- `deploy_check.py`
- `src/self_editor.py` only after proof/sandbox gates

## Tier C - engineering/domain specification

### MASTERZIP v11
Paths:

- `20_DOMAIN_SPECIFICATIONS/MASTERZIP_v11_COMBINED_DETAILED.pdf`
- `20_DOMAIN_SPECIFICATIONS/MASTERZIP_v11_EXTRACTED_TEXT.txt`

Role: ALUM-BOO engineering knowledge, prototype scripts, FMEA, compliance concepts, blueprints, validation ladder, field protocols, inventory/cutting/pricing ideas.

Canonicality: canonical domain handover, but **not canonical evidence of implementation quality or physical validation**.

Current stage: VAL-0 / specification complete or in progress. VAL-1 remains blocked by geometry and hardware evidence.

## Tier D - future architecture/specifications

### WORDLIB semantic core update
Path: `30_RUNTIME_AND_MEMORY_DESIGNS/WORDLIB semantic core update.txt`

Role: next-spec order. It says deploy proof gates must precede tested patch execution sandbox work.

Status: instruction/specification only. The referenced cryptographic-binding archive is absent from this bundle.

### EtherAI Absorption System
Path: `30_RUNTIME_AND_MEMORY_DESIGNS/EtherAI Absorption System.txt`

Role: design record for a durable Redis Streams + SQLite WAL task runtime with at-least-once delivery and safe task types.

Status: narrative/verification summary only. The referenced starter ZIP and wheel are absent from the current filesystem and therefore are not included or claimed available.

### Semantic core setup note
Path: `30_RUNTIME_AND_MEMORY_DESIGNS/Consider best setup.txt`

Role: proposed future local model and memory architecture: one strong reasoning model, one small router, hybrid vector + graph memory.

Status: unimplemented recommendation. Hardware sizing and model selection require a fresh connected-machine assessment.

## Tier E - originals and rollback

Path: `90_ORIGINAL_UPLOADS/`

Contains every source artifact physically available in this conversation, unchanged. Use these files for provenance, rollback, and diffing.

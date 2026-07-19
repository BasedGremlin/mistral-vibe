# Merge and Execution Plan

## Recommended path: adapter-first federation

Do not combine all repositories into one unstructured tree. Use OKComputer as the orchestration shell and integrate the other systems through versioned adapters.

### Phase 0 - restore and verify

1. Unpack this bundle.
2. Verify `99_INTEGRITY/SHA256SUMS.txt`.
3. Run the integrated swarm's dependency install, type-check, tests, and build on a connected machine.
4. Confirm environment variables are server-only.
5. Export or inspect the live Supabase schema before applying any new migration.

Exit gate: clean build, passing tests, no secret leakage, state-machine tests green.

### Phase 1 - MASTERZIP capability audit

Create a registry for every T-tool and subsystem with these fields:

```text
id
name
implementation_path
implementation_class = real | simplified | placeholder | narrative_only
inputs
outputs
dependencies
validation_method
evidence_state
safety_class
allowed_execution_mode
blocking_requirements
```

Do not expose a tool to the swarm until its adapter validates inputs/outputs and its implementation class is known.

Exit gate: no T1-T28 item remains ambiguously labeled "validated" without implementation and evidence classification.

### Phase 2 - WORDLIB selective absorption

Integrate only bounded, testable modules:

1. reasoning guard
2. uncertainty quantifier
3. output-quality evaluator
4. math validator
5. deployment state/stages
6. RAG interfaces

Do not merge `self_editor.py` or autonomous evolution paths yet.

Required gate order:

```text
SPEC-CRYPTOGRAPHIC_BINDING
  -> SPEC-DEPLOY_PROOF_GATE
  -> SPEC-TESTED_PATCH_EXECUTION_SANDBOX
  -> human-approved self-edit integration
```

The current bundle contains only the deploy-proof instruction, not the cryptographic-binding implementation archive.

### Phase 3 - durable task runtime

Reconstruct or recover the EtherAI starter artifact, then integrate it as a worker plane:

```text
Swarm planner
  -> bounded task envelope
  -> durable outbox
  -> Redis Stream
  -> worker lease
  -> result/evidence record
  -> swarm validator
```

Permit only allowlisted task types. Do not reintroduce arbitrary shell execution.

### Phase 4 - hybrid memory

Recommended logical layers:

- Supabase/Postgres: authoritative run metadata, provenance, claims, approvals, checkpoints.
- LanceDB or equivalent local vector store: embeddings and multimodal retrieval.
- Graph layer: relationships, dependencies, evidence lineage, supersession.
- Local filesystem/object storage: model weights and large artifacts.

Do not make two databases co-authoritative for the same state. Each record class needs one owner.

### Phase 5 - physical engineering interface

The swarm may generate analyses, field sheets, cut lists, and test plans. It may not certify a build or sale. Physical stages require evidence ingestion, human witness/approval, and compliance gates.

Canonical physical validation sequence remains:

```text
VAL-0 specification
VAL-1 geometry verification
VAL-2 material/structural evidence
VAL-3 control simulation
VAL-4 unpowered mock-up
VAL-5 single-hinge powered test
VAL-6 integrated bench test
VAL-7 indoor RF test
VAL-8 controlled outdoor test
VAL-9 operational cycles
```

## Two implementation options

### Option A - recommended: federated repositories

Keep swarm, WORDLIB, EtherAI, and engineering specs separate. Connect them through schemas, task envelopes, adapters, and manifests.

Why recommended: smallest blast radius, clear ownership, easier rollback, preserves proof boundaries.

### Option B - monorepo

Move all code into packages under one repository with shared CI and contracts.

Use only after adapters and tests exist. A premature monorepo would hide provenance and make weak components look production-ready simply because they live beside strong ones.

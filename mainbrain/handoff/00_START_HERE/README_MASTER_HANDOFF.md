# WORDLIB Mainbrain - Consolidated Conversation Handoff MasterZIP v1

Generated: 2026-07-17
Owner: Johannes / Joe
Purpose: preserve the strongest executable files, specifications, decisions, provider state, and next-step logic from this conversation before it is merged.

## Start here: the five highest-signal facts

1. **Active software candidate:** `10_CANONICAL_WORKING_TREES/OKComputer_Swarm_Integrated_v1/OKComputer_Swarm_Integrated/` is the newest swarm implementation. It supersedes the original OKComputer archive for active development, while the original is retained unchanged under `90_ORIGINAL_UPLOADS/` for comparison and rollback.

2. **Foundation baseline:** `10_CANONICAL_WORKING_TREES/WORDLIB_v29_BASELINE/wordlib/` is the preserved WORDLIB v29 codebase. It is not automatically merged into the swarm. Its strongest reusable modules are orchestration, reasoning guards, uncertainty/quality evaluation, deployment staging, RAG management, and self-editing infrastructure. Any merge must pass proof and deploy gates.

3. **Engineering domain source:** `20_DOMAIN_SPECIFICATIONS/MASTERZIP_v11_COMBINED_DETAILED.pdf` is the ALUM-BOO engineering handover. It contains valuable domain rules, blueprints, FMEA, validation ladders, and prototype scripts, but it must be treated as **VAL-0 / specification state**, not as proof that physical performance, compliance, or commercial claims have been validated.

4. **Live control-plane work:** two Supabase migrations were applied during this conversation to project `dxyghtyjndylvfugutsr`, adding private swarm run/event/checkpoint tables and service-role-only RPC functions. The reproducible SQL is stored under `40_DATABASE_AND_PROVIDER_STATE/` and inside the integrated app.

5. **Correct next move:** run the integrated swarm on a connected machine, verify dependencies and tests, then use the first real request to audit MASTERZIP v11 into four classes: implemented code, placeholders, unsupported claims, and evidence required before VAL-1. Do not begin a broad codebase merge or physical build before that audit.

## Canonical architecture

```text
User / UI
  -> OKComputer Swarm Runtime
       -> OpenAI Agents SDK: primary planner, workers, validator, synthesizer
       -> Claude: optional adversarial critic only when a valid server-side API key exists
       -> Hugging Face Transformers.js: local semantic role router / embeddings
       -> Supabase: control-plane metadata, run events, checkpoints
       -> WORDLIB: future reasoning, memory, proof-gate, and deployment modules
       -> EtherAI Task Runtime: future durable worker queue, not present as an executable archive here
       -> MASTERZIP v11: engineering knowledge and validation rules, not auto-executable truth
```

Canonical swarm state machine:

```text
INTAKE -> PLAN -> ROUTE -> EXECUTE -> CRITIQUE -> VALIDATE -> PERSIST -> COMPLETE
                                      \---------------------------------> FAILED
```

## Exact next action

On a connected development machine:

```bash
cd 10_CANONICAL_WORKING_TREES/OKComputer_Swarm_Integrated_v1/OKComputer_Swarm_Integrated
cp .env.example .env
# Add credentials only to the local server environment. Never commit them.
npm install
npm run verify:integration
npm run db:push
npm run db:seed
npm run dev
```

First real swarm request:

> Audit MASTERZIP v11. Separate implemented code, placeholders, unsupported claims, and the exact evidence required before VAL-1.

## Read order

1. `CURRENT_STATE.xml`
2. `CANONICAL_SOURCE_MAP.md`
3. `HIGH_SIGNAL_CONVERSATION_RECORD.md`
4. `MERGE_AND_EXECUTION_PLAN.md`
5. `KNOWN_GAPS_AND_RISKS.md`
6. `CONTINUATION_PROMPT.xml`
7. `99_INTEGRITY/MASTER_MANIFEST.json`

## Integrity and honesty rules

- Never represent an uploaded narrative as an executable artifact unless the artifact is physically present in this bundle.
- Never promote MASTERZIP beyond its evidence-backed validation stage.
- Never expose provider keys to browser code, logs, prompts, or this bundle.
- Never merge WORDLIB self-editing capabilities into active execution without cryptographic binding, deploy proof gates, isolated patch testing, and explicit human approval.
- Preserve original archives unchanged for rollback and provenance.

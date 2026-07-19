# The Top 5 Conversations, Models, and Code

Ranked by executable weight and how much of the ecosystem depends on them.
Sources: the two uploaded packages, plus a live connector sweep (Google Drive,
Notion, Linear, Gmail) on 2026-07-17.

---

## 1. WORDLIB → OMEGA Megakernel — the offline brain

**Code (in hand):** `mainbrain/wordlib/` — the single largest, most evolved asset.

**Conversation thread:** `wordlib/CLAUDE_BRIEFING.md` — a 1,200-line evolution
log, v1 through v29, written as a running handoff between Claude sessions.
It is the highest-signal conversation in either package.

What the code actually contains, all verified-real per its own honesty log:

- `launcher.py` — the one brain: venv, services, hub, menu, one-hit install.
- `src/ether_core.py` — EtherCore blob brain; `EvolutionManager.evolve_files()`
  gives **atomic multi-file self-modification** with validate → snapshot →
  deploy → test → verified rollback (a real rollback bug was caught by the
  test suite and fixed at v13.8).
- `src/agents/` — ClawOrchestrator + 12 agents (Architect, Code, Test, Deploy,
  Guardian veto, Researcher, Reasoning, Math, Absorption, Gremlin propose-only,
  Market, EvolutionArchitect).
- `src/reasoning/` — 5-layer honest reasoning stack: output-quality guard,
  sympy math validator, ast code reasoner, structured-output repair+cache,
  Wilson/Brier/ECE uncertainty quantifier, plus quantum-*inspired* (classical,
  honestly labeled) optimizer and an Ollama LLM-as-judge.
- `src/deployment/` — stage engine: idempotent, resumable, retry w/ backoff,
  rollback, self-repair; absorption scanner + environment intelligence.
- `docking/` + `core/contracts/` + `deploy_check.py` (1,442 lines) — the
  spec/docking protocol with CNS deploy proof gates (see #3).
- `tests/` — 23 modules, pytest-free runner for USB deployment.
- Three WCAG 2.2 AA UIs: `/panel`, `/console` (reasoning-transparent),
  `/nephilim` (living orbital UI) — all guarded by tests that fail on any
  phantom endpoint.

**Models (local, confirmed tags):** `dolphin-2.9-mistral-7b` Q4_K_M (primary),
`dolphin3:8b-llama3.1-q4_K_M` (creative), `qwen2.5-coder:7b-instruct-q4_K_M`
(code), `Meta-Llama-3-8B-Instruct` Q4_K_M (classroom-safe),
`nomic-embed-text` (RAG embeddings).

---

## 2. OKComputer Swarm Integrated — the connected orchestration shell

**Code (in hand):** `mainbrain/okcomputer-swarm/` — React 18 + TypeScript +
tRPC + Drizzle + Vite, with the swarm runtime under `api/ai/`.

**Conversation thread:** `handoff/00_START_HERE/HIGH_SIGNAL_CONVERSATION_RECORD.md`
— the consolidation conversation that fused MASTERZIP domain knowledge with
the swarm shell and made five architectural decisions:

1. **OpenAI Agents SDK is primary** — planner, specialist workers, validator,
   synthesizer (`api/ai/openai-swarm.ts`, `execute-swarm.ts`).
2. **Claude is the adversarial critic**, never primary authority
   (`api/ai/claude-critic.ts`), output routed back into validation.
3. **Hugging Face is local-first** — Transformers.js semantic router with
   `mixedbread-ai/mxbai-embed-xsmall-v1`, remote loading disabled
   (`api/ai/hf-local-router.ts`).
4. **Supabase is the control plane, not bulk storage** —
   `control.swarm_runs` / `swarm_events` / `swarm_checkpoints` behind RLS with
   service-role-only RPCs (`SUPABASE_SWARM_CONTROL_MIGRATION.sql`, applied and
   smoke-tested live during the conversation).
5. **Canva is a documentation surface only** (4 operator-guide candidates).

The state machine (`api/ai/state-machine.ts` + its test):
`INTAKE → PLAN → ROUTE → EXECUTE → CRITIQUE → VALIDATE → PERSIST → COMPLETE | FAILED`.
Security corrections from the conversation: simulated provider outputs removed
as an execution path, credentials server-side only, auth + ownership required
on all run reads/writes.

---

## 3. Semantic Core + Docking Protocol — spec-driven self-improvement with proof gates

**Conversation thread:** `handoff/30_RUNTIME_AND_MEMORY_DESIGNS/WORDLIB semantic
core update.txt` — the fork-B decision ordering the gate chain:
`SPEC-CRYPTOGRAPHIC_BINDING` (done) → `SPEC-DEPLOY_PROOF_GATE` (ordered) →
`SPEC-TESTED_PATCH_EXECUTION_SANDBOX` (next wound to close).

**Code (in hand, inside `mainbrain/wordlib/`):** this conversation was
*implemented* in the OMEGA tree — the clearest proof OMEGA supersedes the
Babafile baseline:

- `docking/` — spec registry, lifecycle, validator, auditor, patch applier,
  failure memory, side letters, improvement pipeline.
- `core/contracts/docking/` — typed contracts: SpecDocument, PatchPayload,
  ImprovementProposal/Record, FailureRecord, ChangeTrace, SideLetter.
- `deploy_check.py` grew 319 → 1,442 lines: deploy-time CNS proof-gate checks
  (`canonical_patch_digest()` determinism, digest-mismatch rejection, no
  whitelist/approval bypass, `--json` mode, non-zero exit on gate failure).
- Tests: `test_docking_protocol.py`, `test_patch_payload.py`,
  `test_sideletter_protocol.py`, `test_closed_loop_improvement.py`, etc.

**Models thread:** `Consider best setup.txt` — the upgrade recommendation:
one ~32B-class reasoning brain (Qwen3.5-32B quantized) + a 7–9B fast router,
and a hybrid **LanceDB (vectors) + FalkorDB/Neo4j (graph/ontology)** semantic
core instead of a plain vector DB.

---

## 4. EtherAI Absorption System v11 — the durable task runtime (design in hand, artifact missing)

**Conversation thread:** `handoff/30_RUNTIME_AND_MEMORY_DESIGNS/EtherAI
Absorption System.txt` — a complete production design record:

- Redis Streams consumer-group dispatch, `XREADGROUP` + `XAUTOCLAIM` crash
  recovery, SQLite WAL transactional task **outbox**, worker leases,
  dead-letter records, health-gated Compose startup.
- Honest **at-least-once** delivery claim (not exactly-once), duplicate window
  controlled by stable task_id + leases + terminal-state dedup.
- Wolfram-verified retry policy: delays 1/2/4/8/16s, deterministic ±20% jitter
  from `SHA-256(task_id + attempt)`, reclaim threshold 60s.
- Security correction: the proposed `/execute_verified` arbitrary-shell
  endpoint was **removed**; only `absorb_text` and `verify_artifact` remain.

**Status:** the v11 starter zip/wheel referenced by the record is **not present
in any package** (`handoff/00_START_HERE/MISSING_ARTIFACTS.md`).

**Rebuilt:** `mainbrain/ether-runtime/` now implements the v11 durability model
from this record — pure stdlib, fully offline: SQLite WAL journal +
transactional outbox, consumer-group stream with 60s idle reclaim, execution
leases, the exact 1/2/4/8/16s ±20% deterministic-jitter retry ladder,
dead-lettering, and only the two validated task types. 24 tests prove the
outbox atomicity, the at-least-once duplicate window, lease exclusion, and the
retry math. Redis/HTTP layers remain honest future adapters — see its README.

**Integrated:** wordlib's swarm now reaches this runtime through
`DispatchAgent` (agent #13, `wordlib/src/agents/dispatch_agent.py`) — the
merge plan's Phase-3 "swarm planner → bounded task envelope → durable outbox →
worker lease → result record" loop, adapter-first: wordlib degrades honestly
when the runtime package is absent.

---

## 5. MASTERZIP v11 / ALUM-BOO — the engineering domain spec (VAL-0)

**Document (in hand):** `handoff/20_DOMAIN_SPECIFICATIONS/` — the combined
engineering handover PDF + extracted text: domain rules, blueprints, FMEA,
validation ladders, T1–T28 tool concepts, prototype scripts.

**Standing order from the conversation record:** treat as **VAL-0 /
specification state**. The first real swarm request is the audit:

> Audit MASTERZIP v11. Separate implemented code, placeholders, unsupported
> claims, and the exact evidence required before VAL-1.

Physical validation ladder VAL-0 → VAL-9 (geometry → materials → control sim →
mock-up → powered tests → RF → operational cycles). The swarm may generate
analyses and test plans; it may not certify a build or sale.

**Connector context:** Drive also holds `ALUMBOO_R17_MASTERFILE.md` (2026-07-15)
— the strategy pivot to the aluminum-glass cash-core (AGFS) with Class-A/Class-B
feedstock separation. Same doctrine: no structural claims without tests.

---

## Beyond the zips: the live frontier (connector sweep, 2026-07-17)

The newest *receipts* found in connectors — code for these stayed in chat
handoffs and should be recovered next:

| Version | Where found | Evidence |
| --- | --- | --- |
| v30 Mainbrain release | Drive doc + Notion pages | 103/103 tests, artifact SHA-256 list, deployer SKILL.md |
| v31 MARM + Filesystem MCP | Notion cockpit + evidence pages | 118/118 tests, dual-STDIO sidecar architecture |
| v32 Memory Integrity | Drive doc + Linear project | 132/132 tests, Wolfram stability kernel, Black Vault repair-first plan; MOH-17 ✅, MOH-16 🔄, MOH-18 ⏳, MOH-19 ⛔ |

The `mainbrain/` tree in this repo is the newest **executable** consolidation
of everything above.

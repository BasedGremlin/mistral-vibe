# MAINBRAIN — Unified Best-of-Both Build

Assembled 2026-07-17 from two uploaded packages:

- `Babafile.zip` → `CONVERSATION_HANDOFF_MASTERZIP_v1` (conversation handoff: docs, baseline trees, the OKComputer swarm app)
- `OMEGA_MEGAKERNEL_PACKAGE.zip` → the evolved WORDLIB tree (semantic core + docking protocol era)

This directory is the merge of the strongest parts of both, with duplicates
eliminated by provenance analysis rather than guesswork.

## Layout

```text
mainbrain/
  wordlib/            The OMEGA Megakernel WORDLIB tree (canonical, newest in hand).
                      Offline-first AI workstation: launcher brain, ETHER AI Flask hub,
                      12-agent swarm, 5-layer reasoning stack, atomic self-evolution
                      with rollback, deployment stage engine, docking/spec protocol,
                      CNS deploy proof gates, 23 test modules.
  okcomputer-swarm/   OKComputer Swarm Integrated (from Babafile). React/TypeScript/
                      tRPC/Drizzle shell: OpenAI Agents SDK planner-worker-validator-
                      synthesizer, Claude as adversarial critic, Hugging Face
                      Transformers.js local embeddings, Supabase control plane.
  ether-runtime/      Pure-stdlib durable task runtime — offline reconstruction of
                      the missing EtherAI Absorption v11 artifact (top-5 #4): SQLite
                      WAL journal + transactional outbox, consumer-group stream with
                      idle reclaim, deterministic jittered retries, allowlisted task
                      types, at-least-once with terminal-state dedup. 24 tests.
  handoff/            The conversation-handoff record: start-here docs, the three
                      runtime/memory design conversations, MASTERZIP v11 domain spec,
                      and integrity manifests of the original bundle.
  TOP5.md             The top-5 conversations/models/code, presented in detail.
```

## De-duplication decisions (what was NOT copied, and why)

1. **`WORDLIB_v29_BASELINE` (Babafile) — dropped.** A full recursive diff against
   the OMEGA tree showed zero unique files: every baseline file exists in OMEGA,
   and all 8 differing files are strictly newer/larger in OMEGA (e.g.
   `deploy_check.py` 319 → 1,442 lines with the CNS proof-gate work). The only
   baseline-unique content was `__pycache__` bytecode.
2. **`90_ORIGINAL_UPLOADS` — dropped.** Retained in the original zip for rollback;
   every member is superseded by a canonical working tree or a handoff doc here.
3. **`40_DATABASE_AND_PROVIDER_STATE` — dropped.** All four files are
   byte-identical to copies shipped inside `okcomputer-swarm/` (verified with
   `cmp`). The operative copies live with the app.
4. **Runtime state excluded by the tree's own `.gitignore`**: 245 self-editor
   `.bak` snapshots, event/genome/memory JSON, logs. These are machine-specific
   and regenerated; the self-healer recreates missing directories on boot.

## How the two worlds fit (adapter-first federation)

Per `handoff/00_START_HERE/MERGE_AND_EXECUTION_PLAN.md`: OKComputer is the
connected orchestration shell; WORDLIB is the offline reasoning/memory/proof
foundation. They federate through adapters and evidence gates — not by pasting
one tree into the other.

```text
User / UI
  -> okcomputer-swarm (connected shell)
       -> OpenAI Agents SDK: planner, workers, validator, synthesizer
       -> Claude: adversarial critic (server-side key only)
       -> Transformers.js: local semantic routing (mxbai-embed-xsmall-v1)
       -> Supabase: control.swarm_runs / swarm_events / swarm_checkpoints
  -> wordlib (offline brain)
       -> ETHER AI hub (Flask, :5757) + RAG
       -> 12-agent swarm, reasoning guards, uncertainty quantifier
       -> EvolutionManager: atomic multi-file self-edit with verified rollback
       -> docking/: spec protocol, patch payloads, CNS deploy proof gates
```

Swarm state machine (both worlds observe it):
`INTAKE -> PLAN -> ROUTE -> EXECUTE -> CRITIQUE -> VALIDATE -> PERSIST -> COMPLETE | FAILED`

## Quickstarts

**wordlib** (offline brain; Windows-first, Linux parity):

```text
START_HERE.bat        one-time polished auto-install (8 stages)
RUN_ME.bat            daily driver menu
python tests/run_tests.py   test suite without pytest
```

**okcomputer-swarm** (connected shell; needs Node + server-side keys):

```bash
cd okcomputer-swarm
cp .env.example .env   # keys go in the server environment only, never committed
npm install && npm run verify:integration && npm run dev
```

## Safety rules carried over (non-negotiable)

- Never expose provider keys to browser code, logs, prompts, or this repo.
- Never merge WORDLIB self-editing into active execution without the gate order:
  `SPEC-CRYPTOGRAPHIC_BINDING -> SPEC-DEPLOY_PROOF_GATE ->
  SPEC-TESTED_PATCH_EXECUTION_SANDBOX -> human approval`.
- MASTERZIP v11 stays **VAL-0 / specification state**: audit it into implemented
  code / placeholders / unsupported claims / evidence-required before any
  physical or commercial claim.
- GremlinAgent stays propose-only (Theater Mode); GuardianAgent veto stands.

## The frontier beyond this snapshot

Connector sweep on 2026-07-17 found the ecosystem has release *receipts* newer
than any code in hand — the artifacts themselves stayed in chat handoffs:

- **v30 Mainbrain** release receipt (Drive) — 103/103 tests, Codex Masterfile hashes.
- **v31 MARM + Filesystem MCP** (Notion) — 118/118 tests, sidecar architecture.
- **v32 Memory Integrity** (Drive doc + Linear project `WORDLIB Memory Integrity
  v32`) — 132/132 tests, Wolfram-verified retry/stability kernel, Black Vault
  repair-first plan. Linear: MOH-17 done, MOH-16 in progress, MOH-18 todo,
  MOH-19 blocked.

This `mainbrain/` tree is therefore the newest **executable** consolidation;
the v30–v32 receipts document work whose code should be recovered from those
chat handoffs and layered on top, gate by gate.

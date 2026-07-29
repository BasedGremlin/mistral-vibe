# MAINBRAIN — Engineering Handover

**For:** a successor agent (GPT or otherwise) taking over this project.
**From:** the Claude session that built the current state.
**Date:** 2026-07-29
**Repo:** `johannesphilipp3-ai/mistral-vibe`, branch `claude/top-conversations-models-t3z66v`, PR #2.

Read this file top to bottom before touching anything. It is written to be
executable, not inspirational. Every number in it was re-derived from the tree,
not recalled.

---

## 0. The one rule that matters

**Evidence outranks confident narrative.**

This project's entire value is that it refuses to claim what it has not
measured. Prior handoffs in this lineage were littered with phantom files,
"already generated" artifacts that did not exist, and green badges nobody ran.
Every safety rail here exists because one of those bit someone.

Concretely, and non-negotiably:

- A passing test is **not** a live provider run.
- A passing `deploy_check` is **not** a physical or commercial certification.
- A proposal is **not** an applied patch.
- If you cannot show the command that proves a claim, do not make the claim.
- If a document and the tree disagree, **the tree is right** — fix the document.

You will be tempted to "tidy" this discipline away. Don't. It is the product.

---

## 1. What this system is

Three components plus the conversation record they came from, in one tree at
`mainbrain/`:

| Path | What | Language | State |
| --- | --- | --- | --- |
| `wordlib/` | Offline-first AI workstation — the brain | Python, 111 files | Deployed + verified live |
| `okcomputer-swarm/` | Connected orchestration shell | TypeScript, 99 files | Typechecks clean in CI |
| `ether-runtime/` | Durable task runtime | Python, ~1.4k LOC | Built, tested, SQLite + Redis |
| `handoff/` | Conversation record + MASTERZIP v11 spec | Docs | Reference only (**VAL-0**) |

### The loop, end to end

```
request
  → okcomputer-swarm         OpenAI planner → workers → Claude critic
                             → validator → synthesizer
                             (Supabase control plane, RLS + service-role RPC)
  → wordlib                  ETHER AI hub (Flask :5757) + RAG
                             13-agent swarm, 5-layer reasoning stack
                             EvolutionManager: atomic self-edit + rollback
                             docking/: spec protocol + CNS proof gates
  → ether-runtime            DispatchAgent journals a bounded envelope
                             → outbox → stream → worker lease → result
```

State machine both worlds observe:
`INTAKE → PLAN → ROUTE → EXECUTE → CRITIQUE → VALIDATE → PERSIST → COMPLETE | FAILED`

---

## 2. Verified state (re-derive these; do not trust them)

| Metric | Value | Command that proves it |
| --- | --- | --- |
| wordlib suite | **280 passed** (68+61+38+113) | `cd mainbrain/wordlib && python3 tests/run_tests.py` |
| ether-runtime suite | **56 passed** | `cd mainbrain/ether-runtime && python3 -m pytest -q` |
| CNS proof gates | pass, exit 0 | `cd mainbrain/wordlib && python3 deploy_check.py --json` |
| Swarm typecheck | 0 errors | `cd mainbrain/okcomputer-swarm && npm ci && npx tsc --noEmit -p tsconfig.json` |
| CI | 3/3 jobs green | `.github/workflows/mainbrain-ci.yml` |
| Deployment | 9/9 stages, hub live | `python3 start_here.py --quiet` then `curl :5757/api/core/status` |

**Test dependencies** (install first, or everything looks broken):
```bash
pip install pytest pydantic sympy flask numpy pillow psutil
```

**Gotcha:** `tests/run_tests.py` shells out to `pytest` on `PATH`. If a
different interpreter owns that binary you get `unrecognized arguments`. Use:
```bash
PATH=/usr/local/bin:$PATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 tests/run_tests.py
```

---

## 3. Git and directory layout

```
/home/user/mistral-vibe/            ← host repo (Mistral's "vibe" CLI, NOT ours)
├── .github/workflows/
│   ├── ci.yml                      ← host's own CI (do not touch)
│   └── mainbrain-ci.yml            ← OURS, path-scoped to mainbrain/**
├── .claude/agents/                 ← 4 operating agents (see §6)
├── pyproject.toml                  ← testpaths=["tests"] keeps host CI off our tree
├── .pre-commit-config.yaml         ← exclude: ^mainbrain/
└── mainbrain/                      ← EVERYTHING OURS LIVES HERE
    ├── wordlib/                    ← the brain
    ├── okcomputer-swarm/           ← the shell
    ├── ether-runtime/              ← the worker plane
    ├── handoff/                    ← provenance (VAL-0)
    ├── docs/                       ← .docx + its generator
    ├── skills/mainbrain-workflow/  ← the standing operating loop
    ├── README.md, TOP5.md, HANDOVER_GPT.md
```

### Vendored-tree guards — understand these before editing config

`mainbrain/` is a **vendored tree inside someone else's repo**. Three guards
keep the two worlds from fighting. Breaking any one of them turns the host's CI
red:

1. `pyproject.toml` → `testpaths = ["tests"]` — stops host pytest collecting our
   suites (they have their own deps and would error).
2. `.pre-commit-config.yaml` → `exclude: ^mainbrain/` — stops host lint/format
   rewriting vendored code.
3. `mainbrain/.gitignore` → `!**/lib/` — the host `.gitignore` has an unanchored
   `lib/` rule that would otherwise swallow `okcomputer-swarm/api/lib/` and
   `src/lib/`.

### Git workflow

```bash
git fetch origin main
git checkout -B <your-branch> origin/main      # if the prior PR merged, restart from main
# ... work ...
cd mainbrain/wordlib && git checkout -- docking/   # ALWAYS: restore ledgers after tests
git add mainbrain/ && git commit && git push -u origin <your-branch>
```

**Never merge to `main` yourself.** Open a draft PR; a human merges.

---

## 4. The gate chain — the heart of the system

Self-modification is real here, so it is gated. **Order is load-bearing; do not
reorder or skip.**

```
SPEC-CRYPTOGRAPHIC_BINDING          ✅ done   digest proves content applied == content tested
  → SPEC-DEPLOY_PROOF_GATE          ✅ done   deploy_check enforces gates, non-zero exit
    → SPEC-TESTED_PATCH_EXECUTION_SANDBOX  ✅ done   proves WHERE it was tested
      → redis adapter               ✅ done   distributed worker plane
        → hybrid memory + live brain ⬜ next   LanceDB + graph + 32B/router
```

### `apply_patch_payload()` gate order (`docking/improvement/patch_applier.py`)

```
1.    validate PatchPayload contract
2-3.  linked ImprovementRecord exists + test_result.passed
4-7.  digest chain: tested_patch_digest == patch_payload_hash
7.5.  sandbox_verified is True          ← isolation proof
8.    expected_hash_before matches current file
9.    SelfEditor whitelist
10.   human approval
11.   SelfEditor (the ONLY write path)
```

**Why 7.5 sits where it does:** a digest proves the content applied is the
content tested. It says *nothing about where it was tested*. Without this gate a
digest produced against the live tree still satisfies 4–7. It is placed
**before** the hash, whitelist, and human gates so that a correct file hash, a
whitelisted path, or a human signature cannot substitute for isolation proof. A
test asserts this ordering — if you move it, that test fails, and it should.

### The sandbox (`docking/improvement/sandbox.py`)

`materialize → apply (candidate only) → test (cwd=candidate) → promote`

The distinctive property: it **fingerprints the live tree before and after every
run**. Isolation is *measured per run*, not asserted. `sandbox_verified` is
stamped from `promotable`, which requires green tests **and** an unchanged
fingerprint.

> Historical note worth keeping: the uploaded GREMLIN conglomerate implemented
> the same spec, and its `live_repo_untouched` was a hardcoded `True` documented
> "Always True by construction". That is an assertion, not evidence. We ported
> its (superior) enforcement onto our (superior) proof. Don't regress to a
> constant.

`promote()` requires **all** of: promotable result + explicit `approved_by`
token + exact changeset match. No overrides.

---

## 5. Deployment

**Rollback-safe, always.** Never install over an existing deployment.

```bash
DEPLOY=/home/user/deploy/MAINBRAIN_DEPLOY_$(date +%Y-%m-%d_%H%M)
mkdir -p "$DEPLOY"
cd /home/user/mistral-vibe/mainbrain
tar -cf - --exclude='__pycache__' --exclude='.pytest_cache' wordlib ether-runtime \
  | tar -C "$DEPLOY" -xf -
cd "$DEPLOY/wordlib" && python3 start_here.py --quiet
```

Keep `wordlib/` and `ether-runtime/` **side by side** — `DispatchAgent` resolves
its sibling by relative path and will honestly report unavailable if separated.

**9 stages:** `preflight → venv → core_packages → [rag_packages] → [ollama] →
[services] → hub → [rag_index] → [absorption]`. Bracketed = optional.
**`ollama` skipping without a binary is correct behaviour, not a failure.**

**Four live proofs** (a green suite is not a working system):
1. `curl -s --noproxy 127.0.0.1 http://127.0.0.1:5757/api/core/status`
2. `./.venv/bin/python deploy_check.py --json` → exit 0
3. dispatch → drain → status → `completed`
4. dispatch an `execute_shell` envelope → **must be rejected at submit**

If proof 4 ever succeeds, stop everything and treat it as a critical security
finding.

**Environment boundary:** container deployment proves the automated chain, not
the physical Windows/USB install. Windows users get the same experience from one
double-click of `START_HERE.bat`.

---

## 6. The four operating agents (`.claude/agents/`)

| Agent | Job | Hard rule |
| --- | --- | --- |
| `mainbrain-verifier` | Both suites + proof gates + ledger drift | Reports, never repairs |
| `weakness-auditor` | Re-derives the weakness map from the tree | Every finding needs a command; closes fixed items |
| `patch-sandbox-runner` | Drives the Phase 3 gate | Never promotes on its own initiative |
| `deploy-smoke` | Rollback-safe deploy + the four proofs | Never overwrites a deployment |

**They load at session start.** If you add or edit one mid-session it will not
be dispatchable until restart — run its procedure manually instead.

If your runtime is not Claude Code, these are still valuable as **checklists**:
each file is a complete, executable procedure in prose.

---

## 7. Known weaknesses — honest, ranked

| ID | Weakness | Sev | Fix |
| --- | --- | --- | --- |
| W-01 | Live provider runs never executed | Critical | Keyed staging; capture one real trace as evidence |
| W-03 | ~~Single-node runtime~~ → Redis adapter unproven vs a **live server** | High | Integration run against real Redis |
| W-06 | Local inference unproven (no Ollama/GGUF here) | High | Document model pull; degraded-vs-live probe |
| W-07 | Physical claims unverified | High | **Keep VAL-0.** Audit before any claim |
| W-08 | Path centralization: 48 files pending | Medium | Migrate to `core.paths` (non-blocking, mechanical) |
| W-09 | v30–v32 code exists only in chat handoffs | Medium | Recover from receipts, layer gate by gate |
| W-10 | Hybrid memory (LanceDB + graph) not built | Medium | Next roadmap phase |

**Closed this session:** W-02 (sandbox), W-04 (swarm measured), W-05 (live CI),
W-11 (`ajv-formats` pinned, `npm ci` deterministic).

**Correction to inherited docs:** W-08 was documented as "22 pending". Actual
count is **48** — the earlier figure predated tree growth. Re-derive with
`python3 -c "from core.paths import migration_report; print(migration_report())"`.
Treat every inherited number this way.

---

## 8. Traps that will bite you

1. **Tests append to committed ledgers.** `docking/**/*.jsonl` are append-only
   audit logs; the suite writes to them. Always
   `git checkout -- mainbrain/wordlib/docking/` before committing. CI reports
   this drift and restores it, but hard-fails on *any other* source change.
2. **`npm ci` needs the `overrides` block.** `package.json` pins
   `ajv-formats: 2.1.1`; without it `npm ci` dies with EUSAGE on a transitive
   conflict. Never commit a lockfile `npm ci` rejects — that advertises
   reproducibility the tree cannot deliver.
3. **`node_modules` is 1.3 GB.** Regenerable via `npm ci`. Never ship it.
4. **Don't reorder the gate chain.** Each gate makes the next safe.
5. **Beware "already generated" claims** in any inherited document. This lineage
   has a documented history of phantom artifacts. Verify the file exists.
6. **`start_here.py` internet probe** uses a proxy-aware HTTPS fallback; a raw
   socket probe fails on proxy-only networks (school/corporate/cloud).

---

## 9. Your first hour

```bash
# 1. Ground truth
cd /home/user/mistral-vibe && git log --oneline -5 && git status --porcelain

# 2. Prove the tree is green (never trust a doc, including this one)
pip install pytest pydantic sympy flask numpy pillow psutil
cd mainbrain/wordlib && PATH=/usr/local/bin:$PATH python3 tests/run_tests.py
cd ../ether-runtime && python3 -m pytest -q
cd ../wordlib && python3 deploy_check.py --json

# 3. Restore ledgers
cd /home/user/mistral-vibe && git checkout -- mainbrain/wordlib/docking/

# 4. Re-derive the weakness map yourself
cd mainbrain/wordlib && python3 -c "from core.paths import migration_report; print(migration_report())"

# 5. Read, in order
#    mainbrain/README.md → TOP5.md → skills/mainbrain-workflow/SKILL.md
#    handoff/00_START_HERE/MERGE_AND_EXECUTION_PLAN.md
```

Then pick the next roadmap item — **hybrid memory (W-10)** — or close a Medium
weakness. Do not start a broad refactor; the doctrine is small gated changes
with evidence.

---

## 10. The standing workflow

`mainbrain/skills/mainbrain-workflow/SKILL.md` encodes the loop:

**sense → verify → audit → document → propose**

Propose-only. A human approves every applied patch and every merge. A weekly
routine runs this and opens a draft PR *only if something changed*.

### Never automate these
- Self-edit apply (propose-only; Theater Mode stays on)
- Physical/commercial claims (VAL-0 until real evidence)
- Provider keys (server-side only — never in browser, logs, prompts, or repo)
- Merge to `main`

---

## 11. If you are not Claude Code

Everything here is portable. The Python stack, tests, proof gates, deployment,
and CI are plain tooling. Only two things are Claude-specific:

- `.claude/agents/*.md` — read them as checklists; the procedures are explicit.
- `skills/mainbrain-workflow/SKILL.md` — a runbook in prose.

**Do not port the Python runtime to another language** because a spec says so.
One inherited handoff instructed building a TypeScript `IStoreAdapter` inside
`ether-runtime`; there is no TypeScript in that package and no such interface.
Building it would have created a second untested surface for nothing. **When a
spec and the tree disagree, the tree wins — say so plainly and build what is
real.**

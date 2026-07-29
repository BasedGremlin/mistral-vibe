---
name: mainbrain-workflow
description: The standing operating loop for the MAINBRAIN tree — verify, test, proof-gate, audit weaknesses, regenerate documentation, and propose gated fixes. Use when asked to run the MAINBRAIN workflow, do a health/upgrade pass, refresh the docs, or automate maintenance of mainbrain/. High documentation, high automation, honest gates.
---

# MAINBRAIN Workflow

The automatic strategy for keeping MAINBRAIN tested, documented, and improving —
with humans only at the gates that matter. Every step is honest: a green test
is not a live provider run; a passing proof gate is not a physical
certification; a proposal is not an applied patch.

## Golden rules (never break)

1. **Propose, never auto-apply.** GremlinAgent / self-edit stays propose-only
   (Theater Mode). A human approves every applied patch and every merge to main.
2. **Rollback-safe.** Deploy to a NEW directory; never overwrite the only copy.
   Restore `docking/*.jsonl` ledgers to pristine after any test run before commit.
3. **Keep provider keys server-side.** Never in browser, logs, prompts, or repo.
4. **MASTERZIP stays VAL-0.** No physical or commercial claim without logged evidence.
5. **Numbers are re-derived, never asserted.** Regenerate metrics from source.

## The loop (run top to bottom)

### 1. Sense
- Fetch latest `main`; check open PR + CI state for the working branch.
- If the designated branch's PR merged, restart the branch from `main` for new work.

### 2. Verify
```bash
# wordlib suite (pytest-free grouped runner)
cd mainbrain/wordlib && PATH=/usr/local/bin:$PATH python3 tests/run_tests.py
# ether-runtime suite
cd mainbrain/ether-runtime && python3 -m pytest -q
# proof gates (exit non-zero on failure)
cd mainbrain/wordlib && python3 deploy_check.py --json
```
Red stops the loop with the exact fix — do not proceed to propose on a red tree.
Note: `pydantic sympy flask numpy pillow psutil pytest` are test deps; install
if missing. `PatchPayload` rejects the all-zeros sentinel digest — keep it.

### 3. Deploy (optional, on request)
```bash
cp -r mainbrain /home/user/deploy/MAINBRAIN_DEPLOY_<date>   # rollback-safe
cd .../wordlib && python3 start_here.py --quiet             # 9 stages, exit 0
curl -s 127.0.0.1:5757/api/core/status                      # hub live check
```
Ollama honestly skips without a binary. The internet probe is proxy-aware.

### 4. Audit weaknesses
Re-derive the weakness map from the tree — do not trust a stale copy:
- AST-scan `wordlib/src` for bare stubs / parse errors.
- Grep for files still doing independent path discovery vs `core.paths` (W-08).
- Check whether a live CI workflow exists (W-05) and the swarm has a Node build (W-04).
- The current map lives in `mainbrain/docs/MAINBRAIN_Documentation.docx` and the
  Notion "Weakness Map & Upgrade Roadmap" page — update both if it drifted.

### 5. Document
Regenerate from source of truth (this is `doc-autogen`):
- `mainbrain/docs/MAINBRAIN_Documentation.docx` — via the docx generator script.
- The Notion hub "MAINBRAIN — Master Documentation Hub" and its child pages.
- Append a dated entry to `mainbrain/wordlib/CLAUDE_BRIEFING.md` (the tree's
  own evolution-log convention) for any code change.

### 6. Propose
- Small, gated fix on the designated branch as a **draft PR** (never auto-merge).
- Subscribe to PR activity; babysit CI until green; surface anything ambiguous
  via a question rather than guessing.

## The upgrade gate chain (order is load-bearing)

```
SPEC-CRYPTOGRAPHIC_BINDING (done)
  -> SPEC-DEPLOY_PROOF_GATE (done)
    -> SPEC-TESTED_PATCH_EXECUTION_SANDBOX (next — makes autonomous self-edit safe)
      -> redis adapter (distributed worker plane)
        -> LanceDB + graph + 32B/router (hybrid memory + live brain)
```

Do not skip ahead: each gate makes the next one safe to build.

## Companion skills to grow

- `mainbrain-deployer` — steps 2–3 as one command with a receipt.
- `weakness-auditor` — step 4 standalone; emits the ranked map.
- `doc-autogen` — step 5 standalone; .docx + Notion from source.
- `envelope-runner` — push bounded `verify_artifact` jobs through ether-runtime
  as a self-check of the durable worker plane.

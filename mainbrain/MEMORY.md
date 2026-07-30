# MAINBRAIN — Memory

Brief, falsifiable, dated. Every claim below can be re-checked by running the
command next to it — that is the point of this file. If a future thread
(this one, a fresh one, or another AI) needs "where are we," read this first;
read `HANDOVER_GPT.md` for the full handoff, `wordlib/CLAUDE_BRIEFING.md` for
the dated evolution log, and the Notion "MAINBRAIN — Master Documentation
Hub" for the deep-dive version. Don't trust any external status claim about
this project — including this file, if it's gone stale — without re-deriving
it; see `.claude/skills/verify-and-absorb/SKILL.md`.

**Last verified:** 2026-07-30. **Main:** `b7440b1` (PRs #2, #3, #4 all merged).

## What this is

Two uploaded AI-package handoffs (GREMLIN conglomerate + wordlib) fused into
one working tree at `mainbrain/`, plus `ether-runtime` (a durable offline task
runtime built from scratch) wired in as a bounded worker plane via
`DispatchAgent`.

## Current verified state

| Claim | Check it yourself |
|---|---|
| wordlib: **337** tests green | `cd mainbrain/wordlib && python3 tests/run_tests.py` |
| ether-runtime: 56 tests green | `cd mainbrain/ether-runtime && python3 -m pytest -q` |
| Proof gates pass, 0 syntax errors | `cd mainbrain/wordlib && python3 deploy_check.py --json` |
| No quality drift vs committed baseline | `cd mainbrain/wordlib && python3 quality_watch.py` |
| Recovery procedure exists and its commands are real | `mainbrain/ROLLBACK.md` |
| mainbrain-only PRs run 3 checks in ~100s, not 22 in ~6min | measured on PR #4 |
| Redis adapter proven against a **real** server, not just a double | 47/47 live parity tests; CI runs a `redis:7-alpine` service container with an anti-silent-skip guard |
| Deploy is live | `/home/user/deploy/MAINBRAIN_DEPLOY_2026-07-30_0406`; hub on `:5757`, `curl 127.0.0.1:5757/api/core/status` → 8/8 capabilities |
| Security boundary holds | dispatching `{"kind":"execute_shell",...}` is rejected at submit — allowlist is `absorb_text`, `verify_artifact` only |
| PR #2 | open, ready for review, mainbrain-ci green — merge pending final CI confirmation |

## Things explicitly rejected (and why — don't re-absorb them)

- **A "Gemini handover" package** (`CLAUDE_HANDOVER_FINAL_PACKAGE.zip`, 2026-07-30): every code module was a non-functional stub (`assert True` as its only "test"). Two claims were actively false: it claimed live Ollama `llama3.2` inference (no Ollama binary exists in this deploy — confirmed twice) and claimed OKComputer is unbuildable (CI shows that job green). Discarded in full.
- **Drive already has other MAINBRAIN-adjacent docs in this same ungrounded style** — a "MASTERZIP v12" bible, "Kekos Main Brain," several connector stubs with confident narrative and no runnable substance behind them. Treat anything found there the same way: verify before trusting, per the skill above.

## POLICYGATE/WORDLIB is a different project — decided, not merged

A third Claude Code thread, working `BasedGremlin/POLICYGATE` (a separate repo,
separate account tier from this one — confirmed by a hard `add_repo` lockout,
not assumption), answered a sync-request template meant for two other named
threads. Its self-report (233/233 tests, a RAG failure-diagnosis layer, a real
CI coverage gap closed, a corrupted onboarding script recovered) is **not
independently verified by this thread** — this session cannot reach that repo
without starting fresh scoped to it, the exact mirror of why that thread
couldn't verify this one's claims either.

Both "MAINBRAIN" projects trace back to a common `MAINBRAIN_HANDOVER_v1.zip`
and have since diverged. **Owner decision, 2026-07-30: keep them separate.**
Not one lineage that drifted apart by accident — two intentionally distinct
projects sharing a name. No cross-repo merging. Full record:
[Notion — Master Documentation Hub, "Legacy-thread sync"](https://app.notion.com/p/3ac55018fa378145a442e6ec5c76c028).

## Flagged weaknesses (re-derived 2026-07-30, each one evidenced)

Ranked by blast radius. Anything I could not evidence from the tree is marked
as such rather than stated as fact.

| # | Weakness | Evidence | Status |
|---|---|---|---|
| A | `tests/run_tests.py` shelled out to a bare `pytest` off `PATH` instead of the interpreter running it, so a "green" result could come from a different environment than the one under test | reproduced: a venv with pydantic installed still failed collection with `ModuleNotFoundError: pydantic` | **FIXED** this session — now `sys.executable -m pytest`, verified green in both the venv that previously failed and the original path |
| B | Test-coverage gap in the reasoning layer. **The original "~20 of 45 files" figure was wrong** — it came from a naive substring grep. Re-checked: `math_validator`, `uncertainty_quantifier`, `reasoning_engine` *are* covered by `test_reasoning.py`. The real gap was exactly 2 modules: `reasoning_guard.py` and `prometheus_judge.py` | per-module grep across `tests/`, then reading `test_reasoning.py`'s import list | **FIXED** — 22 tests added; writing them surfaced 3 real scoring bugs (see F) |
| F | **Exploitable eval sandbox escape** in `math_validator.py`'s fallback path. `eval()` with `{"__builtins__": {}}` permits attribute access, so an expression can reach any loaded class and out to the interpreter. This module is *designed* to receive untrusted model output | demonstrated returning a real directory listing via `().__class__.__mro__[1].__subclasses__()` → `BuiltinImporter` → `os.listdir` | **FIXED** — replaced with an AST allowlist (`ast.Attribute` absent by construction); 35 regression tests |
| G | `PrometheusJudge` divided model-supplied scores by 10 with no validation | measured: `50`→168%, `-30`→negative, `"excellent"`→`ValueError` past every fallback | **FIXED** — clamped + typed, all degraded paths routed through one labelled fallback |
| H | **A repo fix is not a deployed fix.** After fixing F, the running deployment at `MAINBRAIN_DEPLOY_2026-07-30_0406` was still vulnerable — it was built from an earlier commit | ran the escape against the deployed copy: still returned `ok=True` | Redeployed from `b7440b1`; **always re-verify the live copy after a security fix, not just the tree** |
| C | W-08 path-centralization debt is **49** items, not the 48 recorded in `HANDOVER_GPT.md` | `deploy_check.py` output: `"49 path centralization item(s) still pending"` | **OPEN**, count corrected here. Worst offenders: `src/self_editor.py`, `src/openclaw_bridge.py`, `src/agents/orchestrator.py` |
| D | `mainbrain/wordlib/.github/workflows/ci.yml` is a **dead vendored workflow** — GitHub only executes workflows at the repo root, so this file never runs despite reading like a gate (it also installs no pytest, so it could not pass if it did run) | `find` shows it nested under `mainbrain/wordlib/`; the real gate is the root `.github/workflows/mainbrain-ci.yml` | **OPEN** — harmless but actively misleading to a future reader |
| E | `src/ultra_renderer/vulkan_skeleton.py` is prose, not code (146 of 148 lines are string literals, 0 functions/classes) | AST scan | **OPEN**, low priority — the filename is honest and nothing imports it |

Checked and found **clean**: zero bare stubs, zero `pass`-only bodies, zero
parse errors across `wordlib/src` and `ether-runtime`; zero TODO/FIXME markers;
swarm `tsc --noEmit` exits 0; no hardcoded secrets/tokens in source.

**Still open**, lower severity, deliberately not fixed:
`openclaw_bridge.launch()` interpolates a model tag into a `shell=True` command
line. The tag now has to match a real Ollama tag pattern before it is used, so
the injection is closed — but the surrounding Windows terminal-launch logic was
left alone on purpose. It cannot be exercised from this environment, and blind-
rewriting an untestable path trades a known small risk for an unknown larger one.

**A note on the audit itself:** two findings from the automated weakness pass
turned out to be false (it claimed no CI covered ether-runtime or the swarm, and
that Redis wasn't wired into CI — it had only searched under `mainbrain/**` and
missed the repo-root workflows), and the coverage figure in B was wrong. Verify
audit output the same way you'd verify an external artifact.

## Known gaps (real, not hidden)

- Layer 2 (real Windows/USB hardware install) is unproven — only the cloud container chain is proven end-to-end.
- No Ollama/GGUF weights in this deploy — "local inference" here is template-mode, not a live model response.
- "test og legacy" / "test austria 1 legacy" — two other threads referenced as candidates for a progress merge. No accessible artifact (repo, branch, or Notion page) exists under either name as of this writing; if a real merge is wanted, a future session needs a concrete export (zip/diff/paste) from one of those threads, not just the name.
- `okcomputer-swarm/` typechecks in CI but has no live CI *build* — see the Weakness Map in Notion for the full ranked list.

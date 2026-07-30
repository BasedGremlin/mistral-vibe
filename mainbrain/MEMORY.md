# MAINBRAIN — Memory

Brief, falsifiable, dated. Every claim below can be re-checked by running the
command next to it — that is the point of this file. If a future thread
(this one, a fresh one, or another AI) needs "where are we," read this first;
read `HANDOVER_GPT.md` for the full handoff, `wordlib/CLAUDE_BRIEFING.md` for
the dated evolution log, and the Notion "MAINBRAIN — Master Documentation
Hub" for the deep-dive version. Don't trust any external status claim about
this project — including this file, if it's gone stale — without re-deriving
it; see `.claude/skills/verify-and-absorb/SKILL.md`.

**Last verified:** 2026-07-30. **Branch:** `claude/top-conversations-models-t3z66v`.

## What this is

Two uploaded AI-package handoffs (GREMLIN conglomerate + wordlib) fused into
one working tree at `mainbrain/`, plus `ether-runtime` (a durable offline task
runtime built from scratch) wired in as a bounded worker plane via
`DispatchAgent`.

## Current verified state

| Claim | Check it yourself |
|---|---|
| wordlib: 280 tests green (68+61+38+113) | `cd mainbrain/wordlib && python3 tests/run_tests.py` |
| ether-runtime: 56 tests green | `cd mainbrain/ether-runtime && python3 -m pytest -q` |
| Proof gates pass, 0 syntax errors / 34 files | `cd mainbrain/wordlib && python3 deploy_check.py --json` |
| Redis adapter proven against a **real** server, not just a double | 47/47 live parity tests; CI runs a `redis:7-alpine` service container with an anti-silent-skip guard |
| Deploy is live | `/home/user/deploy/MAINBRAIN_DEPLOY_2026-07-30_0406`; hub on `:5757`, `curl 127.0.0.1:5757/api/core/status` → 8/8 capabilities |
| Security boundary holds | dispatching `{"kind":"execute_shell",...}` is rejected at submit — allowlist is `absorb_text`, `verify_artifact` only |
| PR #2 | open, ready for review, mainbrain-ci green — merge pending final CI confirmation |

## Things explicitly rejected (and why — don't re-absorb them)

- **A "Gemini handover" package** (`CLAUDE_HANDOVER_FINAL_PACKAGE.zip`, 2026-07-30): every code module was a non-functional stub (`assert True` as its only "test"). Two claims were actively false: it claimed live Ollama `llama3.2` inference (no Ollama binary exists in this deploy — confirmed twice) and claimed OKComputer is unbuildable (CI shows that job green). Discarded in full.
- **Drive already has other MAINBRAIN-adjacent docs in this same ungrounded style** — a "MASTERZIP v12" bible, "Kekos Main Brain," several connector stubs with confident narrative and no runnable substance behind them. Treat anything found there the same way: verify before trusting, per the skill above.

## Known gaps (real, not hidden)

- Layer 2 (real Windows/USB hardware install) is unproven — only the cloud container chain is proven end-to-end.
- No Ollama/GGUF weights in this deploy — "local inference" here is template-mode, not a live model response.
- "test og legacy" / "test austria 1 legacy" — two other threads referenced as candidates for a progress merge. No accessible artifact (repo, branch, or Notion page) exists under either name as of this writing; if a real merge is wanted, a future session needs a concrete export (zip/diff/paste) from one of those threads, not just the name.
- `okcomputer-swarm/` typechecks in CI but has no live CI *build* — see the Weakness Map in Notion for the full ranked list.

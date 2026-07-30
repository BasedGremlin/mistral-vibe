---
name: verify-and-absorb
description: Use whenever an external artifact shows up claiming to improve, replace, merge with, or salvage the current codebase — an uploaded zip, a competing fork or "conglomerate" package, another team's or agent's implementation of the same thing, a handoff from a "legacy" thread, or a spec/instruction document written by someone else describing how to integrate their work. Also use proactively whenever two independent implementations of the same capability exist and Claude must decide what to keep. Trigger on phrases like "absorb this", "see if there's anything worth salvaging", "merge this in", "does their version have anything we're missing", "integrate this handoff", or when a zip/package is attached with language implying it should be adopted. The core discipline: verify every claim independently before believing it, absorb only the specific delta that is genuinely new and better, and make refusal — explicitly not absorbing something, with reasons — just as valid an outcome as absorbing it.
---

# Verify, then absorb — never adopt on faith

External artifacts arrive with confidence baked in: polished READMEs, "VERIFIED" badges, test counts, a narrative of completeness. None of that is evidence until you've reproduced it yourself. The entire value of this skill is refusing to let someone else's claimed state substitute for your own measurement — and then, once you know what's actually true, taking only the real delta rather than the whole package.

Treat "nothing here is worth absorbing" as a fully successful outcome, not a failure to find something. A wholesale merge that discards tested, working code to gain untested, unproven code is a net loss even when the incoming package is bigger or newer-looking.

## Phase 1 — Read the artifact's own account of itself, skeptically

Most substantial handoffs carry their own status documents. Read them, but treat them as testimony, not fact — and specifically look for places where the artifact contradicts itself. A package that ships one document saying "NO-GO, proof gate FAIL" and another saying "conditional pass, 313 tests collected" is telling you neither document was kept in sync with the code. That contradiction is itself a finding: it means nobody has actually run the thing end-to-end recently, and you may be the first to find out what's really true.

Note every concrete, falsifiable claim as you read: test counts, "PASS" markers, "already generated" artifacts, "this file exists" assertions. You will check each one in Phase 2.

## Phase 2 — Independently verify every checkable claim

If a claim can be reproduced by running a command, run the command. Do not report a claim as true because a document said so.

- **Compilation / collection**: does it actually parse, import, and collect cleanly? (`python -m compileall`, `pytest --collect-only`, `tsc --noEmit`, etc.)
- **Test suites**: run them for real, to completion, even if the artifact's own docs say the full run was never finished or "exceeded the available execution window." Being the first to actually complete a run that nobody else finished is exactly the kind of ground truth this phase exists to produce.
- **Proof gates / lint / type checks**: run them, read the actual exit code and output.
- **Any "already generated" or "already exists" claim**: check the file is actually present before trusting it. This class of phantom artifact — confidently described, never actually created — recurs constantly in AI-authored handoffs, precisely because narrative is cheap and verification is not.

When you find a real failure, diagnose it before deciding what it means. A failing test can indicate a genuine defect in the logic, or it can be harness debt — a test author's wrong assumption about a return shape, a stale fixture, a selector that silently changed what it exercises. These have very different implications for whether the underlying capability is trustworthy to build on. Read the assertion, read what actually gets returned, and determine which case you're in before concluding anything about the code under test.

## Phase 3 — Find the actual delta, not just the volume

More files does not mean more value. Ask, concretely: of everything in this artifact, what is genuinely new, and what already exists in some form in the current codebase? Two implementations of the same spec are common in this situation — the question is never "whose tree do we adopt" but "which specific properties does each one actually prove, and can we combine the strongest properties into one implementation."

A concrete pattern worth recognizing: one side has the *enforcement* (a hard gate that blocks the unsafe path) and the other has the *evidence* (a real measurement proving the gate's precondition, rather than an assumption). A hardcoded `is_safe = True` documented as "always true by construction" is an assertion, not a measurement — it looks like proof but isn't. When you find this asymmetry, the right move is usually to port the stronger enforcement onto the stronger evidence, producing something better than either source, rather than picking one side wholesale.

Also watch for a specific category error: a handoff or spec document written by an agent that never actually inspected the target codebase will sometimes prescribe integration in a language, framework, or file structure that doesn't exist in the real project (a TypeScript adapter for a package that is pure Python with no `.ts` file anywhere, a `store/` directory that was never created). Building what the spec describes, rather than what the codebase actually is, creates a second untested surface for no gain. When the spec and the tree disagree, the tree is what's real — build for that, and say plainly that the spec was wrong about this.

## Phase 4 — Decide, and if the decision is architecturally significant, ask

Small, contained, clearly-beneficial ports (a validation rule, a narrow bug fix, a well-scoped enforcement gate) can usually be made and reported after the fact. A decision that would replace a working subsystem, swap out an already-tested implementation, or touch a component several other things depend on is a decision the user should weigh in on — pause and ask, giving them the concrete tradeoff (what's gained, what's put at risk, what the blast radius is) rather than a vague "should I proceed?"

When you do port something, bring the smallest correct piece across — the specific gate, the specific check, the specific fix — with its own test coverage proving the property that made it worth taking. Don't drag along the surrounding tree it arrived in.

## Phase 5 — Propagate the finding everywhere it's actually needed

This is the "share" half of the discipline, and it applies whether the outcome was absorption or refusal — both are worth recording. Reserve this full propagation for genuinely high-value findings: a safety-relevant gate, a correctness fix, an architectural decision, a rejected wholesale merge with real reasoning behind it. Routine edits don't need this treatment; save it for the things a future reader would actually want to find.

Write the reasoning, not just the change, into every surface where someone will later need it:

- **In the code itself** — a comment at the decision point explaining *why* the gate sits where it does, or why a tempting alternative was rejected. Someone reading the code cold should understand the reasoning without archaeology.
- **In the tests** — a test that specifically proves the property you verified, not just that the happy path works. If ordering matters (a gate must run before another check), write a test that would fail if the ordering were wrong.
- **In the commit message** — the full provenance: what was verified, what was found to be stale or wrong, what was kept, what was rejected and why. This is the durable record once the chat context is gone.
- **In the project's running history**, if one exists (a changelog, an evolution log, a decision log) — append an entry there too, matching whatever convention that project already uses. Don't invent a new logging convention; follow the one on the ground.
- **In chat, concisely** — a scannable summary a human can absorb in seconds: what came in, what was independently checked (and what that checking actually found — especially when it contradicted the artifact's own claims), what was kept, what was explicitly rejected and why. Lead with the finding, not the process.

## Worked example

An uploaded package claimed to be a "canonical conglomerate" superseding the current codebase, with two internal documents that flatly disagreed — one said the proof gates failed and the test suite couldn't even be collected; the other said tests collected fine and 53 passed, with the full run simply never completed. Independent verification found both documents were stale: collection was clean, proof gates were healthy, and running the full suite for the first time produced 312 passing tests and exactly 1 failure — which turned out to be a test author's wrong assumption about a function's return shape (harness debt), not a defect.

The package's own version of a safety gate looked, on inspection, deeper and better-wired than the current codebase's version — until its "isolation proof" turned out to be a hardcoded `True` documented as "always true by construction," i.e. an assertion, never a measurement. The current codebase's version measured isolation for real, via a before/after fingerprint, but hadn't wired its result into an enforced gate yet. The correct move was porting the incoming enforcement pattern onto the existing measured evidence — not adopting the incoming package's 481-file tree, and not leaving the existing gate unenforced either.

Separately, a spec document bundled with the same package instructed building a TypeScript adapter against an interface that didn't exist, inside a package that was pure Python with no TypeScript anywhere. That instruction was declined outright, in favor of building the equivalent capability in the language the actual codebase used — and saying so plainly rather than quietly complying with a spec that had never seen the real tree.

The result: one small, well-tested gate ported with full provenance in the commit message and the code comments; a wholesale tree adoption declined with reasons; a wrong-language instruction declined with reasons; and a concise summary delivered in chat covering all three decisions in a few sentences, not a wall of text.

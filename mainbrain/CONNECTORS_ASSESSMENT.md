# Connector Assessment — what to keep, what to switch off

**Assessed:** 2026-07-29, from observed behaviour across this build session.
**Method:** every verdict below comes from actually calling (or failing to call)
the connector during real work. Connectors never invoked are marked as such
rather than guessed about.

---

## 0. The headline correction

**"Free, offline, autonomous" and "connector" are mutually exclusive.**

Every MCP connector is a **network service**: it needs an internet round-trip,
an OAuth session, and a third party's uptime. None of them work offline, and
none are autonomous — they fail the moment the token lapses or the server flaps.

The genuinely offline, free, autonomous capability in this project is **local
code**, not connectors:

| Capability | Where | Offline? | Cost |
| --- | --- | --- | --- |
| Full test suites (336 tests) | `wordlib/tests`, `ether-runtime/tests` | ✅ yes | free |
| CNS proof gates | `deploy_check.py` | ✅ yes | free |
| Tested-patch sandbox | `docking/improvement/sandbox.py` | ✅ yes | free |
| Durable task runtime | `ether-runtime` (SQLite profile) | ✅ yes | free |
| 13-agent swarm + reasoning stack | `wordlib/src/` | ✅ yes | free |
| 9-stage deployment | `start_here.py` | ✅ yes¹ | free |
| Local inference | Ollama + GGUF | ✅ yes² | free |
| RAG over local corpus | `rag_manager.py` + Chroma | ✅ yes² | free |

¹ first install needs network for packages; idempotent and offline thereafter.
² needs a one-time model/package pull, then fully offline.

**If autonomy offline is the goal, invest in the local stack — not connectors.**

---

## 1. Verdicts

### KEEP — earned their place by doing real work

| Connector | What it actually did here | Why keep |
| --- | --- | --- |
| **GitHub** | PR #1 + #2 created, CI check-runs polled, **job logs retrieved to root-cause the `npm ci` EUSAGE failure** | Load-bearing. The whole propose-only workflow (draft PR → watched CI → human merge) depends on it. Without it there is no gate. |
| **Notion** | Created the 6-page documentation hub | The documentation half of "high documentation, honest gates". Used, current, valuable. |
| **Google Drive** | Surfaced the v30/v31/v32 release receipts that revealed newer versions exist only in chat handoffs | That single search produced weakness **W-09**. Keep for provenance archaeology. |
| **Linear** | Returned the live `WORDLIB Memory Integrity v32` project + MOH-16/17 issue states | Corroborated the Drive receipts independently. Keep if you track work there; otherwise demote. |

### DEACTIVATE — never used productively in this project

| Connector | Observation | Recommendation |
| --- | --- | --- |
| **Canva** | Never invoked. Prior handoff explicitly scoped it "documentation surface only, not a source of engineering truth" | Deactivate |
| **Asana** | Never invoked. Linear already covers tracking — two trackers is worse than one | Deactivate |
| **Clinical Trials** | Never invoked. No medical/trial dimension to this project | Deactivate |
| **dot.** | Never invoked. Visual review of live web pages; the swarm UI isn't deployed publicly | Deactivate (revisit if the UI ships) |
| **Superhuman Docs / Coda** | Never invoked. Notion already holds the docs | Deactivate |
| **WorkOS** | Never invoked. It's an auth/SSO control plane; this project has no user directory | Deactivate |
| **Google Calendar** | Never invoked. No scheduling dimension | Deactivate |
| **Gmail** | Invoked once — returned empty. A prior handoff noted Gmail correspondence is *evidence of an account relationship, not authorization* | Deactivate unless you need mail archaeology |

**Net: keep 3–4, switch off 8.**

---

## 2. Why switching them off is a real improvement, not tidying

1. **Stability.** These servers flapped **repeatedly** during this session —
   connect/disconnect cycles mid-task, tools vanishing between calls. One
   scheduled wake-up failed outright because `send_later` disappeared when its
   server dropped; I had to fall back to an in-session cron. Fewer connectors =
   fewer moving parts = fewer mid-task failures.
2. **Attack surface.** Each connector is a live OAuth grant into a real account
   (mail, drive, calendar, workspace). An unused grant is pure downside risk.
3. **Agent focus.** Every connected server injects tool definitions and
   instructions into context. Eight unused connectors is a large permanent tax
   on every request, competing with the actual work.
4. **Honest capability reporting.** A connected-but-unused connector invites the
   false belief that a capability is live. This project's whole discipline is
   not claiming unproven capability.

---

## 3. How to deactivate

Connectors are managed **in the claude.ai UI**, not from code:

> **Settings → Connectors** → toggle off each one listed above.

They can be re-enabled anytime; nothing in this repo depends on the eight
recommended for deactivation. Verify afterwards by confirming the local
verification chain still passes end-to-end (it does not touch any connector):

```bash
cd mainbrain/wordlib && PATH=/usr/local/bin:$PATH python3 tests/run_tests.py
cd ../ether-runtime && python3 -m pytest -q
cd ../wordlib && python3 deploy_check.py --json
```

**Caveat worth knowing:** the weekly maintenance Routine created this session
could not inherit the Notion connector (triggers only carry connectors the
creating session holds and can pass through). Its fired sessions will do the
code/test/docs-in-repo/draft-PR work but **skip the Notion refresh**. If you
want the weekly pass to update Notion too, recreate that Routine from the
claude.ai Routines UI with Notion attached.

---

## 4. Recommended target configuration

```
KEEP:        GitHub        (essential — PR/CI/logs, the gate itself)
             Notion        (documentation hub)
             Google Drive  (release receipts / provenance)
OPTIONAL:    Linear        (only if you track work there)
DEACTIVATE:  Canva, Asana, Clinical Trials, dot., Superhuman Docs,
             WorkOS, Google Calendar, Gmail
```

**Offline/autonomous posture:** with *all* connectors off, the project still
verifies, proof-gates, sandboxes, deploys, and runs its worker plane. The only
things you lose are PR/CI orchestration and documentation publishing — both
human-facing conveniences, not runtime dependencies. That separation is
deliberate and worth preserving.

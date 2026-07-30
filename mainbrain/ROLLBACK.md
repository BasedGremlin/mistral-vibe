# MAINBRAIN — Rollback & Recovery Runbook

Written to be usable at 3am by someone who did not build this. Every command
here was run against the live tree on 2026-07-30; nothing is aspirational.

**First principle:** this system is rollback-safe by construction — deploys go
to a **new timestamped directory** and self-edits **snapshot before writing**.
So in almost every case recovery means *pointing at the previous good copy*,
not repairing the broken one. Repair is the slow path; switching is the fast one.

---

## 0. Decide what actually broke

Run this first. It takes ~10 seconds and tells you which section below applies.

```bash
cd mainbrain/wordlib
python3 deploy_check.py --json | head -40   # proof gates; exit 0 == healthy
curl -s 127.0.0.1:5757/api/core/status      # hub; expect capabilities 8/8
```

| Symptom | Section |
|---|---|
| Gates fail, or hub won't answer | **1 — bad deploy** |
| Gates pass but a file looks wrong after a self-edit | **2 — bad self-edit** |
| Tasks queued but never completing | **3 — stuck worker plane** |
| Tests green but numbers drifting | **4 — quality decay** |
| Ledgers show as modified in `git status` | **5 — ledger drift** |

---

## 1. Bad deployment → switch to the previous directory

Deploys never overwrite. List them newest-last:

```bash
ls -dt /home/user/deploy/MAINBRAIN_DEPLOY_*/
```

As of writing: `2026-07-19`, `2026-07-30_0350`, `2026-07-30_0406`.

**Roll back = stop the bad one, start the previous one.** Nothing is deleted,
so this is reversible in both directions:

```bash
pkill -f "MAINBRAIN_DEPLOY_<bad-timestamp>.*main.py"   # stop the bad hub
cd /home/user/deploy/MAINBRAIN_DEPLOY_<previous>/wordlib
nohup .venv/bin/python app/main.py > logs/hub.log 2>&1 &
sleep 4 && curl -s 127.0.0.1:5757/api/core/status      # confirm 8/8
```

The previous deploy keeps its own `.venv`, so it does not depend on anything the
bad deploy installed or broke.

**Do not** delete the failed directory before diagnosing it — it is the only
evidence of what went wrong, and disk is cheaper than a repeat of the incident.

---

## 2. Bad self-edit → restore from the pre-write snapshot

`SelfEditor` backs up every file *before* modifying it, and backs up the current
file again before rolling back, so a rollback is itself undoable.

```bash
ls mainbrain/wordlib/backups/self_editor/      # available snapshots
```

```python
from self_editor import SelfEditor            # from wordlib/src
SelfEditor().rollback("relative/path/to/file.py")          # newest backup
SelfEditor().rollback("relative/path/to/file.py", "NAME")  # a specific one
```

For a multi-file change, `EvolutionManager.evolve_files()` is already an atomic
transaction with **two-phase verified rollback** (`src/ether_core.py`): if any
file fails its post-write test, all files are restored and each restore is
verified. If you are recovering from a failed `evolve_files`, the rollback has
almost certainly already happened — check the ledger before doing it by hand:

```bash
tail -5 mainbrain/wordlib/docking/improvement/patch_records.jsonl
```

---

## 3. Stuck worker plane

```bash
cd mainbrain/ether-runtime
python3 -m ether_runtime --db <path> doctor    # diagnosis with exact fixes
python3 -m ether_runtime --db <path> status    # counts by state
```

Delivery is **at-least-once** by design, and leases expire. A task stuck in
`running` usually means a worker died mid-flight; the lease lapses and it is
reclaimed. `doctor` will say so rather than making you guess.

The journal is a SQLite file — copy it before experimenting on it.

---

## 4. Quality decay (green tests, worsening numbers)

```bash
cd mainbrain/wordlib
python3 quality_watch.py            # exit 1 == regression vs committed baseline
```

This exists because the proof gates answer "is it broken?" and cannot answer
"is it getting worse?". If it reports decay, the two legitimate responses are
**fix it** or **acknowledge it by re-recording the baseline in a commit that
says why**. Re-baselining silently defeats the tool.

---

## 5. Ledger drift after a test run

The docking `.jsonl` ledgers are append-only committed runtime state, and the
test suite genuinely appends to them. This is known and expected.

```bash
git checkout -- 'mainbrain/wordlib/docking/**/*.jsonl'
```

**Only that glob.** Never `git checkout -- docking/` — source files
(`patch_applier.py`, `sandbox.py`) live in that same tree, and a directory-wide
checkout silently reverts real work. That mistake has already been made once in
this project's history; it is why the glob is written out everywhere it appears.

---

## 6. Full reset to a known-good commit

```bash
git log --oneline -10
git status                                  # ALWAYS look before discarding
git stash -u                                # keep anything uncommitted
git checkout <known-good-sha>
```

Verify you actually landed somewhere good before trusting it:

```bash
cd mainbrain/wordlib && python3 tests/run_tests.py && python3 deploy_check.py --json
cd ../ether-runtime && python3 -m pytest -q
```

---

## What has no rollback path (be honest about this)

- **Anything pushed to a remote.** Force-pushing to rewrite shared history is a
  different and riskier operation than any recovery above; do not treat it as
  routine cleanup.
- **A real Windows/USB install.** Layer 2 has never been executed, so there is
  no tested recovery procedure for it. Sections 1–6 cover the container path
  only. Write the hardware rollback steps *while* doing that install, not after.
- **External side effects** — anything already sent to Notion, Drive, or GitHub.
  Recovering the tree does not un-publish those.

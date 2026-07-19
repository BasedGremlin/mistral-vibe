# ether-runtime — durable task runtime (pure stdlib, offline)

Reconstruction of the missing **EtherAI Absorption System v11** artifact —
top-5 item #4. The original v11 starter zip/wheel referenced by the design
record (`../handoff/30_RUNTIME_AND_MEMORY_DESIGNS/EtherAI Absorption
System.txt`) was never present in any package; this implements its durability
model from that record, with zero third-party dependencies, so it runs and
tests fully offline.

## What it implements from the v11 record

| v11 design element | Here |
| --- | --- |
| SQLite WAL task journaling | `store.py` — WAL journal, terminal status authoritative |
| Transactional task outbox | submit = task + outbox row in ONE transaction |
| Outbox claim leases | publishers claim rows under a lease; no double publish |
| Consumer groups (`XREADGROUP`) | `read_group()` — pending-entries list per group |
| Crash recovery (`XAUTOCLAIM`) | `autoclaim()` — transfers entries idle ≥ 60s |
| Worker execution leases | one runner per task; expiry frees crashed work |
| Retry ladder 1/2/4/8/16s | `retry.py`, nominal total 31s < 60s reclaim |
| Deterministic ±20% jitter | derived from `SHA-256(task_id + attempt)` |
| Dead-letter records | `dead_lettered` status after max attempts |
| At-least-once, not exactly-once | duplicate window controlled by stable task ids, task uniqueness, leases, terminal-state dedup (tested) |
| Only validated task types | `absorb_text`, `verify_artifact`; unknown kinds rejected at submit — no arbitrary-execution endpoint, same boundary the v11 review enforced |

## Usage

```bash
python -m ether_runtime submit-absorb --source NOTE --text "durable text"
python -m ether_runtime submit-verify --file rel/path.bin=<sha256>
python -m ether_runtime work            # drain once
python -m ether_runtime status          # journal counts + retry policy
python -m ether_runtime doctor          # findings with exact fixes
```

Run the tests (stdlib + pytest only):

```bash
cd mainbrain/ether-runtime && python -m pytest -q
```

## Honest divergences from v11

- **No Redis / no Docker / no FastAPI here.** The stream + pending-entries
  tables are a single-node, in-database stand-in for Redis Streams with the
  same claim/ack/reclaim semantics. A Redis adapter can implement the same
  operations later without touching worker logic; an HTTP gateway is a thin
  layer over `TaskRuntime.submit()` when a connected deployment needs one.
- **Single-node coordination.** SQLite is not distributed consensus — same
  limit the v11 record states for its own SQLite authority.
- The Wolfram-verified numbers (31s nominal retry total vs 60s reclaim) are
  re-derived at startup by `retry.validate_policy()`, which raises if the
  invariant is ever broken by edit.

## Integration path (merge plan Phase 3)

Swarm planner → bounded task envelope (`submit`) → durable outbox → stream →
worker lease → result/evidence record (`result` on the journal row) → swarm
validator. Allowlisted task types only.

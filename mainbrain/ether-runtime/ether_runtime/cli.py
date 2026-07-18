"""Command-line entry point.

    python -m ether_runtime submit-absorb  --source NOTE --text "..."
    python -m ether_runtime submit-verify  --file rel/path=sha256hex [...]
    python -m ether_runtime work           [--loop SECONDS]
    python -m ether_runtime status
    python -m ether_runtime doctor
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import retry
from .runtime import TaskRuntime, Worker


def _default_db() -> str:
    return str(Path.cwd() / "data" / "ether_runtime.db")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ether_runtime")
    parser.add_argument("--db", default=_default_db(), help="SQLite database path")
    parser.add_argument("--artifact-root", default=None, help="root for verify_artifact")
    sub = parser.add_subparsers(dest="command", required=True)

    absorb = sub.add_parser("submit-absorb", help="journal an absorb_text task")
    absorb.add_argument("--source", required=True)
    absorb.add_argument("--text", required=True)

    verify = sub.add_parser("submit-verify", help="journal a verify_artifact task")
    verify.add_argument(
        "--file",
        action="append",
        required=True,
        metavar="REL_PATH=SHA256",
        help="repeatable manifest entry",
    )

    work = sub.add_parser("work", help="run the worker")
    work.add_argument("--loop", type=float, default=None, metavar="SECONDS",
                      help="poll interval; omit for a single drain pass")

    sub.add_parser("status", help="journal counts + retry policy")
    sub.add_parser("doctor", help="diagnose runtime state with exact fixes")
    return parser


def _doctor(runtime: TaskRuntime) -> int:
    counts = runtime.store.counts()
    problems: list[str] = []
    if counts["outbox_backlog"] > 0:
        problems.append(
            f"outbox backlog of {counts['outbox_backlog']}:"
            " no publisher is running -> run 'work'"
        )
    dead = counts["tasks_by_status"].get("dead_lettered", 0)
    if dead:
        problems.append(
            f"{dead} dead-lettered task(s): inspect with 'status', fix the"
            " underlying payload/artifact, and resubmit"
        )
    if counts["pending_entries"] > 0 and counts["active_leases"] == 0:
        problems.append(
            f"{counts['pending_entries']} pending entries with no active lease:"
            " a consumer likely crashed -> next 'work' pass reclaims after"
            f" {retry.RECLAIM_IDLE_SECONDS:.0f}s idle"
        )
    for line in problems or ["healthy: no findings"]:
        print(f"[{'WARN' if problems else 'OK'}] {line}")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime = TaskRuntime(args.db, artifact_root=args.artifact_root)
    try:
        if args.command == "submit-absorb":
            task, created = runtime.submit(
                "absorb_text", {"source": args.source, "text": args.text}
            )
            print(json.dumps({"task_id": task.task_id, "created": created}))
        elif args.command == "submit-verify":
            files = {}
            for spec in args.file:
                rel, _, digest = spec.partition("=")
                files[rel] = digest
            task, created = runtime.submit("verify_artifact", {"files": files})
            print(json.dumps({"task_id": task.task_id, "created": created}))
        elif args.command == "work":
            worker = Worker(runtime)
            if args.loop is None:
                executed = worker.run_until_drained()
                print(json.dumps({"executed": executed}))
            else:
                while True:  # pragma: no cover - interactive loop
                    worker.run_once()
                    time.sleep(args.loop)
        elif args.command == "status":
            print(json.dumps(runtime.status(), indent=2, sort_keys=True))
        elif args.command == "doctor":
            return _doctor(runtime)
        return 0
    finally:
        runtime.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

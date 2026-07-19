"""CLI: submit -> work -> status -> doctor round trip."""

import json

from ether_runtime.cli import main


def test_cli_round_trip(tmp_path, capsys):
    db = str(tmp_path / "cli.db")

    assert main(["--db", db, "submit-absorb", "--source", "cli", "--text", "hello"]) == 0
    submitted = json.loads(capsys.readouterr().out)
    assert submitted["created"] is True

    # Doctor sees the unpublished backlog before a worker runs.
    assert main(["--db", db, "doctor"]) == 1
    assert "outbox backlog" in capsys.readouterr().out

    assert main(["--db", db, "work"]) == 0
    assert json.loads(capsys.readouterr().out)["executed"] == 1

    assert main(["--db", db, "status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["tasks_by_status"] == {"completed": 1}
    assert status["policy"]["constraint_check"] == "passed"

    assert main(["--db", db, "doctor"]) == 0
    assert "healthy" in capsys.readouterr().out

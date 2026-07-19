"""Tests for core.paths (single source of truth) + editor.self_healer."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.paths import (PATHS, health_report, migration_report,
                        verify_critical_files, get_project_root,
                        get_logs_dir, PROJECT_STRUCTURE)
from editor.self_healer import run_self_heal, SelfHealer


def test_root_derives_from_file_location():
    # root must be the project dir (parent of core/)
    assert (PATHS.root / "core" / "paths.py").exists()
    assert get_project_root() == PATHS.root


def test_paths_object_is_immutable():
    import dataclasses
    try:
        PATHS.root = Path("/tmp")  # frozen dataclass -> should raise
        assert False, "PATHS should be immutable"
    except dataclasses.FrozenInstanceError:
        pass


def test_health_report_real_not_faked():
    h = health_report()
    # root must be the actual root, not a placeholder
    assert h["filesystem"]["root"] == str(PATHS.root)
    assert h["overall"] in ("OK", "WARNING", "ERROR")
    assert h["python"]["status"] == "OK"  # we're running on >=3.9


def test_verify_critical_files_finds_real_ones():
    crit = verify_critical_files()
    # self_editor and ether_core really exist
    assert crit["src/self_editor.py"] is True
    assert crit["src/ether_core.py"] is True


def test_migration_report_is_honest():
    r = migration_report()
    # paths.py itself counts as migrated; there are real pending files
    assert "core/paths.py" in r["migrated"]
    assert isinstance(r["pending_count"], int)
    assert r["pending_count"] == len(r["pending_migration"])


def test_self_healer_creates_missing_dir():
    import shutil
    # Make a throwaway essential dir missing, then heal
    test_dir = PATHS.root / "logs"
    had_contents = test_dir.exists() and any(test_dir.iterdir())
    if test_dir.exists() and not had_contents:
        shutil.rmtree(test_dir)
        r = run_self_heal()
        assert (PATHS.root / "logs").exists()  # recreated
    else:
        # logs has content; just assert healer runs clean
        r = run_self_heal()
        assert r.status in ("OK", "WARNING")


def test_self_healer_never_fabricates_critical_files():
    # The healer must NOT create fake .py critical files -- only report them
    h = SelfHealer()
    result = h.heal()
    # All critical files exist in this project, so none unrecoverable
    assert result.missing_unrecoverable == []
    # And it does not list any .py file as "created"
    assert not any(c.endswith(".py") for c in result.created)


def test_critical_modules_use_core_paths():
    """Regression guard: the migrated modules must route paths through core.paths
    (they may keep a guarded bootstrap, but must import core.paths)."""
    for rel in ("src/self_editor.py", "src/ether_core.py", "src/openclaw_bridge.py"):
        text = (PATHS.root / rel).read_text(encoding="utf-8")
        assert "from core.paths import" in text, f"{rel} no longer uses core.paths"


def test_migration_report_three_buckets():
    r = migration_report()
    assert "migrated" in r and "bootstrap_only" in r and "pending_migration" in r
    # the 3 migrated files should be in bootstrap_only (core.paths + guarded locator)
    for rel in ("src/self_editor.py", "src/ether_core.py", "src/openclaw_bridge.py"):
        assert rel in r["bootstrap_only"], f"{rel} not recognized as centralized"


def test_main_boot_checks_run_clean():
    """main.boot_checks must return ok with no critical files missing."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("wl_main", PATHS.root / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ok, health = mod.boot_checks(verbose=False)
    assert ok is True
    assert health["overall"] in ("OK", "WARNING")


def test_main_diagnose_paths_reports_centralized():
    """main.diagnose_paths must report entry points as centralized (not warning)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("wl_main_d", PATHS.root / "main.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    diag = m.diagnose_paths()
    # entry points (main/launcher/app/main) are migrated -> no warning severity
    assert diag["severity"] == "ok"
    assert diag["centralized"] >= 9


def test_entry_points_centralized():
    """launcher.py and app/main.py must route paths through core.paths."""
    r = migration_report()
    centralized = set(r["migrated"]) | set(r["bootstrap_only"])
    assert "launcher.py" in centralized
    assert "app/main.py" in centralized

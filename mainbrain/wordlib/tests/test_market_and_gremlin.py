"""Tests for MarketIntelAnalyst (honesty contract) + GremlinCoordinator."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_intel import MarketIntelAnalyst, FeasibilityScore
from gremlin_coordinator import GremlinCoordinator

ROOT = Path(__file__).resolve().parents[1]


def test_market_refuses_to_fabricate_with_no_evidence():
    a = MarketIntelAnalyst()
    r = a.build_report("anything")
    assert r.feasibility is None
    assert r.evidence_count == 0
    assert "INSUFFICIENT DATA" in r.confidence_note


def test_market_requires_source_on_evidence():
    a = MarketIntelAnalyst()
    try:
        a.add_evidence("some claim", source="")
        assert False, "should reject sourceless evidence"
    except ValueError:
        pass


def test_market_scores_only_with_enough_evidence():
    a = MarketIntelAnalyst()
    a.add_evidence("x", "src1")
    a.add_evidence("y", "src2")
    feas = FeasibilityScore(8, 8, 8, 8)
    r = a.build_report("topic", feasibility=feas)
    # Only 2 items < MIN_EVIDENCE_FOR_SCORE -> no score
    assert r.feasibility is None


def test_market_all_sources_traceable():
    a = MarketIntelAnalyst()
    for i in range(3):
        a.add_evidence(f"claim {i}", f"source{i}")
    r = a.build_report("topic", feasibility=FeasibilityScore(7, 7, 7, 7))
    assert len(r.sources) == 3
    assert all(s["source"] for s in r.sources)


def test_gremlin_coordinator_consent_gate():
    gc = GremlinCoordinator(ROOT)
    # Disabled by default -> refuses
    r = gc.activate("test_gap_finder")
    assert r["ok"] is False


def test_gremlin_coordinator_descriptive_only_not_executable():
    gc = GremlinCoordinator(ROOT)
    gc.enable(consent=True)
    r = gc.activate("comet_killer_ui_surface")
    assert r["ok"] is False
    assert "descriptive-only" in r["reason"]


def test_gremlin_coordinator_real_feature_runs():
    gc = GremlinCoordinator(ROOT)
    gc.enable(consent=True)
    r = gc.activate("contrast_and_focus_whisperer",
                    {"pairs": [("#ffffff", "#000000")]})
    assert r["ok"] is True
    assert r["results"][0]["passes_AA"] is True


def test_rollback_guardian_detects_real_rollback():
    """RollbackGuardian must confirm a backup differs from current (not a no-op)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from gremlin_coordinator import GremlinCoordinator
    from self_editor import get_editor, _USB_ROOT, _BACKUPS

    gc = GremlinCoordinator(ROOT)
    gc.enable(consent=True)
    ed = get_editor()
    rel = "storage/kb/_guardian_unit.md"
    ed.write_file(rel, "first\n")
    ed.write_file(rel, "second\n")  # backs up "first"
    r = gc.activate("rollback_guardian", {"path": rel})
    assert r["ok"] is True
    assert r["differs_from_current"] is True
    # cleanup
    p = _USB_ROOT / rel
    if p.exists(): p.unlink()
    for b in _BACKUPS.glob("storage__kb___guardian_unit*"): b.unlink()


def test_rollback_guardian_consent_gated():
    from gremlin_coordinator import GremlinCoordinator
    gc = GremlinCoordinator(ROOT)
    r = gc.activate("rollback_guardian", {"path": "x"})
    assert r["ok"] is False  # disabled by default

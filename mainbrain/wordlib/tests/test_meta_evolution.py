"""Tournament harness + honesty tests for the Meta-Evolution Engine."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evolution.meta_evolution_engine import MetaEvolutionEngine, TaskCase, Genome
from agents.base import AgentResult


def _fresh_engine():
    for f in ("data/evolution_genomes.json", "data/evolution_promotions.json"):
        p = ROOT / f
        if p.exists():
            p.unlink()
    return MetaEvolutionEngine(ROOT)


def test_first_genome_becomes_baseline():
    eng = _fresh_engine()
    g = eng.register_genome("demo", {"x": 1})
    assert g.version == 1
    assert eng.active_genome("demo").version == 1
    assert eng.is_evolved("demo") is False


def test_variant_with_no_tasks_has_no_fitness():
    """Honesty: a tournament with no tasks returns no scores -- never invents."""
    eng = _fresh_engine()
    eng.register_genome("demo", {"x": 1})
    scores = eng.run_tournament("demo", [], lambda g, t: None)
    assert scores == []


def test_tournament_scores_objectively_and_promotes_winner():
    eng = _fresh_engine()
    eng.register_genome("calc", {"double": False})   # v1 baseline
    eng.register_genome("calc", {"double": True})    # v2 challenger

    # Known-answer task: output should be input*2. v2 (double=True) is correct.
    def run_variant(genome, task):
        n = task.payload["n"]
        out = n * 2 if genome.params.get("double") else n
        return AgentResult("calc", ok=True, output=str(out), duration_ms=1)

    tasks = [
        TaskCase("calc", {"n": 3}, check=lambda r: r.output == "6"),
        TaskCase("calc", {"n": 5}, check=lambda r: r.output == "10"),
    ]
    scores = eng.run_tournament("calc", tasks, run_variant)
    # v2 must win objectively
    assert scores[0].genome_key == "calc:v2"
    assert scores[0].correct == 2
    promo = eng.promote_winner("calc", scores)
    assert promo["promoted"] is True
    assert eng.is_evolved("calc") is True


def test_no_promotion_on_insufficient_margin():
    eng = _fresh_engine()
    eng.register_genome("tie", {"v": 1})
    eng.register_genome("tie", {"v": 2})
    # Both identical behavior -> tie -> winner not better than active by margin
    def run_variant(genome, task):
        return AgentResult("tie", ok=True, output="same", duration_ms=1)
    tasks = [TaskCase("tie", {}, check=lambda r: True)]
    scores = eng.run_tournament("tie", tasks, run_variant)
    promo = eng.promote_winner("tie", scores)
    assert promo["promoted"] is False  # no real margin


def test_promotion_is_reversible():
    eng = _fresh_engine()
    eng.register_genome("rev", {"good": False})
    eng.register_genome("rev", {"good": True})
    def run_variant(genome, task):
        return AgentResult("rev", ok=True,
                           output="yes" if genome.params.get("good") else "no",
                           duration_ms=1)
    tasks = [TaskCase("rev", {}, check=lambda r: r.output == "yes")]
    scores = eng.run_tournament("rev", tasks, run_variant)
    eng.promote_winner("rev", scores)
    assert eng.is_evolved("rev") is True
    rb = eng.rollback("rev")
    assert rb["ok"] is True
    assert eng.active_genome("rev").version == 1   # back to baseline


def test_architect_proposes_only_known_levers():
    from agents.evolution_architect import EvolutionArchitect
    from agents.base import Task, AgentContext
    ctx = AgentContext(root=ROOT)
    arch = EvolutionArchitect(ctx)
    # Unknown agent -> refuses, no fabricated params
    r = arch.handle(Task("evolve", {"agent": "ghost", "failures": []}))
    assert r.ok is False
    # Known agent with relevant failures -> real proposal
    r2 = arch.handle(Task("evolve", {"agent": "math",
        "failures": ["identity failed needs simplification"],
        "current_params": {"simplify": False}}))
    assert r2.ok is True
    assert any(p["params"].get("simplify") for p in r2.output["proposals"])

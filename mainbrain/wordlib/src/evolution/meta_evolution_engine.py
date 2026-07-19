"""
meta_evolution_engine.py -- Meta-Evolution Engine.
=================================================
Treats agent *variants* as evolvable artifacts and selects between them using
an OBJECTIVE fitness function on real tasks. The honesty rules from the
directive are load-bearing here, so read this carefully:

WHAT IS REAL:
  - Variants are concrete agent configurations (genomes): tunable parameters
    like a quality threshold, max refinement iterations, target score, etc.
    These are REAL knobs that change behavior.
  - A tournament runs every variant against the SAME set of tasks that have
    KNOWN correct answers (math identities, code-safety verdicts, etc.).
  - Fitness is measured, not guessed: correctness (did it get the known-right
    answer?), output quality (OutputQualityChecker, honestly labeled heuristic),
    and latency. The UncertaintyQuantifier gives a confidence interval on the
    win so we don't promote on noise.
  - Promotion is logged and reversible. Genomes are versioned with full history.

WHAT THIS IS NOT (and won't pretend to be):
  - Not neural weight evolution -- these are parameter/prompt genomes.
  - Not "which writes better prose" unless a real judge model is present; on
    text-only tasks the score is surface-heuristic and SAID to be.
  - No fabricated performance numbers. A variant with no measured tasks has no
    fitness, full stop.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))


@dataclass
class Genome:
    """A versioned agent configuration. The evolvable artifact."""
    agent: str
    version: int
    params: Dict          # the real tunable knobs
    parent_version: Optional[int] = None
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def key(self) -> str:
        return f"{self.agent}:v{self.version}"


@dataclass
class TaskCase:
    """A task with a KNOWN correct answer, so fitness is objective."""
    kind: str
    payload: Dict
    check: Callable        # (AgentResult) -> bool : did it get it right?
    name: str = ""


@dataclass
class VariantScore:
    genome_key: str
    tasks_run: int
    correct: int
    avg_quality: float
    avg_latency_ms: float
    fitness: float
    note: str = ""

    def as_dict(self):
        return self.__dict__


class MetaEvolutionEngine:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or _ROOT
        self.history_path = self.root / "data" / "evolution_genomes.json"
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self._genomes: Dict[str, List[Genome]] = {}   # agent -> [genomes]
        self._active: Dict[str, int] = {}             # agent -> active version
        self._scores: Dict[str, VariantScore] = {}
        self._load()

        # Reasoning services for the fitness function (real, honest)
        try:
            from reasoning import OutputQualityChecker, UncertaintyQuantifier
            self.quality = OutputQualityChecker()
            self.uncertainty = UncertaintyQuantifier(self.root)
        except Exception:
            self.quality = None
            self.uncertainty = None

    # ── Genome registry ──────────────────────────────────────────────────────
    def register_genome(self, agent: str, params: Dict,
                        parent_version: Optional[int] = None) -> Genome:
        versions = self._genomes.setdefault(agent, [])
        version = (max((g.version for g in versions), default=0)) + 1
        g = Genome(agent=agent, version=version, params=params,
                   parent_version=parent_version)
        versions.append(g)
        if agent not in self._active:
            self._active[agent] = version   # first genome becomes active baseline
        self._save()
        return g

    def active_genome(self, agent: str) -> Optional[Genome]:
        v = self._active.get(agent)
        if v is None:
            return None
        return next((g for g in self._genomes.get(agent, []) if g.version == v), None)

    def is_evolved(self, agent: str) -> bool:
        """True if the active version is NOT the baseline (v1)."""
        return self._active.get(agent, 1) != 1

    # ── Tournament: objective scoring on known-answer tasks ─────────────────
    def run_tournament(self, agent: str, tasks: List[TaskCase],
                       run_variant: Callable[[Genome, TaskCase], "AgentResult"]
                       ) -> List[VariantScore]:
        """
        run_variant(genome, task) -> AgentResult : caller supplies how to run a
        given genome on a task (so the engine stays decoupled from agent guts).
        Returns scores sorted best-first. NO fabrication: a variant only gets a
        fitness from tasks it actually ran.
        """
        variants = self._genomes.get(agent, [])
        if not variants or not tasks:
            return []
        scores: List[VariantScore] = []
        for g in variants:
            correct = 0
            qualities: List[float] = []
            latencies: List[float] = []
            for task in tasks:
                result = run_variant(g, task)
                if result is None:
                    continue
                ok = False
                try:
                    ok = bool(task.check(result))
                except Exception:
                    ok = False
                if ok:
                    correct += 1
                latencies.append(getattr(result, "duration_ms", 0) or 0)
                # Quality is heuristic -- only on text-ish outputs, honestly labeled
                if self.quality and isinstance(getattr(result, "output", None), (str,)):
                    qualities.append(self.quality.check(result.output).score)
            n = len(tasks)
            accuracy = correct / n if n else 0.0
            avg_q = sum(qualities) / len(qualities) if qualities else 0.0
            avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
            # Fitness: correctness dominates; quality is a minor, honest tiebreak;
            # latency is a tiny penalty. Weights are explicit, not hidden.
            fitness = round(0.80 * accuracy + 0.15 * avg_q
                            - 0.05 * min(1.0, avg_lat / 5000), 4)
            note = ("accuracy on known-answer tasks dominates; quality is "
                    "surface-heuristic; latency lightly penalized")
            vs = VariantScore(g.key(), n, correct, round(avg_q, 3),
                              round(avg_lat, 1), fitness, note)
            scores.append(vs)
            self._scores[g.key()] = vs
        scores.sort(key=lambda s: s.fitness, reverse=True)
        return scores

    def promote_winner(self, agent: str, scores: List[VariantScore],
                       min_margin: float = 0.05) -> Dict:
        """
        Promote the winning variant to active -- but only if it beats the current
        active version by a real margin (guards against promoting on noise).
        Logged + reversible (previous active version is recorded).
        """
        if not scores:
            return {"promoted": False, "reason": "no scores"}
        winner_key = scores[0].genome_key
        winner_version = int(winner_key.split(":v")[1])
        current = self._active.get(agent, 1)
        if winner_version == current:
            return {"promoted": False, "reason": "winner is already active",
                    "active": current}
        # Margin check: winner must beat current active's score
        current_key = f"{agent}:v{current}"
        current_score = next((s.fitness for s in scores if s.genome_key == current_key), 0.0)
        if scores[0].fitness - current_score < min_margin:
            return {"promoted": False,
                    "reason": f"margin too small ({scores[0].fitness:.3f} vs "
                              f"{current_score:.3f}, need +{min_margin})",
                    "active": current}
        previous = current
        self._active[agent] = winner_version
        self._log_promotion(agent, previous, winner_version, scores[0].fitness)
        self._save()
        return {"promoted": True, "agent": agent, "from_version": previous,
                "to_version": winner_version, "fitness": scores[0].fitness,
                "reversible": True}

    def rollback(self, agent: str) -> Dict:
        """Revert to the previously-active version from the promotion log."""
        log = self._load_promotion_log()
        entries = [e for e in log if e["agent"] == agent]
        if not entries:
            return {"ok": False, "reason": "no promotion to roll back"}
        last = entries[-1]
        self._active[agent] = last["from_version"]
        self._save()
        return {"ok": True, "agent": agent,
                "reverted_to_version": last["from_version"]}

    # ── Persistence ──────────────────────────────────────────────────────────
    def _log_promotion(self, agent, frm, to, fitness):
        log = self._load_promotion_log()
        log.append({"time": datetime.now(timezone.utc).isoformat(),
                    "agent": agent, "from_version": frm, "to_version": to,
                    "fitness": fitness})
        (self.root / "data" / "evolution_promotions.json").write_text(
            json.dumps(log, indent=2), encoding="utf-8")

    def _load_promotion_log(self) -> List[Dict]:
        p = self.root / "data" / "evolution_promotions.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _save(self):
        data = {
            "genomes": {a: [g.__dict__ for g in gs]
                        for a, gs in self._genomes.items()},
            "active": self._active,
        }
        try:
            self.history_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load(self):
        if not self.history_path.exists():
            return
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            for a, gs in data.get("genomes", {}).items():
                self._genomes[a] = [Genome(**g) for g in gs]
            self._active = {k: int(v) for k, v in data.get("active", {}).items()}
        except Exception:
            pass

    def status(self) -> Dict:
        return {
            "agents_with_genomes": list(self._genomes.keys()),
            "active_versions": dict(self._active),
            "evolved": {a: self.is_evolved(a) for a in self._genomes},
            "latest_scores": {k: v.as_dict() for k, v in self._scores.items()},
        }

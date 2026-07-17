"""
Quantum-Inspired Optimizer.
===========================
HONESTY FIRST: there is NO quantum computation here. "Quantum-inspired" is an
industry nickname for CLASSICAL algorithms whose structure is loosely analogous
to quantum concepts. Every function below is ordinary classical math running on
a normal CPU. The quantum words are labels for intuition, not claims of qubits.

What's actually implemented (all real, useful classical methods):
  - parallel_hypothesis_scoring  : evaluate many hypotheses with weighted
    ("superposition")              scores, return a normalized probability
                                    distribution (softmax). Real.
  - correlation_matrix           : Pearson correlation between reasoning-step
    ("entanglement")               score vectors -- which steps move together.
                                    Real statistics.
  - amplitude_decision_scoring   : softmax over outcome utilities to pick among
    ("amplitude")                  multiple options with a confidence. Real.
  - annealing_task_allocation    : simulated annealing to assign tasks to agents
    ("quantum annealing")          minimizing a real cost function. Real, classic.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple


@dataclass
class Hypothesis:
    name: str
    raw_score: float          # any real-valued evidence score
    weight: float = 1.0


def softmax(scores: List[float], temperature: float = 1.0) -> List[float]:
    """Numerically stable softmax. Real."""
    if not scores:
        return []
    t = max(1e-6, temperature)
    mx = max(scores)
    exps = [math.exp((s - mx) / t) for s in scores]
    total = sum(exps)
    return [e / total for e in exps] if total else [1.0 / len(scores)] * len(scores)


class QuantumInspiredOptimizer:
    """Classical algorithms with quantum-metaphor names (clearly labeled)."""

    # ── "Superposition": parallel weighted hypothesis evaluation ────────────
    def parallel_hypothesis_scoring(self, hypotheses: List[Hypothesis],
                                    temperature: float = 1.0) -> List[Dict]:
        """
        Evaluate all hypotheses 'in parallel' and return a probability
        distribution over them (softmax of weighted scores). Classical.
        """
        if not hypotheses:
            return []
        weighted = [h.raw_score * h.weight for h in hypotheses]
        probs = softmax(weighted, temperature)
        ranked = sorted(
            [{"name": h.name, "raw_score": h.raw_score, "probability": round(p, 4)}
             for h, p in zip(hypotheses, probs)],
            key=lambda x: x["probability"], reverse=True)
        return ranked

    # ── "Entanglement": correlation between reasoning-step score vectors ────
    def correlation_matrix(self, step_scores: Dict[str, List[float]]) -> Dict:
        """
        Pearson correlation between each pair of reasoning steps' score series.
        High |correlation| = steps that move together ('entangled'). Classical.
        """
        names = list(step_scores.keys())
        matrix: Dict[str, Dict[str, float]] = {}
        for a in names:
            matrix[a] = {}
            for b in names:
                matrix[a][b] = round(self._pearson(step_scores[a], step_scores[b]), 3)
        # Surface the most strongly correlated distinct pair
        strongest = None
        for i, a in enumerate(names):
            for b in names[i+1:]:
                c = matrix[a][b]
                if strongest is None or abs(c) > abs(strongest[2]):
                    strongest = (a, b, c)
        return {"matrix": matrix, "strongest_pair": strongest}

    def _pearson(self, x: List[float], y: List[float]) -> float:
        n = min(len(x), len(y))
        if n < 2:
            return 0.0
        x, y = x[:n], y[:n]
        mx, my = sum(x)/n, sum(y)/n
        cov = sum((xi-mx)*(yi-my) for xi, yi in zip(x, y))
        vx = math.sqrt(sum((xi-mx)**2 for xi in x))
        vy = math.sqrt(sum((yi-my)**2 for yi in y))
        return cov / (vx*vy) if vx and vy else 0.0

    # ── "Amplitude": multi-outcome decision scoring ─────────────────────────
    def amplitude_decision_scoring(self, options: Dict[str, float],
                                   temperature: float = 1.0) -> Dict:
        """
        Given option->utility, return a softmax distribution and the pick with
        its confidence (the winning probability). Classical decision theory.
        """
        if not options:
            return {"choice": None, "confidence": 0.0, "distribution": {}}
        names = list(options.keys())
        probs = softmax([options[n] for n in names], temperature)
        dist = {n: round(p, 4) for n, p in zip(names, probs)}
        best = max(dist, key=dist.get)
        return {"choice": best, "confidence": dist[best], "distribution": dist}

    # ── "Quantum annealing": simulated annealing task allocation ────────────
    def annealing_task_allocation(self, tasks: List[str], agents: List[str],
                                  cost_fn: Callable[[str, str], float],
                                  iterations: int = 1000,
                                  seed: int = 42) -> Dict:
        """
        Assign each task to an agent minimizing total cost, via simulated
        annealing (a real, classic optimization method -- the 'quantum' label
        is just nickname). cost_fn(task, agent) -> lower is better.
        """
        if not tasks or not agents:
            return {"assignment": {}, "cost": 0.0}
        rng = random.Random(seed)
        # Initial random assignment
        assign = {t: rng.choice(agents) for t in tasks}

        def total_cost(a):
            return sum(cost_fn(t, ag) for t, ag in a.items())

        current = assign
        current_cost = total_cost(current)
        best, best_cost = dict(current), current_cost
        temp = 1.0
        cooling = 0.995

        for _ in range(iterations):
            # Perturb: reassign one random task
            cand = dict(current)
            t = rng.choice(tasks)
            cand[t] = rng.choice(agents)
            cand_cost = total_cost(cand)
            delta = cand_cost - current_cost
            # Accept if better, or probabilistically if worse (annealing)
            if delta < 0 or rng.random() < math.exp(-delta / max(1e-6, temp)):
                current, current_cost = cand, cand_cost
                if current_cost < best_cost:
                    best, best_cost = dict(current), current_cost
            temp *= cooling

        return {"assignment": best, "cost": round(best_cost, 3),
                "method": "simulated annealing (classical)"}

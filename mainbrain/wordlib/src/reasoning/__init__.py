"""
WORDLIB reasoning package (v13).
Real reasoning-support layers. None claim to detect hallucination or perform
quantum computation. Quantum-inspired = classical algorithms with metaphor names.
"""

from .output_quality import OutputQualityChecker, QualityResult
from .reasoning_guard import ReasoningGuard, GuardVerdict
from .math_validator import MathValidator, MathResult
from .code_reasoner import CodeReasoner, CodeAnalysis
from .structured_output import StructuredOutputEngine, ParseResult
from .reasoning_engine import ReasoningEngine, ReasoningTrace, ReasoningStep
from .uncertainty_quantifier import UncertaintyQuantifier, Interval
from .quantum_inspired_optimizer import QuantumInspiredOptimizer, Hypothesis, softmax
from .prometheus_judge import PrometheusJudge, JudgeVerdict

__all__ = [
    "OutputQualityChecker", "QualityResult",
    "ReasoningGuard", "GuardVerdict",
    "MathValidator", "MathResult",
    "CodeReasoner", "CodeAnalysis",
    "StructuredOutputEngine", "ParseResult",
    "ReasoningEngine", "ReasoningTrace", "ReasoningStep",
    "UncertaintyQuantifier", "Interval",
    "QuantumInspiredOptimizer", "Hypothesis", "softmax",
    "PrometheusJudge", "JudgeVerdict",
]

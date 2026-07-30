"""
Tests for ReasoningGuard and PrometheusJudge -- the two reasoning-stack modules
that had no coverage at all.

Both exist to make honesty checkable, which makes them exactly the wrong place
for an untested assumption: a guard that silently stops guarding, or a judge
that reports a heuristic score as a model score, fails in the one direction
nobody notices, because the output still looks like a confident number.

The judge is tested without a live model server. `_ollama_available` and
`_call_ollama` are the seams: stubbing them makes the model-backed path
deterministic and lets the malformed-response cases be exercised on purpose
rather than waited for.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reasoning.prometheus_judge import CHAT_RUBRIC, CREATIVE_RUBRIC, PrometheusJudge
from reasoning.reasoning_guard import ReasoningGuard


def _judge_returning(payload: str) -> PrometheusJudge:
    """A judge whose 'model server' returns exactly `payload`."""
    j = PrometheusJudge()
    j._ollama_available = lambda: True
    j._call_ollama = lambda _prompt: payload
    return j


# ── ReasoningGuard ───────────────────────────────────────────────────────────
def test_guard_flags_overconfident_text():
    v = ReasoningGuard().evaluate(
        "This is 100% guaranteed flawless, it just works, trust me."
    )
    assert v.passed is False
    assert v.flags


def test_guard_passes_measured_evidence_based_text():
    v = ReasoningGuard().evaluate(
        "The suite reports 280 passing tests; see tests/run_tests.py output for "
        "the run this figure comes from."
    )
    assert v.passed is True


def test_guard_verdict_always_carries_its_disclaimer():
    """The disclaimer is the honesty invariant, not decoration.

    A passing verdict means "few red-flag patterns", never "verified true". If
    this string ever goes missing, a caller can quote a pass as if it were a
    correctness result -- which is the specific misuse the disclaimer prevents.
    """
    for text in ("", "totally guaranteed perfect", "a measured, sourced claim"):
        v = ReasoningGuard().evaluate(text)
        assert "NOT verified truth" in v.disclaimer


def test_guard_suggestion_is_actionable_for_each_flag_kind():
    v = ReasoningGuard().evaluate("100% guaranteed, it just works, trust me.")
    assert v.suggestion
    assert v.suggestion != "tighten phrasing"  # the generic last resort


def test_guard_clean_pass_still_tells_you_to_verify():
    v = ReasoningGuard().evaluate("The function returns the parsed configuration.")
    if v.passed and not v.flags:
        assert "verify" in v.suggestion.lower()


# ── PrometheusJudge: honest degradation ──────────────────────────────────────
def test_judge_falls_back_and_says_so_when_no_server():
    j = PrometheusJudge()
    j._ollama_available = lambda: False
    v = j.judge("some text")
    assert v.mode == "heuristic-fallback"
    assert "NOT a real judge model" in v.note


def test_judge_falls_back_when_model_output_is_unparseable():
    v = _judge_returning("this is not json at all, sorry").judge("t")
    assert v.mode == "heuristic-fallback"
    assert "unparseable" in v.note


def test_judge_falls_back_when_json_is_not_an_object():
    """Valid JSON is not necessarily a usable verdict.

    A bare list parses fine but has no criteria in it; reading it as one used
    to depend on `.get` existing on whatever came back.
    """
    v = _judge_returning("[1, 2, 3]").judge("t")
    assert v.mode == "heuristic-fallback"
    assert "not an object" in v.note


def test_judge_falls_back_when_no_criterion_is_numeric():
    """Reporting 0.0 here would be indistinguishable from a genuine bad score.

    "The model said this is terrible" and "the model said nothing usable" are
    different facts and must not collapse to the same number.
    """
    v = _judge_returning('{"coherence": "great", "narrative": null}').judge("t")
    assert v.mode == "heuristic-fallback"
    assert "no usable numeric scores" in v.note


def test_every_fallback_path_agrees_between_mode_and_note():
    """`mode` is what callers branch on, `note` is what humans read.

    If they can disagree, one audience is being misled.
    """
    unreachable = PrometheusJudge()
    unreachable._ollama_available = lambda: False
    verdicts = [
        unreachable.judge("t"),
        _judge_returning("not json").judge("t"),
        _judge_returning("[1,2]").judge("t"),
        _judge_returning('{"coherence": "x"}').judge("t"),
    ]
    for v in verdicts:
        assert v.mode == "heuristic-fallback"
        assert "fell back" in v.note or "heuristic" in v.note.lower()
        assert set(v.scores) == {"surface_quality"}


# ── PrometheusJudge: score normalization (the measured bugs) ─────────────────
def test_scores_above_the_band_are_clamped_not_scaled():
    """Measured: a returned 50 became 5.0 and pushed overall to 1.68 (168%)."""
    v = _judge_returning(
        '{"coherence": 50, "narrative": 10, "emotional": 8, '
        '"originality": 7, "degeneracy": 9}'
    ).judge("t")
    assert v.mode == "model"
    assert v.scores["coherence"] == 1.0
    assert all(0.0 <= s <= 1.0 for s in v.scores.values())
    assert 0.0 <= v.overall <= 1.0


def test_negative_scores_are_clamped_to_zero():
    """Measured: a returned -30 became -3.0 and dragged overall negative."""
    v = _judge_returning(
        '{"coherence": -30, "narrative": 5, "emotional": 5, '
        '"originality": 5, "degeneracy": 5}'
    ).judge("t")
    assert v.scores["coherence"] == 0.0
    assert v.overall >= 0.0


def test_non_numeric_criterion_does_not_raise():
    """Measured: this raised ValueError straight past every fallback."""
    v = _judge_returning('{"coherence": "excellent", "narrative": 5}').judge("t")
    assert v.mode == "model"
    assert "coherence" not in v.scores
    assert v.scores["narrative"] == 0.5


def test_partial_scoring_is_disclosed_in_the_note():
    """An average over 1 of 5 criteria is weaker than one over 5.

    The number alone cannot show that, so the note has to.
    """
    v = _judge_returning('{"coherence": "excellent", "narrative": 5}').judge("t")
    assert "ignored" in v.note
    assert "1 unusable" in v.note


def test_booleans_are_rejected_rather_than_scored():
    """`True` is an int in Python, so True/10 = 0.1 -- a plausible-looking
    score from a value that carries no rating at all."""
    v = _judge_returning('{"coherence": true, "narrative": 8}').judge("t")
    assert "coherence" not in v.scores
    assert v.scores["narrative"] == 0.8


def test_numeric_strings_are_accepted():
    """Models routinely quote numbers; that is a formatting quirk, not a
    missing rating, so it should not cost a criterion."""
    v = _judge_returning('{"coherence": "8", "narrative": 6}').judge("t")
    assert v.scores["coherence"] == 0.8
    assert "ignored" not in v.note


def test_wellformed_response_scores_normally():
    v = _judge_returning(
        '{"coherence": 8, "narrative": 7, "emotional": 6, '
        '"originality": 9, "degeneracy": 10, "suggestions": ["tighten the ending"]}'
    ).judge("t")
    assert v.mode == "model"
    assert v.scores == {
        "coherence": 0.8, "narrative": 0.7, "emotional": 0.6,
        "originality": 0.9, "degeneracy": 1.0,
    }
    assert abs(v.overall - 0.8) < 1e-9
    assert v.suggestions == ["tighten the ending"]
    assert "not a calibrated benchmark" in v.note


def test_suggestions_must_be_a_list_to_be_used():
    v = _judge_returning(
        '{"coherence": 8, "narrative": 7, "suggestions": "just one string"}'
    ).judge("t")
    assert v.suggestions == []


# ── Rubric wiring ────────────────────────────────────────────────────────────
def test_chat_and_creative_rubrics_are_distinct_and_reach_the_prompt():
    j = PrometheusJudge()
    creative = j._build_prompt("text", CREATIVE_RUBRIC)
    chat = j._build_prompt("text", CHAT_RUBRIC)
    assert all(k in creative for k in CREATIVE_RUBRIC)
    assert all(k in chat for k in CHAT_RUBRIC)
    assert "narrative" in creative and "narrative" not in chat


def test_kind_selects_the_rubric_actually_scored():
    payload = ('{"relevance": 8, "accuracy": 8, "clarity": 8, "honesty": 8, '
               '"coherence": 2}')
    v = _judge_returning(payload).judge("t", kind="chat")
    # coherence belongs to the creative rubric and must be ignored for chat,
    # otherwise the two rubrics silently bleed into each other.
    assert set(v.scores) == set(CHAT_RUBRIC)


def test_prompt_bounds_the_text_it_sends():
    """A judge prompt should not grow without limit with its input."""
    j = PrometheusJudge()
    prompt = j._build_prompt("x" * 10_000, CREATIVE_RUBRIC)
    assert prompt.count("x") == 4000


def test_verdict_as_dict_is_json_shaped():
    v = _judge_returning('{"coherence": 8, "narrative": 7}').judge("t")
    d = v.as_dict()
    assert set(d) == {"mode", "scores", "overall", "suggestions", "note"}
    assert isinstance(d["overall"], float)

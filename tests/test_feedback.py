"""Milestone 19: the learning feedback loop, M4's deliberately unbuilt half.

Two readers close the loop the feedback record opened in v0.4.0. Engineer
verdicts become rule gaps ("the platform is reliably wrong here"), and
engineer votes reorder the advice a run produces. Both are deterministic
aggregations over recorded history, and neither is allowed to change a
conclusion: the tests below are mostly about what stays the same.
"""

from __future__ import annotations

import pytest

from veritriage.analytics import RegressionAnalytics
from veritriage.dashboard import DashboardGenerator
from veritriage.feedback import (
    FeedbackRecord,
    MIN_VOTES,
    recommendation_weights,
    reweight_recommendations,
)
from veritriage.learning import Corpus, LearningStore, available_learners
from veritriage.learning.learners.gaps import MIN_INCORRECT, compute_rule_gaps
from veritriage.models import EngineeringRecommendation, RecommendationOutcome
from veritriage.pipeline import analyze
from veritriage.storage import RegressionStore
from veritriage.workspace import WorkspaceServices


def _rec(action: str, priority: int) -> EngineeringRecommendation:
    return EngineeringRecommendation(
        action=action,
        rationale="because the evidence says so",
        priority=priority,
        effort="low",
        confidence=0.5,
    )


def _outcome(action: str, useful: int, false: int) -> RecommendationOutcome:
    total = useful + false
    return RecommendationOutcome(
        artifact_id=f"lp-recommendation_outcome-{action[:8]}",
        key=action,
        summary="",
        observations=total,
        action=action,
        useful_votes=useful,
        false_votes=false,
        usefulness=round(useful / total, 4) if total else None,
    )


# --- Weighting -------------------------------------------------------------


def test_weights_ignore_actions_without_enough_votes():
    weights = recommendation_weights(
        [_outcome("thin", 1, 0), _outcome("solid", 3, 1)]
    )
    assert "thin" not in weights, "one vote is an opinion, not a weight"
    assert weights["solid"] == 0.75


def test_min_votes_is_the_documented_threshold():
    assert recommendation_weights([_outcome("a", MIN_VOTES, 0)]) == {"a": 1.0}
    assert recommendation_weights([_outcome("a", MIN_VOTES - 1, 0)]) == {}


def test_unrated_outcomes_never_enter_the_table():
    assert recommendation_weights([_outcome("never-rated", 0, 0)]) == {}


# --- Reordering ------------------------------------------------------------


def test_useful_advice_rises_and_time_wasting_advice_sinks():
    recs = [_rec("wasted time", 1), _rec("neutral", 2), _rec("helped", 3)]
    weights = {"wasted time": 0.0, "helped": 1.0}
    out = reweight_recommendations(recs, weights)
    assert [r.action for r in out] == ["helped", "neutral", "wasted time"]
    assert [r.priority for r in out] == [1, 2, 3], "priorities stay contiguous"


def test_reordering_never_adds_removes_or_edits_advice():
    recs = [_rec("a", 1), _rec("b", 2), _rec("c", 3)]
    out = reweight_recommendations(recs, {"c": 1.0, "a": 0.0})
    assert sorted(r.action for r in out) == ["a", "b", "c"]
    for original in recs:
        after = next(r for r in out if r.action == original.action)
        assert after.rationale == original.rationale
        assert after.confidence == original.confidence
        assert after.effort == original.effort


def test_no_weights_means_the_list_is_returned_untouched():
    recs = [_rec("a", 1), _rec("b", 2)]
    assert reweight_recommendations(recs, {}) is recs


def test_equally_rated_advice_keeps_its_deterministic_order():
    recs = [_rec("first", 1), _rec("second", 2)]
    out = reweight_recommendations(recs, {"first": 0.8, "second": 0.8})
    assert [r.action for r in out] == ["first", "second"]


def test_reordering_is_deterministic():
    recs = [_rec("a", 1), _rec("b", 2), _rec("c", 3)]
    weights = {"a": 0.2, "b": 0.9, "c": 0.5}
    runs = [[r.action for r in reweight_recommendations(recs, weights)] for _ in range(5)]
    assert len(set(map(tuple, runs))) == 1


# --- Rule gaps -------------------------------------------------------------


@pytest.fixture()
def overruled(tmp_path, fixture_log):
    """History where one signature was judged wrong repeatedly."""
    db = tmp_path / "regressions.db"
    services = WorkspaceServices(session_root=tmp_path / "sessions", db=db)
    for _ in range(3):
        services.investigate([fixture_log("uvm_scoreboard.log")], record_history=True)
    services.investigate([fixture_log("axi_timeout.log")], record_history=True)

    with RegressionStore(db) as store:
        for record in store.all_records():
            if record.classification == "testbench_failure":
                store.save_feedback(
                    FeedbackRecord(
                        regression_id=record.regression_id,
                        diagnosis="incorrect",
                        actual_root_cause="Clock gating in the DUT, not the predictor",
                    )
                )
    return services, db


def test_repeated_overrules_become_a_rule_gap(overruled):
    _, db = overruled
    with RegressionStore(db) as store:
        gaps = compute_rule_gaps(Corpus(store.all_records(), store.all_feedback()))
    assert gaps, "three overruled runs of one signature should raise a gap"
    gap = gaps[0]
    assert gap.times_incorrect >= MIN_INCORRECT
    assert gap.incorrect_rate == 1.0
    assert "Clock gating in the DUT, not the predictor" in gap.reported_root_causes
    assert gap.supporting_regressions, "a gap must cite the runs behind it"


def test_a_single_overrule_is_not_a_gap(tmp_path, fixture_log):
    db = tmp_path / "regressions.db"
    services = WorkspaceServices(session_root=tmp_path / "s", db=db)
    services.investigate([fixture_log("uvm_scoreboard.log")], record_history=True)
    with RegressionStore(db) as store:
        record = store.all_records()[0]
        store.save_feedback(
            FeedbackRecord(regression_id=record.regression_id, diagnosis="incorrect")
        )
        gaps = compute_rule_gaps(Corpus(store.all_records(), store.all_feedback()))
    assert gaps == [], "one overrule is an anecdote"


def test_confirmed_diagnoses_never_become_gaps(tmp_path, fixture_log):
    db = tmp_path / "regressions.db"
    services = WorkspaceServices(session_root=tmp_path / "s", db=db)
    for _ in range(3):
        services.investigate([fixture_log("uvm_scoreboard.log")], record_history=True)
    with RegressionStore(db) as store:
        for record in store.all_records():
            store.save_feedback(
                FeedbackRecord(regression_id=record.regression_id, diagnosis="correct")
            )
        gaps = compute_rule_gaps(Corpus(store.all_records(), store.all_feedback()))
    assert gaps == []


def test_rule_gaps_are_a_pure_function_of_history(overruled):
    _, db = overruled
    with RegressionStore(db) as store:
        corpus = Corpus(store.all_records(), store.all_feedback())
        first = compute_rule_gaps(corpus)
        second = compute_rule_gaps(corpus)
    assert [g.model_dump() for g in first] == [g.model_dump() for g in second]


def test_gap_learner_is_registered_like_any_other():
    assert "rule-gaps" in available_learners()


def test_gaps_round_trip_through_the_learning_store(overruled, tmp_path):
    services, _ = overruled
    services.learn_from_history()
    stored = services.learning_artifacts("rule_gap")
    assert stored, "the learner should have persisted its gaps"
    assert stored[0].kind == "rule_gap"
    assert stored[0].times_incorrect >= MIN_INCORRECT


# --- The surfaces ----------------------------------------------------------


def test_dashboard_shows_the_needs_a_new_rule_section(overruled, tmp_path):
    _, db = overruled
    with RegressionStore(db) as store:
        html = DashboardGenerator(store).render()
    assert "Needs a New Rule" in html
    assert "overruled" in html


def test_dashboard_omits_the_section_without_gaps(tmp_path, fixture_log):
    db = tmp_path / "regressions.db"
    services = WorkspaceServices(session_root=tmp_path / "s", db=db)
    services.investigate([fixture_log("uvm_scoreboard.log")], record_history=True)
    with RegressionStore(db) as store:
        html = DashboardGenerator(store).render()
    assert "Needs a New Rule" not in html


def test_analytics_carries_the_same_gaps_as_the_learner(overruled):
    _, db = overruled
    with RegressionStore(db) as store:
        analytics = RegressionAnalytics(store).compute()
        direct = compute_rule_gaps(Corpus(store.all_records(), store.all_feedback()))
    assert [g.artifact_id for g in analytics.rule_gaps] == [g.artifact_id for g in direct]


# --- The guarantee ---------------------------------------------------------


def test_feedback_reorders_advice_without_touching_any_conclusion(
    overruled, fixture_log
):
    """The whole point: advice may move, conclusions may not."""
    services, _ = overruled
    services.learn_from_history()
    recalled = services.recall_learning()
    assert recalled is not None

    bare = analyze(fixture_log("uvm_scoreboard.log"))
    lensed = analyze(fixture_log("uvm_scoreboard.log"), learning=recalled)

    assert bare.report.classification == lensed.report.classification
    assert [(h.id, h.confidence) for h in bare.report.reasoning.hypotheses] == [
        (h.id, h.confidence) for h in lensed.report.reasoning.hypotheses
    ]
    assert [s.name for s in bare.report.reasoning.signals] == [
        s.name for s in lensed.report.reasoning.signals
    ]
    # Same advice either way, whatever order it ended up in.
    assert sorted(r.action for r in bare.report.reasoning.recommendations) == sorted(
        r.action for r in lensed.report.reasoning.recommendations
    )


def test_platform_without_learning_produces_the_original_order(tmp_path, fixture_log):
    """No learning context means the pre-M19 recommendation order, exactly."""
    services = WorkspaceServices(session_root=tmp_path / "s")
    assert services.recall_learning() is None
    session = services.investigate([fixture_log("uvm_scoreboard.log")])
    direct = analyze(fixture_log("uvm_scoreboard.log"))
    assert [r.action for r in session.report.reasoning.recommendations] == [
        r.action for r in direct.report.reasoning.recommendations
    ]
    assert [r.priority for r in session.report.reasoning.recommendations] == [
        r.priority for r in direct.report.reasoning.recommendations
    ]

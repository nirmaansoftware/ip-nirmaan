"""Milestone 13: the Learning Engine.

Covers the milestone's guarantees, not just its features: learning is a pure
function of recorded history; it never mutates evidence or reasoning; it is
removable without a trace; hints never become conclusions; calibration is
bounded and explainable; and, above all, a brand-new learner needs only a
registration (the crown-jewel architecture test at the bottom of this file).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import imports

import veritriage.learning.engine as engine_module
from veritriage.agents import AgentCoordinator, build_agent_context
from veritriage.feedback import FeedbackRecord
from veritriage.learning import (
    Corpus,
    Learner,
    LearningEngine,
    LearningStore,
    MAX_MULTIPLIER,
    MIN_MULTIPLIER,
    MIN_OBSERVATIONS,
    available_learners,
    calibration_multiplier,
    default_learners,
    get_learner,
    register_learner,
    unregister_learner,
)
from veritriage.mcp.tools import call_tool
from veritriage.models import AgentReliability, LearningArtifact, ProjectProfile
from veritriage.pipeline import analyze
from veritriage.storage import RegressionStore
from veritriage.workspace import WorkspaceServices

# .../src/veritriage/learning/engine.py -> parents[2] is the src/ root.
SRC = Path(engine_module.__file__).parents[2]

BUILT_IN = {
    "agent-reliability",
    "evidence-patterns",
    "hypothesis-history",
    "investigation-patterns",
    "project-profiles",
    "protocol-statistics",
    "recommendation-outcomes",
}


@pytest.fixture()
def workspace(tmp_path, fixture_log):
    """A workspace with a small recorded history and engineer feedback.

    Two runs of one failure mode (so it recurs), one of another, and a
    confirmed diagnosis on the recurring pair.
    """
    db = tmp_path / "regressions.db"
    services = WorkspaceServices(session_root=tmp_path / "sessions", db=db)
    for name in ("uvm_scoreboard.log", "uvm_scoreboard.log", "axi_timeout.log"):
        services.investigate([fixture_log(name)], record_history=True)

    with RegressionStore(db) as store:
        for record in store.all_records():
            if record.classification == "testbench_failure":
                store.save_feedback(
                    FeedbackRecord(
                        regression_id=record.regression_id,
                        diagnosis="correct",
                        actual_root_cause="Predictor missed a back-to-back write",
                        useful_recommendations=["Review the scoreboard prediction"],
                        false_recommendations=["Rerun on another host"],
                    )
                )
    services.learn_from_history()
    return services


@pytest.fixture()
def corpus(workspace, tmp_path):
    with RegressionStore(tmp_path / "regressions.db") as store:
        return Corpus(store.all_records(), store.all_feedback())


# --- The registry -----------------------------------------------------------


def test_seven_built_in_learners_register():
    assert BUILT_IN <= set(available_learners())


def test_learners_run_in_deterministic_id_order():
    assert [x.learner_id for x in default_learners()] == sorted(available_learners())


def test_duplicate_learner_id_is_rejected():
    class _Clash(Learner):
        learner_id = "agent-reliability"
        artifact_kind = "agent_reliability"

        def observe(self, corpus):  # pragma: no cover - never runs
            raise AssertionError

    with pytest.raises(ValueError, match="already registered"):
        register_learner(_Clash)


def test_unknown_learner_raises_with_the_registered_list():
    with pytest.raises(KeyError, match="Unknown learner"):
        get_learner("no-such-learner")


# --- The central law: purity ------------------------------------------------


def test_learning_is_a_pure_function_of_history(tmp_path, corpus):
    """The same corpus must produce byte-identical artifacts, every time."""
    first, second = tmp_path / "a.db", tmp_path / "b.db"
    with LearningStore(first) as store_a, LearningStore(second) as store_b:
        LearningEngine(store_a).observe(corpus.records, corpus.feedback)
        LearningEngine(store_b).observe(corpus.records, corpus.feedback)
        assert store_a.export() == store_b.export()


def test_learning_is_independent_of_arrival_order(tmp_path, corpus):
    forward, backward = tmp_path / "f.db", tmp_path / "r.db"
    with LearningStore(forward) as store_f, LearningStore(backward) as store_r:
        LearningEngine(store_f).observe(corpus.records, corpus.feedback)
        LearningEngine(store_r).observe(
            list(reversed(corpus.records)), list(reversed(corpus.feedback))
        )
        assert store_f.export() == store_r.export()


def test_rebuilding_is_idempotent(workspace):
    first = workspace.learn_from_history()
    second = workspace.learn_from_history()
    assert first.artifacts_by_kind == second.artifacts_by_kind


def test_artifact_timestamps_come_from_the_corpus_not_the_clock(corpus):
    """`as_of` is the newest recorded run, which is what makes purity hold."""
    newest = max(r.created_at for r in corpus.records).isoformat()
    assert corpus.as_of == newest


def test_no_artifact_id_depends_on_process_hashing(tmp_path, corpus):
    """Artifact IDs must be content digests: builtin hash() is salted per process."""
    ids = set()
    for name in ("one.db", "two.db"):
        with LearningStore(tmp_path / name) as store:
            LearningEngine(store).observe(corpus.records, corpus.feedback)
            ids.add(tuple(sorted(a.artifact_id for a in store.all_artifacts())))
    assert len(ids) == 1


# --- Artifacts --------------------------------------------------------------


def test_every_artifact_links_back_to_investigations(workspace):
    artifacts = workspace.learning_artifacts()
    assert artifacts
    for artifact in artifacts:
        assert artifact.summary, artifact.artifact_id
        assert artifact.observations >= 0
        if artifact.observations > 0 and artifact.kind != "recommendation_outcome":
            assert artifact.supporting_regressions, artifact.artifact_id


def test_recurring_failure_becomes_an_investigation_pattern(workspace):
    patterns = workspace.learning_artifacts("investigation_pattern")
    assert patterns, "a failure seen twice should be learned as recurring"
    pattern = patterns[0]
    assert pattern.observations >= 2
    assert "Predictor missed a back-to-back write" in pattern.confirmed_root_causes
    assert "Review the scoreboard prediction" in pattern.successful_actions


def test_one_off_failures_are_not_learned_as_patterns(workspace):
    for pattern in workspace.learning_artifacts("investigation_pattern"):
        assert pattern.observations >= 2


def test_evidence_combinations_are_learned(workspace):
    patterns = workspace.learning_artifacts("evidence_pattern")
    assert patterns
    for pattern in patterns:
        assert pattern.signal_set
        assert 0.0 <= pattern.share <= 1.0
        assert pattern.dominant_classification


def test_agent_reliability_is_measured_only_over_judged_runs(workspace):
    reliability = {a.agent_id: a for a in workspace.agent_reliability()}
    assert reliability
    for item in reliability.values():
        assert item.times_correct <= item.times_led
        if item.accuracy is not None:
            assert 0.0 <= item.accuracy <= 1.0
            assert item.times_led > 0


def test_project_profile_records_maturity_and_dominant_failures(workspace):
    profile = workspace.project_memory()
    assert isinstance(profile, ProjectProfile)
    assert profile.observations == 3
    assert profile.dominant_classifications
    assert "establishing" in profile.verification_maturity
    assert profile.details["unknown_failure_rate"] >= 0.0


def test_protocol_statistics_count_pack_matches(workspace):
    stats = workspace.learning_artifacts("protocol_statistics")
    assert stats
    for item in stats:
        assert item.times_matched > 0
        assert item.times_with_confirmation <= item.times_matched


def test_recommendation_outcomes_read_the_feedback_nothing_else_reads(workspace):
    outcomes = {
        a.action: a for a in workspace.learning_artifacts("recommendation_outcome")
    }
    assert "Review the scoreboard prediction" in outcomes
    assert outcomes["Review the scoreboard prediction"].useful_votes == 2
    assert outcomes["Rerun on another host"].false_votes == 2
    assert outcomes["Rerun on another host"].usefulness == 0.0


def test_hypothesis_history_tracks_confirmation(workspace):
    histories = {a.category: a for a in workspace.learning_artifacts("hypothesis_history")}
    assert histories
    for item in histories.values():
        assert item.times_confirmed <= item.times_led


# --- Calibration ------------------------------------------------------------


def test_calibration_needs_evidence_before_it_applies():
    assert calibration_multiplier(1.0, MIN_OBSERVATIONS - 1) == 1.0
    assert calibration_multiplier(0.0, MIN_OBSERVATIONS - 1) == 1.0
    assert calibration_multiplier(None, 100) == 1.0


def test_calibration_is_bounded():
    """No amount of history can silence a specialist or crown one."""
    for accuracy in (0.0, 0.25, 0.5, 0.75, 1.0):
        multiplier = calibration_multiplier(accuracy, 50)
        assert MIN_MULTIPLIER <= multiplier <= MAX_MULTIPLIER
    assert calibration_multiplier(1.0, 50) > calibration_multiplier(0.0, 50)
    assert calibration_multiplier(0.5, 50) == 1.0


def test_empty_calibration_is_byte_identical_to_no_calibration(fixture_log):
    outcome = analyze(fixture_log("axi_timeout.log"))
    context = build_agent_context(
        graph=outcome.graph,
        classification=outcome.report.classification,
        reasoning=outcome.report.reasoning,
        knowledge=outcome.report.knowledge,
    )
    plain = AgentCoordinator().coordinate(context)
    empty = AgentCoordinator(calibration={}).coordinate(context)
    assert plain.model_dump(mode="json") == empty.model_dump(mode="json")


def test_calibration_changes_influence_and_is_explained(fixture_log):
    outcome = analyze(fixture_log("axi_timeout.log"))
    context = build_agent_context(
        graph=outcome.graph,
        classification=outcome.report.classification,
        reasoning=outcome.report.reasoning,
        knowledge=outcome.report.knowledge,
    )
    plain = AgentCoordinator().coordinate(context)
    leader = plain.findings[0].supporting_agents[0]
    demoted = AgentCoordinator(calibration={leader: MIN_MULTIPLIER}).coordinate(context)

    before = plain.findings[0]
    after = next(f for f in demoted.findings if f.category is before.category)
    assert after.confidence < before.confidence
    # And the adjustment is readable line by line, like every other confidence.
    assert any("Historical calibration" in c.reason for c in after.contributions)


def test_calibration_never_changes_what_an_agent_concluded(fixture_log):
    outcome = analyze(fixture_log("axi_timeout.log"))
    context = build_agent_context(
        graph=outcome.graph,
        classification=outcome.report.classification,
        reasoning=outcome.report.reasoning,
        knowledge=outcome.report.knowledge,
    )
    plain = AgentCoordinator().coordinate(context)
    calibrated = AgentCoordinator(calibration={"rtl": MIN_MULTIPLIER}).coordinate(context)

    def positions(assessment):
        return [
            (r.agent_id, [(h.category, h.confidence, tuple(h.evidence_ids)) for h in r.hypotheses])
            for r in assessment.results
        ]

    assert positions(plain) == positions(calibrated)


# --- Learning never overrides deterministic intelligence --------------------


def test_learning_never_changes_graph_or_reasoning(workspace, fixture_log):
    """Recall must not touch a single deterministic conclusion."""
    bare = analyze(fixture_log("uvm_scoreboard.log"))
    recalled = workspace.recall_learning()
    assert recalled is not None
    lensed = analyze(fixture_log("uvm_scoreboard.log"), learning=recalled)

    assert set(bare.graph.nodes) == set(lensed.graph.nodes)
    assert len(bare.graph.edges) == len(lensed.graph.edges)
    assert bare.report.classification == lensed.report.classification
    assert [
        (h.id, h.confidence) for h in bare.report.reasoning.hypotheses
    ] == [(h.id, h.confidence) for h in lensed.report.reasoning.hypotheses]
    assert [s.name for s in bare.report.reasoning.signals] == [
        s.name for s in lensed.report.reasoning.signals
    ]


def test_platform_without_learning_matches_previous_behaviour(tmp_path, fixture_log):
    """No learning store means exact pre-M13 behavior."""
    services = WorkspaceServices(session_root=tmp_path / "s")
    assert services.recall_learning() is None
    assert services.learning_statistics() is None
    assert services.learning_artifacts() == []
    assert services.agent_reliability() == []
    session = services.investigate([fixture_log("axi_timeout.log")])
    assert session.report.learning is None


def test_hints_never_become_hypotheses(workspace, fixture_log):
    """History may inform an investigation; it can never manufacture evidence."""
    recalled = workspace.recall_learning()
    outcome = analyze(fixture_log("uvm_scoreboard.log"), learning=recalled)
    graph = outcome.graph
    for result in outcome.report.agents.results:
        for hypothesis in result.hypotheses:
            assert hypothesis.evidence_ids
            for node_id in hypothesis.evidence_ids:
                assert node_id in graph.nodes, "a hypothesis cited something not in this run"


def test_learning_adds_no_artifact_type():
    from veritriage.graph.model import ArtifactType

    assert not any("learn" in t.value for t in ArtifactType)


def test_learning_never_rewrites_the_regression_database(workspace, tmp_path):
    with RegressionStore(tmp_path / "regressions.db") as store:
        before = store.export() if hasattr(store, "export") else store.count()
    workspace.learn_from_history()
    with RegressionStore(tmp_path / "regressions.db") as store:
        after = store.export() if hasattr(store, "export") else store.count()
    assert before == after


# --- Recall -----------------------------------------------------------------


def test_recall_ranks_hints_and_carries_provenance(workspace):
    context = workspace.recall_learning()
    assert context is not None and context.hints
    strengths = [h.strength for h in context.hints]
    assert strengths == sorted(strengths, reverse=True)
    assert all(h.artifact_id for h in context.hints)
    assert context.corpus_size == 3


def test_recall_is_empty_before_anything_is_learned(tmp_path):
    services = WorkspaceServices(session_root=tmp_path / "s", db=tmp_path / "r.db")
    assert services.recall_learning() is None


def test_augment_attaches_the_signature_specific_pattern(workspace, fixture_log):
    session = workspace.investigate([fixture_log("uvm_scoreboard.log")], record_history=True)
    learning = session.report.learning
    assert learning is not None
    assert learning.recurring_pattern is not None
    assert learning.recurring_pattern.observations >= 2


def test_agents_receive_memory_before_they_run(workspace, fixture_log):
    """Recall must reach the agents themselves, not only the finished report."""
    recalled = workspace.recall_learning()
    assert recalled.hints_of_kind("investigation_pattern"), "patterns must be recalled up front"

    outcome = analyze(fixture_log("uvm_scoreboard.log"), learning=recalled)
    regression = next(
        r for r in outcome.report.agents.results if r.agent_id == "regression"
    )
    assert regression.applicable
    assert any(
        "Learned from prior investigations" in o.statement for o in regression.observations
    )


def test_agents_without_learning_are_unaffected(fixture_log):
    outcome = analyze(fixture_log("uvm_scoreboard.log"))
    regression = next(
        r for r in outcome.report.agents.results if r.agent_id == "regression"
    )
    assert not regression.applicable


# --- Architecture guards ----------------------------------------------------


def test_no_models_or_embeddings_in_learning():
    """No LLMs, no embeddings, no vector databases, no opaque intelligence."""
    banned = (
        "anthropic",
        "openai",
        "torch",
        "sklearn",
        "numpy",
        "sentence_transformers",
        "faiss",
        "chromadb",
        "embed(",
    )
    for path in (SRC / "veritriage" / "learning").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_learning_never_reads_raw_artifacts():
    """Learners see stored, normalized records; never a log file."""
    for path in (SRC / "veritriage" / "learning").rglob("*.py"):
        if path.name == "persistence.py":
            continue  # the store legitimately owns its own SQLite file
        text = path.read_text(encoding="utf-8")
        for term in (".read_text", ".read_bytes", "open("):
            assert term not in text, f"{path.name} performs artifact I/O ({term})"


def test_learning_never_imports_extraction_or_engine_layers():
    banned = (
        "veritriage.parsers",
        "veritriage.reasoning",
        "veritriage.rules",
        "veritriage.agents",
        "veritriage.workspace",
        "veritriage.pipeline",
    )
    for path in (SRC / "veritriage" / "learning").rglob("*.py"):
        imported = imports(path)
        for module in banned:
            assert module not in imported, f"{path.name} imports {module}"


def test_core_unchanged_by_learning():
    """Dependencies point outward: nothing in the core imports the learning layer."""
    for package in (
        "graph",
        "parsers",
        "rules",
        "reasoning",
        "knowledge",
        "waveform",
        "engineering",
        "project",
        "agents",
        "history",
        "signatures",
        "similarity",
    ):
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            assert "veritriage.learning" not in imports(path), path


def test_agents_gain_memory_without_importing_learning():
    """The whole point of passing hints as plain data through models/."""
    for path in (SRC / "veritriage" / "agents").rglob("*.py"):
        assert "veritriage.learning" not in path.read_text(encoding="utf-8"), path


def test_learning_vocabulary_is_plain_data():
    imported = imports(SRC / "veritriage" / "models" / "learning.py")
    assert not any(
        m.startswith("veritriage.") and not m.startswith("veritriage.models")
        for m in imported
    )


# --- Clients ----------------------------------------------------------------


def test_learning_over_mcp(workspace, fixture_log):
    session = workspace.investigate([fixture_log("uvm_scoreboard.log")], record_history=True)
    workspace.save(session)

    stats = call_tool(workspace, "learning_statistics", {})
    assert stats["corpus_size"] >= 3
    assert stats["learners"]

    relearned = call_tool(workspace, "learn_from_history", {})
    assert relearned["artifacts_by_kind"]

    patterns = call_tool(workspace, "recent_patterns", {"kind": "investigation_pattern"})
    assert patterns and patterns[0]["kind"] == "investigation_pattern"

    reliability = call_tool(workspace, "agent_reliability", {})
    assert reliability

    memory = call_tool(workspace, "project_memory", {})
    assert memory["verification_maturity"]

    similar = call_tool(
        workspace, "similar_investigations", {"session_id": session.session_id}
    )
    assert isinstance(similar, list)


def test_report_renders_the_learning_section(workspace, fixture_log, tmp_path):
    from veritriage.reports import HtmlReportGenerator

    recalled = workspace.recall_learning()
    outcome = analyze(fixture_log("uvm_scoreboard.log"), learning=recalled)
    path = HtmlReportGenerator().write(
        outcome.report, tmp_path / "report.html", graph=outcome.graph
    )
    html = path.read_text(encoding="utf-8")
    assert "What Prior Investigations Suggest" in html
    assert "Project insight" in html


def test_store_survives_a_round_trip(tmp_path, corpus):
    path = tmp_path / "learning.db"
    with LearningStore(path) as store:
        LearningEngine(store).observe(corpus.records, corpus.feedback)
        exported = store.export()
        count = store.count()
    with LearningStore(path) as reopened:
        assert reopened.count() == count
        assert reopened.export() == exported
        assert all(isinstance(a, LearningArtifact) for a in reopened.all_artifacts())
        assert any(isinstance(a, AgentReliability) for a in reopened.all_artifacts())


def test_clearing_the_store_forgets_everything_but_keeps_history(workspace, tmp_path):
    from veritriage.learning import LearningStore as _Store

    with _Store(tmp_path / "learning.db") as store:
        assert store.count() > 0
        store.clear()
        assert store.count() == 0
    # History itself is untouched: learning can be rebuilt from it.
    assert workspace.learn_from_history().corpus_size == 3


# --- The crown jewel: a new learner is a registration and nothing else


class _FlakinessLearner(Learner):
    """A throwaway learner for a fictional family, defined in this test.

    It proves the milestone's success criterion: teaching the platform to learn
    something new requires writing ONLY a learner. It touches no core module,
    yet its artifact reaches the store, the statistics, and the recall path.
    """

    learner_id = "flakiness"
    artifact_kind = "flakiness"

    def observe(self, corpus: Corpus) -> list[LearningArtifact]:
        by_test: dict[str, list] = {}
        for record in corpus.records:
            if record.test_name:
                by_test.setdefault(record.test_name, []).append(record)
        return [
            LearningArtifact(
                artifact_id=f"lp-flakiness-{name}",
                kind="flakiness",
                key=name,
                summary=f"Test {name} has been recorded {len(group)} time(s).",
                observations=len(group),
                confidence=self._support(len(group)),
                supporting_regressions=corpus.cite(group),
                updated_at=corpus.as_of,
                details={"runs": len(group)},
            )
            for name, group in sorted(by_test.items())
        ]


def test_new_learner_needs_only_registration(workspace):
    register_learner(_FlakinessLearner)
    try:
        assert "flakiness" in available_learners()

        stats = workspace.learn_from_history()
        # It ran, with zero changes to the core...
        assert "flakiness" in stats.learners
        assert stats.artifacts_by_kind.get("flakiness", 0) > 0
        # ...and its artifacts round-tripped through the store, linked back to
        # the investigations that produced them.
        learned = workspace.learning_artifacts("flakiness")
        assert learned
        assert all(a.supporting_regressions for a in learned)
    finally:
        unregister_learner("flakiness")
        workspace.learn_from_history()

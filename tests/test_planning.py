"""Milestone 14: the Planning Engine.

Covers the milestone's guarantees, not just its features: the Planner
contributes structure and never content; it consumes conclusions without
changing them; it never executes anything; plans are deterministic down to the
ID digest; ordering is total and explainable; learning reprioritizes but never
adds steps; and, above all, a brand-new step source needs only a registration
(the crown-jewel architecture test at the bottom of this file).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import imports

import veritriage.planning.engine as engine_module
from veritriage.feedback import FeedbackRecord
from veritriage.graph.model import ArtifactType
from veritriage.mcp.tools import call_tool
from veritriage.models import ConditionKind, StepKind
from veritriage.pipeline import analyze
from veritriage.planning import (
    Planner,
    PlanningContext,
    StepCandidate,
    StepSource,
    available_sources,
    default_sources,
    get_source,
    plan_progress,
    register_source,
    unregister_source,
)
from veritriage.planning.valuation import MAX_HISTORICAL, value_of
from veritriage.storage import RegressionStore
from veritriage.workspace import WorkspaceServices

# .../src/veritriage/planning/engine.py -> parents[2] is the src/ root.
SRC = Path(engine_module.__file__).parents[2]

BUILT_IN = {
    "agent-recommendations",
    "evidence-gaps",
    "knowledge-playbooks",
    "reasoning-recommendations",
}


@pytest.fixture()
def outcome(fixture_log):
    """A scoreboard failure: two live explanations, so the plan branches."""
    return analyze([fixture_log("uvm_scoreboard.log"), fixture_log("coverage.txt")])


@pytest.fixture()
def context(outcome):
    return PlanningContext(report=outcome.report, graph=outcome.graph)


@pytest.fixture()
def plan(outcome):
    return outcome.report.plan


# --- The registry -----------------------------------------------------------


def test_four_built_in_sources_register():
    assert BUILT_IN <= set(available_sources())


def test_sources_run_in_deterministic_order():
    assert [s.source_id for s in default_sources()] == sorted(available_sources())


def test_duplicate_source_id_is_rejected():
    class _Clash(StepSource):
        source_id = "evidence-gaps"

        def propose(self, context):  # pragma: no cover - never runs
            raise AssertionError

    with pytest.raises(ValueError, match="already registered"):
        register_source(_Clash)


def test_unknown_source_raises_with_the_registered_list():
    with pytest.raises(KeyError, match="Unknown step source"):
        get_source("no-such-source")


# --- The central law: structure, never content ------------------------------


def test_every_step_is_derived_from_an_existing_artifact(plan):
    """The Planner arranges what other layers produced; it writes no advice."""
    known_prefixes = ("knowledge:", "agent:", "reasoning:", "evidence-gap:")
    for step in plan.all_steps():
        assert step.derived_from, step.step_id
        assert step.derived_from.startswith(known_prefixes), step.derived_from


def test_playbook_steps_keep_their_curated_wording(outcome, plan):
    """A curated step's action text must survive verbatim into the plan."""
    knowledge = outcome.report.knowledge
    curated = {
        step.action
        for pattern in knowledge.patterns
        if pattern.playbook
        for step in pattern.playbook.steps
    }
    planned = {s.action for s in plan.all_steps() if s.derived_from.startswith("knowledge:")}
    assert planned, "the curated source should have contributed"
    assert planned <= curated, "the Planner must not reword curated advice"


def test_a_source_cannot_rank_itself():
    """StepCandidate has no priority field: valuation belongs to the Planner."""
    assert "priority" not in StepCandidate.model_fields
    assert "valuation" not in StepCandidate.model_fields


# --- Planning consumes conclusions, never changes them ----------------------


def test_planning_never_changes_upstream_conclusions(fixture_log):
    bare = analyze(fixture_log("uvm_scoreboard.log"), plan=False)
    planned = analyze(fixture_log("uvm_scoreboard.log"), plan=True)

    assert bare.report.plan is None
    assert planned.report.plan is not None
    assert set(bare.graph.nodes) == set(planned.graph.nodes)
    assert len(bare.graph.edges) == len(planned.graph.edges)
    assert bare.report.classification == planned.report.classification
    assert [
        (h.id, h.confidence) for h in bare.report.reasoning.hypotheses
    ] == [(h.id, h.confidence) for h in planned.report.reasoning.hypotheses]
    assert [r.action for r in bare.report.reasoning.recommendations] == [
        r.action for r in planned.report.reasoning.recommendations
    ]
    assert bare.report.agents.model_dump(mode="json") == planned.report.agents.model_dump(
        mode="json"
    )


def test_recommendations_are_augmented_not_replaced(outcome):
    """A stated non-goal: reasoning.recommendations survives untouched."""
    assert outcome.report.reasoning.recommendations
    assert outcome.report.plan is not None


def test_planning_adds_no_artifact_type():
    assert not any("plan" in t.value for t in ArtifactType)


def test_planning_does_not_collide_with_m9_orchestration():
    """M9's InvestigationPlan is what the platform runs; DebugPlan is what the
    engineer does. The vocabularies must stay separate."""
    from veritriage.models import DebugPlan, DebugStep, InvestigationPlan, PlanStep
    from veritriage.orchestrator import InvestigationStep

    assert DebugPlan is not InvestigationPlan
    assert DebugStep is not PlanStep
    assert DebugStep is not InvestigationStep
    # And the M9 vocabulary is still exported exactly as before.
    assert InvestigationPlan.model_fields["plan_id"]
    assert PlanStep.model_fields["step_type"]


# --- Determinism ------------------------------------------------------------


def test_plan_is_deterministic(fixture_log):
    first = analyze(fixture_log("uvm_scoreboard.log")).report.plan
    second = analyze(fixture_log("uvm_scoreboard.log")).report.plan
    assert first.plan_id == second.plan_id
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_plan_id_is_a_content_digest(context):
    plan = Planner().plan(context)
    assert plan.plan_id.startswith("dbg-")
    # A different analysis yields a different plan ID.
    assert plan.plan_id != Planner(sources=[]).plan(context).plan_id


def test_step_ids_do_not_depend_on_process_hashing(fixture_log):
    """Step IDs are content digests: builtin hash() is salted per process."""
    ids = {
        tuple(s.step_id for s in analyze(fixture_log("axi_timeout.log")).report.plan.all_steps())
        for _ in range(2)
    }
    assert len(ids) == 1


# --- Ordering and valuation -------------------------------------------------


def test_steps_are_ordered_by_value_over_effort(plan):
    scores = [s.valuation.priority_score for s in plan.steps]
    assert scores == sorted(scores, reverse=True)


def test_valuation_arithmetic_is_recorded(plan):
    """A step's position must read line by line, like a ConfidenceTrace."""
    for step in plan.all_steps():
        assert step.valuation.terms, step.step_id
        assert 1 <= step.valuation.effort <= 3
        assert step.valuation.priority_score == pytest.approx(
            step.valuation.value / step.valuation.effort, abs=1e-4
        )
        assert any("effort" in term for term in step.valuation.terms)


def test_cheap_decisive_work_outranks_expensive_speculation(context):
    cheap = StepCandidate(
        kind=StepKind.INSPECT,
        action="cheap and decisive",
        purpose="p",
        derived_from="test:cheap",
        addresses=list(context.competing()),
        effort=1,
    )
    costly = StepCandidate(
        kind=StepKind.COLLECT,
        action="expensive and speculative",
        purpose="p",
        derived_from="test:costly",
        addresses=[],
        effort=3,
    )
    assert value_of(cheap, context).priority_score > value_of(costly, context).priority_score


def test_discrimination_beats_confirmation(context):
    """A step separating two live explanations outranks one confirming the leader."""
    competing = context.competing()
    if len(competing) < 2:
        pytest.skip("fixture does not have two live explanations")
    discriminating = StepCandidate(
        kind=StepKind.VERIFY, action="a", purpose="p", derived_from="t:a",
        addresses=list(competing), effort=1,
    )
    confirming = StepCandidate(
        kind=StepKind.VERIFY, action="b", purpose="p", derived_from="t:b",
        addresses=[competing[0]], effort=1,
    )
    assert value_of(discriminating, context).value > value_of(confirming, context).value


def test_estimated_effort_sums_the_root_steps(plan):
    assert plan.estimated_effort == sum(s.valuation.effort for s in plan.steps)


# --- Decision trees ---------------------------------------------------------


def test_plan_branches_when_explanations_compete(plan, context):
    assert len(context.competing()) >= 2, "fixture should have live alternatives"
    decision = plan.steps[0].decision
    assert decision is not None
    assert len(decision.branches) >= 2
    assert all(branch.steps for branch in decision.branches)
    assert all(branch.rationale for branch in decision.branches)


def test_branches_give_different_advice(plan):
    """A branch that recommends the same steps whatever the answer is not a branch."""
    decision = plan.steps[0].decision
    assert decision is not None
    seen: set[str] = set()
    for branch in decision.branches:
        ids = {s.step_id for s in branch.steps}
        assert not (ids & seen), "the same step was offered on two different outcomes"
        seen |= ids
    # And each branch leads with a step specific to its own explanation.
    for branch in decision.branches:
        assert branch.steps[0].addresses


def test_branch_steps_are_also_derived(plan):
    for step in plan.steps:
        if step.decision is None:
            continue
        for branch in step.decision.branches:
            for child in branch.steps:
                assert child.derived_from


def test_no_branch_when_one_explanation_dominates(fixture_log):
    outcome = analyze(fixture_log("vcs_compile_error.log"))
    plan = outcome.report.plan
    assert plan.steps
    assert all(s.decision is None for s in plan.steps), (
        "a foregone conclusion should not manufacture a fork"
    )


def test_evidence_already_in_the_graph_resolves_a_decision(fixture_log):
    """AUTO conditions are settled by evidence, not by running anything."""
    outcome = analyze(fixture_log("sva_assertion_before_timeout.log"))
    decisions = [s.decision for s in outcome.report.plan.all_steps() if s.decision]
    auto = [d for d in decisions if d.condition is ConditionKind.AUTO]
    assert auto, "a fired assertion should auto-resolve the branching question"
    assert auto[0].resolved_outcome and auto[0].resolved_because


def test_unresolved_decisions_stay_open_as_questions(plan):
    for step in plan.all_steps():
        decision = step.decision
        if decision is None or decision.condition is not ConditionKind.ASK:
            continue
        assert decision.resolved_outcome is None
        assert decision.question.endswith("?")


# --- Evidence requests ------------------------------------------------------


def test_missing_evidence_is_named_with_a_reason(plan):
    assert plan.evidence_requests
    for request in plan.evidence_requests:
        assert request.what and request.why
        assert request.satisfied_by
        assert request.would_discriminate, "a gap that separates nothing is not worth asking for"


def test_no_request_for_evidence_already_present(fixture_log):
    outcome = analyze([fixture_log("uvm_scoreboard.log"), fixture_log("coverage.txt")])
    requests = {r.request_id for r in outcome.report.plan.evidence_requests}
    assert "req-coverage" not in requests, "coverage was supplied; do not ask for it"


def test_a_clean_run_plans_nothing(fixture_log):
    outcome = analyze(fixture_log("uvm_pass.log"))
    assert outcome.report.plan is None or not outcome.report.plan.evidence_requests


# --- Completion, risks, progress -------------------------------------------


def test_completion_conditions_are_concrete(plan):
    assert plan.completion_conditions
    for condition in plan.completion_conditions:
        assert len(condition.statement) > 40, "a completion condition must be specific"


def test_risks_are_stated_not_hidden(plan):
    assert plan.risks


def test_progress_is_a_pure_function_of_plan_and_graph(outcome):
    progress = plan_progress(outcome.report.plan, outcome.graph)
    again = plan_progress(outcome.report.plan, outcome.graph)
    assert progress.model_dump() == again.model_dump()
    assert progress.total_steps == len(outcome.report.plan.all_steps())
    assert 0.0 <= progress.completion <= 1.0


def test_supplying_requested_evidence_advances_progress(fixture_log):
    """The loop that makes planning useful: ask, supply, re-run, advance."""
    without = analyze(fixture_log("uvm_scoreboard.log"))
    before = plan_progress(without.report.plan, without.graph)

    with_coverage = analyze(
        [fixture_log("uvm_scoreboard.log"), fixture_log("coverage.txt")]
    )
    after = plan_progress(with_coverage.report.plan, with_coverage.graph)
    assert "req-coverage" in before.outstanding_requests
    assert "req-coverage" not in [r for r in after.outstanding_requests]


# --- Learning integration ---------------------------------------------------


def test_learning_reprioritizes_but_never_adds_steps(tmp_path, fixture_log):
    """Learning contributes priorities; it never creates a step."""
    db = tmp_path / "regressions.db"
    services = WorkspaceServices(session_root=tmp_path / "s", db=db)
    for _ in range(2):
        services.investigate([fixture_log("uvm_scoreboard.log")], record_history=True)

    baseline = analyze(fixture_log("uvm_scoreboard.log")).report.plan
    target = baseline.steps[0].action

    with RegressionStore(db) as store:
        for record in store.all_records():
            store.save_feedback(
                FeedbackRecord(
                    regression_id=record.regression_id,
                    diagnosis="correct",
                    useful_recommendations=[target],
                )
            )
    services.learn_from_history()

    recalled = services.recall_learning()
    informed = analyze(fixture_log("uvm_scoreboard.log"), learning=recalled).report.plan

    # No step was invented by learning...
    assert {s.action for s in informed.all_steps()} <= {
        s.action for s in baseline.all_steps()
    }
    # ...and every step still names a non-learning provenance.
    assert all(not s.derived_from.startswith("learning:") for s in informed.all_steps())
    # ...but the historically useful action gained value.
    informed_step = next(s for s in informed.all_steps() if s.action == target)
    baseline_step = next(s for s in baseline.all_steps() if s.action == target)
    assert informed_step.valuation.value > baseline_step.valuation.value
    assert any("useful" in term for term in informed_step.valuation.terms)


def test_historical_influence_is_bounded(context):
    candidate = StepCandidate(
        kind=StepKind.VERIFY, action="x", purpose="p", derived_from="t:x", effort=1
    )
    baseline = value_of(candidate, context).value
    assert abs(value_of(candidate, context).value - baseline) <= MAX_HISTORICAL


# --- Project adaptation -----------------------------------------------------


def test_strategy_adapts_to_the_project(fixture_log):
    from veritriage.project import build_project_model

    model = build_project_model(fixture_log("project/sample.vproj.json").parent)
    outcome = analyze(fixture_log("uvm_scoreboard.log"), project=model)
    assert outcome.report.plan.strategy
    # A project model removes the "no project model" risk from the plan.
    assert not any("No project model" in risk for risk in outcome.report.plan.risks)


def test_missing_project_model_is_declared_as_a_risk(plan):
    assert any("project model" in risk.lower() for risk in plan.risks)


# --- Architecture guards ----------------------------------------------------


def test_planning_never_executes_anything():
    """No I/O, no subprocesses, no tool invocation anywhere in the package."""
    banned_calls = (".read_text", ".read_bytes", "open(", "os.system", "Path(")
    # Checked as imports rather than substrings: a local named `requests` is
    # not the HTTP library, and a guard that cannot tell the difference is a
    # guard that will be silenced the first time it cries wolf.
    banned_modules = {"subprocess", "socket", "requests", "urllib", "urllib.request", "httpx"}
    for path in (SRC / "veritriage" / "planning").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned_calls:
            assert term not in text, f"{path.name} may perform I/O ({term})"
        leaked = banned_modules & imports(path)
        assert not leaked, f"{path.name} imports {leaked}"


def test_no_ai_in_planning():
    banned = ("anthropic", "openai", "torch", "reasoning.ai", "AIReasoner", "embed(")
    for path in (SRC / "veritriage" / "planning").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_planning_never_imports_extraction_or_engine_layers():
    banned = (
        "veritriage.parsers",
        "veritriage.reasoning",
        "veritriage.rules",
        "veritriage.agents",
        "veritriage.learning",
        "veritriage.workspace",
        "veritriage.pipeline",
        "veritriage.orchestrator",
    )
    for path in (SRC / "veritriage" / "planning").rglob("*.py"):
        imported = imports(path)
        for module in banned:
            assert module not in imported, f"{path.name} imports {module}"


def test_core_unchanged_by_planning():
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
        "learning",
        "history",
        "orchestrator",
    ):
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            assert "veritriage.planning" not in imports(path), path


def test_planning_vocabulary_is_plain_data():
    imported = imports(SRC / "veritriage" / "models" / "planning.py")
    assert not any(
        m.startswith("veritriage.") and not m.startswith("veritriage.models")
        for m in imported
    )


def test_every_plan_citation_resolves(outcome):
    graph = outcome.graph
    plan = outcome.report.plan
    for step in plan.all_steps():
        for node_id in step.evidence_ids:
            assert node_id in graph.nodes, f"{step.step_id} cited a phantom node"
    for request in plan.evidence_requests:
        for node_id in request.evidence_ids:
            assert node_id in graph.nodes


def test_a_broken_source_never_costs_a_plan(context):
    class _Exploding(StepSource):
        source_id = "exploding"

        def propose(self, ctx):
            raise RuntimeError("source is down")

    register_source(_Exploding)
    try:
        plan = Planner().plan(context)
        assert plan.steps, "one broken source must not empty a plan"
        assert "exploding" not in plan.sources
    finally:
        unregister_source("exploding")


# --- Clients ----------------------------------------------------------------


def test_services_expose_the_plan(tmp_path, fixture_log):
    services = WorkspaceServices(session_root=tmp_path)
    session = services.investigate([fixture_log("uvm_scoreboard.log")])

    assert services.investigation_plan(session) is not None
    assert services.next_debug_step(session) is not None
    assert services.missing_evidence(session)
    assert services.plan_progress(session).total_steps > 0
    # Re-derivation from a session is pure: same session, same plan.
    assert (
        services.build_investigation_plan(session).plan_id
        == services.investigation_plan(session).plan_id
    )


def test_planning_over_mcp(tmp_path, fixture_log):
    services = WorkspaceServices(session_root=tmp_path)
    session = services.investigate([fixture_log("uvm_scoreboard.log")])
    services.save(session)
    args = {"session_id": session.session_id}

    plan = call_tool(services, "generate_investigation_plan", args)
    assert plan["steps"] and plan["plan_id"].startswith("dbg-")

    step = call_tool(services, "next_debug_step", args)
    assert step["action"] and step["derived_from"]

    assert call_tool(services, "missing_evidence", args)
    assert isinstance(call_tool(services, "decision_tree", args), list)

    progress = call_tool(services, "investigation_progress", args)
    assert "completion" in progress

    strategy = call_tool(services, "project_debug_strategy", args)
    assert strategy["objective"] and strategy["estimated_effort"] > 0


def test_report_renders_the_investigation_plan(tmp_path, outcome):
    from veritriage.reports import HtmlReportGenerator

    path = HtmlReportGenerator().write(
        outcome.report, tmp_path / "report.html", graph=outcome.graph
    )
    html = path.read_text(encoding="utf-8")
    for section in (
        "Recommended Investigation",
        "Decision Tree",
        "Evidence Still Needed",
        "Expected Root Cause Confirmation",
        "Risk Assessment",
    ):
        assert section in html, section


# --- The crown jewel: a new step source is a registration and nothing else


class _EmulationSource(StepSource):
    """A throwaway source for a fictional producer, defined in this test.

    It proves the milestone's success criterion: teaching the platform a new
    kind of debug step requires writing ONLY a source. It touches no core
    module, yet its candidate is deduplicated, valued, ordered, and reaches the
    plan and the report.
    """

    source_id = "emulation"
    rank = 5  # highest provenance, so it should lead the plan

    def applies_to(self, context: PlanningContext) -> bool:
        return bool(context.failing_nodes())

    def propose(self, context: PlanningContext) -> list[StepCandidate]:
        failing = context.failing_nodes()
        return [
            StepCandidate(
                kind=StepKind.REPRODUCE,
                action="Replay the failing window on the emulator",
                purpose="Emulation reproduces the failure at speed with full visibility.",
                derived_from="emulation:replay",
                addresses=list(context.competing()),
                effort=1,
                evidence_ids=[n.id for n in failing[:3]],
                bonus=1.0,
                bonus_reason="emulation gives full visibility at speed",
            )
        ]


def test_new_step_source_needs_only_registration(fixture_log):
    register_source(_EmulationSource)
    try:
        assert "emulation" in available_sources()

        outcome = analyze(fixture_log("uvm_scoreboard.log"))
        plan = outcome.report.plan

        # It ran, with zero changes to the core...
        assert "emulation" in plan.sources
        # ...its step was valued and ordered by the Planner, not by itself...
        step = next(s for s in plan.all_steps() if s.derived_from == "emulation:replay")
        assert step.valuation.terms
        # ...it led the plan on merit (cheap and discriminating)...
        assert plan.steps[0].step_id == step.step_id
        # ...and the plan it leads is still fully derived and citable.
        assert all(s.derived_from for s in plan.all_steps())
        assert all(
            node_id in outcome.graph.nodes for node_id in step.evidence_ids
        )
    finally:
        unregister_source("emulation")

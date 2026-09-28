"""Milestone 19, Phase 3: requirement in, organization-driven plan out.

The orchestrator must read a requirement honestly (declared vocabulary,
explicit assumptions, an honest miss when nothing matches), select the right
organizational domains for it, give every task an owner, independent reviewer,
approver, skills, evidence requirements, and escalation path, and do all of it
deterministically from organizational data.
"""

from __future__ import annotations

import pytest

from nirmaan.demos import DEMOS
from nirmaan.models import Level, TaskKind, TaskStatus, Track
from nirmaan.orchestrator import Orchestrator, UnrecognizedRequirement
from nirmaan.views import plan_tree

SPEC = "Design a configurable 4-port AXI-to-NoC bridge supporting 256-bit data, 40-bit address and QoS arbitration."


@pytest.fixture(scope="module")
def orchestrator(nirmaan_org):
    return Orchestrator(nirmaan_org)


def _divisions(org, engine) -> set[str]:
    return {org.division_of(t.unit).id for t in engine.state.tasks.values()
            if t.kind in (TaskKind.WORK, TaskKind.DECISION) and t.unit}


# --- Analysis ---------------------------------------------------------------------------


def test_analysis_extracts_intent_features_and_parameters(orchestrator):
    a = orchestrator.analyze(SPEC)
    assert a.intent == "new_ip"
    assert {"axi", "noc", "qos", "arbitration", "multi_port", "configurable"} <= set(a.features)
    assert a.parameters == {"ports": 4, "data_width": 256, "address_width": 40}
    assert a.feature_evidence["axi"] and a.intent_evidence


def test_silence_becomes_an_explicit_assumption(orchestrator):
    a = orchestrator.analyze(SPEC)
    clocking = next(x for x in a.assumptions if x.id == "clocking-unstated")
    assert "cdc" in clocking.assumed_features and clocking.question
    stated = orchestrator.analyze("Design a single-clock 4-port AXI-to-NoC bridge.")
    assert "clocking-unstated" not in {x.id for x in stated.assumptions}
    assert "cdc" not in stated.features


def test_an_unrecognized_requirement_is_an_honest_miss(orchestrator):
    assert orchestrator.analyze("Order pizza for the team.").unrecognized
    with pytest.raises(UnrecognizedRequirement, match="does not recognize"):
        orchestrator.plan("Order pizza for the team.")


@pytest.mark.parametrize("demo", DEMOS, ids=lambda d: d.key)
def test_every_demo_is_understood_and_planned(orchestrator, demo):
    engine = orchestrator.plan(demo.requirement)
    assert engine.state.project.analysis.intent == demo.expects_intent
    phases = {t.phase for t in engine.state.tasks.values() if t.kind is TaskKind.WORKSTREAM}
    assert set(demo.expects_phases) <= phases, phases


# --- Routing: the right organization, not a hard-coded one ---------------------------------


def test_the_bridge_engages_the_expected_domains(nirmaan_org, orchestrator):
    engine = orchestrator.plan(SPEC)
    assert {"product", "architecture", "design", "verification", "implementation", "documentation",
            "quality"} <= _divisions(nirmaan_org, engine)
    stages = {t.stage for t in engine.state.tasks.values()}
    for stage in ("requirements", "interface-spec", "noc-integration", "qos-architecture", "microarchitecture",
                  "rtl-implementation", "dv-plan", "dv-environment", "directed-tests", "random-tests",
                  "assertions", "coverage", "formal", "cdc-verification", "synthesis", "sta",
                  "documentation", "integration", "verification-signoff", "release"):
        assert stage in stages, stage


def test_rtl_fans_out_per_feature_to_the_right_specialists(orchestrator):
    engine = orchestrator.plan(SPEC)
    owners = {t.id.split(":")[1]: t.owner for t in engine.state.tasks.values() if t.stage == "rtl-implementation"}
    assert owners["rtl-implementation.axi"].startswith("design.rtl.interface.")
    assert owners["rtl-implementation.noc"].startswith("design.rtl.design.interconnect.")
    assert owners["rtl-implementation.arbitration"].startswith("design.rtl.design.interconnect.")
    assert owners["rtl-implementation.control"].startswith("design.rtl.design.control.")


def test_architecture_goes_to_architects_with_the_right_specialty(nirmaan_org, orchestrator):
    engine = orchestrator.plan(SPEC)
    micro = next(t for t in engine.state.tasks.values() if t.stage == "microarchitecture" and t.kind is TaskKind.WORK)
    assert micro.owner == "architecture.micro.noc.staff"
    assert nirmaan_org.division_of(nirmaan_org.roles[micro.reviewer].unit).id == "architecture"
    gate = next(t for t in engine.state.tasks.values() if t.gate == "gate.architecture")
    assert gate.owner == "exec.chief_architect" and gate.human_required


def test_every_task_is_owned_reviewed_and_escalatable(nirmaan_org, orchestrator):
    for demo in DEMOS:
        engine = orchestrator.plan(demo.requirement)
        for task in engine.state.tasks.values():
            assert task.owner, task.id
            assert task.status is not TaskStatus.BLOCKED, (task.id, task.blocked_reason)
            if task.kind in (TaskKind.WORK, TaskKind.DECISION):
                assert task.capability and nirmaan_org.holds(task.owner, task.capability), task.id
                assert task.escalation_path, task.id
                if task.review_state.value == "pending":
                    assert task.reviewer and task.reviewer != task.owner, task.id
                    assert task.approver and task.approver != task.owner, task.id


def test_managers_delegate_rather_than_execute(nirmaan_org, orchestrator):
    engine = orchestrator.plan(SPEC)
    for task in engine.state.tasks.values():
        role = nirmaan_org.roles[task.owner]
        if task.kind is TaskKind.WORK and nirmaan_org.capabilities[task.capability].kind.value != "management":
            assert role.track is Track.INDIVIDUAL, task.id
        if task.kind is TaskKind.WORKSTREAM:
            assert role.track is not Track.INDIVIDUAL, task.id


def test_critical_work_goes_to_senior_people(nirmaan_org, orchestrator):
    engine = orchestrator.plan(SPEC)
    for task in engine.state.tasks.values():
        if task.kind is TaskKind.WORK and task.criticality.value == "critical":
            assert nirmaan_org.roles[task.owner].level.at_least(Level.SENIOR), task.id


def test_routing_explains_itself(orchestrator):
    engine = orchestrator.plan(SPEC)
    for task in engine.state.tasks.values():
        if task.kind is TaskKind.WORK:
            assert task.owner_routing and task.owner_routing.rationale, task.id
            assert task.owner_routing.candidates[0].role == task.owner, task.id


def test_assumed_work_is_flagged_as_risk(orchestrator):
    engine = orchestrator.plan(SPEC)
    cdc = next(t for t in engine.state.tasks.values() if t.stage == "cdc-verification")
    assert "clocking-unstated" in cdc.risk


def test_downstream_work_waits_on_gates_not_just_tasks(orchestrator):
    engine = orchestrator.plan(SPEC)
    rtl = next(t for t in engine.state.tasks.values() if t.stage == "rtl-implementation")
    assert any(engine.state.tasks[d].kind is TaskKind.GATE for d in rtl.depends_on)


def test_branches_are_planned_as_alternatives(orchestrator):
    engine = orchestrator.plan("Investigate a regression failure introduced by a recent RTL commit.")
    branches = {t.stage: t.branch for t in engine.state.tasks.values() if t.branch}
    assert set(branches) == {"rtl-fix", "tb-fix", "infra-fix", "spec-clarification"}
    assert {b[1] for b in branches.values()} == {"rtl_bug", "testbench_bug", "infrastructure", "spec_ambiguity"}


def test_continuity_the_author_merges_their_change(orchestrator):
    engine = orchestrator.plan("Add QoS arbitration to an existing NoC router.")
    merge = next(t for t in engine.state.tasks.values() if t.stage == "merge" and t.kind is TaskKind.WORK)
    authors = {t.owner for t in engine.state.tasks.values() if t.stage == "rtl-change"}
    assert merge.owner in authors and merge.reviewer not in authors | {merge.owner}


# --- Determinism and rendering -----------------------------------------------------------


def test_planning_is_deterministic(nirmaan_org, fixed_clock):
    a = Orchestrator(nirmaan_org, clock=fixed_clock).plan(SPEC).state
    b = Orchestrator(nirmaan_org, clock=fixed_clock).plan(SPEC).state
    assert a.model_dump() == b.model_dump()


def test_the_plan_renders_as_an_organizational_tree(nirmaan_org, orchestrator):
    lines = plan_tree(nirmaan_org, orchestrator.plan(SPEC).state, detail=True)
    text = "\n".join(lines)
    assert lines[0].startswith("PROJECT: ")
    assert "PROGRAM MANAGER" in text
    for phase in ("Requirements", "Architecture", "RTL", "Verification", "Formal", "CDC/RDC", "Signoff"):
        assert f"── {phase}  (lead:" in text, phase
    for label in ("reviewer:", "evidence:", "escalation:", "why this owner:", "Open question:"):
        assert label in text, label

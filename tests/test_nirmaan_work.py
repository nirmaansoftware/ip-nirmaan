"""Milestone 19, Phase 2: tasks, dependencies, reviews, approvals, gates, audit.

The engine's promise: every change passes the lifecycle state machine, the
authority matrix, and the constitution, then lands as one hash-chained audit
entry; and planned, executed, verified, and approved stay distinct.
"""

from __future__ import annotations

import pytest

from nirmaan_helpers import agent, approve_gate, drive, human, tid, work

from nirmaan.models import (
    Assurance,
    Criticality,
    DecisionKind,
    EscalationKind,
    EscalationState,
    EvidenceKind,
    MemoryScope,
    ReviewState,
    TaskKind,
    TaskStatus,
    Verdict,
)
from nirmaan.orchestrator import Orchestrator
from nirmaan.work import (
    AuthorityError,
    PolicyViolationError,
    ProjectStore,
    TaskEngine,
    TransitionError,
    status_report,
    trace_graph,
    verify_chain,
    verify_completion,
    why_blocked,
)
from nirmaan.work.audit import verify_chain as chain_problems

BRIDGE = "Create a 4-port AXI-to-NoC bridge."
REGRESSION = "Investigate a regression failure introduced by a recent RTL commit."


@pytest.fixture()
def bridge(nirmaan_org, fixed_clock) -> TaskEngine:
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)


def _req(engine):
    return tid(engine, "requirements")


# --- Planning state -------------------------------------------------------------------


def test_a_plan_claims_nothing_was_done(bridge):
    statuses = {t.status for t in bridge.state.tasks.values()}
    assert statuses <= {TaskStatus.PLANNED, TaskStatus.READY}
    assert not bridge.state.artifacts and not bridge.state.evidence and not bridge.state.tool_runs
    assert bridge.state.audit[0].action == "project.create"
    assert verify_chain(bridge.state.audit) == []


def test_only_dependency_free_work_is_ready(bridge):
    ready = {t.stage for t in bridge.state.tasks.values()
             if t.status is TaskStatus.READY and t.kind is TaskKind.WORK}
    assert ready == {"requirements"}
    assert bridge.task(tid(bridge, "interface-spec.axi")).status is TaskStatus.PLANNED


def test_every_task_traces_to_the_requirement(bridge):
    req = bridge.state.project.requirement.id
    assert all(t.requirement == req for t in bridge.state.tasks.values())


# --- The review and approval lifecycle ------------------------------------------------


def test_execution_review_and_approval_are_separate(bridge):
    t = _req(bridge)
    task = bridge.task(t)
    bridge.start(t, agent(task.owner))
    bridge.submit(t, agent(task.owner), [{"kind": "requirements_spec", "title": "Bridge requirements"}])
    art = bridge.state.artifacts[bridge.task(t).artifacts[0]]
    assert art.assurance is Assurance.EXECUTED and bridge.task(t).status is TaskStatus.IN_REVIEW

    bridge.review(t, agent(task.reviewer), Verdict.APPROVE, "complete and testable")
    assert bridge.task(t).review_state is ReviewState.PASSED
    assert bridge.state.artifacts[art.id].assurance is Assurance.VERIFIED
    assert bridge.task(t).status is TaskStatus.IN_REVIEW  # reviewed is not approved

    bridge.approve(t, agent(task.approver))
    assert bridge.task(t).status is TaskStatus.COMPLETED
    assert bridge.state.artifacts[art.id].assurance is Assurance.APPROVED


def test_only_the_owner_starts_and_submits(bridge):
    t = _req(bridge)
    with pytest.raises(AuthorityError):
        bridge.start(t, agent("product.management.roadmap.senior"))


def test_nobody_reviews_their_own_work(bridge):
    t = _req(bridge)
    owner = agent(bridge.task(t).owner)
    bridge.start(t, owner)
    bridge.submit(t, owner, [{"kind": "requirements_spec", "title": "x"}])
    with pytest.raises((PolicyViolationError, AuthorityError)):
        bridge.review(t, owner, Verdict.APPROVE)


def test_approval_needs_authority_and_says_who_has_it(bridge):
    t = _req(bridge)
    task = bridge.task(t)
    bridge.start(t, agent(task.owner))
    bridge.submit(t, agent(task.owner), [{"kind": "requirements_spec", "title": "x"}])
    bridge.review(t, agent(task.reviewer), Verdict.APPROVE)
    with pytest.raises(AuthorityError, match="escalate to"):
        bridge.approve(t, agent("product.management.requirements.junior"))


def test_approval_needs_a_passing_review(bridge):
    t = _req(bridge)
    task = bridge.task(t)
    bridge.start(t, agent(task.owner))
    bridge.submit(t, agent(task.owner), [{"kind": "requirements_spec", "title": "x"}])
    with pytest.raises(TransitionError, match="no passing independent review"):
        bridge.approve(t, agent(task.approver))


def test_changes_requested_sends_work_back(bridge):
    t = _req(bridge)
    task = bridge.task(t)
    bridge.start(t, agent(task.owner))
    bridge.submit(t, agent(task.owner), [{"kind": "requirements_spec", "title": "v1"}])
    bridge.review(t, agent(task.reviewer), Verdict.REQUEST_CHANGES, "latency unspecified")
    assert bridge.task(t).status is TaskStatus.CHANGES_REQUESTED
    bridge.start(t, agent(task.owner))
    bridge.submit(t, agent(task.owner), [{"kind": "requirements_spec", "title": "v2"}])
    bridge.review(t, agent(task.reviewer), Verdict.APPROVE)
    bridge.approve(t, agent(task.approver))
    assert bridge.task(t).status is TaskStatus.COMPLETED
    assert len(bridge.task(t).artifacts) == 1  # v1 was superseded by the change request (M27)
    (v1,) = [a for a in bridge.state.attempts.values() if a.task == t]  # provenance keeps it on the record
    assert [a.title for a in v1.artifacts] == ["v1"] and v1.reviews


def test_conflicting_reviews_must_be_escalated(bridge):
    t = _req(bridge)
    task = bridge.task(t)
    bridge.start(t, agent(task.owner))
    bridge.submit(t, agent(task.owner), [{"kind": "requirements_spec", "title": "x"}])
    bridge.review(t, agent(task.reviewer), Verdict.APPROVE)
    bridge.review(t, agent("product.management.requirements.senior"), Verdict.REQUEST_CHANGES, "disagree")
    assert bridge.task(t).review_state is ReviewState.CONFLICTED
    with pytest.raises(PolicyViolationError, match="P7"):
        bridge.approve(t, agent(task.approver))
    esc = bridge.escalate(t, agent(task.owner), EscalationKind.CONFLICT, "reviewers disagree",
                          blocking_question="Is the latency requirement in scope?")
    assert bridge.task(t).status is TaskStatus.ESCALATED
    bridge.resolve_escalation(esc.id, agent(esc.target_role), "in scope; approve with the revision")
    assert bridge.task(t).status is TaskStatus.IN_REVIEW
    bridge.approve(t, agent(task.approver))
    assert bridge.task(t).status is TaskStatus.COMPLETED


# --- Gates and humans ----------------------------------------------------------------


def test_gates_hold_downstream_work(bridge):
    drive(bridge, until=tid(bridge, "requirements.gate"))
    assert bridge.task(tid(bridge, "interface-spec.axi")).status is TaskStatus.PLANNED
    approve_gate(bridge, tid(bridge, "requirements.gate"))
    assert bridge.task(tid(bridge, "interface-spec.axi")).status is TaskStatus.READY


def test_human_gates_refuse_agents(bridge):
    gate = tid(bridge, "microarchitecture.gate")
    drive(bridge, until=gate)
    task = bridge.task(gate)
    assert task.human_required
    with pytest.raises(PolicyViolationError, match="P12"):
        bridge.approve_gate(gate, agent(task.owner))
    bridge.approve_gate(gate, human(task.owner))
    assert bridge.task(gate).status is TaskStatus.COMPLETED


def test_human_gates_are_configurable_per_project(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE, gate_overrides={"gate.architecture": False})
    gate = tid(engine, "microarchitecture.gate")
    drive(engine, until=gate)
    engine.approve_gate(gate, agent(engine.task(gate).owner))
    assert engine.task(gate).status is TaskStatus.COMPLETED


def test_gate_approvers_need_the_signoff_capability(bridge):
    gate = tid(bridge, "requirements.gate")
    drive(bridge, until=gate)
    with pytest.raises(AuthorityError):
        bridge.approve_gate(gate, human("product.management.requirements.senior"))


# --- Evidence -----------------------------------------------------------------------


def test_signoff_needs_evidence_and_claims_never_count(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)
    lint = tid(engine, "rtl-lint")
    drive(engine, until=lint)
    owner = agent(engine.task(lint).owner)
    engine.start(lint, owner)
    engine.submit(lint, owner, [{"kind": "lint_report", "title": "lint"}])
    assert engine.task(lint).status is TaskStatus.IN_PROGRESS  # submitted, not complete
    engine.record_evidence(lint, owner, EvidenceKind.CLAIM, "lint is clean, trust me")
    with pytest.raises(PolicyViolationError, match="P9"):
        engine.complete(lint, owner)
    # An AI agent cannot attest; only a named human can.
    engine.record_evidence(lint, owner, EvidenceKind.HUMAN_ATTESTATION, "ran lint")
    assert engine.task(lint).status is TaskStatus.IN_PROGRESS
    engine.record_evidence(lint, human(engine.task(lint).owner), EvidenceKind.HUMAN_ATTESTATION,
                           "lint run in the EDA farm, 0 errors, 3 waivers approved")
    assert engine.task(lint).status is TaskStatus.COMPLETED


def test_tool_evidence_must_cite_a_real_run(bridge):
    t = _req(bridge)
    with pytest.raises(PolicyViolationError, match="P5"):
        bridge.record_evidence(t, agent(bridge.task(t).owner), EvidenceKind.TOOL_RUN, "simulated it", tool_run="run-9999")
    with pytest.raises(PolicyViolationError, match="P5"):
        bridge.record_evidence(t, agent(bridge.task(t).owner), EvidenceKind.TOOL_RUN, "simulated it")


def test_submissions_must_produce_something(bridge):
    t = _req(bridge)
    owner = agent(bridge.task(t).owner)
    bridge.start(t, owner)
    with pytest.raises(PolicyViolationError, match="P4"):
        bridge.submit(t, owner, [])


def test_artifacts_carry_provenance(bridge):
    t = _req(bridge)
    owner = agent(bridge.task(t).owner)
    bridge.start(t, owner)
    with pytest.raises(PolicyViolationError, match="P8"):
        bridge.submit(t, owner, [{"kind": "requirements_spec", "title": "x", "derived_from": ["ghost#a1"]}])


# --- Failure, retry, escalation ---------------------------------------------------------


def test_failure_retries_then_escalates(bridge):
    t = _req(bridge)
    owner = agent(bridge.task(t).owner)
    bridge.start(t, owner)
    bridge.fail(t, owner, "customer inputs missing")
    assert bridge.task(t).status is TaskStatus.READY and bridge.task(t).attempts == 1
    bridge.start(t, owner)
    bridge.fail(t, owner, "still missing")
    task = bridge.task(t)
    assert task.status is TaskStatus.ESCALATED and task.escalation_state is EscalationState.OPEN
    esc = next(e for e in bridge.state.escalations.values() if e.task == t)
    assert esc.kind is EscalationKind.TECHNICAL
    assert bridge.state.tasks[t].escalation_path[0] in (esc.target_role, *bridge.state.tasks[t].escalation_path)
    bridge.resolve_escalation(esc.id, agent(esc.target_role), "inputs obtained from the customer")
    assert bridge.task(t).status is TaskStatus.READY and bridge.task(t).attempts == 0


def test_escalations_carry_structure_and_can_rise(bridge):
    t = _req(bridge)
    owner = agent(bridge.task(t).owner)
    esc = bridge.escalate(t, owner, EscalationKind.UNCERTAINTY, "Is QoS in scope?",
                          context="request is silent", attempted_actions=("read the request",),
                          blocking_question="Include QoS?", recommended_options=("yes", "no"))
    assert esc.recommended_options == ("yes", "no") and esc.blocking_question
    risen = bridge.reescalate(esc.id, agent(esc.target_role), "needs product input")
    assert risen.supersedes == esc.id
    assert bridge.org.roles[risen.target_role].level.rank > bridge.org.roles[esc.target_role].level.rank
    with pytest.raises(AuthorityError):
        bridge.resolve_escalation(risen.id, agent("product.management.roadmap.junior"), "no")


def test_block_and_unblock(bridge):
    t = _req(bridge)
    owner = agent(bridge.task(t).owner)
    bridge.block(t, owner, "waiting on customer NDA")
    assert "NDA" in " ".join(why_blocked(bridge.state, t).reasons)
    bridge.unblock(t, owner)
    assert bridge.task(t).status is TaskStatus.READY


# --- Branching ---------------------------------------------------------------------------


def test_a_decision_takes_one_branch_and_cancels_the_rest(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(REGRESSION)
    drive(engine, until=tid(engine, "root-cause"), workspace=tmp_path)
    work(engine, tid(engine, "root-cause"), outcome="testbench_bug")
    status = {t.stage: t.status for t in engine.state.tasks.values() if t.branch}
    assert status["tb-fix"] is TaskStatus.READY
    assert {status[s] for s in ("rtl-fix", "infra-fix", "spec-clarification")} == {TaskStatus.CANCELLED}
    work(engine, tid(engine, "tb-fix"))
    assert engine.task(tid(engine, "verify-fix")).status is TaskStatus.READY


def test_decisions_must_choose_a_declared_outcome(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(REGRESSION)
    rc = tid(engine, "root-cause")
    drive(engine, until=rc, workspace=tmp_path)
    owner = agent(engine.task(rc).owner)
    engine.start(rc, owner)
    with pytest.raises(Exception, match="outcome"):
        engine.submit(rc, owner, [{"kind": "root_cause_analysis", "title": "x"}], outcome="gremlins")


# --- Authority over the plan itself ---------------------------------------------------------


def test_cancelling_needs_authority(bridge):
    t = tid(bridge, "driver")
    with pytest.raises(AuthorityError):
        bridge.cancel(t, agent("software.firmware.drivers.junior"), "not needed")
    bridge.cancel(t, agent("software.firmware.manager"), "customer supplies their own driver")
    assert bridge.task(t).status is TaskStatus.CANCELLED


def test_reassignment_respects_capability(bridge):
    t = tid(bridge, "rtl-implementation.control")
    with pytest.raises(AuthorityError):
        bridge.reassign(t, agent("design.rtl.design.manager"), "verification.debug.triage.senior", "load")
    bridge.reassign(t, agent("design.rtl.design.manager"), "design.rtl.design.fsm.senior", "load balance")
    assert bridge.task(t).owner == "design.rtl.design.fsm.senior"


def test_decisions_need_authority_and_evidence(bridge):
    with pytest.raises(AuthorityError):
        bridge.record_decision(agent("design.rtl.design.fsm.junior"), DecisionKind.ARCHITECTURE_DECISION,
                               Criticality.HIGH, "Use a crossbar", "fewer hops")
    with pytest.raises(PolicyViolationError, match="P2"):
        bridge.record_decision(agent("architecture.micro.director"), DecisionKind.ARCHITECTURE_DECISION,
                               Criticality.HIGH, "Use a crossbar", "fewer hops")
    drive(bridge, until=tid(bridge, "requirements.gate"))
    evidence = bridge.task(_req(bridge)).evidence
    decision = bridge.record_decision(agent("architecture.micro.director"), DecisionKind.ARCHITECTURE_DECISION,
                                      Criticality.HIGH, "Use a crossbar", "fewer hops", evidence=evidence)
    assert decision.evidence == evidence


# --- Audit, hidden state, memory, persistence ------------------------------------------------


def test_the_audit_trail_is_tamper_evident(bridge):
    drive(bridge, until=tid(bridge, "requirements.gate"))
    trail = list(bridge.state.audit)
    assert chain_problems(trail) == []
    edited = [*trail]
    edited[3] = edited[3].model_copy(update={"reason": "nothing to see"})
    assert any("edited" in p for p in chain_problems(edited))
    assert any("removed" in p or "order" in p for p in chain_problems(trail[:2] + trail[3:]))


def test_hidden_state_changes_are_refused(bridge):
    t = _req(bridge)
    sneaky = dict(bridge.state.tasks)
    sneaky[t] = sneaky[t].model_copy(update={"status": TaskStatus.COMPLETED})
    bridge._state = bridge.state.model_copy(update={"tasks": sneaky})  # bypassing the engine
    with pytest.raises(PolicyViolationError, match="P10"):
        bridge.block(tid(bridge, "driver"), agent("software.firmware.manager"), "x")


def test_every_mutation_is_audited(bridge):
    before = len(bridge.state.audit)
    t = _req(bridge)
    bridge.start(t, agent(bridge.task(t).owner))
    new = bridge.state.audit[before:]
    mine = [e for e in new if e.actor.endswith(bridge.task(t).owner)]
    assert [e.action for e in mine] == ["task.start"] and mine[0].subject == t
    # Everything else is a derived roll-up, still audited, attributed to the engine.
    assert all(e.action == "task.status" and e.actor.startswith("nirmaan-engine") for e in new if e not in mine)


def test_memory_is_scoped_and_has_provenance(bridge):
    t = _req(bridge)
    bridge.remember(MemoryScope.PROJECT, bridge.state.project.id, "clocking", "single clock confirmed",
                    human("product.management.customer.senior"), source_task=t)
    entry = bridge.state.memory[-1]
    assert entry.scope is MemoryScope.PROJECT and entry.source_task == t and entry.recorded_by


def test_projects_round_trip_and_tampering_is_detected(bridge, tmp_path):
    store = ProjectStore(tmp_path)
    path = store.save(bridge.state)
    assert store.load(bridge.state.project.id).model_dump() == bridge.state.model_dump()
    text = path.read_text().replace('"project.create"', '"project.rewritten"', 1)
    path.write_text(text)
    with pytest.raises(ValueError, match="audit"):
        store.load(bridge.state.project.id)


# --- Managers: status, blockers, completion -----------------------------------------------


def test_why_blocked_walks_the_dependency_chain(bridge):
    blocker = why_blocked(bridge.state, tid(bridge, "microarchitecture"))
    text = "\n".join(blocker.lines())
    assert "IP architecture" in text and "Requirements specification" in text
    assert blocker.is_blocked


def test_status_report_shows_what_managers_need(bridge):
    report = status_report(bridge.org, bridge.state)
    assert report.tasks > 40 and report.progress == 0.0
    assert {g["gate"] for g in report.gates} >= {"gate.architecture", "gate.verification", "gate.release"}
    assert any(a["id"] == "clocking-unstated" for a in report.assumptions)
    assert any("assumption" in r["risk"] for r in report.risks)


def test_a_whole_project_completes_only_under_the_rules(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)
    drive(engine, workspace=tmp_path)
    program = next(t for t in engine.state.tasks.values() if t.kind is TaskKind.PROGRAM)
    assert program.status is TaskStatus.COMPLETED
    assert verify_completion(engine.state, program.id) == []
    for art in engine.state.artifacts.values():
        reviewed = engine.task(art.task).review_state is not ReviewState.NOT_REQUIRED
        # Reviewed work ends approved; unreviewed work can at most be verified.
        assert art.assurance is (Assurance.APPROVED if reviewed else Assurance.VERIFIED), art.id
    assert verify_chain(engine.state.audit) == []
    graph = trace_graph(engine.state)
    kinds = {n["kind"] for n in graph["nodes"]}
    assert {"requirement", "artifact", "evidence", "role"} <= kinds

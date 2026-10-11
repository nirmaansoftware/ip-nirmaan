"""Milestone 50: constitution hardening, from audit A (docs/CONSTITUTION_HARDENING.md).

Each test is one of the audit's probes, and each failed on v1.24.0:

* C2: evidence is about this task and this submission. A run of another task, a superseded submission's
  evidence, the owner's own document, and a review that is not an approval of this submission back nothing.
* M1: a tool run is recorded only through the broker, never twice under one ID.
* H1: the authority matrix's ``human_required`` holds for approving, signing a gate, and cancelling, not only
  for recording a decision; over MCP one session is one role.
* L2: only someone with a stake in a task (or above it) can escalate, and so freeze, it.
* M2: a work or decision task never completes with nothing produced, or a decision with no outcome.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from nirmaan.company import builder
from nirmaan.mcp import McpContext, call_tool
from nirmaan.company.workflows import REVIEWED, documented, ran, rv, st
from nirmaan.models import (
    Actor,
    ActorKind,
    Assurance,
    EscalationKind,
    EvidenceKind,
    IntentRule,
    Level,
    TaskStatus,
    ToolRun,
    Verdict,
    WorkflowTemplate,
)
from nirmaan.org import register_extension
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ToolBroker, run_task
from nirmaan.runtime.model import MockLLM, ModelRuntime
from nirmaan.work import ProjectStore, TaskEngine
from nirmaan.work.engine import AuthorityError, WorkError
from nirmaan.work.policy import PolicyViolationError

from laws import imports, needs
from nirmaan_helpers import drive, human, tid

FIX = Path(__file__).parent / "fixtures" / "rtl"
SRC = Path(__file__).resolve().parent.parent / "src"


def ai(role: str) -> Actor:
    return Actor(role=role, kind=ActorKind.AI_AGENT, name="probe")


@pytest.fixture()
def probe(registries) -> TaskEngine:
    """The audit's throwaway workflow, added as data in this test's registry scope."""

    @register_extension("m50-probe")
    def _ext(b):
        b.add(IntentRule(intent="m50_probe", patterns=(r"\bm50 probe\b",), priority=1),
              WorkflowTemplate(id="m50-probe", name="M50 probe", description="probe", intents=("m50_probe",),
                  stages=(
                      st("doc", "Self documented", "Debug", "rtl.impact", outputs=("impact_analysis",),
                         evidence=(documented("Commit range"),)),
                      st("empty", "No evidence, no review", "Debug", "rtl.impact", outputs=("impact_analysis",)),
                      st("pick", "A decision with no review", "Debug", "rtl.impact", outputs=("impact_analysis",),
                         outcomes=("left", "right")),
                      st("linta", "Lint A", "RTL", "rtl.lint", outputs=("lint_report",),
                         evidence=(ran("Lint run", "lint.run"),)),
                      st("lintb", "Lint B", "RTL", "rtl.lint", outputs=("lint_report",),
                         evidence=(ran("Lint run", "lint.run"),)),
                      st("lintc", "Lint C, after A", "RTL", "rtl.lint", depends_on=("linta",),
                         outputs=("lint_report",), evidence=(ran("Lint run", "lint.run"),)),
                      st("fab", "Fabricated", "RTL", "rtl.lint", outputs=("lint_report",),
                         evidence=(ran("Lint run", "lint.run"),)),
                      st("rev", "Reviewed lint", "RTL", "rtl.lint", review=rv("rtl.review"),
                         outputs=("lint_report",), evidence=(REVIEWED, ran("Lint run", "lint.run"))),
                      st("rev2", "Another reviewed lint", "RTL", "rtl.lint", review=rv("rtl.review"),
                         outputs=("lint_report",), evidence=(REVIEWED,)),
                  )))

    clock = lambda: datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)  # noqa: E731
    return Orchestrator(builder().build(), clock=clock).plan("Run the m50 probe.")


def _lint(engine: TaskEngine, task_id: str):
    run, _ = ToolBroker(engine).invoke(ai(engine.task(task_id).owner), "lint.run",
                                       {"sources": str(FIX / "counter.v")}, task_id)
    assert run.succeeded, run.summary
    return run


# --- C2: evidence is about this task and this submission --------------------------------------


@needs("verilator")  # the probe's lint run is real
def test_a_run_of_another_task_cannot_back_this_one(probe):
    run = _lint(probe, tid(probe, "linta"))
    b = tid(probe, "lintb")
    owner = ai(probe.task(b).owner)
    probe.start(b, owner)
    probe.submit(b, owner, [{"kind": "lint_report", "title": "lint of an unlinted file", "location": "/x/bad.v"}])
    with pytest.raises(PolicyViolationError, match=r"\[P5\].*made for .*linta"):
        probe.record_evidence(b, owner, EvidenceKind.TOOL_RUN, "borrowed", tool_run=run.id)
    assert probe.task(b).status is TaskStatus.IN_PROGRESS


@needs("verilator")  # the probe's lint run is real
def test_the_model_runtime_drops_runs_of_other_tasks(probe):
    """The mock model names every run its prompt shows, upstream ones included; only this task's count."""
    a, c = tid(probe, "linta"), tid(probe, "lintc")
    owner = ai(probe.task(a).owner)
    probe.start(a, owner)
    run = _lint(probe, a)
    probe.record_evidence(a, owner, EvidenceKind.TOOL_RUN, run.summary, tool_run=run.id)
    probe.submit(a, owner, [{"kind": "lint_report", "title": "lint", "location": str(FIX / "counter.v")}])
    assert probe.task(a).status is TaskStatus.COMPLETED

    report = run_task(probe, c, ModelRuntime(MockLLM()))
    cited = {probe.state.evidence[e].tool_run for e in probe.task(c).evidence}
    assert run.id not in cited
    assert all(probe.state.tool_runs[r].task == c for r in cited if r)
    assert "not made for this task" in report.detail
    assert probe.task(c).status is not TaskStatus.COMPLETED  # its own lint had no sources, so it failed


@needs("verilator")  # the probe's lint run is real
def test_a_sent_back_submissions_evidence_does_not_verify_the_next(probe):
    t = tid(probe, "rev")
    owner, reviewer = ai(probe.task(t).owner), ai(probe.task(t).reviewer)
    probe.start(t, owner)
    run = _lint(probe, t)
    first = probe.record_evidence(t, owner, EvidenceKind.TOOL_RUN, "lint of v1", tool_run=run.id)
    probe.submit(t, owner, [{"kind": "lint_report", "title": "v1", "location": str(FIX / "counter.v")}])
    probe.review(t, reviewer, Verdict.REQUEST_CHANGES, "redo it")
    [attempt] = [a for a in probe.state.attempts.values() if a.task == t]
    assert first.id in attempt.evidence and run.id in attempt.tool_runs
    assert probe.task(t).evidence == ()

    probe.start(t, owner)
    probe.submit(t, owner, [{"kind": "lint_report", "title": "v2, never linted", "location": "/x/v2.v"}])
    probe.review(t, reviewer, Verdict.APPROVE, "ok")
    [v2] = probe.task(t).artifacts
    assert probe.state.artifacts[v2].assurance is Assurance.EXECUTED
    with pytest.raises(PolicyViolationError, match=r"\[P9\].*Lint run"):
        probe.approve(t, human(probe.task(t).approver))
    ids = [e for e in probe.state.evidence if probe.state.evidence[e].task == t]
    assert len(ids) == len(set(ids)) == 2  # numbering continues past the moved evidence


def test_an_owner_cannot_substantiate_its_own_work_with_its_own_document(probe):
    t = tid(probe, "doc")
    owner = ai(probe.task(t).owner)
    probe.start(t, owner)
    probe.submit(t, owner, [{"kind": "impact_analysis", "title": "anything"}])
    own = probe.task(t).artifacts[0]
    ev = probe.record_evidence(t, owner, EvidenceKind.DOCUMENT, "see my own note", reference=own)
    assert not ev.substantiated
    assert probe.task(t).status is TaskStatus.IN_PROGRESS
    assert probe.state.artifacts[own].assurance is Assurance.EXECUTED


def test_a_document_counts_only_when_another_task_produced_it_and_it_was_approved(probe):
    other = tid(probe, "rev2")
    owner = ai(probe.task(other).owner)
    probe.start(other, owner)
    probe.submit(other, owner, [{"kind": "lint_report", "title": "someone else's report"}])
    unapproved = probe.task(other).artifacts[0]
    t = tid(probe, "doc")
    doc_owner = ai(probe.task(t).owner)
    probe.start(t, doc_owner)
    assert not probe.record_evidence(t, doc_owner, EvidenceKind.DOCUMENT, "x", reference=unapproved).substantiated
    probe.review(other, ai(probe.task(other).reviewer), Verdict.APPROVE, "fine")
    probe.approve(other, human(probe.task(other).approver))
    assert probe.state.artifacts[unapproved].assurance is Assurance.APPROVED
    assert probe.record_evidence(t, doc_owner, EvidenceKind.DOCUMENT, "x", reference=unapproved).substantiated


def test_only_an_approval_of_this_submission_is_a_review_record(probe):
    t, other = tid(probe, "rev"), tid(probe, "rev2")
    for task_id in (t, other):
        owner = ai(probe.task(task_id).owner)
        probe.start(task_id, owner)
        probe.submit(task_id, owner, [{"kind": "lint_report", "title": "report"}])
    owner, reviewer = ai(probe.task(t).owner), ai(probe.task(t).reviewer)
    probe.review(other, ai(probe.task(other).reviewer), Verdict.APPROVE, "fine")
    elsewhere = next(r.id for r in probe.state.reviews.values() if r.task == other)
    probe.review(t, reviewer, Verdict.REQUEST_CHANGES, "redo it")
    sent_back = next(r.id for r in probe.state.reviews.values() if r.task == t)
    probe.start(t, owner)
    for reference in (sent_back, elsewhere, "no-such-review"):
        ev = probe.record_evidence(t, owner, EvidenceKind.REVIEW_RECORD, "cites a review", reference=reference)
        assert not ev.substantiated, reference
    probe.submit(t, owner, [{"kind": "lint_report", "title": "v2"}])
    probe.review(t, reviewer, Verdict.APPROVE, "now fine")
    current = [r.id for r in probe.state.reviews.values() if r.task == t][-1]
    assert probe.record_evidence(t, owner, EvidenceKind.REVIEW_RECORD, "cites it", reference=current).substantiated


# --- M1: a tool run is recorded only through the broker ----------------------------------------


def test_a_run_nobody_executed_cannot_be_recorded(probe):
    t = tid(probe, "fab")
    owner = ai(probe.task(t).owner)
    probe.start(t, owner)
    fake = ToolRun(id="run-9999", tool="lint.run", actor=owner.label, task=t, succeeded=True, summary="never ran")
    with pytest.raises(WorkError, match="broker"):
        probe.record_tool_run(fake, owner)
    assert "run-9999" not in probe.state.tool_runs


@needs("verilator")  # the probe's lint run is real
def test_a_recorded_run_cannot_be_replaced(probe):
    from nirmaan.work.engine import BROKER_SEAL

    t = tid(probe, "fab")
    owner = ai(probe.task(t).owner)
    run = _lint(probe, t)
    forged = run.model_copy(update={"summary": "something else"})
    with pytest.raises(WorkError, match="already recorded"):
        probe.record_tool_run(forged, owner, seal=BROKER_SEAL)
    assert probe.state.tool_runs[run.id].summary == run.summary


def test_only_the_broker_holds_the_seal():
    """The law behind M1: one module in the source tree imports the seal the engine records runs with."""
    holders = sorted(str(p.relative_to(SRC)) for p in SRC.rglob("*.py")
                     if "nirmaan.work.engine.BROKER_SEAL" in imports(p))
    assert holders == ["nirmaan/runtime/tools.py"]


# --- H1: approving is a person's where the authority matrix says so ---------------------------


def test_an_agent_cannot_approve_critical_work(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Add a QoS feature to the NoC router.")
    t = tid(engine, "microarchitecture")
    drive(engine, until=t)
    task = engine.task(t)
    assert task.criticality.value == "critical"
    assert nirmaan_org.authority[("approve_artifact", "critical")].human_required
    engine.start(t, ai(task.owner))
    engine.submit(t, ai(task.owner), [{"kind": k, "title": k} for k in task.expected_outputs])
    engine.review(t, ai(task.reviewer), Verdict.APPROVE, "ok")
    with pytest.raises(PolicyViolationError, match=r"\[P12\].*needs a person"):
        engine.approve(t, ai(task.approver))
    assert engine.task(t).status is TaskStatus.IN_REVIEW
    assert engine.approve(t, human(task.approver)).status is TaskStatus.COMPLETED


def test_an_agent_cannot_sign_a_gate_even_one_marked_for_agents(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-port AXI-to-NoC bridge.")
    gate = tid(engine, "requirements.gate")
    drive(engine, until=gate)
    assert not engine.task(gate).human_required  # the gate itself would let an agent sign
    with pytest.raises(PolicyViolationError, match=r"\[P12\]"):
        engine.approve_gate(gate, ai(engine.task(gate).owner))
    assert engine.approve_gate(gate, human(engine.task(gate).owner)).status is TaskStatus.COMPLETED


def test_an_agent_cannot_cancel_critical_work(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Add a QoS feature to the NoC router.")
    t = tid(engine, "microarchitecture")
    canceller = next(r.id for r in engine.org.line_chain(engine.task(t).owner) if r.level.at_least(Level.VP))
    with pytest.raises(PolicyViolationError, match=r"\[P12\]"):
        engine.cancel(t, ai(canceller), "not needed")
    assert engine.cancel(t, human(canceller), "not needed").status is TaskStatus.CANCELLED


# --- L2: escalating a task needs a stake in it ---------------------------------------------------


def test_an_unrelated_role_cannot_escalate_a_task(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-port AXI-to-NoC bridge.")
    t = tid(engine, "requirements")
    task = engine.task(t)
    stake = {task.owner, task.reviewer, task.approver, *task.escalation_path,
             *(r.id for r in engine.org.line_chain(task.owner))}
    stranger = next(r for r in engine.org.roles if r not in stake)
    with pytest.raises(AuthorityError, match="no stake"):
        engine.escalate(t, ai(stranger), EscalationKind.TECHNICAL, "freeze it")
    assert engine.task(t).status is TaskStatus.READY
    assert engine.escalate(t, ai(task.reviewer), EscalationKind.TECHNICAL, "unclear").task == t


# --- M2: completing needs something produced -----------------------------------------------------


def test_work_with_nothing_produced_cannot_complete(probe):
    t = tid(probe, "empty")
    owner = ai(probe.task(t).owner)
    probe.start(t, owner)
    with pytest.raises(PolicyViolationError, match=r"\[P4\].*nothing was produced"):
        probe.complete(t, owner)
    assert probe.task(t).status is TaskStatus.IN_PROGRESS


def test_a_decision_cannot_complete_without_an_outcome(probe):
    t = tid(probe, "pick")
    owner = ai(probe.task(t).owner)
    probe.start(t, owner)
    with pytest.raises(PolicyViolationError, match=r"\[P4\].*no outcome"):
        probe.complete(t, owner)
    probe.submit(t, owner, [{"kind": "impact_analysis", "title": "choice"}], outcome="left")
    assert probe.task(t).status is TaskStatus.COMPLETED


# --- H1 over MCP: one session is one role ------------------------------------------------------


def test_an_mcp_session_acts_as_one_role(nirmaan_org, tmp_path):
    store = ProjectStore(tmp_path / "nirmaan")
    session = McpContext(nirmaan_org, store)  # no role configured: the first one it acts as is bound
    plan = call_tool(session, "plan_project", {"requirement": "Create a 4-port AXI-to-NoC bridge."})
    project = plan["project"]
    req = next(t for t in plan["tasks"] if t["id"] == f"{project}:requirements")
    call_tool(session, "start_task", {"project": project, "task": "requirements", "role": req["owner"]})
    call_tool(session, "submit_task", {"project": project, "task": "requirements", "role": req["owner"],
                                       "artifacts": [{"kind": "requirements_spec", "title": "spec"}]})
    assert session.role == req["owner"]
    for tool, extra in (("review_task", {"verdict": "approve"}), ("approve_task", {})):
        with pytest.raises(PermissionError, match="acts as"):
            call_tool(session, tool, {"project": project, "task": "requirements", "role": req["reviewer"], **extra})
    assert store.load(project).tasks[f"{project}:requirements"].status is TaskStatus.IN_REVIEW

    reviewer = McpContext(nirmaan_org, store, role=req["reviewer"])  # configured at launch
    with pytest.raises(PermissionError, match="acts as"):
        call_tool(reviewer, "start_task", {"project": project, "task": "requirements", "role": req["owner"]})
    out = call_tool(reviewer, "review_task", {"project": project, "task": "requirements", "verdict": "approve"})
    assert out["result"] == "passed"
    approver = McpContext(nirmaan_org, store, role=req["approver"])
    assert call_tool(approver, "approve_task", {"project": project, "task": "requirements"})["result"] == "completed"
    gate = next(t for t in plan["tasks"] if t["id"] == f"{project}:requirements.gate")
    signer = McpContext(nirmaan_org, store, role=gate["owner"])
    with pytest.raises(PolicyViolationError, match=r"\[P12\]"):
        call_tool(signer, "approve_task", {"project": project, "task": "requirements.gate"})

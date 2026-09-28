"""Milestone 19, Phases 4 and 5: agents attach to roles and cannot cheat.

A runtime receives a scoped work packet and a tool handle, and everything it
returns goes through the engine: its artifacts are merely EXECUTED, its
statements are CLAIMs, and only tool runs the broker actually made can become
evidence. VeriTriage is reached as a real, executable verification tool.
"""

from __future__ import annotations

import pytest

from nirmaan_helpers import drive, tid

from nirmaan.models import EscalationKind, EvidenceKind, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import (
    EscalationRequest,
    NullRuntime,
    ResultStatus,
    ScriptedRuntime,
    ToolAccessDenied,
    ToolBroker,
    WorkResult,
    assemble,
    available_runtimes,
    run_task,
)
from nirmaan.work import PolicyViolationError, trace_graph

REGRESSION = "Investigate a regression failure introduced by a recent RTL commit."


@pytest.fixture()
def regression(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(REGRESSION)


def _investigate(fixture_log, tmp_path):
    return ("veritriage.investigate", {"paths": str(fixture_log("axi_timeout.log")), "workspace": str(tmp_path)})


def test_unbound_seats_decline_honestly(regression):
    triage = tid(regression, "triage")
    report = run_task(regression, triage, NullRuntime())
    assert report.status is ResultStatus.DECLINED
    assert regression.task(triage).status is TaskStatus.READY  # nothing happened, nothing was claimed
    assert "unbound" in available_runtimes()


def test_an_agent_triages_with_real_veritriage(regression, fixture_log, tmp_path):
    triage = tid(regression, "triage")
    runtime = ScriptedRuntime(
        WorkResult(ResultStatus.SUBMITTED, uncertainty=0.2,
                   artifacts=({"kind": "triage_report", "title": "Triage of axi_timeout"},)),
        tool_calls=(_investigate(fixture_log, tmp_path),),
    )
    report = run_task(regression, triage, runtime)
    assert regression.task(triage).status is TaskStatus.COMPLETED
    ev = regression.state.evidence[report.evidence[0]]
    run = regression.state.tool_runs[report.tool_runs[0]]
    assert ev.kind is EvidenceKind.VERITRIAGE_SESSION and ev.substantiated
    assert run.tool == "veritriage.investigate" and run.succeeded and ev.reference == run.references[0]
    assert ev.reference.startswith("ses-")
    # The organizational trace reaches into VeriTriage's Evidence Graph by session ID.
    graph = trace_graph(regression.state)
    assert any(n["id"] == f"veritriage:{ev.reference}" for n in graph["nodes"])


def test_claims_are_recorded_but_prove_nothing(regression):
    triage = tid(regression, "triage")
    runtime = ScriptedRuntime(WorkResult(
        ResultStatus.SUBMITTED, uncertainty=0.1,
        artifacts=({"kind": "triage_report", "title": "It is an RTL bug"},),
        claims=("I ran the simulator and it is definitely an RTL bug",),
    ))
    report = run_task(regression, triage, runtime)
    ev = regression.state.evidence[report.evidence[0]]
    assert ev.kind is EvidenceKind.CLAIM and not ev.substantiated
    assert regression.task(triage).status is TaskStatus.IN_PROGRESS  # submitted, not completed


def test_agents_cannot_cite_runs_that_never_happened(regression):
    triage = tid(regression, "triage")
    runtime = ScriptedRuntime(WorkResult(
        ResultStatus.SUBMITTED, uncertainty=0.0, tool_runs=("run-0042",),
        artifacts=({"kind": "triage_report", "title": "x"},),
    ))
    with pytest.raises(PolicyViolationError, match="P5"):
        run_task(regression, triage, runtime)


def test_uncertainty_must_be_declared(regression):
    runtime = ScriptedRuntime(WorkResult(ResultStatus.SUBMITTED, uncertainty=None,
                                         artifacts=({"kind": "triage_report", "title": "x"},)))
    with pytest.raises(PolicyViolationError, match="P3"):
        run_task(regression, tid(regression, "triage"), runtime)


def test_completion_without_output_is_refused(regression):
    runtime = ScriptedRuntime(WorkResult(ResultStatus.SUBMITTED, uncertainty=0.5))
    with pytest.raises(PolicyViolationError, match="P4"):
        run_task(regression, tid(regression, "triage"), runtime)


def test_an_uncertain_agent_escalates_up_the_real_chain(regression):
    triage = tid(regression, "triage")
    runtime = ScriptedRuntime(WorkResult(
        ResultStatus.NEEDS_ESCALATION, uncertainty=0.9,
        escalation=EscalationRequest(EscalationKind.UNCERTAINTY, "logs are truncated",
                                     "Can the regression be re-run with full logging?",
                                     recommended_options=("re-run", "use the waveform")),
    ))
    report = run_task(regression, triage, runtime)
    esc = regression.state.escalations[report.escalation]
    owner = regression.task(triage).owner
    assert esc.target_role == regression.org.roles[owner].escalates_to
    assert regression.task(triage).status is TaskStatus.ESCALATED


def test_contract_only_tools_are_never_run(regression):
    from nirmaan_helpers import agent

    broker = ToolBroker(regression)
    with pytest.raises(ToolAccessDenied, match="contract-only"):
        broker.invoke(agent("design.rtl.design.fsm.engineer"), "simulator.run", {})
    with pytest.raises(ToolAccessDenied, match="not granted"):
        broker.invoke(agent("product.management.roadmap.engineer"), "veritriage.investigate", {})
    assert regression.state.tool_runs == {}


def test_a_failing_tool_is_a_recorded_failed_run(regression, tmp_path):
    from nirmaan_helpers import agent

    run, outcome = ToolBroker(regression).invoke(
        agent("verification.debug.triage.engineer"), "veritriage.investigate",
        {"paths": str(tmp_path / "missing.log")}, tid(regression, "triage"))
    assert not run.succeeded and "not found" in run.summary
    ev = regression.record_evidence(tid(regression, "triage"), agent("verification.debug.triage.engineer"),
                                    EvidenceKind.VERITRIAGE_SESSION, run.summary, tool_run=run.id)
    assert not ev.substantiated


def test_the_work_packet_keeps_knowledge_scopes_separate(regression, fixture_log, tmp_path):
    drive(regression, until=tid(regression, "root-cause"), workspace=tmp_path)
    packet = assemble(regression, tid(regression, "root-cause"))
    assert {p["id"] for p in packet.company["constitution"]} == {f"P{i}" for i in range(1, 13)}
    assert any("veritriage_pack:" in src for s in packet.domain["skills"] for src in s["knowledge_sources"])
    assert packet.project["requirement"] == REGRESSION
    assert packet.task["outcomes"] == ["rtl_bug", "testbench_bug", "infrastructure", "spec_ambiguity"]
    assert packet.task["upstream_artifacts"]
    assert "veritriage.investigate" in packet.tools and "approval.grant" not in packet.tools

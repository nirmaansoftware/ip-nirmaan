"""Milestone 29: engineering records. Why did we choose this, and what went wrong?

Decision records and failure records are views over recorded state, like
``nirmaan gaps`` and the export: a decision task already holds its
alternatives, choice, rationale, evidence, who and when, and the branches it
cancelled; failures are already failed tool runs, attempts, blocks, failures,
and escalations. Nothing is inferred, nothing is stored, and the audit trail
is untouched by reading.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import agent, drive, human, tid

import nirmaan
from nirmaan.cli import app
from nirmaan.demos import demo
from nirmaan.export import export_project
from nirmaan.models import Criticality, DecisionKind, EscalationKind, TaskStatus, Verdict
from nirmaan.orchestrator import Orchestrator
from nirmaan.records import FailureCategory, decision_records, failure_records, failure_summary
from nirmaan.runtime import ToolBroker
from nirmaan.work import ProjectStore
from nirmaan.work.engine import state_fingerprint

REGRESSION = demo("4").requirement
BLOCK = "Create an AXI4-Lite register block."


@pytest.fixture()
def decided(nirmaan_org, fixed_clock, tmp_path):
    """Demo 4 driven through its root-cause decision, which concludes rtl_bug."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(REGRESSION)
    drive(engine, outcomes={"root-cause": "rtl_bug"}, workspace=tmp_path / "vt")
    return engine


# --- Decisions -----------------------------------------------------------------------------


def test_a_decision_task_is_a_full_decision_record(decided):
    engine = decided
    root = engine.task(tid(engine, "root-cause"))
    [record] = [r for r in decision_records(engine.state) if r.id == root.id]
    assert record.source == "decision_task" and record.question == root.title
    assert record.alternatives == root.outcomes and len(record.alternatives) == 4
    assert record.chosen == "rtl_bug" and record.status == root.status.value
    assert record.rationale and all(isinstance(r, str) for r in record.rationale)
    assert [e["id"] for e in record.evidence] == list(root.evidence)
    assert record.decided_by and record.decided_at.startswith("2026-09-28")
    untaken = sorted(t.id for t in engine.state.tasks.values()
                     if t.branch and t.branch[0] == root.id and t.branch[1] != "rtl_bug")
    assert len(untaken) == 3 and sorted(c["task"] for c in record.consequences) == untaken
    assert all("rtl_bug" in c["reason"] for c in record.consequences)


def test_an_open_decision_has_no_choice_and_a_recorded_decision_appears(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(REGRESSION)
    root = tid(engine, "root-cause")
    [open_one] = [r for r in decision_records(engine.state) if r.id == root]
    assert open_one.chosen is None and open_one.consequences == () and open_one.decided_by is None
    head = nirmaan_org.head_of(nirmaan_org.root.id)
    engine.record_decision(human(head.id), DecisionKind.ARCHITECTURE_DECISION, Criticality.LOW,
                           "Use round-robin arbitration.", "Fair, and bounded wait for every requester.")
    [explicit] = [r for r in decision_records(engine.state) if r.source == "decision_record"]
    assert explicit.chosen == "Use round-robin arbitration."
    assert explicit.rationale == ("Fair, and bounded wait for every requester.",)
    assert explicit.alternatives == () and explicit.decided_by.endswith(head.id)


# --- Failures ------------------------------------------------------------------------------


def test_a_failed_check_is_recorded_and_resolved_by_a_later_pass(decided):
    engine = decided
    task = engine.task(tid(engine, "triage"))
    actor = agent(task.owner)
    bad, _ = ToolBroker(engine).invoke(actor, "artifact.read", {"artifact": "no-such-artifact"}, task.id)
    [failure] = [f for f in failure_records(engine.state) if f.runs == (bad.id,)]
    assert failure.category is FailureCategory.CHECK_FAILED and failure.subject == "artifact.read"
    assert failure.task == task.id and failure.stage == "triage" and not failure.resolved
    good, _ = ToolBroker(engine).invoke(actor, "artifact.read", {"artifact": task.artifacts[0]}, task.id)
    [failure] = [f for f in failure_records(engine.state) if f.runs == (bad.id,)]
    assert failure.resolved and good.id in failure.resolution


def test_review_block_failure_and_escalation_are_classified(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(BLOCK)
    spec = tid(engine, "interface-spec")
    drive(engine, until=spec)
    task = engine.task(spec)
    owner, reviewer = agent(task.owner), agent(task.reviewer)
    draft = [{"kind": "interface_spec", "title": "Interface spec"}]

    engine.start(spec, owner)
    engine.block(spec, owner, "waiting on the register map")
    engine.unblock(spec, owner, "register map arrived")
    if engine.task(spec).status is TaskStatus.READY:
        engine.start(spec, owner)
    engine.fail(spec, owner, "the first draft contradicted the request")  # within the retry budget
    engine.start(spec, owner)
    engine.submit(spec, owner, draft)
    engine.review(spec, reviewer, Verdict.REQUEST_CHANGES, "the response codes are missing")
    esc = engine.escalate(spec, owner, EscalationKind.UNCERTAINTY, reason="SLVERR or DECERR?",
                          blocking_question="Which response for unmapped addresses?")

    by = {f.category: f for f in failure_records(engine.state) if f.task == spec}
    assert set(by) == {FailureCategory.BLOCKED, FailureCategory.FAILED, FailureCategory.REVIEW_SENT_BACK,
                       FailureCategory.ESCALATED}
    assert by[FailureCategory.BLOCKED].resolved  # it was unblocked
    assert not by[FailureCategory.FAILED].resolved and "contradicted" in by[FailureCategory.FAILED].summary
    sent_back = by[FailureCategory.REVIEW_SENT_BACK]
    assert sent_back.subject == task.reviewer and sent_back.attempt and not sent_back.resolved
    assert by[FailureCategory.ESCALATED].subject == "uncertainty" and not by[FailureCategory.ESCALATED].resolved

    engine.resolve_escalation(esc.id, human(esc.target_role), "SLVERR, as the interface spec says")
    engine.start(spec, owner)
    engine.submit(spec, owner, draft)
    engine.review(spec, reviewer, Verdict.APPROVE, "complete now")
    engine.approve(spec, human(engine.task(spec).approver), "agreed")
    by = {f.category: f for f in failure_records(engine.state) if f.task == spec}
    assert all(f.resolved for f in by.values()), {c.value: f.resolution for c, f in by.items()}
    assert "SLVERR" in by[FailureCategory.ESCALATED].resolution


def test_the_summary_counts_failures_across_projects(decided, nirmaan_org, fixed_clock):
    other = Orchestrator(nirmaan_org, clock=fixed_clock).plan(REGRESSION)
    for engine in (decided, other):
        task = engine.task(tid(engine, "triage"))
        ToolBroker(engine).invoke(agent(task.owner), "artifact.read", {"artifact": "missing"}, task.id)
    rows = {(r.category, r.subject): r for r in failure_summary([decided.state, other.state])}
    row = rows[(FailureCategory.CHECK_FAILED, "artifact.read")]
    assert row.count == 2 and row.projects == 2 and row.resolved == 0


# --- Reads, surfaces, and laws --------------------------------------------------------------


def test_the_views_are_reads(decided):
    before, audit = state_fingerprint(decided.state), len(decided.state.audit)
    decision_records(decided.state), failure_records(decided.state), failure_summary([decided.state])
    assert state_fingerprint(decided.state) == before and len(decided.state.audit) == audit


def test_the_export_carries_both_and_stays_deterministic(nirmaan_org, decided, tmp_path):
    store = ProjectStore(tmp_path / "store")
    store.save(decided.state)
    reloaded = store.load(decided.state.project.id)
    first, second = tmp_path / "a", tmp_path / "b"
    export_project(nirmaan_org, decided.state, first)
    export_project(nirmaan_org, reloaded, second)
    for rel in ("10_signoff/decisions.json", "10_signoff/decisions.md",
                "09_evidence/failures.json", "09_evidence/failures.md"):
        assert (first / rel).read_bytes() == (second / rel).read_bytes(), rel
    data = json.loads((first / "10_signoff/decisions.json").read_text())
    assert any(d["chosen"] == "rtl_bug" for d in data["decisions"])


def test_cli_and_mcp_return_the_same_records(nirmaan_org, decided, tmp_path):
    from nirmaan.integrations.veritriage import AutomationBridge
    from nirmaan.mcp import McpContext, NirmaanMcpServer
    from veritriage.workspace import WorkspaceServices

    root = tmp_path / "store"
    ProjectStore(root).save(decided.state)
    project = decided.state.project.id
    cli = CliRunner().invoke(app, ["decisions", project, "--root", str(root), "--json"])
    assert cli.exit_code == 0, cli.output
    expected = [r.to_dict() for r in decision_records(decided.state)]
    assert json.loads(cli.output) == expected
    failures = CliRunner().invoke(app, ["failures", project, "--root", str(root), "--json"])
    assert failures.exit_code == 0 and json.loads(failures.output)["failures"] == [
        f.to_dict() for f in failure_records(decided.state)]

    bridge = AutomationBridge(WorkspaceServices(session_root=tmp_path / "sessions"))
    server = NirmaanMcpServer(McpContext(nirmaan_org, ProjectStore(root), bridge.publish, bridge.recent))
    line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "decisions", "arguments": {"project": project}}})
    result = server.handle_line(line)["result"]
    assert not result["isError"] and json.loads(result["content"][0]["text"]) == expected


def test_records_name_no_stage_tool_kind_or_role(nirmaan_org):
    org = nirmaan_org
    vocabulary = (set(org.units) | set(org.skills) | set(org.capabilities) | set(org.roles) | set(org.tools)
                  | {s.id for w in org.workflows.values() for s in w.stages}
                  | {k for w in org.workflows.values() for s in w.stages for k in s.outputs})
    path = Path(nirmaan.__file__).parent / "records.py"
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in vocabulary, f"records.py hard-codes {node.value!r}"


# --- Crown jewel ---------------------------------------------------------------------------


def test_a_new_decision_stage_is_recorded_with_no_core_changes(fixed_clock):
    """An extension workflow with a decision stage and two branches; its record needs no core change."""
    from nirmaan.company import builder
    from nirmaan.models import (
        Criticality as C,
        EvidenceKind,
        EvidenceRequirement,
        IntentRule,
        ReviewRequirement,
        StageTemplate,
        WorkflowTemplate,
    )
    from nirmaan.org import register_extension, unregister_extension

    reviewed = EvidenceRequirement(description="Independent review recorded", accepts=(EvidenceKind.REVIEW_RECORD,))

    @register_extension("test-fork")
    def fork(b):
        b.add(
            IntentRule(intent="fork_choice", patterns=(r"\bfork in the road\b",), priority=5),
            WorkflowTemplate(id="fork", name="Fork", description="Choose a path.", intents=("fork_choice",), stages=(
                StageTemplate(id="brief", title="Brief", phase="Requirements", capability="req.analyze",
                              criticality=C.MEDIUM, review=ReviewRequirement(capability="req.review"),
                              outputs=("requirements_spec",), evidence=(reviewed,)),
                StageTemplate(id="choose", title="Choose a path", phase="Requirements", capability="req.analyze",
                              depends_on=("brief",), criticality=C.MEDIUM, outcomes=("left", "right"),
                              review=ReviewRequirement(capability="req.review"),
                              outputs=("requirements_spec",), evidence=(reviewed,)),
                StageTemplate(id="go-left", title="Go left", phase="Requirements", capability="req.analyze",
                              depends_on=("choose",), branch=("choose", "left"), criticality=C.LOW,
                              outputs=("requirements_spec",)),
                StageTemplate(id="go-right", title="Go right", phase="Requirements", capability="req.analyze",
                              depends_on=("choose",), branch=("choose", "right"), criticality=C.LOW,
                              outputs=("requirements_spec",)),
            )),
        )

    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("We are at a fork in the road.")
        drive(engine, outcomes={"choose": "left"})
        [record] = [r for r in decision_records(engine.state) if r.id == tid(engine, "choose")]
        assert record.alternatives == ("left", "right") and record.chosen == "left"
        assert [c["task"] for c in record.consequences] == [tid(engine, "go-right")]
        assert engine.task(tid(engine, "go-right")).status is TaskStatus.CANCELLED
    finally:
        unregister_extension("test-fork")

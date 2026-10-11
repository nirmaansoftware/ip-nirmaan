"""Milestone 33 (working name): recurring failures propose skill changes; only a person adopts them.

``learning_proposals`` reads the failure records of several projects and
proposes changes to the skills whose work keeps failing the same way, citing
every record it rests on. Adopting one is a recorded human decision through the
engine; it changes no skill by itself.
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
from nirmaan.models import Level, Verdict
from nirmaan.orchestrator import Orchestrator
from nirmaan.proposals import (
    ProposalError,
    decide_proposal,
    learning_proposals,
    register_proposal_rule,
    unregister_proposal_rule,
)
from nirmaan.records import decision_records
from nirmaan.runtime import ToolBroker
from nirmaan.work import ProjectStore, WorkError
from nirmaan.work.engine import state_fingerprint

REQUESTS = ("Create an AXI4-Lite register block.", "Create an APB register block with four 32-bit registers.")


def _plan(org, clock, text):
    return Orchestrator(org, clock=clock).plan(text)


def _failed_check(engine, stage="rtl-implementation"):
    task = engine.task(tid(engine, stage))
    run, _ = ToolBroker(engine).invoke(agent(task.owner), "artifact.read", {"artifact": "missing"}, task.id)
    return run


def _sent_back(engine, comments):
    spec = tid(engine, "interface-spec")
    drive(engine, until=spec)
    task = engine.task(spec)
    engine.start(spec, agent(task.owner))
    engine.submit(spec, agent(task.owner), [{"kind": "interface_spec", "title": "Interface spec"}])
    engine.review(spec, agent(task.reviewer), Verdict.REQUEST_CHANGES, comments)


def _manager(org):
    from nirmaan.models import Criticality, DecisionKind
    from nirmaan.org import AuthorityService

    authority = AuthorityService(org)
    return next(r.id for r in sorted(org.roles.values(), key=lambda r: r.id) if r.level is Level.MANAGER
                and authority.check(r.id, DecisionKind.CROSS_TEAM_DECISION, Criticality.MEDIUM, None).allowed)


@pytest.fixture()
def two_failing(nirmaan_org, fixed_clock):
    engines = [_plan(nirmaan_org, fixed_clock, text) for text in REQUESTS]
    runs = [_failed_check(e) for e in engines]
    return engines, runs


# --- Proposals -----------------------------------------------------------------------------


def test_a_check_failing_in_two_projects_proposes_a_skill_change(nirmaan_org, two_failing):
    engines, runs = two_failing
    [proposal] = [p for p in learning_proposals(nirmaan_org, [e.state for e in engines])
                  if p.rule == "recurring-check-failure"]
    assert proposal.capability == "rtl.implement" and proposal.subject == "artifact.read"
    assert proposal.targets == ("rtl_design",) and proposal.count == 2 and proposal.projects == 2
    assert sorted(r for e in proposal.evidence for r in e["runs"]) == sorted(r.id for r in runs)
    assert "artifact.read" in proposal.suggestion and proposal.status == "open"


def test_one_failure_proposes_nothing_and_the_id_survives_new_evidence(nirmaan_org, fixed_clock, two_failing):
    engines, _ = two_failing
    assert learning_proposals(nirmaan_org, [engines[0].state]) == []
    first = learning_proposals(nirmaan_org, [e.state for e in engines])[0].id
    _failed_check(engines[0])
    again = learning_proposals(nirmaan_org, [e.state for e in engines])[0]
    assert again.id == first and again.count == 3


def test_reviews_sending_work_back_propose_a_validation_criterion(nirmaan_org, fixed_clock):
    engines = [_plan(nirmaan_org, fixed_clock, text) for text in REQUESTS]
    _sent_back(engines[0], "the unmapped-address response is not specified")
    _sent_back(engines[1], "the error response for misaligned addresses is missing")
    [proposal] = [p for p in learning_proposals(nirmaan_org, [e.state for e in engines])
                  if p.rule == "recurring-review-send-back"]
    assert proposal.capability == "arch.interface" and proposal.targets == ("interface_specification",)
    assert "unmapped-address" in proposal.suggestion and "misaligned" in proposal.suggestion


def test_reading_changes_nothing(nirmaan_org, two_failing):
    engines, _ = two_failing
    before = [state_fingerprint(e.state) for e in engines], nirmaan_org.fingerprint
    learning_proposals(nirmaan_org, [e.state for e in engines])
    assert ([state_fingerprint(e.state) for e in engines], nirmaan_org.fingerprint) == before


# --- Deciding ------------------------------------------------------------------------------


def test_a_manager_adopts_a_proposal_as_a_recorded_decision(nirmaan_org, two_failing):
    engines, _ = two_failing
    proposal = learning_proposals(nirmaan_org, [e.state for e in engines])[0]
    skills_before = nirmaan_org.skills["rtl_design"]
    decision = decide_proposal(engines[0], proposal, human(_manager(nirmaan_org)), adopt=True,
                               reason="Twice in two projects; worth a procedure.")
    assert proposal.id in decision.statement and decision.rationale.startswith("Twice")
    recorded = [r for r in decision_records(engines[0].state) if r.source == "decision_record"]
    assert len(recorded) == 1 and proposal.id in recorded[0].chosen
    again = learning_proposals(nirmaan_org, [e.state for e in engines])[0]
    assert again.status == "adopted"
    assert nirmaan_org.skills["rtl_design"] == skills_before  # adopting edits no knowledge by itself


def test_only_an_authorized_human_may_decide(nirmaan_org, fixed_clock, two_failing):
    engines, _ = two_failing
    proposal = learning_proposals(nirmaan_org, [e.state for e in engines])[0]
    with pytest.raises(ProposalError, match="human"):
        decide_proposal(engines[0], proposal, agent(_manager(nirmaan_org)), adopt=True, reason="x")
    with pytest.raises(WorkError):
        decide_proposal(engines[0], proposal, human(engines[0].task(tid(engines[0], "rtl-implementation")).owner),
                        adopt=False, reason="x")
    elsewhere = _plan(nirmaan_org, fixed_clock, "Create a parameterizable synchronous FIFO.")
    with pytest.raises(ProposalError, match="rests on"):
        decide_proposal(elsewhere, proposal, human(_manager(nirmaan_org)), adopt=True, reason="x")


def test_the_cli_lists_and_decides(nirmaan_org, two_failing, tmp_path):
    engines, _ = two_failing
    root = tmp_path / "store"
    for e in engines:
        ProjectStore(root).save(e.state)
    ids = [e.state.project.id for e in engines]
    listed = CliRunner().invoke(app, ["learn", *ids, "--root", str(root), "--json"])
    assert listed.exit_code == 0, listed.output
    [proposal] = json.loads(listed.output)
    decided = CliRunner().invoke(app, ["learn", *ids, "--root", str(root), "--decide", proposal["id"], "--in", ids[0],
                                       "--as", _manager(nirmaan_org), "--reject", "--reason", "One-off typos."])
    assert decided.exit_code == 0, decided.output
    again = json.loads(CliRunner().invoke(app, ["learn", *ids, "--root", str(root), "--json"]).output)
    assert again[0]["status"] == "rejected"


def test_proposals_name_no_stage_tool_kind_or_role(nirmaan_org):
    org = nirmaan_org
    engineering_tools = {t for t, spec in org.tools.items() if spec.category != "platform"}
    vocabulary = (set(org.units) | set(org.skills) | set(org.capabilities) | set(org.roles) | engineering_tools
                  | {s.id for w in org.workflows.values() for s in w.stages}
                  | {k for w in org.workflows.values() for s in w.stages for k in s.outputs})
    path = Path(nirmaan.__file__).parent / "proposals.py"
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in vocabulary, f"proposals.py hard-codes {node.value!r}"


# --- Crown jewel ---------------------------------------------------------------------------


def test_a_new_proposal_rule_needs_no_core_changes(nirmaan_org, fixed_clock):
    """A rule for recurring escalations, registered here, proposes from them."""
    from nirmaan.models import EscalationKind
    from nirmaan.proposals import Proposal, proposal_id, providers
    from nirmaan.records import FailureCategory

    @register_proposal_rule("recurring-escalation")
    def recurring_escalation(org, observed):
        hits = [(state, record) for state, record in observed if record.category is FailureCategory.ESCALATED]
        if len({(s.project.id, r.task) for s, r in hits}) < 2:
            return []
        capability = hits[0][0].tasks[hits[0][1].task].capability
        return [Proposal(id=proposal_id("recurring-escalation", capability, "uncertainty"),
                         rule="recurring-escalation", capability=capability, subject="uncertainty",
                         targets=providers(org, capability), statement="Seats keep escalating.",
                         suggestion="Add the recurring question to the procedures.", count=len(hits),
                         projects=len({s.project.id for s, _ in hits}),
                         evidence=tuple({"project": s.project.id, "task": r.task} for s, r in hits))]

    try:
        engines = [_plan(nirmaan_org, fixed_clock, text) for text in REQUESTS]
        for e in engines:
            spec = tid(e, "interface-spec")
            drive(e, until=spec)
            e.escalate(spec, agent(e.task(spec).owner), EscalationKind.UNCERTAINTY, reason="SLVERR or DECERR?",
                       blocking_question="Which response?")
        rules = {p.rule for p in learning_proposals(nirmaan_org, [e.state for e in engines])}
        assert "recurring-escalation" in rules
    finally:
        unregister_proposal_rule("recurring-escalation")

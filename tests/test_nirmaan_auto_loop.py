"""Milestone 29: an unattended owner and reviewer loop in one command.

``nirmaan drive`` runs a task's owner seat (with M26's attempts), its
independent reviewer seat, and the owner again on a change request (M27),
until the task reaches something only a person may do (an approval or a gate),
an escalation, a block, or a decline. It never approves, never crosses a gate,
decides each step from state alone (so it resumes by being run again), audits
every step, and stops before a step whose worst case would exceed its call
budget. No test calls a model API; real-tool tests skip when an executable is
absent (or fail when CI names it in NIRMAAN_REQUIRE_EDA).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import attach_evidence, drive, human, needs, tid

from nirmaan.models import ActorKind, ReviewState, TaskKind, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import (
    Completion,
    MockLLM,
    ModelRuntime,
    ResultStatus,
    Stop,
    loop,
    plan_loop,
    register_runtime,
    unregister_runtime,
)
from nirmaan.work import ProjectStore

FIXTURES = Path(__file__).parent / "fixtures"
AXI = FIXTURES / "rtl" / "axi4_lite"
AXI_BLOCK = "Create an AXI4-Lite register block."
BRIDGE = "Create a 4-port AXI-to-NoC bridge."
SPEC_V1 = "# AXI4-Lite register block\n\nFour 32-bit registers.\n"
SPEC_V2 = SPEC_V1 + "\nUnmapped addresses answer SLVERR.\n"

#: What the loop may never do: approve, sign, complete, resolve, or otherwise decide for a person.
DECISIONS = ("task.approve", "gate.approve", "task.complete", "escalation.resolve", "task.unblock", "task.cancel")


# --- Scripted seats that cite what their prompt declares -----------------------------------------


class Seat:
    """A scripted model. A reply may be a function of the prompt, so it can cite the prompt's own tokens."""

    name = "test-seat"

    def __init__(self, *replies) -> None:
        self.replies = list(replies)
        self.calls: list = []

    def complete(self, prompt) -> Completion:
        self.calls.append(prompt)
        reply = self.replies.pop(0)
        return Completion(reply(prompt) if callable(reply) else reply, self.name)


def first(prompt, kind: str | None = None) -> str:
    cited = [c for c in prompt.citations if kind is None or c.kind == kind]
    return cited[0].token


def file(path: str, kind: str, content: str, cite: str, entry: str | None = None) -> dict:
    return {"path": path, "kind": kind, "title": path, "summary": f"{path}, from {cite}.",
            "content": content, **({"entry": entry} if entry else {})}


def answer(*files: dict) -> str:
    meta = [{k: v for k, v in f.items() if k != "content"} for f in files]
    head = json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], "files": meta,
                       "escalation": None}, indent=1)
    return f"{head}\n" + "".join(f"=== FILE: {f['path']} ===\n{f['content']}=== END FILE ===\n" for f in files)


def spec(body: str):
    return lambda prompt: answer(file("interface_spec.md", "interface_spec", body, first(prompt, "artifact")))


def verdict(word: str, comments: str):
    def reply(prompt) -> str:
        runs = [c for c in prompt.citations if c.kind == "run"]
        cite = runs[0].token if runs else first(prompt)
        return json.dumps({"verdict": word, "comments": f"{comments} See {cite}.", "uncertainty": 0.2})
    return reply


def loop_entries(engine) -> list:
    return [e for e in engine.state.audit if e.action == "loop.step"]


def decisions_by_agents(engine, *tasks: str) -> list:
    """Every decision an AI agent took on these tasks: the loop acts only as AI agents, so this stays empty."""
    return [e for e in engine.state.audit
            if e.action in DECISIONS and e.actor_kind is ActorKind.AI_AGENT and e.subject in tasks]


@pytest.fixture()
def axi_spec(nirmaan_org, fixed_clock, tmp_path):
    """The AXI4-Lite register block at its interface-spec seat, requirements approved."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    seat = tid(engine, "interface-spec")
    drive(engine, until=seat)
    return engine, seat


@pytest.fixture()
def runtimes():
    """Register scripted seats under runtime IDs, as the CLI finds them; unregister afterwards."""
    names: list[str] = []

    def add(runtime_id: str, llm) -> None:
        register_runtime(runtime_id)(lambda: ModelRuntime(llm, runtime_id=runtime_id))
        names.append(runtime_id)

    yield add
    for name in names:
        unregister_runtime(name)


def cli(*args: str):
    from nirmaan.cli import app

    return CliRunner().invoke(app, list(args))


# --- 1. The full loop on the AXI4-Lite flow, in one command ---------------------------------------


def test_one_command_drives_owner_review_repair_and_review_and_stops_at_the_human_approval(
        axi_spec, runtimes, tmp_path, monkeypatch):
    engine, seat = axi_spec
    monkeypatch.setitem(sys.modules, "anthropic", None)  # any import of the SDK now fails
    owner = Seat(spec(SPEC_V1), spec(SPEC_V2))
    reviewer = Seat(verdict("request_changes", "Unmapped addresses are unspecified."),
                    verdict("approve", "SLVERR is now specified."))
    runtimes("test-owner", owner)
    runtimes("test-reviewer", reviewer)
    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    project = engine.state.project.id

    result = cli("drive", project, "interface-spec", "--runtime", "test-owner", "--reviewer-runtime",
                 "test-reviewer", "--review-rounds", "2", "--root", str(root))
    assert result.exit_code == 0, result.output
    state = ProjectStore(root).load(project)
    task = state.tasks[seat]
    assert task.status is TaskStatus.IN_REVIEW and task.review_state is ReviewState.PASSED
    assert len(owner.calls) == 2 and len(reviewer.calls) == 2
    assert "Repair after review" in owner.calls[1].render() and "Unmapped addresses" in owner.calls[1].render()
    assert "awaiting_approval" in result.output and "calls: 4 of 20" in result.output

    steps = [e for e in state.audit if e.action == "loop.step"]
    assert [(e.details["seat"], e.details["status"]) for e in steps] == [
        ("owner", "submitted"), ("reviewer", "submitted"), ("owner", "submitted"), ("reviewer", "submitted")]
    assert [e.details["runtime"] for e in steps] == ["test-owner", "test-reviewer"] * 2
    assert all(e.actor == f"test-owner@{task.owner}" for e in steps if e.details["seat"] == "owner")
    assert not [e for e in state.audit if e.action in DECISIONS and e.subject == seat]

    # The loop left a state a person can act on: the approver approves, and only the repaired file counts.
    from nirmaan.company import build_organization
    from nirmaan.work import TaskEngine

    after = TaskEngine(build_organization(), state)
    after.approve(seat, human(task.approver), "agreed")
    assert after.task(seat).status is TaskStatus.COMPLETED
    (art,) = [after.state.artifacts[a] for a in after.task(seat).artifacts]
    assert Path(art.location).read_text() == SPEC_V2


@needs("verilator", "iverilog", "vvp", "yosys", "sby", "yices-smt2")
def test_the_loop_drives_real_axi4_lite_rtl_through_attempts_review_and_repair(nirmaan_org, fixed_clock, tmp_path):
    from nirmaan.models import MemoryScope

    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    engine.remember(MemoryScope.TASK, rtl, "input.workspace", str(tmp_path / "work"), human(engine.task(rtl).owner))
    source = (AXI / "axi4_lite_regs.v").read_text()
    mutant = source.replace("assign s_axil_arready = !s_axil_rvalid;", "assign s_axil_arready = 1'b1;")

    def rtl_answer(text: str):
        def reply(prompt) -> str:
            cite = first(prompt, "artifact")
            return answer(file("axi4_lite_regs.v", "rtl_source", text, cite, entry="axi4_lite_regs"),
                          file("axi4_lite_regs_tb.v", "testbench", (AXI / "axi4_lite_regs_tb.v").read_text(), cite,
                               entry="axi4_lite_regs_tb"),
                          file("axi4_lite_regs.sby", "formal_spec", (AXI / "axi4_lite_regs.sby").read_text(), cite))
        return reply

    owner = Seat(rtl_answer(mutant), rtl_answer(source), rtl_answer("// Reviewed.\n" + source))
    reviewer = Seat(verdict("request_changes", "Document the reviewed handshake."), verdict("approve", "Clean."))
    report = loop(engine, ModelRuntime(owner), ModelRuntime(reviewer), rtl, attempts=2, review_rounds=2)

    assert report.stops == {rtl: Stop.AWAITING_APPROVAL}, report.steps
    assert [(s.seat, s.status, s.calls) for s in report.steps] == [
        ("owner", "submitted", 2), ("reviewer", "submitted", 1), ("owner", "submitted", 1),
        ("reviewer", "submitted", 1)]
    assert report.calls == 5
    task = engine.task(rtl)
    assert task.status is TaskStatus.IN_REVIEW and task.review_state is ReviewState.PASSED
    submitted = {engine.state.artifacts[a].kind: engine.state.artifacts[a] for a in task.artifacts}
    assert Path(submitted["rtl_source"].location).read_text().startswith("// Reviewed.")
    runs = [r for r in engine.state.tool_runs.values() if r.task == rtl]
    assert any(not r.succeeded and r.tool == "formal.run" for r in runs)  # the mutant's counterexample, recorded
    assert not decisions_by_agents(engine, rtl)


# --- 2. It never self-approves ---------------------------------------------------------------------


def test_the_loop_never_approves_and_a_reviewed_task_costs_nothing_more(axi_spec):
    engine, seat = axi_spec
    report = loop(engine, ModelRuntime(Seat(spec(SPEC_V1))), ModelRuntime(Seat(verdict("approve", "Fine."))), seat)
    assert report.stops == {seat: Stop.AWAITING_APPROVAL} and report.calls == 2
    before = len(engine.state.audit)

    again = loop(engine, ModelRuntime(Seat()), ModelRuntime(Seat()), seat)  # an empty script: any call would fail
    assert again.stops == {seat: Stop.AWAITING_APPROVAL} and again.steps == [] and again.calls == 0
    assert len(engine.state.audit) == before
    assert engine.task(seat).review_state is ReviewState.PASSED and engine.task(seat).status is TaskStatus.IN_REVIEW
    assert not decisions_by_agents(engine, seat)


def test_the_loop_module_calls_no_decision_a_person_makes():
    path = Path(__file__).parent.parent / "src" / "nirmaan" / "runtime" / "loop.py"
    tree = ast.parse(path.read_text())
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not called & {"approve", "approve_gate", "complete", "resolve_escalation", "unblock", "cancel",
                         "reassign", "review", "submit", "start", "record_evidence"}
    assert "HUMAN" not in path.read_text()  # the loop acts as no person


# --- 3. Project mode stops at gates, and never crosses one --------------------------------------------


@pytest.mark.parametrize("human_gate", [True, False])
def test_project_mode_stops_at_a_gate_and_never_crosses_it(nirmaan_org, fixed_clock, human_gate):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(
        BRIDGE, gate_overrides={"gate.requirements": human_gate})
    req = tid(engine, "requirements")
    gate = next(t for t in engine.state.tasks.values() if t.kind is TaskKind.GATE and t.depends_on == (req,))
    assert gate.human_required is human_gate
    behind = [t.id for t in engine.state.tasks.values() if gate.id in t.depends_on]

    report = loop(engine, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()))
    assert report.stops[req] is Stop.AWAITING_APPROVAL
    assert [s.task for s in report.steps] == [req, req]  # nothing else was ready
    task = engine.task(req)
    attach_evidence(engine, req)
    engine.approve(req, human(task.approver), "requirements agreed")
    assert engine.task(gate.id).status is TaskStatus.READY

    before = len(engine.state.audit)
    report = loop(engine, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()))
    assert report.steps == [] and report.calls == 0
    assert report.stops[gate.id] is Stop.AWAITING_GATE
    assert engine.task(gate.id).status is TaskStatus.READY
    assert all(engine.task(t).status is TaskStatus.PLANNED for t in behind)
    assert len(engine.state.audit) == before
    assert not [e for e in engine.state.audit if e.action == "gate.approve"]


# --- 4. The budget ------------------------------------------------------------------------------------


def test_a_step_starts_only_if_its_worst_case_fits_the_budget(axi_spec):
    engine, seat = axi_spec
    owner, reviewer = Seat(spec(SPEC_V1)), Seat(verdict("approve", "Fine."))
    report = loop(engine, ModelRuntime(owner), ModelRuntime(reviewer), seat, max_calls=1)
    assert report.stops == {seat: Stop.BUDGET} and report.calls == 1
    assert len(owner.calls) == 1 and reviewer.calls == []
    assert engine.task(seat).review_state is ReviewState.PENDING

    # Resumed with a budget of one: the reviewer step fits; the owner is not asked again.
    report = loop(engine, ModelRuntime(Seat()), ModelRuntime(reviewer), seat, max_calls=1)
    assert [s.seat for s in report.steps] == ["reviewer"] and report.calls == 1


def test_an_owner_step_is_charged_its_attempts(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    llm = MockLLM()
    report = loop(engine, ModelRuntime(llm), ModelRuntime(MockLLM()), rtl, attempts=3, max_calls=2)
    assert report.stops == {rtl: Stop.BUDGET} and llm.calls == [] and report.steps == []
    assert engine.task(rtl).status is TaskStatus.READY


# --- 5. Resume after interruption ------------------------------------------------------------------------


class Crash:
    """A model connection that drops once, on the given call."""

    name = "crash"

    def __init__(self, inner: Seat, on: int) -> None:
        self.inner, self.on, self.seen = inner, on, 0

    def complete(self, prompt) -> Completion:
        self.seen += 1
        if self.seen == self.on:
            raise RuntimeError("connection lost")
        return self.inner.complete(prompt)


def test_an_interrupted_loop_resumes_from_saved_state_alone(axi_spec, runtimes, tmp_path):
    engine, seat = axi_spec
    owner = Seat(spec(SPEC_V1), spec(SPEC_V2))
    reviewer = Seat(verdict("request_changes", "Name the error response."), verdict("approve", "Named."))
    runtimes("test-owner", owner)
    runtimes("test-reviewer", Crash(reviewer, on=2))
    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    project = engine.state.project.id
    args = ("drive", project, "interface-spec", "--runtime", "test-owner", "--reviewer-runtime", "test-reviewer",
            "--review-rounds", "2", "--root", str(root))

    crashed = cli(*args)
    assert crashed.exit_code != 0 and "connection lost" in str(crashed.exception)
    state = ProjectStore(root).load(project)  # every finished step was saved
    assert state.tasks[seat].status is TaskStatus.IN_REVIEW and state.tasks[seat].review_state is ReviewState.PENDING
    assert [e.details["seat"] for e in state.audit if e.action == "loop.step"] == ["owner", "reviewer", "owner"]

    resumed = cli(*args)
    assert resumed.exit_code == 0, resumed.output
    state = ProjectStore(root).load(project)
    assert state.tasks[seat].review_state is ReviewState.PASSED
    assert len(owner.calls) == 2 and len(reviewer.calls) == 2  # nothing finished was redone
    steps = [e for e in state.audit if e.action == "loop.step"]
    assert [e.details["seat"] for e in steps] == ["owner", "reviewer", "owner", "reviewer"]


# --- 6. Escalation when a limit is spent ----------------------------------------------------------------


def test_spent_review_rounds_escalate_with_no_model_call_and_the_loop_stops(axi_spec):
    engine, seat = axi_spec
    owner = Seat(spec(SPEC_V1))
    report = loop(engine, ModelRuntime(owner), ModelRuntime(Seat(verdict("request_changes", "Too thin."))), seat)
    assert report.stops == {seat: Stop.ESCALATED}
    assert [(s.seat, s.status, s.calls) for s in report.steps] == [
        ("owner", "submitted", 1), ("reviewer", "submitted", 1), ("owner", "needs_escalation", 0)]
    assert len(owner.calls) == 1
    esc = engine.state.escalations[report.steps[-1].escalation]
    assert esc.task == seat and "1 of 1 review rounds" in esc.reason
    assert engine.task(seat).status is TaskStatus.ESCALATED


def test_spent_attempts_escalate_after_the_refusals(nirmaan_org, fixed_clock):
    """The default mock answer carries no RTL file, so each attempt is refused; the third step escalates."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    llm = MockLLM()
    report = loop(engine, ModelRuntime(llm), ModelRuntime(MockLLM()), rtl, attempts=2)
    assert [(s.status, s.calls) for s in report.steps] == [("refused", 2), ("needs_escalation", 0)]
    assert report.stops == {rtl: Stop.ESCALATED} and len(llm.calls) == 2
    assert "2 of 2 attempts" in engine.state.escalations[report.steps[-1].escalation].reason


def test_with_one_attempt_a_refusal_stops_the_loop_rather_than_asking_forever(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    llm = MockLLM()
    report = loop(engine, ModelRuntime(llm), ModelRuntime(MockLLM()), rtl)
    assert report.stops == {rtl: Stop.REFUSED} and len(llm.calls) == 1
    assert engine.task(rtl).status is TaskStatus.IN_PROGRESS


def test_a_seat_that_declines_stops_the_loop(axi_spec):
    engine, seat = axi_spec
    report = loop(engine, ModelRuntime(Seat("not json")), ModelRuntime(Seat()), seat)
    assert report.stops == {seat: Stop.DECLINED} and len(report.steps) == 1


# --- 7. Dry run ---------------------------------------------------------------------------------------


def test_the_plan_is_the_worst_case_sequence_from_state(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(AXI_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    task = engine.task(rtl)
    plan = plan_loop(engine, "mock-llm", "mock-llm", rtl, attempts=3, review_rounds=2)
    assert [(p.seat, p.role, p.round, p.calls) for p in plan.steps] == [
        ("owner", task.owner, 1, 3), ("reviewer", task.reviewer, 1, 1), ("owner", task.owner, 2, 3),
        ("reviewer", task.reviewer, 2, 1), ("owner", task.owner, 3, 0)]
    assert plan.calls == 8 and plan.stops == {rtl: Stop.AWAITING_APPROVAL}


def test_dry_run_prints_the_plan_and_calls_and_saves_nothing(axi_spec, runtimes, tmp_path):
    engine, seat = axi_spec
    owner, reviewer = Seat(), Seat()
    runtimes("test-owner", owner)
    runtimes("test-reviewer", reviewer)
    root = tmp_path / "store"
    path = ProjectStore(root).save(engine.state)
    saved = Path(path).read_bytes()

    result = cli("drive", engine.state.project.id, "interface-spec", "--runtime", "test-owner",
                 "--reviewer-runtime", "test-reviewer", "--review-rounds", "2", "--dry-run", "--root", str(root))
    assert result.exit_code == 0, result.output
    task = engine.task(seat)
    assert f"1. owner {task.owner} on test-owner: round 1 of 2, up to 1 call" in result.output
    assert f"2. reviewer {task.reviewer} on test-reviewer: 1 call" in result.output
    assert "worst case: 4 calls, budget 20" in result.output
    assert "dry run: no model was called" in result.output
    assert owner.calls == [] and reviewer.calls == []
    assert Path(path).read_bytes() == saved


def test_a_shared_runtime_is_named_in_the_report(axi_spec):
    engine, seat = axi_spec
    report = loop(engine, ModelRuntime(Seat(spec(SPEC_V1)), "same"),
                  ModelRuntime(Seat(verdict("approve", "Fine.")), "same"), seat)
    assert report.shared_runtime
    roles = {s.seat: s.role for s in report.steps}
    assert roles["owner"] == engine.task(seat).owner and roles["reviewer"] == engine.task(seat).reviewer
    assert roles["owner"] != roles["reviewer"]


# --- 8. Crown jewel: a new workflow is driven with no core changes -----------------------------------------


@pytest.fixture()
def notes_flow(fixed_clock):
    """A two-stage workflow, gated by a human between the stages, added as data in the test."""
    from nirmaan.company import builder
    from nirmaan.models import (
        Criticality,
        EvidenceKind,
        EvidenceRequirement,
        IntentRule,
        ReviewRequirement,
        StageTemplate,
        WorkflowTemplate,
    )
    from nirmaan.org import register_extension, unregister_extension

    @register_extension("test-loop-notes")
    def notes(b):
        reviewed = EvidenceRequirement(description="Independent review recorded",
                                       accepts=(EvidenceKind.REVIEW_RECORD,))
        b.add(
            IntentRule(intent="loop_notes", patterns=(r"\bloop notes\b",), priority=5),
            WorkflowTemplate(
                id="loop-notes", name="Loop notes", description="Two notes, gated.", intents=("loop_notes",),
                stages=(
                    StageTemplate(id="first-note", title="First note", phase="Requirements",
                                  capability="req.analyze", criticality=Criticality.MEDIUM,
                                  review=ReviewRequirement(capability="req.review"), gate="gate.requirements",
                                  outputs=("requirements_spec",), evidence=(reviewed,), max_review_rounds=2),
                    StageTemplate(id="second-note", title="Second note", phase="Requirements",
                                  capability="req.analyze", depends_on=("first-note",),
                                  criticality=Criticality.MEDIUM, review=ReviewRequirement(capability="req.review"),
                                  outputs=("requirements_spec",), evidence=(reviewed,)),
                ),
            ),
        )

    try:
        org = builder().build()
        yield Orchestrator(org, clock=fixed_clock).plan("Write loop notes for a timer.",
                                                        gate_overrides={"gate.requirements": True})
    finally:
        unregister_extension("test-loop-notes")


def test_a_new_workflow_is_driven_with_no_core_changes(notes_flow):
    engine = notes_flow
    one, two = tid(engine, "first-note"), tid(engine, "second-note")
    gate = next(t for t in engine.state.tasks.values() if t.kind is TaskKind.GATE)
    assert gate.human_required and engine.task(two).depends_on == (gate.id,)

    reviewer = Seat(verdict("request_changes", "Say what the timer counts."), verdict("approve", "Clear now."),
                    verdict("approve", "Fine."))
    owner = MockLLM()
    report = loop(engine, ModelRuntime(owner), ModelRuntime(reviewer))  # the whole project
    assert [(s.task, s.seat) for s in report.steps] == [(one, "owner"), (one, "reviewer")] * 2
    assert report.stops[one] is Stop.AWAITING_APPROVAL and engine.task(two).status is TaskStatus.PLANNED
    assert "Repair after review" in owner.calls[1].render()

    engine.approve(one, human(engine.task(one).approver), "agreed")
    report = loop(engine, ModelRuntime(owner), ModelRuntime(reviewer))
    assert report.steps == [] and report.stops[gate.id] is Stop.AWAITING_GATE

    engine.approve_gate(gate.id, human(gate.owner), "signed")
    report = loop(engine, ModelRuntime(owner), ModelRuntime(reviewer))
    assert [(s.task, s.seat) for s in report.steps] == [(two, "owner"), (two, "reviewer")]
    assert report.stops[two] is Stop.AWAITING_APPROVAL
    assert not decisions_by_agents(engine, one, two, gate.id)
    assert {(e.details["seat"], e.details["runtime"]) for e in loop_entries(engine)} == {
        ("owner", "mock-llm"), ("reviewer", "test-seat")}


# --- 9. The laws -----------------------------------------------------------------------------------------


def test_the_loop_names_no_seat_stage_or_tool_and_keeps_the_import_laws(nirmaan_org):
    src = Path(__file__).parent.parent / "src" / "nirmaan"
    text = (src / "runtime" / "loop.py").read_text()
    stages = {s.id for w in nirmaan_org.workflows.values() for s in w.stages}
    names = {*nirmaan_org.tools, *nirmaan_org.roles, *nirmaan_org.gates, *nirmaan_org.capabilities}
    quoted = set(re.findall(r"[\"']([A-Za-z0-9_.\-]+)[\"']", text))
    assert not quoted & (stages | names)
    tree = ast.parse(text)
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m.split(".")[0] in ("veritriage", "anthropic") for m in imported)
    assert all(m.startswith(("nirmaan.", "__future__", "dataclasses", "enum", "typing")) for m in imported), imported


def test_every_loop_step_is_audited_as_the_seat_that_acted(axi_spec):
    engine, seat = axi_spec
    report = loop(engine, ModelRuntime(Seat(spec(SPEC_V1))), ModelRuntime(Seat(verdict("approve", "Fine."))), seat)
    entries = loop_entries(engine)
    assert len(entries) == len(report.steps) == 2
    task = engine.task(seat)
    owner_entry, reviewer_entry = entries
    assert owner_entry.subject == seat and owner_entry.actor.endswith(f"@{task.owner}")
    assert reviewer_entry.actor.endswith(f"@{task.reviewer}")
    assert reviewer_entry.details["review"] == report.steps[1].review
    assert all(e.details["step"] == n for n, e in enumerate(entries, 1))
    assert all(e.actor_kind is ActorKind.AI_AGENT for e in entries)

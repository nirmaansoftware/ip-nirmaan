"""Milestone 52: runtime and loop fixes (docs/RUNTIME_LOOP_FIXES.md).

Each test was written first, from an audit probe, and failed on main:

* C1: a task with no review whose evidence the submission does not meet made
  ``drive`` resubmit until the call budget was gone. Now it is a refused
  attempt, bounded by the attempt limit, and escalates when that is spent.
* H2: a malformed or ungroundable model answer raised out of the whole loop,
  and the CLI exited without saving. Now it is a refused attempt; the CLI saves
  before it reports an error; the first stage's prompt has a citable record.
* H3: ``drive --runtime mock-llm`` on a fresh project now does what its dry run
  says: owner, reviewer, then a stop for a person's approval.
* Evidence binding: a passing run from a refused attempt backs nothing later.
* M5: a person resolving a repair-budget escalation grants a fresh budget.
* M6: only data saved before M48 turns a max_/min_ parameter into a bound.
* M4: a requirement's ``inputs`` clause is honored by every reader.
* L1, L4, L5, and the gate overrides.

No test calls a model API; the one real-tool test is gated with ``needs``.
"""

from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from laws import needs
from nirmaan_helpers import agent, drive, human, tid

from nirmaan.company import builder
from nirmaan.company.workflows import REVIEWED, ran, rv, st
from nirmaan.models import (
    Condition,
    EvidenceKind,
    EvidenceRequirement,
    IntentRule,
    TaskKind,
    TaskStatus,
    Verdict,
    WorkflowTemplate,
)
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import register_extension
from nirmaan.registry import Registry
from nirmaan.runtime import (
    Completion,
    MockLLM,
    ModelRuntime,
    ResultStatus,
    ScriptedRuntime,
    Stop,
    WorkResult,
    assemble,
    loop,
    register_runtime,
    render_work_prompt,
    run_task,
)
from nirmaan.runtime.tools import ToolBroker
from nirmaan.work import PolicyViolationError, ProjectStore, WorkError
from nirmaan.work.policy import unsatisfied_requirements

FIXTURES = Path(__file__).parent / "fixtures"
COUNTER = FIXTURES / "rtl" / "counter.v"
AXI_BLOCK = "Create an AXI4-Lite register block."
BRIDGE = "Create a 4-port AXI-to-NoC bridge."
CLOCK = lambda: datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)  # noqa: E731
LINT_REPORT = {"kind": "lint_report", "title": "Lint report"}


@pytest.fixture()
def probe(registries):
    """A throwaway workflow, added as data in the test's registry scope: two review-less stages and a reviewed one."""

    @register_extension("m52-probe")
    def _ext(b):
        b.add(IntentRule(intent="m52_probe", patterns=(r"\bm52 probe\b",), priority=1),
              WorkflowTemplate(id="m52-probe", name="M52 probe", description="probe", intents=("m52_probe",), stages=(
                  st("empty", "No evidence, no review", "Debug", "rtl.impact", outputs=("impact_analysis",)),
                  st("linta", "Lint A", "RTL", "rtl.lint", outputs=("lint_report",),
                     evidence=(ran("Lint run", "lint.run"),)),
                  st("rev", "Reviewed lint", "RTL", "rtl.lint", review=rv("rtl.review"), outputs=("lint_report",),
                     evidence=(REVIEWED,)),
              )))

    org = builder().build()
    return Orchestrator(org, clock=CLOCK).plan("Run the m52 probe.")


def answer(**fields) -> str:
    return json.dumps({"uncertainty": 0.2, "artifacts": [], "tool_runs": [], "claims": [], **fields})


def attempts_of(engine, task_id: str) -> list:
    return sorted((a for a in engine.state.attempts.values() if a.task == task_id), key=lambda a: a.number)


# --- C1: a review-less submission that misses its evidence is a refused attempt -------------------


def test_unmet_evidence_on_a_task_with_no_review_escalates_instead_of_resubmitting(probe):
    engine = probe
    seat = tid(engine, "linta")
    llm = MockLLM()
    report = loop(engine, ModelRuntime(llm, "mock-llm"), task_id=seat, max_calls=20)

    assert [(s.status, s.calls) for s in report.steps] == [("refused", 1), ("needs_escalation", 0)]
    assert report.stops == {seat: Stop.ESCALATED} and len(llm.calls) == 1 and report.calls == 1
    task = engine.task(seat)
    assert task.status is TaskStatus.ESCALATED and task.artifacts == ()
    (attempt,) = attempts_of(engine, seat)
    assert "'Lint run' is not met" in attempt.refusal and attempt.artifacts
    assert "1 of 1 attempts" in engine.state.escalations[report.steps[-1].escalation].reason


@needs("verilator")  # the lint tool must be executable for its failed run to exist
def test_the_attempt_limit_bounds_the_retries_and_the_repair_prompt_cites_the_failed_run(probe):
    engine = probe
    seat = tid(engine, "linta")
    llm = MockLLM()
    report = loop(engine, ModelRuntime(llm, "mock-llm"), task_id=seat, max_calls=20, attempts=3)

    assert [(s.status, s.calls) for s in report.steps] == [("refused", 3), ("needs_escalation", 0)]
    assert len(llm.calls) == 3 and len(engine.state.tool_runs) == 3
    first = attempts_of(engine, seat)[0]
    tokens = {c.token for c in llm.calls[1].citations}
    assert f"[run:{first.tool_runs[0]}]" in tokens  # the refused attempt's failed run stays citable
    assert any(t.startswith("[evidence:") for t in tokens)
    assert "Repair: your previous attempt 1 was refused" in llm.calls[1].render()


def test_a_final_submission_with_no_review_completes_or_is_refused(probe):
    engine = probe
    seat = tid(engine, "linta")
    owner = agent(engine.task(seat).owner)
    engine.start(seat, owner)
    with pytest.raises(PolicyViolationError, match="'Lint run' is not met"):
        engine.submit(seat, owner, [LINT_REPORT], final=True)
    assert engine.task(seat).artifacts == ()
    # A person may still submit first and record the evidence after (the two-step flow): not final.
    engine.submit(seat, owner, [LINT_REPORT])
    assert engine.task(seat).status is TaskStatus.IN_PROGRESS and len(engine.task(seat).artifacts) == 1


# --- H2: a bad answer is a refused attempt, never an abort ------------------------------------------


@pytest.mark.parametrize("reply, principle", [
    (lambda cite: json.dumps({"artifacts": [], "notes": "forgot uncertainty"}), "P3"),
    (lambda cite: answer(tool_runs=["run-0042"], artifacts=[
        {"kind": "impact_analysis", "title": "x", "summary": f"From {cite}."}]), "P5"),
])
def test_a_malformed_answer_is_a_refused_attempt_not_an_abort(probe, reply, principle):
    engine = probe
    seat = tid(engine, "empty")
    cite = f"[requirement:{engine.state.project.requirement.id}]"
    report = loop(engine, ModelRuntime(MockLLM([reply(cite)]), "mock-llm"), task_id=seat, max_calls=5)

    assert [(s.status, s.calls) for s in report.steps] == [("refused", 1), ("needs_escalation", 0)]
    assert report.stops == {seat: Stop.ESCALATED}
    (attempt,) = attempts_of(engine, seat)
    assert f"[{principle}]" in attempt.refusal
    assert len([c for c in engine.state.model_calls.values() if c.task == seat]) == 1


class Cite:
    """A model answering with one artifact, citing the first token its prompt declares (or nothing)."""

    name = "cite"

    def __init__(self, cite: bool = True) -> None:
        self.cite = cite
        self.calls: list = []

    def complete(self, prompt) -> Completion:
        self.calls.append(prompt)
        token = prompt.citations[0].token if self.cite and prompt.citations else ""
        if prompt.mode == "review":
            return Completion(json.dumps({"verdict": "approve", "uncertainty": 0.1,
                                          "comments": f"It follows from {token}."}), self.name)
        return Completion(answer(artifacts=[{"kind": out, "title": out, "summary": f"From {token}."}
                                            for out in prompt.outputs]), self.name)


def test_the_first_stage_can_ground_its_answer_in_the_requirement(nirmaan_org):
    engine = Orchestrator(nirmaan_org, clock=CLOCK).plan(AXI_BLOCK)
    first = tid(engine, "requirements")
    prompt = render_work_prompt(assemble(engine, first), "work")
    requirement = [c for c in prompt.citations if c.kind == "requirement"]
    assert [c.target for c in requirement] == [engine.state.project.requirement.id]
    assert engine.state.project.requirement.text in requirement[0].label

    report = run_task(engine, first, ModelRuntime(Cite()))
    assert report.status is ResultStatus.SUBMITTED, report.detail
    assert engine.task(first).status is TaskStatus.IN_REVIEW


def test_an_uncited_first_answer_is_refused_and_the_loop_goes_on(nirmaan_org):
    engine = Orchestrator(nirmaan_org, clock=CLOCK).plan(AXI_BLOCK)
    first = tid(engine, "requirements")
    report = loop(engine, ModelRuntime(Cite(cite=False)), max_calls=5)
    assert report.stops[first] is Stop.ESCALATED
    (attempt,) = attempts_of(engine, first)
    assert "[P4]" in attempt.refusal and "dropped uncited artifacts" in report.steps[0].detail


def test_drive_saves_what_a_failed_step_did_before_it_reports_the_error(tmp_path, registries):
    @register_runtime("m52-broken")
    class Broken:
        runtime_id = "m52-broken"

        def accepts(self, packet):
            return True

        def execute(self, packet, tools):
            raise WorkError("the seat broke")

    from nirmaan.cli import app

    runner = CliRunner()
    planned = runner.invoke(app, ["plan", AXI_BLOCK, "--root", str(tmp_path)])
    assert planned.exit_code == 0, planned.output
    project = ProjectStore(tmp_path).list()[0].project.id
    result = runner.invoke(app, ["drive", project, "requirements", "--runtime", "m52-broken", "--root", str(tmp_path)])
    assert result.exit_code != 0 and "the seat broke" in result.output
    saved = ProjectStore(tmp_path).load(project)
    assert saved.tasks[f"{project}:requirements"].status is TaskStatus.IN_PROGRESS
    assert "task.start" in [e.action for e in saved.audit]


# --- H3: the mock runtime drives a fresh project as its dry run says -------------------------------


def test_drive_with_the_mock_runtime_on_a_fresh_project_stops_for_approval(tmp_path):
    from nirmaan.cli import app

    runner = CliRunner()
    assert runner.invoke(app, ["plan", AXI_BLOCK, "--root", str(tmp_path)]).exit_code == 0
    project = ProjectStore(tmp_path).list()[0].project.id
    dry = runner.invoke(app, ["drive", project, "--runtime", "mock-llm", "--dry-run", "--root", str(tmp_path)])
    assert f"{project}:requirements: then stop, awaiting_approval" in dry.output
    real = runner.invoke(app, ["drive", project, "--runtime", "mock-llm", "--max-calls", "40",
                               "--root", str(tmp_path)])
    assert real.exit_code == 0, real.output
    assert f"{project}:requirements: stopped, awaiting_approval" in real.output
    assert "needs_escalation" not in real.output


# --- Evidence is bound to the submission it was recorded for ---------------------------------------


@needs("verilator")
def test_a_passing_run_of_a_refused_attempt_backs_no_later_submission(probe, tmp_path):
    engine = probe
    seat = tid(engine, "linta")
    owner = agent(engine.task(seat).owner)
    engine.start(seat, owner)
    run, _ = ToolBroker(engine).invoke(owner, "lint.run", {"sources": str(COUNTER), "top": "counter",
                                                           "workdir": str(tmp_path)}, seat)
    assert run.succeeded, run.summary
    ev = engine.record_evidence(seat, owner, EvidenceKind.TOOL_RUN, run.summary, tool_run=run.id)
    attempt = engine.record_attempt(seat, owner, [LINT_REPORT], "refused for another reason", (run.id,), (ev.id,))

    assert attempt.evidence == (ev.id,) and ev.id not in engine.task(seat).evidence
    engine.submit(seat, owner, [LINT_REPORT])
    assert engine.task(seat).status is TaskStatus.IN_PROGRESS
    assert unsatisfied_requirements(engine.state, engine.task(seat)) == ["Lint run"]
    again = engine.record_evidence(seat, owner, EvidenceKind.TOOL_RUN, "the same run, again", tool_run=run.id)
    assert not again.substantiated and engine.task(seat).status is TaskStatus.IN_PROGRESS


# --- M5: a person's resolution of a spent budget grants a fresh one --------------------------------


def test_resolving_a_spent_budget_lets_the_work_continue_once(probe):
    engine = probe
    seat = tid(engine, "rev")
    runtime = ScriptedRuntime(WorkResult(ResultStatus.SUBMITTED, uncertainty=0.1, artifacts=(LINT_REPORT,)))
    reviewer = agent(engine.task(seat).reviewer)
    assert run_task(engine, seat, runtime).status is ResultStatus.SUBMITTED
    engine.review(seat, reviewer, Verdict.REQUEST_CHANGES, "no")
    spent = run_task(engine, seat, runtime)
    assert spent.status is ResultStatus.NEEDS_ESCALATION
    esc = engine.state.escalations[spent.escalation]

    # An agent in the target seat may resolve it, but grants nothing: the next run escalates again.
    engine.resolve_escalation(esc.id, agent(esc.target_role), "carry on")
    again = run_task(engine, seat, runtime)
    assert again.status is ResultStatus.NEEDS_ESCALATION
    engine.resolve_escalation(again.escalation, human(esc.target_role), "go ahead, one more round")
    assert run_task(engine, seat, runtime).status is ResultStatus.SUBMITTED
    # The grant is one fresh budget, not an unlimited one.
    engine.review(seat, reviewer, Verdict.REQUEST_CHANGES, "still no")
    assert run_task(engine, seat, runtime).status is ResultStatus.NEEDS_ESCALATION


# --- M6: only old data turns max_/min_ parameters into bounds --------------------------------------


def test_a_real_max_input_stays_a_parameter():
    req = EvidenceRequirement(description="x", accepts=(EvidenceKind.TOOL_RUN,), tools=("dft.scan_insert",),
                              params=(("max_chain_length", "8"),))
    assert req.params == (("max_chain_length", "8"),) and req.bounds == ()


def test_a_project_saved_before_m48_still_reads_its_max_parameter_as_a_bound(tmp_path):
    old = FIXTURES / "projects" / "m28-tool-runs.json"
    project = json.loads(old.read_text())["project"]["id"]
    (tmp_path / "projects").mkdir()
    shutil.copy(old, tmp_path / "projects" / f"{project}.json")
    state = ProjectStore(tmp_path).load(project)
    (req,) = [r for r in state.tasks[f"{project}:rtl-fix"].evidence_requirements if r.tools == ("synth.run",)]
    assert [str(b) for b in req.bounds] == ["latches<=0"] and req.params == ()


# --- M4: an inputs clause on a requirement is honored -----------------------------------------------


def test_an_inputs_clause_on_a_requirement_is_honored(nirmaan_org):
    from nirmaan.runtime.model import _facts
    from nirmaan.applicability import applies
    from nirmaan.work.policy import run_facts

    engine = Orchestrator(nirmaan_org, clock=CLOCK).plan(AXI_BLOCK)
    first = tid(engine, "requirements")
    clause = (Condition(on="inputs", any_of=("register_map",)),)
    task = engine.task(first)
    assert not applies(clause, run_facts(engine.state, task, set()))
    assert not applies(clause, _facts(assemble(engine, first)))
    req = EvidenceRequirement(description="Checked against the register map", accepts=(EvidenceKind.TOOL_RUN,),
                              tools=("regmap.check",), when=clause)
    gated = task.model_copy(update={"evidence_requirements": (req,)})
    assert unsatisfied_requirements(engine.state, gated) == []


# --- L1: reading a registry while another thread removes entries ----------------------------------


def test_registry_values_are_read_from_a_snapshot():
    reg = Registry("m52.race")
    stop = threading.Event()

    def churn():
        i = 0
        while not stop.is_set():
            reg[f"k{i % 50}"] = i
            reg.pop(f"k{(i + 25) % 50}", None)
            i += 1

    worker = threading.Thread(target=churn, daemon=True)
    worker.start()
    errors = 0
    try:
        for _ in range(5000):
            try:
                list(reg.values())
                list(reg.items())
            except KeyError:
                errors += 1
    finally:
        stop.set()
        worker.join()
    assert errors == 0


# --- L4: preflight runs once per distinct tool and parameters ---------------------------------------


class Handle:
    """A tool handle that records what preflight asks for and runs nothing."""

    def __init__(self) -> None:
        self.invoked: list = []

    def invoke(self, tool, bounds=(), **params):
        from nirmaan.runtime.tools import ToolOutcome

        self.invoked.append((tool, tuple(sorted(params.items())), tuple(bounds)))
        return f"run-{len(self.invoked)}", ToolOutcome(succeeded=True, summary="ok")

    def declared(self, tool, inputs):
        return {}


def test_preflight_runs_each_distinct_tool_and_parameters(probe):
    engine = probe
    seat = tid(engine, "linta")
    packet = assemble(engine, seat)
    reqs = tuple(ran(f"Lint {n}", "lint.run", params=(("top", n),)) for n in ("a", "b", "a"))
    packet = packet.model_copy(update={"task": packet.task.model_copy(update={"evidence_requirements": reqs})})
    handle = Handle()
    notes = ModelRuntime(MockLLM())._preflight(packet, handle, {})
    assert [dict(p)["top"] for _, p, _ in handle.invoked] == ["a", "b"] and len(notes) == 2


# --- L5: upstream evidence is seen through gates ----------------------------------------------------


def test_upstream_evidence_is_seen_through_a_gate(nirmaan_org):
    engine = Orchestrator(nirmaan_org, clock=CLOCK).plan(BRIDGE)
    behind = next(t for t in engine.state.tasks.values()
                  if any(engine.task(d).kind is TaskKind.GATE for d in t.depends_on))
    drive(engine, until=behind.id)
    gated = {a.id.split("#")[0] for a in assemble(engine, behind.id).task.upstream_artifacts}
    seen = {e.task for e in assemble(engine, behind.id).task.evidence}
    assert gated and gated <= seen


# --- Gate overrides: an option that cannot let an agent sign is gone ---------------------------------


def test_no_option_claims_to_let_an_agent_sign_a_gate(tmp_path):
    from nirmaan.cli import app
    from nirmaan.mcp.tools import list_tools

    result = CliRunner().invoke(app, ["plan", AXI_BLOCK, "--auto-gate", "gate.requirements", "--root", str(tmp_path)])
    assert result.exit_code == 2 and not (tmp_path / "projects").exists()  # a usage error: no such option
    plan_project = next(s for s in list_tools() if s.name == "plan_project")
    assert "auto_gates" not in plan_project.input_schema["properties"]

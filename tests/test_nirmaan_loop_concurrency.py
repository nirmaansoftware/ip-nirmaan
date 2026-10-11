"""Milestone 36: concurrent tasks and a project wide call budget in the unattended loop.

``nirmaan drive --jobs N`` works the independent tasks that are ready at once.
Model calls run in parallel; every read and write of project state happens in
one writer's turn, and turns go round the batch in plan order, so the final
state and the audit chain do not depend on ``--jobs``. A person sets the
project's call budget (``nirmaan budget``); it is recorded on the trail, read
back by every invocation, spent as M31 records model calls, and stops the loop
with an audited reason. No test calls a model API.
"""

from __future__ import annotations

import ast
import re
import threading
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import agent, human

from nirmaan.models import ActorKind, ReviewState, TaskKind, TaskStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import (
    Completion,
    MockLLM,
    ModelRuntime,
    Stop,
    loop,
    plan_loop,
    register_runtime,
    unregister_runtime,
)
from nirmaan.work import ProjectStore, TaskEngine
from nirmaan.work.budget import budget, spend
from nirmaan.work.engine import AuthorityError

#: What the loop may never do: approve, sign, complete, resolve, or otherwise decide for a person.
DECISIONS = ("task.approve", "gate.approve", "escalation.resolve", "task.unblock", "task.cancel")


# --- A workflow of independent stages, added as data in the test --------------------------------


@pytest.fixture()
def fan_org(registries):
    """Three independent stages (a, b, c), one behind a (d), and one behind b's human gate (e).

    Every stage reads the project status as evidence, so each task runs a real tool (``status.read``,
    which reads state) before its model call: run IDs and summaries depend on the order of writes.
    """
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
    from nirmaan.org import register_extension

    @register_extension("test-loop-fan-out")  # in the test's own registry scope (M49): no unregister
    def fan(b):
        read = EvidenceRequirement(description="Project status read", accepts=(EvidenceKind.TOOL_RUN,),
                                   tools=("status.read",))
        review = ReviewRequirement(capability="req.review")

        def stage(stage_id: str, **kw) -> StageTemplate:
            return StageTemplate(id=stage_id, title=stage_id, phase="Requirements", capability="req.analyze",
                                 criticality=Criticality.MEDIUM, outputs=("requirements_spec",), evidence=(read,),
                                 **kw)

        b.add(
            IntentRule(intent="fan_out", patterns=(r"\bfan out\b",), priority=5),
            WorkflowTemplate(
                id="fan-out", name="Fan out", description="Independent stages.", intents=("fan_out",),
                stages=(stage("fan-a"), stage("fan-b", review=review, gate="gate.requirements"),
                        stage("fan-c", review=review), stage("fan-d", depends_on=("fan-a",)),
                        stage("fan-e", review=review, depends_on=("fan-b",))),
            ),
        )

    return builder().build()


def plan(org, clock) -> TaskEngine:
    return Orchestrator(org, clock=clock).plan("Fan out a timer.", gate_overrides={"gate.requirements": True})


def ids(engine: TaskEngine) -> dict[str, str]:
    return {s: f"{engine.state.project.id}:fan-{s}" for s in "abcde"}


class Instrument:
    """A model that takes a while, and records which task each call served and when."""

    name = "mock-llm"

    def __init__(self, engine: TaskEngine, delay: float = 0.15, crash_on: str | None = None) -> None:
        self.engine, self.delay, self.crash_on = engine, delay, crash_on
        self.inner = MockLLM()
        self.lock = threading.Lock()
        self.in_flight = self.most = self.answered = 0
        self.spans: list[tuple[str, str, float, float]] = []

    def task_of(self, prompt) -> str:
        run = max(c.target for c in prompt.citations if c.kind == "run")  # its own run is the newest it cites
        return self.engine.state.tool_runs[run].task

    def complete(self, prompt) -> Completion:
        task = self.task_of(prompt)
        with self.lock:
            self.in_flight += 1
            self.most = max(self.most, self.in_flight)
        start = time.monotonic()
        try:
            time.sleep(self.delay)
            if self.crash_on and task.endswith(self.crash_on) and prompt.mode == "review":
                self.crash_on = None
                raise RuntimeError("connection lost")
            reply = self.inner.complete(prompt)
            with self.lock:
                self.answered += 1
            return reply
        finally:
            with self.lock:
                self.in_flight -= 1
                self.spans.append((task, prompt.mode, start, time.monotonic()))


def decisions_by_agents(engine: TaskEngine) -> list:
    return [e for e in engine.state.audit if e.action in DECISIONS and e.actor_kind is ActorKind.AI_AGENT]


def cli(*args: str):
    from nirmaan.cli import app

    return CliRunner().invoke(app, list(args))


# --- 1. The result does not depend on --jobs ----------------------------------------------------------


def test_jobs_one_and_four_give_the_same_state_and_the_same_audit_chain(fan_org, fixed_clock):
    finals = {}
    for jobs in (1, 4):
        engine = plan(fan_org, fixed_clock)
        report = loop(engine, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()), jobs=jobs)
        t = ids(engine)
        assert report.stops[t["b"]] is Stop.AWAITING_APPROVAL and report.stops[t["c"]] is Stop.AWAITING_APPROVAL
        assert engine.task(t["d"]).status is TaskStatus.COMPLETED
        finals[jobs] = (engine.state.model_dump(mode="json"), [e.hash for e in engine.state.audit],
                        [(s.number, s.task, s.seat, s.status) for s in report.steps])
    assert finals[1] == finals[4]
    state = finals[4][0]
    assert len(state["tool_runs"]) == 4 and len(state["model_calls"]) == 6


def test_the_turns_interleave_tasks_in_plan_order(fan_org, fixed_clock):
    """Concurrency is visible in the trail: the batch's first steps come before any task's second."""
    engine = plan(fan_org, fixed_clock)
    t = ids(engine)
    report = loop(engine, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()), jobs=2)
    first = [(s.task, s.seat) for s in report.steps[:3]]
    assert first == [(t["a"], "owner"), (t["b"], "owner"), (t["c"], "owner")]
    assert [s.task for s in report.steps].index(t["d"]) > 2  # d became ready in the batch; it runs in the next


# --- 2. Independent tasks overlap; dependent ones never do ----------------------------------------------


@pytest.mark.parametrize("jobs, most", [(1, 1), (4, 3)])
def test_independent_tasks_overlap_up_to_jobs_and_dependent_tasks_never_do(fan_org, fixed_clock, jobs, most):
    engine = plan(fan_org, fixed_clock)
    t = ids(engine)
    llm = Instrument(engine)
    report = loop(engine, ModelRuntime(llm), ModelRuntime(llm), jobs=jobs)
    assert report.calls == 6 and llm.answered == 6
    assert llm.most == most

    spans = {task: [(s, e) for who, _, s, e in llm.spans if who == task] for task in t.values()}
    assert spans[t["d"]] and min(s for s, _ in spans[t["d"]]) >= max(e for _, e in spans[t["a"]])
    assert not spans[t["e"]]  # behind a human gate


# --- 3. The project budget ------------------------------------------------------------------------------


def test_the_budget_persists_across_invocations_and_stops_the_loop(fan_org, fixed_clock, tmp_path):
    engine = plan(fan_org, fixed_clock)
    t = ids(engine)
    person = human(engine.task(t["b"]).approver)
    engine.set_budget(person, calls=3, cost_usd=None, reason="a first allowance")
    store = ProjectStore(tmp_path)
    store.save(engine.state)
    project = engine.state.project.id

    first = TaskEngine(fan_org, store.load(project), clock=fixed_clock)
    report = loop(first, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()), jobs=4,
                  on_step=lambda e: store.save(e.state))
    assert spend(first.state).calls == report.calls == 3
    assert Stop.PROJECT_BUDGET in report.stops.values()
    stops = [e for e in first.state.audit if e.action == "loop.stop"]
    assert stops and all(e.details["stop"] == "project_budget" and e.details["budget_calls"] == 3 for e in stops)
    assert all(e.actor_kind is ActorKind.AI_AGENT for e in stops)
    store.save(first.state)

    again = TaskEngine(fan_org, store.load(project), clock=fixed_clock)  # a later invocation, from state alone
    llm = MockLLM()
    report = loop(again, ModelRuntime(llm), ModelRuntime(llm), jobs=4)
    assert report.steps == [] and llm.calls == [] and Stop.PROJECT_BUDGET in report.stops.values()
    assert spend(again.state).calls == 3


def test_raising_the_budget_is_a_persons_audited_decision_and_the_loop_continues(fan_org, fixed_clock):
    engine = plan(fan_org, fixed_clock)
    t = ids(engine)
    person = human(engine.task(t["b"]).approver)
    engine.set_budget(person, calls=2, cost_usd=None, reason="a first allowance")
    loop(engine, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()), jobs=4)
    assert spend(engine.state).calls == 2

    before = len(engine.state.audit)
    with pytest.raises(AuthorityError):
        engine.set_budget(agent(engine.task(t["b"]).owner), calls=100, cost_usd=None, reason="more, please")
    assert len(engine.state.audit) == before and budget(engine.state).calls == 2

    engine.set_budget(person, calls=10, cost_usd=None, reason="phase two")
    entry = engine.state.audit[-1]
    assert entry.action == "budget.set" and entry.actor_kind is ActorKind.HUMAN and entry.reason == "phase two"
    assert entry.details["calls"] == 10 and entry.details["previous_calls"] == 2
    assert budget(engine.state).calls == 10 and budget(engine.state).set_by == person.label

    report = loop(engine, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()), jobs=4)
    assert Stop.PROJECT_BUDGET not in report.stops.values()
    assert spend(engine.state).calls == 6
    assert engine.task(t["d"]).status is TaskStatus.COMPLETED


def test_a_cost_limit_never_treats_an_unknown_cost_as_free(fan_org, fixed_clock):
    engine = plan(fan_org, fixed_clock)
    person = human(engine.task(ids(engine)["b"]).approver)
    engine.set_budget(person, calls=None, cost_usd=5.0, reason="spend cap")
    unpriced = MockLLM(model="a-model-with-no-profile")
    report = loop(engine, ModelRuntime(unpriced), ModelRuntime(unpriced), jobs=4)
    assert spend(engine.state).unknown_cost >= 1
    assert Stop.PROJECT_BUDGET in report.stops.values()
    reasons = {e.reason for e in engine.state.audit if e.action == "loop.stop"}
    assert any("unknown cost" in r for r in reasons)


def test_a_budget_is_checked_before_a_step_and_never_exceeded(fan_org, fixed_clock):
    """With attempts of 2 an owner step may make 2 calls; a budget of 3 never lets three such steps start."""
    engine = plan(fan_org, fixed_clock)
    engine.set_budget(human(engine.task(ids(engine)["b"]).approver), calls=3, cost_usd=None, reason="tight")
    report = loop(engine, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()), jobs=4, attempts=2)
    assert spend(engine.state).calls <= 3 and report.calls <= 3


# --- 4. Resuming after an interruption mid-batch ------------------------------------------------------


def test_an_interruption_mid_batch_loses_no_call_and_resumes_from_state(fan_org, fixed_clock):
    engine = plan(fan_org, fixed_clock)
    t = ids(engine)
    llm = Instrument(engine, delay=0.05, crash_on="fan-c")
    saved = []
    with pytest.raises(RuntimeError, match="connection lost"):
        loop(engine, ModelRuntime(llm), ModelRuntime(llm), jobs=4, on_step=lambda e: saved.append(e.state))
    state = saved[-1]
    assert len(state.model_calls) == llm.answered  # every answered call is recorded and saved
    assert state.tasks[t["c"]].status is TaskStatus.IN_REVIEW

    resumed = TaskEngine(fan_org, state, clock=fixed_clock)
    again = Instrument(resumed, delay=0.0)
    report = loop(resumed, ModelRuntime(again), ModelRuntime(again), jobs=4)
    assert report.stops[t["b"]] is Stop.AWAITING_APPROVAL and report.stops[t["c"]] is Stop.AWAITING_APPROVAL
    assert resumed.task(t["d"]).status is TaskStatus.COMPLETED
    assert len(resumed.state.model_calls) == llm.answered + again.answered == 6  # nothing double counted
    owners = [e.subject for e in resumed.state.audit if e.action == "loop.step" and e.details["seat"] == "owner"]
    assert sorted(owners) == sorted([t["a"], t["b"], t["c"], t["d"]])  # no task was worked twice


# --- 5. Human gates are never crossed -----------------------------------------------------------------


@pytest.mark.parametrize("jobs", [1, 4])
def test_human_gates_are_never_crossed_at_any_jobs(fan_org, fixed_clock, jobs):
    engine = plan(fan_org, fixed_clock)
    t = ids(engine)
    loop(engine, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()), jobs=jobs)
    gate = engine.task(f"{t['b']}.gate")
    assert gate.kind is TaskKind.GATE and gate.status is TaskStatus.PLANNED
    assert engine.task(t["b"]).review_state is ReviewState.PASSED
    engine.approve(t["b"], human(engine.task(t["b"]).approver), "agreed")
    assert engine.task(gate.id).status is TaskStatus.READY

    report = loop(engine, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()), jobs=jobs)
    assert report.stops[gate.id] is Stop.AWAITING_GATE and report.steps == []
    assert engine.task(t["e"]).status is TaskStatus.PLANNED
    assert not decisions_by_agents(engine)


# --- 6. Dry run, and the budget command -------------------------------------------------------------


def test_the_budget_command_records_a_person_and_dry_run_shows_the_batch_and_the_budget(
        fan_org, fixed_clock, tmp_path, monkeypatch):
    import nirmaan.cli as cli_module

    engine = plan(fan_org, fixed_clock)
    t = ids(engine)
    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    project = engine.state.project.id
    monkeypatch.setattr(cli_module, "_load", lambda p, r: TaskEngine(fan_org, ProjectStore(r).load(p),
                                                                     clock=fixed_clock))

    approver = engine.task(t["b"]).approver
    refused = cli("budget", project, "--calls", "2", "--as", approver, "--root", str(root))
    assert refused.exit_code != 0 and "reason" in refused.output
    result = cli("budget", project, "--calls", "2", "--as", approver, "--reason", "trial", "--root", str(root))
    assert result.exit_code == 0, result.output
    state = ProjectStore(root).load(project)
    assert budget(state).calls == 2 and state.audit[-1].actor_kind is ActorKind.HUMAN
    shown = cli("budget", project, "--root", str(root))
    assert "calls: 0 of 2 spent" in shown.output

    saved = state.model_dump(mode="json")
    dry = cli("drive", project, "--runtime", "mock-llm", "--jobs", "4", "--dry-run", "--root", str(root))
    assert dry.exit_code == 0, dry.output
    assert f"concurrently: {t['a']}, {t['b']}, {t['c']} (up to 4 calls in flight)" in dry.output
    assert "project budget: 0 of 2 calls spent, 2 left" in dry.output and "does not fit" in dry.output
    assert ProjectStore(root).load(project).model_dump(mode="json") == saved

    plan_ = plan_loop(engine, "mock-llm", jobs=4)
    assert plan_.concurrent == (t["a"], t["b"], t["c"])


# --- 7. Crown jewel: a new runtime and a new workflow, concurrent with no core changes ---------------


def test_a_new_runtime_on_a_new_workflow_runs_concurrently_with_no_core_changes(fan_org, fixed_clock, tmp_path,
                                                                                 monkeypatch):
    """A runtime written here gives the turn up through the public hook; the CLI drives it with --jobs."""
    import nirmaan.cli as cli_module
    from nirmaan.models import Verdict
    from nirmaan.runtime import ResultStatus, ReviewResult, WorkResult
    from nirmaan.runtime.writer import outside_writer

    seen = {"in_flight": 0, "most": 0}
    lock = threading.Lock()

    def think() -> None:
        with outside_writer():  # the hook a runtime puts around work that touches no project state
            with lock:
                seen["in_flight"] += 1
                seen["most"] = max(seen["most"], seen["in_flight"])
            time.sleep(0.1)
            with lock:
                seen["in_flight"] -= 1

    class Slow:
        runtime_id = "test-slow"

        def accepts(self, packet) -> bool:
            return True

        def execute(self, packet, tools) -> WorkResult:
            run, _ = tools.invoke("status.read")  # inside the turn: the broker records it
            think()
            notes = tuple({"kind": k, "title": f"{k} note"} for k in packet.task.expected_outputs)
            return WorkResult(ResultStatus.SUBMITTED, uncertainty=0.2, artifacts=notes, tool_runs=(run,))

        def review(self, packet) -> ReviewResult:
            think()
            return ReviewResult(Verdict.APPROVE, "judged on the recorded status read", uncertainty=0.2)

    register_runtime("test-slow")(Slow)
    try:
        engine = plan(fan_org, fixed_clock)
        root = tmp_path / "store"
        ProjectStore(root).save(engine.state)
        project = engine.state.project.id
        monkeypatch.setattr(cli_module, "_load", lambda p, r: TaskEngine(fan_org, ProjectStore(r).load(p),
                                                                         clock=fixed_clock))
        result = cli("drive", project, "--runtime", "test-slow", "--jobs", "3", "--root", str(root))
        assert result.exit_code == 0, result.output
    finally:
        unregister_runtime("test-slow")
    assert seen["most"] == 3
    state = ProjectStore(root).load(project)
    t = ids(engine)
    assert state.tasks[t["d"]].status is TaskStatus.COMPLETED
    assert state.tasks[t["b"]].review_state is ReviewState.PASSED
    assert state.tasks[t["e"]].status is TaskStatus.PLANNED


# --- 8. The laws ----------------------------------------------------------------------------------------


def test_the_writer_names_nothing_and_keeps_the_import_laws(nirmaan_org):
    src = Path(__file__).parent.parent / "src" / "nirmaan"
    stages = {s.id for w in nirmaan_org.workflows.values() for s in w.stages}
    names = {*nirmaan_org.tools, *nirmaan_org.roles, *nirmaan_org.gates, *nirmaan_org.capabilities}
    for path, allowed in ((src / "runtime" / "writer.py", ("__future__", "contextlib", "copy", "threading", "typing")),
                          (src / "work" / "budget.py", ("__future__", "dataclasses", "nirmaan.models"))):
        text = path.read_text()
        quoted = set(re.findall(r"[\"']([A-Za-z0-9_.\-]+)[\"']", text))
        assert not quoted & (stages | names), path
        tree = ast.parse(text)
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert all(m.startswith(allowed) for m in imported), (path, imported)
    loop_text = (src / "runtime" / "loop.py").read_text()
    assert "threading" not in loop_text and "HUMAN" not in loop_text

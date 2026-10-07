"""The unattended owner and reviewer loop (M29): ``nirmaan drive``.

The loop holds two seats of a task, and only two: its owner (``run_task``, with
M26's attempts and M27's limits) and its planned reviewer (``review_task``,
where P6 is checked before the runtime is asked anything). It runs them in
turn until the task reaches something the loop may not do: an approval or a
gate that a person gives, an escalation, a block, or a decline. It never
approves, signs, completes, resolves, or cancels anything.

Each next step is a function of the task's state alone, so an interrupted loop
resumes by being run again. Every step is audited (``loop.step``), and a step
starts only if its worst case fits the call budget. With no task named, the
loop works the plan in dependency order and stops at every gate. It names no
seat, stage, or tool: who acts comes from the task's ``owner`` and
``reviewer``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from nirmaan.models import Actor, ActorKind, ReviewState, TaskKind, TaskStatus
from nirmaan.runtime.base import (
    AgentRuntime,
    ResultStatus,
    RunReport,
    _spent,
    exhausted,
    limits,
    review_task,
    run_task,
)
from nirmaan.work.engine import TaskEngine, WorkError

OWNER, REVIEWER = "owner", "reviewer"
_OWNER_STATES = (TaskStatus.READY, TaskStatus.CHANGES_REQUESTED, TaskStatus.IN_PROGRESS)
_DONE_STATES = (TaskStatus.APPROVED, TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED)


class Stop(str, Enum):
    """Why the loop stopped working a task."""

    #: The review passed; the approver, a person, decides.
    AWAITING_APPROVAL = "awaiting_approval"
    #: A gate is ready; the loop never signs one.
    AWAITING_GATE = "awaiting_gate"
    #: Reviews conflict; a manager settles them (P7).
    CONFLICTED = "conflicted"
    ESCALATED = "escalated"
    BLOCKED = "blocked"
    DECLINED = "declined"
    #: The engine refused the submission and asking again would not escalate.
    REFUSED = "refused"
    #: The next step's worst case does not fit what is left of the call budget.
    BUDGET = "budget"
    #: Upstream work is not done.
    WAITING = "waiting"
    DONE = "done"


@dataclass(frozen=True)
class LoopStep:
    number: int
    task: str
    seat: str
    role: str
    runtime: str
    status: str
    calls: int
    detail: str = ""
    review: str | None = None
    escalation: str | None = None


@dataclass(frozen=True)
class PlannedStep:
    task: str
    seat: str
    role: str
    runtime: str
    round: int
    rounds: int
    calls: int


@dataclass
class LoopReport:
    budget: int
    shared_runtime: bool
    steps: list[LoopStep] = field(default_factory=list)
    stops: dict[str, Stop] = field(default_factory=dict)
    calls: int = 0


@dataclass
class LoopPlan:
    budget: int
    shared_runtime: bool
    steps: list[PlannedStep] = field(default_factory=list)
    stops: dict[str, Stop] = field(default_factory=dict)

    @property
    def calls(self) -> int:
        return sum(s.calls for s in self.steps)


def next_step(engine: TaskEngine, task_id: str) -> tuple[str | None, Stop | None]:
    """The seat that acts next on a task, or why nobody in the loop may. From state alone."""
    task = engine.task(task_id)
    status = task.status
    if task.kind is TaskKind.GATE:
        if status is TaskStatus.READY:
            return None, Stop.AWAITING_GATE
        return None, Stop.DONE if status in _DONE_STATES else Stop.WAITING
    if status in _OWNER_STATES:
        return OWNER, None
    if status is TaskStatus.IN_REVIEW:
        if task.review_state is ReviewState.PENDING:
            return REVIEWER, None
        return None, Stop.AWAITING_APPROVAL if task.review_state is ReviewState.PASSED else Stop.CONFLICTED
    if status is TaskStatus.ESCALATED:
        return None, Stop.ESCALATED
    if status is TaskStatus.BLOCKED:
        return None, Stop.BLOCKED
    return None, Stop.WAITING if status is TaskStatus.PLANNED else Stop.DONE


def owner_calls(engine: TaskEngine, task_id: str, attempts: int | None = None,
                review_rounds: int | None = None) -> int:
    """The most calls the owner seat's next run may make: none when it would escalate (M27)."""
    budget = limits(engine, task_id, attempts, review_rounds)
    if exhausted(engine, task_id, budget):
        return 0
    return budget.attempts - len(_spent(engine, task_id)[1])


def order(engine: TaskEngine) -> list[str]:
    """The project's work, decision, and gate tasks in a stable dependency order."""
    tasks = engine.state.tasks
    seen: set[str] = set()
    ordered: list[str] = []

    def visit(task_id: str) -> None:
        if task_id in seen:
            return
        seen.add(task_id)
        for dep in tasks[task_id].depends_on:
            if dep in tasks:
                visit(dep)
        ordered.append(task_id)

    for task_id in tasks:
        visit(task_id)
    return [t for t in ordered if tasks[t].kind in (TaskKind.WORK, TaskKind.DECISION, TaskKind.GATE)]


def _runtime_id(runtime: AgentRuntime) -> str:
    return getattr(runtime, "runtime_id", "runtime")


def loop(engine: TaskEngine, owner: AgentRuntime, reviewer: AgentRuntime | None = None,
         task_id: str | None = None, max_calls: int = 20, attempts: int | None = None,
         review_rounds: int | None = None, kind: ActorKind = ActorKind.AI_AGENT,
         on_step: Callable[[TaskEngine], None] | None = None) -> LoopReport:
    """Drive one task (or, with none named, every task in dependency order) until each stops.

    ``on_step`` is called after every step (the CLI saves the project there),
    so an interruption loses at most the step in flight.
    """
    if max_calls < 0:
        raise WorkError(f"the call budget must be at least 0, got {max_calls}")
    reviewer = reviewer or owner
    report = LoopReport(max_calls, _runtime_id(owner) == _runtime_id(reviewer))
    targets = [task_id] if task_id else order(engine)
    for target in targets:
        engine.task(target)  # an unknown task fails before anything runs
    while True:
        current = next((t for t in targets if t not in report.stops and next_step(engine, t)[0]), None)
        if current is None:
            break
        report.stops[current] = _drive(engine, current, owner, reviewer, report, attempts, review_rounds,
                                       kind, on_step)
        if report.stops[current] is Stop.BUDGET:
            break
    for target in targets:  # what is left waiting on people, or on upstream work
        stop = next_step(engine, target)[1]
        if target not in report.stops and stop is not None and (task_id or stop not in (Stop.WAITING, Stop.DONE)):
            report.stops[target] = stop
    return report


def _drive(engine: TaskEngine, task_id: str, owner: AgentRuntime, reviewer: AgentRuntime, report: LoopReport,
           attempts: int | None, review_rounds: int | None, kind: ActorKind,
           on_step: Callable[[TaskEngine], None] | None) -> Stop:
    while True:
        seat, stop = next_step(engine, task_id)
        if seat is None:
            return stop or Stop.DONE
        task = engine.task(task_id)
        worst = owner_calls(engine, task_id, attempts, review_rounds) if seat == OWNER else 1
        if worst > report.budget - report.calls:
            return Stop.BUDGET
        if seat == OWNER:
            runtime, role = owner, task.owner
            run = run_task(engine, task_id, owner, kind, attempts=attempts, review_rounds=review_rounds)
            calls = len(run.attempts)
        else:
            runtime, role = reviewer, task.reviewer
            run = review_task(engine, task_id, reviewer, kind=kind)
            calls = 1  # charged whether or not the runtime answered: at most one call
        report.calls += calls
        _record(engine, report, task_id, seat, role or "", runtime, kind, run, calls)
        if on_step is not None:
            on_step(engine)
        if run.status is ResultStatus.DECLINED:
            return Stop.DECLINED
        if run.status is ResultStatus.REFUSED and owner_calls(engine, task_id, attempts, review_rounds) > 0:
            return Stop.REFUSED  # asking again would ask the model again, not escalate


def _record(engine: TaskEngine, report: LoopReport, task_id: str, seat: str, role: str, runtime: AgentRuntime,
            kind: ActorKind, run: RunReport, calls: int) -> None:
    name = _runtime_id(runtime)
    step = LoopStep(len(report.steps) + 1, task_id, seat, role, name, run.status.value, calls, run.detail,
                    run.review, run.escalation)
    details: dict[str, Any] = {"step": step.number, "seat": seat, "runtime": name, "status": step.status,
                               "calls": calls, "review": run.review, "escalation": run.escalation,
                               "attempts": [a["attempt"] for a in run.attempts if a["attempt"]],
                               "tool_runs": list(run.tool_runs)}
    engine.record_step(task_id, Actor(role=role, kind=kind, name=name), f"{seat} step: {step.status}", details)
    report.steps.append(step)


def plan_loop(engine: TaskEngine, owner: str, reviewer: str | None = None, task_id: str | None = None,
              max_calls: int = 20, attempts: int | None = None, review_rounds: int | None = None) -> LoopPlan:
    """The worst case sequence of calls the loop would make from the current state. Changes nothing."""
    reviewer = reviewer or owner
    plan = LoopPlan(max_calls, owner == reviewer)
    targets = [task_id] if task_id else order(engine)
    for target in targets:
        seat, stop = next_step(engine, target)
        if seat is None:
            if task_id or stop not in (Stop.WAITING, Stop.DONE):
                plan.stops[target] = stop or Stop.DONE
            continue
        plan.stops[target] = _schedule(engine, target, seat, owner, reviewer, attempts, review_rounds, plan.steps)
    return plan


def _schedule(engine: TaskEngine, task_id: str, seat: str, owner: str, reviewer: str, attempts: int | None,
              review_rounds: int | None, steps: list[PlannedStep]) -> Stop:
    task = engine.task(task_id)
    budget = limits(engine, task_id, attempts, review_rounds)
    rounds = budget.review_rounds
    current = len(_spent(engine, task_id)[0]) + 1

    def add(who: str, number: int, calls: int) -> None:
        role, runtime = (task.owner, owner) if who == OWNER else (task.reviewer, reviewer)
        steps.append(PlannedStep(task_id, who, role or "", runtime, number, rounds, calls))

    if seat == OWNER:
        first = owner_calls(engine, task_id, attempts, review_rounds)
        add(OWNER, current, first)
        if first == 0:
            return Stop.ESCALATED
        if task.review_state is ReviewState.NOT_REQUIRED:
            return Stop.DONE
    add(REVIEWER, current, 1)
    while current < rounds:
        current += 1
        add(OWNER, current, budget.attempts)
        add(REVIEWER, current, 1)
    add(OWNER, current + 1, 0)  # a change request in the last round escalates, with no call
    return Stop.AWAITING_APPROVAL

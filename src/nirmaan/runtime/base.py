"""The agent runtime interface: where LLM workers attach, and cannot cheat.

An :class:`AgentRuntime` receives a :class:`WorkPacket` and a tool handle, and
returns a :class:`WorkResult`. It never touches project state. ``run_task``
applies the result through the task engine, so everything a runtime proposes
passes the same state machine, authority matrix, and constitution as a human:

* artifacts become EXECUTED, never more;
* evidence can only cite tool runs the broker actually recorded;
* unbacked statements are stored as CLAIM evidence, which satisfies nothing;
* uncertainty must be declared, and an escalation request is routed up the
  real chain rather than answered by the agent itself.

``NullRuntime`` (the default for every seat) declines honestly: no worker is
attached. ``ScriptedRuntime`` replays a fixed result, for tests and
simulations. Model-backed runtimes (M20) live in :mod:`nirmaan.runtime.model`.
A runtime is one class implementing ``accepts`` and ``execute`` (and, to sit
in a review seat, ``review``), registered with ``@register_runtime``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, NamedTuple, Protocol

from nirmaan.models import Actor, ActorKind, EscalationKind, EvidenceKind, TaskStatus, Verdict
from nirmaan.runtime.context import WorkPacket, assemble
from nirmaan.runtime.tools import ToolBroker, ToolOutcome
from nirmaan.work.engine import TaskEngine, WorkError
from nirmaan.work.policy import PolicyContext, PolicyEngine, PolicyViolationError


class ResultStatus(str, Enum):
    SUBMITTED = "submitted"
    NEEDS_ESCALATION = "needs_escalation"
    DECLINED = "declined"
    #: A check the work must pass cannot run here (e.g. its tool is not installed); the task is blocked.
    BLOCKED = "blocked"
    #: Set by ``run_task``, not a runtime: the engine refused the submission; the evidence stands.
    REFUSED = "refused"


@dataclass(frozen=True)
class EscalationRequest:
    kind: EscalationKind
    reason: str
    blocking_question: str
    attempted_actions: tuple[str, ...] = ()
    recommended_options: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkResult:
    status: ResultStatus
    uncertainty: float | None
    artifacts: tuple[dict[str, Any], ...] = ()
    tool_runs: tuple[str, ...] = ()
    claims: tuple[str, ...] = ()
    notes: str = ""
    outcome: str | None = None
    escalation: EscalationRequest | None = None


@dataclass(frozen=True)
class ReviewResult:
    """A reviewing runtime's verdict. ``None`` means no review is recorded."""

    verdict: Verdict | None
    comments: str = ""
    uncertainty: float | None = None
    notes: str = ""


class ToolHandle:
    """What a runtime gets instead of the broker: bound to one actor and task."""

    def __init__(self, broker: ToolBroker, actor: Actor, task_id: str) -> None:
        self._broker, self._actor, self._task = broker, actor, task_id

    def invoke(self, tool_id: str, **params: str) -> tuple[str, ToolOutcome]:
        run, outcome = self._broker.invoke(self._actor, tool_id, params, self._task)
        return run.id, outcome


class AgentRuntime(Protocol):
    runtime_id: str

    def accepts(self, packet: WorkPacket) -> bool: ...

    def execute(self, packet: WorkPacket, tools: ToolHandle) -> WorkResult: ...


_RUNTIMES: dict[str, Callable[[], AgentRuntime]] = {}


def register_runtime(runtime_id: str) -> Callable[[Callable[[], AgentRuntime]], Callable[[], AgentRuntime]]:
    def _register(factory):
        if runtime_id in _RUNTIMES and _RUNTIMES[runtime_id] is not factory:
            raise ValueError(f"Runtime {runtime_id!r} is already registered")
        _RUNTIMES[runtime_id] = factory
        return factory

    return _register


def unregister_runtime(runtime_id: str) -> None:
    _RUNTIMES.pop(runtime_id, None)


def get_runtime(runtime_id: str) -> AgentRuntime:
    try:
        return _RUNTIMES[runtime_id]()
    except KeyError:
        raise KeyError(f"Unknown runtime {runtime_id!r}. Registered: {', '.join(sorted(_RUNTIMES))}") from None


def available_runtimes() -> list[str]:
    return sorted(_RUNTIMES)


@register_runtime("unbound")
class NullRuntime:
    """No worker is attached to this seat. Says so; does nothing."""

    runtime_id = "unbound"

    def accepts(self, packet: WorkPacket) -> bool:
        return False

    def execute(self, packet: WorkPacket, tools: ToolHandle) -> WorkResult:
        return WorkResult(ResultStatus.DECLINED, uncertainty=1.0, notes="no runtime is bound to this role")


class ScriptedRuntime:
    """Replays a scripted result, optionally invoking real tools first."""

    runtime_id = "scripted"

    def __init__(self, result: WorkResult, tool_calls: tuple[tuple[str, dict[str, str]], ...] = ()) -> None:
        self._result, self._calls = result, tool_calls

    def accepts(self, packet: WorkPacket) -> bool:
        return True

    def execute(self, packet: WorkPacket, tools: ToolHandle) -> WorkResult:
        runs = tuple(tools.invoke(tool, **params)[0] for tool, params in self._calls)
        return WorkResult(
            status=self._result.status, uncertainty=self._result.uncertainty,
            artifacts=self._result.artifacts, tool_runs=(*runs, *self._result.tool_runs),
            claims=self._result.claims, notes=self._result.notes, outcome=self._result.outcome,
            escalation=self._result.escalation,
        )


@dataclass
class RunReport:
    task: str
    status: ResultStatus
    detail: str
    tool_runs: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    escalation: str | None = None
    review: str | None = None
    #: One entry per attempt (M26): number, status, detail, tool_runs, evidence, and the Attempt ID if refused.
    attempts: list[dict[str, Any]] = field(default_factory=list)


class Limits(NamedTuple):
    """A task's budget (M27): attempts per review round (M26), and review rounds."""

    attempts: int
    review_rounds: int


def limits(engine: TaskEngine, task_id: str, attempts: int | None = None,
           review_rounds: int | None = None) -> Limits:
    """Each limit from the override, else the task's workflow stage, else its capability, else 1."""
    task = engine.task(task_id)
    workflow = engine.org.workflows.get(task.workflow or "")
    stage = workflow.stage(task.stage) if workflow and task.stage else None
    capability = engine.org.capabilities.get(task.capability or "")
    chosen = []
    for name, override in (("max_attempts", attempts), ("max_review_rounds", review_rounds)):
        if override is not None and override < 1:
            raise WorkError(f"{name.removeprefix('max_').replace('_', ' ')} must be at least 1, got {override}")
        value = override if override is not None else getattr(stage, name, None)
        chosen.append(value if value is not None else getattr(capability, name, 1))
    return Limits(*chosen)


def _spent(engine: TaskEngine, task_id: str) -> tuple[list, list]:
    """The task's superseded submissions, and this round's refused attempts, from state (M27)."""
    records = sorted((a for a in engine.state.attempts.values() if a.task == task_id), key=lambda a: a.number)
    sent_back = [a for a in records if a.reviews]
    since = sent_back[-1].number if sent_back else 0
    return sent_back, [a for a in records if not a.reviews and a.number > since]


def exhausted(engine: TaskEngine, task_id: str, budget: Limits) -> str | None:
    """Why running the owner seat again would exceed a limit (M27), or None. Reads state only."""
    sent_back, refused = _spent(engine, task_id)
    if len(sent_back) >= budget.review_rounds:
        return f"{len(sent_back)} of {budget.review_rounds} review rounds were sent back"
    if refused and len(refused) >= budget.attempts:  # with a limit of 1, M26 records no attempt
        return f"{len(refused)} of {budget.attempts} attempts were refused in this review round"
    return None


def _exhausted(engine: TaskEngine, task_id: str, actor: Actor, budget: Limits) -> RunReport | None:
    """Escalate, through the owner's route, when running the seat again would exceed a limit (M27)."""
    reason = exhausted(engine, task_id, budget)
    if reason is None:
        return None
    sent_back, refused = _spent(engine, task_id)
    esc = engine.escalate(
        task_id, actor, EscalationKind.TECHNICAL, reason=f"repair budget exhausted: {reason}",
        attempted_actions=tuple(f"{a.id}: {a.refusal}" for a in (*sent_back, *refused)),
        blocking_question="How should this task proceed?",
        recommended_options=("Allow more attempts or review rounds", "Reassign", "Change approach",
                             "Cancel with rationale"),
    )
    return RunReport(task_id, ResultStatus.NEEDS_ESCALATION, esc.reason, escalation=esc.id)


def run_task(engine: TaskEngine, task_id: str, runtime: AgentRuntime,
             kind: ActorKind = ActorKind.AI_AGENT, attempts: int | None = None,
             review_rounds: int | None = None) -> RunReport:
    """Hand one task to a runtime and apply its result through the engine.

    When the engine refuses a submission and the attempt limit allows (M26),
    the refused attempt is recorded and the same seat is asked again, with the
    refused attempts in its packet. A task a review sent back is worked again
    with the review's findings (M27) while review rounds remain. The counts
    live in state, so each limit covers every run; an exhausted one escalates.
    """
    task = engine.task(task_id)
    if task.owner is None:
        raise WorkError(f"{task_id} has no owner")
    budget = limits(engine, task_id, attempts, review_rounds)
    actor = Actor(role=task.owner, kind=kind, name=getattr(runtime, "runtime_id", "runtime"))
    packet = assemble(engine, task_id)
    if not runtime.accepts(packet):
        return RunReport(task_id, ResultStatus.DECLINED, f"runtime {runtime.runtime_id!r} declined {task_id}")
    if task.status in (TaskStatus.READY, TaskStatus.CHANGES_REQUESTED, TaskStatus.IN_PROGRESS):
        stop = _exhausted(engine, task_id, actor, budget)
        if stop is not None:
            return stop
    if task.status in (TaskStatus.READY, TaskStatus.CHANGES_REQUESTED):
        engine.start(task_id, actor)
    elif task.status is not TaskStatus.IN_PROGRESS:
        raise WorkError(f"{task_id} is {task.status.value}; it cannot be worked")

    tools = ToolHandle(ToolBroker(engine), actor, task_id)
    report = RunReport(task_id, ResultStatus.DECLINED, "")
    refused: list[str] = []
    limit = budget.attempts
    used = len(_spent(engine, task_id)[1])
    for number in range(used + 1, limit + 1):
        if number > used + 1:
            packet = assemble(engine, task_id)  # now carries the refused attempts
        result = runtime.execute(packet, tools)
        step, refusal = _apply(engine, task_id, actor, result, f"attempt {number} of {limit}" if limit > 1 else "")
        entry: dict[str, Any] = {"number": number, "status": step.status.value, "detail": step.detail,
                                 "tool_runs": step.tool_runs, "evidence": step.evidence, "attempt": None}
        if refusal is not None and limit > 1:
            entry["attempt"] = engine.record_attempt(task_id, actor, list(result.artifacts), refusal,
                                                     tuple(step.tool_runs), tuple(step.evidence)).id
            refused.append(entry["attempt"])
        report.attempts.append(entry)
        report.tool_runs += step.tool_runs
        report.evidence += step.evidence
        report.status, report.detail = step.status, step.detail
        report.escalation, report.review = step.escalation, step.review
        if refusal is None:
            break
    if refused:
        summary = (f"all {len(refused)} attempts were refused: {', '.join(refused)}"
                   if report.status is ResultStatus.REFUSED
                   else f"{report.status.value} on attempt {report.attempts[-1]['number']}, after {', '.join(refused)}")
        report.detail = "; ".join(p for p in (report.detail, summary) if p)
    return report


def _apply(engine: TaskEngine, task_id: str, actor: Actor, result: WorkResult,
           attempt: str) -> tuple[RunReport, str | None]:
    """Apply one runtime result through the engine; also return the engine's refusal, if any."""
    PolicyEngine(engine.org).enforce(PolicyContext(
        engine.org, engine.state, "runtime.result", actor, engine.task(task_id),
        {"uncertainty": result.uncertainty, "artifacts": result.artifacts,
         "claims_completion": result.status is ResultStatus.SUBMITTED},
    ))
    report = RunReport(task_id, result.status, result.notes, tool_runs=list(result.tool_runs))

    for run_id in result.tool_runs:
        run = engine.state.tool_runs.get(run_id)
        kind_ = EvidenceKind.VERITRIAGE_SESSION if run and run.tool == "veritriage.investigate" else EvidenceKind.TOOL_RUN
        ev = engine.record_evidence(task_id, actor, kind_, run.summary if run else run_id,
                                    reference=(run.references[0] if run and run.references else None),
                                    tool_run=run_id)
        report.evidence.append(ev.id)
    for claim in result.claims:
        ev = engine.record_evidence(task_id, actor, EvidenceKind.CLAIM, claim)
        report.evidence.append(ev.id)

    if result.status is ResultStatus.NEEDS_ESCALATION and result.escalation:
        req = result.escalation
        esc = engine.escalate(task_id, actor, req.kind, reason=req.reason,
                              context=f"uncertainty {result.uncertainty}", attempted_actions=req.attempted_actions,
                              evidence=tuple(report.evidence), blocking_question=req.blocking_question,
                              recommended_options=req.recommended_options)
        report.escalation = esc.id
    elif result.status is ResultStatus.BLOCKED:
        engine.block(task_id, actor, result.notes)
    elif result.status is ResultStatus.SUBMITTED:
        notes = "; ".join(p for p in (attempt, result.notes) if p)
        try:
            engine.submit(task_id, actor, list(result.artifacts), notes=notes, outcome=result.outcome)
        except PolicyViolationError as exc:
            # The runs recorded above really happened (a failed lint is a fact worth keeping), so a
            # refused submission is reported rather than raised: the caller can save the evidence.
            report.status = ResultStatus.REFUSED
            report.detail = "; ".join(p for p in (result.notes, f"submission refused: {exc}") if p)
            return report, str(exc)
    return report, None


def review_task(engine: TaskEngine, task_id: str, runtime: AgentRuntime, role: str | None = None,
                kind: ActorKind = ActorKind.AI_AGENT) -> RunReport:
    """Seat a runtime as a task's reviewer (by default the planned one) and record its verdict.

    Independence (P6) is enforced before the runtime is asked anything, so a
    seat can never be handed its own work to judge.
    """
    task = engine.task(task_id)
    seat = role or task.reviewer
    if seat is None:
        raise WorkError(f"{task_id} has no reviewer")
    actor = Actor(role=seat, kind=kind, name=getattr(runtime, "runtime_id", "runtime"))
    policy = PolicyEngine(engine.org)
    policy.enforce(PolicyContext(engine.org, engine.state, "task.review", actor, task))
    if task.status is not TaskStatus.IN_REVIEW:
        raise WorkError(f"{task_id} is {task.status.value}, not in review")
    packet = assemble(engine, task_id, role=seat)
    review = getattr(runtime, "review", None)
    if review is None or not runtime.accepts(packet):
        return RunReport(task_id, ResultStatus.DECLINED, f"runtime {runtime.runtime_id!r} does not review {task_id}")

    result: ReviewResult = review(packet)
    policy.enforce(PolicyContext(engine.org, engine.state, "runtime.result", actor, task,
                                 {"uncertainty": result.uncertainty, "artifacts": (), "claims_completion": False}))
    if result.verdict is None:
        return RunReport(task_id, ResultStatus.DECLINED, result.notes)
    engine.review(task_id, actor, result.verdict, result.comments)
    record = [r for r in engine.state.reviews.values() if r.task == task_id and r.reviewer == seat][-1]
    detail = "; ".join(p for p in (f"{result.verdict.value}: {result.comments}", result.notes) if p)
    return RunReport(task_id, ResultStatus.SUBMITTED, detail, review=record.id)

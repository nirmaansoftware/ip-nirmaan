"""The whole-flow runner (G3, council record 2026-11-17, decision 3; gates WF6 to WF8).

A whole-flow case (``flow: whole``) puts its request in, seats every work stage with the same seat runtime, in
dependency order, and judges only the final block. Each stage runs through the unchanged ``run_task``, so its own
before-review checks run for real. Review and approval are a pass-through by the harness under its own actor name,
with a true note: the stage's output was not reviewed, and either the gate runs that passed are named or the stage
had no check ("submitted, not checked"). A stage that does not reach review stops the flow: later stages are
recorded as not run, every held-out check is not run, and the trial is failed. There is never a fallback to a
reference document.

The case's fixed inputs are given to their stage as task inputs and as customer documents (``document.<name>``,
``runtime/context.py``), so the requirements seat reads them as text. The held-out checks see the files of every
seated stage, the final stage's first, so a driver check can name the RTL stage's ``rtl_source``. The trial records
every stage (``EvalStage``), the sums of calls and tokens over all of them, attestations on any of them, and the
flow digest: sha256 over the sorted (stage, skill, skill digest) of every skill each stage's seat was given.

This module is not a ``harness.CODE`` file: it is digested in the fingerprint's ``flow`` section, present only for
a whole-flow run (``harness.FLOW_CODE``), so an edit here never changes the default fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import nirmaan
from nirmaan.evals.cases import EvalError, case_digest, resolve, skill_digest, validate_case
from nirmaan.evals.runner import (REPLAY, _REVIEWED, _UNSAFE, ReplayLLM, _ancestors, _give_inputs, _judge,
                                  runtime_cli)
from nirmaan.models import (Actor, ActorKind, EvalCase, EvalResult, EvalStage, EvidenceKind, GateRun, MemoryScope,
                            ScoreStatus, Task, TaskKind, TaskStatus, Verdict)
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import Organization
from nirmaan.runtime import AgentRuntime, run_task
from nirmaan.runtime.context import DOCUMENT, assemble
from nirmaan.runtime.files import digest
from nirmaan.runtime.harness import harness_sha256, run_attempts, run_tools
from nirmaan.work import PolicyViolationError, ProjectStore, TaskEngine, WorkError, verify_chain

#: The harness's own actor for the pass-through review and approval: never the fixture's.
PASSTHROUGH = "eval-flow-passthrough"
NOT_RUN = "not run"
NOTE_CHECKED = "Whole-flow evaluation: not reviewed. Before-review checks passed: {runs}."
NOTE_UNCHECKED = "Whole-flow evaluation: not reviewed. This stage has no before-review check: submitted, not checked."


@dataclass(frozen=True)
class FlowRun:
    result: EvalResult
    engine: TaskEngine
    stages: tuple[EvalStage, ...]
    flow_digest: str


def _order(engine: TaskEngine, case: EvalCase) -> list[Task]:
    """Every work stage in dependency order, the case's seat last; a gate or a decision is refused."""
    [seat] = [t for t in engine.state.tasks.values() if t.kind is TaskKind.WORK and t.stage == case.seat]
    before = _ancestors(engine, seat.id)
    other = [t.id for t in before if t.kind is not TaskKind.WORK]
    if other:
        raise EvalError(f"a gate or decision precedes the final stage ({', '.join(other)}); a whole flow seats "
                        "work stages only")
    return [*before, seat]


def _give_documents(engine: TaskEngine, case: EvalCase, task: Task, repo: Path, actor: Actor) -> None:
    """The case's fixed inputs for this stage as customer documents, each with its digest (``runtime/context.py``)."""
    for key, paths in case.inputs.get(task.stage or "", {}).items():
        for n, rel in enumerate(paths, start=1):
            path = resolve(repo, rel)
            name = key if len(paths) == 1 else f"{key}-{n}"
            engine.remember(MemoryScope.TASK, task.id, f"{DOCUMENT}{name}", f"{digest(path.read_bytes())} {path}",
                            actor)


class FlowReplayLLM:
    """A whole flow's reference answer, stage by stage: each prompt is answered with the case's reference files of
    the kinds that stage outputs (``WorkPrompt.outputs``). Proves the case and its judges; never a model."""

    name = REPLAY

    def __init__(self, case: EvalCase, repo: Path) -> None:
        self._files = [(Path(f.path).name, f.kind, resolve(repo, f.path).read_text(encoding="utf-8"), f.entry)
                       for f in case.reference]
        self.calls: list = []

    def complete(self, prompt, tools=None):
        self.calls.append(prompt)
        return ReplayLLM([f for f in self._files if f[1] in prompt.outputs]).complete(prompt)


def flow_digest(given: dict[str, dict[str, str]]) -> str:
    """sha256 over the sorted (stage, skill, skill digest) of every skill each seated stage was given."""
    rows = sorted([stage, skill, d] for stage, skills in given.items() for skill, d in skills.items())
    return "sha256:" + hashlib.sha256(json.dumps(rows).encode("utf-8")).hexdigest()


def run_flow(org: Organization, case: EvalCase, seat_runtime: AgentRuntime, *, replay: bool, repo: Path,
             attempts: int | None = None, sandbox: Path | None = None,
             clock: Callable[[], datetime] | None = None, knowledge: bool = True,
             variant: str = "default") -> FlowRun:
    """Seat every stage, judge the final block, and keep what each stage did."""
    if case.flow != "whole":
        raise EvalError(f"case {case.id} is not a whole-flow case")
    attempts = run_attempts(attempts, variant)
    problems = validate_case(org, case, repo)
    if problems:
        raise EvalError(f"case {case.id} cannot run: {'; '.join(problems)}")
    if run_tools(variant):
        raise EvalError(f"the whole-flow runner seats no brokered tools; harness variant {variant} cannot run it")
    started_at, started = (clock or (lambda: datetime.now(timezone.utc)))(), time.monotonic()
    sandbox = Path(sandbox) if sandbox else Path(tempfile.mkdtemp(prefix="nirmaan-flow-"))
    sandbox.mkdir(parents=True, exist_ok=True)
    engine = Orchestrator(org, clock=clock).plan(case.request)
    order = _order(engine, case)
    seat = order[-1]
    cli = runtime_cli(seat_runtime)  # before any stage runs, as the answers' harness is
    stages: list[EvalStage] = []
    given: dict[str, dict[str, str]] = {}
    gate_runs: list[str] = []
    stopped: Task | None = None
    detail, used = "", 0
    for task in order:
        if stopped is not None:
            stages.append(EvalStage(stage=str(task.stage), task=task.id, role=task.owner, status=NOT_RUN,
                                    note=f"Not run: stage {stopped.stage} did not complete."))
            continue
        actor = Actor(role=str(task.owner), kind=ActorKind.SYSTEM, name=PASSTHROUGH)
        engine.remember(MemoryScope.TASK, task.id, "input.workspace",
                        str(sandbox / "stages" / _UNSAFE.sub("_", task.id)), actor)
        _give_inputs(engine, case, task, repo, actor)
        _give_documents(engine, case, task, repo, actor)
        skills = {s.id: skill_digest(org, s.id, repo, knowledge=knowledge)
                  for s in assemble(engine, task.id, knowledge=knowledge).domain.skills}
        given[str(task.stage)] = skills
        runs: list[str] = []
        try:
            report = run_task(engine, task.id, seat_runtime, attempts=attempts or case.attempts, knowledge=knowledge)
            detail, used, runs = report.detail, len(report.attempts), list(report.tool_runs)
        except (WorkError, PolicyViolationError, PermissionError) as exc:
            detail, used = f"the engine refused the stage's work: {exc}", 1
        gate_runs += runs
        passed = [r for r in dict.fromkeys(runs) if r in engine.state.tool_runs and engine.state.tool_runs[r].succeeded]
        note = NOTE_CHECKED.format(runs=", ".join(passed)) if passed else NOTE_UNCHECKED
        reached = engine.task(task.id).status in _REVIEWED
        reviewed_by = approved_by = None
        if reached and task.id != seat.id:  # the final stage is judged, not approved
            try:
                if engine.task(task.id).status is TaskStatus.IN_REVIEW:
                    reviewed_by, approved_by = f"{task.reviewer} ({PASSTHROUGH})", f"{task.approver} ({PASSTHROUGH})"
                    engine.review(task.id, Actor(role=str(task.reviewer), kind=ActorKind.SYSTEM, name=PASSTHROUGH),
                                  Verdict.APPROVE, note)
                    engine.approve(task.id, Actor(role=str(task.approver), kind=ActorKind.SYSTEM, name=PASSTHROUGH),
                                   note)
            except (WorkError, PolicyViolationError, PermissionError) as exc:
                detail = f"the pass-through could not approve stage {task.stage}: {exc}"
            reached = engine.task(task.id).status is TaskStatus.COMPLETED
        calls = [c for c in engine.state.model_calls.values() if c.task == task.id]
        stages.append(EvalStage(
            stage=str(task.stage), task=task.id, role=task.owner, submitted_by=task.owner if runs or calls else None,
            reviewed_by=reviewed_by, approved_by=approved_by, status=engine.task(task.id).status.value,
            attempts=used, gate_runs=tuple(GateRun(tool=r.tool, run=r.id, succeeded=r.succeeded, summary=r.summary)
                                           for r in (engine.state.tool_runs[i] for i in dict.fromkeys(runs)
                                                     if i in engine.state.tool_runs)),
            skills=skills, model=next((c.model for c in calls if c.model), None), model_calls=len(calls),
            input_tokens=sum(c.input_tokens or 0 for c in calls), output_tokens=sum(c.output_tokens or 0 for c in calls),
            note=note if reached else f"Did not complete: {detail}"))
        if not reached:
            stopped = task

    final = engine.task(seat.id)
    reached_review = stopped is None and final.status in _REVIEWED
    # The checks see every seated stage's files, the final stage's first, under the final stage's task.
    seen = list(final.artifacts) + [a for t in order[:-1] for a in engine.task(t.id).artifacts]
    judged = final.model_copy(update={"artifacts": tuple(dict.fromkeys(seen))})
    scores = tuple(_judge(engine, judged, check, repo, reached_review, sandbox / "judge" / f"check-{n}")
                   for n, check in enumerate(case.held_out, start=1))
    ids = {t.id for t in order}
    from nirmaan.costs import calls_cost

    spend = calls_cost(c for c in engine.state.model_calls.values() if c.task in ids)
    ProjectStore(sandbox / ".nirmaan").save(engine.state)
    result = EvalResult(
        case=case.id, case_digest=case_digest(case, repo), runtime=seat_runtime.runtime_id, replay=replay,
        version=nirmaan.__version__, started_at=started_at, duration_s=round(time.monotonic() - started, 3),
        seat=seat.id, seat_status=NOT_RUN if stopped not in (None, seat) else final.status.value,
        submitted=reached_review, attempts=used,
        gate_runs=tuple(GateRun(tool=run.tool, run=run.id, succeeded=run.succeeded, summary=run.summary)
                        for run in (engine.state.tool_runs[r] for r in dict.fromkeys(gate_runs)
                                    if r in engine.state.tool_runs)),
        scores=scores, passed=reached_review and all(s.status is ScoreStatus.PASSED for s in scores),
        detail=detail if stopped is None else f"stage {stopped.stage} did not complete: {detail}",
        audit_ok=not verify_chain(engine.state.audit), sandbox=str(sandbox),
        attestations=tuple(e.id for e in engine.state.evidence.values()
                           if e.task in ids and e.kind is EvidenceKind.HUMAN_ATTESTATION),
        model_calls=spend.calls, input_tokens=spend.input_tokens, output_tokens=spend.output_tokens,
        cost_usd=None if spend.unknown_cost_calls else spend.cost_usd,
        harness=harness_sha256(attempts=attempts, knowledge=knowledge, cli=cli, variant=variant, flow="whole"),
        cli=cli)
    return FlowRun(result, engine, tuple(stages), flow_digest(given))


def evaluate(org: Organization, case: EvalCase, seat_runtime: AgentRuntime, *, replay: bool, repo: Path,
             attempts: int | None = None, sandbox: Path | None = None,
             clock: Callable[[], datetime] | None = None, knowledge: bool = True,
             variant: str = "default") -> tuple[EvalResult, TaskEngine]:
    """The target of ``runner.evaluate``'s dispatch for a whole-flow case: the result and the engine."""
    run = run_flow(org, case, seat_runtime, replay=replay, repo=repo, attempts=attempts, sandbox=sandbox,
                   clock=clock, knowledge=knowledge, variant=variant)
    return run.result, run.engine

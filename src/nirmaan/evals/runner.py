"""The evaluation runner: one case, one seat, a sandbox, and judges that are real tool runs.

``run_case`` plans the case's request, fixes every upstream work stage to the
case's reference documents, puts a runtime in the seat through the unchanged
``run_task``, and runs the held-out checks through the broker. It names no
stage, tool, artifact kind, or role: all of those come from the case.

What the harness does on the sandbox project, and does not:

* upstream stages are submitted, reviewed, and approved by a ``SYSTEM`` actor
  named ``eval-fixture``, whose review names the reference documents; no human
  attestation is recorded;
* a gate among the seat's upstream stops the run, because a gate is a decision
  no fixture can stand in for;
* a score of "passed" stands only if it cites a successful run recorded in the
  sandbox; otherwise it is recorded as failed.
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

import nirmaan
from nirmaan.evals.cases import EvalError, case_digest, resolve, validate_case
from nirmaan.evals.scorers import ScoreContext, scorer_spec
from nirmaan.models import (
    Actor,
    ActorKind,
    CaseFile,
    EvalCase,
    EvalResult,
    GateRun,
    HeldOutCheck,
    MemoryScope,
    Score,
    ScoreStatus,
    Task,
    TaskKind,
    TaskStatus,
    Verdict,
)
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import Organization
from nirmaan.runtime import AgentRuntime, Completion, ModelRuntime, ToolBroker, ToolHandle, WorkPrompt, run_task
from nirmaan.runtime.files import write_file
from nirmaan.work import PolicyViolationError, ProjectStore, TaskEngine, WorkError, verify_chain
from nirmaan.work.policy import unsatisfied_requirements

FIXTURE = "eval-fixture"
SCORER = "eval-scorer"
REPLAY = "replay"
#: Statuses that mean the work reached review: its own before-review checks passed.
_REVIEWED = (TaskStatus.IN_REVIEW, TaskStatus.APPROVED, TaskStatus.COMPLETED)
_UNSAFE = re.compile(r"[^A-Za-z0-9._\-]")


class ReplayLLM:
    """Answers with fixed files, citing every approved upstream artifact the prompt offers.

    Replaying a case's reference answer proves the case and its judges; replaying
    a deliberately wrong answer proves the judges catch it. Never a network call.
    """

    name = REPLAY

    def __init__(self, files: Sequence[tuple[str, str, str, str | None]]) -> None:
        self._files = list(files)  # (path, kind, content, entry)
        self.calls: list[WorkPrompt] = []

    def complete(self, prompt: WorkPrompt) -> Completion:
        self.calls.append(prompt)
        cites = [c.token for c in prompt.citations if c.kind == "artifact"]
        if not cites:
            return Completion("", self.name, error="nothing approved upstream to cite")
        meta = [{"path": path, "kind": kind, "title": path, "summary": f"{path}, from {' and '.join(cites)}.",
                 **({"entry": entry} if entry else {})} for path, kind, _, entry in self._files]
        head = json.dumps({"uncertainty": 0.0, "artifacts": [], "tool_runs": [], "claims": [], "files": meta,
                           "escalation": None, "notes": "replayed answer"})
        blocks = "".join(f"=== FILE: {path} ===\n{content}=== END FILE ===\n" for path, _, content, _ in self._files)
        return Completion(f"{head}\n{blocks}", self.name)


def replay_llm(case: EvalCase, repo: Path) -> ReplayLLM:
    """The case's own reference answer, as a model would give it."""
    return ReplayLLM([(Path(f.path).name, f.kind, resolve(repo, f.path).read_text(encoding="utf-8"), f.entry)
                      for f in case.reference])


def _ancestors(engine: TaskEngine, task_id: str) -> list[Task]:
    """Every task the seat depends on, directly or not, dependencies first."""
    order: list[str] = []

    def visit(tid: str) -> None:
        for dep in engine.task(tid).depends_on:
            if dep not in order:
                visit(dep)
                order.append(dep)

    visit(task_id)
    return [engine.task(t) for t in order]


def _fix_upstream(engine: TaskEngine, case: EvalCase, task: Task, repo: Path, sandbox: Path) -> None:
    """Submit, review, and approve one upstream stage with the case's reference documents."""
    def actor(role: str | None) -> Actor:
        if role is None:
            raise EvalError(f"{task.id} has no role to act for it")
        return Actor(role=role, kind=ActorKind.SYSTEM, name=FIXTURE)

    files = case.upstream.get(task.stage or "", ())
    if files and any(r.before_review for r in task.evidence_requirements):
        # M45: a stage with checks before review is fixed through them, never by a submission alone: the
        # reference files go through the unchanged run_task, so its gates run for real on them.
        engine.remember(MemoryScope.TASK, task.id, "input.workspace",
                        str(sandbox / "upstream" / _UNSAFE.sub("_", task.id)), actor(task.owner))
        fixed = [(Path(f.path).name, f.kind, resolve(repo, f.path).read_text(encoding="utf-8"), f.entry)
                 for f in files]
        run_task(engine, task.id, ModelRuntime(ReplayLLM(fixed), runtime_id=FIXTURE))
        _review_fixture(engine, case, task, files, actor)
        return
    drafts = []
    for f in files:
        name = Path(f.path).name
        location, digest = write_file(sandbox / "upstream" / _UNSAFE.sub("_", task.id), name,
                                      resolve(repo, f.path).read_text(encoding="utf-8"))
        drafts.append({"kind": f.kind, "title": name, "location": str(location), "digest": digest,
                       "summary": f"Reference document {f.path}, fixed by evaluation case {case.id}."})
    if not files:
        drafts = [{"kind": kind, "title": f"{task.title} ({kind})",
                   "summary": f"The request, as stated in evaluation case {case.id}: {case.request}"}
                  for kind in task.expected_outputs]
    if not drafts:
        raise EvalError(f"{task.id} produces nothing the harness can stand in for")
    engine.start(task.id, actor(task.owner))
    engine.submit(task.id, actor(task.owner), drafts, notes=f"evaluation fixture for {case.id}")
    _review_fixture(engine, case, task, files, actor)


def _review_fixture(engine: TaskEngine, case: EvalCase, task: Task, files: Sequence[CaseFile],
                    actor: Callable[[str | None], Actor]) -> None:
    """Review and approve a fixed upstream stage as the fixture; refuse when it is not complete after that."""
    if engine.task(task.id).status is TaskStatus.IN_REVIEW:
        named = ", ".join(f.path for f in files) or "the request"
        engine.review(task.id, actor(task.reviewer), Verdict.APPROVE,
                      f"Evaluation fixture: {named}, as reviewed in the repository, not here.")
        engine.approve(task.id, actor(task.approver), f"evaluation fixture for {case.id}")
    if engine.task(task.id).status is not TaskStatus.COMPLETED:
        missing = unsatisfied_requirements(engine.state, engine.task(task.id))
        raise EvalError(f"{task.id} needs evidence the harness cannot honestly supply: {missing}")


def _prepare(engine: TaskEngine, case: EvalCase, repo: Path, sandbox: Path) -> Task:
    """The seat task, READY, with every upstream work stage fixed to the case's documents."""
    [seat] = [t for t in engine.state.tasks.values() if t.kind is TaskKind.WORK and t.stage == case.seat]
    upstream = _ancestors(engine, seat.id)
    gates = [t.id for t in upstream if t.kind is TaskKind.GATE]
    if gates:
        raise EvalError(f"a gate precedes the seat ({', '.join(gates)}); an evaluation fixes work stages only")
    for task in upstream:
        if task.kind is TaskKind.DECISION:
            raise EvalError(f"a decision precedes the seat ({task.id}); an evaluation fixes work stages only")
        if task.kind is TaskKind.WORK and engine.task(task.id).status is not TaskStatus.COMPLETED:
            _fix_upstream(engine, case, engine.task(task.id), repo, sandbox)
    seat = engine.task(seat.id)
    if seat.status is not TaskStatus.READY:
        raise EvalError(f"{seat.id} is {seat.status.value} after its upstream was fixed, not ready")
    return seat


def _judge(engine: TaskEngine, task: Task, check: HeldOutCheck, repo: Path, reached_review: bool) -> Score:
    def score(status: ScoreStatus, summary: str) -> Score:
        return Score(scorer=check.scorer, name=check.name, status=status, summary=summary)

    if not reached_review:
        return score(ScoreStatus.NOT_RUN, "the work never reached review, so there is nothing to judge")
    spec = scorer_spec(check.scorer)
    if spec is None:
        return score(ScoreStatus.NOT_RUN, f"no scorer {check.scorer!r} is registered")
    tools = ToolHandle(ToolBroker(engine), Actor(role=str(task.owner), kind=ActorKind.SYSTEM, name=SCORER), task.id)
    result = spec.fn(ScoreContext(engine, task, check, repo, tools))
    recorded = [engine.state.tool_runs.get(r) for r in result.runs]
    if result.status is ScoreStatus.PASSED and not (recorded and all(r and r.succeeded for r in recorded)):
        return score(ScoreStatus.FAILED, f"claimed a pass with no passing run recorded in the sandbox: "
                                         f"{result.summary}")
    return result


def run_case(org: Organization, case: EvalCase, runtime: AgentRuntime | None = None, *, repo: Path,
             attempts: int | None = None, sandbox: Path | None = None,
             clock: Callable[[], datetime] | None = None) -> EvalResult:
    """Evaluate one seat on one case. ``runtime=None`` replays the case's reference answer."""
    replay = runtime is None
    seat_runtime = runtime or ModelRuntime(replay_llm(case, repo), runtime_id=REPLAY)
    return evaluate(org, case, seat_runtime, replay=replay, repo=repo, attempts=attempts, sandbox=sandbox,
                    clock=clock)[0]


def evaluate(org: Organization, case: EvalCase, seat_runtime: AgentRuntime, *, replay: bool, repo: Path,
             attempts: int | None = None, sandbox: Path | None = None,
             clock: Callable[[], datetime] | None = None) -> tuple[EvalResult, TaskEngine]:
    """``run_case`` with the runtime given and the replay flag stated, returning the sandbox engine too (M45)."""
    problems = validate_case(org, case, repo)
    if problems:
        raise EvalError(f"case {case.id} cannot run: {'; '.join(problems)}")
    started_at, started = (clock or (lambda: datetime.now(timezone.utc)))(), time.monotonic()
    sandbox = Path(sandbox) if sandbox else Path(tempfile.mkdtemp(prefix="nirmaan-eval-"))
    sandbox.mkdir(parents=True, exist_ok=True)

    engine = Orchestrator(org, clock=clock).plan(case.request)
    seat = _prepare(engine, case, repo, sandbox)
    engine.remember(MemoryScope.TASK, seat.id, "input.workspace", str(sandbox / "seat"),
                    Actor(role=str(seat.owner), kind=ActorKind.SYSTEM, name=FIXTURE))
    tool_runs: list[str] = []
    try:
        report = run_task(engine, seat.id, seat_runtime, attempts=attempts or case.attempts)
        detail, used, tool_runs = report.detail, len(report.attempts), list(report.tool_runs)
    except (WorkError, PolicyViolationError, PermissionError) as exc:
        detail, used = f"the engine refused the seat's work: {exc}", 1

    task = engine.task(seat.id)
    reached_review = task.status in _REVIEWED
    from nirmaan.costs import calls_cost

    spend = calls_cost(c for c in engine.state.model_calls.values() if c.task == seat.id)
    scores = tuple(_judge(engine, task, check, repo, reached_review) for check in case.held_out)
    ProjectStore(sandbox / ".nirmaan").save(engine.state)
    return EvalResult(
        case=case.id, case_digest=case_digest(case, repo), runtime=seat_runtime.runtime_id, replay=replay,
        version=nirmaan.__version__, started_at=started_at, duration_s=round(time.monotonic() - started, 3),
        seat=seat.id, seat_status=task.status.value, submitted=reached_review, attempts=used,
        gate_runs=tuple(GateRun(tool=run.tool, run=run.id, succeeded=run.succeeded, summary=run.summary)
                        for run in (engine.state.tool_runs[r] for r in dict.fromkeys(tool_runs)
                                    if r in engine.state.tool_runs)),
        scores=scores, passed=reached_review and all(s.status is ScoreStatus.PASSED for s in scores),
        detail=detail, audit_ok=not verify_chain(engine.state.audit), sandbox=str(sandbox),
        model_calls=spend.calls, input_tokens=spend.input_tokens, output_tokens=spend.output_tokens,
        cost_usd=None if spend.unknown_cost_calls else spend.cost_usd,
    ), engine


def write_result(result: EvalResult, out: Path) -> Path:
    """One JSON file per case and runtime under ``out``."""
    target = Path(out) / _UNSAFE.sub("_", result.runtime) / f"{_UNSAFE.sub('_', result.case)}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return target

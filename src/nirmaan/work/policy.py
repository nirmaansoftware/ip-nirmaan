"""The policy engine: the company constitution, enforced.

Each article of the constitution names registered checks. The task engine runs
them before it commits any change, so a violation of a BLOCK article refuses
the change outright, and a WARN article's violation is written to the audit
trail. Checks are pure functions of the proposed action and the current state;
``@register_check`` is the extension point for new policy.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import Any, Callable

from nirmaan.models import (
    Actor,
    ActorKind,
    Assurance,
    Criticality,
    Enforcement,
    EscalationKind,
    EscalationState,
    EvidenceKind,
    ProjectState,
    Task,
    TaskKind,
    ToolStatus,
    Verdict,
    param_matches,
)
from nirmaan.org import Organization
from nirmaan.registry import Registry
from nirmaan.work.audit import verify_chain


@dataclass(frozen=True)
class PolicyContext:
    org: Organization
    state: ProjectState
    action: str
    actor: Actor
    task: Task | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyViolation:
    principle: str
    check: str
    message: str
    enforcement: Enforcement


class PolicyViolationError(PermissionError):
    def __init__(self, violations: list[PolicyViolation]) -> None:
        self.violations = violations
        lines = "; ".join(f"[{v.principle}] {v.message}" for v in violations)
        super().__init__(f"Refused by the constitution: {lines}")


Check = Callable[[PolicyContext], list[str]]
_CHECKS: MutableMapping[str, Check] = Registry("policy.checks")


def register_check(check_id: str) -> Callable[[Check], Check]:
    def _register(fn: Check) -> Check:
        if check_id in _CHECKS and _CHECKS[check_id] is not fn:
            raise ValueError(f"Policy check {check_id!r} is already registered")
        _CHECKS[check_id] = fn
        return fn

    return _register


def unregister_check(check_id: str) -> None:
    _CHECKS.pop(check_id, None)


def available_checks() -> list[str]:
    return sorted(_CHECKS)


class PolicyEngine:
    def __init__(self, org: Organization) -> None:
        self._org = org
        unknown = sorted(
            c for p in org.principles.values() for c in p.checks if c not in _CHECKS
        )
        if unknown:
            raise ValueError(f"Constitution names unregistered policy checks: {unknown}")

    def evaluate(self, ctx: PolicyContext) -> list[PolicyViolation]:
        found: list[PolicyViolation] = []
        for principle in self._org.principles.values():
            for check_id in principle.checks:
                for message in _CHECKS[check_id](ctx):
                    found.append(PolicyViolation(principle.id, check_id, message, principle.enforcement))
        return found

    def enforce(self, ctx: PolicyContext) -> list[PolicyViolation]:
        """Raise on any BLOCK violation; return WARN violations for the audit trail."""
        violations = self.evaluate(ctx)
        blocking = [v for v in violations if v.enforcement is Enforcement.BLOCK]
        if blocking:
            raise PolicyViolationError(blocking)
        return violations


# --- Evidence helpers shared by checks and the engine -------------------------------


def unsatisfied_requirements(state: ProjectState, task: Task) -> list[str]:
    """Evidence requirements on the task not met by substantiated evidence."""
    attached = [state.evidence[e] for e in task.evidence if e in state.evidence]
    produced = {state.artifacts[a].kind for a in task.artifacts if a in state.artifacts}
    upstream = upstream_kinds(state, task)
    return [
        req.description
        for req in task.evidence_requirements
        if req.applies(produced, upstream) and not any(satisfies(state, ev, req) for ev in attached)
    ]


def upstream_kinds(state: ProjectState, task: Task) -> set[str]:
    """The kinds of the artifacts a task builds on, when one of its requirements asks (M37)."""
    if not any(req.when_upstream for req in task.evidence_requirements):
        return set()
    return {art.kind for art in upstream_artifacts(state, task)}


def satisfies(state: ProjectState, ev, req) -> bool:
    """Substantiated, of an accepted kind, and (if tool-backed) from a named tool run with the fixed params."""
    if not ev.substantiated or ev.kind not in req.accepts:
        return False
    if (req.tools or req.params) and ev.kind in (EvidenceKind.TOOL_RUN, EvidenceKind.VERITRIAGE_SESSION):
        run = state.tool_runs.get(ev.tool_run or "")
        return (run is not None and (not req.tools or run.tool in req.tools)
                and all(param_matches(run.params.get(k), v) for k, v in req.params))
    return True


def upstream_artifacts(state: ProjectState, task: Task) -> list:
    """The artifacts a task builds on: its dependencies' own, seen through any gate (M27).

    A gate produces nothing; approving it approves the stage behind it. A stage
    that waits on a gate therefore builds on the gated stage's artifacts, and
    those are the ones that must be approved.
    """
    found: dict[str, Any] = {}

    def visit(task_id: str) -> None:
        dep = state.tasks[task_id]
        if dep.kind is TaskKind.GATE:
            for before in dep.depends_on:
                visit(before)
            return
        for art_id in dep.artifacts:
            found.setdefault(art_id, state.artifacts[art_id])

    for dep_id in task.depends_on:
        visit(dep_id)
    return list(found.values())


def latest_verdicts(state: ProjectState, task_id: str) -> dict[str, Verdict]:
    """Each reviewer's latest verdict on the current submission; a superseded one's reviews are over (M27)."""
    stale = {r for a in state.attempts.values() if a.task == task_id for r in a.reviews}
    verdicts: dict[str, Verdict] = {}
    for review in state.reviews.values():
        if review.task == task_id and review.id not in stale:
            verdicts[review.reviewer] = review.verdict
    return verdicts


# --- The constitution's checks ---------------------------------------------------------


@register_check("traceable-to-requirement")
def _traceable(ctx: PolicyContext) -> list[str]:
    if ctx.action not in ("project.create", "task.create"):
        return []
    req = ctx.state.project.requirement.id
    tasks = [ctx.task] if ctx.task else list(ctx.state.tasks.values())
    return [f"task {t.id} does not trace to requirement {req}" for t in tasks if t.requirement != req]


@register_check("decision-needs-evidence")
def _decision_evidence(ctx: PolicyContext) -> list[str]:
    if ctx.action != "decision.record":
        return []
    crit: Criticality = ctx.payload["criticality"]
    ids: list[str] = list(ctx.payload.get("evidence", ()))
    if crit.rank < Criticality.HIGH.rank:  # M40: even a minor decision may not cite evidence never recorded
        return [f"decision evidence {e} was never recorded" for e in ids if e not in ctx.state.evidence]
    if not ids:
        return [f"a {crit.value} decision needs evidence"]
    weak = [e for e in ids if e not in ctx.state.evidence or not ctx.state.evidence[e].substantiated]
    return [f"decision evidence {e} is missing or unsubstantiated" for e in weak]


@register_check("uncertainty-declared")
def _uncertainty(ctx: PolicyContext) -> list[str]:
    if ctx.action != "runtime.result":
        return []
    if ctx.payload.get("uncertainty") is None:
        return ["an agent result must declare its uncertainty"]
    return []


@register_check("no-fabricated-completion")
def _no_fabrication(ctx: PolicyContext) -> list[str]:
    task = ctx.task
    if task is None:
        return []
    if ctx.action == "task.submit" and task.kind in (TaskKind.WORK, TaskKind.DECISION):
        if not ctx.payload.get("artifacts"):
            return [f"{task.id} submitted with no artifacts: nothing was produced"]
    if ctx.action == "runtime.result" and ctx.payload.get("claims_completion") and not ctx.payload.get("artifacts"):
        return ["an agent claimed completion without producing an artifact"]
    return []


@register_check("tool-claims-need-runs")
def _tool_claims(ctx: PolicyContext) -> list[str]:
    if ctx.action != "evidence.record":
        return []
    kind: EvidenceKind = ctx.payload["kind"]
    run_id = ctx.payload.get("tool_run")
    if kind not in (EvidenceKind.TOOL_RUN, EvidenceKind.VERITRIAGE_SESSION):
        return []
    if run_id is None:
        return [f"{kind.value} evidence must cite a brokered tool run; none was given"]
    run = ctx.state.tool_runs.get(run_id)
    if run is None:
        return [f"tool run {run_id} was never recorded: the tool was not executed"]
    tool = ctx.org.tools.get(run.tool)
    if tool is None or tool.status is not ToolStatus.AVAILABLE:
        return [f"{run.tool} is not an executable tool"]
    if kind is EvidenceKind.VERITRIAGE_SESSION and not run.tool.startswith("veritriage."):
        return [f"run {run_id} is not a VeriTriage run"]
    return []


@register_check("independent-review")
def _independent(ctx: PolicyContext) -> list[str]:
    task = ctx.task
    if task is None or ctx.action not in ("task.review", "task.approve", "gate.approve"):
        return []
    if ctx.actor.role == task.owner and task.kind is not TaskKind.GATE:
        return [f"{ctx.actor.role} owns {task.id} and may not {ctx.action.split('.')[1]} it"]
    return []


@register_check("conflicts-escalate")
def _conflicts(ctx: PolicyContext) -> list[str]:
    task = ctx.task
    if task is None or ctx.action != "task.approve":
        return []
    verdicts = set(latest_verdicts(ctx.state, task.id).values())
    if len(verdicts) < 2:
        return []
    resolved = any(
        e.task == task.id and e.kind is EscalationKind.CONFLICT and e.state is EscalationState.RESOLVED
        for e in ctx.state.escalations.values()
    )
    return [] if resolved else [f"reviews of {task.id} conflict; escalate before approving"]


@register_check("provenance")
def _provenance(ctx: PolicyContext) -> list[str]:
    if ctx.action != "task.submit":
        return []
    problems = []
    for draft in ctx.payload.get("artifacts", ()):
        if not draft.get("kind") or not draft.get("title"):
            problems.append("every artifact needs a kind and a title")
        for upstream in draft.get("derived_from", ()):
            if upstream not in ctx.state.artifacts:
                problems.append(f"artifact derives from unknown artifact {upstream}")
    return problems


@register_check("signoff-needs-evidence")
def _signoff_evidence(ctx: PolicyContext) -> list[str]:
    task = ctx.task
    if task is None or ctx.action not in ("task.approve", "task.complete"):
        return []
    return [f"{task.id} lacks evidence: {m}" for m in unsatisfied_requirements(ctx.state, task)]


@register_check("approved-inputs")
def _approved_inputs(ctx: PolicyContext) -> list[str]:
    """Work whose capability requires it starts only from approved upstream artifacts."""
    task = ctx.task
    if task is None or ctx.action != "task.start" or not task.capability:
        return []
    capability = ctx.org.capabilities.get(task.capability)
    if capability is None or not capability.approved_inputs:
        return []
    return [
        f"{task.id} works only from approved upstream artifacts: {art.id} ({art.title}) is "
        f"{art.assurance.value}, not approved"
        for art in upstream_artifacts(ctx.state, task)
        if art.assurance is not Assurance.APPROVED
    ]


@register_check("evidence-before-review")
def _before_review(ctx: PolicyContext) -> list[str]:
    """A requirement marked before_review is met, over the very files submitted, at submission."""
    task = ctx.task
    if task is None or ctx.action != "task.submit":
        return []
    attached = [ctx.state.evidence[e] for e in task.evidence if e in ctx.state.evidence]
    problems = []
    kinds = {draft.get("kind") for draft in ctx.payload.get("artifacts", ())}
    upstream = upstream_kinds(ctx.state, task)
    for req in (r for r in task.evidence_requirements if r.before_review and r.applies(kinds, upstream)):
        met = [ev for ev in attached if satisfies(ctx.state, ev, req)]
        if not met:
            problems.append(f"{task.id} cannot go to review: {req.description!r} is not met")
            continue
        inputs = {}  # the approved upstream files each upstream binding asks a run to have used
        for binding in (b for b in req.files if b.upstream):
            approved = {art.location for art in upstream_artifacts(ctx.state, task)
                        if art.kind in binding.kinds and art.assurance is Assurance.APPROVED and art.location}
            if binding.optional and not approved:
                continue  # M41: nothing approved upstream, so the optional input asks for nothing
            inputs[binding.param] = approved
            if not any(ev.kind is not EvidenceKind.TOOL_RUN
                       or approved & set(ctx.state.tool_runs[ev.tool_run].values(binding.param))
                       for ev in met):
                problems.append(f"{task.id} cannot go to review: no passing run for {req.description!r} "
                                f"used an approved upstream {' or '.join(binding.kinds)} file")
        # M44: a file the requirement yields is the very file one passing run wrote, over the approved inputs.
        runs = [ctx.state.tool_runs[ev.tool_run] for ev in met if ev.kind is EvidenceKind.TOOL_RUN]
        runs = [r for r in runs if all(approved & set(r.values(param)) for param, approved in inputs.items())]
        for draft in ctx.payload.get("artifacts", ()):
            names = [name for kind, name in req.yields if kind == draft.get("kind")]
            location = draft.get("location")
            if names and not any(location and r.outputs.get(name) == location for r in runs for name in names):
                problems.append(f"{task.id} cannot go to review: no passing run for {req.description!r} over the "
                                f"approved inputs wrote {location or 'the ' + str(draft.get('kind'))}")
        for binding in (b for b in req.files if not b.entry and not b.upstream):
            for draft in ctx.payload.get("artifacts", ()):
                location = draft.get("location")
                if draft.get("kind") not in binding.kinds or not location:
                    continue
                if not any(ev.kind is not EvidenceKind.TOOL_RUN
                           or location in ctx.state.tool_runs[ev.tool_run].values(binding.param)
                           for ev in met):
                    problems.append(f"{task.id} cannot go to review: no passing run for {req.description!r} "
                                    f"covers {location}")
    return problems


@register_check("state-changes-audited")
def _audited(ctx: PolicyContext) -> list[str]:
    # The engine's state cannot be edited in place (read-only containers, M32), so the one way to change
    # it behind the engine is to replace it: the engine reports whether it still holds what it committed.
    if ctx.payload.get("_state_intact") is False:
        return ["project state changed outside the task engine (no audit entry)"]
    return []


@register_check("audit-chain-intact")
def _chain(ctx: PolicyContext) -> list[str]:
    if ctx.action == "project.create":
        return []
    start, previous = ctx.payload.get("_chain_verified", (0, None))
    problems = verify_chain(ctx.state.audit, start, previous) if start else verify_chain(ctx.state.audit)
    return [f"audit trail broken: {p}" for p in problems]


@register_check("human-decisions")
def _human_decisions(ctx: PolicyContext) -> list[str]:
    """M40: the authority matrix marks the decisions only a person may record."""
    if ctx.action != "decision.record" or ctx.actor.kind is ActorKind.HUMAN:
        return []
    kind, crit = ctx.payload["kind"], ctx.payload["criticality"]
    if not ctx.org.authority[(kind.value, crit.value)].human_required:
        return []
    return [f"a {crit.value} {kind.value} decision needs a person; {ctx.actor.kind.value} may not record it"]


@register_check("human-gates")
def _human_gates(ctx: PolicyContext) -> list[str]:
    task = ctx.task
    if task is None or ctx.action != "gate.approve" or not task.human_required:
        return []
    if ctx.actor.kind is not ActorKind.HUMAN:
        return [f"{task.title} requires a human approver; {ctx.actor.kind.value} may not approve it"]
    return []

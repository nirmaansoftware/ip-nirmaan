"""The organizational orchestrator: requirement in, owned and gated plan out.

    requirement -> analyze -> select workflows -> instantiate stages
      -> route owners, reviewers, approvers -> gates -> workstreams -> program

Everything is data-driven. Workflows come from the registry by intent, stages
from their feature conditions, owners from the capability join in the router,
approvers from the authority matrix, and workstream leads from the org chart.
This module names no department, protocol, or role, and a test holds it to
that. The output is a :class:`ProjectState` whose every task is PLANNED or
READY: planning never claims anything was done.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Callable

from nirmaan.models import (
    ApprovalState,
    Criticality,
    Project,
    ProjectState,
    RequirementAnalysis,
    ReviewState,
    RoutingDecision,
    StageTemplate,
    Task,
    TaskKind,
    TaskStatus,
    Variant,
    WorkflowTemplate,
)
from nirmaan.orchestrator.analyze import analyze, make_requirement
from nirmaan.orchestrator.router import Router
from nirmaan.org import Organization
from nirmaan.work.engine import TaskEngine, system_actor

Clock = Callable[[], datetime]


class UnrecognizedRequirement(ValueError):
    """No declared intent matched. An honest miss, never a guess."""

    def __init__(self, analysis: RequirementAnalysis, known: list[str]) -> None:
        self.analysis = analysis
        super().__init__(
            "The organization does not recognize what this requirement asks for. "
            f"Declared intents: {', '.join(known)}. Rephrase, or register a new intent and workflow."
        )


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Orchestrator:
    def __init__(self, org: Organization, clock: Clock | None = None) -> None:
        self._org = org
        self._router = Router(org)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def router(self) -> Router:
        return self._router

    def analyze(self, text: str) -> RequirementAnalysis:
        return analyze(self._org, make_requirement(text))

    def plan(
        self,
        text: str,
        program: str = "nirmaan-ip-portfolio",
        gate_overrides: dict[str, bool] | None = None,
        submitted_by: str = "owner",
    ) -> TaskEngine:
        """Plan a project and return the engine that now owns its state."""
        org = self._org
        requirement = make_requirement(text, submitted_by)
        analysis = analyze(org, requirement)
        if analysis.intent is None:
            raise UnrecognizedRequirement(analysis, sorted({r.intent for r in org.intents}))
        workflows = sorted(
            (wf for wf in org.workflows.values() if analysis.intent in wf.intents), key=lambda w: w.id
        )
        overrides = dict(gate_overrides or {})
        digest = hashlib.sha1(
            "|".join([requirement.id, org.fingerprint, *(f"{k}={v}" for k, v in sorted(overrides.items()))]).encode()
        ).hexdigest()[:10]
        pid = f"prj-{digest}"
        project = Project(
            id=pid,
            name=_project_name(text),
            program=program,
            requirement=requirement,
            analysis=analysis,
            workflows=tuple(w.id for w in workflows),
            organization_fingerprint=org.fingerprint,
            gate_overrides=overrides,
            created_at=self._clock(),
        )
        tasks = self._tasks(pid, requirement.id, project.name, analysis, workflows, overrides)
        state = ProjectState(project=project, tasks=tasks)
        engine = TaskEngine(org, state, clock=self._clock)
        engine.record_creation(system_actor(org, "nirmaan-orchestrator"))
        return engine

    # --- Instantiation -----------------------------------------------------------------

    def _tasks(
        self,
        pid: str,
        req_id: str,
        name: str,
        analysis: RequirementAnalysis,
        workflows: list[WorkflowTemplate],
        overrides: dict[str, bool],
    ) -> dict[str, Task]:
        org = self._org
        features = set(analysis.features)
        assumed = {f: a for a in analysis.assumptions for f in a.assumed_features}
        observed = features - set(assumed)
        self._context = tuple(
            dict.fromkeys(s for rule in org.features if rule.feature in features for s in rule.skills)
        )

        tasks: dict[str, Task] = {}
        self._owners: dict[tuple[str, str], list[str]] = {}
        order: list[str] = []
        instances: dict[tuple[str, str], list[str]] = {}  # (workflow, stage) -> task IDs
        entry: dict[tuple[str, str], list[str]] = {}  # what dependents wait on (gate or work)
        phases: dict[str, list[str]] = {}

        for wf in workflows:
            prefix = "" if len(workflows) == 1 else f"{wf.id}."
            for stage in wf.stages:
                if not stage.when.holds(features):
                    continue
                variants: list[Variant | None] = (
                    [v for v in stage.variants if v.when.holds(features)] if stage.variants else [None]
                )
                if not variants:
                    continue
                ids: list[str] = []
                for variant in variants:
                    tid = f"{pid}:{prefix}{stage.id}" + (f".{variant.key}" if variant else "")
                    task = self._work_task(tid, pid, req_id, wf, stage, variant, observed, assumed, instances, entry)
                    tasks[tid] = task
                    order.append(tid)
                    ids.append(tid)
                    phases.setdefault(stage.phase, []).append(tid)
                instances[(wf.id, stage.id)] = ids
                entry[(wf.id, stage.id)] = ids
                self._owners[(wf.id, stage.id)] = [tasks[t].owner for t in ids if tasks[t].owner]
                if stage.gate:
                    gate_task = self._gate_task(pid, req_id, wf, stage, ids, tasks, overrides, prefix)
                    tasks[gate_task.id] = gate_task
                    order.append(gate_task.id)
                    phases[stage.phase].append(gate_task.id)
                    entry[(wf.id, stage.id)] = [gate_task.id]

        # Workstreams (one per phase) under one program root.
        lead_wf = workflows[0]
        program_id = f"{pid}:program"
        lead = self._router.owner(lead_wf.lead_capability, Criticality.HIGH)
        workstreams: dict[str, Task] = {}
        for phase, ids in phases.items():
            # Gates are approvals by leadership, not the phase's work: they do not
            # decide who manages it. Units keep plan order so the phase's closing
            # work can break ties.
            work = [t for t in ids if tasks[t].kind is not TaskKind.GATE and tasks[t].unit]
            decisions = {tasks[t].branch[0] for t in work if tasks[t].branch}
            if work and len(decisions) == 1 and all(tasks[t].branch for t in work):
                # Alternative branches are coordinated by whoever owns the decision.
                work = list(decisions)
            units = [tasks[t].unit for t in work if tasks[t].unit]  # one entry per task: counts matter
            manager = self._router.unit_manager(units, lead_wf.workstream_capability)
            ws_id = f"{pid}:ws.{_slug(phase)}"
            workstreams[ws_id] = Task(
                id=ws_id, title=f"{phase} workstream", kind=TaskKind.WORKSTREAM, project=pid, phase=phase,
                parent=program_id, requirement=req_id, capability=lead_wf.workstream_capability,
                owner=manager.chosen, owner_routing=manager,
                unit=org.roles[manager.chosen].unit if manager.chosen else None,
                escalation_path=_chain(org, manager.chosen),
                description=f"Plan, delegate, track, and verify completion of {phase.lower()} work.",
                review_state=ReviewState.NOT_REQUIRED, approval_state=ApprovalState.NOT_REQUIRED,
                criticality=max((tasks[t].criticality for t in ids), key=lambda c: c.rank),
            )
            for t in ids:
                tasks[t] = tasks[t].model_copy(update={"parent": ws_id})
        program = Task(
            id=program_id, title=f"Program: {name}",
            kind=TaskKind.PROGRAM, project=pid, phase="Program", requirement=req_id,
            capability=lead_wf.lead_capability, owner=lead.chosen, owner_routing=lead,
            unit=org.roles[lead.chosen].unit if lead.chosen else None,
            escalation_path=_chain(org, lead.chosen),
            description="Own the plan, the critical path, and the risks; report status.",
            review_state=ReviewState.NOT_REQUIRED, approval_state=ApprovalState.NOT_REQUIRED,
            criticality=Criticality.HIGH,
        )
        ordered = {program.id: program}
        ordered.update(workstreams)
        for tid in order:
            ordered[tid] = tasks[tid]
        return _prioritize(ordered)

    def _work_task(self, tid, pid, req_id, wf, stage: StageTemplate, variant, observed, assumed,
                   instances, entry) -> Task:
        org = self._org
        skills = tuple(dict.fromkeys((*stage.skills, *(variant.skills if variant else ()))))
        owner = self._router.owner(stage.capability, stage.criticality, skills, self._context)
        inherited = self._owners.get((wf.id, stage.owner_from or ""), [])
        if inherited and org.holds(inherited[0], stage.capability):
            owner = RoutingDecision(
                capability=stage.capability, chosen=inherited[0],
                rationale=f"continuity: owned by whoever owns '{stage.owner_from}'",
                candidates=owner.candidates,
            )
        unit = org.roles[owner.chosen].unit if owner.chosen else None
        reviewer: RoutingDecision | None = None
        approver = None
        if stage.review and owner.chosen:
            reviewer = self._router.reviewer(
                stage.review, owner.chosen, stage.criticality, unit, skills, self._context
            )
            approver = self._router.approver(owner.chosen, stage.criticality, unit)
        depends: list[str] = []
        for dep in stage.depends_on:
            depends += entry.get((wf.id, dep), [])
        branch = None
        if stage.branch:
            decision_ids = instances.get((wf.id, stage.branch[0]), [])
            branch = (decision_ids[0], stage.branch[1]) if decision_ids else None
        title = f"{stage.title}: {variant.title}" if variant else stage.title
        # Work that needs an independent reviewer and has none can never pass
        # review: plan it blocked, visibly, rather than as a silent deadlock.
        unstaffed = owner.rationale if not owner.chosen else (
            reviewer.rationale if reviewer is not None and not reviewer.chosen else None
        )
        return Task(
            id=tid, title=title, kind=TaskKind.DECISION if stage.outcomes else TaskKind.WORK, project=pid,
            description=stage.description, phase=stage.phase, workflow=wf.id, stage=stage.id,
            depends_on=tuple(depends), requirement=req_id, capability=stage.capability, skills=skills,
            owner=owner.chosen, reviewer=reviewer.chosen if reviewer else None, approver=approver, unit=unit,
            escalation_path=_chain(org, owner.chosen), owner_routing=owner, reviewer_routing=reviewer,
            criticality=stage.criticality, risk=_risk(stage, variant, observed, assumed, owner, reviewer),
            inputs=tuple(dict.fromkeys(o for d in stage.depends_on for o in _outputs(wf, d))),
            expected_outputs=stage.outputs, evidence_requirements=stage.evidence,
            outcomes=stage.outcomes, branch=branch, max_retries=stage.max_retries, on_failure=stage.on_failure,
            review_state=ReviewState.PENDING if stage.review else ReviewState.NOT_REQUIRED,
            approval_state=ApprovalState.PENDING if stage.review else ApprovalState.NOT_REQUIRED,
            status=TaskStatus.BLOCKED if unstaffed else TaskStatus.PLANNED,
            blocked_reason=unstaffed,
        )

    def _gate_task(self, pid, req_id, wf, stage: StageTemplate, ids, tasks, overrides, prefix) -> Task:
        org = self._org
        gate = org.gates[stage.gate]
        owners = [tasks[t].owner for t in ids if tasks[t].owner]
        decision = self._router.gate_approver(gate, stage.criticality, owners[0] if owners else None)
        return Task(
            id=f"{pid}:{prefix}{stage.id}.gate", title=f"Gate: {gate.name}", kind=TaskKind.GATE, project=pid,
            description=gate.description, phase=stage.phase, workflow=wf.id, stage=stage.id,
            depends_on=tuple(ids), requirement=req_id, capability=gate.approver_capability,
            owner=decision.chosen, approver=decision.chosen, owner_routing=decision,
            unit=org.roles[decision.chosen].unit if decision.chosen else None,
            escalation_path=_chain(org, decision.chosen), criticality=stage.criticality, gate=gate.id,
            human_required=overrides.get(gate.id, gate.human_required),
            review_state=ReviewState.NOT_REQUIRED, approval_state=ApprovalState.PENDING,
            status=TaskStatus.PLANNED if decision.chosen else TaskStatus.BLOCKED,
            blocked_reason=None if decision.chosen else decision.rationale,
        )


def _chain(org: Organization, role: str | None) -> tuple[str, ...]:
    return tuple(r.id for r in org.escalation_chain(role)) if role else ()


def _outputs(wf: WorkflowTemplate, stage_id: str) -> tuple[str, ...]:
    stage = wf.stage(stage_id)
    return stage.outputs if stage else ()


def _risk(stage: StageTemplate, variant: Variant | None, observed: set[str], assumed: dict, owner,
          reviewer: RoutingDecision | None = None) -> str:
    notes: list[str] = []
    for cond in (stage.when, variant.when if variant else None):
        if cond is None or cond.is_unconditional:
            continue
        if not cond.holds(observed):
            reasons = sorted({assumed[f].id for f in (*cond.all_of, *cond.any_of) if f in assumed})
            if reasons:
                notes.append(f"exists only under assumption {', '.join(reasons)}")
    if stage.criticality is Criticality.CRITICAL:
        notes.append("critical: independent review and gate required")
    if owner.chosen is None:
        notes.append("unstaffed: no eligible owner")
    elif reviewer is not None and reviewer.chosen is None:
        notes.append("unstaffed: no independent reviewer")
    return "; ".join(notes)


def _prioritize(tasks: dict[str, Task]) -> dict[str, Task]:
    """Priority = dependency depth x 10: the earliest work is the most urgent."""
    depth: dict[str, int] = {}

    def of(tid: str, trail: frozenset[str] = frozenset()) -> int:
        if tid in depth:
            return depth[tid]
        deps = [d for d in tasks[tid].depends_on if d in tasks and d not in trail]
        depth[tid] = 1 + max((of(d, trail | {tid}) for d in deps), default=-1)
        return depth[tid]

    return {tid: t.model_copy(update={"priority": of(tid) * 10}) for tid, t in tasks.items()}


def _project_name(text: str) -> str:
    words = re.sub(r"[.!?]+$", "", text.strip()).split()
    name = " ".join(words[:12])
    return name[0].upper() + name[1:] if name else "Unnamed project"

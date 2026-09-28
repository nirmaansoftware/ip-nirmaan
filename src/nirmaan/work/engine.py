"""The task engine: the only way project state changes.

Every operation runs the same gauntlet before it commits: the lifecycle state
machine (is this transition legal?), the authority matrix (may this role do
this?), and the constitution (does policy allow it?). Only then is a new state
produced, never an in-place edit, and one hash-chained audit entry records who
did what, to what, and why. An operation that fails any check changes nothing.

The engine keeps planned, executed, verified, and approved distinct: submitting
work makes artifacts EXECUTED; substantiated evidence that satisfies every
requirement makes them VERIFIED; an authorized, independent approval makes
them APPROVED. Nothing skips a rung, and a claim is never evidence.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

from nirmaan.models import (
    Actor,
    ActorKind,
    ApprovalState,
    Artifact,
    Assurance,
    Criticality,
    Decision,
    DecisionKind,
    Escalation,
    EscalationKind,
    EscalationState,
    Evidence,
    EvidenceKind,
    MemoryEntry,
    MemoryScope,
    OnFailure,
    ProjectState,
    ReviewRecord,
    ReviewState,
    Task,
    TaskKind,
    TaskStatus,
    ToolRun,
    ToolStatus,
    Verdict,
)
from nirmaan.org import AuthorityService, Organization, route_escalation
from nirmaan.work import audit
from nirmaan.work.policy import (
    PolicyContext,
    PolicyEngine,
    latest_verdicts,
    unsatisfied_requirements,
)

Clock = Callable[[], datetime]

S = TaskStatus
_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    S.PLANNED: {S.READY, S.BLOCKED, S.CANCELLED, S.ESCALATED},
    S.READY: {S.IN_PROGRESS, S.BLOCKED, S.CANCELLED, S.ESCALATED, S.PLANNED, S.COMPLETED},
    S.IN_PROGRESS: {S.IN_REVIEW, S.COMPLETED, S.FAILED, S.BLOCKED, S.ESCALATED, S.CANCELLED, S.READY},
    S.IN_REVIEW: {S.CHANGES_REQUESTED, S.APPROVED, S.ESCALATED, S.BLOCKED, S.IN_REVIEW},
    S.CHANGES_REQUESTED: {S.IN_PROGRESS, S.ESCALATED, S.CANCELLED, S.FAILED, S.READY},
    S.APPROVED: {S.COMPLETED, S.ESCALATED},
    S.BLOCKED: {S.READY, S.PLANNED, S.ESCALATED, S.CANCELLED, S.IN_PROGRESS},
    S.ESCALATED: set(TaskStatus),
    S.FAILED: {S.READY, S.ESCALATED},
    S.COMPLETED: set(),
    S.CANCELLED: set(),
}



class WorkError(RuntimeError):
    """An operation the engine refused. Nothing changed."""


class TransitionError(WorkError):
    pass


class AuthorityError(WorkError):
    pass


def system_actor(org: Organization, name: str = "nirmaan-engine") -> Actor:
    head = org.head_of(org.root.id)
    return Actor(role=head.id if head else next(iter(org.roles)), kind=ActorKind.SYSTEM, name=name)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def state_fingerprint(state: ProjectState) -> str:
    payload = json.dumps(state.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class TaskEngine:
    def __init__(self, org: Organization, state: ProjectState, clock: Clock | None = None) -> None:
        self._org = org
        self._state = state
        self._clock = clock or _utc_now
        self._authority = AuthorityService(org)
        self._policy = PolicyEngine(org)
        self._fingerprint = state_fingerprint(state)
        # Derived consequences (roll-ups, completions on approval, branch pruning)
        # are attributed to the engine itself, acting under the company's head.
        self.system = system_actor(org)

    # --- Read ----------------------------------------------------------------------

    @property
    def state(self) -> ProjectState:
        return self._state

    @property
    def org(self) -> Organization:
        return self._org

    def task(self, task_id: str) -> Task:
        try:
            return self._state.tasks[task_id]
        except KeyError:
            raise WorkError(f"Unknown task {task_id!r}") from None

    def children(self, task_id: str) -> list[Task]:
        return [t for t in self._state.tasks.values() if t.parent == task_id]

    # --- Commit machinery ------------------------------------------------------------

    def _check(self, action: str, actor: Actor, task: Task | None = None, **payload: Any) -> list:
        if actor.role not in self._org.roles:
            raise AuthorityError(f"Unknown role {actor.role!r}")
        payload["_expected_fingerprint"] = self._fingerprint
        payload["_actual_fingerprint"] = state_fingerprint(self._state)
        ctx = PolicyContext(self._org, self._state, action, actor, task, payload)
        return self._policy.enforce(ctx)

    def _commit(
        self,
        actor: Actor,
        action: str,
        subject: str,
        reason: str = "",
        details: dict[str, Any] | None = None,
        warnings: list | None = None,
        **updates: Any,
    ) -> None:
        details = dict(details or {})
        if warnings:
            details["policy_warnings"] = [f"[{w.principle}] {w.message}" for w in warnings]
        trail = audit.append(self._state.audit, self._clock(), actor, action, subject, reason, details)
        self._state = self._state.model_copy(update={**updates, "audit": trail})
        self._fingerprint = state_fingerprint(self._state)

    def _with_task(self, task: Task, **changes: Any) -> dict[str, Task]:
        if "status" in changes and changes["status"] is not task.status:
            if changes["status"] not in _TRANSITIONS[task.status]:
                raise TransitionError(
                    f"{task.id}: {task.status.value} -> {changes['status'].value} is not a legal transition"
                )
        tasks = dict(self._state.tasks)
        tasks[task.id] = task.model_copy(update=changes)
        return tasks

    def _require(self, allowed: bool, message: str) -> None:
        if not allowed:
            raise AuthorityError(message)

    def _authorize(self, actor: Actor, decision: DecisionKind, task: Task) -> None:
        verdict = self._authority.check(actor.role, decision, task.criticality, task.unit)
        if not verdict.allowed:
            hint = f"; escalate to {verdict.escalate_to}" if verdict.escalate_to else ""
            raise AuthorityError(f"{verdict.reason}{hint}")

    # --- Planning-time --------------------------------------------------------------

    def record_creation(self, actor: Actor) -> None:
        """Audit the plan the orchestrator produced, then settle readiness."""
        warnings = self._check("project.create", actor)
        self._commit(
            actor, "project.create", self._state.project.id,
            reason=f"planned from requirement {self._state.project.requirement.id}",
            details={"tasks": len(self._state.tasks), "workflows": list(self._state.project.workflows)},
            warnings=warnings,
        )
        self.refresh()

    def refresh(self) -> list[str]:
        """Settle derived state: readiness and container roll-ups. Audited."""
        changed: list[str] = []
        for _ in range(len(self._state.tasks) + 1):
            moved = self._refresh_once()
            if not moved:
                break
            changed += moved
        return changed

    def _refresh_once(self) -> list[str]:
        moved: list[str] = []
        for task in list(self._state.tasks.values()):
            if task.kind in (TaskKind.PROGRAM, TaskKind.WORKSTREAM):
                target = self._container_status(task)
                if target is not None and target is not task.status:
                    self._system_move(task, target, "roll-up of child tasks")
                    moved.append(task.id)
                continue
            if task.status is S.PLANNED and task.owner and self._deps_satisfied(task):
                self._system_move(task, S.READY, "all dependencies satisfied")
                moved.append(task.id)
        return moved

    def _system_move(self, task: Task, status: TaskStatus, reason: str) -> None:
        # Containers follow their children; their transitions are derived, not requested.
        tasks = dict(self._state.tasks)
        tasks[task.id] = task.model_copy(update={"status": status})
        self._commit(self.system, "task.status", task.id, reason=reason,
                     details={"from": task.status.value, "to": status.value}, tasks=tasks)

    def _deps_satisfied(self, task: Task) -> bool:
        return all(
            self._state.tasks[d].status in (S.COMPLETED, S.CANCELLED) for d in task.depends_on
        )

    def _container_status(self, task: Task) -> TaskStatus | None:
        kids = self.children(task.id)
        if not kids:
            return None
        statuses = {k.status for k in kids}
        if statuses <= {S.COMPLETED, S.CANCELLED}:
            return S.COMPLETED if S.COMPLETED in statuses else S.CANCELLED
        if statuses & {S.FAILED}:
            return S.BLOCKED
        if statuses - {S.PLANNED, S.READY}:
            return S.IN_PROGRESS
        return S.READY if S.READY in statuses else S.PLANNED

    # --- Execution lifecycle -------------------------------------------------------

    def start(self, task_id: str, actor: Actor) -> Task:
        task = self.task(task_id)
        self._require(actor.role == task.owner, f"only the owner ({task.owner}) starts {task_id}")
        self._authorize(actor, DecisionKind.EXECUTE_TASK, task)
        if task.status is not S.READY and task.status is not S.CHANGES_REQUESTED:
            raise TransitionError(f"{task_id} is {task.status.value}, not ready to start")
        warnings = self._check("task.start", actor, task)
        self._commit(actor, "task.start", task_id, warnings=warnings,
                     tasks=self._with_task(task, status=S.IN_PROGRESS))
        self.refresh()
        return self.task(task_id)

    def submit(
        self,
        task_id: str,
        actor: Actor,
        artifacts: list[dict[str, Any]],
        notes: str = "",
        outcome: str | None = None,
    ) -> Task:
        """The owner hands in work. Artifacts become EXECUTED, never more."""
        task = self.task(task_id)
        self._require(actor.role == task.owner, f"only the owner ({task.owner}) submits {task_id}")
        if task.status is not S.IN_PROGRESS:
            raise TransitionError(f"{task_id} is {task.status.value}; start it before submitting")
        if task.kind is TaskKind.DECISION:
            if outcome not in task.outcomes:
                raise WorkError(f"{task_id} is a decision; outcome must be one of {list(task.outcomes)}")
        elif outcome is not None:
            raise WorkError(f"{task_id} is not a decision task")
        warnings = self._check("task.submit", actor, task, artifacts=artifacts)

        new_artifacts = dict(self._state.artifacts)
        ids = list(task.artifacts)
        for index, draft in enumerate(artifacts):
            art_id = f"{task_id}#a{len(ids) + 1}"
            new_artifacts[art_id] = Artifact(
                id=art_id,
                kind=draft["kind"],
                title=draft["title"],
                task=task_id,
                produced_by=actor.label,
                assurance=Assurance.EXECUTED,
                location=draft.get("location"),
                derived_from=tuple(draft.get("derived_from", ())),
            )
            ids.append(art_id)
        needs_review = task.review_state is not ReviewState.NOT_REQUIRED
        changes: dict[str, Any] = {"artifacts": tuple(ids), "outcome": outcome}
        if needs_review:
            changes.update(status=S.IN_REVIEW, review_state=ReviewState.PENDING)
        self._commit(
            actor, "task.submit", task_id, reason=notes,
            details={"artifacts": ids[len(task.artifacts):], "outcome": outcome},
            warnings=warnings,
            tasks=self._with_task(task, **changes),
            artifacts=new_artifacts,
        )
        self._promote_if_verified(task_id)
        if not needs_review and not unsatisfied_requirements(self._state, self.task(task_id)):
            # Nothing further to wait for: the work completes on submission.
            self.complete(task_id, actor)
        return self.task(task_id)

    def review(self, task_id: str, actor: Actor, verdict: Verdict, comments: str = "") -> Task:
        task = self.task(task_id)
        if task.status is not S.IN_REVIEW:
            raise TransitionError(f"{task_id} is {task.status.value}, not in review")
        stage_review = self._review_requirement(task)
        self._require(
            actor.role == task.reviewer
            or (stage_review is not None and self._org.holds(actor.role, stage_review)),
            f"{actor.role} is neither the assigned reviewer nor holds the review capability",
        )
        self._authorize(actor, DecisionKind.REVIEW_ARTIFACT, task)
        warnings = self._check("task.review", actor, task, verdict=verdict)

        review_id = f"{task_id}#r{sum(1 for r in self._state.reviews.values() if r.task == task_id) + 1}"
        reviews = dict(self._state.reviews)
        reviews[review_id] = ReviewRecord(
            id=review_id, task=task_id, reviewer=actor.role, verdict=verdict, comments=comments
        )
        verdicts = {**latest_verdicts(self._state, task_id), actor.role: verdict}
        distinct = set(verdicts.values())
        if len(distinct) > 1:
            review_state, status = ReviewState.CONFLICTED, S.IN_REVIEW
        elif Verdict.APPROVE in distinct:
            review_state, status = ReviewState.PASSED, S.IN_REVIEW
        else:
            review_state, status = ReviewState.CHANGES_REQUESTED, S.CHANGES_REQUESTED

        evidence = dict(self._state.evidence)
        task_evidence = list(task.evidence)
        if verdict is Verdict.APPROVE:
            ev_id = f"{task_id}#e{len(task_evidence) + 1}"
            evidence[ev_id] = Evidence(
                id=ev_id, kind=EvidenceKind.REVIEW_RECORD, task=task_id,
                description=f"Independent review by {actor.role}: {comments or 'approved'}",
                recorded_by=actor.label, reference=review_id, substantiated=True,
            )
            task_evidence.append(ev_id)
        self._commit(
            actor, "task.review", task_id, reason=comments,
            details={"verdict": verdict.value, "review_state": review_state.value},
            warnings=warnings,
            tasks=self._with_task(task, status=status, review_state=review_state,
                                  evidence=tuple(task_evidence)),
            reviews=reviews,
            evidence=evidence,
        )
        self._promote_if_verified(task_id)
        return self.task(task_id)

    def approve(self, task_id: str, actor: Actor, note: str = "") -> Task:
        """An authorized, independent approval. Requires a passed review and evidence."""
        task = self.task(task_id)
        if task.kind is TaskKind.GATE:
            return self.approve_gate(task_id, actor, note)
        if task.status is not S.IN_REVIEW:
            raise TransitionError(f"{task_id} is {task.status.value}, not awaiting approval")
        if task.review_state is ReviewState.PENDING or task.review_state is ReviewState.CHANGES_REQUESTED:
            raise TransitionError(f"{task_id} has no passing independent review yet")
        self._authorize(actor, DecisionKind.APPROVE_ARTIFACT, task)
        warnings = self._check("task.approve", actor, task)
        artifacts = dict(self._state.artifacts)
        for art_id in task.artifacts:
            artifacts[art_id] = artifacts[art_id].model_copy(update={"assurance": Assurance.APPROVED})
        self._commit(
            actor, "task.approve", task_id, reason=note, warnings=warnings,
            tasks=self._with_task(task, status=S.APPROVED, approval_state=ApprovalState.GRANTED),
            artifacts=artifacts,
        )
        # Completion is the consequence of an approval, not a separate decision.
        return self.complete(task_id, self.system)

    def complete(self, task_id: str, actor: Actor) -> Task:
        task = self.task(task_id)
        needs_review = task.review_state is not ReviewState.NOT_REQUIRED
        if needs_review and task.status is not S.APPROVED:
            raise TransitionError(f"{task_id} must be approved before it completes")
        if not needs_review and task.status is not S.IN_PROGRESS:
            raise TransitionError(f"{task_id} is {task.status.value}; nothing to complete")
        self._require(
            actor.role in (task.owner, task.approver) or actor.kind is ActorKind.SYSTEM
            or actor.role == task.reviewer,
            f"{actor.role} may not complete {task_id}",
        )
        warnings = self._check("task.complete", actor, task)
        self._commit(actor, "task.complete", task_id, warnings=warnings,
                     tasks=self._with_task(task, status=S.COMPLETED))
        if task.kind is TaskKind.DECISION:
            self._take_branch(self.task(task_id))
        self.refresh()
        return self.task(task_id)

    def approve_gate(self, task_id: str, actor: Actor, note: str = "") -> Task:
        task = self.task(task_id)
        if task.kind is not TaskKind.GATE:
            raise WorkError(f"{task_id} is not a gate")
        if task.status is not S.READY:
            raise TransitionError(f"{task_id} is {task.status.value}; its work is not finished")
        gate = self._org.gates[task.gate] if task.gate else None
        self._require(gate is not None and self._org.holds(actor.role, gate.approver_capability),
                      f"{actor.role} does not hold {gate.approver_capability if gate else 'the gate capability'}")
        self._require(self._org.roles[actor.role].level.at_least(gate.min_level),
                      f"{gate.name} needs {gate.min_level.display_name} or above")
        verdict = self._authority.check(actor.role, DecisionKind.APPROVE_GATE, task.criticality)
        self._require(verdict.allowed, verdict.reason)
        warnings = self._check("gate.approve", actor, task)
        self._commit(actor, "gate.approve", task_id, reason=note, warnings=warnings,
                     details={"gate": task.gate, "human": actor.kind is ActorKind.HUMAN},
                     tasks=self._with_task(task, status=S.COMPLETED, approval_state=ApprovalState.GRANTED))
        self.refresh()
        return self.task(task_id)

    def fail(self, task_id: str, actor: Actor, reason: str) -> Task:
        """Record a failed attempt; retry within budget, then fail and (maybe) escalate."""
        task = self.task(task_id)
        self._require(actor.role == task.owner or actor.kind is ActorKind.SYSTEM,
                      f"only the owner reports failure of {task_id}")
        if task.status not in (S.IN_PROGRESS, S.CHANGES_REQUESTED):
            raise TransitionError(f"{task_id} is {task.status.value}; only active work can fail")
        attempts = task.attempts + 1
        retry = task.on_failure is not OnFailure.FAIL and attempts <= task.max_retries
        status = S.READY if retry else S.FAILED
        warnings = self._check("task.fail", actor, task)
        self._commit(actor, "task.fail", task_id, reason=reason, warnings=warnings,
                     details={"attempt": attempts, "retry": retry},
                     tasks=self._with_task(task, status=status, attempts=attempts))
        if not retry and task.on_failure is not OnFailure.FAIL:
            self.escalate(
                task_id, actor if actor.kind is not ActorKind.SYSTEM else Actor(role=task.owner),
                EscalationKind.TECHNICAL,
                reason=f"failed after {attempts} attempt(s): {reason}",
                attempted_actions=(f"{attempts} attempt(s)",),
                blocking_question="How should this task proceed?",
                recommended_options=("Reassign", "Change approach", "Cancel with rationale"),
            )
        self.refresh()
        return self.task(task_id)

    def block(self, task_id: str, actor: Actor, reason: str) -> Task:
        task = self.task(task_id)
        self._require(actor.role == task.owner or self._manages(actor, task), f"{actor.role} may not block {task_id}")
        warnings = self._check("task.block", actor, task)
        self._commit(actor, "task.block", task_id, reason=reason, warnings=warnings,
                     tasks=self._with_task(task, status=S.BLOCKED, blocked_reason=reason))
        self.refresh()
        return self.task(task_id)

    def unblock(self, task_id: str, actor: Actor, reason: str = "") -> Task:
        task = self.task(task_id)
        if task.status is not S.BLOCKED:
            raise TransitionError(f"{task_id} is not blocked")
        self._require(actor.role == task.owner or self._manages(actor, task), f"{actor.role} may not unblock {task_id}")
        target = S.READY if self._deps_satisfied(task) else S.PLANNED
        warnings = self._check("task.unblock", actor, task)
        self._commit(actor, "task.unblock", task_id, reason=reason, warnings=warnings,
                     tasks=self._with_task(task, status=target, blocked_reason=None))
        self.refresh()
        return self.task(task_id)

    def cancel(self, task_id: str, actor: Actor, reason: str) -> Task:
        task = self.task(task_id)
        self._authorize(actor, DecisionKind.CANCEL_TASK, task)
        warnings = self._check("task.cancel", actor, task)
        self._commit(actor, "task.cancel", task_id, reason=reason, warnings=warnings,
                     tasks=self._with_task(task, status=S.CANCELLED))
        self.refresh()
        return self.task(task_id)

    def reassign(self, task_id: str, actor: Actor, new_owner: str, reason: str) -> Task:
        task = self.task(task_id)
        self._authorize(actor, DecisionKind.ASSIGN_TASK, task)
        if new_owner not in self._org.roles:
            raise WorkError(f"Unknown role {new_owner!r}")
        if task.capability and not self._org.holds(new_owner, task.capability):
            raise AuthorityError(f"{new_owner} does not hold {task.capability}")
        if new_owner == task.reviewer:
            raise AuthorityError(f"{new_owner} reviews {task_id}; owner and reviewer must differ")
        warnings = self._check("task.assign", actor, task)
        self._commit(actor, "task.assign", task_id, reason=reason, warnings=warnings,
                     details={"from": task.owner, "to": new_owner},
                     tasks=self._with_task(task, owner=new_owner, unit=self._org.roles[new_owner].unit,
                                           escalation_path=tuple(r.id for r in self._org.escalation_chain(new_owner))))
        self.refresh()
        return self.task(task_id)

    # --- Evidence and tools ------------------------------------------------------------

    def record_tool_run(self, run: ToolRun, actor: Actor) -> ToolRun:
        """Only the tool broker calls this, after it actually invoked the tool."""
        tool = self._org.tools.get(run.tool)
        if tool is None or tool.status is not ToolStatus.AVAILABLE:
            raise WorkError(f"{run.tool} cannot have run: it is not executable")
        runs = dict(self._state.tool_runs)
        runs[run.id] = run
        warnings = self._check("tool.run", actor)
        self._commit(actor, "tool.run", run.task or self._state.project.id, reason=run.summary,
                     details={"tool": run.tool, "run": run.id, "succeeded": run.succeeded},
                     warnings=warnings, tool_runs=runs)
        return run

    def record_evidence(
        self,
        task_id: str,
        actor: Actor,
        kind: EvidenceKind,
        description: str,
        reference: str | None = None,
        tool_run: str | None = None,
    ) -> Evidence:
        task = self.task(task_id)
        warnings = self._check("evidence.record", actor, task, kind=kind, tool_run=tool_run)
        substantiated = False
        if kind in (EvidenceKind.TOOL_RUN, EvidenceKind.VERITRIAGE_SESSION):
            substantiated = self._state.tool_runs[tool_run].succeeded
        elif kind is EvidenceKind.HUMAN_ATTESTATION:
            substantiated = actor.kind is ActorKind.HUMAN
        elif kind is EvidenceKind.DOCUMENT:
            substantiated = reference is not None and reference in self._state.artifacts
        elif kind is EvidenceKind.REVIEW_RECORD:
            substantiated = reference is not None and reference in self._state.reviews
        ev_id = f"{task_id}#e{len(task.evidence) + 1}"
        evidence = dict(self._state.evidence)
        evidence[ev_id] = Evidence(
            id=ev_id, kind=kind, description=description, task=task_id, recorded_by=actor.label,
            reference=reference, tool_run=tool_run, substantiated=substantiated,
        )
        self._commit(actor, "evidence.record", task_id, reason=description, warnings=warnings,
                     details={"evidence": ev_id, "kind": kind.value, "substantiated": substantiated},
                     tasks=self._with_task(task, evidence=(*task.evidence, ev_id)), evidence=evidence)
        self._promote_if_verified(task_id)
        current = self.task(task_id)
        if (
            current.status is S.IN_PROGRESS
            and current.artifacts
            and current.review_state is ReviewState.NOT_REQUIRED
            and not unsatisfied_requirements(self._state, current)
        ):
            # Submitted work that needed only evidence now has it.
            self.complete(task_id, self.system)
        return self._state.evidence[ev_id]

    def _promote_if_verified(self, task_id: str) -> None:
        task = self.task(task_id)
        if not task.artifacts or unsatisfied_requirements(self._state, task):
            return
        artifacts = dict(self._state.artifacts)
        promoted = []
        for art_id in task.artifacts:
            art = artifacts[art_id]
            if art.assurance.rank < Assurance.VERIFIED.rank:
                artifacts[art_id] = art.model_copy(update={"assurance": Assurance.VERIFIED, "evidence": task.evidence})
                promoted.append(art_id)
        if promoted:
            self._commit(self.system, "artifact.verified", task_id, reason="every evidence requirement is met",
                         details={"artifacts": promoted}, artifacts=artifacts)

    # --- Escalation --------------------------------------------------------------------

    def escalate(
        self,
        task_id: str | None,
        actor: Actor,
        kind: EscalationKind,
        reason: str,
        context: str = "",
        attempted_actions: tuple[str, ...] = (),
        evidence: tuple[str, ...] = (),
        blocking_question: str = "",
        recommended_options: tuple[str, ...] = (),
        supersedes: str | None = None,
        target_role: str | None = None,
    ) -> Escalation:
        task = self.task(task_id) if task_id else None
        target = target_role or route_escalation(self._org, actor.role, kind)
        if target is None:
            raise WorkError(f"{actor.role} has nobody to escalate {kind.value} to")
        warnings = self._check("escalation.raise", actor, task)
        esc_id = f"esc-{len(self._state.escalations) + 1:03d}"
        escalations = dict(self._state.escalations)
        escalations[esc_id] = Escalation(
            id=esc_id, task=task_id, kind=kind, raised_by=actor.role, target_role=target, reason=reason,
            context=context, attempted_actions=attempted_actions, evidence=evidence,
            blocking_question=blocking_question, recommended_options=recommended_options, supersedes=supersedes,
        )
        updates: dict[str, Any] = {"escalations": escalations}
        if task is not None and (not task.status.is_terminal or task.status is S.FAILED):
            previous = task.status_before_escalation if task.status is S.ESCALATED else task.status
            updates["tasks"] = self._with_task(
                task, status=S.ESCALATED, escalation_state=EscalationState.OPEN,
                status_before_escalation=previous,
            )
        self._commit(actor, "escalation.raise", task_id or esc_id, reason=reason, warnings=warnings,
                     details={"escalation": esc_id, "kind": kind.value, "to": target}, **updates)
        return self._state.escalations[esc_id]

    def resolve_escalation(self, escalation_id: str, actor: Actor, resolution: str) -> Escalation:
        esc = self._state.escalations.get(escalation_id)
        if esc is None:
            raise WorkError(f"Unknown escalation {escalation_id!r}")
        if esc.state is not EscalationState.OPEN:
            raise TransitionError(f"{escalation_id} is already {esc.state.value}")
        target = self._org.roles[esc.target_role]
        chain = {r.id for r in self._org.escalation_chain(esc.target_role)}
        self._require(
            actor.role == esc.target_role or actor.role in chain,
            f"{escalation_id} is for {target.title}; {actor.role} cannot resolve it",
        )
        warnings = self._check("escalation.resolve", actor, self._state.tasks.get(esc.task or ""))
        escalations = dict(self._state.escalations)
        escalations[escalation_id] = esc.model_copy(
            update={"state": EscalationState.RESOLVED, "resolution": resolution, "resolved_by": actor.role}
        )
        updates: dict[str, Any] = {"escalations": escalations}
        if esc.task:
            task = self._state.tasks[esc.task]
            still_open = any(
                e.task == esc.task and e.state is EscalationState.OPEN and e.id != escalation_id
                for e in self._state.escalations.values()
            )
            if task.status is S.ESCALATED and not still_open:
                restored = task.status_before_escalation or S.PLANNED
                if restored is S.FAILED:
                    restored = S.READY  # resolution authorizes another attempt
                tasks = dict(self._state.tasks)
                tasks[task.id] = task.model_copy(update={
                    "status": restored, "escalation_state": EscalationState.RESOLVED,
                    "status_before_escalation": None,
                    "attempts": 0 if restored is S.READY else task.attempts,
                })
                updates["tasks"] = tasks
        self._commit(actor, "escalation.resolve", esc.task or escalation_id, reason=resolution,
                     warnings=warnings, details={"escalation": escalation_id}, **updates)
        self.refresh()
        return self._state.escalations[escalation_id]

    def reescalate(self, escalation_id: str, actor: Actor, reason: str) -> Escalation:
        """Take an unresolved escalation one level further up."""
        esc = self._state.escalations[escalation_id]
        self._require(actor.role == esc.target_role, f"only {esc.target_role} can re-escalate {escalation_id}")
        chain = self._org.escalation_chain(esc.target_role)
        if not chain:
            raise WorkError(f"{esc.target_role} is the top of the chain")
        escalations = dict(self._state.escalations)
        escalations[escalation_id] = esc.model_copy(update={
            "state": EscalationState.RESOLVED, "resolution": f"re-escalated: {reason}", "resolved_by": actor.role,
        })
        self._commit(actor, "escalation.forward", esc.task or escalation_id, reason=reason,
                     details={"escalation": escalation_id, "to": chain[0].id}, escalations=escalations)
        return self.escalate(
            esc.task, actor, esc.kind, reason=f"{esc.reason} | {reason}", context=esc.context,
            attempted_actions=(*esc.attempted_actions, f"{actor.role}: {reason}"), evidence=esc.evidence,
            blocking_question=esc.blocking_question, recommended_options=esc.recommended_options,
            supersedes=escalation_id, target_role=chain[0].id,
        )

    # --- Decisions and memory -------------------------------------------------------------

    def record_decision(
        self,
        actor: Actor,
        kind: DecisionKind,
        criticality: Criticality,
        statement: str,
        rationale: str,
        evidence: tuple[str, ...] = (),
        task_id: str | None = None,
        subject_unit: str | None = None,
    ) -> Decision:
        verdict = self._authority.check(actor.role, kind, criticality, subject_unit)
        if not verdict.allowed:
            hint = f"; escalate to {verdict.escalate_to}" if verdict.escalate_to else ""
            raise AuthorityError(f"{verdict.reason}{hint}")
        warnings = self._check("decision.record", actor, self._state.tasks.get(task_id or ""),
                               criticality=criticality, evidence=evidence)
        dec_id = f"dec-{len(self._state.decisions) + 1:03d}"
        decisions = dict(self._state.decisions)
        decisions[dec_id] = Decision(id=dec_id, kind=kind, criticality=criticality, statement=statement,
                                     rationale=rationale, made_by=actor.role, task=task_id, evidence=evidence)
        self._commit(actor, "decision.record", task_id or dec_id, reason=statement, warnings=warnings,
                     details={"decision": dec_id, "kind": kind.value}, decisions=decisions)
        return decisions[dec_id]

    def remember(self, scope: MemoryScope, owner: str, key: str, value: str, actor: Actor,
                 source_task: str | None = None, evidence: tuple[str, ...] = ()) -> MemoryEntry:
        entry = MemoryEntry(scope=scope, owner=owner, key=key, value=value, recorded_by=actor.label,
                            source_task=source_task, evidence=evidence)
        warnings = self._check("memory.write", actor)
        self._commit(actor, "memory.write", owner, reason=key, warnings=warnings,
                     details={"scope": scope.value, "key": key}, memory=[*self._state.memory, entry])
        return entry

    # --- Branching -------------------------------------------------------------------------

    def _take_branch(self, decision: Task) -> None:
        for task in list(self._state.tasks.values()):
            if task.branch and task.branch[0] == decision.id and task.branch[1] != decision.outcome:
                if not task.status.is_terminal:
                    self._commit(
                        self.system, "task.cancel", task.id,
                        reason=f"branch not taken: {decision.id} concluded '{decision.outcome}'",
                        tasks=self._with_task(task, status=S.CANCELLED),
                    )

    # --- Helpers ---------------------------------------------------------------------------

    def _manages(self, actor: Actor, task: Task) -> bool:
        return task.owner is not None and actor.role in {r.id for r in self._org.line_chain(task.owner)}

    def _review_requirement(self, task: Task) -> str | None:
        wf = self._org.workflows.get(task.workflow or "")
        stage = wf.stage(task.stage) if wf and task.stage else None
        return stage.review.capability if stage and stage.review else None

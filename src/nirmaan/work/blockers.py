"""Why is this task blocked? The dependency and evidence chain, as data.

A pure projection of project state. Every reason names the task, role,
escalation, or evidence requirement responsible, and unmet dependencies are
explained recursively (each once), so the answer bottoms out at whatever can
actually move next.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nirmaan.models import (
    EscalationState,
    ProjectState,
    ReviewState,
    Task,
    TaskKind,
    TaskStatus,
)
from nirmaan.work.policy import unsatisfied_requirements

_DONE = (TaskStatus.COMPLETED, TaskStatus.CANCELLED)


@dataclass
class Blocker:
    task: str
    title: str
    status: str
    owner: str | None
    reasons: list[str] = field(default_factory=list)
    upstream: list["Blocker"] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return bool(self.reasons or self.upstream)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "title": self.title,
            "status": self.status,
            "owner": self.owner,
            "reasons": self.reasons,
            "upstream": [u.to_dict() for u in self.upstream],
        }

    def lines(self, indent: int = 0) -> list[str]:
        pad = "  " * indent
        head = f"{pad}{self.title} [{self.status}] owner={self.owner or 'unassigned'}"
        out = [head] + [f"{pad}  - {r}" for r in self.reasons]
        for up in self.upstream:
            out += up.lines(indent + 1)
        return out


def why_blocked(state: ProjectState, task_id: str, _seen: set[str] | None = None) -> Blocker:
    seen = _seen if _seen is not None else set()
    seen.add(task_id)
    task = state.tasks[task_id]
    node = Blocker(task=task.id, title=task.title, status=task.status.value, owner=task.owner)

    if task.status in _DONE:
        return node
    if task.owner is None:
        node.reasons.append(f"no owner: {task.blocked_reason or 'nobody eligible holds ' + str(task.capability)}")
    if task.status is TaskStatus.BLOCKED and task.blocked_reason:
        node.reasons.append(f"blocked: {task.blocked_reason}")
    if task.status is TaskStatus.FAILED:
        node.reasons.append(f"failed after {task.attempts} attempt(s)")
    for esc in state.escalations.values():
        if esc.task == task.id and esc.state is EscalationState.OPEN:
            question = f"; question: {esc.blocking_question}" if esc.blocking_question else ""
            node.reasons.append(
                f"escalation {esc.id} ({esc.kind.value}) awaiting {esc.target_role}: {esc.reason}{question}"
            )
    if task.branch:
        decision = state.tasks.get(task.branch[0])
        if decision is not None and decision.status not in _DONE:
            node.reasons.append(
                f"conditional branch: runs only if {decision.title} concludes '{task.branch[1]}'"
            )
    if task.kind in (TaskKind.PROGRAM, TaskKind.WORKSTREAM):
        for child in (t for t in state.tasks.values() if t.parent == task.id):
            if child.status not in _DONE and child.id not in seen:
                sub = why_blocked(state, child.id, seen)
                if sub.is_blocked or child.status is not TaskStatus.PLANNED:
                    node.upstream.append(sub)
        return node

    for dep_id in task.depends_on:
        dep = state.tasks[dep_id]
        if dep.status in _DONE:
            continue
        if dep_id in seen:
            node.reasons.append(f"waits on {dep.title} [{dep.status.value}] (explained above)")
            continue
        node.upstream.append(why_blocked(state, dep_id, seen))

    if task.status is TaskStatus.IN_REVIEW:
        if task.review_state is ReviewState.PENDING:
            node.reasons.append(
                f"awaiting independent review by {task.reviewer}" if task.reviewer
                else "no independent reviewer is staffed: escalate for staffing"
            )
        elif task.review_state is ReviewState.CONFLICTED:
            node.reasons.append("reviews conflict: must be escalated (constitution P7) before approval")
        elif task.review_state is ReviewState.PASSED:
            node.reasons.append(f"review passed; awaiting approval by {task.approver}")
    if task.status is TaskStatus.CHANGES_REQUESTED:
        node.reasons.append(f"changes requested; back with {task.owner}")
    if task.kind is TaskKind.GATE and task.status is TaskStatus.READY:
        who = "a human " if task.human_required else ""
        node.reasons.append(f"awaiting {who}gate approval by {task.owner}")
    if task.status in (TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW) and task.artifacts:
        for missing in unsatisfied_requirements(state, task):
            node.reasons.append(f"evidence missing: {missing}")
    return node


def blocked_tasks(state: ProjectState) -> list[Task]:
    """Tasks that cannot move without someone else acting."""
    return [
        t
        for t in state.tasks.values()
        if t.kind not in (TaskKind.PROGRAM, TaskKind.WORKSTREAM)
        and (
            t.status in (TaskStatus.BLOCKED, TaskStatus.ESCALATED, TaskStatus.FAILED)
            or t.owner is None
        )
    ]

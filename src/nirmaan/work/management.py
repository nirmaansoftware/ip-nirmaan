"""What managers do beyond answering questions: track, detect, verify, report.

Every function here is a pure projection of project state, so a status report
can never disagree with the tasks it summarizes. Completion is *verified*
(children done, evidence present, gates passed), never just asserted.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from nirmaan.models import (
    Assurance,
    EscalationState,
    ProjectState,
    ReviewState,
    TaskKind,
    TaskStatus,
)
from nirmaan.org import Organization
from nirmaan.work.blockers import blocked_tasks, why_blocked
from nirmaan.work.policy import unsatisfied_requirements


@dataclass
class StatusReport:
    project: str
    name: str
    intent: str | None
    tasks: int
    by_status: dict[str, int]
    by_phase: dict[str, dict[str, int]]
    active_teams: list[str]
    blocked: list[dict]
    escalations: list[dict]
    pending_reviews: list[dict]
    gates: list[dict]
    risks: list[dict]
    assumptions: list[dict]
    assurance: dict[str, int]
    progress: float
    audit_entries: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def status_report(org: Organization, state: ProjectState) -> StatusReport:
    work = [t for t in state.tasks.values() if t.kind in (TaskKind.WORK, TaskKind.DECISION, TaskKind.GATE)]
    by_status = Counter(t.status.value for t in work)
    by_phase: dict[str, Counter] = {}
    for t in work:
        by_phase.setdefault(t.phase, Counter())[t.status.value] += 1
    live = [t for t in work if t.status is not TaskStatus.CANCELLED]
    done = sum(1 for t in live if t.status is TaskStatus.COMPLETED)
    teams = sorted({
        org.units[t.unit].name
        for t in work
        if t.unit and t.status not in (TaskStatus.CANCELLED, TaskStatus.COMPLETED)
    })
    return StatusReport(
        project=state.project.id,
        name=state.project.name,
        intent=state.project.analysis.intent,
        tasks=len(work),
        by_status=dict(sorted(by_status.items())),
        by_phase={p: dict(sorted(c.items())) for p, c in by_phase.items()},
        active_teams=teams,
        blocked=[
            {"task": t.id, "title": t.title, "why": why_blocked(state, t.id).lines()[1:]}
            for t in blocked_tasks(state)
        ],
        escalations=[
            {"id": e.id, "task": e.task, "kind": e.kind.value, "to": e.target_role, "reason": e.reason}
            for e in state.escalations.values()
            if e.state is EscalationState.OPEN
        ],
        pending_reviews=[
            {
                "task": t.id,
                "title": t.title,
                "reviewer": t.reviewer,
                "approver": t.approver,
                "state": t.review_state.value,
            }
            for t in work
            if t.status is TaskStatus.IN_REVIEW
        ],
        gates=[
            {
                "task": t.id,
                "gate": t.gate,
                "title": t.title,
                "approver": t.owner,
                "human_required": t.human_required,
                "status": t.status.value,
            }
            for t in work
            if t.kind is TaskKind.GATE
        ],
        risks=[
            {"task": t.id, "title": t.title, "risk": t.risk}
            for t in work
            if t.risk and t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
        ],
        assumptions=[
            {"id": a.id, "note": a.note, "question": a.question, "features": list(a.assumed_features)}
            for a in state.project.analysis.assumptions
        ],
        assurance=_assurance(state),
        progress=round(done / len(live), 3) if live else 0.0,
        audit_entries=len(state.audit),
    )


def _assurance(state: ProjectState) -> dict[str, int]:
    counts = Counter(a.assurance.value for a in state.artifacts.values())
    return {level.value: counts.get(level.value, 0) for level in Assurance}


def verify_completion(state: ProjectState, task_id: str) -> list[str]:
    """Why a task (or container) is not verifiably complete. Empty means it is."""
    task = state.tasks[task_id]
    problems: list[str] = []
    if task.kind in (TaskKind.PROGRAM, TaskKind.WORKSTREAM):
        for child in (t for t in state.tasks.values() if t.parent == task.id):
            problems += [f"{child.id}: {p}" for p in verify_completion(state, child.id)]
        return problems
    if task.status is TaskStatus.CANCELLED:
        return []
    if task.status is not TaskStatus.COMPLETED:
        problems.append(f"status is {task.status.value}")
    if task.kind in (TaskKind.WORK, TaskKind.DECISION):
        if not task.artifacts:
            problems.append("no artifact was produced")
        problems += [f"evidence missing: {m}" for m in unsatisfied_requirements(state, task)]
        if task.review_state not in (ReviewState.NOT_REQUIRED, ReviewState.PASSED):
            problems.append(f"review is {task.review_state.value}")
    return problems

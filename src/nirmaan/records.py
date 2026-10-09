"""Engineering records (M29): why was this chosen, and what went wrong? Views, never stored.

A decision task already holds everything an architecture decision record
asks for: its declared outcomes are the alternatives, its recorded outcome the
choice, its artifacts the written rationale, its evidence what backs it, the
audit trail who decided, who approved, and when, and the branches the engine
cancelled are its consequences. Failures are already recorded as structure:
failed tool runs, refused or sent-back attempts, blocks, failures, and
escalations. These functions read them; nothing is inferred, stored, or
audited, and a field with no record behind it stays empty.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable

from nirmaan.models import AuditEntry, ProjectState, ReviewState, Task, TaskKind, TaskStatus

_PASSED_REVIEW = (TaskStatus.APPROVED, TaskStatus.COMPLETED)
_REACHED_REVIEW = (TaskStatus.IN_REVIEW, *_PASSED_REVIEW)


# --- Decisions -----------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionRecord:
    id: str
    source: str  # "decision_task" or "decision_record"
    question: str
    context: str
    alternatives: tuple[str, ...]
    chosen: str | None
    rationale: tuple[str, ...]
    evidence: tuple[dict[str, Any], ...]
    decided_by: str | None
    decided_at: str | None
    approved_by: str | None
    consequences: tuple[dict[str, Any], ...]
    status: str
    kind: str | None = None  # M40: a recorded decision's kind and criticality, and its supersession links
    criticality: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _entries(state: ProjectState, action: str, subject: str) -> list[AuditEntry]:
    return [e for e in state.audit if e.action == action and e.subject == subject]


def _evidence(state: ProjectState, ids: Iterable[str]) -> tuple[dict[str, Any], ...]:
    return tuple({"id": e, "kind": state.evidence[e].kind.value, "substantiated": state.evidence[e].substantiated,
                  "description": state.evidence[e].description}
                 for e in ids if e in state.evidence)


def _from_task(state: ProjectState, task: Task) -> DecisionRecord:
    decided = [e for e in _entries(state, "task.submit", task.id)
               if task.outcome is not None and e.details.get("outcome") == task.outcome]
    approved = _entries(state, "task.approve", task.id)
    consequences = []
    for other in sorted(state.tasks.values(), key=lambda t: t.id):
        if other.branch and other.branch[0] == task.id and other.status is TaskStatus.CANCELLED:
            cancel = _entries(state, "task.cancel", other.id)
            consequences.append({"task": other.id, "title": other.title,
                                 "reason": cancel[-1].reason if cancel else "",
                                 "at": cancel[-1].at.isoformat() if cancel else None})
    rationale = tuple(f"{a.title}: {a.summary}" if a.summary else a.title
                      for a in (state.artifacts[i] for i in task.artifacts if i in state.artifacts))
    return DecisionRecord(
        id=task.id, source="decision_task", question=task.title, context=task.description,
        alternatives=task.outcomes, chosen=task.outcome, rationale=rationale,
        evidence=_evidence(state, task.evidence),
        decided_by=decided[-1].actor if decided else None,
        decided_at=decided[-1].at.isoformat() if decided else None,
        approved_by=approved[-1].actor if approved else None,
        consequences=tuple(consequences), status=task.status.value,
    )


def decision_records(state: ProjectState) -> list[DecisionRecord]:
    """Every decision task and every recorded decision, by ID."""
    records = [_from_task(state, t) for t in state.tasks.values() if t.kind is TaskKind.DECISION]
    replaced_by = {d.supersedes: d.id for d in state.decisions.values() if d.supersedes}
    for dec in state.decisions.values():
        entry = [e for e in state.audit if e.action == "decision.record" and e.details.get("decision") == dec.id]
        task = state.tasks.get(dec.task or "")
        records.append(DecisionRecord(
            id=dec.id, source="decision_record", question=dec.subject or (task.title if task else dec.statement),
            context="", alternatives=dec.options,
            chosen=dec.statement, rationale=(dec.rationale,) if dec.rationale else (),
            evidence=_evidence(state, dec.evidence),
            decided_by=entry[-1].actor if entry else dec.made_by,
            decided_at=entry[-1].at.isoformat() if entry else None,
            approved_by=None, consequences=(), status="superseded" if dec.id in replaced_by else "recorded",
            kind=dec.kind.value, criticality=dec.criticality.value, supersedes=dec.supersedes,
            superseded_by=replaced_by.get(dec.id),
        ))
    return sorted(records, key=lambda r: r.id)


# --- Failures ------------------------------------------------------------------------------


class FailureCategory(str, Enum):
    CHECK_FAILED = "check_failed"
    REVIEW_SENT_BACK = "review_sent_back"
    SUBMISSION_REFUSED = "submission_refused"
    BLOCKED = "blocked"
    FAILED = "failed"
    ESCALATED = "escalated"


@dataclass(frozen=True)
class FailureRecord:
    project: str
    category: FailureCategory
    subject: str | None
    task: str | None
    stage: str | None
    attempt: str | None
    runs: tuple[str, ...]
    evidence: tuple[str, ...]
    summary: str
    at: str
    resolved: bool
    resolution: str

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "category": self.category.value}


def _record(state: ProjectState, entry: AuditEntry, category: FailureCategory, task_id: str | None,
            summary: str, resolution: str, subject: str | None = None, attempt: str | None = None,
            runs: tuple[str, ...] = (), evidence: tuple[str, ...] = ()) -> tuple[int, FailureRecord]:
    task = state.tasks.get(task_id or "")
    return entry.sequence, FailureRecord(
        project=state.project.id, category=category, subject=subject, task=task_id,
        stage=task.stage if task else None, attempt=attempt, runs=runs, evidence=evidence, summary=summary,
        at=entry.at.isoformat(), resolved=bool(resolution), resolution=resolution,
    )


def failure_records(state: ProjectState) -> list[FailureRecord]:
    """Every recorded failure, in the order the audit trail recorded it."""
    found: list[tuple[int, FailureRecord]] = []
    attempt_of = {r: a.id for a in state.attempts.values() for r in a.tool_runs}
    run_entries = [e for e in state.audit if e.action == "tool.run"]
    for index, entry in enumerate(run_entries):
        run = state.tool_runs.get(entry.details.get("run", ""))
        if run is None or run.succeeded:
            continue
        later = [state.tool_runs[e.details["run"]] for e in run_entries[index + 1:]
                 if e.details.get("run") in state.tool_runs]
        fixed = next((r for r in later if r.tool == run.tool and r.task == run.task and r.succeeded), None)
        evidence = tuple(e.id for e in state.evidence.values() if e.tool_run == run.id)
        found.append(_record(state, entry, FailureCategory.CHECK_FAILED, run.task, run.summary,
                             f"{fixed.id} of {fixed.tool} succeeded" if fixed else "", subject=run.tool,
                             attempt=attempt_of.get(run.id), runs=(run.id,), evidence=evidence))

    for attempt in state.attempts.values():
        task = state.tasks.get(attempt.task)
        entry = next((e for e in state.audit if e.details.get("attempt") == attempt.id
                      or e.details.get("superseded") == attempt.id), None)
        if entry is None or task is None:
            continue
        if attempt.reviews:
            reviewers = sorted({state.reviews[r].reviewer for r in attempt.reviews if r in state.reviews})
            passed = task.status in _PASSED_REVIEW or task.review_state is ReviewState.PASSED
            found.append(_record(state, entry, FailureCategory.REVIEW_SENT_BACK, task.id, attempt.refusal,
                                 f"passed review later; the task is {task.status.value}" if passed else "",
                                 subject=", ".join(reviewers) or None, attempt=attempt.id,
                                 evidence=attempt.evidence))
        elif not any(r in state.tool_runs and not state.tool_runs[r].succeeded for r in attempt.tool_runs):
            accepted = task.status in _REACHED_REVIEW
            found.append(_record(state, entry, FailureCategory.SUBMISSION_REFUSED, task.id, attempt.refusal,
                                 f"a later submission was accepted; the task is {task.status.value}"
                                 if accepted else "", attempt=attempt.id, runs=attempt.tool_runs,
                                 evidence=attempt.evidence))

    for index, entry in enumerate(state.audit):
        if entry.action == "task.block":
            unblocked = next((e for e in state.audit[index + 1:]
                              if e.action == "task.unblock" and e.subject == entry.subject), None)
            task = state.tasks.get(entry.subject)
            resolution = (f"unblocked: {unblocked.reason or 'no reason given'}" if unblocked
                          else f"the task is {task.status.value}" if task and task.status is not TaskStatus.BLOCKED
                          else "")
            found.append(_record(state, entry, FailureCategory.BLOCKED, entry.subject, entry.reason, resolution))
        elif entry.action == "task.fail":
            task = state.tasks.get(entry.subject)
            done = task is not None and task.status is TaskStatus.COMPLETED
            found.append(_record(state, entry, FailureCategory.FAILED, entry.subject, entry.reason,
                                 "completed later" if done else ""))
        elif entry.action == "escalation.raise":
            esc = state.escalations.get(entry.details.get("escalation", ""))
            if esc is None:
                continue
            found.append(_record(state, entry, FailureCategory.ESCALATED, esc.task, esc.reason,
                                 f"resolved by {esc.resolved_by}: {esc.resolution}" if esc.resolution else "",
                                 subject=esc.kind.value, evidence=esc.evidence))
    return [record for _, record in sorted(found, key=lambda pair: pair[0])]


@dataclass(frozen=True)
class FailureCount:
    category: FailureCategory
    subject: str | None
    count: int
    projects: int
    resolved: int

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "category": self.category.value}


def failure_summary(states: Iterable[ProjectState]) -> list[FailureCount]:
    """Failures counted by category and subject, across projects."""
    groups: dict[tuple[FailureCategory, str | None], list[FailureRecord]] = {}
    for state in states:
        for record in failure_records(state):
            groups.setdefault((record.category, record.subject), []).append(record)
    return [FailureCount(category, subject, len(rows), len({r.project for r in rows}), sum(r.resolved for r in rows))
            for (category, subject), rows in sorted(groups.items(), key=lambda kv: (kv[0][0].value, kv[0][1] or ""))]


# --- Export sections -----------------------------------------------------------------------


def decisions_section(org, state: ProjectState, w, folder) -> list[str]:
    records = decision_records(state)
    w.json(f"{folder.id}/decisions.json", {"project": state.project.id, "decisions": [r.to_dict() for r in records]})
    lines = ["# Decisions", "", "Every decision task and recorded decision, from the record: the alternatives "
             "declared, the choice made, the written rationale, the evidence, who decided and approved, and "
             "the branches the choice cancelled. Nothing here is inferred.", ""]
    for r in records:
        lines += [f"## `{r.id}` {r.question}", "",
                  f"- Chosen: {r.chosen or 'not yet decided'} ({r.status})",
                  f"- Alternatives: {', '.join(r.alternatives) or 'none recorded'}",
                  f"- Decided by: {r.decided_by or 'nobody yet'}" + (f" at {r.decided_at}" if r.decided_at else ""),
                  f"- Approved by: {r.approved_by or 'not recorded'}"]
        lines += [f"- Supersedes: `{r.supersedes}`"] if r.supersedes else []
        lines += [f"- Superseded by: `{r.superseded_by}`"] if r.superseded_by else []
        lines += [f"- Rationale: {text}" for text in r.rationale]
        lines += [f"- Evidence: `{e['id']}` {e['kind']}" + ("" if e["substantiated"] else " (unsubstantiated)")
                  for e in r.evidence]
        lines += [f"- Cancelled: `{c['task']}` {c['title']}" for c in r.consequences] + [""]
    w.text(f"{folder.id}/decisions.md", lines)
    return ["decisions.json", "decisions.md"]


def failures_section(org, state: ProjectState, w, folder) -> list[str]:
    records = failure_records(state)
    summary = failure_summary([state])
    w.json(f"{folder.id}/failures.json", {"project": state.project.id, "failures": [r.to_dict() for r in records],
                                          "summary": [c.to_dict() for c in summary]})
    lines = ["# Failures", "", f"{len(records)} recorded, {sum(r.resolved for r in records)} resolved. "
             "Each comes from a record: a failed tool run, a refused or sent-back submission, a block, a "
             "failure, or an escalation. A root cause appears only where one was recorded.", ""]
    for r in records:
        state_text = f"resolved: {r.resolution}" if r.resolved else "open"
        lines.append(f"- `{r.category.value}`" + (f" {r.subject}" if r.subject else "")
                     + f" on `{r.task}`: {r.summary} ({state_text})")
    w.text(f"{folder.id}/failures.md", lines)
    return ["failures.json", "failures.md"]

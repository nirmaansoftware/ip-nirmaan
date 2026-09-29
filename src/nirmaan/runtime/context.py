"""The work packet: everything an agent may know about one task, by scope.

Knowledge is assembled per task from four separate scopes, never mixed into
one prompt: company (constitution and standards), domain (the role's skills
and the VeriTriage Knowledge Packs they cite), project (requirement, analysis,
decisions, and approved upstream artifacts), and task (inputs, evidence
requirements, permitted tools). Each item says where it came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nirmaan.models import Assurance, MemoryScope, TaskStatus
from nirmaan.runtime.files import excerpt, read_verified
from nirmaan.work.engine import TaskEngine

#: The most of one file's content a packet carries.
MAX_CONTENT = 60_000


@dataclass(frozen=True)
class WorkPacket:
    task_id: str
    role: dict[str, Any]
    company: dict[str, Any]
    domain: dict[str, Any]
    project: dict[str, Any]
    task: dict[str, Any]
    tools: tuple[str, ...]
    memory: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def _artifact(art, trusted: bool | None = None, content: bool = False) -> dict[str, Any]:
    entry = {"id": art.id, "kind": art.kind, "title": art.title, "assurance": art.assurance.value,
             "summary": art.summary, "location": art.location, "digest": art.digest}
    if trusted is not None:
        entry["trusted"] = trusted
    if content and art.digest:
        # A recorded file is read only if its bytes still match what was recorded.
        text, problem = read_verified(art.location, art.digest)
        if text is not None and len(text) > MAX_CONTENT:
            text, problem = None, f"too large to include ({len(text)} characters)"
        entry["content"], entry["content_problem"] = text, problem
    return entry


def _failed_run(state, run_id: str, evidence: tuple[str, ...]) -> dict[str, Any]:
    """A refused attempt's failed run (M26): its evidence, and a bounded excerpt of its log."""
    run = state.tool_runs[run_id]
    log = run.references[0] if run.references else None
    lines, note = excerpt(log)
    return {"run": run.id, "tool": run.tool, "summary": run.summary, "log": log,
            "evidence": next((e for e in evidence if state.evidence[e].tool_run == run.id), None),
            "excerpt": lines, "excerpt_note": note}


def assemble(engine: TaskEngine, task_id: str, role: str | None = None) -> WorkPacket:
    """The packet for ``role``'s seat on a task: the owner by default, or e.g. its reviewer."""
    org, state = engine.org, engine.state
    task = engine.task(task_id)
    if task.owner is None:
        raise ValueError(f"{task_id} has no owner to assemble context for")
    seat = role or task.owner
    card = org.agent_card(seat)
    capability = org.capabilities.get(task.capability or "")

    skills = [org.skills[s] for s in task.skills if s in org.skills]
    if task.capability:
        skills += [s for s in org.providers_of(task.capability) if s.id in card["skills"] and s not in skills]
    domain = {
        "skills": [
            {
                "id": s.id,
                "name": s.name,
                "procedures": list(s.procedures),
                "constraints": list(s.constraints),
                "common_failure_modes": list(s.common_failure_modes),
                "validation_criteria": list(s.validation_criteria),
                "knowledge_sources": [f"{k.kind.value}:{k.ref}" for k in s.knowledge_sources],
            }
            for s in skills
        ],
    }

    upstream = []
    for dep in task.depends_on:
        for art_id in state.tasks[dep].artifacts:
            art = state.artifacts[art_id]
            approved = art.assurance is Assurance.APPROVED
            upstream.append(_artifact(art, trusted=approved, content=approved))
    evidence = [
        {"id": ev.id, "task": ev.task, "kind": ev.kind.value, "description": ev.description,
         "substantiated": ev.substantiated, "tool_run": ev.tool_run, "reference": ev.reference}
        for source in (*task.depends_on, task_id)
        for ev in (state.evidence[e] for e in state.tasks[source].evidence)
    ]
    attempts = [
        {"id": a.id, "number": a.number, "refusal": a.refusal, "reviews": list(a.reviews),
         "failed_runs": [_failed_run(state, run_id, a.evidence) for run_id in a.tool_runs
                         if run_id in state.tool_runs and not state.tool_runs[run_id].succeeded],
         "artifacts": [_artifact(art, content=True) for art in a.artifacts]}
        for a in sorted(state.attempts.values(), key=lambda a: a.number) if a.task == task_id
    ]
    memory = tuple(
        m.model_dump(mode="json")
        for m in state.memory
        if (m.scope is MemoryScope.PROJECT and m.owner == state.project.id)
        or (m.scope is MemoryScope.TASK and m.owner == task_id)
        or (m.scope is MemoryScope.AGENT and m.owner == seat)
        or (m.scope is MemoryScope.TEAM and task.unit and org.is_within(task.unit, m.owner))
    )
    return WorkPacket(
        task_id=task_id,
        role=card,
        company={
            "name": org.name,
            "constitution": [
                {"id": p.id, "title": p.title, "statement": p.statement} for p in org.principles.values()
            ],
        },
        domain=domain,
        project={
            "id": state.project.id,
            "requirement": state.project.requirement.text,
            "intent": state.project.analysis.intent,
            "features": list(state.project.analysis.features),
            "parameters": dict(state.project.analysis.parameters),
            "assumptions": [a.model_dump(mode="json") for a in state.project.analysis.assumptions],
            "decisions": [d.model_dump(mode="json") for d in state.decisions.values()],
        },
        task={
            "id": task.id,
            "title": task.title,
            "kind": task.kind.value,
            "status": task.status.value,
            "capability": task.capability,
            "expected_outputs": list(task.expected_outputs),
            "evidence_requirements": [r.model_dump(mode="json") for r in task.evidence_requirements],
            "outcomes": list(task.outcomes),
            "approved_inputs": bool(capability and capability.approved_inputs),
            "upstream_artifacts": upstream,
            "artifacts": [_artifact(state.artifacts[a], content=True) for a in task.artifacts],
            "evidence": evidence,
            "owner": task.owner,
            "reviewer": task.reviewer,
            "escalation_path": list(task.escalation_path),
            "attempts": attempts,
            "reviews": [{"id": r.id, "reviewer": r.reviewer, "verdict": r.verdict.value, "comments": r.comments}
                        for r in state.reviews.values() if r.task == task_id],
            "ready": task.status in (TaskStatus.READY, TaskStatus.IN_PROGRESS, TaskStatus.CHANGES_REQUESTED),
        },
        tools=tuple(card["tools"]),
        memory=memory,
    )

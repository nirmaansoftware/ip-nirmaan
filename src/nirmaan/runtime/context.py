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
from nirmaan.work.engine import TaskEngine


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


def assemble(engine: TaskEngine, task_id: str) -> WorkPacket:
    org, state = engine.org, engine.state
    task = engine.task(task_id)
    if task.owner is None:
        raise ValueError(f"{task_id} has no owner to assemble context for")
    card = org.agent_card(task.owner)

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
            upstream.append({
                "id": art.id,
                "kind": art.kind,
                "title": art.title,
                "assurance": art.assurance.value,
                "trusted": art.assurance is Assurance.APPROVED,
            })
    memory = tuple(
        m.model_dump(mode="json")
        for m in state.memory
        if (m.scope is MemoryScope.PROJECT and m.owner == state.project.id)
        or (m.scope is MemoryScope.TASK and m.owner == task_id)
        or (m.scope is MemoryScope.AGENT and m.owner == task.owner)
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
            "upstream_artifacts": upstream,
            "reviewer": task.reviewer,
            "escalation_path": list(task.escalation_path),
            "ready": task.status in (TaskStatus.READY, TaskStatus.IN_PROGRESS, TaskStatus.CHANGES_REQUESTED),
        },
        tools=tuple(card["tools"]),
        memory=memory,
    )

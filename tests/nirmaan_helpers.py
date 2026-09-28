"""Test helpers for IP Nirmaan: drive a project forward the honest way.

``drive`` moves tasks through the engine exactly as people would: owners start
and submit, independent reviewers review, authorized approvers approve, gate
owners (as humans when a gate requires it) sign off. Evidence is attached only
in forms the engine can substantiate: human attestations, the task's own
document artifact, or a real VeriTriage run. Nothing is faked, so a project
that completes under ``drive`` completed under the real rules.
"""

from __future__ import annotations

from pathlib import Path

from nirmaan.models import (
    Actor,
    ActorKind,
    EvidenceKind,
    ReviewState,
    TaskKind,
    TaskStatus,
    Verdict,
)
from nirmaan.runtime import ToolBroker
from nirmaan.work import TaskEngine
from nirmaan.work.policy import unsatisfied_requirements

FIXTURES = Path(__file__).parent / "fixtures"


def human(role: str) -> Actor:
    return Actor(role=role, kind=ActorKind.HUMAN, name="test")


def agent(role: str) -> Actor:
    return Actor(role=role, kind=ActorKind.AI_AGENT, name="test")


def tid(engine: TaskEngine, stage: str) -> str:
    return f"{engine.state.project.id}:{stage}"


def attach_evidence(engine: TaskEngine, task_id: str, workspace: Path | None = None) -> None:
    task = engine.task(task_id)
    owner = human(task.owner)
    for req in task.evidence_requirements:
        kinds = {k.value for k in req.accepts}
        if "review_record" in kinds and len(kinds) == 1:
            continue  # recorded by the review itself
        if "human_attestation" in kinds:
            engine.record_evidence(task_id, owner, EvidenceKind.HUMAN_ATTESTATION, f"attested: {req.description}")
        elif "document" in kinds and task.artifacts:
            engine.record_evidence(task_id, owner, EvidenceKind.DOCUMENT, req.description, reference=task.artifacts[0])
        elif "veritriage_session" in kinds:
            run, _ = ToolBroker(engine).invoke(
                owner, "veritriage.investigate",
                {"paths": str(FIXTURES / "axi_timeout.log"), "workspace": str(workspace or "/tmp/nirmaan-vt")},
                task_id,
            )
            engine.record_evidence(task_id, owner, EvidenceKind.VERITRIAGE_SESSION, run.summary,
                                   reference=run.references[0] if run.references else None, tool_run=run.id)


def work(engine: TaskEngine, task_id: str, outcome: str | None = None, workspace: Path | None = None) -> None:
    """Take one READY work/decision task all the way to COMPLETED."""
    task = engine.task(task_id)
    owner = agent(task.owner)
    engine.start(task_id, owner)
    if task.kind is TaskKind.DECISION:
        outcome = outcome or task.outcomes[0]
    produced = [{"kind": k, "title": f"{task.title} ({k})"} for k in (task.expected_outputs or ("note",))]
    engine.submit(task_id, owner, produced, outcome=outcome)
    task = engine.task(task_id)
    if task.status is TaskStatus.COMPLETED:
        return
    attach_evidence(engine, task_id, workspace)
    task = engine.task(task_id)
    if task.status is TaskStatus.COMPLETED:
        return
    if task.review_state is not ReviewState.NOT_REQUIRED:
        engine.review(task_id, agent(task.reviewer), Verdict.APPROVE, "looks right")
        engine.approve(task_id, agent(task.approver))
    else:
        missing = unsatisfied_requirements(engine.state, engine.task(task_id))
        raise AssertionError(f"{task_id} cannot complete: {missing}")


def approve_gate(engine: TaskEngine, task_id: str) -> None:
    task = engine.task(task_id)
    engine.approve_gate(task_id, human(task.owner) if task.human_required else agent(task.owner))


def drive(engine: TaskEngine, until: str | None = None, outcomes: dict[str, str] | None = None,
          workspace: Path | None = None, limit: int = 500) -> None:
    """Complete READY tasks in plan order until ``until`` is READY (or everything is done)."""
    outcomes = outcomes or {}
    for _ in range(limit):
        if until and engine.task(until).status is TaskStatus.READY:
            return
        ready = [t for t in engine.state.tasks.values()
                 if t.status is TaskStatus.READY and t.kind in (TaskKind.WORK, TaskKind.DECISION, TaskKind.GATE)]
        if not ready:
            return
        task = ready[0]
        if task.kind is TaskKind.GATE:
            approve_gate(engine, task.id)
        else:
            work(engine, task.id, outcomes.get(task.stage or ""), workspace)

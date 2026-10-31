"""The work packet: everything an agent may know about one task, by scope.

Knowledge is assembled per task from four separate scopes, never mixed into
one prompt: company (constitution and standards), domain (the role's skills,
the VeriTriage Knowledge Packs they cite, and the text of the knowledge
documents they cite, M61), project (requirement, analysis,
decisions, and approved upstream artifacts), and task (inputs, evidence
requirements, permitted tools). Each item says where it came from.

The packet is typed (M39): frozen models all the way down, so a renderer reads
attributes the type checker knows, never keys of an untyped dict.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from nirmaan.models import (
    Assumption,
    Assurance,
    Decision,
    EvidenceRequirement,
    MemoryEntry,
    MemoryScope,
    TaskStatus,
)
from nirmaan.org.knowledge import cited, over_domain_cap, read_document
from nirmaan.runtime.files import excerpt, read_verified
from nirmaan.work.engine import TaskEngine
from nirmaan.work.policy import upstream_artifacts

#: The most of one file's content a packet carries.
MAX_CONTENT = 60_000


class _View(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Authority(_View):
    decision: str
    criticality: str


class RoleCard(_View):
    """The seat's agent card (``Organization.agent_card``), typed."""

    id: str
    name: str
    kind: str
    runtime: str
    role: str
    level: str
    department: str
    division: str
    manager: str | None
    skills: dict[str, str]
    capabilities: dict[str, str]
    responsibilities: tuple[str, ...]
    authority: tuple[Authority, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    tools: tuple[str, ...]
    policies: tuple[str, ...]
    review_requirements: tuple[str, ...]
    escalation_targets: tuple[str, ...]
    quality_gates: tuple[str, ...]


class Principle(_View):
    id: str
    title: str
    statement: str


class CompanyScope(_View):
    name: str
    constitution: tuple[Principle, ...]


class SkillView(_View):
    id: str
    name: str
    procedures: tuple[str, ...]
    constraints: tuple[str, ...]
    common_failure_modes: tuple[str, ...]
    validation_criteria: tuple[str, ...]
    knowledge_sources: tuple[str, ...]


class KnowledgeDocumentView(_View):
    """A knowledge document a skill on the task cites (M61): its whole text and digest."""

    ref: str
    skill: str
    digest: str
    text: str


class DomainScope(_View):
    skills: tuple[SkillView, ...]
    #: The cited knowledge documents, whole, in skill order (M61).
    documents: tuple[KnowledgeDocumentView, ...] = ()
    #: Why the seat must decline this task (M61): a cited document missing, or over the domain cap.
    declines: str | None = None


class ProjectScope(_View):
    id: str
    requirement: str
    #: The requirement's record ID (M52): the record every task traces to, so every seat may cite it.
    requirement_id: str = ""
    intent: str | None
    features: tuple[str, ...]
    parameters: dict[str, int]
    assumptions: tuple[Assumption, ...]
    decisions: tuple[Decision, ...]


class ArtifactView(_View):
    """A recorded artifact; ``content`` only while its file still matches the recorded digest."""

    id: str
    kind: str
    title: str
    assurance: str
    summary: str
    location: str | None
    digest: str | None
    trusted: bool | None = None
    content: str | None = None
    content_problem: str | None = None


class EvidenceView(_View):
    id: str
    task: str | None
    kind: str
    description: str
    substantiated: bool
    tool_run: str | None
    reference: str | None


class FailedRun(_View):
    """A refused attempt's failed run (M26): its evidence, and a bounded excerpt of its log."""

    run: str
    tool: str
    summary: str
    log: str | None
    evidence: str | None
    excerpt: tuple[str, ...]
    excerpt_note: str


class AttemptView(_View):
    id: str
    number: int
    refusal: str
    reviews: tuple[str, ...]
    failed_runs: tuple[FailedRun, ...]
    artifacts: tuple[ArtifactView, ...]


class ReviewView(_View):
    id: str
    reviewer: str
    verdict: str
    comments: str


class TaskScope(_View):
    id: str
    title: str
    kind: str
    status: str
    capability: str | None
    expected_outputs: tuple[str, ...]
    model_needs: tuple[str, ...]
    evidence_requirements: tuple[EvidenceRequirement, ...]
    outcomes: tuple[str, ...]
    approved_inputs: bool
    upstream_artifacts: tuple[ArtifactView, ...]
    artifacts: tuple[ArtifactView, ...]
    evidence: tuple[EvidenceView, ...]
    owner: str | None
    reviewer: str | None
    escalation_path: tuple[str, ...]
    attempts: tuple[AttemptView, ...]
    reviews: tuple[ReviewView, ...]
    ready: bool


class WorkPacket(_View):
    task_id: str
    role: RoleCard
    company: CompanyScope
    domain: DomainScope
    project: ProjectScope
    task: TaskScope
    tools: tuple[str, ...]
    memory: tuple[MemoryEntry, ...] = ()


def _artifact(art, trusted: bool | None = None, content: bool = False) -> ArtifactView:
    entry = {}
    if content and art.digest:
        # A recorded file is read only if its bytes still match what was recorded.
        text, problem = read_verified(art.location, art.digest)
        if text is not None and len(text) > MAX_CONTENT:
            text, problem = None, f"too large to include ({len(text)} characters)"
        entry = {"content": text, "content_problem": problem}
    return ArtifactView(id=art.id, kind=art.kind, title=art.title, assurance=art.assurance.value,
                        summary=art.summary, location=art.location, digest=art.digest, trusted=trusted, **entry)


def _failed_run(state, run_id: str, evidence: tuple[str, ...]) -> FailedRun:
    """A refused attempt's failed run (M26): its evidence, and a bounded excerpt of its log."""
    run = state.tool_runs[run_id]
    log = run.references[0] if run.references else None
    lines, note = excerpt(log)
    return FailedRun(run=run.id, tool=run.tool, summary=run.summary, log=log,
                     evidence=next((e for e in evidence if state.evidence[e].tool_run == run.id), None),
                     excerpt=tuple(lines), excerpt_note=note)


def _documents(skills) -> tuple[tuple[KnowledgeDocumentView, ...], str | None]:
    """The knowledge documents the task's skills cite (M61), or none and why the seat declines.

    A document is carried whole or not at all: a missing one, or a total over
    the domain cap, empties the list and states the reason, never a cut.
    """
    found: dict[str, KnowledgeDocumentView] = {}
    for skill in skills:
        for ref in cited(skill):
            if ref in found:
                continue
            text, digest, problem = read_document(ref)
            if problem is not None:
                return (), f"{skill.id}: {problem}"
            found[ref] = KnowledgeDocumentView(ref=ref, skill=skill.id, digest=digest, text=text)
    over = over_domain_cap(sum(len(d.text) for d in found.values()))
    return ((), over) if over else (tuple(found.values()), None)


def assemble(engine: TaskEngine, task_id: str, role: str | None = None, *, knowledge: bool = True) -> WorkPacket:
    """The packet for ``role``'s seat on a task: the owner by default, or e.g. its reviewer.

    ``knowledge=False`` (M67, the ablation) leaves out the knowledge documents only: the skills, their
    cards and everything else are as with them, and nothing is declined for a document.
    """
    org, state = engine.org, engine.state
    task = engine.task(task_id)
    if task.owner is None:
        raise ValueError(f"{task_id} has no owner to assemble context for")
    seat = role or task.owner
    card = RoleCard.model_validate(org.agent_card(seat))
    capability = org.capabilities.get(task.capability or "")

    skills = [org.skills[s] for s in task.skills if s in org.skills]
    if task.capability:
        skills += [s for s in org.providers_of(task.capability) if s.id in card.skills and s not in skills]
    documents, declines = _documents(skills) if knowledge else ((), None)
    domain = DomainScope(skills=tuple(
        SkillView(id=s.id, name=s.name, procedures=s.procedures, constraints=s.constraints,
                  common_failure_modes=s.common_failure_modes, validation_criteria=s.validation_criteria,
                  knowledge_sources=tuple(f"{k.kind.value}:{k.ref}" for k in s.knowledge_sources))
        for s in skills
    ), documents=documents, declines=declines)

    upstream = []
    built_on = upstream_artifacts(state, task)  # M27: seen through gates
    for art in built_on:
        approved = art.assurance is Assurance.APPROVED
        upstream.append(_artifact(art, trusted=approved, content=approved))
    # M52: the upstream evidence is the evidence of the tasks whose artifacts it builds on, so through gates too.
    sources = dict.fromkeys((*(art.task for art in built_on), task_id))
    evidence = tuple(
        EvidenceView(id=ev.id, task=ev.task, kind=ev.kind.value, description=ev.description,
                     substantiated=ev.substantiated, tool_run=ev.tool_run, reference=ev.reference)
        for source in sources
        for ev in (state.evidence[e] for e in state.tasks[source].evidence)
    )
    attempts = tuple(
        AttemptView(id=a.id, number=a.number, refusal=a.refusal, reviews=a.reviews,
                    failed_runs=tuple(_failed_run(state, run_id, a.evidence) for run_id in a.tool_runs
                                      if run_id in state.tool_runs and not state.tool_runs[run_id].succeeded),
                    artifacts=tuple(_artifact(art, content=True) for art in a.artifacts))
        for a in sorted(state.attempts.values(), key=lambda a: a.number) if a.task == task_id
    )
    memory = tuple(
        m
        for m in state.memory
        if (m.scope is MemoryScope.PROJECT and m.owner == state.project.id)
        or (m.scope is MemoryScope.TASK and m.owner == task_id)
        or (m.scope is MemoryScope.AGENT and m.owner == seat)
        or (m.scope is MemoryScope.TEAM and task.unit and org.is_within(task.unit, m.owner))
    )
    analysis = state.project.analysis
    return WorkPacket(
        task_id=task_id,
        role=card,
        company=CompanyScope(
            name=org.name,
            constitution=tuple(Principle(id=p.id, title=p.title, statement=p.statement)
                               for p in org.principles.values()),
        ),
        domain=domain,
        project=ProjectScope(
            id=state.project.id,
            requirement=state.project.requirement.text,
            requirement_id=state.project.requirement.id,
            intent=analysis.intent,
            features=tuple(analysis.features),
            parameters=dict(analysis.parameters),
            assumptions=analysis.assumptions,
            decisions=tuple(state.decisions.values()),
        ),
        task=TaskScope(
            id=task.id,
            title=task.title,
            kind=task.kind.value,
            status=task.status.value,
            capability=task.capability,
            expected_outputs=tuple(task.expected_outputs),
            model_needs=tuple(str(n) for n in capability.model_needs) if capability else (),
            evidence_requirements=tuple(task.evidence_requirements),
            outcomes=tuple(task.outcomes),
            approved_inputs=bool(capability and capability.approved_inputs),
            upstream_artifacts=tuple(upstream),
            artifacts=tuple(_artifact(state.artifacts[a], content=True) for a in task.artifacts),
            evidence=evidence,
            owner=task.owner,
            reviewer=task.reviewer,
            escalation_path=tuple(task.escalation_path),
            attempts=attempts,
            reviews=tuple(ReviewView(id=r.id, reviewer=r.reviewer, verdict=r.verdict.value, comments=r.comments)
                          for r in state.reviews.values() if r.task == task_id),
            ready=task.status in (TaskStatus.READY, TaskStatus.IN_PROGRESS, TaskStatus.CHANGES_REQUESTED),
        ),
        tools=card.tools,
        memory=memory,
    )

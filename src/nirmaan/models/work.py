"""Work vocabulary: requirements, projects, tasks, artifacts, evidence, audit.

The distinction the whole platform is built around lives here as types, not
conventions: an artifact's :class:`Assurance` says whether it is merely
planned, actually executed, verified by recorded evidence, or approved by an
authorized, independent role. Nothing may skip a rung.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nirmaan.models.governance import Criticality, DecisionKind, EscalationKind
from nirmaan.models.org import ActorKind
from nirmaan.models.workflow import EvidenceKind, EvidenceRequirement, OnFailure


class Actor(BaseModel):
    """Who performed an action: a role, plus what kind of worker filled it."""

    model_config = ConfigDict(frozen=True)

    role: str
    kind: ActorKind = ActorKind.AI_AGENT
    name: str = ""

    @property
    def label(self) -> str:
        who = self.name or self.kind.value
        return f"{who}@{self.role}"


class Requirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    text: str
    submitted_by: str = "owner"


class Assumption(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    note: str
    question: str
    assumed_features: tuple[str, ...] = ()


class RequirementAnalysis(BaseModel):
    """What the organization understood, and exactly why."""

    model_config = ConfigDict(frozen=True)

    requirement_id: str
    intent: str | None
    intent_evidence: tuple[str, ...] = Field(default=(), description="Matched phrases.")
    features: tuple[str, ...] = ()
    feature_evidence: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    parameters: dict[str, int] = Field(default_factory=dict)
    assumptions: tuple[Assumption, ...] = ()
    unrecognized: bool = Field(
        default=False, description="No intent matched: an honest miss, never a guess."
    )


class TaskKind(str, Enum):
    PROGRAM = "program"
    WORKSTREAM = "workstream"
    WORK = "work"
    DECISION = "decision"
    GATE = "gate"


class TaskStatus(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED)

    @property
    def is_active(self) -> bool:
        return self in (
            TaskStatus.IN_PROGRESS,
            TaskStatus.IN_REVIEW,
            TaskStatus.CHANGES_REQUESTED,
        )


class ReviewState(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    PASSED = "passed"
    CHANGES_REQUESTED = "changes_requested"
    CONFLICTED = "conflicted"


class ApprovalState(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    GRANTED = "granted"


class EscalationState(str, Enum):
    NONE = "none"
    OPEN = "open"
    RESOLVED = "resolved"


class Assurance(str, Enum):
    """planned < executed < verified < approved. The platform's core distinction."""

    PLANNED = "planned"
    EXECUTED = "executed"
    VERIFIED = "verified"
    APPROVED = "approved"

    @property
    def rank(self) -> int:
        return list(Assurance).index(self)


class RoutingCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str
    score: float
    reasons: tuple[str, ...] = ()


class RoutingDecision(BaseModel):
    """Why this role owns (or reviews) this task: the candidates and the rule."""

    model_config = ConfigDict(frozen=True)

    capability: str
    chosen: str | None
    rationale: str
    candidates: tuple[RoutingCandidate, ...] = ()


class Task(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    kind: TaskKind
    project: str
    description: str = ""
    phase: str = ""
    workflow: str | None = None
    stage: str | None = None
    parent: str | None = None
    depends_on: tuple[str, ...] = ()
    requirement: str = Field(description="Traceability: the requirement this serves.")

    capability: str | None = None
    skills: tuple[str, ...] = ()
    owner: str | None = Field(default=None, description="Owning role.")
    reviewer: str | None = None
    approver: str | None = None
    unit: str | None = Field(default=None, description="Owning unit (the authority domain).")
    escalation_path: tuple[str, ...] = ()
    owner_routing: RoutingDecision | None = None
    reviewer_routing: RoutingDecision | None = None

    criticality: Criticality = Criticality.MEDIUM
    priority: int = Field(default=50, ge=0, description="Lower is more urgent.")
    risk: str = ""
    inputs: tuple[str, ...] = Field(default=(), description="Artifact kinds consumed.")
    expected_outputs: tuple[str, ...] = ()
    evidence_requirements: tuple[EvidenceRequirement, ...] = ()
    gate: str | None = None
    human_required: bool = False
    outcomes: tuple[str, ...] = ()
    branch: tuple[str, str] | None = None

    status: TaskStatus = TaskStatus.PLANNED
    review_state: ReviewState = ReviewState.PENDING
    approval_state: ApprovalState = ApprovalState.PENDING
    escalation_state: EscalationState = EscalationState.NONE
    outcome: str | None = Field(default=None, description="Recorded decision outcome.")
    artifacts: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    attempts: int = 0
    max_retries: int = 1
    on_failure: OnFailure = OnFailure.RETRY_THEN_ESCALATE
    blocked_reason: str | None = None
    status_before_escalation: TaskStatus | None = None


class Artifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    title: str
    task: str
    produced_by: str = Field(description="Actor label, for provenance.")
    assurance: Assurance = Assurance.EXECUTED
    location: str | None = None
    summary: str = Field(default="", description="The written content, e.g. an agent's cited report.")
    digest: str | None = Field(default=None, description="'sha256:<hex>' of the file at location, when it is one.")
    evidence: tuple[str, ...] = ()
    derived_from: tuple[str, ...] = Field(default=(), description="Upstream artifact IDs.")


class Attempt(BaseModel):
    """A submission the engine refused, kept on the record (M26). Nothing in it ever counts.

    Its files are full :class:`Artifact` records (location, digest, provenance)
    held here rather than in ``ProjectState.artifacts``, so nothing that
    reviews, verifies, approves, exports, or links artifacts can see them.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    task: str
    number: int = Field(ge=1, description="Counts every refused attempt recorded on the task.")
    actor: str
    refusal: str = Field(description="The engine's reason for refusing the submission.")
    tool_runs: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    artifacts: tuple[Artifact, ...] = ()


class ToolRun(BaseModel):
    """A brokered tool invocation. The only thing a TOOL_RUN evidence may cite."""

    model_config = ConfigDict(frozen=True)

    id: str
    tool: str
    actor: str
    task: str | None
    params: dict[str, str] = Field(default_factory=dict)
    succeeded: bool
    summary: str
    references: tuple[str, ...] = ()


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: EvidenceKind
    description: str
    task: str | None
    recorded_by: str
    reference: str | None = Field(default=None, description="Session ID, path, or review ID.")
    tool_run: str | None = None
    #: True only when the platform itself can stand behind it: a successful
    #: brokered tool run, a recorded review, or a named human's attestation.
    substantiated: bool = False


class Verdict(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"


class ReviewRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    task: str
    reviewer: str
    verdict: Verdict
    comments: str = ""


class Escalation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    task: str | None
    kind: EscalationKind
    raised_by: str
    target_role: str
    reason: str
    context: str = ""
    attempted_actions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    blocking_question: str = ""
    recommended_options: tuple[str, ...] = ()
    state: EscalationState = EscalationState.OPEN
    resolution: str | None = None
    resolved_by: str | None = None
    supersedes: str | None = Field(default=None, description="Escalation this one re-raises.")


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: DecisionKind
    criticality: Criticality
    statement: str
    rationale: str
    made_by: str
    task: str | None = None
    evidence: tuple[str, ...] = ()


class MemoryScope(str, Enum):
    COMPANY = "company"
    PROJECT = "project"
    TEAM = "team"
    TASK = "task"
    AGENT = "agent"


class MemoryEntry(BaseModel):
    """Structured memory with provenance. Never conversational residue."""

    model_config = ConfigDict(frozen=True)

    scope: MemoryScope
    owner: str = Field(description="Project, team unit, task, or agent ID.")
    key: str
    value: str
    recorded_by: str
    source_task: str | None = None
    evidence: tuple[str, ...] = ()


class AuditEntry(BaseModel):
    """One hash-chained audit record: who, what, when, why."""

    model_config = ConfigDict(frozen=True)

    sequence: int
    at: datetime
    actor: str
    actor_kind: ActorKind
    action: str
    subject: str
    reason: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str
    hash: str


class SpecRequirement(BaseModel):
    """A requirement quoted from a specification artifact, so verification can prove it (M24)."""

    model_config = ConfigDict(frozen=True)

    id: str
    text: str
    source: str = Field(description="The artifact it is quoted from, e.g. the interface spec.")
    section: str = ""
    recorded_by: str


class VerificationItem(BaseModel):
    """A test, assertion, or coverage point, and the requirements it is declared to prove (M24).

    A declaration of intent: it backs nothing on its own. Only a passing,
    substantiated run over the file that holds it does.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str = Field(description="A registered verification-item kind, e.g. 'test'.")
    name: str = Field(description="The test, check label, property, or cover point, as it appears in the file.")
    artifact: str = Field(description="The located artifact whose file holds the item.")
    proves: tuple[str, ...]
    rationale: str = ""
    recorded_by: str


class Project(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    program: str
    requirement: Requirement
    analysis: RequirementAnalysis
    workflows: tuple[str, ...]
    organization_fingerprint: str
    gate_overrides: dict[str, bool] = Field(
        default_factory=dict, description="Gate ID -> human approval required."
    )
    created_at: datetime


class ProjectState(BaseModel):
    """Everything about one project. Replaced wholesale, never edited in place."""

    model_config = ConfigDict(frozen=True)

    project: Project
    tasks: dict[str, Task]
    artifacts: dict[str, Artifact] = Field(default_factory=dict)
    evidence: dict[str, Evidence] = Field(default_factory=dict)
    tool_runs: dict[str, ToolRun] = Field(default_factory=dict)
    reviews: dict[str, ReviewRecord] = Field(default_factory=dict)
    escalations: dict[str, Escalation] = Field(default_factory=dict)
    decisions: dict[str, Decision] = Field(default_factory=dict)
    memory: list[MemoryEntry] = Field(default_factory=list)
    audit: list[AuditEntry] = Field(default_factory=list)
    spec_requirements: dict[str, SpecRequirement] = Field(default_factory=dict)
    verification_items: dict[str, VerificationItem] = Field(default_factory=dict)
    attempts: dict[str, Attempt] = Field(default_factory=dict)
    schema_version: str = "1"

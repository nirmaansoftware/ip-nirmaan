"""Workflow and requirement-analysis vocabulary.

A workflow is a reusable engineering process (new IP, RTL change, timing
closure), declared as stages with dependencies, conditions, branches, review
requirements, and gates. The orchestrator instantiates one into a task graph;
nothing in it names a department or a person, only capabilities.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from nirmaan.models.governance import Criticality
from nirmaan.models.org import Level


class EvidenceKind(str, Enum):
    """What can back a claim. Ordered from strongest to weakest."""

    #: A tool invocation brokered and recorded by the platform.
    TOOL_RUN = "tool_run"
    #: A VeriTriage investigation session (itself backed by an Evidence Graph).
    VERITRIAGE_SESSION = "veritriage_session"
    #: An independent review recorded by the task engine.
    REVIEW_RECORD = "review_record"
    #: A named human attesting to something the platform cannot observe.
    HUMAN_ATTESTATION = "human_attestation"
    #: A document or artifact reference.
    DOCUMENT = "document"
    #: An unbacked statement. Recorded for honesty; satisfies no requirement.
    CLAIM = "claim"


class FileInput(BaseModel):
    """One tool parameter filled from the files the task itself produced (M23)."""

    model_config = ConfigDict(frozen=True)

    param: str = Field(description="The tool parameter to fill, e.g. 'sources'.")
    kinds: tuple[str, ...] = Field(description="Artifact kinds whose files feed it, in this order.")
    entry: bool = Field(
        default=False,
        description="Pass the entry point the first such file declares (e.g. its top module), not paths.",
    )
    upstream: bool = Field(
        default=False,
        description="Fill from the approved upstream artifacts of these kinds (M25), not the task's own files.",
    )


class EvidenceRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: str
    accepts: tuple[EvidenceKind, ...] = Field(
        description="Evidence kinds that satisfy it. CLAIM is never accepted."
    )
    tools: tuple[str, ...] = Field(
        default=(),
        description="For tool-backed kinds: the tools whose runs count. Empty means any.",
    )
    files: tuple[FileInput, ...] = Field(
        default=(),
        description="Run the tools over the task's own produced files, filling these parameters.",
    )
    before_review: bool = Field(
        default=False,
        description="Must be met, over the files submitted, before the work may be submitted for review.",
    )
    params: tuple[tuple[str, str], ...] = Field(
        default=(),
        description="Fixed tool parameters (M26); a run counts only if it was made with every one of them.",
    )
    when_produced: tuple[str, ...] = Field(
        default=(),
        description="Applies only when the task produced an artifact of one of these kinds (M26). Empty: always.",
    )
    when: "Condition" = Field(
        default_factory=lambda: Condition(),
        description="Planned only when the request's features meet this condition (M27). Default: always.",
    )

    def applies(self, kinds) -> bool:
        """Whether the requirement binds work that produced artifacts of these ``kinds``."""
        return not self.when_produced or any(k in self.when_produced for k in kinds)


class ReviewRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability: str = Field(description="Review capability the reviewer must hold.")
    min_level: Level = Level.SENIOR
    independent: bool = Field(default=True, description="Reviewer may not be the owner.")


class Condition(BaseModel):
    """When a stage (or variant) applies, in terms of requirement features."""

    model_config = ConfigDict(frozen=True)

    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()
    none_of: tuple[str, ...] = ()

    def holds(self, features: frozenset[str] | set[str]) -> bool:
        return (
            all(f in features for f in self.all_of)
            and (not self.any_of or any(f in features for f in self.any_of))
            and not any(f in features for f in self.none_of)
        )

    @property
    def is_unconditional(self) -> bool:
        return not (self.all_of or self.any_of or self.none_of)


EvidenceRequirement.model_rebuild()


class Variant(BaseModel):
    """Fan-out: one task per applicable variant of a stage."""

    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    when: Condition = Condition()
    skills: tuple[str, ...] = Field(default=(), description="Extra skills that refine routing.")


class OnFailure(str, Enum):
    RETRY_THEN_ESCALATE = "retry_then_escalate"
    ESCALATE = "escalate"
    FAIL = "fail"


class StageTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    phase: str = Field(description="Workstream grouping, e.g. 'Architecture', 'RTL'.")
    capability: str = Field(description="Execution capability the owner must hold.")
    description: str = ""
    skills: tuple[str, ...] = Field(default=(), description="Skills that refine routing.")
    depends_on: tuple[str, ...] = ()
    when: Condition = Condition()
    variants: tuple[Variant, ...] = ()
    criticality: Criticality = Criticality.MEDIUM
    review: ReviewRequirement | None = None
    gate: str | None = Field(default=None, description="Gate ID this stage closes.")
    outputs: tuple[str, ...] = ()
    evidence: tuple[EvidenceRequirement, ...] = ()
    max_retries: int = Field(default=1, ge=0)
    on_failure: OnFailure = OnFailure.RETRY_THEN_ESCALATE
    #: Overrides the capability's limits for this stage (M27); None inherits them.
    max_attempts: int | None = Field(default=None, ge=1)
    max_review_rounds: int | None = Field(default=None, ge=1)
    #: Continuity of ownership: this stage is owned by whoever owns that stage
    #: (e.g. "merge" by the author of the change), if they hold the capability.
    owner_from: str | None = None
    #: A decision stage: its owner records one of these outcomes when done.
    outcomes: tuple[str, ...] = ()
    #: Branch membership: (decision stage ID, outcome). Instantiated as a
    #: candidate branch; the stages on untaken branches are cancelled when the
    #: decision is recorded.
    branch: tuple[str, str] | None = None


class WorkflowTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str
    intents: tuple[str, ...] = Field(description="Requirement intents this workflow serves.")
    stages: tuple[StageTemplate, ...]
    version: str = "1"
    lead_capability: str = Field(
        default="program.plan", description="Capability that owns the program root task."
    )
    workstream_capability: str = Field(
        default="mgmt.plan", description="Capability that owns each phase workstream."
    )

    def stage(self, stage_id: str) -> StageTemplate | None:
        return next((s for s in self.stages if s.id == stage_id), None)


# --- Requirement-analysis vocabulary -----------------------------------------


class IntentRule(BaseModel):
    """A declared phrase shape that identifies what kind of request this is."""

    model_config = ConfigDict(frozen=True)

    intent: str
    patterns: tuple[str, ...] = Field(description="Case-insensitive regexes.")
    priority: int = Field(default=50, description="Lower wins when several match.")
    description: str = ""


class FeatureRule(BaseModel):
    """A declared marker that the requirement touches a technical feature."""

    model_config = ConfigDict(frozen=True)

    feature: str
    patterns: tuple[str, ...]
    implies: tuple[str, ...] = ()
    skills: tuple[str, ...] = Field(
        default=(), description="Skills this feature brings into play; routing prefers holders."
    )
    description: str = ""


class ParameterRule(BaseModel):
    """Extracts a named numeric parameter. First capture group is the value."""

    model_config = ConfigDict(frozen=True)

    name: str
    patterns: tuple[str, ...]
    unit: str = ""


class AssumptionRule(BaseModel):
    """What the organization assumes when a requirement is silent.

    Recorded on the analysis as an explicit, reviewable assumption, never
    silently folded in: principle 3, uncertainty is represented.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    applies_to_intents: tuple[str, ...] = ()
    when: Condition = Condition()
    assume_features: tuple[str, ...] = ()
    note: str
    question: str = Field(description="The question a human should answer to settle it.")

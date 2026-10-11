"""Workflow and requirement-analysis vocabulary.

A workflow is a reusable engineering process (new IP, RTL change, timing
closure), declared as stages with dependencies, conditions, branches, review
requirements, and gates. The orchestrator instantiates one into a task graph;
nothing in it names a department or a person, only capabilities.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nirmaan.models.governance import Criticality
from nirmaan.models.limits import Limits, migrate_limits
from nirmaan.models.org import Level, text_value


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
    optional: bool = Field(
        default=False,
        description="An upstream binding left out when no approved upstream file of these kinds exists (M41). "
                    "When one exists, a passing run must still have used it. Per parameter, not a condition on "
                    "the requirement; decided by the one evaluator over the available inputs (M48).",
    )


class ConditionPhase(str, Enum):
    """When a condition kind's facts are known (M48)."""

    #: From the request, when the work is planned (its features, say).
    PLAN = "plan"
    #: From the work, when it runs or is submitted (the kinds it produced, say).
    RUN = "run"


class Condition(BaseModel):
    """When something applies: a test over one set of facts (M48: one condition type).

    ``on`` names a registered condition kind (``nirmaan.applicability``): the
    request's ``features`` (the default, and the only kind before M48), the
    kinds the task ``produced``, the kinds it builds on (``upstream``), the
    approved upstream files available to it (``inputs``), or any kind an
    extension registers. The kind declares its phase.
    """

    model_config = ConfigDict(frozen=True)

    on: str = Field(default="features", description="The condition kind whose facts this tests.")
    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()
    none_of: tuple[str, ...] = ()

    def holds(self, facts: frozenset[str] | set[str]) -> bool:
        return (
            all(f in facts for f in self.all_of)
            and (not self.any_of or any(f in facts for f in self.any_of))
            and not any(f in facts for f in self.none_of)
        )

    @property
    def is_unconditional(self) -> bool:
        return not (self.all_of or self.any_of or self.none_of)


class Bound(BaseModel):
    """A limit on a metric a tool run reports (M48), e.g. latches <= 0.

    A passing run fails when the metric breaks it, or was never reported.
    """

    model_config = ConfigDict(frozen=True)

    metric: str
    op: Literal["max", "min"]
    value: float

    @property
    def label(self) -> str:
        """How failures name it, as they did when bounds were ``max_``/``min_`` parameters."""
        return f"{self.op}_{self.metric}"

    def __str__(self) -> str:
        return f"{self.metric}{'<=' if self.op == 'max' else '>='}{text_value(self.value)}"

    @classmethod
    def parse(cls, text: str) -> "Bound":
        """``metric<=value`` or ``metric>=value``, the one text form (the CLI's ``--bound``)."""
        for sign, op in (("<=", "max"), (">=", "min")):
            metric, found, value = text.partition(sign)
            if found and metric.strip().isidentifier():
                try:
                    return cls(metric=metric.strip(), op=op, value=float(value))
                except ValueError:
                    raise ValueError(f"the bound {text!r} needs a number") from None
        raise ValueError(f"a bound reads metric<=value or metric>=value, not {text!r}")

    def problem(self, metrics: dict[str, Any]) -> str | None:
        """Why a passing run with these metrics breaks this bound, or None."""
        measured = metrics.get(self.metric)
        if isinstance(measured, bool) or not isinstance(measured, (int, float)):
            return f"{self.metric} was not reported, so {self.label} cannot be checked"
        if self.op == "max" and measured > self.value:
            return f"{self.metric} {measured} exceeds {self.label} {text_value(self.value)}"
        if self.op == "min" and measured < self.value:
            return f"{self.metric} {measured} is below {self.label} {text_value(self.value)}"
        return None


def _legacy_bound(key: str, value: Any) -> Bound | None:
    """A fixed ``max_<metric>``/``min_<metric>`` parameter, as data written before M48 set a bound."""
    if key[:4] not in ("max_", "min_") or len(key) == 4:
        return None
    try:
        number = float(text_value(value))
    except ValueError:
        return None
    return Bound(metric=key[4:], op=key[:3], value=number)


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
    bounds: tuple[Bound, ...] = Field(
        default=(),
        description="Limits on the metrics a run reports (M48); a run counts only if it was checked against each.",
    )
    when: tuple[Condition, ...] = Field(
        default=(),
        description="Applies only when every clause holds, each decided in its kind's phase (M48). Empty: always.",
    )
    yields: tuple[tuple[str, str], ...] = Field(
        default=(),
        description="Files a passing run writes that become the task's artifacts (M44), as (artifact kind, the "
                    "run's output name) pairs: such an artifact must be the very file a passing run wrote.",
    )

    @model_validator(mode="before")
    @classmethod
    def _old_form(cls, data: Any) -> Any:
        """Data written before M48: one ``when``, ``when_produced``, ``when_upstream``, and bound parameters.

        They become clauses (features, then produced, then upstream) and bounds
        (docs/UNIFIED_APPLICABILITY.md, section 3).
        """
        if not isinstance(data, dict):
            return data
        data = dict(data)
        when = data.get("when", ())
        clauses = [when] if isinstance(when, (Condition, dict)) else list(when or ())
        for field, on in (("when_produced", "produced"), ("when_upstream", "upstream")):
            kinds = tuple(data.pop(field, ()) or ())
            if kinds:
                clauses.append(Condition(on=on, any_of=kinds))
        data["when"] = tuple(c for c in clauses
                             if not (Condition.model_validate(c) if isinstance(c, dict) else c).is_unconditional)
        params, bounds = [], list(data.get("bounds", ()) or ())
        for key, value in data.get("params", ()) or ():
            bound = _legacy_bound(key, value)
            if bound is None:
                params.append((key, value))
            else:
                bounds.append(bound)
        if len(params) != len(data.get("params", ()) or ()):
            data["params"], data["bounds"] = tuple(params), tuple(bounds)
        return data


class ReviewRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability: str = Field(description="Review capability the reviewer must hold.")
    min_level: Level = Level.SENIOR
    independent: bool = Field(default=True, description="Reviewer may not be the owner.")


class Variant(BaseModel):
    """Fan-out: one task per applicable variant of a stage."""

    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    when: Condition = Condition()
    skills: tuple[str, ...] = Field(default=(), description="Extra skills that refine routing.")


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
    #: Overrides the capability's limits for this stage (M27, M48); a field left None inherits them.
    limits: Limits = Field(default_factory=Limits)
    #: Continuity of ownership: this stage is owned by whoever owns that stage
    #: (e.g. "merge" by the author of the change), if they hold the capability.
    owner_from: str | None = None
    #: A decision stage: its owner records one of these outcomes when done.
    outcomes: tuple[str, ...] = ()
    #: Branch membership: (decision stage ID, outcome). Instantiated as a
    #: candidate branch; the stages on untaken branches are cancelled when the
    #: decision is recorded.
    branch: tuple[str, str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _old_limits(cls, data: Any) -> Any:
        """``max_retries``, ``on_failure``, ``max_attempts`` and ``max_review_rounds``, as written before M48."""
        return migrate_limits(data)


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

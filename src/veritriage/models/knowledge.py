"""Models for the knowledge context that travels inside an AnalysisReport.

These are *views*: what the Knowledge Engine concluded about one regression,
flattened for the report. The knowledge itself (packs, patterns, state
machines, playbooks) lives in ``veritriage.knowledge``; this module stays
import-light so the models package never grows upward dependencies.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeReference(BaseModel):
    """A pointer into a specification, guideline, or engineering note."""

    source: str = Field(description="Document or standard, e.g. 'AMBA AXI Specification'.")
    section: str | None = Field(default=None, description="Section/rule, e.g. 'A3.2.1'.")
    note: str | None = Field(default=None, description="Why this reference is relevant.")
    uri: str | None = Field(
        default=None,
        description="Resolved link into external documentation, when a resolver knew one.",
    )


class MatchedConcept(BaseModel):
    """A verification concept the evidence touches."""

    concept_id: str
    name: str
    pack: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


class PlaybookStepView(BaseModel):
    """One deterministic debug step, in execution order."""

    order: int = Field(ge=1)
    action: str
    detail: str | None = None
    signals: list[str] = Field(
        default_factory=list, description="Waveform/RTL signals worth pulling up for this step."
    )


class PlaybookView(BaseModel):
    """A structured debug playbook attached to a matched pattern."""

    playbook_id: str
    name: str
    pack: str
    steps: list[PlaybookStepView] = Field(default_factory=list)


class MatchedPattern(BaseModel):
    """One known failure pattern the evidence deterministically matched."""

    pattern_id: str
    name: str
    pack: str
    pack_version: str
    score: float = Field(ge=0.0, le=1.0, description="Match strength; 1.0 = every clause matched.")
    summary: str
    matched_evidence: dict[str, list[str]] = Field(
        default_factory=dict, description="Requirement name -> matching evidence node IDs."
    )
    typical_causes: list[str] = Field(default_factory=list)
    ownership: str = Field(description="Who usually owns this failure class, e.g. 'design'.")
    suggested_signals: list[str] = Field(default_factory=list)
    references: list[KnowledgeReference] = Field(default_factory=list)
    playbook: PlaybookView | None = None


class StateProgress(BaseModel):
    """One protocol state and whether the evidence shows it was reached."""

    state: str
    description: str | None = None
    reached: bool
    evidence_ids: list[str] = Field(default_factory=list)


class StateProjection(BaseModel):
    """Evidence projected onto a protocol state machine: where progress stopped."""

    machine_id: str
    name: str
    pack: str
    states: list[StateProgress] = Field(default_factory=list)
    stopped_at: str | None = Field(
        default=None, description="First expected state the evidence never reached."
    )


class KnowledgeContext(BaseModel):
    """Everything the Knowledge Engine concluded about this regression.

    Produced deterministically before (and independently of) any AI; the AI
    explanation layer may reference these conclusions but never creates them.
    """

    pack_versions: dict[str, str] = Field(
        default_factory=dict, description="Knowledge pack id -> version used for this analysis."
    )
    concepts: list[MatchedConcept] = Field(default_factory=list)
    patterns: list[MatchedPattern] = Field(
        default_factory=list, description="Matched failure patterns, strongest first."
    )
    state_projection: StateProjection | None = None
    historical_note: str | None = Field(
        default=None, description="How the regression database supports the matched patterns."
    )

    @property
    def is_empty(self) -> bool:
        return not (self.concepts or self.patterns or self.state_projection)

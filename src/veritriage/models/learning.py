"""Learning Engine vocabulary (Milestone 13).

The artifacts the Learning Engine derives from recorded history, and the
context it hands forward to agents and the report. Like every model in this
package these are plain data importing nothing from the graph or engine
layers.

Everything here is deliberately explainable: an artifact carries how many
observations support it, which regressions those were, and a plain-language
summary. There are no vectors, no model weights, and no hidden state, so any
learned claim can be printed and argued with.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LearningArtifact(BaseModel):
    """Base for every learned record.

    ``supporting_regressions`` is what makes learning auditable: every claim
    links back to the investigations that produced it, so an engineer can open
    the evidence behind a hint rather than trusting it.
    """

    artifact_id: str = Field(description="Stable ID, e.g. 'lp-agent_reliability-protocol'.")
    kind: str = Field(description="Artifact family, e.g. 'agent_reliability'.")
    schema_version: str = "1"
    key: str = Field(description="What this artifact is about (signature, agent ID, action, ...).")
    summary: str = Field(description="Plain-language statement of what was learned.")
    observations: int = Field(ge=0, description="How many recorded runs support this artifact.")
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How much support this artifact has, from its observation count.",
    )
    supporting_regressions: list[str] = Field(
        default_factory=list, description="Regression IDs this was learned from (bounded sample)."
    )
    updated_at: str = Field(default="", description="ISO timestamp of the last recomputation.")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Kind-specific plain data; never opaque."
    )


class InvestigationPattern(LearningArtifact):
    """A recurring failure mode, its confirmed causes, and what fixed it."""

    kind: str = "investigation_pattern"
    signature: str = ""
    classification: str = ""
    confirmed_root_causes: list[str] = Field(default_factory=list)
    successful_actions: list[str] = Field(
        default_factory=list, description="Recommendation actions engineers voted useful."
    )
    typical_modules: list[str] = Field(default_factory=list)


class EvidencePattern(LearningArtifact):
    """A co-occurring evidence combination and what it historically meant."""

    kind: str = "evidence_pattern"
    signal_set: list[str] = Field(
        default_factory=list, description="The deterministic signals that fired together."
    )
    dominant_classification: str = ""
    share: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Fraction of occurrences with that outcome."
    )


class AgentReliability(LearningArtifact):
    """How often one specialist's leading position matched the real outcome."""

    kind: str = "agent_reliability"
    agent_id: str = ""
    times_applicable: int = 0
    times_led: int = 0
    times_correct: int = 0
    accuracy: float | None = Field(
        default=None, description="times_correct / times_led; None until the agent has led."
    )
    calibration_multiplier: float = Field(
        default=1.0, description="Bounded influence multiplier applied by the Coordinator."
    )


class ProjectProfile(LearningArtifact):
    """What a project characteristically looks like, learned over its runs."""

    kind: str = "project_profile"
    project_key: str = ""
    dominant_classifications: list[str] = Field(default_factory=list)
    common_modules: list[str] = Field(default_factory=list)
    protocols: list[str] = Field(default_factory=list)
    recurring_signatures: list[str] = Field(default_factory=list)
    verification_maturity: str = Field(
        default="unknown",
        description="Explainable label derived from corpus size and the unexplained-failure rate.",
    )


class ProtocolStatistics(LearningArtifact):
    """How much one Knowledge Pack's patterns actually earn their place."""

    kind: str = "protocol_statistics"
    pack: str = ""
    times_matched: int = 0
    times_with_confirmation: int = 0
    pattern_ids: list[str] = Field(default_factory=list)


class RecommendationOutcome(LearningArtifact):
    """Whether a recommendation historically helped or wasted time."""

    kind: str = "recommendation_outcome"
    action: str = ""
    useful_votes: int = 0
    false_votes: int = 0
    usefulness: float | None = Field(
        default=None, description="useful / (useful + false); None without votes."
    )


class RuleGap(LearningArtifact):
    """A failure signature the deterministic rules keep getting wrong.

    Not a conclusion and not a correction: a bounded, auditable statement
    that engineers overruled the platform on this signature often enough
    that a missing rule or pack pattern is the likely explanation. What to
    do about it stays a human decision.
    """

    kind: str = "rule_gap"
    signature: str = ""
    classification: str = Field(
        default="", description="What the platform concluded, repeatedly and wrongly."
    )
    times_judged: int = 0
    times_incorrect: int = 0
    incorrect_rate: float | None = Field(
        default=None, description="times_incorrect / times_judged; None until judged."
    )
    reported_root_causes: list[str] = Field(
        default_factory=list, description="What engineers said the cause actually was."
    )
    typical_modules: list[str] = Field(default_factory=list)


class HypothesisHistory(LearningArtifact):
    """How often a hypothesis category led, and how often it was confirmed."""

    kind: str = "hypothesis_history"
    category: str = ""
    times_led: int = 0
    times_confirmed: int = 0
    confirmation_rate: float | None = None


class LearningHint(BaseModel):
    """One evidence-backed thing history suggests. Never a conclusion.

    A hint may inform an investigation; it can never manufacture evidence for
    one. Hypotheses still cite Evidence Graph nodes from the current run.
    """

    kind: str = Field(description="Artifact family the hint came from.")
    statement: str = Field(description="What history suggests, in engineering terms.")
    strength: float = Field(
        ge=0.0, le=1.0, description="How strongly history supports it (never a probability of truth)."
    )
    artifact_id: str
    supporting_regressions: list[str] = Field(default_factory=list)


class LearningStatistics(BaseModel):
    """The shape of what the platform has learned so far."""

    corpus_size: int = Field(default=0, description="Recorded regressions the artifacts derive from.")
    feedback_count: int = 0
    artifacts_by_kind: dict[str, int] = Field(default_factory=dict)
    learners: list[str] = Field(default_factory=list)
    generated_at: str = ""


class LearningContext(BaseModel):
    """What the Learning Engine recalled for one run.

    Attached to the report as ``AnalysisReport.learning`` and handed to agents
    through ``AgentContext``. Everything in it is derived, rebuildable, and
    linked back to prior investigations.
    """

    generated_at: str = ""
    corpus_size: int = Field(default=0, description="How many runs this recall is based on.")
    hints: list[LearningHint] = Field(default_factory=list)
    agent_reliability: list[AgentReliability] = Field(default_factory=list)
    project_profile: ProjectProfile | None = None
    recurring_pattern: InvestigationPattern | None = None
    common_recommendations: list[RecommendationOutcome] = Field(default_factory=list)
    recommendation_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Recommendation action -> learned usefulness in [0, 1], from engineer votes. "
        "Used to reorder advice; never to add, remove or rewrite it.",
    )
    rule_gaps: list[RuleGap] = Field(
        default_factory=list,
        description="Signatures engineers repeatedly judged incorrect: candidates for a new rule.",
    )
    calibration: dict[str, float] = Field(
        default_factory=dict,
        description="Agent ID -> bounded influence multiplier applied by the Coordinator.",
    )

    @property
    def is_empty(self) -> bool:
        return not (
            self.hints
            or self.agent_reliability
            or self.project_profile
            or self.recurring_pattern
            or self.common_recommendations
            or self.rule_gaps
        )

    def hints_of_kind(self, kind: str) -> list[LearningHint]:
        """Hints from one artifact family, in recall order."""
        return [h for h in self.hints if h.kind == kind]

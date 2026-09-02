"""Learning feedback: the interface through which engineers correct the platform.

Milestone 4 deliberately ships the *interfaces and storage* for feedback, not
any learning. The contract is designed so online improvement can be added
later without touching the reasoning engine:

* Feedback is keyed by regression ID, so every judgment stays attached to the
  full stored record (graph, reasoning, classification) it judges.
* ``diagnosis`` and ``actual_root_cause`` give future components labeled
  outcomes: a signature whose regressions are repeatedly marked ``incorrect``
  is a candidate for a new rule or generator; confirmed root causes become
  the ``root_cause`` shown for similar failures.
* Per-recommendation votes (``useful_recommendations`` /
  ``false_recommendations``) let a future ranker reweight recommendation
  templates from evidence rather than intuition.

No model retraining is involved anywhere: improvement means better rules,
better priors, and better historical context, all deterministic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from veritriage.feedback.reweight import (
    MIN_VOTES,
    NEUTRAL,
    recommendation_weights,
    reweight_recommendations,
)

__all__ = [
    "FeedbackRecord",
    "FeedbackSink",
    "MIN_VOTES",
    "NEUTRAL",
    "recommendation_weights",
    "reweight_recommendations",
]


class FeedbackRecord(BaseModel):
    """One engineer judgment about one analyzed regression."""

    regression_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    diagnosis: Literal["correct", "incorrect"] | None = Field(
        default=None, description="Was the platform's top diagnosis right?"
    )
    actual_root_cause: str | None = Field(
        default=None, description="The confirmed root cause, in the engineer's words."
    )
    useful_recommendations: list[str] = Field(
        default_factory=list, description="Recommendation actions that helped."
    )
    false_recommendations: list[str] = Field(
        default_factory=list, description="Recommendation actions that wasted time."
    )
    notes: str | None = None


class FeedbackSink(Protocol):
    """Anything that can persist and recall feedback (the store implements this)."""

    def save_feedback(self, record: FeedbackRecord) -> None: ...

    def feedback_for(self, regression_id: str) -> list[FeedbackRecord]: ...

    def all_feedback(self) -> list[FeedbackRecord]: ...

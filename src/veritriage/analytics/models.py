"""Typed results for regression analytics."""

from __future__ import annotations

from pydantic import BaseModel, Field

from veritriage.models import RuleGap


class Counter(BaseModel):
    """One labeled count with its share of the relevant total."""

    label: str
    count: int = Field(ge=0)
    share: float = Field(ge=0.0, le=1.0, description="Fraction of the relevant population.")


class DailyPoint(BaseModel):
    """Runs and failures on one calendar day (UTC)."""

    day: str = Field(description="ISO date, e.g. 2026-07-19.")
    runs: int = Field(ge=0)
    failures: int = Field(ge=0)


class FailureCluster(BaseModel):
    """A recurring problem area: regressions grouped by failure similarity."""

    cluster_id: str
    label: str = Field(description="Engineer-readable name, e.g. 'Testbench Failure in axi_scoreboard'.")
    size: int = Field(ge=1)
    category: str = Field(description="Dominant failure classification in the cluster.")
    modules: list[str] = Field(default_factory=list)
    signatures: list[str] = Field(default_factory=list, description="Signature digests merged into this cluster.")
    regression_ids: list[str] = Field(default_factory=list, description="Members, newest first.")
    tests: list[str] = Field(default_factory=list, description="Distinct test names seen in the cluster.")


class AnalyticsReport(BaseModel):
    """Everything the dashboard renders, computed in one pass over history."""

    total_runs: int = 0
    total_failures: int = 0
    unknown_failures: int = 0
    distinct_signatures: int = 0
    failing_modules: list[Counter] = Field(default_factory=list)
    failure_categories: list[Counter] = Field(default_factory=list)
    assertion_hotspots: list[Counter] = Field(default_factory=list)
    signal_frequency: list[Counter] = Field(
        default_factory=list, description="How often each reasoning rule's signal fired (rule effectiveness)."
    )
    repeated_recommendations: list[Counter] = Field(default_factory=list)
    confidence_histogram: list[Counter] = Field(
        default_factory=list, description="Classification confidence, bucketed by decade."
    )
    daily: list[DailyPoint] = Field(default_factory=list)
    clusters: list[FailureCluster] = Field(default_factory=list)
    rule_gaps: list[RuleGap] = Field(
        default_factory=list,
        description="Signatures engineers repeatedly judged incorrect: the platform is "
        "reliably wrong here and a rule or pack pattern is missing.",
    )
    heatmap: dict[str, dict[str, int]] = Field(
        default_factory=dict, description="module -> failure category -> count."
    )

    @property
    def failure_rate(self) -> float:
        return self.total_failures / self.total_runs if self.total_runs else 0.0

    @property
    def unknown_rate(self) -> float:
        return self.unknown_failures / self.total_failures if self.total_failures else 0.0

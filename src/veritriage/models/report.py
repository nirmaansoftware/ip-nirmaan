"""Top-level analysis report and its constituent result models."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from veritriage.models.agents import AgentAssessment
from veritriage.models.automation import AutomationContext
from veritriage.models.design import DesignContext
from veritriage.models.events import Severity, SimulationEvent
from veritriage.models.evidence import Evidence
from veritriage.models.failure import AssertionFailure, Failure, FailureCategory
from veritriage.models.engineering import EngineeringContextView
from veritriage.models.history import HistoricalContext
from veritriage.models.knowledge import KnowledgeContext
from veritriage.models.learning import LearningContext
from veritriage.models.planning import DebugPlan
from veritriage.models.project import ProjectContext
from veritriage.models.reasoning import ReasoningResult
from veritriage.models.waveform import WaveformContext


class Recommendation(BaseModel):
    """A suggested next debugging step, always paired with a rationale."""

    action: str = Field(description="What the engineer should do next.")
    rationale: str = Field(description="Why this step follows from the evidence.")
    priority: int = Field(default=1, ge=1, description="1 = do first; higher numbers come later.")


class ClassificationResult(BaseModel):
    """The output of one rule: a verdict backed by evidence.

    The rule engine may produce several of these; the highest-confidence one
    becomes the report's primary classification and the rest are kept as
    alternatives so the engineer can see what else was considered.
    """

    category: FailureCategory
    confidence: int = Field(ge=0, le=100, description="Confidence in percent, 0-100.")
    rule_name: str = Field(description="Name of the rule that produced this result.")
    summary: str = Field(description="One-line verdict, e.g. 'Likely testbench issue'.")
    evidence: list[Evidence] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)


class LogSummary(BaseModel):
    """Aggregate statistics about the parsed log."""

    total_lines: int = Field(ge=0)
    counts: dict[Severity, int] = Field(
        default_factory=dict, description="Event count per severity."
    )
    test_name: str | None = Field(default=None, description="Test name, if detected.")
    simulator: str | None = Field(default=None, description="Simulator, if detected.")
    last_sim_time: str | None = Field(
        default=None, description="Last simulation time observed in the log."
    )

    def count(self, severity: Severity) -> int:
        """Event count for one severity (0 if none were seen)."""
        return self.counts.get(severity, 0)


class GraphStats(BaseModel):
    """Aggregate shape of the Evidence Graph, embedded in the report.

    Keys are plain strings (artifact-type and relation values) so this model
    stays independent of the graph package; the full graph itself is written
    to ``evidence_graph.json``.
    """

    node_count: int = 0
    edge_count: int = 0
    nodes_by_type: dict[str, int] = Field(default_factory=dict)
    edges_by_relation: dict[str, int] = Field(default_factory=dict)


class AnalysisReport(BaseModel):
    """The complete result of one `veritriage analyze` run.

    Serialized verbatim to ``analysis.json`` and rendered to HTML. Fields are
    additive across versions; ``schema_version`` bumps on breaking changes.
    Version 2 introduces multi-artifact input and the Evidence Graph. Version 14
    marks the reference ``uri`` and the ``learning`` ``rule_gaps`` and
    ``recommendation_weights`` fields.
    """

    schema_version: str = "14"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input_files: list[str] = Field(description="Paths of the analyzed artifacts, as given on the CLI.")
    parser_names: list[str] = Field(description="Parsers used, one per input artifact.")
    summary: LogSummary
    graph_stats: GraphStats = Field(default_factory=GraphStats)
    classification: ClassificationResult
    alternatives: list[ClassificationResult] = Field(
        default_factory=list, description="Other rule verdicts, sorted by descending confidence."
    )
    failures: list[Failure | AssertionFailure] = Field(default_factory=list)
    events: list[SimulationEvent] = Field(
        default_factory=list,
        description="Notable events (warning and above) in log order.",
    )
    reasoning: ReasoningResult | None = Field(
        default=None,
        description="Reasoning-engine output: working set, signals, ranked hypotheses, recommendations.",
    )
    knowledge: KnowledgeContext | None = Field(
        default=None,
        description="Verification Knowledge Engine conclusions: matched patterns, concepts, "
        "state projection, playbooks.",
    )
    history: HistoricalContext | None = Field(
        default=None,
        description="Regression-database context: is this failure new, and what resembles it.",
    )
    waveform: WaveformContext | None = Field(
        default=None,
        description="Waveform Intelligence Engine conclusions: engineering observations "
        "(handshake stalls, dead clocks, stalled FSMs, unretired transactions) plus honest "
        "notes on analyses an adapter could not run.",
    )
    engineering: EngineeringContextView | None = Field(
        default=None,
        description="Engineering Context Engine output: recent changes with their "
        "correlated failures, CI environment, ownership, impacted tests, the engineering "
        "timeline, and the investigation projection.",
    )
    project: ProjectContext | None = Field(
        default=None,
        description="Verification Project Intelligence output: the structural understanding "
        "of the project the run belongs to (DUT topology, identified protocols, UVM "
        "environment), plus the run's projection onto the expected simulation lifecycle and "
        "the origin breakdown of its failing evidence. Present only when a project model is "
        "supplied; the Evidence Graph is never affected.",
    )
    agents: AgentAssessment | None = Field(
        default=None,
        description="Agent Framework output: what each domain specialist concluded, the "
        "merged findings with agreement and conflict made explicit, and whether the agent "
        "layer agrees with the deterministic reasoning engine. A second opinion that sits "
        "beside `reasoning` and never replaces it.",
    )
    learning: LearningContext | None = Field(
        default=None,
        description="Learning Engine output: what prior investigations suggest for this "
        "one. Hints, agent reliability, project memory, and recurring patterns, each "
        "linked back to the regressions it was learned from. Never a conclusion: learning "
        "informs, it does not decide.",
    )
    plan: DebugPlan | None = Field(
        default=None,
        description="Planning Engine output: a structured, branching investigation plan "
        "derived from the conclusions above. Every step names the artifact it restates; "
        "the Planner contributes structure, ordering, branching, and valuation, never new "
        "debug advice, and never executes anything. Distinct from the M9 orchestration "
        "`InvestigationPlan`, which is what the platform runs rather than what the "
        "engineer should do.",
    )
    design: DesignContext | None = Field(
        default=None,
        description="Design Intelligence output: the structural understanding of the "
        "system this run exercised. The affected design region, hierarchy, clock and "
        "reset topology, protocol map, verification topology, dependencies, and risk "
        "hotspots, all derived from the Project Model. Present only when a project "
        "model is supplied; the Evidence Graph is never affected.",
    )
    automation: AutomationContext | None = Field(
        default=None,
        description="Automation Engine output: the events this run published, which "
        "rules looked at them, what each decided, and which actions were requested and "
        "executed. Appended by the workspace after analysis, exactly as historical "
        "context is; automation never changes a conclusion.",
    )
    ai_summary: str | None = Field(
        default=None, description="Optional AI-generated narrative; grounded in `evidence` only."
    )

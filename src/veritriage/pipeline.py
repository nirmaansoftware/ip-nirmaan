"""End-to-end analysis pipeline: parse artifacts, build the graph, classify.

This is the library-level entry point; the CLI is a thin wrapper around it.

Flow: each artifact is parsed by its matching parser, every parser emits a
GraphFragment, the GraphBuilder merges and correlates them into the Evidence
Graph, and the rule engine classifies from the graph. The graph, not any raw
file, is what every downstream consumer (report, AI layer) works from.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Sequence

# Importing the engineering package registers its providers and the context
# manifest parser, so a *.engctx.json artifact is handled with no other setup;
# live provider collection stays a CLI-layer decision to keep this function pure.
from veritriage.engineering import (
    EngineeringContext,
    augment_with_ownership,
    build_engineering_view,
    emit_engineering_evidence,
    engineering_reasoning_rules,
    stored_context,
)
from veritriage.agents import AgentCoordinator, build_agent_context
from veritriage.design import build_design_graph, build_design_view
from veritriage.planning import Planner, PlanningContext
from veritriage.graph.builder import GraphBuilder
from veritriage.feedback.reweight import reweight_recommendations
from veritriage.graph.graph import EvidenceGraph
from veritriage.knowledge import KnowledgeEngine, knowledge_reasoning_rules
from veritriage.models import AnalysisReport, LearningContext, LogSummary, Severity
from veritriage.parsers import find_parser, get_parser
from veritriage.parsers.base import ParseResult
from veritriage.project import ProjectModel, build_project_view, project_reasoning_rules
from veritriage.reasoning import ReasoningEngine
from veritriage.reasoning.signals import default_reasoning_rules
from veritriage.rules import RuleEngine
# Importing the waveform package registers its adapters and the waveform parser,
# so a .vcd or .wave.json artifact is handled with no other pipeline setup.
from veritriage.waveform import build_waveform_context, waveform_reasoning_rules


class AnalysisOutcome(NamedTuple):
    """What one analysis run produces: the report and the full graph."""

    report: AnalysisReport
    graph: EvidenceGraph


def analyze(
    paths: Path | Sequence[Path],
    parser_name: str | None = None,
    engine: RuleEngine | None = None,
    engineering: EngineeringContext | None = None,
    project: ProjectModel | None = None,
    agents: bool = True,
    learning: LearningContext | None = None,
    plan: bool = True,
) -> AnalysisOutcome:
    """Analyze one or more artifacts and return the report plus the graph.

    Args:
        paths: Artifact paths (simulation log, compile log, coverage summary,
            test metadata, waveform, context manifest). A single Path is
            accepted for convenience.
        parser_name: Force one registered parser for every artifact;
            auto-detected per file when None.
        engine: Rule engine to use; the default built-in rule set if None.
        engineering: Already-normalized engineering context (collected by the
            CLI from the provider registry). The pipeline consumes it and
            never calls a provider itself, so this function stays a pure
            function of its inputs. Context manifests passed as artifact
            files need no parameter at all.
        project: Already-built Project Model (built by the CLI from the project
            provider registry). When supplied, project-aware reasoning rules
            join the rule set and a ProjectContext is attached to the report;
            the Evidence Graph is never affected. The pipeline never builds a
            model itself, so it stays a pure function of its inputs.
        agents: Run the Agent Framework after deterministic reasoning and attach
            the resulting :class:`AgentAssessment` to the report. On by default.
            Agents form a second opinion over the finished deterministic result:
            they never mutate the graph, the classification, or the reasoning
            hypotheses, so turning this off changes only the ``agents`` field.
        learning: Already-recalled learning context (recalled by the workspace
            from the learning store, exactly as ``project`` is built there).
            When supplied it reaches the agents as memory, calibrates their
            influence at merge time, and is attached to the report. The
            pipeline never opens the learning store, so it stays a pure
            function of its inputs.
        plan: Derive an investigation plan from the finished report and attach
            it as ``report.plan``. On by default. Planning consumes conclusions
            and never changes them, so turning this off changes only that field.

    Raises:
        FileNotFoundError: If any path does not exist.
    """
    artifact_paths = [paths] if isinstance(paths, Path) else list(paths)
    if not artifact_paths:
        raise ValueError("At least one artifact path is required")
    for path in artifact_paths:
        if not path.is_file():
            raise FileNotFoundError(f"No such artifact: {path}")

    results: list[ParseResult] = []
    builder = GraphBuilder()
    for path in artifact_paths:
        parser = get_parser(parser_name) if parser_name else find_parser(path)
        result = parser.parse(path)
        results.append(result)
        builder.add_fragment(parser.emit_evidence(result))

    # Merge injected context with any manifest artifacts; content-hashed node
    # IDs make double delivery of the same commit a no-op merge, not a dupe.
    context = engineering or EngineeringContext()
    for result in results:
        stored = stored_context(result)
        if stored is not None:
            context = context.merge(stored)
    if engineering is not None and not engineering.is_empty:
        builder.add_fragment(emit_engineering_evidence(engineering))
    graph = builder.build()

    engine = engine or RuleEngine()
    primary, alternatives = engine.classify(graph)

    # Knowledge runs before reasoning and feeds it through the standard rule
    # interface: matched patterns become ordinary evidence-cited signals. The
    # reasoning engine itself has no knowledge dependency.
    knowledge_engine = KnowledgeEngine()
    knowledge = knowledge_engine.analyze(graph)
    # Waveform observations and engineering changes reach reasoning through
    # the same rule interface as knowledge: ordinary evidence-cited signals.
    # Project intelligence, when supplied, joins reasoning through the same rule
    # interface as every other subsystem: ordinary evidence-cited signals. The
    # project model never enters the Evidence Graph; it only interprets it.
    reasoning = ReasoningEngine(
        rules=[
            *default_reasoning_rules(),
            *knowledge_reasoning_rules(knowledge_engine.knowledge),
            *waveform_reasoning_rules(),
            *engineering_reasoning_rules(),
            *(project_reasoning_rules(project) if project is not None else []),
        ]
    ).reason(graph)
    waveform = build_waveform_context(results)

    # Keep the report focused: warnings and above. INFO stays available to
    # parsers but would bloat analysis.json on chatty logs.
    notable_events = [
        e for r in results for e in r.events if e.severity != Severity.INFO
    ]
    report = AnalysisReport(
        input_files=[str(p) for p in artifact_paths],
        parser_names=[r.parser_name for r in results],
        summary=_merge_summaries(results),
        graph_stats=graph.stats(),
        classification=primary,
        alternatives=alternatives,
        failures=[f for r in results for f in r.failures],
        events=notable_events,
        reasoning=reasoning,
        knowledge=None if knowledge.is_empty else knowledge,
        waveform=None if (waveform is None or waveform.is_empty) else waveform,
    )
    # Engineering view and ownership routing come last: both read the finished
    # report (correlations, hypotheses) and only append, never rewrite.
    report.engineering = build_engineering_view(context, graph, report)
    augment_with_ownership(report, graph, context)
    # Project context is a pure lens over the finished report and graph; it
    # reads correlations and hypotheses and only attaches structure.
    if project is not None:
        report.project = build_project_view(project, graph, report)
        # Design Intelligence derives the structural graph from the project
        # model and never from source. Like the project model itself it is a
        # lens over the Evidence Graph, never part of it. Built before the
        # agents run, so a specialist can ask a structural question.
        design_graph = build_design_graph(project)
        if not design_graph.is_empty:
            report.design = build_design_view(design_graph, graph)
    # The Agent Framework runs last, over the finished deterministic result: it
    # is a second opinion, not a stage of the pipeline's conclusion path. It
    # reads the report and the graph and writes only report.agents.
    report.learning = learning
    # Feedback closes the loop M4 opened: engineer votes reorder the advice
    # this run produced. A reorder only, and only when a learning context was
    # recalled, so the deterministic conclusions above are untouched and a
    # platform without a learning store behaves exactly as it did before.
    if learning is not None and learning.recommendation_weights:
        report.reasoning.recommendations = reweight_recommendations(
            report.reasoning.recommendations, learning.recommendation_weights
        )
    if agents:
        assessment = AgentCoordinator(
            calibration=learning.calibration if learning is not None else None
        ).coordinate(
            build_agent_context(
                graph=graph,
                classification=report.classification,
                reasoning=reasoning,
                knowledge=report.knowledge,
                knowledge_graph=knowledge_engine.knowledge,
                project=report.project,
                waveform=report.waveform,
                engineering=report.engineering,
                history=report.history,
                learning=learning,
                design=report.design,
            )
        )
        report.agents = None if assessment.is_empty else assessment
    # Planning runs last of all, over everything above it: it is the only layer
    # that consumes conclusions from every other layer, and the only one that
    # answers "what should happen next?" rather than "what is true?".
    if plan:
        derived = Planner().plan(PlanningContext(report=report, graph=graph))
        report.plan = None if derived.is_empty else derived
    return AnalysisOutcome(report=report, graph=graph)


def _merge_summaries(results: list[ParseResult]) -> LogSummary:
    """Combine per-artifact summaries into one run-level summary."""
    counts: dict[Severity, int] = {}
    total_lines = 0
    test_name = simulator = last_sim_time = None
    for result in results:
        total_lines += result.summary.total_lines
        for severity, count in result.summary.counts.items():
            counts[severity] = counts.get(severity, 0) + count
        test_name = test_name or result.summary.test_name
        simulator = simulator or result.summary.simulator
        last_sim_time = result.summary.last_sim_time or last_sim_time
    return LogSummary(
        total_lines=total_lines,
        counts=counts,
        test_name=test_name,
        simulator=simulator,
        last_sim_time=last_sim_time,
    )

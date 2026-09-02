"""WorkspaceServices: the stable public API every client consumes.

The CLI and every MCP tool call these methods and nothing else, so
investigation logic exists exactly once and "adding a client" never means
"re-implementing the platform". Everything here is deterministic and AI-free;
the optional AI review stays outside the workspace entirely.

Return types are exclusively normalized models (from ``veritriage.models``,
the graph package, and the workspace's own API models): no ``ParseResult``,
parser, adapter, or provider object ever crosses this API
(``test_public_api_never_exposes_raw_parser_objects`` pins it). Raw artifact
paths go in; normalized objects come out.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from veritriage.engineering.model import RegressionDiff
    from veritriage.models import (
        AgentAssessment,
        AgentReliability,
        AgentResult,
        LearningArtifact,
        LearningContext,
        ActionRequest,
        ActionResult,
        Answer,
        AutomationContext,
        AutomationStatus,
        ConversationSession,
        Event,
        GeneratedView,
        Prompt,
        ProviderStatus,
        DebugPlan,
        DesignContext,
        LearningStatistics,
        LogAnnotationView,
        PlanProgress,
        ProjectContext,
        ProjectProfile,
        ProjectSummary,
    )
    from veritriage.project import ProjectModel

from veritriage.engineering import EngineeringContext
from veritriage.engineering.timeline import build_timeline
from veritriage.graph.model import ArtifactType, EvidenceNode
from veritriage.models import (
    EngineeringContextView,
    MatchedPattern,
    SimilarFailure,
    TimelineEventView,
    WaveformObservationView,
)
from veritriage.pipeline import analyze
from veritriage.workspace.persistence import SessionStore, SessionSummary
from veritriage.workspace.search import (
    EvidenceHit,
    KnowledgeHit,
    search_evidence,
    search_knowledge,
)
from veritriage.workspace.session import InvestigationSession, make_session


class InvestigationSummary(BaseModel):
    """One bounded summary of a session: the elevator answer."""

    session_id: str
    created_at: str
    input_files: list[str]
    classification: str
    confidence: int
    top_hypothesis: str | None = None
    top_hypothesis_id: str | None = None
    top_hypothesis_confidence: float | None = None
    evidence_nodes: int
    matched_patterns: list[str] = Field(default_factory=list)
    waveform_observations: int = 0
    engineering_commits: int = 0
    seen_before: bool | None = None
    recommendations: int = 0


class ComparisonView(BaseModel):
    """A deterministic comparison of two investigations."""

    session_a: str
    session_b: str
    same_signature: bool
    classification_a: str
    classification_b: str
    shared_failing_descriptions: list[str] = Field(default_factory=list)
    only_in_a: int = 0
    only_in_b: int = 0


class WorkspaceServices:
    """The platform's public service layer. One instance per workspace."""

    def __init__(
        self,
        session_root: Path | None = None,
        db: Path | None = None,
        project_root: Path | None = None,
        learning_db: Path | None = None,
    ) -> None:
        from veritriage.project import ProjectStore

        self._store = SessionStore(session_root)
        self._db = db
        self._project_store = ProjectStore(project_root)
        # The learning store defaults beside the regression database. It is a
        # derived, rebuildable view: deleting it returns the platform to exact
        # pre-M13 behavior, which is why it is a separate file.
        self._learning_db = learning_db or (
            Path(db).parent / "learning.db" if db is not None else None
        )
        # The event bus is created lazily so a workspace that never automates
        # never builds one, and so WORKSPACE_OPENED is published exactly once.
        self._bus = None
        self._automation_enabled = True

    # --- Investigations ----------------------------------------------------

    def gather_engineering_context(
        self, root: Path, max_commits: int = 10
    ) -> EngineeringContext | None:
        """Collect engineering context from every provider available at a root.

        The workspace-level wrapper over the provider registry (added in M9
        so orchestration steps and MCP tools gather context through services
        like everything else). Returns None when nothing contributed, so
        callers can pass the result straight to :meth:`investigate`.
        """
        from veritriage.engineering import collect_context

        gathered = collect_context(root, max_commits=max_commits)
        return None if gathered.is_empty else gathered

    def render_report(
        self,
        session: InvestigationSession,
        output_dir: Path,
        metrics: dict | None = None,
    ) -> Path:
        """Write the session's analysis.json, evidence_graph.json, and
        report.html to a directory; returns the report path.

        ``metrics`` is optional plain data (an orchestration trace's step
        timings) rendered as an "Investigation performance" report section;
        without it the output is byte-identical to pre-M9 reports.
        """
        from veritriage.reports import HtmlReportGenerator
        from veritriage.utils import write_json

        write_json(session.report, output_dir / "analysis.json")
        write_json(session.graph, output_dir / "evidence_graph.json")
        return HtmlReportGenerator().write(
            session.report,
            output_dir / "report.html",
            graph=session.graph,
            metrics=metrics,
        )

    def investigate(
        self,
        paths: Sequence[Path],
        engineering: EngineeringContext | None = None,
        parser_name: str | None = None,
        record_history: bool = False,
        now: datetime | None = None,
        project: "ProjectModel | None" = None,
        agents: bool = True,
        learn: bool = True,
        plan: bool = True,
        automate: bool = True,
    ) -> InvestigationSession:
        """Run one full analysis and wrap it into an immutable session.

        With ``record_history`` (and a workspace database), the run is
        recorded in the regression database and the report is augmented with
        historical context *before* the session is created, so the session
        stays immutable from birth. Recording is off by default: MCP and
        library callers get a read-only posture unless they opt in.
        """
        # Recall runs before the analysis, so agents receive memory and the
        # Coordinator receives calibration. Nothing here can alter a
        # deterministic conclusion: recall only supplies context.
        recalled = (
            self.recall_learning(project.project_id if project is not None else None)
            if learn
            else None
        )
        outcome = analyze(
            list(paths),
            parser_name=parser_name,
            engineering=engineering,
            project=project,
            agents=agents,
            learning=recalled,
            plan=plan,
        )
        if record_history and self._db is not None:
            from veritriage.history import HistoryEngine, capture_execution_metadata
            from veritriage.storage import RegressionStore

            with RegressionStore(self._db) as store:
                engine = HistoryEngine(store)
                _, context = engine.record(
                    outcome, execution=capture_execution_metadata()
                )
                engine.augment(outcome, context)
            # The signature-specific half of recall, once the run has one.
            # Mirrors HistoryEngine.record/augment, and like it, appends only.
            if learn and recalled is not None:
                self._augment_learning(outcome.report, context.signature)
        # Automation observes the finished analysis and decides what should
        # follow. Appended after the fact, exactly as historical context is:
        # nothing here can change a conclusion.
        if automate:
            self._automate(outcome.report)
        return make_session(outcome.report, outcome.graph, now=now)

    # --- Project intelligence (M11) ----------------------------------------
    #
    # The Project Model is built from the provider registry, cached, and reused
    # by investigations. Like collect_context it is gathered here (a workspace
    # decision), not inside the pure pipeline, and it never enters the graph.

    def build_project_model(self, root: Path) -> "ProjectModel":
        """Build and cache the Project Model for a source root."""
        from veritriage.project import build_project_model

        model = build_project_model(root)
        if not model.is_empty:
            self._project_store.save(model)
        return model

    def load_project_model(self, root: Path) -> "ProjectModel | None":
        """The cached model for a root (None if never built)."""
        return self._project_store.load_for_root(root)

    def project_summary(self, model: "ProjectModel") -> "ProjectSummary":
        """The bounded 'what is this project?' answer."""
        from veritriage.models import ProjectSummary

        return ProjectSummary(
            project_id=model.project_id,
            source_root=model.source_root,
            built_at=model.built_at.isoformat(),
            dut_top=model.dut.top,
            simulator=model.sim_infra.simulator_vendor,
            module_count=len(model.dut.modules),
            interface_count=len(model.dut.interfaces),
            identified_protocols=sorted(
                {i.protocol_id for i in model.dut.interfaces if i.protocol_id}
            ),
            uvm_component_count=len(model.env.components),
            lifecycle_phase_count=len(model.lifecycle.phases),
        )

    def project_context(self, session: InvestigationSession) -> "ProjectContext | None":
        """The project context attached to a session's report, if any."""
        return session.report.project

    def explain_log(
        self, path: Path, model: "ProjectModel | None" = None
    ) -> "list[LogAnnotationView]":
        """Classify a log's lines by origin and lifecycle phase (log intelligence)."""
        from veritriage.project import explain_log

        return explain_log(path, model)

    # --- Agent Framework (M12) ---------------------------------------------
    #
    # Read-only accessors over what the Coordinator already attached to the
    # report. Agents run inside the analysis, so there is nothing to trigger
    # here: these exist so a client never has to reach into report internals.

    def agent_assessment(self, session: InvestigationSession) -> "AgentAssessment | None":
        """The agent layer's second opinion on a session, if agents ran."""
        return session.report.agents

    def agent_result(
        self, session: InvestigationSession, agent_id: str
    ) -> "AgentResult | None":
        """One specialist's full assessment: observations, position, limits."""
        assessment = session.report.agents
        if assessment is None:
            return None
        return next((r for r in assessment.results if r.agent_id == agent_id), None)

    # --- Learning Engine (M13) ---------------------------------------------
    #
    # The workspace owns the learning store the way it owns the project store
    # and the regression database: the pipeline never opens one, so analyze()
    # stays a pure function. Every method degrades to nothing (None, empty
    # list) when no learning database is configured, so the platform behaves
    # exactly as it did before M13.

    def _learning_engine(self):
        """Open a Learning Engine over the workspace's learning store, or None."""
        if self._learning_db is None:
            return None
        from veritriage.learning import LearningEngine, LearningStore

        return LearningEngine(LearningStore(self._learning_db))

    def changes_since_last_green(
        self,
        regression_id: str,
        root: Path | None = None,
        max_commits: int = 50,
    ) -> "RegressionDiff | None":
        """What landed between the last recorded green run and this one.

        The regression database has recorded each run's commit since v0.4.0
        and the provider seam could list commits since M7; this joins them.
        Returns None whenever the question cannot be honestly answered: no
        recorded green run, a run without a commit, no registered provider
        that can resolve a range, or commits this checkout does not have.
        """
        if self._db is None or not Path(self._db).is_file():
            return None
        from veritriage.engineering.providers import available_providers
        from veritriage.engineering.regression_diff import diff_against_last_green
        from veritriage.storage import RegressionStore

        where = Path(root) if root is not None else Path.cwd()
        with RegressionStore(self._db) as store:
            records = store.all_records()
        target = next(
            (r for r in records if r.regression_id == regression_id), None
        )
        if target is None:
            return None
        for provider_cls in available_providers().values():
            if not provider_cls.available(where):
                continue
            diff = diff_against_last_green(
                records, target, provider_cls(), where, max_commits=max_commits
            )
            if diff is not None:
                return diff
        return None

    def learn_from_history(self) -> "LearningStatistics | None":
        """Recompute every learning artifact from the regression database.

        The normal path, not a fallback: learning is a pure function of
        recorded history, so a full rebuild is both cheap to reason about and
        the only way a corrected feedback record can fix everything it touches.
        """
        if self._db is None or not Path(self._db).is_file():
            return None
        engine = self._learning_engine()
        if engine is None:
            return None
        from veritriage.storage import RegressionStore

        with RegressionStore(self._db) as store:
            return engine.observe(store.all_records(), store.all_feedback())

    def recall_learning(self, project_key: str | None = None) -> "LearningContext | None":
        """What history suggests for an upcoming investigation."""
        engine = self._learning_engine()
        if engine is None:
            return None
        recalled = engine.recall(project_key)
        return None if recalled.is_empty else recalled

    def _augment_learning(self, report, signature_digest: str) -> None:
        engine = self._learning_engine()
        if engine is not None:
            engine.augment(report, signature_digest)

    def learning_statistics(self) -> "LearningStatistics | None":
        """The shape of what the platform has learned so far."""
        engine = self._learning_engine()
        return engine.statistics() if engine is not None else None

    def learning_artifacts(self, kind: str | None = None) -> "list[LearningArtifact]":
        """Stored learning artifacts, optionally filtered to one family."""
        engine = self._learning_engine()
        return list(engine.artifacts(kind)) if engine is not None else []

    def agent_reliability(self) -> "list[AgentReliability]":
        """Each specialist's track record and the calibration it has earned."""
        from veritriage.models import AgentReliability as _AgentReliability

        return [
            a
            for a in self.learning_artifacts("agent_reliability")
            if isinstance(a, _AgentReliability)
        ]

    def project_memory(self, project_key: str | None = None) -> "ProjectProfile | None":
        """What a project characteristically looks like, learned over its runs."""
        engine = self._learning_engine()
        if engine is None:
            return None
        return engine.recall(project_key).project_profile

    # --- Planning Engine (M14) ---------------------------------------------
    #
    # Read-only accessors over the plan the pipeline already derived, plus a
    # pure re-derivation for callers holding only a session. Planning opens no
    # store and executes nothing, so none of this needs configuration.

    def investigation_plan(self, session: InvestigationSession) -> "DebugPlan | None":
        """The investigation plan attached to a session, if planning ran."""
        return session.report.plan

    def build_investigation_plan(self, session: InvestigationSession) -> "DebugPlan":
        """Re-derive the plan from a session. Pure: same session, same plan."""
        from veritriage.planning import build_plan

        return build_plan(session.report, session.graph)

    def next_debug_step(self, session: InvestigationSession):
        """The single highest-value next action, or None when there is nothing to do."""
        plan = session.report.plan or self.build_investigation_plan(session)
        return plan.steps[0] if plan.steps else None

    def missing_evidence(self, session: InvestigationSession) -> list:
        """What the platform does not have, and why each item would matter."""
        plan = session.report.plan or self.build_investigation_plan(session)
        return list(plan.evidence_requests)

    def decision_tree(self, session: InvestigationSession) -> list:
        """Every branching point in the plan, with its outcomes."""
        plan = session.report.plan or self.build_investigation_plan(session)
        return [s.decision for s in plan.all_steps() if s.decision is not None]

    def plan_progress(self, session: InvestigationSession) -> "PlanProgress":
        """How far along the investigation is, given the evidence available now."""
        from veritriage.planning import plan_progress

        plan = session.report.plan or self.build_investigation_plan(session)
        return plan_progress(plan, session.graph)

    # --- Design Intelligence (M15) -----------------------------------------
    #
    # The Design Graph is derived from the Project Model, so these methods build
    # it on demand from the cached model. Nothing here reads source: only a
    # ProjectProvider may, and that law stays in M11.

    def design_graph(self, root: Path | None = None):
        """The structural graph for a project root, or None without a model."""
        from veritriage.design import build_design_graph

        model = self.load_project_model(root or Path(".")) or self.build_project_model(
            root or Path(".")
        )
        if model.is_empty:
            return None
        graph = build_design_graph(model)
        return None if graph.is_empty else graph

    def design_context(self, session: InvestigationSession) -> "DesignContext | None":
        """The design context attached to a session's report, if any."""
        return session.report.design

    def design_query(self, root: Path | None = None):
        """A DesignQuery over the project's structure, or None without a model."""
        from veritriage.design import DesignQuery

        graph = self.design_graph(root)
        return DesignQuery(graph) if graph is not None else None

    def describe_module(self, name: str, root: Path | None = None) -> dict | None:
        """One structural element and everything one hop around it."""
        query = self.design_query(root)
        if query is None:
            return None
        node = query.resolve_scope(name)
        if node is None:
            return None
        graph = query.graph
        return {
            "node": node.model_dump(mode="json"),
            "relations": [
                {
                    "relation": e.relation.value,
                    "other": (
                        graph.nodes[e.target_id].name
                        if e.source_id == node.id
                        else graph.nodes[e.source_id].name
                    ),
                    "direction": "out" if e.source_id == node.id else "in",
                    "rationale": e.rationale,
                    "inferred": e.inferred,
                }
                for e in graph.edges
                if node.id in (e.source_id, e.target_id)
            ],
        }

    def design_hierarchy(self, root: Path | None = None, top: str | None = None) -> list[dict]:
        """The instantiation tree as flat, renderable rows."""
        query = self.design_query(root)
        if query is None:
            return []
        return [
            {"depth": depth, "name": node.name, "kind": node.kind.value, "node_id": node.id}
            for depth, node in query.hierarchy(top)
        ]

    def affected_design_region(self, session: InvestigationSession) -> list[dict]:
        """The design neighbourhood around a session's failing scopes."""
        context = session.report.design
        if context is None:
            return []
        return [n.model_dump(mode="json") for n in context.affected_region]

    # --- Conversation (M16) -------------------------------------------------
    #
    # Conversation navigates a finished investigation; it owns no intelligence
    # and stores nothing. A ConversationSession is returned to the caller to
    # keep however it likes: navigation state is not intelligence, and it does
    # not belong in a database.

    def start_conversation(
        self, session: InvestigationSession, conversation: "ConversationSession | None" = None
    ):
        """Open a navigable conversation over a finished investigation."""
        from veritriage.conversation import ConversationContext, ConversationEngine

        return ConversationEngine(
            ConversationContext(
                session_id=session.session_id, report=session.report, graph=session.graph
            ),
            session=conversation,
        )

    def ask(
        self,
        session: InvestigationSession,
        question,
        conversation: "ConversationSession | None" = None,
    ) -> tuple["Answer", "ConversationSession"]:
        """Ask one question; returns the answer and the updated conversation.

        Stateless from the platform's point of view: pass the conversation back
        in to continue it, or drop it to start fresh.
        """
        engine = self.start_conversation(session, conversation)
        answer = engine.ask(question)
        return answer, engine.session

    def conversation_vocabulary(self) -> list[str]:
        """The phrasings the deterministic parser understands."""
        from veritriage.conversation import vocabulary

        return vocabulary()

    # --- Generative AI (M17) ------------------------------------------------
    #
    # Provider selection, capability discovery, and grounded rendering. Every
    # method degrades to the structured object when generation is off, fails,
    # or is not configured: prose is an additional view, never the source of
    # truth, so nothing here can cost a conclusion.

    def ai_provider_status(self, provider: str | None = None) -> "list[ProviderStatus]":
        """Every registered generative provider, its capabilities, and health."""
        from veritriage.ai import AIService

        return AIService(provider).status()

    def preview_prompt(
        self,
        session: InvestigationSession,
        renderer: str = "engineer-summary",
    ) -> "Prompt":
        """Exactly what a provider would be asked, without asking it.

        Prompt construction is a pure function of the structured input, so this
        is auditable before any generation happens.

        Raises:
            KeyError: If the renderer is not one of the named views.
        """
        from veritriage.ai import AIService, PromptContext
        from veritriage.ai.renderers import RENDERERS

        if renderer not in RENDERERS:
            known = ", ".join(sorted(RENDERERS))
            raise KeyError(f"Unknown renderer {renderer!r}. Available: {known}")
        return AIService.build_prompt(RENDERERS[renderer], PromptContext(report=session.report))

    def render_investigation(
        self,
        session: InvestigationSession,
        renderer: str = "engineer-summary",
        provider: str | None = None,
    ) -> "GeneratedView":
        """Render one investigation as prose, grounded in its own artifacts."""
        from veritriage.ai import AIService, render_report

        return render_report(AIService(provider), session.report, renderer)

    def render_answer(self, answer, provider: str | None = None) -> "GeneratedView":
        """Render a conversation answer as prose, preserving its citations."""
        from veritriage.ai import AIService, render_answer

        return render_answer(AIService(provider), answer)

    def ai_renderers(self) -> list[str]:
        """Every named view generation can produce."""
        from veritriage.ai import available_renderers

        return available_renderers()

    # --- Automation (M18) ---------------------------------------------------
    #
    # The workspace is where automation meets execution. The automation package
    # decides (it imports only models and executes nothing); the workspace
    # dispatches the resulting requests to methods it already has. That split is
    # what keeps automation out of the execution business and out of a cycle
    # with the M9 orchestrator.

    @property
    def events(self):
        """The workspace event bus. Ordered, synchronous, replayable."""
        if self._bus is None:
            from veritriage.automation import EventBus

            self._bus = EventBus()
            self._bus.publish(
                __import__("veritriage.models", fromlist=["EventKind"]).EventKind.WORKSPACE_OPENED,
                {"session_root": str(self._store.root)},
                source="workspace",
            )
        return self._bus

    def publish_event(self, kind, payload: dict | None = None, subject: str | None = None):
        """Publish one event onto the workspace bus."""
        return self.events.publish(kind, payload or {}, subject=subject)

    def recent_events(self, kind=None, limit: int = 50) -> "list[Event]":
        """The recorded event log, newest last."""
        return self.events.events(kind=kind, limit=limit)

    def replay_events(self, kind=None, since: int | None = None) -> int:
        """Re-deliver recorded events to the current subscribers."""
        return self.events.replay(kind=kind, since=since)

    def automation_status(self) -> "AutomationStatus":
        """Registered rules and triggers, the action vocabulary, and bus health."""
        from veritriage.automation import available_rules, available_triggers, enabled_rules
        from veritriage.models import ActionKind, AutomationStatus

        return AutomationStatus(
            enabled=self._automation_enabled,
            registered_rules=sorted(available_rules()),
            enabled_rules=[r.rule_id for r in enabled_rules()],
            registered_triggers=sorted(available_triggers()),
            action_vocabulary=[a.value for a in ActionKind],
            events_recorded=len(self.events.events()),
            events_dropped=self.events.dropped,
            subscribers=self.events.subscriber_count,
        )

    def automation_rules(self) -> list:
        """Every registered rule, in firing order."""
        from veritriage.automation import enabled_rules

        return enabled_rules()

    def _automate(self, report) -> None:
        """Publish this run's events, evaluate rules, and dispatch what they ask for."""
        from veritriage.automation import RuleEngine
        from veritriage.models import AutomationContext, EventKind

        published: list = []
        published.append(
            self.publish_event(
                EventKind.ANALYSIS_COMPLETED,
                {
                    "classification": report.classification.category.value,
                    "confidence": report.classification.confidence,
                    "signals": ",".join(
                        s.name for s in (report.reasoning.signals if report.reasoning else [])
                    ),
                    "agent_conflicts": len(report.agents.conflicts) if report.agents else 0,
                    "agents_agree_with_reasoning": (
                        report.agents.agrees_with_reasoning if report.agents else None
                    ),
                    "design_region_size": (
                        len(report.design.affected_region) if report.design else 0
                    ),
                },
            )
        )
        if report.history is not None:
            published.append(
                self.publish_event(
                    EventKind.REGRESSION_DETECTED,
                    {
                        "regression_id": report.history.regression_id,
                        "signature": report.history.signature,
                        "seen_before": report.history.seen_before,
                        "times_seen": report.history.times_seen,
                    },
                    subject=report.history.regression_id,
                )
            )
        if report.plan is not None:
            published.append(
                self.publish_event(
                    EventKind.PLAN_GENERATED,
                    {"plan_id": report.plan.plan_id, "steps": len(report.plan.steps)},
                )
            )

        engine = RuleEngine()
        outcomes: list = []
        requests: list = []
        for event in published:
            for outcome in engine.evaluate(event):
                outcomes.append(outcome)
                requests.extend(outcome.requests)

        results = self.dispatch_actions(requests, report) if requests else []
        context = AutomationContext(
            events=published,
            outcomes=outcomes,
            rules_evaluated=len(outcomes),
            rules_fired=sorted({o.rule_id for o in outcomes if o.matched}),
            actions_requested=requests,
            actions_executed=results,
        )
        report.automation = None if context.is_empty else context

    def dispatch_actions(
        self, requests: "list[ActionRequest]", report=None
    ) -> "list[ActionResult]":
        """Execute what automation asked for, through methods this class has.

        The action vocabulary is a closed enum, so this dispatcher is the whole
        execution surface: there is no path from a rule to code the platform
        does not already own. Anything not safe to do unattended is recorded as
        skipped, with the reason.
        """
        from veritriage.models import ActionKind, ActionResult

        results: list = []
        for request in requests:
            rule_id = request.reason.split(":", 1)[0]
            try:
                executed, detail, skipped = self._perform(request, report)
                results.append(
                    ActionResult(
                        action=request.action,
                        requested_by=rule_id,
                        executed=executed,
                        detail=detail,
                        skipped_reason=skipped,
                    )
                )
            except Exception as exc:  # an action failure must not cost the analysis
                results.append(
                    ActionResult(
                        action=request.action,
                        requested_by=rule_id,
                        executed=False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
        return results

    def _perform(self, request, report) -> tuple[bool, str | None, str | None]:
        """One action. Returns (executed, detail, skipped_reason)."""
        from veritriage.models import ActionKind

        action = request.action
        if action is ActionKind.NOTIFY:
            # Recorded for a client to deliver. The platform calls no webhook.
            return True, request.reason, None
        if action is ActionKind.REFRESH_LEARNING:
            stats = self.learn_from_history()
            if stats is None:
                return False, None, "No regression database is configured."
            return True, f"Learned from {stats.corpus_size} recorded investigation(s).", None
        if action is ActionKind.GENERATE_PLAN:
            if report is None or report.plan is None:
                return False, None, "This run produced no investigation plan."
            return True, f"Plan {report.plan.plan_id} with {len(report.plan.steps)} step(s).", None
        if action is ActionKind.SUMMARIZE_CHANGES:
            if report is None:
                return False, None, "No report to summarize."
            return True, report.classification.summary, None
        if action is ActionKind.REBUILD_DESIGN_GRAPH:
            graph = self.design_graph()
            if graph is None:
                return False, None, "This workspace has no project model."
            return True, f"Design graph rebuilt: {len(graph.nodes)} element(s).", None
        if action is ActionKind.GENERATE_REPORT:
            # Rendering needs an output directory the caller chose, so this is
            # surfaced rather than guessed at.
            return False, None, (
                "Report rendering needs an output directory; run it explicitly with "
                "'veritriage analyze -o <dir>'."
            )
        if action is ActionKind.RUN_ANALYSIS:
            return False, None, (
                "Re-running analysis unattended is deliberately not automatic; the "
                "request is recorded for a caller to act on."
            )
        if action is ActionKind.EXPORT_BUNDLE:
            return False, None, (
                "Bundle export needs a destination path; the request is recorded for a "
                "caller to act on."
            )
        return False, None, f"No dispatcher for {action.value!r}."

    def save(self, session: InvestigationSession) -> Path:
        return self._store.save(session)

    def load(self, session_id: str) -> InvestigationSession | None:
        return self._store.load(session_id)

    def list_sessions(self) -> list[SessionSummary]:
        return self._store.list_sessions()

    def summary(self, session: InvestigationSession) -> InvestigationSummary:
        """The bounded answer to "what did this investigation conclude?"."""
        report = session.report
        top = (
            report.reasoning.hypotheses[0]
            if report.reasoning and report.reasoning.hypotheses
            else None
        )
        return InvestigationSummary(
            session_id=session.session_id,
            created_at=session.created_at.isoformat(),
            input_files=list(session.input_files),
            classification=report.classification.category.value,
            confidence=report.classification.confidence,
            top_hypothesis=top.title if top else None,
            top_hypothesis_id=top.id if top else None,
            top_hypothesis_confidence=round(top.confidence, 4) if top else None,
            evidence_nodes=report.graph_stats.node_count,
            matched_patterns=(
                [p.pattern_id for p in report.knowledge.patterns] if report.knowledge else []
            ),
            waveform_observations=(
                len(report.waveform.observations) if report.waveform else 0
            ),
            engineering_commits=(
                len(report.engineering.commits) if report.engineering else 0
            ),
            seen_before=report.history.seen_before if report.history else None,
            recommendations=(
                len(report.reasoning.recommendations) if report.reasoning else 0
            ),
        )

    # --- Evidence queries --------------------------------------------------

    def evidence(
        self,
        session: InvestigationSession,
        artifact_type: str | None = None,
        failing_only: bool = False,
    ) -> list[EvidenceNode]:
        """Evidence nodes, optionally filtered by type and failure status."""
        nodes = list(session.graph.nodes.values())
        if artifact_type is not None:
            wanted = ArtifactType(artifact_type)
            nodes = [n for n in nodes if n.artifact_type == wanted]
        if failing_only:
            nodes = [n for n in nodes if n.is_failing]
        return nodes

    def evidence_graph_view(
        self, session: InvestigationSession, max_nodes: int = 60
    ) -> dict:
        """The bounded, normalized graph projection (the same view AI gets)."""
        return session.graph.to_reasoning_view(max_nodes=max_nodes)

    def search(self, session: InvestigationSession, query: str) -> list[EvidenceHit]:
        return search_evidence(session, query)

    # --- Knowledge queries -------------------------------------------------

    def search_knowledge(self, query: str) -> list[KnowledgeHit]:
        return search_knowledge(query)

    def matched_patterns(self, session: InvestigationSession) -> list[MatchedPattern]:
        return list(session.report.knowledge.patterns) if session.report.knowledge else []

    # --- Layer views ---------------------------------------------------------

    def waveform_observations(
        self, session: InvestigationSession
    ) -> list[WaveformObservationView]:
        return list(session.report.waveform.observations) if session.report.waveform else []

    def engineering_context(
        self, session: InvestigationSession
    ) -> EngineeringContextView | None:
        return session.report.engineering

    def timeline(self, session: InvestigationSession) -> list[TimelineEventView]:
        """The investigation timeline; built from the graph when the report
        carries no engineering section (timeline works without context)."""
        if session.report.engineering is not None:
            return list(session.report.engineering.timeline)
        return build_timeline(session.graph, session.report)

    # --- History -------------------------------------------------------------

    def similar_regressions(
        self, session: InvestigationSession, limit: int = 5
    ) -> list[SimilarFailure]:
        """Historical regressions resembling this session, from the database.

        Read-only: the session is compared against history without being
        recorded (recording stays a CLI decision, as it has been since M4).
        Returns [] when the workspace has no database.
        """
        if self._db is None or not Path(self._db).is_file():
            return []
        from veritriage.history.record import RegressionRecord, extract_run_context
        from veritriage.signatures import build_signature
        from veritriage.similarity import SimilarFailureEngine
        from veritriage.storage import RegressionStore

        report, graph = session.report, session.graph
        signature = build_signature(report, graph)
        test_name, seed, configuration = extract_run_context(graph)
        probe = RegressionRecord(
            regression_id=f"probe-{session.session_id}",
            created_at=session.created_at or datetime.now(timezone.utc),
            test_name=test_name or report.summary.test_name,
            seed=seed,
            configuration=configuration,
            signature=signature,
            report=report,
            graph=graph,
        )
        with RegressionStore(self._db) as store:
            engine = SimilarFailureEngine(store)
            probe.embedding = engine.provider.embed(probe)
            return engine.find_similar(probe, top_k=limit)

    # --- Bundles and collaboration (M10) -----------------------------------
    #
    # Bundle operations delegate to the collab package through lazy imports,
    # so WorkspaceServices stays the single public boundary (clients never
    # import collab) with no import-time coupling: exactly how this class
    # already reaches storage, history, and reports.

    def export_bundle(
        self,
        session: InvestigationSession,
        path: Path,
        exported_by: str | None = None,
        title: str | None = None,
        compress: bool = True,
    ) -> Path:
        """Export a session as a portable, sealed investigation bundle file."""
        from veritriage.collab import export_bundle, make_bundle

        bundle = make_bundle(session, exported_by=exported_by, title=title)
        return export_bundle(bundle, path, compress=compress)

    def import_bundle(self, path: Path, save_session: bool = True):
        """Import a bundle file; optionally persist its session so the
        investigation can continue. Returns the bundle."""
        from veritriage.collab import import_bundle

        bundle = import_bundle(path)
        if save_session:
            self._store.save(bundle.session)
        return bundle

    def validate_bundle(self, path: Path):
        """Validate a bundle file; returns a deterministic ValidationResult."""
        from veritriage.collab import import_bundle, validate_bundle

        return validate_bundle(import_bundle(path))

    def review_bundle(
        self, path: Path, verdict: str, reviewer: str, comment: str = ""
    ) -> Path:
        """Append a review to a bundle file in place; returns the path."""
        from veritriage.collab import add_review, export_bundle, import_bundle

        reviewed = add_review(import_bundle(path), verdict, reviewer, comment)
        return export_bundle(reviewed, path)

    def annotate_bundle(
        self, path: Path, target_type: str, target_id: str, author: str, text: str
    ) -> Path:
        """Append an annotation to a bundle file in place; returns the path."""
        from veritriage.collab import add_annotation, export_bundle, import_bundle

        annotated = add_annotation(import_bundle(path), target_type, target_id, author, text)
        return export_bundle(annotated, path)

    def compare_bundles(self, a: Path, b: Path):
        """Explain what changed between two bundle files."""
        from veritriage.collab import compare_bundles, import_bundle

        return compare_bundles(import_bundle(a), import_bundle(b))

    def collaboration_view(self, path: Path) -> dict:
        """Plain collaboration data for the report's Collaboration section.

        Presentation only: built here so the reports package stays ignorant
        of bundle internals.
        """
        from veritriage.collab import import_bundle, review_status, validate_bundle

        bundle = import_bundle(path)
        result = validate_bundle(bundle)
        return {
            "bundle_id": bundle.bundle_id,
            "fingerprint": bundle.metadata.fingerprint,
            "title": bundle.metadata.title,
            "exported_by": bundle.metadata.exported_by,
            "review_status": review_status(bundle),
            "reviews": [
                {"verdict": r.verdict.value, "reviewer": r.reviewer, "comment": r.comment}
                for r in bundle.reviews
            ],
            "annotations": [
                {"target": f"{a.target_type}:{a.target_id}", "author": a.author, "text": a.text}
                for a in bundle.annotations
            ],
            "validation_ok": result.ok,
            "validation_findings": [
                {"severity": f.severity.value, "message": f.message} for f in result.findings
            ],
        }

    # --- Comparison ----------------------------------------------------------

    def compare(
        self, a: InvestigationSession, b: InvestigationSession
    ) -> ComparisonView:
        """Deterministic diff of two investigations: signature, class, evidence."""
        from veritriage.signatures import build_signature

        sig_a = build_signature(a.report, a.graph)
        sig_b = build_signature(b.report, b.graph)
        failing_a = {n.description for n in a.graph.failing()}
        failing_b = {n.description for n in b.graph.failing()}
        return ComparisonView(
            session_a=a.session_id,
            session_b=b.session_id,
            same_signature=sig_a.digest == sig_b.digest,
            classification_a=a.report.classification.category.value,
            classification_b=b.report.classification.category.value,
            shared_failing_descriptions=sorted(failing_a & failing_b),
            only_in_a=len(failing_a - failing_b),
            only_in_b=len(failing_b - failing_a),
        )

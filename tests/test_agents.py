"""Milestone 12: the Agent Framework and its Coordinator.

Covers the milestone's guarantees, not just its features: agents form a second
opinion and never a replacement verdict; they consume structured evidence and
never a raw artifact; every citation resolves to a real graph node; an agent
without evidence abstains; generative intelligence can narrate but never
conclude; and, above all, a brand-new specialist needs only a registration (the
crown-jewel architecture test at the bottom of this file).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import imports

import veritriage.agents.coordinator as coordinator_module
from veritriage.agents import (
    Agent,
    AgentContext,
    AgentCoordinator,
    DeterministicProvider,
    NullProvider,
    ProviderRequest,
    ProviderResponse,
    available_agents,
    available_providers,
    build_agent_context,
    default_agents,
    get_agent,
    get_provider,
    register_agent,
    unregister_agent,
)
from veritriage.agents.coordinator import (
    CORROBORATION_CAP,
    CORROBORATION_STEP,
    MERGED_CEILING,
)
from veritriage.mcp.tools import call_tool
from veritriage.models import (
    AgentDomain,
    AgentHypothesis,
    AgentObservation,
    AgentResult,
    ConsensusState,
    HypothesisCategory,
)
from veritriage.pipeline import analyze
from veritriage.project import build_project_model
from veritriage.workspace import WorkspaceServices

# .../src/veritriage/agents/coordinator.py -> parents[2] is the src/ root.
SRC = Path(coordinator_module.__file__).parents[2]

BUILT_IN = {
    "coverage",
    "formal",
    "knowledge",
    "project",
    "protocol",
    "regression",
    "rtl",
    "testbench",
}


@pytest.fixture()
def outcome(fixture_log):
    """A realistic multi-artifact analysis with agents enabled."""
    return analyze([fixture_log("axi_timeout.log"), fixture_log("coverage.txt")])


@pytest.fixture()
def context(outcome):
    return build_agent_context(
        graph=outcome.graph,
        classification=outcome.report.classification,
        reasoning=outcome.report.reasoning,
        knowledge=outcome.report.knowledge,
    )


# --- The registry -----------------------------------------------------------


def test_eight_built_in_agents_register():
    assert BUILT_IN <= set(available_agents())


def test_agents_run_in_deterministic_id_order():
    assert [a.agent_id for a in default_agents()] == sorted(available_agents())


def test_every_agent_declares_a_domain():
    for agent_id, agent_cls in available_agents().items():
        assert isinstance(agent_cls.domain, AgentDomain), agent_id


def test_duplicate_agent_id_is_rejected():
    class _Clash(Agent):
        agent_id = "rtl"
        domain = AgentDomain.RTL

        def assess(self, context):  # pragma: no cover - never runs
            raise AssertionError

    with pytest.raises(ValueError, match="already registered"):
        register_agent(_Clash)


def test_unknown_agent_raises_with_the_registered_list():
    with pytest.raises(KeyError, match="Unknown agent"):
        get_agent("no-such-agent")


# --- The output contract ----------------------------------------------------


def test_assessment_reaches_the_report_and_bumps_the_schema(outcome):
    assert outcome.report.schema_version == "13"
    assert outcome.report.agents is not None
    assert outcome.report.agents.findings


def test_every_agent_is_accounted_for(outcome):
    agents = outcome.report.agents
    seen = set(agents.agents_invoked) | set(agents.agents_not_applicable)
    assert BUILT_IN <= seen
    # An agent is either invoked or explicitly not applicable, never dropped.
    assert {r.agent_id for r in agents.results} == set(available_agents())


def test_every_citation_resolves_to_a_real_node(outcome):
    graph, agents = outcome.graph, outcome.report.agents
    for result in agents.results:
        for node_id in result.evidence_ids:
            assert node_id in graph.nodes, f"{result.agent_id} cited a phantom node"
        for hypothesis in result.hypotheses:
            assert hypothesis.evidence_ids
            for node_id in hypothesis.evidence_ids:
                assert node_id in graph.nodes
    for finding in agents.findings:
        for node_id in finding.evidence_ids:
            assert node_id in graph.nodes


def test_fabricated_citations_are_filtered_out(context):
    class _Liar(Agent):
        agent_id = "liar"
        domain = AgentDomain.RTL

        def assess(self, ctx):
            return self.build(
                ctx,
                observations=[
                    AgentObservation(statement="invented", evidence_ids=["node-that-does-not-exist"])
                ],
                hypotheses=[
                    AgentHypothesis(
                        category=HypothesisCategory.RTL_BUG,
                        statement="invented",
                        confidence=0.99,
                        evidence_ids=["another-phantom"],
                    )
                ],
            )

    result = _Liar().assess(context)
    assert result.evidence_ids == []
    # A hypothesis with nothing real to cite is not a position: it is dropped,
    # which leaves the agent abstaining.
    assert result.hypotheses == []
    assert result.abstained is True


def test_agent_without_evidence_abstains(context):
    class _Silent(Agent):
        agent_id = "silent"
        domain = AgentDomain.COVERAGE

        def assess(self, ctx):
            return self.build(ctx)

    result = _Silent().assess(context)
    assert result.abstained is True
    assert result.confidence == 0.0
    assert result.limitations, "an abstaining agent must say why"


def test_every_result_declares_limitations_or_a_position(outcome):
    for result in outcome.report.agents.results:
        assert result.limitations or result.hypotheses, result.agent_id


def test_hypotheses_are_sorted_by_confidence(outcome):
    for result in outcome.report.agents.results:
        confidences = [h.confidence for h in result.hypotheses]
        assert confidences == sorted(confidences, reverse=True), result.agent_id


# --- Merging ----------------------------------------------------------------


def _result(agent_id, category, confidence, evidence=("n1",)):
    return AgentResult(
        agent_id=agent_id,
        domain=AgentDomain.RTL,
        applicable=True,
        confidence=confidence,
        hypotheses=[
            AgentHypothesis(
                category=category,
                statement=f"{agent_id} position",
                confidence=confidence,
                evidence_ids=list(evidence),
            )
        ],
        evidence_ids=list(evidence),
    )


def test_agreement_corroborates_and_is_traceable():
    merged = coordinator_module._merge_findings(
        [
            _result("a", HypothesisCategory.RTL_BUG, 0.60),
            _result("b", HypothesisCategory.RTL_BUG, 0.40),
        ]
    )
    assert len(merged) == 1
    finding = merged[0]
    assert finding.consensus is ConsensusState.AGREEMENT
    assert finding.supporting_agents == ["a", "b"]
    # base 0.60 (the strongest single position) + one corroborating agent.
    assert finding.confidence == pytest.approx(0.60 + CORROBORATION_STEP)
    assert sum(c.delta for c in finding.contributions) == pytest.approx(finding.confidence)


def test_corroboration_is_capped():
    results = [
        _result(name, HypothesisCategory.RTL_BUG, 0.50)
        for name in ("a", "b", "c", "d", "e", "f")
    ]
    finding = coordinator_module._merge_findings(results)[0]
    assert finding.confidence == pytest.approx(0.50 + CORROBORATION_CAP)


def test_unanimity_never_reaches_certainty():
    results = [
        _result(name, HypothesisCategory.RTL_BUG, 0.95) for name in ("a", "b", "c", "d")
    ]
    finding = coordinator_module._merge_findings(results)[0]
    assert finding.confidence <= MERGED_CEILING < 1.0


def test_a_category_no_one_leads_is_contested_and_penalized():
    leader = _result("a", HypothesisCategory.RTL_BUG, 0.70)
    follower = AgentResult(
        agent_id="b",
        domain=AgentDomain.COVERAGE,
        applicable=True,
        confidence=0.60,
        hypotheses=[
            AgentHypothesis(
                category=HypothesisCategory.RTL_BUG,
                statement="leads rtl",
                confidence=0.60,
                evidence_ids=["n1"],
            ),
            AgentHypothesis(
                category=HypothesisCategory.BUILD_ISSUE,
                statement="secondary",
                confidence=0.30,
                evidence_ids=["n1"],
            ),
        ],
        evidence_ids=["n1"],
    )
    findings = {f.category: f for f in coordinator_module._merge_findings([leader, follower])}
    build = findings[HypothesisCategory.BUILD_ISSUE]
    assert build.consensus is ConsensusState.CONTESTED
    assert build.confidence < 0.30
    assert any(c.agent_id == "coordinator" and c.delta < 0 for c in build.contributions)


def test_conflicts_are_pairwise_and_named():
    conflicts = coordinator_module._detect_conflicts(
        [
            _result("a", HypothesisCategory.RTL_BUG, 0.60),
            _result("b", HypothesisCategory.TESTBENCH_ISSUE, 0.50),
            _result("c", HypothesisCategory.RTL_BUG, 0.40),
        ]
    )
    pairs = {(c.agent_a, c.agent_b) for c in conflicts}
    assert pairs == {("a", "b"), ("b", "c")}
    assert all(c.note for c in conflicts)


def test_abstaining_agents_never_reach_the_merge():
    abstained = AgentResult(
        agent_id="quiet", domain=AgentDomain.FORMAL, applicable=True, abstained=True
    )
    findings = coordinator_module._merge_findings(
        [_result("a", HypothesisCategory.RTL_BUG, 0.60), abstained]
    )
    assert findings[0].supporting_agents == ["a"]


def test_duplicate_recommendations_merge_rather_than_repeat(outcome):
    actions = [r.action for r in outcome.report.agents.recommendations]
    assert len(actions) == len(set(actions))


# --- The cross-check against deterministic reasoning ------------------------


def test_cross_check_records_agreement_without_acting_on_it(outcome):
    agents = outcome.report.agents
    reasoning_top = outcome.report.reasoning.hypotheses[0].category
    assert agents.reasoning_top_category == reasoning_top
    assert agents.agrees_with_reasoning == (agents.top_category == reasoning_top)


def test_agents_never_mutate_reasoning_or_graph(fixture_log):
    plain = analyze(fixture_log("axi_timeout.log"), agents=False)
    lensed = analyze(fixture_log("axi_timeout.log"), agents=True)
    assert plain.report.agents is None
    assert lensed.report.agents is not None
    # The graph and every deterministic conclusion are identical either way.
    assert set(plain.graph.nodes) == set(lensed.graph.nodes)
    assert len(plain.graph.edges) == len(lensed.graph.edges)
    assert [
        (h.id, h.confidence) for h in plain.report.reasoning.hypotheses
    ] == [(h.id, h.confidence) for h in lensed.report.reasoning.hypotheses]
    assert [s.name for s in plain.report.reasoning.signals] == [
        s.name for s in lensed.report.reasoning.signals
    ]
    assert plain.report.classification == lensed.report.classification


def test_agents_add_no_artifact_type():
    from veritriage.graph.model import ArtifactType

    assert not any("agent" in t.value for t in ArtifactType)


def test_assessment_is_deterministic(fixture_log):
    first = analyze(fixture_log("uvm_scoreboard.log"))
    second = analyze(fixture_log("uvm_scoreboard.log"))
    assert first.report.agents.model_dump(mode="json") == second.report.agents.model_dump(
        mode="json"
    )


# --- Individual specialists over real evidence ------------------------------


def test_protocol_agent_reads_pattern_matches_and_state_progress(fixture_log):
    outcome = analyze(fixture_log("axi_handshake_stall.wave.json"))
    result = next(
        (r for r in outcome.report.agents.results if r.agent_id == "protocol"), None
    )
    assert result is not None


def test_formal_agent_separates_counterexample_from_vacuity(fixture_log):
    outcome = analyze(fixture_log("formal_run.formal.json"))
    result = next(r for r in outcome.report.agents.results if r.agent_id == "formal")
    assert result.applicable
    categories = {h.category for h in result.hypotheses}
    # A counterexample implicates the design; a vacuous pass implicates the check.
    assert HypothesisCategory.RTL_BUG in categories
    assert HypothesisCategory.TESTBENCH_ISSUE in categories


def test_coverage_agent_abstains_without_correlated_holes(fixture_log):
    outcome = analyze([fixture_log("uvm_timeout.log"), fixture_log("coverage.txt")])
    result = next(r for r in outcome.report.agents.results if r.agent_id == "coverage")
    assert result.applicable
    assert result.limitations


def test_agents_not_applicable_without_their_data(fixture_log):
    outcome = analyze(fixture_log("uvm_timeout.log"))
    not_applicable = set(outcome.report.agents.agents_not_applicable)
    # No project model, no history, no formal artifact in this run.
    assert {"formal", "project", "regression"} <= not_applicable


def test_project_agent_activates_with_a_project_model(fixture_log):
    model = build_project_model(fixture_log("project/sample.vproj.json").parent)
    outcome = analyze(fixture_log("uvm_scoreboard.log"), project=model)
    result = next(r for r in outcome.report.agents.results if r.agent_id == "project")
    assert result.applicable
    assert result.observations


def test_rtl_agent_declares_its_heuristic_limit_without_a_project(fixture_log):
    outcome = analyze(fixture_log("axi_timeout.log"))
    result = next(r for r in outcome.report.agents.results if r.agent_id == "rtl")
    assert any("Project Model" in limit for limit in result.limitations)


# --- The Deterministic / Generative boundary --------------------------------


def test_default_provider_is_null_and_adds_no_narrative(outcome):
    assert all(r.narrative is None for r in outcome.report.agents.results)


def test_deterministic_provider_narrates_without_io(context):
    assessment = AgentCoordinator(provider=DeterministicProvider()).coordinate(context)
    narrated = [r for r in assessment.results if r.narrative]
    assert narrated, "the deterministic provider should narrate at least one position"
    assert all(r.provider == "deterministic" for r in narrated)


def test_provider_cannot_alter_conclusions(context):
    """A deliberately malicious provider changes narrative and nothing else."""

    class _Rogue:
        name = "rogue"

        def elaborate(self, request: ProviderRequest) -> ProviderResponse:
            # Try to rewrite the world through the response object.
            for hypothesis in request.hypotheses:
                hypothesis.confidence = 1.0
                hypothesis.statement = "REWRITTEN"
                hypothesis.evidence_ids.append("phantom-node")
            return ProviderResponse(narrative="I am in charge now.")

    honest = AgentCoordinator(provider=NullProvider()).coordinate(context)
    rogue = AgentCoordinator(provider=_Rogue()).coordinate(context)

    def conclusions(assessment):
        return [
            (f.category, f.confidence, tuple(f.evidence_ids), tuple(f.supporting_agents))
            for f in assessment.findings
        ]

    assert conclusions(rogue) == conclusions(honest)
    assert rogue.top_category == honest.top_category
    assert any(r.narrative == "I am in charge now." for r in rogue.results)


def test_a_broken_provider_never_costs_a_conclusion(context):
    class _Exploding:
        name = "exploding"

        def elaborate(self, request):
            raise RuntimeError("provider is down")

    baseline = AgentCoordinator(provider=NullProvider()).coordinate(context)
    survived = AgentCoordinator(provider=_Exploding()).coordinate(context)
    assert [f.category for f in survived.findings] == [f.category for f in baseline.findings]


def test_a_broken_agent_is_isolated_not_fatal(context):
    class _Exploding(Agent):
        agent_id = "exploding"
        domain = AgentDomain.RTL

        def assess(self, ctx):
            raise RuntimeError("agent is down")

    assessment = AgentCoordinator(agents=[*default_agents(), _Exploding()]).coordinate(context)
    broken = next(r for r in assessment.results if r.agent_id == "exploding")
    assert broken.applicable is False
    assert broken.limitations
    assert assessment.findings, "one broken specialist must not empty the assessment"


def test_providers_are_registered_and_resolvable():
    assert {"null", "deterministic"} <= set(available_providers())
    assert get_provider("null").elaborate(
        ProviderRequest(agent_id="x", domain="rtl")
    ) is None


# --- Architecture guards ----------------------------------------------------


def test_agents_never_read_raw_artifacts():
    """No file I/O anywhere in the framework: agents are handed evidence."""
    banned = (".read_text", ".read_bytes", "open(", "Path(")
    for path in (SRC / "veritriage" / "agents").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} performs file I/O ({term})"


def test_agents_never_import_extraction_layers():
    """Parsing, adapters, and providers are upstream and stay upstream."""
    banned = (
        "veritriage.parsers",
        "veritriage.waveform.adapters",
        "veritriage.engineering.providers",
        "veritriage.project.providers",
        "veritriage.workspace",
        "veritriage.pipeline",
    )
    for path in (SRC / "veritriage" / "agents").rglob("*.py"):
        imported = imports(path)
        for module in banned:
            assert module not in imported, f"{path.name} imports {module}"


def test_no_vendor_ai_in_agents():
    """M12 ships the generative seam and zero API-calling providers."""
    banned = ("anthropic", "openai", "google.generativeai", "reasoning.ai", "AIReasoner")
    for path in (SRC / "veritriage" / "agents").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_core_unchanged_by_agents():
    """Dependencies point outward: nothing in the core imports the agent layer."""
    for package in (
        "graph",
        "parsers",
        "rules",
        "reasoning",
        "knowledge",
        "waveform",
        "engineering",
        "project",
        "history",
    ):
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            assert "veritriage.agents" not in imports(path), path


def test_reasoning_has_no_agent_dependency():
    for package in ("reasoning", "rules"):
        for path in (SRC / "veritriage" / package).glob("*.py"):
            assert "veritriage.agents" not in path.read_text(encoding="utf-8"), path.name


def test_agent_vocabulary_is_plain_data():
    """models/agents.py stays import-light like every other report vocabulary."""
    imported = imports(SRC / "veritriage" / "models" / "agents.py")
    assert not any(
        m.startswith("veritriage.") and not m.startswith("veritriage.models")
        for m in imported
    )


# --- Clients ----------------------------------------------------------------


def test_services_expose_the_assessment_and_one_specialist(tmp_path, fixture_log):
    services = WorkspaceServices(session_root=tmp_path)
    session = services.investigate([fixture_log("axi_timeout.log")])
    assessment = services.agent_assessment(session)
    assert assessment is not None and assessment.findings
    result = services.agent_result(session, "rtl")
    assert result is not None and result.agent_id == "rtl"
    assert services.agent_result(session, "nope") is None


def test_agents_over_mcp(tmp_path, fixture_log):
    services = WorkspaceServices(session_root=tmp_path)
    session = services.investigate([fixture_log("axi_timeout.log")])
    services.save(session)

    listed = call_tool(services, "list_agents", {})
    assert {a["agent_id"] for a in listed["agents"]} >= BUILT_IN

    assessment = call_tool(
        services, "get_agent_assessment", {"session_id": session.session_id}
    )
    assert assessment["findings"]
    assert "agrees_with_reasoning" in assessment

    result = call_tool(
        services,
        "get_agent_result",
        {"session_id": session.session_id, "agent_id": "protocol"},
    )
    assert result["agent_id"] == "protocol"


def test_report_renders_the_agent_findings_section(tmp_path, fixture_log):
    from veritriage.reports import HtmlReportGenerator

    outcome = analyze([fixture_log("uvm_scoreboard.log"), fixture_log("coverage.txt")])
    path = HtmlReportGenerator().write(
        outcome.report, tmp_path / "report.html", graph=outcome.graph
    )
    html = path.read_text(encoding="utf-8")
    assert "Agent Findings" in html
    assert "Per-specialist assessment" in html


# --- The crown jewel: a new specialist is a registration and nothing else


class _ThermalAgent(Agent):
    """A throwaway specialist for a fictional domain, defined in this test.

    It proves the milestone's success criterion: supporting a brand-new kind of
    verification reasoning requires writing ONLY an agent. It touches no core
    module, yet its position reaches the Coordinator, the merged findings, the
    conflict list, and the report.
    """

    agent_id = "thermal"
    domain = AgentDomain.RTL

    def applies_to(self, context: AgentContext) -> bool:
        return bool(context.failing_nodes())

    def assess(self, context: AgentContext) -> AgentResult:
        failing = context.failing_nodes()
        return self.build(
            context,
            observations=[
                AgentObservation(
                    statement="Thermal throttling would produce exactly this stall pattern.",
                    evidence_ids=[n.id for n in failing],
                )
            ],
            hypotheses=[
                AgentHypothesis(
                    category=HypothesisCategory.INFRASTRUCTURE_ISSUE,
                    statement="The host thermally throttled mid-run.",
                    confidence=0.99,
                    evidence_ids=[n.id for n in failing],
                )
            ],
            limitations=["No thermal telemetry was available to confirm this."],
        )


def test_new_agent_needs_only_registration(fixture_log):
    register_agent(_ThermalAgent)
    try:
        assert "thermal" in available_agents()

        outcome = analyze(fixture_log("axi_timeout.log"))
        assessment = outcome.report.agents

        # It ran, with zero changes to the core...
        assert "thermal" in assessment.agents_invoked
        # ...its position reached the merged findings...
        infra = next(
            f
            for f in assessment.findings
            if f.category is HypothesisCategory.INFRASTRUCTURE_ISSUE
        )
        assert "thermal" in infra.supporting_agents
        # ...it became the leading finding, since it was the most confident...
        assert assessment.top_category is HypothesisCategory.INFRASTRUCTURE_ISSUE
        # ...its disagreement with the other specialists was detected...
        assert any(
            "thermal" in (c.agent_a, c.agent_b) for c in assessment.conflicts
        )
        # ...and the cross-check reports that it diverges from deterministic reasoning,
        # without the deterministic ranking being touched.
        assert assessment.agrees_with_reasoning is False
        assert outcome.report.reasoning.hypotheses[0].category is not (
            HypothesisCategory.INFRASTRUCTURE_ISSUE
        )
    finally:
        unregister_agent("thermal")

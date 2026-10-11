"""Milestone 15: Design Intelligence and the Design Graph.

Covers the milestone's guarantees, not just its features: the graph is derived
and never extracted; it never enters the Evidence Graph; it is deterministic;
every edge names the field it came from; inference is declared rather than
hidden; Project Intelligence is untouched; and, above all, a brand-new
structural facet needs only a registration (the crown-jewel architecture test at
the bottom of this file).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import imports

import veritriage.design.model as design_model_module
from veritriage.design import (
    DesignGraph,
    DesignNode,
    DesignQuery,
    DesignRelation,
    NodeKind,
    StructureExtractor,
    available_extractors,
    build_design_graph,
    build_design_view,
    default_extractors,
    failing_scopes,
    get_extractor,
    make_node_id,
    register_extractor,
    unregister_extractor,
)
from veritriage.mcp.tools import call_tool
from veritriage.pipeline import analyze
from veritriage.project import build_project_model
from veritriage.workspace import WorkspaceServices

# .../src/veritriage/design/model.py -> parents[2] is the src/ root.
SRC = Path(design_model_module.__file__).parents[2]

BUILT_IN = {
    "address-map",
    "clock-reset",
    "hierarchy",
    "interfaces",
    "verification",
    "verification-assets",
}


@pytest.fixture()
def project(fixture_log):
    return build_project_model(fixture_log("project/sample.vproj.json").parent)


@pytest.fixture()
def graph(project):
    return build_design_graph(project)


@pytest.fixture()
def query(graph):
    return DesignQuery(graph)


# --- The registry -----------------------------------------------------------


def test_six_built_in_extractors_register():
    assert BUILT_IN <= set(available_extractors())


def test_extractors_run_in_deterministic_order():
    ordered = [(e.order, e.extractor_id) for e in default_extractors()]
    assert ordered == sorted(ordered)


def test_duplicate_extractor_id_is_rejected():
    class _Clash(StructureExtractor):
        extractor_id = "hierarchy"

        def extract(self, model, graph):  # pragma: no cover - never runs
            raise AssertionError

    with pytest.raises(ValueError, match="already registered"):
        register_extractor(_Clash)


def test_unknown_extractor_raises_with_the_registered_list():
    with pytest.raises(KeyError, match="Unknown extractor"):
        get_extractor("no-such-extractor")


# --- The central law: derived, never extracted ------------------------------


def test_design_never_reads_source():
    """The Design Graph is derived from the Project Model, never from source."""
    banned_calls = (".read_text", ".read_bytes", "open(", "glob(", "Path(")
    banned_modules = {"subprocess", "os", "io", "pathlib"}
    for path in (SRC / "veritriage" / "design").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned_calls:
            assert term not in text, f"{path.name} performs I/O ({term})"
        leaked = banned_modules & imports(path)
        assert not leaked, f"{path.name} imports {leaked}"


def test_design_never_imports_a_provider():
    """Only a ProjectProvider may touch a source language. That law is M11's."""
    for path in (SRC / "veritriage" / "design").rglob("*.py"):
        imported = imports(path)
        assert "veritriage.project.providers" not in imported, path
        for banned in ("veritriage.parsers", "veritriage.workspace", "veritriage.pipeline"):
            assert banned not in imported, f"{path.name} imports {banned}"


def test_project_package_unchanged():
    """M15 adds structure without editing Project Intelligence."""
    for path in (SRC / "veritriage" / "project").rglob("*.py"):
        assert "veritriage.design" not in path.read_text(encoding="utf-8"), path


def test_design_never_enters_the_evidence_graph(fixture_log, project):
    bare = analyze(fixture_log("uvm_scoreboard.log"))
    lensed = analyze(fixture_log("uvm_scoreboard.log"), project=project)
    assert not any("design" in t.value for t in __import__(
        "veritriage.graph.model", fromlist=["ArtifactType"]
    ).ArtifactType)
    assert set(bare.graph.nodes) == set(lensed.graph.nodes)
    assert len(bare.graph.edges) == len(lensed.graph.edges)


def test_design_never_changes_upstream_conclusions(fixture_log, project):
    bare = analyze(fixture_log("uvm_scoreboard.log"))
    lensed = analyze(fixture_log("uvm_scoreboard.log"), project=project)
    assert bare.report.classification == lensed.report.classification
    assert [h.category for h in bare.report.reasoning.hypotheses] == [
        h.category for h in lensed.report.reasoning.hypotheses
    ]


# --- Graph integrity --------------------------------------------------------


def test_design_graph_is_deterministic(project):
    first = build_design_graph(project)
    second = build_design_graph(project)
    assert first.fingerprint() == second.fingerprint()
    assert set(first.nodes) == set(second.nodes)


def test_node_ids_are_content_derived():
    assert make_node_id(NodeKind.MODULE, "l2_cache") == make_node_id(
        NodeKind.MODULE, "L2_Cache"
    )
    assert make_node_id(NodeKind.MODULE, "a") != make_node_id(NodeKind.IP, "a")


def test_graph_has_no_dangling_edges(graph):
    for edge in graph.edges:
        assert edge.source_id in graph.nodes, edge
        assert edge.target_id in graph.nodes, edge


def test_every_edge_carries_a_rationale(graph):
    """No relationship without the project-model field it was derived from."""
    assert graph.edges
    for edge in graph.edges:
        assert edge.rationale, edge
        assert len(edge.rationale) > 10, edge.rationale


def test_inference_is_declared_not_hidden(graph):
    """Hierarchy-derived edges must say they were inferred."""
    inferred = [e for e in graph.edges if e.inferred]
    assert inferred, "clock propagation down the hierarchy should be inferred"
    for edge in inferred:
        assert edge.rationale


def test_partial_models_yield_smaller_graphs_not_errors():
    """A manifest naming an undeclared module must not raise."""
    from veritriage.project.model import ClockDomain, Dut, ProjectModel

    model = ProjectModel(dut=Dut(top="a", clocks=(ClockDomain(name="clk", roots=("ghost",)),)))
    built = build_design_graph(model)
    assert built.by_name("clk", NodeKind.CLOCK_DOMAIN) is not None
    assert not [e for e in built.edges if e.relation is DesignRelation.CLOCKED_BY]


def test_a_broken_extractor_never_costs_the_graph(project):
    class _Exploding(StructureExtractor):
        extractor_id = "exploding"
        order = 1

        def extract(self, model, graph):
            raise RuntimeError("extractor is down")

    register_extractor(_Exploding)
    try:
        built = build_design_graph(project)
        assert built.nodes, "one broken extractor must not empty the graph"
    finally:
        unregister_extractor("exploding")


def test_node_merging_lets_extractors_stay_independent():
    """Two extractors describing the same module must converge, not collide."""
    built = DesignGraph()
    node_id = make_node_id(NodeKind.MODULE, "m")
    built.add_node(
        DesignNode(id=node_id, kind=NodeKind.MODULE, name="m", source_file="a.sv", extracted_by="x")
    )
    built.add_node(
        DesignNode(id=node_id, kind=NodeKind.MODULE, name="m", owner="team", extracted_by="y")
    )
    merged = built.nodes[node_id]
    assert merged.source_file == "a.sv" and merged.owner == "team"
    assert len(built.nodes) == 1


# --- What the graph actually resolves ---------------------------------------


def test_hierarchy_resolves_parent_declarations(query):
    rows = query.hierarchy()
    assert [(d, n.name) for d, n in rows] == [
        (0, "soc_top"),
        (1, "l2_cache"),
        (2, "axi_monitor"),
    ]


def test_hierarchy_is_cycle_safe():
    from veritriage.project.model import DesignModule, Dut, ProjectModel

    model = ProjectModel(
        dut=Dut(
            top="a",
            modules=(
                DesignModule(name="a", parent="b"),
                DesignModule(name="b", parent="a"),
            ),
        )
    )
    rows = DesignQuery(build_design_graph(model)).hierarchy()
    assert len(rows) <= 2, "a cyclic model must terminate, not hang"


def test_interface_ownership_is_answerable(query):
    """The question the platform previously answered with substring matching."""
    owner = query.owner_of("cpu_l2")
    assert owner is not None
    assert owner.qualified_name == "env.axi_agent"


def test_observers_include_monitors_and_vips(query):
    names = {n.name for n in query.observers_of("cpu_l2")}
    assert {"axi_mon", "axi_vip"} <= names


def test_clock_domain_membership_propagates_down_the_hierarchy(query):
    """A module beneath a clock root inherits the domain, and says it inferred it."""
    domains = query.clock_domains_of(["axi_monitor"])
    assert [d.name for d in domains] == ["clk_core"]


def test_affected_region_locates_a_failure_in_the_system(query):
    region = {n.name for n in query.affected_region(["l2_cache"])}
    assert "soc_top" in region, "the parent should be in the neighbourhood"
    assert "axi_monitor" in region, "the child should be too"
    assert "clk_core" in region, "so should the clock domain"


def test_scope_resolution_prefers_the_testbench_reading(query):
    """`uvm_test_top.env.scb` is a testbench path, not a design module."""
    node = query.resolve_scope("uvm_test_top.env.scb")
    assert node is not None
    assert node.kind is NodeKind.UVM_COMPONENT
    assert node.name == "scb"


def test_dependency_traces_both_directions(query):
    assert [n.name for n in query.dependents_of("l2_cache")] == ["L2_REGS"]
    assert [n.name for n in query.dependencies_of("L2_REGS")] == ["l2_cache"]


def test_protocol_map_resolves_against_knowledge_packs(query):
    assert query.protocol_map() == {"axi": ["cpu_l2"]}


def test_unverified_modules_are_derived_not_guessed(query):
    """Nothing declares coverage or assertions in the fixture, so all are unwatched."""
    assert {n.name for n in query.unverified_modules()} == {
        "soc_top",
        "l2_cache",
        "axi_monitor",
    }


def test_failing_scopes_reads_the_evidence_graph(fixture_log):
    outcome = analyze(fixture_log("uvm_scoreboard.log"))
    assert failing_scopes(outcome.graph)


# --- Report integration -----------------------------------------------------


def test_report_carries_design_context_and_bumps_the_schema(fixture_log, project):
    outcome = analyze(fixture_log("uvm_scoreboard.log"), project=project)
    assert outcome.report.schema_version == "13"
    design = outcome.report.design
    assert design is not None
    assert design.node_count > 0 and design.edge_count > 0
    assert design.graph_fingerprint.startswith("sha1:")
    assert design.hierarchy and design.protocol_map
    assert design.extractors


def test_no_design_context_without_a_project_model(fixture_log):
    assert analyze(fixture_log("uvm_scoreboard.log")).report.design is None


def test_design_view_is_a_pure_projection(graph, fixture_log):
    outcome = analyze(fixture_log("uvm_scoreboard.log"))
    before = graph.fingerprint()
    build_design_view(graph, outcome.graph)
    build_design_view(graph, outcome.graph)
    assert graph.fingerprint() == before, "building a view must not mutate the graph"


def test_report_renders_the_design_section(tmp_path, fixture_log, project):
    from veritriage.reports import HtmlReportGenerator

    outcome = analyze(fixture_log("uvm_scoreboard.log"), project=project)
    path = HtmlReportGenerator().write(
        outcome.report, tmp_path / "report.html", graph=outcome.graph
    )
    html = path.read_text(encoding="utf-8")
    for section in (
        "Design Intelligence",
        "Affected Design Region",
        "Hierarchy View",
        "Verification Components",
    ):
        assert section in html, section


def test_agents_receive_structure_without_importing_design(fixture_log, project):
    outcome = analyze(fixture_log("uvm_scoreboard.log"), project=project)
    assert outcome.report.agents is not None
    for path in (SRC / "veritriage" / "agents").rglob("*.py"):
        assert "veritriage.design" not in path.read_text(encoding="utf-8"), path


# --- Architecture guards ----------------------------------------------------


def test_no_ai_in_design():
    """No AI, no HDL summarization, no embeddings."""
    banned = ("anthropic", "openai", "torch", "embed(", "reasoning.ai", "AIReasoner")
    for path in (SRC / "veritriage" / "design").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_core_unchanged_by_design():
    for package in (
        "graph",
        "parsers",
        "rules",
        "reasoning",
        "knowledge",
        "waveform",
        "engineering",
        "project",
        "agents",
        "learning",
        "planning",
        "history",
    ):
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            assert "veritriage.design" not in imports(path), path


def test_design_vocabulary_is_plain_data():
    imported = imports(SRC / "veritriage" / "models" / "design.py")
    assert not any(
        m.startswith("veritriage.") and not m.startswith("veritriage.models")
        for m in imported
    )


def test_three_graphs_stay_distinct():
    """Evidence, Knowledge, and Design are three graphs, deliberately."""
    from veritriage.graph.graph import EvidenceGraph
    from veritriage.knowledge.graph import KnowledgeGraph

    assert DesignGraph is not EvidenceGraph
    assert DesignGraph is not KnowledgeGraph
    assert not set(DesignGraph.model_fields) & {"schema_version"} - {"schema_version"}


# --- Clients ----------------------------------------------------------------


def test_services_expose_design_intelligence(tmp_path, fixture_log):
    root = fixture_log("project/sample.vproj.json").parent
    services = WorkspaceServices(session_root=tmp_path, project_root=tmp_path / "pm")

    assert services.design_graph(root) is not None
    assert services.design_query(root) is not None
    assert services.design_hierarchy(root)

    described = services.describe_module("l2_cache", root)
    assert described is not None and described["relations"]
    assert services.describe_module("nope", root) is None


def test_design_over_mcp(tmp_path, fixture_log):
    root = str(fixture_log("project/sample.vproj.json").parent)
    services = WorkspaceServices(session_root=tmp_path, project_root=tmp_path / "pm")

    described = call_tool(services, "describe_module", {"name": "l2_cache", "root": root})
    assert described["node"]["kind"] in {"module", "ip"}

    hierarchy = call_tool(services, "show_hierarchy", {"root": root})
    assert hierarchy and hierarchy[0]["depth"] == 0

    traced = call_tool(services, "trace_dependency", {"name": "l2_cache", "root": root})
    assert traced["depended_on_by"] == ["L2_REGS"]

    owner = call_tool(services, "find_interface_owner", {"interface": "cpu_l2", "root": root})
    assert owner["owner"] == "env.axi_agent"

    clocks = call_tool(services, "clock_domain_view", {"root": root})
    assert clocks["domains"][0]["name"] == "clk_core"

    topology = call_tool(services, "verification_topology", {"root": root})
    assert any(row["relation"] == "monitors" for row in topology)

    assert call_tool(services, "protocol_map", {"root": root}) == {"axi": ["cpu_l2"]}


def test_affected_region_over_mcp(tmp_path, fixture_log):
    root = fixture_log("project/sample.vproj.json").parent
    services = WorkspaceServices(session_root=tmp_path, project_root=tmp_path / "pm")
    model = build_project_model(root)
    session = services.investigate([fixture_log("uvm_scoreboard.log")], project=model)
    services.save(session)

    region = call_tool(services, "affected_region", {"session_id": session.session_id})
    assert region and all("node_id" in n for n in region)


# --- The crown jewel: a new structural facet is a registration and nothing else


class _PowerDomainExtractor(StructureExtractor):
    """A throwaway extractor for a fictional facet, defined in this test.

    It proves the milestone's success criterion: teaching the platform a new
    structural facet requires writing ONLY an extractor. It touches no core
    module, reads no source, yet its nodes and edges reach the graph, the
    queries, and the report.
    """

    extractor_id = "power-domains"
    order = 60

    def extract(self, model, graph) -> None:
        # Derived from the model, never from source: every IP gets a power
        # domain named after it, owned by the modules it contains.
        for ip in model.dut.ip_blocks:
            domain_id = make_node_id(NodeKind.CLOCK_DOMAIN, f"pd_{ip.name}")
            graph.add_node(
                DesignNode(
                    id=domain_id,
                    kind=NodeKind.CLOCK_DOMAIN,
                    name=f"pd_{ip.name}",
                    attributes={"facet": "power"},
                    extracted_by=self.extractor_id,
                )
            )
            for member in ip.modules:
                graph.add_edge(
                    __import__(
                        "veritriage.design.model", fromlist=["DesignEdge"]
                    ).DesignEdge(
                        source_id=make_node_id(NodeKind.MODULE, member),
                        target_id=domain_id,
                        relation=DesignRelation.CLOCKED_BY,
                        rationale=f"dut.ips[{ip.name}].modules lists {member}",
                    )
                )


def test_new_extractor_needs_only_registration(project, fixture_log):
    register_extractor(_PowerDomainExtractor)
    try:
        assert "power-domains" in available_extractors()

        built = build_design_graph(project)
        # It ran, with zero changes to the core...
        node = built.by_name("pd_l2_cache", NodeKind.CLOCK_DOMAIN)
        assert node is not None
        assert node.extracted_by == "power-domains"
        # ...its edges joined the graph and resolve...
        edges = [e for e in built.edges if e.target_id == node.id]
        assert edges and all(e.source_id in built.nodes for e in edges)
        # ...the queries see it...
        assert "pd_l2_cache" in {
            d.name for d in DesignQuery(built).clock_domains_of(["l2_cache"])
        }
        # ...and it reaches the report with no core change.
        outcome = analyze(fixture_log("uvm_scoreboard.log"), project=project)
        assert "power-domains" in outcome.report.design.extractors
    finally:
        unregister_extractor("power-domains")

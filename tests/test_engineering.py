"""Milestone 7: Engineering Context Engine.

Covers the milestone's guarantees, not just its features: providers isolate
every engineering tool, the context engine is tool-agnostic and deterministic,
engineering context enters the platform only as evidence (never conclusions),
ownership routes people without ever ranking failures, projections never
mutate the graph, and, above all, a brand-new engineering system needs only a
new provider (the crown-jewel architecture test at the bottom of this file).
"""

from __future__ import annotations

import inspect
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import veritriage.engineering.context as context_module
import veritriage.engineering.impact as impact_module
import veritriage.engineering.inference as inference_module
import veritriage.engineering.investigation as investigation_module
import veritriage.engineering.model as model_module
import veritriage.engineering.ownership as ownership_module
import veritriage.engineering.timeline as timeline_module
from veritriage.engineering import (
    ChangeCategory,
    ChangedFile,
    Commit,
    ContextCapability,
    ContextProvider,
    EngineeringContext,
    HistoricalRegression,
    collect_context,
    emit_engineering_evidence,
    impacted_tests_from_history,
    register_provider,
    stored_context,
    unregister_provider,
)
from veritriage.engineering.parser import EngineeringContextParser
from veritriage.engineering.providers.git import GitProvider, categorize_path
from veritriage.engineering.providers.manifest import load_manifest
from veritriage.graph.model import ArtifactType, RelationType
from veritriage.pipeline import analyze
from veritriage.reports import HtmlReportGenerator

# .../src/veritriage/engineering/model.py -> parents[2] is the src/ root.
SRC = Path(model_module.__file__).parents[2]

_TOOL_AGNOSTIC_MODULES = (
    model_module,
    context_module,
    inference_module,
    impact_module,
    ownership_module,
    timeline_module,
    investigation_module,
)


# --- helpers ---------------------------------------------------------------


def _commit(revision: str, *files: ChangedFile, source: str = "test") -> Commit:
    from veritriage.engineering.model import make_context_id

    return Commit(
        id=make_context_id(source, revision),
        revision=revision,
        timestamp=datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),
        author="tester",
        title=f"change {revision}",
        files=tuple(files),
        source=source,
    )


def _rtl_file(path: str, module: str) -> ChangedFile:
    return ChangedFile(path=path, category=ChangeCategory.RTL, modules=(module,))


def _make_git_repo(tmp_path: Path) -> Path:
    """A throwaway git repo with two commits touching RTL and testbench files."""
    repo = tmp_path / "repo"
    (repo / "rtl").mkdir(parents=True)
    (repo / "tb").mkdir()

    def _git(*args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True
        )

    _git("init", "-q")
    _git("config", "user.email", "t@example.com")
    _git("config", "user.name", "Test Author")
    (repo / "rtl" / "axi_monitor.sv").write_text("module axi_monitor; endmodule\n")
    _git("add", "-A")
    _git("commit", "-q", "-m", "add axi monitor rtl")
    (repo / "tb" / "scoreboard.sv").write_text("class scoreboard; endclass\n")
    _git("add", "-A")
    _git("commit", "-q", "-m", "add scoreboard checks")
    return repo


# --- Providers -------------------------------------------------------------


def test_manifest_provider_roundtrips(fixture_log):
    context = load_manifest(fixture_log("change_context.engctx.json"))
    assert context.sources == ("engineering_manifest",)
    # A manifest carries recorded context but cannot answer a live range query.
    assert context.capabilities == frozenset(ContextCapability) - {
        ContextCapability.CHANGE_RANGE
    }
    assert [c.revision for c in context.commits] == ["a1b2c3d4e5f", "9f8e7d6c5b4"]
    rtl = context.commits[0].files_in_category(ChangeCategory.RTL)
    assert {f.path for f in rtl} == {"rtl/axi_monitor.sv", "rtl/axi_arbiter.sv"}
    assert context.ci_run is not None and context.ci_run.environment_changes
    assert {o.owner for o in context.ownership} == {"asha", "diego"}
    assert context.issues[0].tracker_id == "PROJ-482"
    assert context.changed_modules() == ["axi_monitor", "axi_arbiter", "scoreboard"]


def test_git_provider_reads_a_real_repo(tmp_path):
    repo = _make_git_repo(tmp_path)
    assert GitProvider.available(repo)
    context = GitProvider().collect(repo, max_commits=5)
    assert context.capabilities == frozenset(
        {
            ContextCapability.COMMITS,
            ContextCapability.CHANGED_FILES,
            ContextCapability.CHANGE_RANGE,
        }
    )
    assert len(context.commits) == 2
    by_title = {c.title: c for c in context.commits}
    rtl_commit = by_title["add axi monitor rtl"]
    assert rtl_commit.author == "Test Author"
    assert rtl_commit.files[0].category == ChangeCategory.RTL
    assert rtl_commit.files[0].modules == ("axi_monitor",)
    tb_commit = by_title["add scoreboard checks"]
    assert tb_commit.files[0].category == ChangeCategory.TESTBENCH


def test_git_provider_degrades_outside_a_repo(tmp_path):
    lone = tmp_path / "no_repo"
    lone.mkdir()
    assert not GitProvider.available(lone)
    assert collect_context(lone).is_empty


def test_path_category_heuristics():
    assert categorize_path("rtl/axi_arbiter.sv") == ChangeCategory.RTL
    assert categorize_path("tb/axi_scoreboard.sv") == ChangeCategory.TESTBENCH
    assert categorize_path("verif/env/axi_env.sv") == ChangeCategory.TESTBENCH
    assert categorize_path("constraints/top.sdc") == ChangeCategory.CONSTRAINT
    assert categorize_path("checkers/axi_sva.sv") == ChangeCategory.ASSERTION
    assert categorize_path("sim/Makefile") == ChangeCategory.BUILD
    assert categorize_path("flist/design.f") == ChangeCategory.BUILD
    assert categorize_path("docs/spec.md") == ChangeCategory.DOCS
    assert categorize_path("scripts/run.py") == ChangeCategory.OTHER


def test_merge_deduplicates_commits():
    a = EngineeringContext(sources=("x",), commits=(_commit("r1"),))
    b = EngineeringContext(sources=("y",), commits=(_commit("r1"), _commit("r2")))
    merged = a.merge(b)
    assert [c.revision for c in merged.commits] == ["r1", "r2"]
    assert merged.sources == ("x", "y")


# --- Evidence emission and correlation -------------------------------------


def test_emit_engineering_evidence_is_deterministic_and_provenanced():
    context = EngineeringContext(
        sources=("test",),
        commits=(_commit("r1", _rtl_file("rtl/axi_monitor.sv", "axi_monitor")),),
    )
    first = emit_engineering_evidence(context)
    second = emit_engineering_evidence(context)
    assert [n.id for n in first.nodes] == [n.id for n in second.nodes]
    node = first.nodes[0]
    assert node.artifact_type == ArtifactType.ENGINEERING_CHANGE
    assert node.attributes["kind"] == "commit"
    assert node.attributes["source"] == "test"
    assert node.attributes["modules"] == ["axi_monitor"]


def test_ownership_and_issues_never_become_graph_nodes(fixture_log):
    context = load_manifest(fixture_log("change_context.engctx.json"))
    fragment = emit_engineering_evidence(context)
    kinds = {n.attributes.get("kind") for n in fragment.nodes}
    assert kinds == {"commit", "ci_run"}


def test_change_correlates_with_failure_in_same_scope(fixture_log):
    # uvm_assertion.log fails in /rtl/axi_monitor.sv; the manifest changes it.
    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    graph = outcome.graph
    commit_ids = {
        n.id
        for n in graph.nodes_of_type(ArtifactType.ENGINEERING_CHANGE)
        if n.attributes.get("kind") == "commit"
    }
    correlations = [
        e
        for e in graph.edges
        if e.relation == RelationType.CORRELATES_WITH and e.source_id in commit_ids
    ]
    assert correlations, "expected a change-to-failure correlation edge"
    assert "axi_monitor" in correlations[0].rationale


# --- Reasoning integration (evidence, never conclusions) --------------------


def test_engineering_signals_influence_ranking_with_trace(fixture_log):
    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    reasoning = outcome.report.reasoning
    signals = [s for s in reasoning.signals if s.name.startswith("engineering:")]
    assert {s.name for s in signals} >= {
        "engineering:recent-change-in-failing-scope",
        "engineering:environment-drift",
    }
    for signal in signals:
        assert signal.evidence_ids, "engineering signals must cite evidence"
        assert all(i in outcome.graph.nodes for i in signal.evidence_ids)
    top = reasoning.hypotheses[0]
    trace_sources = {c.source for c in top.confidence_trace.contributions}
    assert "engineering:recent-change-in-failing-scope" in trace_sources


def test_context_free_run_is_unchanged(fixture_log):
    outcome = analyze(fixture_log("uvm_assertion.log"))
    assert outcome.report.engineering is None
    assert not [
        s for s in outcome.report.reasoning.signals if s.name.startswith("engineering:")
    ]


# --- Ownership: routes people, never ranks ----------------------------------


def test_ownership_appends_one_routing_recommendation(fixture_log):
    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    recommendations = outcome.report.reasoning.recommendations
    routing = [r for r in recommendations if r.action.startswith("Loop in")]
    assert len(routing) == 1
    assert "asha" in routing[0].action
    # Appended last: nothing reasoning produced was displaced.
    assert recommendations[-1] is routing[0]
    assert routing[0].evidence_ids


def test_ownership_never_reaches_ranking(fixture_log):
    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    assert not [
        s for s in outcome.report.reasoning.signals if "ownership" in s.name.lower()
    ]
    for package in ("reasoning", "rules"):
        for path in (SRC / "veritriage" / package).glob("*.py"):
            assert "ownership" not in path.read_text(encoding="utf-8"), path.name


# --- Impact analysis --------------------------------------------------------


def test_in_run_impact_names_the_current_test(fixture_log):
    outcome = analyze(
        [
            fixture_log("uvm_assertion.log"),
            fixture_log("test_metadata.json"),
            fixture_log("change_context.engctx.json"),
        ]
    )
    impacted = outcome.report.engineering.impacted_tests
    assert impacted, "expected the current run's test to be flagged as impacted"
    assert "axi_monitor" in impacted[0].changed_modules


def test_historical_impact_is_deterministic_and_cited(fixture_log):
    context = load_manifest(fixture_log("change_context.engctx.json"))
    history = [
        HistoricalRegression(
            regression_id="reg-1",
            test_name="axi_burst_test",
            failing_modules=("uvm_test_top.env.mon", "/rtl/axi_monitor.sv"),
        ),
        HistoricalRegression(
            regression_id="reg-2",
            test_name="axi_burst_test",
            failing_modules=("/rtl/axi_monitor.sv",),
        ),
        HistoricalRegression(
            regression_id="reg-3",
            test_name="pcie_link_test",
            failing_modules=("/rtl/pcie_phy.sv",),
        ),
    ]
    first = impacted_tests_from_history(context, history)
    second = impacted_tests_from_history(context, history)
    assert first == second
    assert [t.test_name for t in first] == ["axi_burst_test"]
    assert first[0].regression_ids == ["reg-1", "reg-2"]
    assert first[0].score == 0.5


# --- Projections ------------------------------------------------------------


def test_projections_do_not_mutate_the_graph(fixture_log):
    from veritriage.engineering import build_investigation, build_timeline

    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    before = outcome.graph.model_dump_json()
    build_timeline(outcome.graph, outcome.report)
    build_investigation(outcome.graph, outcome.report)
    assert outcome.graph.model_dump_json() == before


def test_investigation_is_a_projection_of_graph_nodes(fixture_log):
    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    view = outcome.report.engineering.investigation
    assert view is not None
    for layer in view.layers:
        for node_id in layer.node_ids:
            assert node_id in outcome.graph.nodes
    assert any(layer.name == "engineering" and layer.node_ids for layer in view.layers)
    # The change-to-failure edge shows up as a cross-layer relationship.
    assert any(e.relation == "correlates_with" for e in view.cross_edges)


def test_timeline_orders_change_before_simulation(fixture_log):
    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    phases = [e.phase for e in outcome.report.engineering.timeline]
    assert phases.index("change") < phases.index("simulation")


# --- Report -----------------------------------------------------------------


def test_report_renders_engineering_section(fixture_log):
    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("change_context.engctx.json")]
    )
    html = HtmlReportGenerator().render(outcome.report, graph=outcome.graph)
    assert "Engineering Context" in html
    assert "rework AR channel arbitration priority" in html
    assert "Environment drift" in html
    # Escapes, not literals, so this source file itself stays dash-free.
    assert "\u2014" not in html and "\u2013" not in html


# --- Architecture guards ----------------------------------------------------


def test_engineering_core_is_tool_agnostic():
    # The context engine, models, inference, impact, ownership, and the
    # projections must not import a provider, run a subprocess, or read files:
    # they consume normalized context and evidence only. (Checked against
    # imports and calls, not documentation prose, which may legitimately
    # mention the words.)
    for module in _TOOL_AGNOSTIC_MODULES:
        source = inspect.getsource(module)
        assert "from veritriage.engineering.providers" not in source, (
            f"{module.__name__} imports a provider"
        )
        assert "import subprocess" not in source, f"{module.__name__} runs a subprocess"
        assert ".read_text" not in source and "open(" not in source


def test_no_git_outside_providers():
    # The "no git outside providers" law, enforceable repo-wide since the M4
    # capture_execution_metadata migration: subprocess use and git invocation
    # live only under engineering/providers/. Invocation is matched as a
    # subprocess argv (["git"), not as prose, so docstrings may say "git".
    allowed = (SRC / "veritriage" / "engineering" / "providers").resolve()
    for path in (SRC / "veritriage").rglob("*.py"):
        if allowed in path.resolve().parents:
            continue
        text = path.read_text(encoding="utf-8")
        assert "import subprocess" not in text, f"{path} uses subprocess outside providers"
        assert '["git"' not in text and "['git'" not in text, (
            f"{path} invokes git outside providers"
        )


def test_reasoning_has_no_engineering_dependency():
    for package in ("reasoning", "rules"):
        for path in (SRC / "veritriage" / package).glob("*.py"):
            assert "veritriage.engineering" not in path.read_text(encoding="utf-8"), path.name


def test_engineering_never_depends_on_ai():
    banned = ("anthropic", "reasoning.ai", "AIReasoner", "import openai")
    for path in (SRC / "veritriage" / "engineering").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_manifest_parser_registers_like_any_parser(fixture_log):
    parser = EngineeringContextParser()
    result = parser.parse(fixture_log("change_context.engctx.json"))
    assert stored_context(result) is not None
    fragment = parser.emit_evidence(result)
    assert fragment.nodes


# --- The crown jewel: a new system is a new provider and nothing else --------


class _FakePerforceProvider(ContextProvider):
    """A throwaway provider for a fictional system, defined entirely in this
    test.

    It exists to prove the milestone's success criterion: supporting a
    brand-new engineering system requires writing ONLY a provider. This class
    touches no core module, yet its output flows all the way to evidence,
    correlation, reasoning, and the report.
    """

    name = "fake_perforce"
    source = "perforce"
    capabilities = frozenset({ContextCapability.COMMITS, ContextCapability.CHANGED_FILES})

    @classmethod
    def available(cls, root: Path) -> bool:
        return (root / "p4.marker").is_file()

    def collect(self, root: Path, max_commits: int = 10) -> EngineeringContext:
        return EngineeringContext(
            sources=(self.name,),
            capabilities=self.capabilities,
            commits=(
                _commit(
                    "CL501234",
                    _rtl_file("rtl/axi_monitor.sv", "axi_monitor"),
                    source=self.source,
                ),
            ),
        )


def test_new_system_needs_only_a_provider(fixture_log, tmp_path):
    register_provider(_FakePerforceProvider)
    try:
        (tmp_path / "p4.marker").write_text("")
        gathered = collect_context(tmp_path)
        assert gathered.sources == ("fake_perforce",)

        outcome = analyze(fixture_log("uvm_assertion.log"), engineering=gathered)

        # The change reached evidence...
        commits = [
            n
            for n in outcome.graph.nodes_of_type(ArtifactType.ENGINEERING_CHANGE)
            if n.attributes.get("kind") == "commit"
        ]
        assert commits and commits[0].attributes["source"] == "perforce"
        # ...correlated with the failure...
        assert any(
            e.relation == RelationType.CORRELATES_WITH and e.source_id == commits[0].id
            for e in outcome.graph.edges
        )
        # ...influenced reasoning...
        assert any(
            s.name == "engineering:recent-change-in-failing-scope"
            for s in outcome.report.reasoning.signals
        )
        # ...and reached the report.
        assert outcome.report.engineering is not None
        assert outcome.report.engineering.commits[0].revision == "CL501234"
    finally:
        unregister_provider("fake_perforce")

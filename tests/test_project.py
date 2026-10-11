"""Milestone 11: Verification Project Intelligence (manifest-first increment).

Covers the milestone's guarantees, not just its features: a project is understood
before any failure is analyzed; the Project Model is deterministic and content
addressed; it never enters the Evidence Graph (it is a lens over it); it reaches
reasoning only through the standard rule interface; protocol identification reuses
the Knowledge Engine; and, above all, a brand-new project source needs only a new
provider (the crown-jewel architecture test at the bottom of this file).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from laws import imports

import veritriage.project.inference as inference_module
import veritriage.project.insights as insights_module
import veritriage.project.lifecycle as lifecycle_module
import veritriage.project.model as model_module
from veritriage.graph.model import ArtifactType
from veritriage.pipeline import analyze
from veritriage.project import (
    ProjectCapability,
    ProjectModel,
    build_project_model,
    explain_log,
    project_lifecycle,
)
from veritriage.project.insights import apply_insights
from veritriage.project.model import (
    Dut,
    Interface,
    LogProfile,
    LogSource,
    SimulationLifecycle,
    LifecyclePhase,
    compute_fingerprint,
    seal_project,
)
from veritriage.project.providers import (
    ProjectProvider,
    available_project_providers,
    register_project_provider,
    unregister_project_provider,
)
from veritriage.workspace import WorkspaceServices

# .../src/veritriage/project/model.py -> parents[2] is the src/ root.
SRC = Path(model_module.__file__).parents[2]


@pytest.fixture()
def project_root(fixture_log):
    return fixture_log("project/sample.vproj.json").parent


# --- Model building ---------------------------------------------------------


def test_manifest_builds_structured_model(project_root):
    model = build_project_model(project_root)
    assert model.dut.top == "soc_top"
    assert len(model.dut.modules) == 3
    interface = next(i for i in model.dut.interfaces if i.name == "cpu_l2")
    assert interface.protocol_id == "axi"
    assert model.sim_infra.simulator_vendor == "vcs"
    types = {c.type for c in model.env.components}
    assert {"monitor", "scoreboard", "predictor", "agent"} <= types
    assert [p.name for p in model.lifecycle.phases][:3] == ["compile", "build", "connect"]


def test_project_id_and_fingerprint_are_deterministic(project_root):
    a = build_project_model(project_root)
    b = build_project_model(project_root)
    assert a.project_id == b.project_id and a.project_id.startswith("pm-")
    assert a.fingerprint == b.fingerprint and a.fingerprint.startswith("sha256:")


def test_merge_unions_partial_models():
    left = ProjectModel(dut=Dut(interfaces=(Interface(name="a"),)))
    right = ProjectModel(dut=Dut(interfaces=(Interface(name="b"),)))
    names = {i.name for i in left.merge(right).dut.interfaces}
    assert names == {"a", "b"}
    # The same union regardless of direction (set of contents is stable).
    assert names == {i.name for i in right.merge(left).dut.interfaces}


def test_empty_root_yields_sealed_empty_model(tmp_path):
    model = build_project_model(tmp_path)
    assert model.is_empty and model.project_id.startswith("pm-")


# --- Protocol identification (reuses the Knowledge Engine) -------------------


def test_protocol_identification_uses_knowledge_markers():
    # No declared protocol, but AXI signal names: the AXI pack markers identify it.
    model = ProjectModel(
        dut=Dut(interfaces=(Interface(name="bus", signals=("arvalid", "rvalid", "awvalid")),))
    )
    enriched = apply_insights(model)
    assert enriched.dut.interfaces[0].protocol_id == "axi"


def test_declared_protocol_is_preserved():
    model = ProjectModel(dut=Dut(interfaces=(Interface(name="bus", protocol_id="apb"),)))
    assert apply_insights(model).dut.interfaces[0].protocol_id == "apb"


# --- Log intelligence -------------------------------------------------------


def test_explain_log_classifies_origin_and_phase(project_root, fixture_log):
    model = build_project_model(project_root)
    annotations = explain_log(fixture_log("uvm_assertion.log"), model)
    assert annotations
    assert all(a.origin == "testbench" for a in annotations)  # per the project's log profile
    assert any(a.phase for a in annotations)


# --- Lifecycle projection ---------------------------------------------------


def test_lifecycle_projection_finds_where_progress_stopped(project_root, fixture_log):
    model = build_project_model(project_root)
    outcome = analyze(fixture_log("vcs_compile_error.log"), project=model)
    projection = project_lifecycle(model, outcome.graph)
    assert projection is not None
    assert projection.last_reached == "compile"
    assert projection.stopped_at == "build"


# --- Pipeline integration ---------------------------------------------------


def test_pipeline_attaches_project_context_and_bumps_schema(project_root, fixture_log):
    model = build_project_model(project_root)
    outcome = analyze(fixture_log("uvm_assertion.log"), project=model)
    assert outcome.report.schema_version == "13"
    assert outcome.report.project is not None
    assert [p.protocol_id for p in outcome.report.project.identified_protocols] == ["axi"]


def test_project_influences_ranking_with_trace(project_root, fixture_log):
    model = build_project_model(project_root)
    outcome = analyze(fixture_log("vcs_compile_error.log"), project=model)
    signals = [s for s in outcome.report.reasoning.signals if s.name.startswith("project:")]
    assert any(s.name == "project:lifecycle" for s in signals)
    for signal in signals:
        assert all(i in outcome.graph.nodes for i in signal.evidence_ids)  # cite real evidence
    trace_sources = {
        c.source for h in outcome.report.reasoning.hypotheses for c in h.confidence_trace.contributions
    }
    assert any(s.startswith("project:") for s in trace_sources)


def test_log_origin_rule_shifts_blame_off_the_design(project_root, fixture_log):
    # The sample project classifies uvm_test_top.env messages as testbench origin,
    # so the log-origin rule should raise a non-RTL hypothesis.
    model = build_project_model(project_root)
    outcome = analyze(fixture_log("uvm_scoreboard.log"), project=model)
    assert any(
        s.name == "project:log-origin" for s in outcome.report.reasoning.signals
    )


def test_non_project_run_has_no_project_context(fixture_log):
    outcome = analyze(fixture_log("uvm_assertion.log"))
    assert outcome.report.project is None


# --- Services ---------------------------------------------------------------


def test_services_build_load_and_summarize(tmp_path, project_root):
    services = WorkspaceServices(project_root=tmp_path / "project")
    model = services.build_project_model(project_root)
    loaded = services.load_project_model(project_root)
    assert loaded is not None and loaded.project_id == model.project_id
    summary = services.project_summary(model)
    assert summary.dut_top == "soc_top"
    assert summary.identified_protocols == ["axi"]
    assert summary.uvm_component_count == 5


# --- Architecture guards ----------------------------------------------------


def test_project_never_enters_the_evidence_graph(project_root, fixture_log):
    # No project ArtifactType, and the graph is identical with and without a model.
    assert not any("project" in t.value for t in ArtifactType)
    model = build_project_model(project_root)
    bare = analyze(fixture_log("uvm_assertion.log"))
    lensed = analyze(fixture_log("uvm_assertion.log"), project=model)
    assert set(bare.graph.nodes) == set(lensed.graph.nodes)
    assert len(bare.graph.edges) == len(lensed.graph.edges)


def test_project_core_is_source_agnostic():
    # The model, insight, inference, and lifecycle layers never read source: they
    # consume normalized data only. (Checked against I/O calls, not prose.)
    for module in (model_module, insights_module, inference_module, lifecycle_module):
        source = inspect.getsource(module)
        assert ".read_text" not in source, module.__name__
        assert "open(" not in source, module.__name__
        assert "Path(" not in source, module.__name__


def test_reasoning_has_no_project_dependency():
    for package in ("reasoning", "rules"):
        for path in (SRC / "veritriage" / package).glob("*.py"):
            assert "veritriage.project" not in path.read_text(encoding="utf-8"), path.name


def test_core_unchanged_by_project():
    # Nothing in the intelligence core below the pipeline imports the project layer.
    for package in ("graph", "parsers", "rules", "reasoning", "knowledge", "waveform", "history"):
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            assert "veritriage.project" not in imports(path), path
    # And the knowledge engine (which project consumes) never imports project back.
    for path in (SRC / "veritriage" / "knowledge").rglob("*.py"):
        assert "veritriage.project" not in path.read_text(encoding="utf-8"), path


def test_project_never_depends_on_ai():
    banned = ("anthropic", "reasoning.ai", "AIReasoner", "import openai")
    for path in (SRC / "veritriage" / "project").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_lifecycle_projection_does_not_mutate_the_graph(project_root, fixture_log):
    model = build_project_model(project_root)
    outcome = analyze(fixture_log("uvm_assertion.log"))
    before_nodes, before_edges = set(outcome.graph.nodes), len(outcome.graph.edges)
    project_lifecycle(model, outcome.graph)
    assert set(outcome.graph.nodes) == before_nodes
    assert len(outcome.graph.edges) == before_edges


# --- The crown jewel: a new project source is a new provider and nothing else


class _FakeSpecProvider(ProjectProvider):
    """A throwaway provider for a fictional source, defined entirely in this test.

    It proves the milestone's success criterion: supporting a brand-new project
    source requires writing ONLY a provider. It touches no core module, yet its
    output flows to the Project Model, a reasoning signal, and the report.
    """

    name = "fake_spec"
    source = "fake_spec"
    capabilities = frozenset({ProjectCapability.HIERARCHY, ProjectCapability.LOG_PROFILE})

    @classmethod
    def available(cls, root: Path) -> bool:
        return root.is_dir() and any(root.glob("*.fakespec"))

    def collect(self, root: Path) -> ProjectModel:
        # Declares that every failing message is infrastructure origin, so the
        # standard log-origin reasoning rule fires with zero core change.
        return ProjectModel(
            source_root=str(root),
            dut=Dut(top="fake_dut"),
            lifecycle=SimulationLifecycle(
                phases=(LifecyclePhase(name="boot", markers=("UVM",)),)
            ),
            log_profile=LogProfile(rules=(LogSource(pattern=".", origin="infrastructure"),)),
        )


def test_new_project_source_needs_only_a_provider(tmp_path, fixture_log):
    register_project_provider(_FakeSpecProvider)
    try:
        assert "fake_spec" in available_project_providers()
        (tmp_path / "design.fakespec").write_text("opaque fake-spec bytes")

        model = build_project_model(tmp_path)
        # The provider's output reached the sealed model...
        assert model.dut.top == "fake_dut"
        assert model.project_id.startswith("pm-")

        # ...and reasoning: its log profile makes the failing evidence infra origin,
        # so the standard project log-origin rule fires, with no core change.
        outcome = analyze(fixture_log("uvm_scoreboard.log"), project=model)
        assert any(
            s.name == "project:log-origin" for s in outcome.report.reasoning.signals
        )
        # ...and the report carries the project context.
        assert outcome.report.project is not None
        assert outcome.report.project.dut_top == "fake_dut"
    finally:
        unregister_project_provider("fake_spec")


def test_fingerprint_detects_structural_change():
    base = seal_project(ProjectModel(dut=Dut(top="a")))
    changed = seal_project(ProjectModel(dut=Dut(top="b")))
    assert base.fingerprint != changed.fingerprint
    # Recomputing over the same content is stable.
    assert compute_fingerprint(base) == compute_fingerprint(
        ProjectModel(dut=Dut(top="a"))
    )

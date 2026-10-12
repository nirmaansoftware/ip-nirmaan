"""Milestone 6: Waveform Intelligence Engine.

Covers the milestone's guarantees, not just its features: adapters isolate every
format, the observation engine is format-agnostic and deterministic, capability
degradation is honest, observations carry provenance and confidence into the
Evidence Graph and reasoning, and, above all, a brand-new simulator needs only a
new adapter (the crown-jewel architecture test at the bottom of this file).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import veritriage.waveform.engine as engine_module
import veritriage.waveform.model as model_module
import veritriage.waveform.observations as observations_module
from veritriage.graph.model import ArtifactType, RelationType
from veritriage.models import Severity
from veritriage.pipeline import analyze
from veritriage.reports import HtmlReportGenerator
from veritriage.waveform import (
    ObservationKind,
    SignalRole,
    WaveformCapability,
    WaveformEngine,
    WaveformMetadata,
    WaveformParser,
    find_adapter,
    register_adapter,
    unregister_adapter,
)
from veritriage.waveform.adapters import WaveformAdapter, WaveformAdapterError, available_adapters
from veritriage.waveform.model import (
    HandshakeRef,
    ObservationCategory,
    TransactionRef,
    WaveformSignal,
)
from veritriage.waveform.observations import KIND_CATEGORY, default_detectors

# .../src/veritriage/waveform/model.py -> parents[2] is the src/ root.
SRC = Path(model_module.__file__).parents[2]


# --- helpers ---------------------------------------------------------------


def _sig(name, role, toggle_count, first=None, last=None, scope="tb.dut", width=1):
    return WaveformSignal(
        name=name,
        scope=scope,
        role=role,
        width=width,
        toggle_count=toggle_count,
        first_edge=first,
        last_edge=last,
    )


def _metadata(signals, *, handshakes=None, transactions=None, capabilities=None,
              dump_start=0, dump_end=1000, adapter="test"):
    return WaveformMetadata(
        source_path="synthetic",
        format="test",
        adapter=adapter,
        dump_start=dump_start,
        dump_end=dump_end,
        signals=signals,
        handshakes=handshakes or [],
        transactions=transactions or [],
        capabilities=frozenset(WaveformCapability) if capabilities is None else frozenset(capabilities),
    )


def _kinds(observations):
    return {o.kind for o in observations}


# --- Adapters --------------------------------------------------------------


def test_manifest_adapter_roundtrips(fixture_log):
    adapter = find_adapter(fixture_log("axi_handshake_stall.wave.json"))
    assert adapter is not None and adapter.name == "waveform_manifest"
    md = adapter.extract(fixture_log("axi_handshake_stall.wave.json"))
    assert md.format == "manifest" and md.adapter == "waveform_manifest"
    assert md.simulator == "vcs" and md.dump_end == 20000
    assert md.capabilities == frozenset(WaveformCapability)  # canonical: resolves all
    arready = md.signal("arready")
    assert arready is not None and arready.role == SignalRole.READY and arready.is_constant
    assert md.handshakes[0].initiator == "arvalid"
    assert md.transactions[0].end is None


def test_vcd_adapter_extracts_activity_and_infers_roles(fixture_log):
    adapter = find_adapter(fixture_log("axi_handshake_stall.vcd"))
    assert adapter is not None and adapter.name == "vcd"
    md = adapter.extract(fixture_log("axi_handshake_stall.vcd"))
    roles = {s.name: s.role for s in md.signals}
    # "arstate" contains the substring "rst": it must still be STATE, not RESET.
    assert roles["arstate"] == SignalRole.STATE
    assert roles["rst_n"] == SignalRole.RESET
    assert roles["clk"] == SignalRole.CLOCK
    counts = {s.name: s.toggle_count for s in md.signals}
    assert counts["arready"] == 0  # never toggled (only its initial value)
    assert counts["clk"] >= 4 and counts["arvalid"] == 2
    assert md.dump_start == 0 and md.dump_end == 50
    # Hierarchy is preserved; nested scope carries the parent path.
    assert md.signal("arstate").scope == "tb.axi"


def test_vcd_adapter_declares_limited_capabilities(fixture_log):
    md = find_adapter(fixture_log("axi_handshake_stall.vcd")).extract(
        fixture_log("axi_handshake_stall.vcd")
    )
    assert WaveformCapability.ACTIVITY in md.capabilities
    # Raw VCD has neither a transaction DB nor declared handshakes.
    assert WaveformCapability.TRANSACTIONS not in md.capabilities
    assert WaveformCapability.PROTOCOL_ANNOTATIONS not in md.capabilities


def test_vcd_adapter_rejects_non_vcd(tmp_path):
    bogus = tmp_path / "not.vcd"
    bogus.write_text("this is not a vcd header\n")
    from veritriage.waveform.adapters.vcd import VcdAdapter

    with pytest.raises(WaveformAdapterError):
        VcdAdapter().extract(bogus)


def test_registry_dispatch_and_decline(tmp_path):
    assert find_adapter(Path("x.vcd")).name == "vcd"
    assert find_adapter(Path("x.wave.json")).name == "waveform_manifest"
    # A plain log is not a waveform artifact: the registry declines it.
    assert find_adapter(Path("sim.log")) is None


# --- Detectors (format-agnostic, over synthetic metadata) ------------------


def test_signal_never_toggled_detector():
    md = _metadata([_sig("arready", SignalRole.READY, 0)])
    obs = WaveformEngine().observe(md).observations
    assert _kinds(obs) == {ObservationKind.SIGNAL_NEVER_TOGGLED}
    assert obs[0].severity == Severity.WARNING


def test_clock_stopped_detector_dead_and_gated():
    dead = WaveformEngine().observe(_metadata([_sig("clk", SignalRole.CLOCK, 0)])).observations
    assert dead[0].kind == ObservationKind.CLOCK_STOPPED and dead[0].severity == Severity.FATAL
    gated = WaveformEngine().observe(
        _metadata([_sig("clk", SignalRole.CLOCK, 100, first=0, last=100)], dump_end=1000)
    ).observations
    assert gated[0].kind == ObservationKind.CLOCK_STOPPED and gated[0].severity == Severity.ERROR


def test_fsm_stalled_detector():
    stalled = WaveformEngine().observe(
        _metadata([_sig("fsm_state", SignalRole.STATE, 3, first=0, last=100)], dump_end=1000)
    ).observations
    assert stalled[0].kind == ObservationKind.FSM_STALLED


def test_handshake_detector_completed_incomplete_and_never_started():
    initiator = _sig("v", SignalRole.VALID, 4, first=10)
    responder_dead = _sig("r", SignalRole.READY, 0)
    md_stall = _metadata(
        [initiator, responder_dead],
        handshakes=[HandshakeRef(name="AR", initiator="v", responder="r")],
    )
    stall = WaveformEngine().observe(md_stall).observations
    assert ObservationKind.HANDSHAKE_INCOMPLETE in _kinds(stall)

    md_ok = _metadata(
        [_sig("v", SignalRole.VALID, 4), _sig("r", SignalRole.READY, 4)],
        handshakes=[HandshakeRef(name="AR", initiator="v", responder="r")],
    )
    ok = WaveformEngine().observe(md_ok).observations
    assert ObservationKind.HANDSHAKE_COMPLETED in _kinds(ok)

    md_none = _metadata(
        [_sig("v", SignalRole.VALID, 0), _sig("r", SignalRole.READY, 0)],
        handshakes=[HandshakeRef(name="AR", initiator="v", responder="r")],
    )
    none = WaveformEngine().observe(md_none).observations
    assert ObservationKind.PROTOCOL_SEQUENCE_INCOMPLETE in _kinds(none)


def test_transaction_and_retry_detectors():
    md = _metadata(
        [_sig("clk", SignalRole.CLOCK, 100, first=0, last=1000)],
        transactions=[
            TransactionRef(id="rd0", kind="read", start=10, end=None),
            TransactionRef(id="wr9", kind="write", start=20, end=90, retry_count=5),
        ],
    )
    kinds = _kinds(WaveformEngine().observe(md).observations)
    assert ObservationKind.TRANSACTION_NOT_RETIRED in kinds
    assert ObservationKind.REPEATED_RETRIES in kinds


def test_unexpected_reset_detector():
    md = _metadata([_sig("rst_n", SignalRole.RESET, 3, first=10, last=800)], dump_end=1000)
    obs = WaveformEngine().observe(md).observations
    assert ObservationKind.UNEXPECTED_RESET in _kinds(obs)


def test_healthy_waveform_yields_no_observations():
    md = _metadata(
        [
            _sig("clk", SignalRole.CLOCK, 100, first=0, last=1000),
            _sig("rst_n", SignalRole.RESET, 1, first=5, last=5),
            _sig("v", SignalRole.VALID, 8),
            _sig("r", SignalRole.READY, 8),
        ],
        handshakes=[HandshakeRef(name="AR", initiator="v", responder="r")],
        transactions=[TransactionRef(id="t0", kind="read", start=10, end=90)],
        dump_end=1000,
    )
    observations = WaveformEngine().observe(md).observations
    # Only the positive "handshake completed" progress note; nothing wrong.
    assert _kinds(observations) <= {ObservationKind.HANDSHAKE_COMPLETED}


# --- Engine, capabilities, provenance, determinism -------------------------


def test_engine_gates_detectors_on_capability():
    md = _metadata(
        [_sig("clk", SignalRole.CLOCK, 100, first=0, last=1000)],
        transactions=[TransactionRef(id="rd0", kind="read", start=10, end=None)],
        capabilities={WaveformCapability.ACTIVITY, WaveformCapability.CLOCK_DETECTION},
        dump_end=1000,
    )
    result = WaveformEngine().observe(md)
    # The transaction detector could not run and is reported, not silently passed.
    unavailable = {u.required_capability for u in result.unavailable}
    assert WaveformCapability.TRANSACTIONS in unavailable
    assert ObservationKind.TRANSACTION_NOT_RETIRED not in _kinds(result.observations)


def test_every_observation_kind_has_a_detector():
    emitted: set[ObservationKind] = set()
    for detector in default_detectors():
        emitted |= set(detector.emits)
    assert emitted == set(ObservationKind)


def test_kind_category_map_is_complete_and_typed():
    assert set(KIND_CATEGORY) == set(ObservationKind)
    assert all(isinstance(v, ObservationCategory) for v in KIND_CATEGORY.values())


def test_observations_carry_provenance():
    md = _metadata([_sig("arready", SignalRole.READY, 0)], adapter="myadapter")
    obs = WaveformEngine().observe(md).observations[0]
    assert obs.detector == "signal-never-toggled"
    assert obs.source_adapter == "myadapter"
    assert obs.input_signals == ["tb.dut.arready"]
    assert obs.observation_id.startswith("wobs-")
    assert obs.category == ObservationCategory.ACTIVITY


def test_observation_ids_are_deterministic():
    md = _metadata([_sig("arready", SignalRole.READY, 0)])
    first = [o.observation_id for o in WaveformEngine().observe(md).observations]
    second = [o.observation_id for o in WaveformEngine().observe(md).observations]
    assert first == second and first


# --- Parser and pipeline integration ---------------------------------------


def test_waveform_parser_emits_provenanced_evidence(fixture_log):
    parser = WaveformParser()
    result = parser.parse(fixture_log("axi_handshake_stall.wave.json"))
    fragment = parser.emit_evidence(result)
    assert fragment.nodes
    node = fragment.nodes[0]
    assert node.artifact_type == ArtifactType.WAVEFORM_METADATA
    assert node.attributes["observation_id"].startswith("wobs-")
    assert node.attributes["detector"]
    assert node.attributes["waveform_kind"]
    assert node.attributes["source_adapter"] == "waveform_manifest"


def test_pipeline_analyzes_a_waveform_artifact(fixture_log):
    outcome = analyze(fixture_log("axi_handshake_stall.wave.json"))
    report = outcome.report
    assert report.schema_version == "14"
    assert report.waveform is not None
    kinds = {o.kind for o in report.waveform.observations}
    assert "handshake_incomplete" in kinds
    assert "transaction_not_retired" in kinds
    # Confidence propagates from observation to evidence node (refinement 9).
    wave_nodes = outcome.graph.nodes_of_type(ArtifactType.WAVEFORM_METADATA)
    txn = next(n for n in wave_nodes if n.attributes.get("waveform_kind") == "transaction_not_retired")
    assert txn.confidence == pytest.approx(0.95)


def test_non_waveform_run_has_no_waveform_context(fixture_log):
    outcome = analyze(fixture_log("uvm_assertion.log"))
    assert outcome.report.waveform is None


# --- Correlation and reasoning integration ---------------------------------


def test_waveform_observation_correlates_with_failure(fixture_log):
    # uvm_assertion.log fails in /rtl/axi_monitor.sv; the manifest observes the
    # 'axi' scope, so the correlator links the two.
    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("axi_handshake_stall.wave.json")]
    )
    graph = outcome.graph
    wave_ids = {n.id for n in graph.nodes_of_type(ArtifactType.WAVEFORM_METADATA)}
    correlations = [
        e
        for e in graph.edges
        if e.relation == RelationType.CORRELATES_WITH and e.source_id in wave_ids
    ]
    assert correlations, "expected waveform observations to correlate to the failure"


def test_waveform_influences_ranking_with_trace(fixture_log):
    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("axi_handshake_stall.wave.json")]
    )
    reasoning = outcome.report.reasoning
    waveform_signals = [s for s in reasoning.signals if s.name.startswith("waveform:")]
    assert waveform_signals, "expected waveform-derived reasoning signals"
    for signal in waveform_signals:
        assert signal.evidence_ids
        assert all(i in outcome.graph.nodes for i in signal.evidence_ids)
    top = reasoning.hypotheses[0]
    trace_sources = {c.source for c in top.confidence_trace.contributions}
    assert any(s.startswith("waveform:") for s in trace_sources)


# --- Report ----------------------------------------------------------------


def test_report_renders_waveform_section(fixture_log):
    outcome = analyze(
        [fixture_log("uvm_assertion.log"), fixture_log("axi_handshake_stall.wave.json")]
    )
    html = HtmlReportGenerator().render(outcome.report, graph=outcome.graph)
    assert "Waveform Intelligence" in html
    assert "handshake incomplete" in html
    # Standing constraint: no em or en dashes anywhere in generated content.
    # (Escapes, not literals, so this source file itself stays dash-free.)
    assert "\u2014" not in html and "\u2013" not in html


def test_capability_gap_is_surfaced_in_report(fixture_log):
    outcome = analyze(fixture_log("axi_handshake_stall.vcd"))
    assert outcome.report.waveform is not None
    unavailable = {u.required_capability for u in outcome.report.waveform.unavailable}
    assert "transactions" in unavailable
    assert "protocol_annotations" in unavailable


# --- Architecture guards ---------------------------------------------------


def test_waveform_core_is_format_agnostic():
    # The engine, detectors, and model must not import any adapter and must
    # never read a file: they consume normalized metadata only, so they stay
    # oblivious to every simulator format. (Checked against imports and I/O
    # calls, not documentation prose, which may legitimately mention adapters.)
    for module in (model_module, engine_module, observations_module):
        source = inspect.getsource(module)
        assert "waveform.adapters" not in source, f"{module.__name__} imports an adapter"
        assert "import" in source  # sanity: we are reading real module source
        assert ".read_text" not in source and "open(" not in source
        assert "Path(" not in source


def test_reasoning_has_no_waveform_dependency():
    for package in ("reasoning", "rules"):
        for path in (SRC / "veritriage" / package).glob("*.py"):
            assert "veritriage.waveform" not in path.read_text(encoding="utf-8"), path.name


def test_waveform_never_depends_on_ai():
    banned = ("anthropic", "reasoning.ai", "AIReasoner", "import openai")
    for path in (SRC / "veritriage" / "waveform").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


# --- The crown jewel: a new simulator is a new adapter and nothing else -----


class _FakeFstAdapter(WaveformAdapter):
    """A throwaway adapter for a fictional format, defined entirely in this test.

    It exists to prove the milestone's success criterion: supporting a brand-new
    simulator requires writing ONLY an adapter. This class touches no core module
    (no graph, reasoning, knowledge, report, or AI code), yet its output flows
    all the way to evidence, reasoning, and the report.
    """

    name = "fake_fst"
    format = "fake_fst"
    file_patterns = ("*.fakewave",)
    capabilities = frozenset({WaveformCapability.ACTIVITY, WaveformCapability.CLOCK_DETECTION})

    def extract(self, path: Path) -> WaveformMetadata:
        return WaveformMetadata(
            source_path=str(path),
            format=self.format,
            adapter=self.name,
            dump_start=0,
            dump_end=5000,
            signals=[WaveformSignal(name="clk", scope="tb", role=SignalRole.CLOCK, toggle_count=0)],
            capabilities=self.capabilities,
        )


def test_new_simulator_needs_only_an_adapter(tmp_path):
    register_adapter(_FakeFstAdapter)
    try:
        assert "fake_fst" in available_adapters()
        artifact = tmp_path / "sim.fakewave"
        artifact.write_text("opaque fake-fst bytes")  # content the adapter ignores

        outcome = analyze(artifact)

        # The observation reached evidence...
        wave_nodes = outcome.graph.nodes_of_type(ArtifactType.WAVEFORM_METADATA)
        assert wave_nodes and wave_nodes[0].attributes["waveform_kind"] == "clock_stopped"
        assert wave_nodes[0].attributes["source_adapter"] == "fake_fst"
        # ...the report...
        assert outcome.report.waveform is not None
        assert outcome.report.waveform.observations[0].kind == "clock_stopped"
        # ...and reasoning (a dead clock is FATAL, so it drives a hypothesis).
        assert any(
            s.name == "waveform:clock_stopped" for s in outcome.report.reasoning.signals
        )
    finally:
        unregister_adapter("fake_fst")

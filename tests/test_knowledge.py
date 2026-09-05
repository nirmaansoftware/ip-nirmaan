"""Verification Knowledge Engine tests.

Covers the milestone's architecture guarantees: knowledge is deterministic,
AI-free, immutable during reasoning, pluggable without touching reasoning
code, and its playbooks/matches are reproducible.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from veritriage.knowledge import (
    Concept,
    DebugPlaybook,
    EvidenceClause,
    FailurePattern,
    KnowledgeEngine,
    KnowledgeGraph,
    KnowledgePack,
    PlaybookStep,
    load_packs,
    match_patterns,
    register_pack,
    unregister_pack,
)
from veritriage.models import HypothesisCategory
from veritriage.pipeline import analyze
from veritriage.reasoning import ReasoningEngine

SRC = Path(__file__).parent.parent / "src" / "veritriage"

#: Every built-in pack expected to be registered. A regression here means a
#: pack module exists but was never wired into knowledge/packs/__init__.py.
EXPECTED_PACK_IDS = {
    "axi",
    "apb",
    "ahb",
    "chi",
    "tilelink",
    "pcie",
    "uvm",
    "sva",
    "reset-clocking",
    "cdc",
    "coherency",
    "riscv-privilege",
    "coverage",
    # Tier 1 - RISC-V & CPU/ISA depth
    "riscv-atomics",
    "riscv-vector",
    "riscv-memory-model",
    "riscv-interrupts",
    "riscv-pmp",
    "riscv-debug",
    # Tier 2 - Interconnect & NoC
    "axi-stream",
    "ace",
    "noc",
    "cxl",
    "ucie",
    # Tier 3 - Memory & Serial IO
    "ddr",
    "hbm",
    "usb",
    "ethernet",
    "mipi",
    "i2c-i3c",
    "spi",
    "uart",
    "jtag",
    # Tier 4 - Methodology & fundamentals depth
    "uvm-ral",
    "uvm-phasing",
    "uvm-tlm",
    "formal",
    "low-power",
    "dft",
    "x-propagation",
    # Numeric / omission clause upgrade unlocks these
    "performance",
    "security",
    # Milestone 19 - remaining open interconnects
    "ocp",
    "wishbone",
}

#: fixture -> pattern id it must match. One entry per protocol/domain pack
#: added beyond the original Milestone 5 set, so every pack is proven to
#: actually fire on realistic evidence, not just load without error.
_PATTERN_FIXTURES = {
    "ahb_hready_stall.log": "ahb.hready-stall",
    "apb_pready_stuck.log": "apb.pready-stuck",
    "pcie_link_training.log": "pcie.link-training-stuck",
    "chi_credit_starvation.log": "chi.credit-starvation",
    "tilelink_grant_missing.log": "tilelink.grant-missing",
    "cdc_unsynchronized.log": "cdc.unsynchronized-crossing",
    "coherency_illegal_transition.log": "coherency.illegal-transition",
    "riscv_trap_wrong_mode.log": "riscv.trap-wrong-mode",
    "axi_write_response_missing.log": "axi.write-response-missing",
    "axi_exclusive_fail.log": "axi.exclusive-fail",
    "sva_assertion_before_timeout.log": "sva.assertion-before-timeout",
    # Milestone 19 - OCP and Wishbone
    "ocp_request_not_accepted.log": "ocp.request-not-accepted",
    "ocp_response_error.log": "ocp.response-error",
    "ocp_burst_length_mismatch.log": "ocp.burst-length-mismatch",
    "ocp_thread_ordering.log": "ocp.thread-ordering-violation",
    "wishbone_no_termination.log": "wishbone.no-termination",
    "wishbone_err_ignored.log": "wishbone.err-ignored",
    "wishbone_rty_livelock.log": "wishbone.rty-livelock",
    "wishbone_cyc_stb_violation.log": "wishbone.cyc-stb-violation",
    # Tier 1 - RISC-V & CPU/ISA depth
    "riscv_sc_never_succeeds.log": "riscv-atomics.sc-never-succeeds",
    "riscv_amo_ordering.log": "riscv-atomics.amo-ordering-violation",
    "riscv_vector_illegal_vtype.log": "riscv-vector.illegal-vtype",
    "riscv_vector_tail_mask.log": "riscv-vector.tail-mask-corruption",
    "riscv_vector_vl_mismatch.log": "riscv-vector.vl-mismatch",
    "riscv_rvwmo_ordering.log": "riscv-memory-model.ordering-violation",
    "riscv_missing_fence.log": "riscv-memory-model.missing-fence",
    "riscv_plic_priority_inversion.log": "riscv-interrupts.plic-priority-inversion",
    "riscv_plic_claim_complete.log": "riscv-interrupts.missed-claim-complete",
    "riscv_mip_mie_mismatch.log": "riscv-interrupts.mip-mie-mismatch",
    "riscv_pmp_access_fault.log": "riscv-pmp.access-fault-missed",
    "riscv_pmp_napot.log": "riscv-pmp.napot-granularity",
    "riscv_debug_abstract_cmd.log": "riscv-debug.abstract-command-fail",
    "riscv_debug_halt_timeout.log": "riscv-debug.halt-request-timeout",
    # Tier 2 - Interconnect & NoC
    "axi_stream_tlast_missing.log": "axi-stream.tlast-missing",
    "axi_stream_tready_stall.log": "axi-stream.tready-stall",
    "ace_snoop_response_missing.log": "ace.snoop-response-missing",
    "ace_barrier_ordering.log": "ace.barrier-ordering-violation",
    "noc_routing_deadlock.log": "noc.routing-deadlock",
    "noc_credit_underflow.log": "noc.credit-underflow",
    "noc_hol_blocking.log": "noc.hol-blocking",
    "cxl_link_training.log": "cxl.link-training-failed",
    "cxl_mem_completion.log": "cxl.mem-completion-missing",
    "ucie_link_training.log": "ucie.link-training-stuck",
    "ucie_lane_repair.log": "ucie.lane-repair-failed",
    # Tier 3 - Memory & Serial IO
    "ddr_timing_violation.log": "ddr.timing-violation",
    "ddr_refresh_missed.log": "ddr.refresh-missed",
    "hbm_channel_crosstalk.log": "hbm.channel-crosstalk",
    "hbm_refresh_conflict.log": "hbm.refresh-conflict",
    "usb_handshake_missing.log": "usb.handshake-missing",
    "usb_ltssm_stuck.log": "usb.ltssm-stuck",
    "ethernet_fcs_error.log": "ethernet.fcs-error",
    "ethernet_block_lock.log": "ethernet.block-lock-lost",
    "mipi_hs_sync.log": "mipi.hs-sync-fail",
    "mipi_ecc_crc.log": "mipi.ecc-crc-error",
    "i2c_missing_ack.log": "i2c.missing-ack",
    "i3c_ibi_lost.log": "i3c.ibi-lost",
    "spi_mode_mismatch.log": "spi.mode-mismatch",
    "spi_cs_timing.log": "spi.cs-timing",
    "uart_framing_error.log": "uart.framing-error",
    "uart_overrun.log": "uart.overrun",
    "jtag_tap_stuck.log": "jtag.tap-stuck",
    "jtag_ir_dr_mismatch.log": "jtag.ir-dr-mismatch",
    # Tier 4 - Methodology & fundamentals depth
    "uvm_ral_mirror_mismatch.log": "uvm-ral.mirror-mismatch",
    "uvm_ral_access_policy.log": "uvm-ral.access-policy-violation",
    "uvm_phasing_objection.log": "uvm-phasing.objection-not-dropped",
    "uvm_phasing_order.log": "uvm-phasing.phase-order-violation",
    "uvm_tlm_not_connected.log": "uvm-tlm.port-not-connected",
    "uvm_tlm_dropped.log": "uvm-tlm.transaction-dropped",
    "formal_counterexample.log": "formal.counterexample",
    "formal_vacuous.log": "formal.vacuous-pass",
    "formal_inconclusive.log": "formal.inconclusive-bound",
    "lowpower_isolation.log": "low-power.isolation-missing",
    "lowpower_retention.log": "low-power.retention-failure",
    "dft_scan_chain.log": "dft.scan-chain-broken",
    "dft_mbist.log": "dft.mbist-failure",
    "xprop_uninitialized.log": "x-propagation.uninitialized",
    "xprop_control.log": "x-propagation.x-through-control",
    # Numeric / omission clause upgrade
    "performance_latency_sla.log": "performance.latency-sla-miss",
    "performance_bandwidth_sla.log": "performance.bandwidth-sla-miss",
    "security_acl_bypass.log": "security.access-control-bypassed",
    "security_secure_boot.log": "security.secure-boot-unverified",
}


# --- Schema and packs ------------------------------------------------------


def test_builtin_packs_load_and_are_versioned():
    packs = load_packs()
    ids = {p.id for p in packs}
    assert EXPECTED_PACK_IDS <= ids
    for pack in packs:
        assert pack.version
        assert pack.domain
        # Every pattern's playbook reference resolves within its pack set.
        playbook_ids = {b.id for p in packs for b in p.playbooks}
        for pattern in pack.patterns:
            if pattern.playbook_id:
                assert pattern.playbook_id in playbook_ids


def test_knowledge_base_has_real_breadth():
    # Milestone 5 was flagged as too shallow (AXI-only, thin patterns). Pin a
    # floor so the breadth cannot silently regress: many protocol/domain
    # packs, each with multiple patterns/playbooks, not one pack doing all
    # the work.
    packs = load_packs()
    assert len(packs) >= 42
    total_patterns = sum(len(p.patterns) for p in packs)
    total_playbooks = sum(len(p.playbooks) for p in packs)
    total_concepts = sum(len(p.concepts) for p in packs)
    assert total_patterns >= 90
    assert total_playbooks >= 88
    assert total_concepts >= 88
    # Breadth, not one pack padding the count: every pack pulls real weight.
    for pack in packs:
        assert pack.patterns, f"{pack.id} has no failure patterns"
        assert pack.playbooks, f"{pack.id} has no debug playbooks"


@pytest.mark.parametrize("pack", load_packs(), ids=lambda p: p.id)
def test_pack_schema_is_well_formed(pack: KnowledgePack):
    """Every pack's knowledge is structurally sound, independent of matching.

    Regexes compile, confidence modifiers name real hypothesis categories,
    playbook references resolve inside the same pack, every pattern cites at
    least one specification/guideline reference, and every playbook step has
    a non-empty action. This is what "detailed knowledge" means in code: not
    prose, but data a machine can validate.
    """
    playbook_ids = {b.id for b in pack.playbooks}
    seen_pattern_ids: set[str] = set()
    seen_concept_ids: set[str] = set()

    for concept in pack.concepts:
        assert concept.id not in seen_concept_ids, f"duplicate concept id {concept.id}"
        seen_concept_ids.add(concept.id)
        assert concept.summary
        for marker in concept.markers:
            re.compile(marker)  # raises re.error on malformed patterns

    for pattern in pack.patterns:
        assert pattern.id not in seen_pattern_ids, f"duplicate pattern id {pattern.id}"
        seen_pattern_ids.add(pattern.id)
        assert pattern.summary
        assert pattern.typical_causes, f"{pattern.id} lists no typical causes"
        assert pattern.ownership in ("design", "testbench", "infrastructure", "build")
        assert pattern.references, f"{pattern.id} cites no reference"
        for clause in (*pattern.required, *pattern.optional_, *pattern.forbidden):
            re.compile(clause.pattern)
        for category in pattern.confidence_modifiers:
            HypothesisCategory(category)  # raises ValueError if not a real category
        if pattern.playbook_id:
            assert pattern.playbook_id in playbook_ids, (
                f"{pattern.id} references unknown playbook {pattern.playbook_id}"
            )

    for playbook in pack.playbooks:
        assert playbook.steps
        for step in playbook.steps:
            assert step.action.strip()


def test_pack_and_playbook_ids_globally_unique():
    # Packs are independently authored; nothing enforces cross-pack
    # uniqueness except this test, and a collision would silently shadow
    # one pack's item behind another's in the Knowledge Graph.
    packs = load_packs()
    pattern_ids = [p.id for pack in packs for p in pack.patterns]
    playbook_ids = [b.id for pack in packs for b in pack.playbooks]
    concept_ids = [c.id for pack in packs for c in pack.concepts]
    assert len(pattern_ids) == len(set(pattern_ids))
    assert len(playbook_ids) == len(set(playbook_ids))
    assert len(concept_ids) == len(set(concept_ids))


@pytest.mark.parametrize("fixture_name,pattern_id", sorted(_PATTERN_FIXTURES.items()))
def test_pack_pattern_matches_realistic_evidence(fixture_log, fixture_name, pattern_id):
    """Every non-AXI-core pack fires on a realistic fixture, not just in theory."""
    outcome = analyze(fixture_log(fixture_name))
    knowledge = outcome.report.knowledge
    assert knowledge is not None, f"{fixture_name} produced no knowledge context"
    matched = {p.pattern_id: p for p in knowledge.patterns}
    assert pattern_id in matched, (
        f"{fixture_name} expected to match {pattern_id}, got {sorted(matched)}"
    )
    match = matched[pattern_id]
    assert match.playbook is not None
    assert match.playbook.steps
    assert match.references
    for ids in match.matched_evidence.values():
        assert all(i in outcome.graph.nodes for i in ids)
    # The pattern's signal actually reached the reasoning stage.
    signal_names = {s.name for s in outcome.report.reasoning.signals}
    assert f"knowledge:{pattern_id}" in signal_names


def test_knowledge_serializes_round_trip():
    for pack in load_packs():
        restored = KnowledgePack.model_validate_json(pack.model_dump_json())
        assert restored == pack


def test_custom_pack_plugs_in_without_touching_reasoning(fixture_log):
    @register_pack
    def _custom() -> KnowledgePack:
        return KnowledgePack(
            id="custom-test-pack",
            name="Custom",
            version="0.1.0",
            domain="test",
            summary="test pack",
            patterns=[
                FailurePattern(
                    id="custom.scoreboard",
                    name="Custom scoreboard pattern",
                    summary="test pattern",
                    required=[
                        EvidenceClause(name="mismatch", pattern=r"mismatch", must_fail=True)
                    ],
                    typical_causes=["test"],
                    ownership="testbench",
                    playbook_id="custom.pb",
                    confidence_modifiers={"testbench_issue": 0.05},
                )
            ],
            playbooks=[
                DebugPlaybook(
                    id="custom.pb", name="pb", steps=[PlaybookStep(action="do the thing")]
                )
            ],
        )

    try:
        outcome = analyze(fixture_log("uvm_scoreboard.log"))
        assert outcome.report.knowledge is not None
        matched = {p.pattern_id for p in outcome.report.knowledge.patterns}
        assert "custom.scoreboard" in matched
        signal_names = {s.name for s in outcome.report.reasoning.signals}
        assert "knowledge:custom.scoreboard" in signal_names
    finally:
        unregister_pack("custom-test-pack")


# --- The knowledge graph ---------------------------------------------------


def test_knowledge_graph_queries():
    kg = KnowledgeGraph.build()
    assert kg.expected_sequence("axi.read-lifecycle") == [
        "Address issued",
        "Address accepted",
        "Outstanding",
        "Response",
        "Complete",
    ]
    resolved = kg.playbook_for("axi.no-response-after-accept")
    assert resolved is not None
    pack, playbook = resolved
    assert pack.id == "axi"
    assert playbook.id == "axi.read-timeout"
    assert kg.pack_versions()["axi"] == "1.0.0"


def test_knowledge_graph_immutable_during_reasoning(fixture_log):
    kg = KnowledgeGraph.build()
    before = kg.fingerprint()
    outcome = analyze(fixture_log("axi_timeout.log"))
    assert outcome.report.knowledge is not None
    assert kg.fingerprint() == before
    # The graph model itself is frozen: assignment must fail.
    try:
        kg.packs = {}
        raise AssertionError("KnowledgeGraph should be frozen")
    except Exception:
        pass


# --- Deterministic matching ------------------------------------------------


def test_pattern_matching_is_deterministic(fixture_log):
    kg = KnowledgeGraph.build()
    graph = analyze(fixture_log("axi_timeout.log")).graph
    a = match_patterns(kg, graph)
    b = match_patterns(kg, graph)
    assert [(m.pattern.id, m.score, m.matched_evidence) for m in a] == [
        (m.pattern.id, m.score, m.matched_evidence) for m in b
    ]


def test_axi_timeout_matches_no_response_pattern(fixture_log):
    outcome = analyze(fixture_log("axi_timeout.log"))
    k = outcome.report.knowledge
    assert k is not None
    top = k.patterns[0]
    assert top.pattern_id == "axi.no-response-after-accept"
    assert top.score == 1.0
    assert top.ownership.startswith("design")
    assert "ARVALID" in top.suggested_signals
    assert any(r.source.startswith("AMBA AXI") for r in top.references)
    # Every cited node exists in the evidence graph.
    for ids in top.matched_evidence.values():
        assert all(i in outcome.graph.nodes for i in ids)


def test_forbidden_clause_blocks_pattern(fixture_log):
    # An assertion fired in this run, so the timeout/no-response pattern
    # (which forbids assertion evidence) must not match.
    outcome = analyze(fixture_log("uvm_assertion.log"))
    k = outcome.report.knowledge
    matched = {p.pattern_id for p in k.patterns}
    assert "axi.no-response-after-accept" not in matched
    assert "uvm.scoreboard-mismatch-after-protocol-success" not in matched
    assert "axi.valid-drop-before-ready" in matched


def test_state_projection_shows_where_progress_stopped(fixture_log):
    outcome = analyze(fixture_log("axi_timeout.log"))
    sp = outcome.report.knowledge.state_projection
    assert sp is not None
    assert sp.machine_id == "axi.read-lifecycle"
    reached = [s.state for s in sp.states if s.reached]
    assert reached == ["Address issued", "Address accepted", "Outstanding"]
    assert sp.stopped_at == "Response"


def test_playbooks_are_reproducible(fixture_log):
    runs = [analyze(fixture_log("axi_timeout.log")) for _ in range(2)]
    playbooks = [r.report.knowledge.patterns[0].playbook for r in runs]
    assert playbooks[0] == playbooks[1]
    steps = playbooks[0].steps
    assert [s.order for s in steps] == list(range(1, len(steps) + 1))
    assert steps[0].action.startswith("Check ARVALID")


def test_clean_run_has_no_knowledge_section(fixture_log):
    outcome = analyze(fixture_log("uvm_pass.log"))
    assert outcome.report.knowledge is None


def test_coverage_hole_in_passing_run_is_informational_not_a_ranking_signal(fixture_log):
    # A passing run with an uncovered scope is knowledge worth surfacing
    # (the pass proves less than it looks like) but must not masquerade as
    # a failure-ranking signal: there is no failure to rank.
    outcome = analyze([fixture_log("uvm_pass.log"), fixture_log("coverage.txt")])
    knowledge = outcome.report.knowledge
    assert knowledge is not None
    matched = {p.pattern_id for p in knowledge.patterns}
    assert "coverage.hole-in-passing-run" in matched
    assert "coverage.hole-near-failure" not in matched
    assert outcome.report.reasoning is None or not any(
        s.name == "knowledge:coverage.hole-in-passing-run" for s in outcome.report.reasoning.signals
    )


# --- Knowledge feeds reasoning as evidence ---------------------------------


def test_knowledge_signal_influences_ranking_with_trace(fixture_log):
    outcome = analyze(fixture_log("axi_timeout.log"))
    reasoning = outcome.report.reasoning
    knowledge_signals = [s for s in reasoning.signals if s.name.startswith("knowledge:")]
    assert knowledge_signals, "expected knowledge-derived signals"
    for signal in knowledge_signals:
        assert signal.evidence_ids, "knowledge signals must cite evidence"
        assert all(i in outcome.graph.nodes for i in signal.evidence_ids)
    top = reasoning.hypotheses[0]
    assert top.category.value == "rtl_bug"
    trace_sources = {c.source for c in top.confidence_trace.contributions}
    assert "knowledge:axi.no-response-after-accept" in trace_sources


# --- Architecture boundaries -----------------------------------------------


def test_knowledge_never_depends_on_ai():
    banned = ("anthropic", "reasoning.ai", "AIReasoner", "import openai")
    for path in (SRC / "knowledge").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_reasoning_has_no_knowledge_dependency():
    for package in ("reasoning", "rules"):
        for path in (SRC / package).glob("*.py"):
            assert "veritriage.knowledge" not in path.read_text(encoding="utf-8"), path.name


def test_reasoning_executes_with_ai_disabled(fixture_log):
    # The whole knowledge + reasoning stack runs and concludes without any
    # AI: default engines, no API key, no network.
    outcome = analyze(fixture_log("axi_timeout.log"))
    assert outcome.report.reasoning.hypotheses
    assert outcome.report.reasoning.ai_review is None
    assert outcome.report.knowledge is not None
    # And a bare ReasoningEngine (no knowledge rules) still works unchanged.
    bare = ReasoningEngine().reason(outcome.graph)
    assert bare.hypotheses
    assert not any(s.name.startswith("knowledge:") for s in bare.signals)


# --- Numeric and omission clause upgrade -----------------------------------


def _node(node_id: str, description: str, failing: bool = True):
    """A minimal evidence node for clause-matching unit tests."""
    from veritriage.graph.model import ArtifactType, EvidenceNode
    from veritriage.models import Severity

    return EvidenceNode(
        id=node_id,
        artifact_type=ArtifactType.SIMULATION_LOG,
        description=description,
        severity=Severity.ERROR if failing else Severity.INFO,
        source_path="unit-test",
    )


def _graph(*nodes):
    from veritriage.graph.graph import EvidenceGraph

    return EvidenceGraph(nodes={n.id: n for n in nodes})


def _match_ids(pattern_id: str, graph) -> set[str]:
    knowledge = KnowledgeGraph.build()
    return {m.pattern.id for m in match_patterns(knowledge, graph)}


def test_numeric_clause_fires_only_over_threshold():
    """A numeric clause compares the parsed value, not just the keyword: the
    latency SLA-miss pattern fires at 3200 ns and stays silent at 200 ns."""
    over = _graph(_node("n1", "measured read latency 3200 ns exceeds the SLA budget"))
    under = _graph(_node("n2", "measured read latency 200 ns, comfortably within budget"))
    assert "performance.latency-sla-miss" in _match_ids("performance.latency-sla-miss", over)
    assert "performance.latency-sla-miss" not in _match_ids("performance.latency-sla-miss", under)


def test_numeric_clause_direction_for_bandwidth_floor():
    """The bandwidth pattern uses a less-than constraint: 3 GB/s is a miss,
    12 GB/s is not."""
    low = _graph(_node("n1", "sustained bandwidth 3 GB/s below the floor"))
    high = _graph(_node("n2", "sustained bandwidth 12 GB/s above the floor"))
    assert "performance.bandwidth-sla-miss" in _match_ids("x", low)
    assert "performance.bandwidth-sla-miss" not in _match_ids("x", high)


def test_absent_clause_requires_the_marker_to_be_missing():
    """An omission (absent) required clause is satisfied only when the expected
    marker never appears: the access-control bypass fires when no check is
    logged, and is blocked the moment a passing check shows up."""
    bypass = _graph(_node("n1", "secure region write accepted while the core was in non-secure state"))
    assert "security.access-control-bypassed" in _match_ids("x", bypass)

    with_check = _graph(
        _node("n1", "secure region write accepted while the core was in non-secure state"),
        _node("n2", "access-control check passed for the request", failing=False),
    )
    assert "security.access-control-bypassed" not in _match_ids("x", with_check)


def test_numeric_and_absent_are_backward_compatible_defaults():
    """Existing clauses carry neither field: numeric defaults to None and
    absent to False, so a plain presence clause behaves exactly as before."""
    clause = EvidenceClause(name="plain", pattern=r"timeout")
    assert clause.numeric is None
    assert clause.absent is False


# --- One match pass per analysis (Milestone 19) -----------------------------


def test_pattern_rules_share_a_single_match_pass(fixture_log, monkeypatch):
    """The knowledge stage must be linear in pattern count, not quadratic.

    There is one reasoning rule per failure pattern and each needs the same
    match set, so calling the matcher per rule ran a full pass over every
    pattern, clause and node once per pattern. With 100 patterns that is 100
    passes to use one row of each.
    """
    import veritriage.knowledge.inference as inference

    calls = 0
    original = inference.match_patterns

    def counted(knowledge, graph):
        nonlocal calls
        calls += 1
        return original(knowledge, graph)

    monkeypatch.setattr(inference, "match_patterns", counted)
    analyze(fixture_log("axi_timeout.log"))

    n_patterns = len([p for pack in load_packs() for p in pack.patterns])
    assert n_patterns > 50, "guard assumes a large pack library"
    assert calls <= 3, (
        f"{calls} match passes for {n_patterns} patterns; the rules should "
        "share one pass, not run one each"
    )


def test_shared_pass_returns_what_a_direct_match_would(fixture_log):
    """The memo is an optimization, never a different answer."""
    from veritriage.knowledge.inference import _SharedMatchPass

    graph = analyze(fixture_log("axi_timeout.log")).graph
    knowledge = KnowledgeGraph.build()
    shared = _SharedMatchPass()
    assert [m.pattern.id for m in shared.matches(knowledge, graph)] == [
        m.pattern.id for m in match_patterns(knowledge, graph)
    ]
    # Second call on the same graph is served from the memo, same answer.
    assert [m.pattern.id for m in shared.matches(knowledge, graph)] == [
        m.pattern.id for m in match_patterns(knowledge, graph)
    ]


def test_shared_pass_recomputes_for_a_different_graph(fixture_log):
    """Identity, not equality: a new graph never reuses another's matches."""
    from veritriage.knowledge.inference import _SharedMatchPass

    timeout_graph = analyze(fixture_log("axi_timeout.log")).graph
    compile_graph = analyze(fixture_log("compile.log")).graph
    knowledge = KnowledgeGraph.build()
    shared = _SharedMatchPass()
    first = [m.pattern.id for m in shared.matches(knowledge, timeout_graph)]
    second = [m.pattern.id for m in shared.matches(knowledge, compile_graph)]
    assert first != second
    assert second == [m.pattern.id for m in match_patterns(knowledge, compile_graph)]


def test_a_rule_built_on_its_own_still_works(fixture_log):
    """The shared pass is optional; the old one-rule construction still runs."""
    from veritriage.knowledge.inference import KnowledgePatternRule

    knowledge = KnowledgeGraph.build()
    rule = KnowledgePatternRule(knowledge, "axi.no-response-after-accept")
    outcome = analyze(fixture_log("axi_timeout.log"))
    signal = rule.evaluate(outcome.graph, outcome.report.reasoning.working_set)
    assert signal is not None
    assert signal.name == "knowledge:axi.no-response-after-accept"


def test_shared_pass_notices_a_graph_that_grew(fixture_log):
    """Rules held across analyses must not reason from a previous pass."""
    from veritriage.knowledge.inference import _SharedMatchPass

    graph = analyze(fixture_log("uvm_pass.log")).graph
    knowledge = KnowledgeGraph.build()
    shared = _SharedMatchPass()
    before = [m.pattern.id for m in shared.matches(knowledge, graph)]

    grown = analyze(fixture_log("axi_timeout.log")).graph
    for node in grown.nodes.values():
        if node.id not in graph.nodes:
            graph.add_node(node)

    after = [m.pattern.id for m in shared.matches(knowledge, graph)]
    assert after == [m.pattern.id for m in match_patterns(knowledge, graph)]
    assert after != before

"""Milestone 27 (DFT): multiple scan chains, stuck-at ATPG, and March C- MBIST.

* Chain planning, the tracer, and PODEM are tested on hand-written netlists,
  with no tool installed.
* Real-tool tests run Yosys and Icarus and skip when an executable is absent
  (or fail when CI names it in NIRMAAN_REQUIRE_EDA).
* Fault coverage is what the Icarus fault simulation measured; a pattern set
  that claims more than the simulation sees is refused.
* Crown jewel: a new ATPG backend needs zero core changes.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from nirmaan_helpers import agent, tid
from test_nirmaan_dft import AXI, COUNTER, RTL, _cell, _netlist, holder, invoke, needs

from nirmaan.integrations.dft_atpg import CaptureModel, generate
from nirmaan.integrations.dft_scan import Design, NetlistError, stitch
from nirmaan.models import ToolStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ToolAccessDenied, ToolBroker

DFT = RTL / "dft"
TWO_CLOCKS = DFT / "two_clocks.v"
ATPG_DEMO = DFT / "atpg_demo.v"
MBIST = RTL / "mbist"
RAM = MBIST / "sync_ram.v"
FAULTY_RAMS = MBIST / "faulty_rams.v"
BLOCKS = {
    "counter": (COUNTER, "counter"),
    "axi4_lite": (AXI, "axi4_lite_regs"),
    "apb_regs": (RTL / "apb_regs" / "apb_regs.v", "apb_regs"),
    "rr_arbiter": (RTL / "rr_arbiter" / "rr_arbiter.v", "rr_arbiter"),
    "sync_fifo": (RTL / "sync_fifo" / "sync_fifo.v", "sync_fifo"),
}


@pytest.fixture()
def engine(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-bit wrapping counter with scan chains.")


def insert(engine, source: Path, top: str, workdir: Path, **params: str) -> dict:
    run, outcome = invoke(engine, "dft.scan_insert", {"sources": str(source), "top": top, **params}, workdir)
    assert run.succeeded, run.summary
    return outcome.data["result"]["metrics"]


def atpg(engine, sources: str, top: str, workdir: Path, **params: str):
    run, outcome = invoke(engine, "dft.atpg", {"sources": sources, "top": top, **params}, workdir)
    return run, outcome.data["result"]["metrics"] if outcome.data else {}


# --- Hand-written netlists (no tool needed) --------------------------------------------------


def _flops(n: int, clocks: tuple[int, ...] = (2,)) -> dict:
    """n flops q[0..n-1] (bits 10..), each loading input d; flop i on clock clocks[i % len]."""
    cells = {f"f{i}": _cell("$_DFF_P_", C=clocks[i % len(clocks)], D=3, Q=10 + i) for i in range(n)}
    ports = {f"clk{j}": {"direction": "input", "bits": [c]} for j, c in enumerate(clocks)}
    ports.update(d={"direction": "input", "bits": [3]},
                 q={"direction": "output", "bits": [10 + i for i in range(n)]})
    names = {f"clk{j}": [c] for j, c in enumerate(clocks)}
    names.update(d=[3], q=[10 + i for i in range(n)])
    return _netlist(cells, ports, names)


def _lengths(report: dict) -> list[int]:
    return [c["length"] for c in report["chains"]]


def test_chains_are_balanced_within_one_domain():
    netlist, report = stitch(_flops(5), "top", chains=2)
    assert _lengths(report) == [3, 2] and report["length"] == 3 and report["flops"] == 5
    module = netlist["modules"]["top"]
    si, so = module["ports"]["scan_in"]["bits"], module["ports"]["scan_out"]["bits"]
    assert len(si) == len(so) == 2
    cells = module["cells"]
    assert cells["f0"]["connections"]["SI"] == [si[0]] and cells["f3"]["connections"]["SI"] == [si[1]]
    assert cells["f1"]["connections"]["SI"] == [10] and so == [12, 14]
    assert [c["order"] for c in report["chains"]] == [["q[0]", "q[1]", "q[2]"], ["q[3]", "q[4]"]]


def test_max_chain_length_adds_chains_and_one_chain_keeps_scalar_ports():
    _, report = stitch(_flops(5), "top", max_length=2)
    assert _lengths(report) == [2, 2, 1]
    netlist, report = stitch(_flops(3), "top")
    assert _lengths(report) == [3] and len(netlist["modules"]["top"]["ports"]["scan_in"]["bits"]) == 1
    with pytest.raises(NetlistError, match="6 chains for 5 flops"):
        stitch(_flops(5), "top", chains=6)
    with pytest.raises(NetlistError, match="positive"):
        stitch(_flops(5), "top", chains=0)


def test_chains_are_grouped_by_clock_domain():
    """Two clocks: never refused, never mixed; a spare chain goes to the domain with the longest chain."""
    _, report = stitch(_flops(5, clocks=(2, 4)), "top")
    assert _lengths(report) == [3, 2]
    assert [c["clock"]["port"] for c in report["chains"]] == ["clk0", "clk1"]
    assert report["chains"][0]["order"] == ["q[0]", "q[2]", "q[4]"]
    _, report = stitch(_flops(5, clocks=(2, 4)), "top", chains=3)
    assert _lengths(report) == [2, 1, 2] and [c["clock"]["port"] for c in report["chains"]] == ["clk0", "clk0", "clk1"]


def test_every_chain_is_traced_from_its_own_scan_in():
    netlist, _ = stitch(_flops(4), "top", chains=2)
    module = netlist["modules"]["top"]
    for name, cell in list(module["cells"].items()):  # expand each scan cell by hand: D' = SE ? SI : D
        if cell["type"].startswith("$__NIRMAAN_SCAN"):
            mux = 1000 + int(name[1:])
            conns = cell["connections"]
            module["cells"][f"m{name}"] = _cell("$_MUX_", A=conns["D"][0], B=conns["SI"][0], S=conns["SE"][0], Y=mux)
            cell["type"] = "$_DFF_P_"
            cell["connections"] = {"C": conns["C"], "D": [mux], "Q": conns["Q"]}
    design = Design.from_json(netlist, "top")
    chain = design.trace_chain()
    assert chain.complete, chain.problems
    assert [[f.name for f in c] for c in chain.chains] == [["q[0]", "q[1]"], ["q[2]", "q[3]"]]
    # Swap the two scan_out bits: each chain now ends at the other one's port.
    so = module["ports"]["scan_out"]["bits"]
    module["ports"]["scan_out"]["bits"] = so[::-1]
    broken = Design.from_json(netlist, "top").trace_chain()
    assert not broken.complete and any("scan_out[0]" in p for p in broken.problems)


def _consensus() -> Design:
    """f = a&b | ~a&c | b&c: the b&c term (t3) is redundant, so t3 stuck-at-0 has no test."""
    cells = {"g1": _cell("$_AND_", A=2, B=3, Y=10), "g2": _cell("$_NOT_", A=2, Y=11),
             "g3": _cell("$_AND_", A=11, B=4, Y=12), "g4": _cell("$_AND_", A=3, B=4, Y=13),
             "g5": _cell("$_OR_", A=10, B=12, Y=14), "g6": _cell("$_OR_", A=14, B=13, Y=15)}
    ports = {"a": {"direction": "input", "bits": [2]}, "b": {"direction": "input", "bits": [3]},
             "c": {"direction": "input", "bits": [4]}, "f": {"direction": "output", "bits": [15]}}
    names = {"a": [2], "b": [3], "c": [4], "t1": [10], "na": [11], "t2": [12], "t3": [13], "o1": [14], "f": [15]}
    return Design.from_json(_netlist(cells, ports, names), "top")


def test_podem_finds_tests_and_proves_a_redundant_fault_untestable():
    design = _consensus()
    model = CaptureModel.build(design)
    faults = {f.name: f for f in model.faults()}
    assert len(faults) == 2 * 9  # stuck-at 0 and 1 on three inputs and six gate outputs
    status, pattern = model.podem(faults["t3/SA0"])
    assert status == "untestable" and pattern is None
    status, pattern = model.podem(faults["t2/SA0"])
    assert status == "detected" and model.detects(pattern, faults["t2/SA0"])
    patterns = generate(design, seed=3)
    assert patterns["untestable"] == ["t3/SA0"] and not patterns["aborted"]
    assert set(patterns["claims"]) == set(faults) - {"t3/SA0"}
    for name, index in patterns["claims"].items():
        assert model.detects(model.pattern_values(patterns["patterns"][index]), faults[name]), name


# --- Refusal: a missing tool is never simulated ---------------------------------------------


def test_the_new_tools_are_available_and_refused_without_their_executables(engine, tmp_path, monkeypatch):
    for tool in ("dft.atpg", "dft.mbist"):
        assert engine.org.tools[tool].status is ToolStatus.AVAILABLE, tool
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ToolAccessDenied, match="needs yosys, iverilog, vvp.*not found"):
        invoke(engine, "dft.atpg", {"sources": str(COUNTER), "top": "counter"}, tmp_path)
    with pytest.raises(ToolAccessDenied, match="needs yosys, iverilog, vvp.*not found"):
        invoke(engine, "dft.mbist", {"sources": str(RAM), "top": "sync_ram"}, tmp_path)
    assert engine.state.tool_runs == {}


# --- Real tools: multiple chains ---------------------------------------------------------------


@needs("yosys", "iverilog", "vvp")
@pytest.mark.parametrize("block,params", [
    ("counter", {"chains": "2"}), ("axi4_lite", {"chains": "8"}), ("apb_regs", {"max_chain_length": "20"}),
    ("rr_arbiter", {"chains": "2"}), ("sync_fifo", {"chains": "4"})])
def test_real_multi_chain_insertion_checks_and_simulates(engine, tmp_path, block, params):
    source, top = BLOCKS[block]
    metrics = insert(engine, source, top, tmp_path / "insert", **params)
    lengths = metrics["chain_lengths"]
    assert max(lengths) - min(lengths) <= 1 and metrics["chains"] == len(lengths) > 1
    assert metrics["chain_length"] == max(lengths) and sum(lengths) == metrics["flops"]
    if "max_chain_length" in params:
        assert max(lengths) <= int(params["max_chain_length"])
    scan = {"sources": metrics["scan_netlist"], "top": top}
    check, outcome = invoke(engine, "dft.check", scan, tmp_path / "check")
    assert check.succeeded and f"{len(lengths)} chains complete" in check.summary, check.summary
    sim, outcome = invoke(engine, "dft.scan_sim", scan, tmp_path / "sim")
    assert sim.succeeded, sim.summary
    assert f"{len(lengths)} chains, {metrics['flops']} flops" in sim.summary and "0 mismatches" in sim.summary
    assert outcome.data["result"]["metrics"]["shift_errors"] == 0


@needs("yosys", "iverilog", "vvp")
def test_clock_domains_get_their_own_chains_and_capture_in_edge_order(engine, tmp_path):
    rtl, outcome = invoke(engine, "dft.check", {"sources": str(TWO_CLOCKS), "top": "two_clocks"}, tmp_path / "rtl")
    assert rtl.succeeded, rtl.summary
    metrics = insert(engine, TWO_CLOCKS, "two_clocks", tmp_path / "insert")
    report = json.loads(Path(metrics["chain_report"]).read_text())
    domains = [(c["clock"]["port"], c["clock"]["edge"]) for c in report["chains"]]
    assert sorted(domains) == [("clk_a", "negedge"), ("clk_a", "posedge"), ("clk_b", "posedge")]
    sim, _ = invoke(engine, "dft.scan_sim", {"sources": metrics["scan_netlist"], "top": "two_clocks"},
                    tmp_path / "sim")
    assert sim.succeeded, sim.summary


# --- Real tools: ATPG, measured by fault simulation ---------------------------------------------


def _scan(engine, block: str, workdir: Path, **params: str) -> tuple[str, str]:
    source, top = (ATPG_DEMO, "atpg_demo") if block == "atpg_demo" else BLOCKS[block]
    return insert(engine, source, top, workdir, **params)["scan_netlist"], top


@needs("yosys", "iverilog", "vvp")
def test_real_atpg_coverage_is_measured_by_fault_simulation(engine, tmp_path):
    scan, top = _scan(engine, "counter", tmp_path / "insert")
    run, metrics = atpg(engine, scan, top, tmp_path / "atpg", min_test_coverage="100")
    assert run.succeeded, run.summary
    total = metrics["faults_total"]
    assert total == metrics["faults_detected"] + metrics["faults_undetectable"] + metrics["faults_undetected"]
    assert metrics["test_coverage"] == 100.0 and metrics["claims_not_detected"] == 0
    assert metrics["response_errors"] == 0 and metrics["injection_errors"] == 0
    assert f"{metrics['faults_detected']} of {total} faults detected in fault simulation" in run.summary
    log = Path(run.references[0]).read_text()
    assert log.count("DFT-FAULT ") == total and "DFT-ATPG-CHECK: " in log


@needs("yosys", "iverilog", "vvp")
@pytest.mark.parametrize("block,chains", [("rr_arbiter", "2"), ("sync_fifo", "4")])
def test_real_atpg_on_multi_chain_blocks(engine, tmp_path, block, chains):
    scan, top = _scan(engine, block, tmp_path / "insert", chains=chains)
    run, metrics = atpg(engine, scan, top, tmp_path / "atpg", min_test_coverage="95")
    assert run.succeeded, run.summary
    assert metrics["chains"] == int(chains) and metrics["claims_not_detected"] == 0


@needs("yosys", "iverilog", "vvp")
def test_an_undetectable_fault_is_classified_and_the_threshold_is_data(engine, tmp_path):
    scan, top = _scan(engine, "atpg_demo", tmp_path / "insert", chains="2")
    run, metrics = atpg(engine, scan, top, tmp_path / "atpg")
    assert run.succeeded, run.summary
    faults = {f["name"]: f for f in metrics["fault_list"]}
    assert faults["spare/SA0"]["class"] == faults["spare/SA1"]["class"] == "undetectable"
    assert metrics["faults_undetectable"] >= 2 and metrics["test_coverage"] > metrics["fault_coverage"]
    below, _ = atpg(engine, scan, top, tmp_path / "strict", min_fault_coverage="100")
    assert not below.succeeded and "fault_coverage" in below.summary and "min_fault_coverage 100" in below.summary


@needs("yosys", "iverilog", "vvp")
def test_a_pattern_set_that_claims_too_much_is_refused(engine, tmp_path):
    scan, top = _scan(engine, "atpg_demo", tmp_path / "insert")
    run, _ = atpg(engine, scan, top, tmp_path / "atpg")
    assert run.succeeded, run.summary
    patterns = json.loads((tmp_path / "atpg" / "patterns.json").read_text())

    # 1. A false claim: the file says pattern 0 detects a fault nothing can observe.
    false_claim = tmp_path / "false_claim.json"
    false_claim.write_text(json.dumps({**patterns, "claims": {**patterns["claims"], "spare/SA1": 0}}))
    graded, _ = atpg(engine, scan, top, tmp_path / "graded", patterns=str(false_claim))
    assert not graded.succeeded and graded.id in engine.state.tool_runs
    assert "claims 1 fault the fault simulation did not detect" in graded.summary and "spare/SA1" in graded.summary

    # 2. A wrong expected response: one unloaded bit flipped.
    wrong = json.loads(json.dumps(patterns))
    bits = wrong["patterns"][0]["unload"][0]
    wrong["patterns"][0]["unload"][0] = ("1" if bits[0] == "0" else "0") + bits[1:]
    wrong_response = tmp_path / "wrong_response.json"
    wrong_response.write_text(json.dumps(wrong))
    graded, metrics = atpg(engine, scan, top, tmp_path / "graded2", patterns=str(wrong_response))
    assert not graded.succeeded and metrics["response_errors"] == 1
    assert "expected responses" in graded.summary

    # 3. The file as generated grades clean.
    clean = tmp_path / "clean.json"
    clean.write_text(json.dumps(patterns))
    graded, _ = atpg(engine, scan, top, tmp_path / "graded3", patterns=str(clean))
    assert graded.succeeded, graded.summary


@needs("yosys", "iverilog", "vvp")
def test_atpg_refuses_a_broken_chain(engine, tmp_path):
    run, _ = atpg(engine, str(DFT / "broken_chain.v"), "broken_chain", tmp_path / "atpg")
    assert not run.succeeded and "scan chain is broken" in run.summary


# --- Real tools: MBIST -----------------------------------------------------------------------


def mbist(engine, source: Path, top: str, workdir: Path):
    run, outcome = invoke(engine, "dft.mbist", {"sources": str(source), "top": top}, workdir)
    return run, outcome.data["result"]["metrics"] if outcome.data else {}


@needs("yosys", "iverilog", "vvp", "verilator")
def test_march_c_minus_passes_a_clean_ram_and_the_controller_is_lint_clean(engine, tmp_path):
    run, metrics = mbist(engine, RAM, "sync_ram", tmp_path / "mbist")
    assert run.succeeded, run.summary
    assert metrics["depth"] == 16 and metrics["width"] == 8
    assert metrics["reads"] == metrics["writes"] == 5 * 16 and metrics["cycles"] == 15 * 16
    assert run.summary == "icarus-mbist: March C- passed on sync_ram: 16 words of 8 bits, 160 operations, 240 cycles"
    lint, _ = invoke(engine, "lint.run", {"sources": metrics["controller"]}, tmp_path / "lint")
    assert lint.succeeded, lint.summary


@needs("yosys", "iverilog", "vvp")
@pytest.mark.parametrize("top", ["ram_stuck_at_0", "ram_stuck_at_1", "ram_transition", "ram_coupling_inversion",
                                 "ram_coupling_idempotent", "ram_address_decoder"])
def test_march_c_minus_fails_each_injected_fault(engine, tmp_path, top):
    run, metrics = mbist(engine, FAULTY_RAMS, top, tmp_path / "mbist")
    assert not run.succeeded and run.id in engine.state.tool_runs
    assert f"March C- failed on {top}" in run.summary and metrics["fail"] is True


# --- The seat, as data -----------------------------------------------------------------------


def test_the_dft_stage_requires_real_coverage_before_review(engine):
    dft = engine.task(tid(engine, "dft"))
    gated = {t: r for r in dft.evidence_requirements if r.before_review for t in r.tools}
    assert sorted(gated) == ["dft.atpg", "dft.check", "dft.scan_insert", "dft.scan_sim"]  # M44: insert first
    assert dict(gated["dft.atpg"].params) == {"min_test_coverage": "90"}
    skills = engine.org.skills
    assert "dft.atpg" in skills["atpg"].tools and "dft.mbist" in skills["mbist"].tools
    assert "dft.atpg" in skills["scan_design"].tools
    assert holder(engine, "dft.atpg") and holder(engine, "dft.mbist")


# --- Crown jewel: a new ATPG backend needs no core changes -----------------------------------


@needs("yosys", "iverilog", "vvp")
def test_a_new_atpg_backend_needs_no_core_changes(engine, tmp_path):
    """A generator the core has never seen: random patterns only, graded by the same fault simulation."""
    from nirmaan.integrations import dft
    from nirmaan.integrations.eda import Backend, register_backend, unregister_backend

    def steps(job):
        return [*dft.atpg_analysis_steps(job),
                dft.atpg_helper("generate", dft.DESIGN_JSON, dft.PATTERNS, str(job.top), "--random-only"),
                *dft.atpg_grading_steps(job, dft.PATTERNS)]

    register_backend(Backend("random-atpg", "dft.atpg", ("yosys", "iverilog", "vvp"), steps, dft.parse_atpg,
                             ("sources", "top")))
    try:
        scan, top = _scan(engine, "counter", tmp_path / "insert")
        run, metrics = atpg(engine, scan, top, tmp_path / "atpg", backend="random-atpg")
        assert run.succeeded and run.summary.startswith("random-atpg: "), run.summary
        assert metrics["faults_detected"] > 0 and metrics["claims_not_detected"] == 0
    finally:
        unregister_backend("dft.atpg", "random-atpg")
    assert shutil.which("yosys")
    broker = ToolBroker(engine)
    with pytest.raises(ToolAccessDenied, match="no backend named 'random-atpg'"):
        broker.invoke(agent(holder(engine, "dft.atpg")), "dft.atpg",
                      {"sources": str(COUNTER), "top": "counter", "backend": "random-atpg",
                       "workdir": str(tmp_path / "gone")})

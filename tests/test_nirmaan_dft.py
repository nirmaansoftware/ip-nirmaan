"""Milestone 25 (DFT): scan insertion, testability rules, and chain simulation.

* The stitcher, chain tracer, and rules are tested on hand-written netlists,
  with no tool installed.
* Real-tool tests run Yosys and Icarus over the fixture RTL and skip when an
  executable is absent (or fail when CI names it in NIRMAAN_REQUIRE_EDA).
* A missing Yosys is a refusal with a reason, never a simulated run.
* A DFT stage's scan netlist reaches review only after real rule checks and a
  real chain simulation passed on it.
* Crown jewel: a new testability rule needs zero core changes.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from nirmaan_helpers import agent, human, tid
from laws import needs

from nirmaan.integrations.dft import DftRule, register_rule, rules, unregister_rule
from nirmaan.integrations.dft_scan import SCAN_CELL, Design, NetlistError, stitch, techmap_file
from nirmaan.models import Assurance, EvidenceKind, ReviewState, TaskStatus, ToolStatus, Verdict
from nirmaan.orchestrator import Orchestrator
from nirmaan.org import AuthorityService
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, review_task, run_task
from nirmaan.runtime import ToolAccessDenied, ToolBroker
from nirmaan.work import PolicyViolationError

FIXTURES = Path(__file__).parent / "fixtures"
RTL = FIXTURES / "rtl"
COUNTER = RTL / "counter.v"
AXI = RTL / "axi4_lite" / "axi4_lite_regs.v"
UNTESTABLE = RTL / "dft" / "untestable.v"
BROKEN = RTL / "dft" / "broken_chain.v"
DFT_TOOLS = ("dft.scan_insert", "dft.check", "dft.scan_sim")


@pytest.fixture()
def engine(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-bit wrapping counter with scan chains.")


def holder(engine, tool: str) -> str:
    authority = AuthorityService(engine.org)
    for role in engine.org.roles:
        if authority.may_use_tool(role, tool)[0]:
            return role
    raise AssertionError(f"no role may use {tool}")


def invoke(engine, tool: str, params: dict[str, str], workdir: Path, task: str | None = None):
    return ToolBroker(engine).invoke(agent(holder(engine, tool)), tool, {"workdir": str(workdir), **params}, task)


def insert(engine, source: Path, top: str, workdir: Path):
    run, outcome = invoke(engine, "dft.scan_insert", {"sources": str(source), "top": top}, workdir)
    assert run.succeeded, run.summary
    return outcome.data["result"]["metrics"]


# --- Hand-written netlists (no tool needed) --------------------------------------------------


def _netlist(cells: dict, ports: dict, names: dict) -> dict:
    return {"modules": {"top": {"attributes": {"top": "00000000000000000000000000000001"}, "ports": ports,
                                "cells": cells,
                                "netnames": {n: {"hide_name": 0, "bits": b} for n, b in names.items()}}}}


def _cell(kind: str, **conns) -> dict:
    outputs = {"Y", "Q"}
    return {"type": kind, "connections": {p: [b] for p, b in conns.items()},
            "port_directions": {p: "output" if p in outputs else "input" for p in conns}}


def _two_flops() -> dict:
    """clk=2, d=3; q0 (bit 4) loads d, q1 (bit 5) loads ~q0 (bit 6)."""
    return _netlist(
        {"f1": _cell("$_DFF_P_", C=2, D=6, Q=5), "f0": _cell("$_DFF_P_", C=2, D=3, Q=4),
         "n": _cell("$_NOT_", A=4, Y=6)},
        {"clk": {"direction": "input", "bits": [2]}, "d": {"direction": "input", "bits": [3]},
         "q": {"direction": "output", "bits": [4, 5]}},
        {"clk": [2], "d": [3], "q": [4, 5], "$n": [6]})


def test_the_dft_tools_are_available_and_atpg_stays_a_contract(nirmaan_org):
    for tool in DFT_TOOLS:
        assert nirmaan_org.tools[tool].status is ToolStatus.AVAILABLE, tool
    assert nirmaan_org.tools["dft.run"].status is ToolStatus.CONTRACT_ONLY


def test_stitching_puts_every_flop_on_one_chain_in_name_order():
    netlist, report = stitch(_two_flops(), "top")
    module = netlist["modules"]["top"]
    assert [f["flop"] for f in report["order"]] == ["q[0]", "q[1]"]
    assert report["length"] == 2 and report["clock"] == {"port": "clk", "edge": "posedge"}
    se, si = module["ports"]["scan_en"]["bits"][0], module["ports"]["scan_in"]["bits"][0]
    assert module["ports"]["scan_out"]["bits"] == [5]  # the last flop's Q
    f0, f1 = module["cells"]["f0"], module["cells"]["f1"]
    assert f0["type"] == f1["type"] == SCAN_CELL + "_DFF_P_"
    assert f0["connections"]["SI"] == [si] and f1["connections"]["SI"] == [4]
    assert f0["connections"]["SE"] == f1["connections"]["SE"] == [se]


def test_stitching_refuses_what_one_mux_d_chain_cannot_cover():
    latch = _two_flops()
    latch["modules"]["top"]["cells"]["l"] = _cell("$_DLATCH_P_", E=3, D=3, Q=6)
    with pytest.raises(NetlistError, match="cannot take a mux-D scan flop"):
        stitch(latch, "top")
    generated = _two_flops()  # M27 groups clock domains into chains, but a clock must still be an input
    generated["modules"]["top"]["cells"]["f1"]["connections"]["C"] = [6]
    with pytest.raises(NetlistError, match="not a module input"):
        stitch(generated, "top")
    taken = _two_flops()
    taken["modules"]["top"]["ports"]["scan_en"] = {"direction": "input", "bits": [9]}
    with pytest.raises(NetlistError, match="already has port"):
        stitch(taken, "top")
    empty = _netlist({}, {"a": {"direction": "input", "bits": [2]}}, {"a": [2]})
    with pytest.raises(NetlistError, match="no flip-flops"):
        stitch(empty, "top")


def _scan_pair(second_si: int) -> Design:
    """Two flops with scan muxes; the second one's shift input is ``second_si``."""
    return Design.from_json(_netlist(
        {"f0": _cell("$_DFF_P_", C=2, D=10, Q=4), "f1": _cell("$_DFF_P_", C=2, D=11, Q=5),
         "m0": _cell("$_MUX_", A=3, B=8, S=7, Y=10), "m1": _cell("$_MUX_", A=4, B=second_si, S=7, Y=11)},
        {"clk": {"direction": "input", "bits": [2]}, "d": {"direction": "input", "bits": [3]},
         "scan_en": {"direction": "input", "bits": [7]}, "scan_in": {"direction": "input", "bits": [8]},
         "scan_out": {"direction": "output", "bits": [5]}},
        {"clk": [2], "d": [3], "a": [4], "b": [5], "scan_en": [7], "scan_in": [8]}), "top")


def test_the_chain_is_traced_functionally():
    chain = _scan_pair(second_si=4).trace_chain()
    assert chain.complete and [f.name for f in chain.order] == ["a", "b"]
    broken = _scan_pair(second_si=3).trace_chain()  # b shifts in d, not a
    assert not broken.complete and broken.off_chain == ["b"]
    assert any("flop b is not on the scan chain" in p for p in broken.problems)


def test_rules_find_latches_and_generated_clocks_in_a_netlist():
    from nirmaan.integrations.dft import check_design

    design = copy.deepcopy(_two_flops())
    cells = design["modules"]["top"]["cells"]
    cells["l"] = _cell("$_DLATCH_P_", E=3, D=3, Q=7)
    cells["g"] = _cell("$_AND_", A=2, B=3, Y=8)
    cells["f1"]["connections"]["C"] = [8]  # clocked by clk & d
    diags, verdicts = check_design(Design.from_json(design, "top"))
    assert verdicts["no-latches"] == verdicts["clock-from-input"] == "fail"
    assert verdicts["scan-chain-complete"] == "not applicable"
    assert any(d.code == "clock-from-input" and "q[1]" in d.message and "$_AND_" in d.message for d in diags)


def test_the_techmap_covers_every_plain_flop_type():
    text = techmap_file()
    for kind in ("$_DFF_P_", "$_DFF_N_", "$_DFF_PN0_", "$_DFF_NP1_"):
        assert f"module \\{SCAN_CELL}{kind[1:]} " in text and f"\\{kind} _TECHMAP_REPLACE_" in text


# --- Refusal: a missing Yosys is never simulated ------------------------------------------------


def test_without_yosys_every_dft_tool_is_refused(engine, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    for tool in DFT_TOOLS:
        with pytest.raises(ToolAccessDenied, match="needs yosys.*not found"):
            invoke(engine, tool, {"sources": str(COUNTER), "top": "counter"}, tmp_path)
    assert engine.state.tool_runs == {}


# --- Real tools: insertion, rules, and the chain simulation ----------------------------------------


@needs("yosys")
def test_real_scan_insertion_of_the_counter(engine, tmp_path):
    metrics = insert(engine, COUNTER, "counter", tmp_path)
    assert metrics["chain_length"] == 4 and metrics["order"] == ["count[0]", "count[1]", "count[2]", "count[3]"]
    assert metrics["clock"] == {"port": "clk", "edge": "posedge"}
    netlist = Path(metrics["scan_netlist"]).read_text()
    assert "module counter(" in netlist and all(f"{p};" in netlist for p in ("scan_en", "scan_in", "scan_out"))
    assert Path(metrics["chain_report"]).is_file()


@needs("yosys", "iverilog", "vvp")
@pytest.mark.parametrize("source,top", [(COUNTER, "counter"), (AXI, "axi4_lite_regs")], ids=["counter", "axi4_lite"])
def test_real_scan_chain_shifts_and_captures(engine, tmp_path, source, top):
    """Insert, check, and simulate for real: every flop on the chain, shift and capture clean."""
    rtl, _ = invoke(engine, "dft.check", {"sources": str(source), "top": top}, tmp_path / "rtl")
    assert rtl.succeeded and "chain rule not applicable" in rtl.summary, rtl.summary
    metrics = insert(engine, source, top, tmp_path / "insert")
    params = {"sources": metrics["scan_netlist"], "top": top}
    check, outcome = invoke(engine, "dft.check", params, tmp_path / "check")
    assert check.succeeded and "chain complete" in check.summary, check.summary
    flops = outcome.data["result"]["metrics"]["flip_flops"]
    assert metrics["chain_length"] == flops > 0 and outcome.data["result"]["metrics"]["chain_length"] == flops
    sim, outcome = invoke(engine, "dft.scan_sim", params, tmp_path / "sim")
    assert sim.succeeded, sim.summary
    assert sim.summary == (f"icarus-scan: scan chain passed: {flops} flops, {2 * flops} bits shifted through, "
                           f"one capture checked, 0 mismatches")
    assert f"DFT-SCAN: chain length {flops}, shift errors 0, capture errors 0" in Path(sim.references[0]).read_text()


@needs("yosys", "iverilog", "vvp")
def test_a_broken_chain_is_caught_and_recorded(engine, tmp_path):
    params = {"sources": str(BROKEN), "top": "broken_chain"}
    check, outcome = invoke(engine, "dft.check", params, tmp_path / "check")
    assert not check.succeeded and check.id in engine.state.tool_runs
    diags = outcome.data["result"]["diagnostics"]
    assert [d["code"] for d in diags] == ["scan-chain-complete"]
    assert "flop b is not on the scan chain" in diags[0]["message"]
    sim, outcome = invoke(engine, "dft.scan_sim", params, tmp_path / "sim")
    assert not sim.succeeded and sim.id in engine.state.tool_runs
    assert "scan chain is broken" in sim.summary and "flop b" in sim.summary


@needs("yosys", "iverilog", "vvp")
def test_a_chain_that_shifts_wrong_fails_in_simulation(engine, tmp_path):
    """The scan netlist is edited after insertion so one flop shifts in its inverse."""
    metrics = insert(engine, COUNTER, "counter", tmp_path / "insert")
    netlist = Path(metrics["scan_netlist"]).read_text()
    # Rewire scan_in into the first flop through an inverter: the chain still exists, but shifts wrong.
    edited = netlist.replace("scan_en ? scan_in :", "scan_en ? ~scan_in :", 1)
    assert edited != netlist
    bad = tmp_path / "inverted.v"
    bad.write_text(edited)
    sim, _ = invoke(engine, "dft.scan_sim", {"sources": str(bad), "top": "counter"}, tmp_path / "sim")
    assert not sim.succeeded and sim.id in engine.state.tool_runs


@needs("yosys")
def test_rule_violations_are_found_in_untestable_rtl(engine, tmp_path):
    params = {"sources": str(UNTESTABLE), "top": "untestable"}
    run, outcome = invoke(engine, "dft.check", params, tmp_path / "check")
    assert not run.succeeded and "dft check failed" in run.summary
    result = outcome.data["result"]
    by_rule: dict[str, list[str]] = {}
    for d in result["diagnostics"]:
        by_rule.setdefault(d["code"], []).append(d["message"])
    assert any("held" in m for m in by_rule["no-latches"])
    assert any("slow" in m for m in by_rule["clock-from-input"]) and any("div" in m for m in by_rule["clock-from-input"])
    assert by_rule["no-combinational-loops"] and "one-clock-domain" not in by_rule  # retired in M27
    assert result["metrics"]["rules"]["reset-from-input"] == "pass"
    insertion, _ = invoke(engine, "dft.scan_insert", params, tmp_path / "insert")
    assert not insertion.succeeded and "scan insertion failed" in insertion.summary


# --- The DFT seat: data, gated on real runs before review ------------------------------------------


def test_the_dft_stage_is_planned_only_when_test_is_asked_for(engine, nirmaan_org, fixed_clock):
    stages = [t.stage for t in engine.state.tasks.values() if t.stage]
    assert stages == ["requirements", "interface-spec", "microarchitecture", "rtl-implementation", "dft"]
    dft = engine.task(tid(engine, "dft"))
    assert dft.capability == "dft.insert" and dft.expected_outputs == ("dft_netlist",)
    assert dft.owner.startswith("implementation.dft.engineering.scan.")
    gated = [r for r in dft.evidence_requirements if r.before_review]
    assert sorted(t for r in gated for t in r.tools) == ["dft.atpg", "dft.check", "dft.scan_sim"]
    plain = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-bit wrapping counter.")
    assert "dft" not in [t.stage for t in plain.state.tasks.values()]


@needs("verilator", "yosys", "iverilog", "vvp")
def test_a_scan_netlist_reaches_review_only_after_real_checks(engine, tmp_path):
    """RTL by an agent seat, then scan by a DFT engineer: the netlist is gated on its own runs."""
    from test_nirmaan_design_agents import answer, counter_files, token, upstream, with_workspace
    from nirmaan_helpers import drive

    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    with_workspace(engine, rtl, tmp_path / "rtl")
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[
        answer(*counter_files(token(upstream(engine, "microarchitecture"))))])))
    assert report.status is ResultStatus.SUBMITTED, report.detail
    review_task(engine, rtl, ModelRuntime(MockLLM()))
    engine.approve(rtl, human(engine.task(rtl).approver), "lint-clean and simulated")

    seat = tid(engine, "dft")
    task = engine.task(seat)
    assert task.status is TaskStatus.READY
    owner = human(task.owner)
    engine.start(seat, owner)
    source = next(engine.state.artifacts[a] for a in engine.task(rtl).artifacts
                  if engine.state.artifacts[a].kind == "rtl_source")
    assert source.assurance is Assurance.APPROVED
    broker = ToolBroker(engine)

    def run(tool: str, sources: str, workdir: str):
        extra = {"min_test_coverage": "90"} if tool == "dft.atpg" else {}  # the stage's requirement (M27)
        done, outcome = broker.invoke(owner, tool, {"sources": sources, "top": "counter",
                                                    "workdir": str(tmp_path / workdir), **extra}, seat)
        engine.record_evidence(seat, owner, EvidenceKind.TOOL_RUN, done.summary,
                               reference=done.references[0], tool_run=done.id)
        return done, outcome

    _, outcome = run("dft.scan_insert", source.location, "insert")
    netlist = outcome.data["result"]["metrics"]["scan_netlist"]
    draft = [{"kind": "dft_netlist", "title": "Counter scan netlist", "location": netlist,
              "summary": "One mux-D chain of 4 flops."}]
    with pytest.raises(PolicyViolationError, match="cannot go to review"):
        engine.submit(seat, owner, draft)  # not checked yet

    # A broken netlist fails both checks; the failures are recorded, and it cannot be submitted.
    for tool in ("dft.check", "dft.scan_sim", "dft.atpg"):
        failed, _ = run(tool, str(BROKEN), f"broken-{tool}")
        assert not failed.succeeded
    with pytest.raises(PolicyViolationError, match="cannot go to review"):
        engine.submit(seat, owner, [{**draft[0], "location": str(BROKEN)}])

    for tool in ("dft.check", "dft.scan_sim", "dft.atpg"):
        passed, _ = run(tool, netlist, tool)
        assert passed.succeeded, passed.summary
    engine.submit(seat, owner, draft)
    task = engine.task(seat)
    assert task.status is TaskStatus.IN_REVIEW
    engine.review(seat, agent(task.reviewer), Verdict.APPROVE, "chain complete, shift and capture clean")
    assert engine.task(seat).review_state is ReviewState.PASSED
    engine.approve(seat, human(task.approver), "scan approved")
    task = engine.task(seat)
    assert task.status is TaskStatus.COMPLETED
    assert engine.state.artifacts[task.artifacts[0]].location == netlist


# --- Crown jewel: a new rule needs no core changes -----------------------------------------------


@needs("yosys")
def test_a_new_dft_rule_needs_no_core_changes(engine, tmp_path):
    """A rule the core has never heard of: every flop must have an asynchronous reset."""

    def async_reset(design) -> list[str]:
        return [f"flop {f.name} has no asynchronous reset" for f in design.flops if f.reset is None]

    register_rule(DftRule("async-reset-everywhere", "Every flop has an asynchronous reset.", async_reset))
    try:
        assert "async-reset-everywhere" in [r.id for r in rules()]
        run, outcome = invoke(engine, "dft.check", {"sources": str(COUNTER), "top": "counter"}, tmp_path / "w1")
        assert not run.succeeded
        assert {d["code"] for d in outcome.data["result"]["diagnostics"]} == {"async-reset-everywhere"}
        assert "flop count[0] has no asynchronous reset" in run.summary
    finally:
        unregister_rule("async-reset-everywhere")
    run, _ = invoke(engine, "dft.check", {"sources": str(COUNTER), "top": "counter"}, tmp_path / "w2")
    assert run.succeeded, run.summary

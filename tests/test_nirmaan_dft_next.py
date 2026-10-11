"""Milestone 29 (DFT): transition-fault ATPG, lockup latches across clock domains, and an MBIST stage.

* The lockup stitcher, the tracer's crossing rules, and the two-frame
  transition model are tested on hand-written netlists, with no tool installed.
* Real-tool tests run Yosys and Icarus and skip when an executable is absent
  (or fail when CI names it in NIRMAAN_REQUIRE_EDA).
* Transition coverage is what the Icarus fault simulation measured; a pattern
  pair the simulation does not bear out is refused.
* Crown jewel: a new transition-fault backend needs zero core changes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from nirmaan_helpers import agent, drive, human, tid
from test_nirmaan_dft import COUNTER, RTL, _cell, _netlist, holder, invoke
from test_nirmaan_dft_advanced import ATPG_DEMO, BLOCKS, RAM, TWO_CLOCKS, _flops, insert
from laws import needs

from nirmaan.integrations.dft_atpg import build_model
from nirmaan.integrations.dft_scan import Design, stitch
from nirmaan.models import Assurance, TaskStatus, ToolStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import MockLLM, ModelRuntime, ResultStatus, ToolAccessDenied, ToolBroker, review_task, run_task

MBIST = RTL / "mbist"
RAM_2CYCLE = MBIST / "sync_ram_2cycle.v"
RAM_BLOCK = MBIST / "ram_block.v"
BLOCK_RAM = MBIST / "block_ram.v"
RAM_BLOCK_TB = MBIST / "ram_block_tb.v"
MEMORY_BLOCK = "Create a register file backed by a synchronous RAM."


@pytest.fixture()
def engine(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-bit wrapping counter with scan chains.")


def transition(engine, sources: str, top: str, workdir: Path, **params: str):
    run, outcome = invoke(engine, "dft.atpg_transition", {"sources": sources, "top": top, **params}, workdir)
    return run, outcome.data["result"]["metrics"] if outcome.data else {}


# --- Hand-written netlists (no tool needed) --------------------------------------------------


def _expand(netlist: dict) -> dict:
    """Expand each scan cell by hand into a mux in front of the plain flop: D' = SE ? SI : D."""
    module = netlist["modules"]["top"]
    for name, cell in list(module["cells"].items()):
        if cell["type"].startswith("$__NIRMAAN_SCAN"):
            mux = 1000 + int(name[1:])
            conns = cell["connections"]
            module["cells"][f"m{name}"] = _cell("$_MUX_", A=conns["D"][0], B=conns["SI"][0], S=conns["SE"][0], Y=mux)
            cell["type"] = "$_DFF_" + cell["type"].rsplit("_DFF_", 1)[1]
            cell["connections"] = {"C": conns["C"], "D": [mux], "Q": conns["Q"]}
    return netlist


def test_lockup_stitching_crosses_domains_with_a_latch_at_each_crossing():
    netlist, report = stitch(_flops(4, clocks=(2, 4)), "top", cross=True)
    assert [c["order"] for c in report["chains"]] == [["q[0]", "q[2]", "q[1]", "q[3]"]]
    assert len(report["lockups"]) == 1
    lockup = report["lockups"][0]
    assert (lockup["from"], lockup["to"], lockup["clock"], lockup["type"]) == ("q[2]", "q[1]", "clk0", "$_DLATCH_N_")
    cells = netlist["modules"]["top"]["cells"]
    latch = cells[lockup["cell"]]
    assert latch["connections"]["E"] == [2] and latch["connections"]["D"] == [12]
    assert cells["f1"]["connections"]["SI"] == latch["connections"]["Q"]
    # Without cross, M27's chains per domain are unchanged and need no latch.
    _, plain = stitch(_flops(4, clocks=(2, 4)), "top")
    assert len(plain["chains"]) == 2 and plain["lockups"] == []


def test_the_tracer_follows_lockups_and_catches_a_crossing_without_one():
    netlist, report = stitch(_flops(4, clocks=(2, 4)), "top", cross=True)
    expanded = _expand(netlist)
    design = Design.from_json(expanded, "top")
    assert [lk.cell for lk in design.lockups] == [report["lockups"][0]["cell"]] and not design.latches
    chain = design.trace_chain()
    assert chain.complete, chain.problems
    assert [f.name for f in chain.order] == ["q[0]", "q[2]", "q[1]", "q[3]"]
    # Bypass the latch: q[1]'s scan mux takes q[2] directly.
    module = expanded["modules"]["top"]
    module["cells"]["mf1"]["connections"]["B"] = [12]
    del module["cells"][report["lockups"][0]["cell"]]
    broken = Design.from_json(expanded, "top").trace_chain()
    assert not broken.complete
    assert not broken.problems and broken.hazards  # still one whole chain, but its shift is not safe
    assert any("q[2] -> q[1]" in p and "no lockup latch" in p for p in broken.hazards), broken.hazards


def test_a_second_edge_flop_must_not_load_a_first_edge_flop():
    """One clock, both edges: q[0] rises, q[1] falls. Loading q[1] from q[0] races in one pulse."""
    cells = {"f0": _cell("$_DFF_P_", C=2, D=3, Q=10), "f1": _cell("$_DFF_N_", C=2, D=3, Q=11)}
    ports = {"clk": {"direction": "input", "bits": [2]}, "d": {"direction": "input", "bits": [3]},
             "q": {"direction": "output", "bits": [10, 11]}}
    netlist, report = stitch(_netlist(cells, ports, {"clk": [2], "d": [3], "q": [10, 11]}), "top", cross=True)
    assert report["chains"][0]["order"] == ["q[1]", "q[0]"] and report["lockups"] == []  # second edge first
    assert Design.from_json(_expand(netlist), "top").trace_chain().complete
    wrong = _expand(netlist)  # reverse the order by hand: q[0] first, q[1] loads it
    module = wrong["modules"]["top"]
    si = module["ports"]["scan_in"]["bits"][0]
    module["cells"]["mf0"]["connections"]["B"] = [si]
    module["cells"]["mf1"]["connections"]["B"] = [10]
    module["ports"]["scan_out"]["bits"] = [11]
    problems = Design.from_json(wrong, "top").trace_chain().hazards
    assert any("captures earlier in the same pulse" in p for p in problems), problems


def _launch_capture_design() -> Design:
    """q0 loads input a; q1 loads q0 & a; output y is q1. clk=2, a=3, q0=4, q1=5."""
    cells = {"f0": _cell("$_DFF_P_", C=2, D=3, Q=4), "f1": _cell("$_DFF_P_", C=2, D=6, Q=5),
             "g": _cell("$_AND_", A=4, B=3, Y=6)}
    ports = {"clk": {"direction": "input", "bits": [2]}, "a": {"direction": "input", "bits": [3]},
             "y": {"direction": "output", "bits": [5]}}
    return Design.from_json(_netlist(cells, ports, {"clk": [2], "a": [3], "q0": [4], "q1": [5], "t": [6]}), "top")


def test_transition_faults_are_two_frame_stuck_at_faults_with_a_launch_condition():
    model, faults = build_model(_launch_capture_design(), fault_model="transition")
    by_name = {f.name: f for f in faults}
    assert sorted(by_name) == sorted(f"{n}/{k}" for n in ("a", "q0", "q1", "t") for k in ("STR", "STF"))
    # A primary input is held through launch and capture: its transitions are proven untestable.
    assert model.podem(by_name["a/STR"]) == ("untestable", None)
    # q0 rises at launch when it was 0 and a is 1; held at 0 it makes q1 capture 0 instead of 1.
    status, pattern = model.podem(by_name["q0/STR"])
    assert status == "detected" and model.detects(pattern, by_name["q0/STR"])
    assert pattern[model.index[4]] == 0 and pattern[model.index[3]] == 1
    # The launch condition is checked: with q0 already 1 there is no transition to delay.
    assert not model.detects({**pattern, model.index[4]: 1}, by_name["q0/STR"])


def test_the_stuck_at_model_covers_both_capture_edges():
    """Stuck-at over two capture edges: a fault is a fault on both copies of its net."""
    cells = {"f0": _cell("$_DFF_P_", C=2, D=3, Q=4), "f1": _cell("$_DFF_N_", C=2, D=6, Q=5),
             "g": _cell("$_NOT_", A=4, Y=6)}
    ports = {"clk": {"direction": "input", "bits": [2]}, "a": {"direction": "input", "bits": [3]},
             "y": {"direction": "output", "bits": [5]}}
    design = Design.from_json(_netlist(cells, ports, {"clk": [2], "a": [3], "q0": [4], "q1": [5], "t": [6]}),
                              "top")
    model, faults = build_model(design)
    by_name = {f.name: f for f in faults}
    # q1 (falling edge) captures ~q0 after q0 (rising edge) took a: so q1 sees ~a, not ~(loaded q0).
    status, pattern = model.podem(by_name["a/SA0"])
    assert status == "detected" and pattern[model.index[3]] == 1
    assert by_name["t/SA1"].extra, "the stuck-at fault on t sits on both of its copies"


# --- Refusal and data --------------------------------------------------------------------------


def test_the_transition_tool_is_available_and_refused_without_its_executables(engine, tmp_path, monkeypatch):
    assert engine.org.tools["dft.atpg_transition"].status is ToolStatus.AVAILABLE
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ToolAccessDenied, match="needs yosys, iverilog, vvp.*not found"):
        invoke(engine, "dft.atpg_transition", {"sources": str(COUNTER), "top": "counter"}, tmp_path)
    assert engine.state.tool_runs == {}


def test_the_seat_data_names_the_new_tool_stage_and_checks(nirmaan_org, fixed_clock):
    skills = nirmaan_org.skills
    for skill in ("atpg", "fault_modeling", "scan_design"):
        assert "dft.atpg_transition" in skills[skill].tools, skill
    at_speed = Orchestrator(nirmaan_org, clock=fixed_clock).plan(
        "Create a 4-bit wrapping counter with scan chains and at-speed test.")
    dft = at_speed.task(tid(at_speed, "dft"))
    gated = {t: r for r in dft.evidence_requirements if r.before_review for t in r.tools}
    assert sorted(gated) == ["dft.atpg", "dft.atpg_transition", "dft.check", "dft.scan_sim"]
    assert dict(gated["dft.atpg_transition"].params) == {"min_test_coverage": "80"}
    plain = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-bit wrapping counter with scan chains.")
    plain_dft = plain.task(tid(plain, "dft"))
    assert "dft.atpg_transition" not in {t for r in plain_dft.evidence_requirements for t in r.tools}


def test_the_mbist_stage_is_planned_for_a_block_with_memory(nirmaan_org, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(MEMORY_BLOCK)
    stages = [t.stage for t in engine.state.tasks.values() if t.stage]
    assert stages == ["requirements", "interface-spec", "microarchitecture", "rtl-implementation", "mbist"]
    task = engine.task(tid(engine, "mbist"))
    assert task.capability == "dft.mbist" and task.expected_outputs == ("mbist_configuration",)
    assert task.owner.startswith("implementation.dft.")
    (gate,) = [r for r in task.evidence_requirements if r.before_review]
    assert gate.tools == ("dft.mbist",) and gate.files[0].upstream and gate.files[0].kinds == ("rtl_source",)
    plain = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create a 4-bit wrapping counter.")
    assert "mbist" not in [t.stage for t in plain.state.tasks.values()]


# --- Real tools: transition ATPG -----------------------------------------------------------------


@needs("yosys", "iverilog", "vvp")
@pytest.mark.parametrize("block,chains,floor", [("counter", "1", 80.0), ("atpg_demo", "2", 80.0),
                                                ("rr_arbiter", "2", 80.0)])
def test_real_transition_coverage_is_measured_by_fault_simulation(engine, tmp_path, block, chains, floor):
    source, top = (ATPG_DEMO, "atpg_demo") if block == "atpg_demo" else BLOCKS[block]
    scan = insert(engine, source, top, tmp_path / "insert", chains=chains)["scan_netlist"]
    run, metrics = transition(engine, scan, top, tmp_path / "atpg", min_test_coverage=str(floor))
    assert run.succeeded, run.summary
    total = metrics["faults_total"]
    assert total == metrics["faults_detected"] + metrics["faults_undetectable"] + metrics["faults_undetected"]
    assert metrics["claims_not_detected"] == 0 and metrics["response_errors"] == metrics["injection_errors"] == 0
    assert metrics["fault_model"] == "transition" and metrics["test_coverage"] >= floor
    assert "transition faults detected in fault simulation" in run.summary and "launch on capture" in run.summary
    faults = {f["name"]: f for f in metrics["fault_list"]}
    assert all(n.endswith(("/STR", "/STF")) for n in faults) and total == 2 * len({n[:-4] for n in faults})
    log = Path(run.references[0]).read_text()
    assert log.count("DFT-FAULT ") == total and "DFT-ATPG-CHECK: " in log
    print(f"{block}: {metrics['faults_detected']}/{total} transition faults detected, "
          f"{metrics['faults_undetectable']} proven undetectable, test coverage {metrics['test_coverage']}%")


@needs("yosys", "iverilog", "vvp")
def test_a_broken_pattern_pair_is_refused(engine, tmp_path):
    scan = insert(engine, COUNTER, "counter", tmp_path / "insert")["scan_netlist"]
    run, metrics = transition(engine, scan, "counter", tmp_path / "atpg")
    assert run.succeeded, run.summary
    pi_faults = [f["name"] for f in metrics["fault_list"] if f["class"] == "undetectable"]
    assert "en/STR" in pi_faults and "rst/STF" in pi_faults
    patterns = json.loads((tmp_path / "atpg" / "patterns.json").read_text())
    assert patterns["fault_model"] == "transition" and patterns["protocol"] == "launch-on-capture"

    def grade(name: str, doc: dict):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(doc))
        return transition(engine, scan, "counter", tmp_path / name, patterns=str(path))

    # 1. A wrong capture response: one unloaded bit of the second frame flipped.
    wrong = json.loads(json.dumps(patterns))
    bits = wrong["patterns"][0]["unload"][0]
    wrong["patterns"][0]["unload"][0] = ("1" if bits[0] == "0" else "0") + bits[1:]
    graded, m = grade("wrong_capture", wrong)
    assert not graded.succeeded and m["response_errors"] >= 1 and "expected responses" in graded.summary

    # 2. A wrong launch: every load inverted, the expected captures kept, so the pairs no longer fit.
    pair = json.loads(json.dumps(patterns))
    for entry in pair["patterns"]:
        entry["load"] = ["".join("1" if b == "0" else "0" for b in chain) for chain in entry["load"]]
    graded, m = grade("wrong_launch", pair)
    assert not graded.succeeded and m["response_errors"] >= 1

    # 3. A false claim: a primary-input transition, which no launch-on-capture pair can detect.
    graded, _ = grade("false_claim", {**patterns, "claims": {**patterns["claims"], "en/STR": 0}})
    assert not graded.succeeded and "en/STR" in graded.summary and "did not detect" in graded.summary

    # 4. A stuck-at pattern file is not a transition pattern file.
    stuck = json.loads(json.dumps(patterns))
    stuck["fault_model"] = "stuck-at"
    graded, _ = grade("stuck_file", stuck)
    assert not graded.succeeded and "fault model" in graded.summary

    # 5. The file as generated grades clean.
    graded, _ = grade("clean", patterns)
    assert graded.succeeded, graded.summary


@needs("yosys", "iverilog", "vvp")
def test_atpg_runs_across_capture_edges_and_transition_atpg_refuses_them(engine, tmp_path):
    scan = insert(engine, TWO_CLOCKS, "two_clocks", tmp_path / "insert")["scan_netlist"]
    run, outcome = invoke(engine, "dft.atpg", {"sources": scan, "top": "two_clocks", "min_test_coverage": "90"},
                          tmp_path / "atpg")
    assert run.succeeded, run.summary
    metrics = outcome.data["result"]["metrics"]
    assert metrics["claims_not_detected"] == 0 and metrics["response_errors"] == 0
    refused, _ = transition(engine, scan, "two_clocks", tmp_path / "transition")
    assert not refused.succeeded and "both edges" in refused.summary


# --- Real tools: lockup latches ----------------------------------------------------------------


def _without_lockups(scan: Path, out: Path) -> int:
    """The same scan netlist with each lockup latch turned into a plain wire."""
    text = scan.read_text()
    edited, count = re.subn(r"if \(!?\\?[\w$]+ ?\) (nirmaan_lockup_\d+) (<?=)", r"\1 \2", text)
    out.write_text(edited)
    return count


@needs("yosys", "iverilog", "vvp")
def test_a_chain_across_clock_domains_shifts_through_its_lockups(engine, tmp_path):
    metrics = insert(engine, TWO_CLOCKS, "two_clocks", tmp_path / "insert", cross_domains="lockup")
    assert metrics["chains"] == 1 and metrics["lockups"] >= 1
    report = json.loads(Path(metrics["chain_report"]).read_text())
    assert report["chains"][0]["order"][:4] == ["c[0]", "c[1]", "c[2]", "c[3]"]  # the falling edge first
    params = {"sources": metrics["scan_netlist"], "top": "two_clocks"}
    check, _ = invoke(engine, "dft.check", params, tmp_path / "check")
    assert check.succeeded, check.summary
    sim, outcome = invoke(engine, "dft.scan_sim", params, tmp_path / "sim")
    assert sim.succeeded, sim.summary
    assert "skewed clocks" in sim.summary and outcome.data["result"]["metrics"]["skew_passes"] == 2
    atpg, outcome = invoke(engine, "dft.atpg", params, tmp_path / "atpg")
    assert atpg.succeeded, atpg.summary

    # The same chain without its lockups: caught by the rule check and by the skewed shift.
    bare = tmp_path / "no_lockup.v"
    assert _without_lockups(Path(metrics["scan_netlist"]), bare) == metrics["lockups"]
    params = {"sources": str(bare), "top": "two_clocks"}
    check, outcome = invoke(engine, "dft.check", params, tmp_path / "check2")
    assert not check.succeeded and "no lockup latch" in check.summary
    sim, outcome = invoke(engine, "dft.scan_sim", params, tmp_path / "sim2")
    assert not sim.succeeded and "no lockup latch" in sim.summary
    # The simulation alone also sees it: generate the testbench as if the tracer allowed the crossing.
    from nirmaan.integrations.dft_scan import Design as D, testbench

    design_json = tmp_path / "sim2" / "design.json"
    tb, _ = testbench(D.load(design_json, "two_clocks"), strict=False)
    (tmp_path / "tb.v").write_text(tb)
    sim, outcome = invoke(engine, "simulator.run", {"sources": f"{bare},{tmp_path / 'tb.v'}",
                                                    "top": "nirmaan_scan_tb"}, tmp_path / "sim3")
    assert not sim.succeeded, sim.summary


# --- Real tools: MBIST -------------------------------------------------------------------------


def mbist(engine, source: str, workdir: Path, top: str | None = None):
    params = {"sources": source, **({"top": top} if top else {})}
    run, outcome = invoke(engine, "dft.mbist", params, workdir)
    return run, outcome.data["result"]["metrics"] if outcome.data else {}


@needs("yosys", "iverilog", "vvp", "verilator")
def test_march_c_minus_on_a_two_cycle_ram(engine, tmp_path):
    run, metrics = mbist(engine, str(RAM_2CYCLE), tmp_path / "mbist", "sync_ram_2cycle")
    assert run.succeeded, run.summary
    assert (metrics["depth"], metrics["width"], metrics["read_latency"]) == (32, 16, 2)
    assert metrics["measured_latency"] == 2 and metrics["cycles"] == (10 + 5 * 2) * 32
    lint, _ = invoke(engine, "lint.run", {"sources": metrics["controller"]}, tmp_path / "lint")
    assert lint.succeeded, lint.summary
    faulty, metrics = mbist(engine, str(RAM_2CYCLE), tmp_path / "faulty", "ram_2cycle_stuck_at_1")
    assert not faulty.succeeded and "March C- failed on ram_2cycle_stuck_at_1" in faulty.summary


@needs("yosys", "iverilog", "vvp")
def test_a_declared_read_latency_is_measured_not_trusted(engine, tmp_path):
    wrong = tmp_path / "wrong_latency.v"
    wrong.write_text(RAM.read_text().replace("module sync_ram", "(* read_latency = 2 *)\nmodule sync_ram"))
    run, metrics = mbist(engine, str(wrong), tmp_path / "mbist", "sync_ram")
    assert not run.succeeded and "declares a read latency of 2" in run.summary and "measured 1" in run.summary


@needs("yosys", "iverilog", "vvp")
def test_mbist_finds_the_memories_in_a_hierarchy(engine, tmp_path):
    run, metrics = mbist(engine, f"{RAM_BLOCK},{BLOCK_RAM}", tmp_path / "mbist")
    assert run.succeeded, run.summary
    assert [m["module"] for m in metrics["memories"]] == ["block_ram"] and "block_ram" in run.summary
    none, _ = mbist(engine, str(COUNTER), tmp_path / "none", "counter")
    assert not none.succeeded and "no memory" in none.summary


# --- The MBIST stage gates review --------------------------------------------------------------


def _ram_block_answer(engine, faulty: bool) -> str:
    from test_nirmaan_design_agents import answer, file, token, upstream

    cite = token(upstream(engine, "microarchitecture"))
    ram = BLOCK_RAM.read_text()
    if faulty:  # bit 3 of word 5 stuck at 0: invisible to the block's own testbench
        ram = ram.replace("mem[addr] <= wdata;", "mem[addr] <= (addr == 4'd5) ? (wdata & 8'hF7) : wdata;")
        assert "8'hF7" in ram
    return answer(file("ram_block.v", "rtl_source", RAM_BLOCK.read_text(), cite, entry="ram_block"),
                  file("block_ram.v", "rtl_source", ram, cite),
                  file("ram_block_tb.v", "testbench", RAM_BLOCK_TB.read_text(), cite, entry="ram_block_tb"))


@needs("verilator", "yosys", "iverilog", "vvp")
@pytest.mark.parametrize("faulty", [False, True], ids=["clean", "faulty"])
def test_the_mbist_stage_gates_review_on_the_memories_of_the_approved_rtl(nirmaan_org, fixed_clock, tmp_path,
                                                                          faulty):
    from test_nirmaan_design_agents import answer, file, token, upstream, with_workspace

    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(MEMORY_BLOCK)
    rtl = tid(engine, "rtl-implementation")
    drive(engine, until=rtl)
    with_workspace(engine, rtl, tmp_path / "rtl")
    report = run_task(engine, rtl, ModelRuntime(MockLLM(script=[_ram_block_answer(engine, faulty)])))
    assert report.status is ResultStatus.SUBMITTED, report.detail  # the block's own gates pass either way
    review_task(engine, rtl, ModelRuntime(MockLLM()))
    engine.approve(rtl, human(engine.task(rtl).approver), "lint-clean, simulated, synthesized")
    assert all(engine.state.artifacts[a].assurance is Assurance.APPROVED for a in engine.task(rtl).artifacts)

    seat = tid(engine, "mbist")
    assert engine.task(seat).status is TaskStatus.READY
    with_workspace(engine, seat, tmp_path / "mbist")
    plan = file("mbist_plan.md", "mbist_configuration",
                "# MBIST\n\nMarch C- on every single-port RAM in the approved RTL.\n",
                token(next(a for a in engine.task(rtl).artifacts
                           if engine.state.artifacts[a].kind == "rtl_source")))
    report = run_task(engine, seat, ModelRuntime(MockLLM(script=[answer(plan)])))
    runs = [r for r in engine.state.tool_runs.values() if r.tool == "dft.mbist"]
    assert len(runs) == 1 and "block_ram" in runs[0].summary
    if faulty:
        assert report.status is ResultStatus.REFUSED and not runs[0].succeeded
        assert "March C- failed on block_ram" in runs[0].summary
        assert engine.task(seat).status is not TaskStatus.IN_REVIEW
    else:
        assert report.status is ResultStatus.SUBMITTED, report.detail
        assert runs[0].succeeded and engine.task(seat).status is TaskStatus.IN_REVIEW


# --- Crown jewel: a new transition-fault backend needs no core changes ---------------------------


@needs("yosys", "iverilog", "vvp")
def test_a_new_transition_backend_needs_no_core_changes(engine, tmp_path):
    """A generator the core has never seen: random pattern pairs only, graded by the same fault simulation."""
    from nirmaan.integrations import dft
    from nirmaan.integrations.eda import Backend, register_backend, unregister_backend

    def steps(job):
        return [*dft.atpg_analysis_steps(job),
                dft.atpg_helper("generate", dft.DESIGN_JSON, dft.PATTERNS, str(job.top), "--random-only",
                                "--model", "transition"),
                *dft.atpg_grading_steps(job, dft.PATTERNS, "transition")]

    register_backend(Backend("random-transition", "dft.atpg_transition", ("yosys", "iverilog", "vvp"), steps,
                             dft.parse_atpg, ("sources", "top")))
    try:
        scan = insert(engine, COUNTER, "counter", tmp_path / "insert")["scan_netlist"]
        run, metrics = transition(engine, scan, "counter", tmp_path / "atpg", backend="random-transition")
        assert run.succeeded and run.summary.startswith("random-transition: "), run.summary
        assert metrics["faults_detected"] > 0 and metrics["claims_not_detected"] == 0
    finally:
        unregister_backend("dft.atpg_transition", "random-transition")
    with pytest.raises(ToolAccessDenied, match="no backend named 'random-transition'"):
        ToolBroker(engine).invoke(agent(holder(engine, "dft.atpg_transition")), "dft.atpg_transition",
                                  {"sources": str(COUNTER), "top": "counter", "backend": "random-transition",
                                   "workdir": str(tmp_path / "gone")})

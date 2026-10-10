"""Milestones 25, 27, and 29 (physical design): OpenSTA and OpenROAD behind the broker.

* Parsers are tested against logs CAPTURED from real OpenROAD runs in CI
  (M27; each starts with a ``# CAPTURED:`` line naming the run).
* A missing executable or a missing PDK input is a refusal with a reason, and
  no run is recorded. Design-input problems, tool failures, and timeouts are
  recorded failed runs.
* Liberty-mapped synthesis (the netlist STA and place-and-route consume) runs
  for real with Yosys and a toy test library.
* The physical-implementation workflow plans synth, floorplan, place and
  route, then STA signoff.
* Crown jewels: a new physical-design backend needs zero core changes; signoff
  timing on extracted parasitics is a limit in the workflow data (M29).
* M29: power grid, taps, CTS, repair, fillers, antenna and IR checks, and
  OpenRCX extraction, for real on Nangate45 and sky130hd in CI, with signoff
  STA on the SPEF through OpenROAD's OpenSTA and standalone OpenSTA.
* M34: timing corners (slow, typical, fast sky130hd Liberty), metal fill, and
  DRC and LVS with the PDK's KLayout decks (``pv.run``), for real on sky130hd
  in CI, with a broken layout and a broken netlist failing as recorded runs.
* Real OpenSTA and OpenROAD tests skip without the tools and Nangate45; the CI
  physical-design job requires them.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import agent, tid
from test_nirmaan_eda import holder
from laws import needs

from nirmaan.integrations.eda import Backend, EdaResult, register_backend, unregister_backend
from nirmaan.integrations.pd_parsers import VIOLATOR_REPORT_LIMIT, parse_klayout, parse_openroad, parse_opensta
from nirmaan.integrations.physical import PDK_ROOT_ENV, needs_pdk
from nirmaan.models import EvidenceKind, TaskKind, ToolStatus
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ToolAccessDenied, ToolBroker, available_bindings, unavailable_reason
from nirmaan.work.policy import unsatisfied_requirements

FIXTURES = Path(__file__).parent / "fixtures"
PD = FIXTURES / "pd"
AXI = FIXTURES / "rtl" / "axi4_lite" / "axi4_lite_regs.v"
TOP = "axi4_lite_regs"
SDC = PD / "axi4_lite_regs.sdc"
TINY_LIB = PD / "tiny_cells.lib"
PNR_REQUEST = "Place and route the AXI4-Lite register block."
PNR_PDK = {"site": "unithd", "hor_layers": "met3", "ver_layers": "met2"}


def _text(name: str) -> str:
    return (PD / name).read_text(encoding="utf-8")


@pytest.fixture()
def project(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(PNR_REQUEST)


def invoke(engine, tool: str, params: dict[str, str], workdir: Path, task: str | None = None):
    return ToolBroker(engine).invoke(agent(holder(engine, tool)), tool, {"workdir": str(workdir), **params}, task)


def fake_tool(bin_dir: Path, name: str, body: str) -> Path:
    """A stand-in executable the test writes: it exercises the runner, and never stands in for evidence of a real tool."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe = bin_dir / name
    exe.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    exe.chmod(0o755)
    return exe


def only_on_path(monkeypatch, bin_dir: Path) -> None:
    """PATH holds the test's stand-ins and the shell utilities they use, nothing else."""
    monkeypatch.setenv("PATH", f"{bin_dir}:{Path(shutil.which('sh')).parent}")


def fake_pdk(root: Path, rc: bool = False) -> dict[str, str]:
    """Stand-in PDK files; ``rc`` adds the layer RC script place and route needs from CTS on (M29)."""
    root.mkdir(parents=True, exist_ok=True)
    for name in ("cells.lib", "tech.lef", "cells.lef", "rc.tcl"):
        (root / name).write_text("stand-in\n", encoding="utf-8")
    pdk = {"liberty": str(root / "cells.lib"), "tech_lef": str(root / "tech.lef"), "lef": str(root / "cells.lef")}
    return {**pdk, "rc_tcl": str(root / "rc.tcl")} if rc else pdk


# --- The catalog ------------------------------------------------------------------------


def test_sta_and_pnr_have_real_bindings(nirmaan_org):
    for tool in ("sta.run", "pnr.run", "pv.run"):  # M34: physical verification through KLayout
        assert nirmaan_org.tools[tool].status is ToolStatus.AVAILABLE, tool
        assert tool in available_bindings(), tool


def test_the_catalog_says_why_a_tool_cannot_run_here(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    reason = unavailable_reason("sta.run")
    assert "opensta needs sta on PATH, not found" in reason and "never simulated" in reason
    assert "openroad needs openroad" in unavailable_reason("pnr.run")
    assert unavailable_reason("status.read") is None  # a platform tool always runs

    from nirmaan.cli import app

    result = CliRunner().invoke(app, ["org", "tools"], env={"COLUMNS": "400"})
    assert result.exit_code == 0, result.output
    line = next(ln for ln in result.output.splitlines() if "sta.run" in ln)
    assert "no:" in line and "opensta needs sta" in line


# --- Parsers, against logs captured from real runs ----------------------------------------


def test_the_logs_say_where_they_were_captured():
    logs = sorted(PD.glob("*.log"))
    assert [p.name for p in logs] == ["klayout_pv.log", "klayout_pv_drc.log", "klayout_pv_lvs.log",  # M34
                                      "openroad_error.log", "openroad_route.log", "openroad_signoff.log",
                                      "openroad_sky130_fill.log", "opensta_corners.log", "opensta_met.log",
                                      "opensta_spef.log", "opensta_violated.log"]
    for log in logs:
        first, second = log.read_text(encoding="utf-8").splitlines()[:2]
        assert first.startswith("# CAPTURED:") and "CI run" in first, log
        # M29: standalone OpenSTA, built in CI. M34: pv.run's first step writes the CDL in OpenROAD.
        exe = "sta" if log.name in ("opensta_spef.log", "opensta_corners.log") else "openroad"
        assert second.startswith(f"$ {exe} -no_init -no_splash -exit "), log  # as eda.execute logs a step


def test_opensta_timing_met():
    result = parse_opensta(_text("opensta_met.log"), 0)
    assert result.passed, result.summary
    m = result.metrics
    assert (m["worst_slack"], m["worst_hold_slack"], m["tns"], m["wns"]) == (7.264, 0.101, 0.0, 0.0)
    assert m["violating_endpoints"] == [] and result.diagnostics == ()
    assert result.summary == "timing met: worst setup slack 7.264, worst hold slack 0.101, TNS 0.000"


def test_opensta_timing_violated():
    result = parse_opensta(_text("opensta_violated.log"), 0)
    assert not result.passed
    m = result.metrics
    assert (m["worst_slack"], m["worst_hold_slack"], m["tns"], m["wns"]) == (-0.905, 0.06, -157.481, -0.905)
    violators = m["violating_endpoints"]
    assert len(violators) == VIOLATOR_REPORT_LIMIT and {v["check"] for v in violators} == {"setup"}
    assert violators[0] == {"endpoint": "_1600_", "check": "setup", "slack": -0.905}
    assert not result.errors
    assert result.summary == ("timing violated: at least 100 violating endpoints, worst setup slack -0.905, "
                              "worst hold slack 0.060, TNS -157.481; worst: _1600_ (setup) -0.905")


def test_opensta_unconstrained_or_crashed_is_not_timing_met():
    for unconstrained in ("No paths found.\nworst slack INF\nworst slack INF\ntns 0.000\nwns 0.000\n",
                          "No paths found.\nworst slack max INF\nworst slack min INF\ntns max 0.000\n"):
        result = parse_opensta(unconstrained, 0)
        assert not result.passed and "no constrained timing paths" in result.summary
    crashed = parse_opensta("Error: sta.tcl, 2 cannot read file netlist.v\n", 1)
    assert not crashed.passed and crashed.errors[0].message == "sta.tcl, 2 cannot read file netlist.v"
    assert "1 error" in crashed.summary
    orstyle = parse_opensta("[ERROR ORD-2010] no technology has been read.\n", 1)  # as M27's first run printed
    assert orstyle.errors[0].code == "ORD-2010"


def test_openroad_full_flow():
    result = parse_openroad(_text("openroad_route.log"), 0, "route")
    assert result.passed, result.summary
    m = result.metrics
    assert m["stages_completed"] == ["floorplan", "place", "cts", "route", "timing"] and m["failed_stage"] is None
    assert (m["design_area_um2"], m["utilization_pct"]) == (2127.0, 43.0)  # printed as um^2
    assert (m["wirelength_um"], m["drc_violations"]) == (12645.0, 0)  # the last iteration's figures
    assert (m["worst_slack"], m["worst_hold_slack"]) == (7.422, 0.158)
    # M29: the clock tree, and slack at each checkpoint (ideal clock, propagated, global-routing estimate).
    assert (m["cts_buffers"], m["cts_sinks"], m["clock_skew"], m["clock_insertion_delay"]) == (17, 206, -0.005, 0.115)
    assert m["slack_by_stage"] == {"place": {"setup": 7.458, "hold": 0.151, "tns": 0.0},
                                   "cts": {"setup": 7.446, "hold": 0.156, "tns": 0.0},
                                   "route": {"setup": 7.422, "hold": 0.158, "tns": 0.0}}
    # No power grid was asked for: the supply pins stay open, and the summary says so instead of failing.
    assert m["power_grids"] == [] and m["unconnected_supply_pins"] == 2762 and m["parasitics"] == "estimated"
    assert [d.code for d in result.warnings] == ["IFP-0028"]
    assert result.summary == ("place and route passed: routed, 0 DRC violations, wirelength 12645 um, "
                              "utilization 43%, no power grid, clock skew -0.005, worst setup slack 7.422, "
                              "worst hold slack 0.158, TNS 0.000")


SIGNOFF_STAGES = ["floorplan", "place", "cts", "route", "extract"]


def test_openroad_signoff_flow():
    """M29: taps, a connected power grid, CTS, fillers, antenna and IR checks, and extracted parasitics."""
    result = parse_openroad(_text("openroad_signoff.log"), 0, "extract", SIGNOFF_STAGES)
    assert result.passed, result.summary
    m = result.metrics
    assert m["stages_completed"] == [*SIGNOFF_STAGES, "timing"] and m["parasitics"] == "extracted"
    assert (m["tap_cells"], m["endcap_cells"], m["filler_cells"]) == (0, 100, 1494)  # taps every 120 um > the die
    assert m["power_grids"] == ["grid"] and m["supply_nets"] == ["VDD", "VSS"] and m["unconnected_supply_pins"] == 0
    assert m["worst_ir_drop_v"] == {"VDD": 0.00156, "VSS": 0.000588}
    assert (m["antenna_net_violations"], m["antenna_pin_violations"], m["drc_violations"]) == (0, 0, 0)
    assert (m["cts_buffers"], m["clock_skew"], m["clock_insertion_delay"]) == (17, 0.003, 0.111)
    assert m["slack_by_stage"]["route"] == {"setup": 7.435, "hold": 0.158, "tns": 0.0}  # global-routing estimate
    assert m["slack_by_stage"]["extract"] == {"setup": 7.449, "hold": 0.155, "tns": 0.0}  # extracted
    assert (m["worst_slack"], m["worst_hold_slack"]) == (7.449, 0.155)
    # Unused QNs and dummy loads drive nothing, and the supply ports reach no cell pin: no wire to extract.
    assert (m["unannotated_drivers"], m["floating_outputs"], m["unannotated_nets"]) == (219, 221, 0)
    assert result.summary == ("place and route passed: routed and extracted, 0 DRC violations, wirelength "
                              "12562 um, utilization 43%, power grid connected, clock skew 0.003, worst setup "
                              "slack 7.449, worst hold slack 0.155, TNS 0.000 on extracted parasitics")


def test_openroad_signoff_checks_fail_the_run():
    log = _text("openroad_signoff.log")
    for real, broken, reason in (
            ("nirmaan-unconnected-supply-pins: 0", "nirmaan-unconnected-supply-pins: 3", "3 unconnected supply pins"),
            ("Found 0 net violations.", "Found 2 net violations.", "2 antenna violations")):
        assert log.count(real) == 1
        result = parse_openroad(log.replace(real, broken), 0, "extract", SIGNOFF_STAGES)
        assert not result.passed and reason in result.summary, result.summary
    no_extract = "\n".join(ln for ln in log.splitlines() if "nirmaan-stage-done: extract" not in ln)
    assert not parse_openroad(no_extract, 0, "extract", SIGNOFF_STAGES).passed  # planned, never finished


def test_opensta_on_the_extracted_spef():
    result = parse_opensta(_text("opensta_spef.log"), 0)
    assert result.passed, result.summary
    m = result.metrics
    assert (m["worst_slack"], m["worst_hold_slack"], m["tns"]) == (7.449, 0.155, 0.0)  # the flow's extracted figures
    assert (m["unannotated_drivers"], m["floating_outputs"], m["unannotated_nets"]) == (221, 221, 0)
    # A listed driver that does drive a load is an unannotated net, counted by name.
    log = _text("opensta_spef.log")
    line = next(ln for ln in log.splitlines() if ln.startswith("nirmaan-floating-drivers:"))
    dropped = line.replace(" VDD", "")
    assert parse_opensta(log.replace(line, dropped), 0).metrics["unannotated_nets"] == 1


def test_opensta_reports_each_corner():
    """M34: slow, typical, and fast sky130hd Liberty on one extracted SPEF, through standalone OpenSTA."""
    result = parse_opensta(_text("opensta_corners.log"), 0)
    assert result.passed, result.summary
    m = result.metrics
    assert m["slack_by_corner"] == {"tt": {"setup": 4.428, "hold": 0.629}, "ss": {"setup": 1.276, "hold": 1.283},
                                    "ff": {"setup": 5.606, "hold": 0.399}}
    assert m["timing_corners"] == 3 and m["unannotated_nets"] == 0
    assert (m["worst_slack"], m["worst_hold_slack"]) == (1.276, 0.399)  # setup on ss, hold on ff
    assert result.summary == ("timing met: worst setup slack 1.276, worst hold slack 0.399, TNS 0.000 across 3 "
                              "corners (tt 4.428/0.629, ss 1.276/1.283, ff 5.606/0.399)")
    # A corner whose section reports no path does not count, and fails the run.
    log = _text("opensta_corners.log")
    ff = log[log.index("nirmaan-corner: ff"):log.index("nirmaan-corner-done: ff")]
    empty = parse_opensta(log.replace(ff, "nirmaan-corner: ff\nNo paths found.\n"), 0)
    assert not empty.passed and empty.metrics["timing_corners"] == 2 and "corner ff" in empty.summary
    assert parse_opensta(_text("opensta_met.log"), 0).metrics["timing_corners"] == 1  # one corner, as before


def test_openroad_reports_metal_fill():
    result = parse_openroad(_text("openroad_sky130_fill.log"), 0, "extract", SIGNOFF_STAGES)
    assert result.passed, result.summary
    m = result.metrics
    assert m["fill_shapes"] == 12947 and m["drc_violations"] == 0 and m["unconnected_supply_pins"] == 0
    assert (m["worst_slack"], m["worst_hold_slack"]) == (4.428, 0.629)
    assert "metal fill 12947 shapes" in result.summary
    assert parse_openroad(_text("openroad_signoff.log"), 0, "extract", SIGNOFF_STAGES).metrics["fill_shapes"] is None


def test_klayout_drc_and_lvs_clean():
    result = parse_klayout(_text("klayout_pv.log"), 0)
    assert result.passed, result.summary
    m = result.metrics
    assert (m["gds_empty_cells"], m["fill_shapes"], m["drc_violations"], m["lvs_mismatches"]) == (0, 12947, 0, 0)
    assert m["drc_by_rule"] == {} and m["lvs_unmatched_circuits"] == []
    assert not result.errors  # the deck's own "ERROR : ..." text is not a tool error; none here anyway
    assert result.summary == ("physical verification passed: GDS written with 12947 fill shapes, DRC clean, "
                              "LVS clean (layout matches the netlist)")


def test_klayout_broken_layout_and_netlist_fail():
    drc = parse_klayout(_text("klayout_pv_drc.log"), 0)
    assert not drc.passed and drc.metrics["drc_violations"] == 782 and drc.metrics["lvs_mismatches"] == 0
    assert list(drc.metrics["drc_by_rule"])[:3] == ["licon_OFFGRID", "li_OFFGRID", "poly_OFFGRID"]
    assert drc.summary == ("physical verification failed: 782 DRC violations (licon_OFFGRID 200, li_OFFGRID 172, "
                           "poly_OFFGRID 138)")
    lvs = parse_klayout(_text("klayout_pv_lvs.log"), 0)
    assert not lvs.passed and lvs.metrics["drc_violations"] == 0
    assert lvs.metrics["lvs_mismatched"] == {"circuits": 1, "nets": 2, "devices": 0, "pins": 0, "subcircuits": 1}
    assert lvs.metrics["lvs_unmatched_circuits"] == ["axi4_lite_regs"]
    assert "LVS mismatch: 1 mismatched circuit, 2 mismatched nets, 1 mismatched subcircuit" in lvs.summary
    # A check that ran and printed no count, or a stream that left a cell empty, fails.
    clean = _text("klayout_pv.log")
    no_lvs = "\n".join(ln for ln in clean.splitlines() if not ln.startswith("nirmaan-lvs-"))
    assert "no LVS comparison reported" in parse_klayout(no_lvs, 0).summary
    assert parse_klayout(no_lvs, 0, ["drc"]).passed  # DRC only: no LVS asked for
    empty = clean.replace("nirmaan-gds-empty-cells: 0", "nirmaan-gds-empty-cells: 1\nnirmaan-gds-empty-cell: X")
    assert "1 layout cell with no GDS (X)" in parse_klayout(empty, 0).summary
    crashed = parse_klayout(clean + "\nERROR: drc.lydrc:12: undefined method\n", 1)
    assert not crashed.passed and crashed.errors[-1].message == "drc.lydrc:12: undefined method"


def test_openroad_failure_names_the_stage():
    result = parse_openroad(_text("openroad_error.log"), 1, "route")
    assert not result.passed
    assert result.metrics["stages_completed"] == ["floorplan"] and result.metrics["failed_stage"] == "place"
    assert result.metrics["utilization_pct"] == 318.0
    assert result.errors[0].code == "GPL-0301" and "352.253" in result.errors[0].message
    assert "failed in place" in result.summary


def test_openroad_drc_violations_and_missing_stages_fail():
    route = _text("openroad_route.log")
    assert route.count("Number of violations = 0.") == 1
    drc = parse_openroad(route.replace("Number of violations = 0.", "Number of violations = 7."), 0, "route")
    assert not drc.passed and drc.metrics["drc_violations"] == 7 and "7 DRC violations" in drc.summary
    floorplan_only = "\n".join(ln for ln in route.splitlines()
                               if "stage" not in ln or "floorplan" in ln or "timing" in ln)
    assert parse_openroad(floorplan_only, 0, "floorplan").passed
    assert not parse_openroad(floorplan_only, 0, "route").passed  # route was asked for and never finished


# --- Refusal: a missing executable or PDK is never a run ----------------------------------


def test_a_missing_executable_is_a_refusal_with_a_reason(project, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    pdk = fake_pdk(tmp_path / "pdk")
    with pytest.raises(ToolAccessDenied, match="opensta needs sta on PATH, not found"):
        # OpenSTA reads the Liberty file only; the LEFs are OpenROAD's (M28 contracts refuse the rest).
        invoke(project, "sta.run", {"netlist": str(AXI), "sdc": str(SDC), "top": TOP, "liberty": pdk["liberty"]},
               tmp_path)
    with pytest.raises(ToolAccessDenied, match="openroad needs openroad on PATH, not found"):
        invoke(project, "pnr.run", {"netlist": str(AXI), "sdc": str(SDC), "top": TOP, **pdk, **PNR_PDK}, tmp_path)
    assert project.state.tool_runs == {}


def test_a_missing_pdk_is_a_refusal_with_a_reason(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "sta", "echo should never run; exit 1")
    fake_tool(bin_dir, "openroad", "echo should never run; exit 1")
    only_on_path(monkeypatch, bin_dir)
    monkeypatch.delenv(PDK_ROOT_ENV, raising=False)
    design = {"netlist": str(AXI), "sdc": str(SDC), "top": TOP}
    with pytest.raises(ToolAccessDenied, match="needs a Liberty file .*no PDK is bundled"):
        invoke(project, "sta.run", design, tmp_path)
    with pytest.raises(ToolAccessDenied, match="liberty not found: .*nowhere.lib"):
        invoke(project, "sta.run", {**design, "liberty": str(tmp_path / "nowhere.lib")}, tmp_path)
    with pytest.raises(ToolAccessDenied, match="needs a technology LEF.*needs a placement site"):
        invoke(project, "pnr.run", {**design, "liberty": str(TINY_LIB)}, tmp_path)
    assert project.state.tool_runs == {}  # the stand-ins never ran


def test_relative_pdk_paths_resolve_under_the_pdk_root(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "sta", f"cat '{PD / 'opensta_met.log'}'")
    only_on_path(monkeypatch, bin_dir)
    fake_pdk(tmp_path / "sky")
    monkeypatch.setenv(PDK_ROOT_ENV, str(tmp_path / "sky"))
    params = {"netlist": str(AXI), "sdc": str(SDC), "top": TOP, "liberty": "cells.lib"}
    run, _ = invoke(project, "sta.run", params, tmp_path / "w")
    assert run.succeeded, run.summary
    script = (tmp_path / "w" / "sta.tcl").read_text()
    assert f'read_liberty "{tmp_path / "sky" / "cells.lib"}"' in script


# --- The runner: real steps, parsed output, recorded failures ------------------------------


def test_sta_runs_the_script_it_writes_and_parses_the_output(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "sta", f"echo \"argv: $*\"; cat '{PD / 'opensta_violated.log'}'")
    only_on_path(monkeypatch, bin_dir)
    params = {"netlist": str(AXI), "sdc": str(SDC), "top": TOP, "liberty": str(TINY_LIB)}
    run, outcome = invoke(project, "sta.run", params, tmp_path / "w")
    assert not run.succeeded and run.id in project.state.tool_runs  # a violation is a recorded failed run
    assert run.summary.startswith("opensta: timing violated: at least 100 violating endpoints")
    log, result = (Path(r) for r in run.references)
    assert "argv: -no_init -no_splash -exit sta.tcl" in log.read_text() and result.is_file()
    assert outcome.data["result"]["metrics"]["worst_slack"] == -0.905
    script = (tmp_path / "w" / "sta.tcl").read_text()
    for line in (f'read_liberty "{TINY_LIB}"', f'read_verilog "{AXI}"', f"link_design {TOP}",
                 f'read_sdc "{SDC}"', "report_worst_slack -max", "report_tns",
                 "-group_path_count 100 -endpoint_path_count 1"):  # M27: -group_count is deprecated
        assert line in script, line
    assert "read_spef" not in script and "read_lef" not in script  # standalone OpenSTA reads no LEF


def test_design_input_problems_and_timeouts_are_recorded_failed_runs(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "sta", "sleep 30")
    only_on_path(monkeypatch, bin_dir)
    base = {"sdc": str(SDC), "top": TOP, "liberty": str(TINY_LIB)}
    missing, _ = invoke(project, "sta.run", {**base, "netlist": str(tmp_path / "nope.v")}, tmp_path / "a")
    assert not missing.succeeded and "not found" in missing.summary and "nope.v" in missing.summary
    no_param, _ = invoke(project, "sta.run", base, tmp_path / "b")
    assert not no_param.succeeded and "missing parameter netlist" in no_param.summary
    slow, _ = invoke(project, "sta.run", {**base, "netlist": str(AXI), "timeout": "1"}, tmp_path / "c")
    assert not slow.succeeded and slow.summary == "opensta: timed out after 1s in sta"
    fake_tool(bin_dir, "sta", "echo 'Error: sta.tcl, 3 unknown cell INV'; exit 1")
    crashed, _ = invoke(project, "sta.run", {**base, "netlist": str(AXI)}, tmp_path / "d")
    assert not crashed.succeeded and "unknown cell INV" in crashed.summary
    assert len(project.state.tool_runs) == 4


def test_pnr_stages_follow_stop_after(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "openroad", f"cat '{PD / 'openroad_route.log'}'")
    only_on_path(monkeypatch, bin_dir)
    params = {"netlist": str(AXI), "sdc": str(SDC), "top": TOP, **fake_pdk(tmp_path / "pdk", rc=True), **PNR_PDK}
    run, outcome = invoke(project, "pnr.run", params, tmp_path / "full")
    assert run.succeeded, run.summary
    assert outcome.data["commands"] == [["openroad", "-no_init", "-no_splash", "-exit", "pnr.tcl"]]
    full = (tmp_path / "full" / "pnr.tcl").read_text()
    for step in ("initialize_floorplan -utilization 40 -aspect_ratio 1 -core_space 2 -site unithd",
                 "place_pins -hor_layers met3 -ver_layers met2", "global_placement", "detailed_route",
                 "estimate_parasitics -global_routing", "report_worst_slack -min", "write_def route.def"):
        assert step in full, step
    assert full.index("read_lef") < full.index("read_liberty") < full.index("link_design")

    run, _ = invoke(project, "pnr.run", {**params, "stop_after": "floorplan", "utilization": "55"},
                    tmp_path / "fp")
    floorplan = (tmp_path / "fp" / "pnr.tcl").read_text()
    assert "-utilization 55" in floorplan and "global_placement" not in floorplan
    assert "estimate_parasitics" not in floorplan and "write_def floorplan.def" in floorplan

    bad, _ = invoke(project, "pnr.run", {**params, "stop_after": "signoff"}, tmp_path / "bad")
    assert not bad.succeeded and "stop_after" in bad.summary


def test_sta_falls_back_to_openroads_embedded_opensta(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "openroad", f"cat '{PD / 'opensta_met.log'}'")
    only_on_path(monkeypatch, bin_dir)  # openroad, and no sta
    params = {"netlist": str(AXI), "sdc": str(SDC), "top": TOP, **fake_pdk(tmp_path / "pdk")}
    with pytest.raises(ToolAccessDenied, match="openroad-sta: needs a technology LEF"):
        invoke(project, "sta.run", {**params, "tech_lef": ""}, tmp_path / "refused")
    run, outcome = invoke(project, "sta.run", params, tmp_path / "w")
    assert run.succeeded and run.summary.startswith("openroad-sta: timing met"), run.summary
    assert outcome.data["commands"] == [["openroad", "-no_init", "-no_splash", "-exit", "sta.tcl"]]
    script = (tmp_path / "w" / "sta.tcl").read_text()
    assert script.index("read_lef") < script.index("read_liberty") < script.index(f"link_design {TOP}")


# --- Liberty-mapped synthesis, for real ---------------------------------------------------


@needs("yosys")
def test_real_liberty_mapped_synthesis_writes_the_netlist(project, tmp_path):
    params = {"sources": str(AXI), "top": TOP, "liberty": str(TINY_LIB), "backend": "yosys-liberty"}
    run, outcome = invoke(project, "synth.run", params, tmp_path)
    assert run.succeeded, run.summary
    metrics = outcome.data["result"]["metrics"]
    netlist = Path(metrics["netlist"])
    assert netlist.is_file() and f"module {TOP}(" in netlist.read_text()
    assert set(metrics["cells_by_type"]) <= {"INV", "BUF", "NAND2", "NOR2", "DFF"}
    assert metrics["flip_flops"] == metrics["cells_by_type"]["DFF"] > 0 and metrics["area"] > 0


@needs("yosys")
def test_real_liberty_mapped_synthesis_ties_constants_to_tie_cells(project, tmp_path):
    """A router cannot route a constant net, so a PDK's tie cells drive the constants."""
    params = {"sources": str(AXI), "top": TOP, "liberty": str(TINY_LIB), "backend": "yosys-liberty",
              "tie_high": "TIEHI/Y", "tie_low": "TIELO/Y"}
    run, outcome = invoke(project, "synth.run", params, tmp_path)
    assert run.succeeded, run.summary
    netlist = Path(outcome.data["result"]["metrics"]["netlist"]).read_text()
    assert "TIELO" in netlist and "1'b0" not in netlist
    bad, _ = invoke(project, "synth.run", {**params, "tie_low": "TIELO"}, tmp_path / "bad")
    assert not bad.succeeded and "tie_low must be CELL/PORT" in bad.summary


@needs("yosys")
def test_real_liberty_mapped_synthesis_buffers_port_to_port_assigns(project, tmp_path):
    """M29: one output port driving another becomes a buffer, so the routed netlist has no shared port net."""
    params = {"sources": str(AXI), "top": TOP, "liberty": str(TINY_LIB), "backend": "yosys-liberty",
              "tie_high": "TIEHI/Y", "tie_low": "TIELO/Y"}
    plain, outcome = invoke(project, "synth.run", params, tmp_path / "plain")
    assert plain.succeeded and "assign " in Path(outcome.data["result"]["metrics"]["netlist"]).read_text()
    run, outcome = invoke(project, "synth.run", {**params, "buffer_cell": "BUF/A/Y"}, tmp_path / "buf")
    assert run.succeeded, run.summary
    assert "assign " not in Path(outcome.data["result"]["metrics"]["netlist"]).read_text()
    bad, _ = invoke(project, "synth.run", {**params, "buffer_cell": "BUF/A"}, tmp_path / "bad")
    assert not bad.succeeded and "buffer_cell must be CELL/IN/OUT" in bad.summary


def test_liberty_mapped_synthesis_without_a_liberty_is_refused(project, tmp_path):
    with pytest.raises(ToolAccessDenied, match="needs a Liberty file"):
        invoke(project, "synth.run", {"sources": str(AXI), "top": TOP, "backend": "yosys-liberty"}, tmp_path)


# --- The workflow -----------------------------------------------------------------------


def test_the_physical_implementation_workflow_plans_the_stages(project):
    assert project.state.project.workflows == ("physical-implementation",)
    tasks = {t.stage: t for t in project.state.tasks.values() if t.stage and t.kind is TaskKind.WORK}
    order = ["timing-constraints", "synthesis", "floorplan", "place-route", "physical-verification", "sta-signoff"]
    assert set(order) <= set(tasks)
    for earlier, later in zip(order, order[1:]):
        assert tasks[earlier].id in tasks[later].depends_on, later
    tools = {stage: {t for r in tasks[stage].evidence_requirements for t in r.tools} for stage in order}
    assert tools["synthesis"] == {"synth.run"} and tools["floorplan"] == {"pnr.run"}
    assert tools["place-route"] == {"pnr.run"} and tools["sta-signoff"] == {"sta.run"}
    assert tools["physical-verification"] == {"pv.run"}  # M34
    gates = [t for t in project.state.tasks.values() if t.kind is TaskKind.GATE and t.stage == "sta-signoff"]
    assert [g.gate for g in gates] == ["gate.implementation"] and tasks["sta-signoff"].id in gates[0].depends_on


def test_the_workflow_asks_for_power_and_extracted_parasitics_as_data(project):
    """M29: a power-grid stage, and limits a run counts only if made with (a metric it never reported fails)."""
    tasks = {t.stage: t for t in project.state.tasks.values() if t.stage and t.kind is TaskKind.WORK}
    assert tasks["floorplan"].id in tasks["power-grid"].depends_on
    assert tasks["power-grid"].id in tasks["place-route"].depends_on
    limits = {stage: {k: v for r in tasks[stage].evidence_requirements for k, v in r.params}
              for stage in ("power-grid", "place-route", "physical-verification", "sta-signoff")}
    assert limits == {"power-grid": {"max_unconnected_supply_pins": "0"},
                      "place-route": {"max_drc_violations": "0", "max_unconnected_supply_pins": "0"},
                      # M34: signoff DRC and LVS on the filled layout, and timing on at least three corners.
                      "physical-verification": {"max_drc_violations": "0", "max_lvs_mismatches": "0",
                                                "min_fill_shapes": "1"},
                      "sta-signoff": {"max_unannotated_nets": "0", "min_timing_corners": "3"}}
    assert {t for r in tasks["power-grid"].evidence_requirements for t in r.tools} == {"pnr.run"}


# --- M34: corners, fill, and physical verification, through stand-ins ------------------------


def test_sta_defines_one_corner_per_liberty_and_reads_the_spef_into_each(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "sta", f"cat '{PD / 'opensta_met.log'}'")
    only_on_path(monkeypatch, bin_dir)
    pdk = fake_pdk(tmp_path / "pdk")
    for corner in ("ss.lib", "ff.lib"):
        (tmp_path / "pdk" / corner).write_text("stand-in\n", encoding="utf-8")
    spef = tmp_path / "route.spef"
    spef.write_text("*SPEF stand-in\n", encoding="utf-8")
    params = {"netlist": str(AXI), "sdc": str(SDC), "top": TOP, "liberty": pdk["liberty"], "corner": "tt",
              "liberty_ss": str(tmp_path / "pdk" / "ss.lib"), "liberty_ff": str(tmp_path / "pdk" / "ff.lib"),
              "spef": str(spef)}
    invoke(project, "sta.run", params, tmp_path / "w")
    script = (tmp_path / "w" / "sta.tcl").read_text()
    assert script.index("define_corners tt ss ff") < script.index(f'read_liberty -corner ss "{tmp_path}/pdk/ss.lib"')
    assert f'read_liberty -corner tt "{pdk["liberty"]}"' in script
    for corner in ("tt", "ss", "ff"):
        assert f"read_spef -corner {corner} " in script, corner
        assert f'puts "nirmaan-corner: {corner}"' in script
        assert f"report_checks -path_delay max -scenes {corner} -format end" in script
        assert f"report_checks -path_delay min -scenes {corner} -format end" in script
    plain = invoke(project, "sta.run", {k: v for k, v in params.items() if not k.startswith("liberty_")},
                   tmp_path / "one")
    assert "define_corners" not in (tmp_path / "one" / "sta.tcl").read_text() and plain[0].succeeded
    # The single-corner log reports one corner, so a three-corner limit fails it.
    one, _ = invoke(project, "sta.run", {**params, "liberty_ss": "", "liberty_ff": "", "min_timing_corners": "3"},
                    tmp_path / "limit")
    assert not one.succeeded and "timing_corners 1 is below min_timing_corners 3" in one.summary, one.summary
    with pytest.raises(ToolAccessDenied, match="liberty_ss not found: .*nowhere.lib"):
        invoke(project, "sta.run", {**params, "liberty_ss": str(tmp_path / "nowhere.lib")}, tmp_path / "x")
    clash, _ = invoke(project, "sta.run", {**params, "corner": "ss"}, tmp_path / "clash")
    assert not clash.succeeded and "timing corners must differ" in clash.summary


def test_pnr_fills_metal_and_writes_the_netlist_lvs_needs(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "openroad", f"cat '{PD / 'openroad_route.log'}'")
    only_on_path(monkeypatch, bin_dir)
    pdk = fake_pdk(tmp_path / "pdk", rc=True)
    (tmp_path / "pdk" / "fill.json").write_text("{}\n", encoding="utf-8")
    params = {"netlist": str(AXI), "sdc": str(SDC), "top": TOP, **pdk, **PNR_PDK,
              "filler_cells": "FILL1", "fill_rules": str(tmp_path / "pdk" / "fill.json")}
    invoke(project, "pnr.run", params, tmp_path / "w")
    script = (tmp_path / "w" / "pnr.tcl").read_text()
    route = script[script.index("nirmaan-stage: route"):script.index("nirmaan-stage-done: route")]
    assert route.index("filler_placement") < route.index(f'density_fill -rules "{tmp_path}/pdk/fill.json"')
    assert "nirmaan-fill-shapes" in route
    assert "write_verilog final.v" in script and "write_verilog -include_pwr_gnd final_pg.v" in script
    with pytest.raises(ToolAccessDenied, match="fill_rules not found"):
        invoke(project, "pnr.run", {**params, "fill_rules": str(tmp_path / "none.json")}, tmp_path / "x")


def fake_pv_pdk(root: Path, lvs: bool = True) -> dict[str, str]:
    """Stand-in KLayout inputs: technology, cell GDS, a DRC deck, and (``lvs``) an LVS deck and cell CDL."""
    pdk = fake_pdk(root)
    names = {"gds": "cells.gds", "klayout_tech": "tech.lyt", "drc_deck": "drc.lydrc",
             **({"lvs_deck": "lvs.lylvs", "cdl": "cells.cdl"} if lvs else {})}
    for name in names.values():
        (root / name).write_text("<lef-files>x</lef-files>\n" if name.endswith(".lyt") else "stand-in\n",
                                 encoding="utf-8")
    return {"tech_lef": pdk["tech_lef"], "lef": pdk["lef"], **{k: str(root / v) for k, v in names.items()}}


def test_pv_runs_stream_drc_and_lvs_and_counts_them_itself(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "openroad", 'echo "argv: $*"')
    fake_tool(bin_dir, "klayout", 'echo "argv: $*"')
    only_on_path(monkeypatch, bin_dir)
    layout = tmp_path / "route.def"
    layout.write_text("stand-in\n", encoding="utf-8")
    pdk = fake_pv_pdk(tmp_path / "pdk")
    params = {"def": str(layout), "netlist": str(AXI), "top": TOP, **pdk}
    run, outcome = invoke(project, "pv.run", params, tmp_path / "w")
    # The stand-ins print no counts: a run that cannot show its counts is a recorded failed run.
    assert not run.succeeded and run.id in project.state.tool_runs
    assert "no GDS written" in run.summary and "no DRC count" in run.summary and "no LVS comparison" in run.summary
    steps = outcome.data["commands"]
    assert [s[0] for s in steps] == ["openroad", "klayout", "klayout", "klayout", "klayout", "klayout"]
    assert steps[1][-1] == "stream.py" and steps[2][-1] == pdk["drc_deck"] and steps[3][-1] == "drc_count.py"
    assert steps[4][-1] == pdk["lvs_deck"] and steps[5][-1] == "lvs_count.py"
    work = tmp_path / "w"
    tech = (work / "klayout.lyt").read_text()
    assert f"<lef-files>{pdk['tech_lef']}</lef-files><lef-files>{pdk['lef']}</lef-files>" in tech
    assert f'.INCLUDE "{pdk["cdl"]}"' in (work / "reference.cdl").read_text()
    assert f'read_verilog "{AXI}"' in (work / "cdl.tcl").read_text()
    drc_only, outcome = invoke(project, "pv.run", {**params, "lvs_deck": "", "cdl": ""}, tmp_path / "d")
    assert [s[-1] for s in outcome.data["commands"]] == ["stream.py", pdk["drc_deck"], "drc_count.py"]
    with pytest.raises(ToolAccessDenied, match="needs a check to run"):
        invoke(project, "pv.run", {**params, "drc_deck": "", "lvs_deck": ""}, tmp_path / "none")
    with pytest.raises(ToolAccessDenied, match="needs the cells' GDS"):
        invoke(project, "pv.run", {**params, "gds": ""}, tmp_path / "nogds")


def test_min_limits_fail_a_run_below_them_or_without_the_metric(project, tmp_path, monkeypatch):
    """M34: ``min_<metric>`` is the runner's limit from below, as ``max_<metric>`` is from above."""
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "sta", f"cat '{PD / 'opensta_met.log'}'")
    only_on_path(monkeypatch, bin_dir)
    base = {"netlist": str(AXI), "sdc": str(SDC), "top": TOP, "liberty": str(TINY_LIB)}
    met, _ = invoke(project, "sta.run", {**base, "min_timing_corners": "1"}, tmp_path / "a")
    assert met.succeeded, met.summary
    unknown, _ = invoke(project, "sta.run", {**base, "min_no_such_metric": "1"}, tmp_path / "b")
    assert not unknown.succeeded and "no_such_metric was not reported" in unknown.summary


# --- Crown jewel: a new PD backend needs zero core changes ---------------------------------


def test_a_new_pd_backend_needs_no_core_changes(project, tmp_path, monkeypatch):
    """A router the core has never heard of: an executable, a PDK requirement, steps, a parser."""
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "tinyroute", 'echo "routed $1 with $2"; echo "tinyroute: 0 opens, 0 shorts"')

    def parse(run) -> EdaResult:
        clean = run.returncode == 0 and "0 opens, 0 shorts" in run.log
        # M29: the metrics the place-route evidence limits; a run that never reports them cannot meet it.
        metrics = {"drc_violations": 0, "unconnected_supply_pins": 0} if clean else {}
        return EdaResult(clean, "routed clean" if clean else "routing failed", metrics=metrics)

    register_backend(Backend("tinyroute", "pnr.run", ("tinyroute",),
                             lambda job: [["tinyroute", job.params["netlist"], *job.params["lef"]]], parse,
                             required=("netlist",), files=("netlist",),
                             environment=needs_pdk(lef="a cell LEF")))
    try:
        only_on_path(monkeypatch, bin_dir)
        params = {"netlist": str(AXI), "backend": "tinyroute"}
        with pytest.raises(ToolAccessDenied, match="tinyroute: needs a cell LEF"):
            invoke(project, "pnr.run", params, tmp_path / "w1")  # no PDK: refused
        assert project.state.tool_runs == {}
        lef = fake_pdk(tmp_path / "pdk")["lef"]
        place_route = tid(project, "place-route")
        limits = {"max_drc_violations": "0", "max_unconnected_supply_pins": "0"}  # as the workflow names them
        run, _ = invoke(project, "pnr.run", {**params, "lef": lef, **limits}, tmp_path / "w2", place_route)
        assert run.succeeded and run.summary == "tinyroute: routed clean"
        assert f"routed {AXI} with {lef}" in Path(run.references[0]).read_text()  # it really ran
        owner = agent(project.task(place_route).owner)
        ev = project.record_evidence(place_route, owner, EvidenceKind.TOOL_RUN, run.summary, tool_run=run.id)
        assert ev.substantiated
        pnr_req = next(r for r in project.task(place_route).evidence_requirements if r.tools == ("pnr.run",))
        unmet = unsatisfied_requirements(project.state, project.task(place_route))
        assert pnr_req.description not in unmet and unmet  # met by the run; the review is still owed
    finally:
        unregister_backend("pnr.run", "tinyroute")


def test_signoff_on_extracted_parasitics_needs_no_core_changes(project, tmp_path, monkeypatch):
    """M29 crown jewel: a timer the core has never heard of meets sta-signoff only when it reads a SPEF.

    Nothing in the core names SPEF: the stage asks for ``max_unannotated_nets=0``, and a run that never
    reports the metric fails the limit.
    """
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "tinysta", 'if [ -n "$1" ]; then echo "annotated from $1"; fi; echo "tinysta: slack 1.0"')

    def parse(run) -> EdaResult:
        metrics = {"unannotated_nets": 0, "timing_corners": 3} if "annotated from" in run.log else {}
        return EdaResult(run.returncode == 0, "timing met", metrics=metrics)

    register_backend(Backend("tinysta", "sta.run", ("tinysta",),
                             lambda job: [["tinysta", job.params.get("spef", "")]], parse,
                             required=("netlist",), files=("netlist", "spef")))
    try:
        only_on_path(monkeypatch, bin_dir)
        signoff = tid(project, "sta-signoff")
        req = next(r for r in project.task(signoff).evidence_requirements if r.tools == ("sta.run",))
        owner = agent(project.task(signoff).owner)
        base = {"netlist": str(AXI), "backend": "tinysta", **dict(req.params)}
        estimated, _ = invoke(project, "sta.run", base, tmp_path / "est", signoff)
        assert not estimated.succeeded and "unannotated_nets was not reported" in estimated.summary
        spef = tmp_path / "route.spef"
        spef.write_text("*SPEF stand-in\n", encoding="utf-8")
        extracted, _ = invoke(project, "sta.run", {**base, "spef": str(spef)}, tmp_path / "ext", signoff)
        assert extracted.succeeded, extracted.summary
        project.record_evidence(signoff, owner, EvidenceKind.TOOL_RUN, extracted.summary, tool_run=extracted.id)
        assert req.description not in unsatisfied_requirements(project.state, project.task(signoff))
    finally:
        unregister_backend("sta.run", "tinysta")


def test_physical_verification_needs_no_core_changes(project, tmp_path, monkeypatch):
    """M34 crown jewel: a DRC and LVS tool the core has never heard of meets the physical-verification stage.

    The stage asks for limits only (no DRC violation, no LVS mismatch, some fill), so any backend that
    reports those metrics serves it, and one that does not report them cannot.
    """
    bin_dir = tmp_path / "bin"
    fake_tool(bin_dir, "tinypv", 'echo "checked $1"; echo "tinypv: 0 drc, 0 lvs, 12 fill"')

    def parse(run) -> EdaResult:
        clean = run.returncode == 0 and "0 drc, 0 lvs" in run.log
        metrics = {"drc_violations": 0, "lvs_mismatches": 0, "fill_shapes": 12} if clean else {}
        return EdaResult(clean, "clean" if clean else "failed", metrics=metrics)

    register_backend(Backend("tinypv", "pv.run", ("tinypv",), lambda job: [["tinypv", job.params["def"]]], parse,
                             required=("def",), files=("def",)))
    try:
        only_on_path(monkeypatch, bin_dir)
        layout = tmp_path / "route.def"
        layout.write_text("stand-in\n", encoding="utf-8")
        stage = tid(project, "physical-verification")
        req = next(r for r in project.task(stage).evidence_requirements if r.tools == ("pv.run",))
        params = {"def": str(layout), "netlist": str(AXI), "top": TOP, "backend": "tinypv", **dict(req.params)}
        run, _ = invoke(project, "pv.run", params, tmp_path / "w", stage)
        assert run.succeeded and f"checked {layout}" in Path(run.references[0]).read_text()
        project.record_evidence(stage, agent(project.task(stage).owner), EvidenceKind.TOOL_RUN, run.summary,
                                tool_run=run.id)
        assert req.description not in unsatisfied_requirements(project.state, project.task(stage))
        short, _ = invoke(project, "pv.run", {**params, "min_fill_shapes": "100"}, tmp_path / "w2", stage)
        assert not short.succeeded and "fill_shapes 12 is below min_fill_shapes 100" in short.summary
    finally:
        unregister_backend("pv.run", "tinypv")


# --- The import laws ----------------------------------------------------------------------


def test_the_physical_modules_keep_the_import_laws():
    src = Path(__file__).resolve().parent.parent / "src" / "nirmaan" / "integrations"
    imports = {}
    for name in ("physical.py", "pd_parsers.py"):
        tree = ast.parse((src / name).read_text(encoding="utf-8"))
        modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        modules |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m.split(".")[0] == "veritriage" for m in modules), name
        imports[name] = {m for m in modules if m.startswith("nirmaan")}
    assert imports["pd_parsers.py"] <= {"nirmaan.integrations.eda_parsers"}  # the parsers stay pure


# --- Real tools (skipped without OpenSTA or OpenROAD and Nangate45) -------------------------

#: Nangate45 as OpenROAD-flow-scripts lays it out under ``flow/platforms`` (NIRMAAN_PDK_ROOT).
NANGATE45 = {
    "liberty": "nangate45/lib/NangateOpenCellLibrary_typical.lib",
    "tech_lef": "nangate45/lef/NangateOpenCellLibrary.tech.lef",
    "lef": "nangate45/lef/NangateOpenCellLibrary.macro.mod.lef",
}
NANGATE45_TIES = {"tie_high": "LOGIC1_X1/Z", "tie_low": "LOGIC0_X1/Z",
                  "buffer_cell": "BUF_X1/A/Z"}  # M29: no port-to-port assign for the timer to trip on
NANGATE45_PNR = {"site": "FreePDK45_38x28_10R_NP_162NW_34O", "hor_layers": "metal3", "ver_layers": "metal2",
                 "rc_tcl": "nangate45/setRC.tcl"}  # M29: layer RC, which clock-tree synthesis needs
FAST_SDC = PD / "axi4_lite_regs_fast.sdc"


def nangate45() -> dict[str, str]:
    """Nangate45 under NIRMAAN_PDK_ROOT; skip without it (fail when CI requires STA or OpenROAD)."""
    root = os.environ.get(PDK_ROOT_ENV, "")
    if root and all((Path(root) / p).is_file() for p in NANGATE45.values()):
        return dict(NANGATE45)
    reason = f"{PDK_ROOT_ENV} does not point at OpenROAD-flow-scripts platforms with nangate45"
    if set(os.environ.get("NIRMAAN_REQUIRE_EDA", "").replace(",", " ").split()) & {"sta", "openroad"}:
        pytest.fail(reason)
    pytest.skip(reason)


def _mapped_netlist(project, tmp_path, pdk) -> str:
    params = {"sources": str(AXI), "top": TOP, "backend": "yosys-liberty", "liberty": pdk["liberty"],
              **NANGATE45_TIES}
    run, outcome = invoke(project, "synth.run", params, tmp_path / "synth")
    assert run.succeeded, run.summary
    return outcome.data["result"]["metrics"]["netlist"]


@needs("openroad", "yosys")
def test_real_opensta_times_the_axi4_lite_block(project, tmp_path):
    """OpenSTA through whichever backend is installed: standalone ``sta``, or OpenROAD's embedded one."""
    pdk = nangate45()
    netlist = _mapped_netlist(project, tmp_path, pdk)
    design = {"netlist": netlist, "top": TOP, **pdk}  # OpenROAD's OpenSTA reads the LEFs too
    run, outcome = invoke(project, "sta.run", {**design, "sdc": str(SDC)}, tmp_path / "sta")
    metrics = outcome.data["result"]["metrics"]
    assert outcome.data["backend"] in {"opensta", "openroad-sta"}
    assert run.succeeded, run.summary  # 100 MHz is easy for Nangate45
    assert metrics["worst_slack"] > 0 and metrics["worst_hold_slack"] >= 0 and metrics["tns"] == 0

    fast, outcome = invoke(project, "sta.run", {**design, "sdc": str(FAST_SDC)}, tmp_path / "sta_fast")
    metrics = outcome.data["result"]["metrics"]
    assert not fast.succeeded and fast.id in project.state.tool_runs  # a violation is a recorded failed run
    assert metrics["worst_slack"] < 0 and metrics["tns"] < 0 and metrics["violating_endpoints"], fast.summary
    assert fast.summary.startswith(f"{outcome.data['backend']}: timing violated:"), fast.summary


@needs("openroad", "yosys")
def test_real_openroad_places_and_routes_the_axi4_lite_block(project, tmp_path):
    pdk = nangate45()
    netlist = _mapped_netlist(project, tmp_path, pdk)
    run, outcome = invoke(project, "pnr.run", {"netlist": netlist, "sdc": str(SDC), "top": TOP, **pdk,
                                               **NANGATE45_PNR}, tmp_path / "pnr")
    metrics = outcome.data["result"]["metrics"]
    assert metrics["stages_completed"] == ["floorplan", "place", "cts", "route", "timing"], run.summary
    assert metrics["drc_violations"] == 0 and metrics["wirelength_um"] > 0, run.summary
    assert metrics["utilization_pct"] > 0 and metrics["worst_slack"] > 0, run.summary
    assert run.succeeded, run.summary
    assert set(metrics["outputs"]) == {"def", "netlist", "pg_netlist"}  # M34: the netlist LVS compares against


@needs("openroad", "yosys")
def test_real_openroad_failure_is_a_recorded_failed_run(project, tmp_path):
    pdk = nangate45()
    netlist = _mapped_netlist(project, tmp_path, pdk)
    run, outcome = invoke(project, "pnr.run", {"netlist": netlist, "sdc": str(SDC), "top": TOP, **pdk,
                                               **NANGATE45_PNR, "utilization": "300"}, tmp_path / "pnr_over")
    assert not run.succeeded and run.id in project.state.tool_runs
    assert outcome.data["result"]["diagnostics"], run.summary
    assert "place and route failed" in run.summary, run.summary


# --- M29: signoff steps for real (power grid, CTS, repair, fillers, extraction) ------------

#: The Nangate45 platform's own signoff inputs, as OpenROAD-flow-scripts ships them.
NANGATE45_SIGNOFF = {
    "tap_cell": "TAPCELL_X1", "endcap_cell": "TAPCELL_X1", "tap_distance": "120",
    "pdn_tcl": "nangate45/grid_strategy-M1-M4-M7.tcl",
    "rcx_rules": "nangate45/rcx_patterns.rules",
    "filler_cells": "FILLCELL_X1,FILLCELL_X2,FILLCELL_X4,FILLCELL_X8,FILLCELL_X16,FILLCELL_X32",
    "supply_voltage": "1.1",
}


def _signoff_pnr(project, tmp_path, pdk, netlist, name, **extra):
    params = {"netlist": netlist, "sdc": str(SDC), "top": TOP, **pdk, **NANGATE45_PNR, **NANGATE45_SIGNOFF, **extra}
    return invoke(project, "pnr.run", params, tmp_path / name)


@needs("openroad", "yosys")
def test_real_signoff_flow_connects_power_builds_the_clock_tree_and_extracts(project, tmp_path):
    pdk = nangate45()
    netlist = _mapped_netlist(project, tmp_path, pdk)
    run, outcome = _signoff_pnr(project, tmp_path, pdk, netlist, "signoff")
    m = outcome.data["result"]["metrics"]
    assert m["stages_completed"] == ["floorplan", "place", "cts", "route", "extract", "timing"], run.summary
    assert m["drc_violations"] == 0 and m["power_grids"] and m["unconnected_supply_pins"] == 0, run.summary
    assert m["tap_cells"] + m["endcap_cells"] > 0 and m["filler_cells"] > 0, run.summary
    assert m["antenna_net_violations"] == 0 and m["antenna_pin_violations"] == 0, run.summary
    assert m["cts_buffers"] > 0 and m["cts_sinks"] > 0, run.summary
    assert m["clock_skew"] is not None and m["clock_insertion_delay"] is not None, run.summary
    assert set(m["slack_by_stage"]) == {"place", "cts", "route", "extract"}, m["slack_by_stage"]
    assert m["parasitics"] == "extracted" and m["worst_slack"] > 0 and m["unannotated_nets"] == 0, run.summary
    assert set(m["outputs"]) == {"def", "netlist", "pg_netlist", "spef"} and run.succeeded, run.summary

    # Signoff STA on the routed netlist with the extracted SPEF, in a separate run: through OpenROAD's
    # embedded OpenSTA, and through standalone OpenSTA when it is installed (CI builds it, M29).
    design = {"netlist": m["outputs"]["netlist"], "top": TOP, **pdk, "sdc": str(SDC), "spef": m["outputs"]["spef"]}
    for backend in sta_backends():
        sta, sta_outcome = invoke(project, "sta.run", {**design, "backend": backend}, tmp_path / f"sta_{backend}")
        sm = sta_outcome.data["result"]["metrics"]
        assert sta_outcome.data["backend"] == backend
        assert sm["unannotated_nets"] == 0 and sm["worst_slack"] > 0, sta.summary  # every net has parasitics
        assert sta.succeeded, sta.summary


def sta_backends() -> list[str]:
    """OpenROAD's embedded OpenSTA always; standalone OpenSTA when on PATH or required (M29)."""
    required = "sta" in os.environ.get("NIRMAAN_REQUIRE_EDA", "").replace(",", " ").split()
    return ["openroad-sta", *(["opensta"] if shutil.which("sta") or required else [])]


@needs("openroad", "yosys")
def test_real_signoff_flow_with_an_impossible_clock_is_a_recorded_failed_run(project, tmp_path):
    pdk = nangate45()
    netlist = _mapped_netlist(project, tmp_path, pdk)
    run, outcome = _signoff_pnr(project, tmp_path, pdk, netlist, "signoff_fast", sdc=str(FAST_SDC), stop_after="cts")
    m = outcome.data["result"]["metrics"]
    assert not run.succeeded and run.id in project.state.tool_runs
    assert m["stages_completed"] == ["floorplan", "place", "cts", "timing"], run.summary  # every stage ran
    assert "timing violated" in run.summary and m["worst_slack"] < 0 and m["slack_by_stage"]["cts"]["setup"] < 0


#: sky130 HD as OpenROAD-flow-scripts ships it under ``flow/platforms/sky130hd`` (M29).
SKY130HD = {
    "liberty": "sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib",
    "tech_lef": "sky130hd/lef/sky130_fd_sc_hd.tlef",
    "lef": "sky130hd/lef/sky130_fd_sc_hd_merged.lef",
}
SKY130HD_PNR = {
    "site": "unithd", "hor_layers": "met3", "ver_layers": "met2",
    # Signals stop below met5, which carries the power straps: on met5 the router left shorts it never fixed.
    # M34: and below met4: with met4, the KLayout deck found three met3 islands under the minimum area
    # (m3.6) where a via2 and a via3 stack, which the router's own DRC did not count.
    "routing_layers": "met1,met3",
    # The probe buffers have met5 pins the router cannot reach below met4 (GRT-0029 when repair chose one).
    "dont_use": "sky130_fd_sc_hd__probe_p_*,sky130_fd_sc_hd__probec_p_*,sky130_fd_sc_hd__lpflow_*",
    "tap_cell": "sky130_fd_sc_hd__tapvpwrvgnd_1", "tap_distance": "14",
    "pdn_tcl": "sky130hd/pdn.tcl", "rc_tcl": "sky130hd/setRC.tcl", "rcx_rules": "sky130hd/rcx_patterns.rules",
    "filler_cells": "sky130_fd_sc_hd__fill_1,sky130_fd_sc_hd__fill_2,sky130_fd_sc_hd__fill_4,sky130_fd_sc_hd__fill_8",
    "supply_voltage": "1.8",
    "fill_rules": "sky130hd/fill.json",  # M34: metal fill before signoff DRC
}
#: M34: the slow and fast corners, fetched by CI from the open_pdks build of the SkyWater library (pinned by
#: sha256) into the platform's lib directory; the typical corner is the platform's own.
SKY130HD_CORNERS = {"corner": "tt", "liberty_ss": "sky130hd/lib/sky130_fd_sc_hd__ss_100C_1v60.lib",
                    "liberty_ff": "sky130hd/lib/sky130_fd_sc_hd__ff_n40C_1v95.lib"}
#: M34: the platform's KLayout signoff inputs.
SKY130HD_PV = {"gds": "sky130hd/gds/sky130_fd_sc_hd.gds", "klayout_tech": "sky130hd/sky130hd.lyt",
               "drc_deck": "sky130hd/drc/sky130hd.lydrc", "lvs_deck": "sky130hd/lvs/sky130hd.lylvs",
               "cdl": "sky130hd/cdl/sky130hd.cdl"}


def sky130hd(*extra: dict[str, str]) -> None:
    """Skip without the sky130hd platform (and the inputs named), or fail when CI requires OpenROAD."""
    root = os.environ.get(PDK_ROOT_ENV, "")
    paths = [v for d in (SKY130HD, *extra) for k, v in d.items() if k != "corner"]
    if not (root and all((Path(root) / p).is_file() for p in paths)):
        reason = f"{PDK_ROOT_ENV} has no sky130hd platform with {', '.join(p for p in paths if not (Path(root) / p).is_file())}"
        if "openroad" in os.environ.get("NIRMAAN_REQUIRE_EDA", "").split():
            pytest.fail(reason)
        pytest.skip(reason)


@needs("openroad", "yosys", "klayout")
def test_real_signoff_flow_on_sky130hd(project, tmp_path):
    """M29 signoff flow, and M34: metal fill, three timing corners, and KLayout DRC and LVS, clean and broken."""
    sky130hd(SKY130HD_CORNERS, SKY130HD_PV)
    params = {"sources": str(AXI), "top": TOP, "backend": "yosys-liberty", "liberty": SKY130HD["liberty"],
              "tie_high": "sky130_fd_sc_hd__conb_1/HI", "tie_low": "sky130_fd_sc_hd__conb_1/LO",
              "buffer_cell": "sky130_fd_sc_hd__buf_4/A/X"}
    synth, outcome = invoke(project, "synth.run", params, tmp_path / "synth")
    assert synth.succeeded, synth.summary
    netlist = outcome.data["result"]["metrics"]["netlist"]
    run, outcome = invoke(project, "pnr.run", {"netlist": netlist, "sdc": str(SDC), "top": TOP, **SKY130HD,
                                               **SKY130HD_PNR, "utilization": "30", "timeout": "900"},
                          tmp_path / "pnr")
    m = outcome.data["result"]["metrics"]
    assert m["stages_completed"] == ["floorplan", "place", "cts", "route", "extract", "timing"], run.summary
    assert m["drc_violations"] == 0 and m["unconnected_supply_pins"] == 0, run.summary
    assert m["parasitics"] == "extracted" and run.succeeded, run.summary
    assert m["fill_shapes"] > 0, run.summary  # M34
    out = m["outputs"]

    # M34: signoff timing on the SPEF at the slow, typical, and fast corners, through both timers.
    design = {"netlist": out["netlist"], "top": TOP, **SKY130HD, "sdc": str(SDC), "spef": out["spef"],
              **SKY130HD_CORNERS, "max_unannotated_nets": "0", "min_timing_corners": "3"}
    for backend in sta_backends():
        sta, sta_outcome = invoke(project, "sta.run", {**design, "backend": backend}, tmp_path / f"corners_{backend}")
        sm = sta_outcome.data["result"]["metrics"]
        corners = sm["slack_by_corner"]
        assert sm["timing_corners"] == 3 and set(corners) == {"ss", "tt", "ff"}, sta.summary
        assert corners["ss"]["setup"] < corners["tt"]["setup"] < corners["ff"]["setup"], corners  # slow is slowest
        assert corners["ff"]["hold"] < corners["tt"]["hold"], corners  # fast is the hold corner
        assert sm["worst_slack"] == corners["ss"]["setup"] and sm["worst_hold_slack"] == corners["ff"]["hold"]
        assert sta.succeeded, sta.summary

    # M34: DRC and LVS with the platform's KLayout decks, on the filled layout, against the routed netlist.
    pv = {"def": out["def"], "netlist": out["pg_netlist"], "top": TOP, "tech_lef": SKY130HD["tech_lef"],
          "lef": SKY130HD["lef"], **SKY130HD_PV,
          "max_drc_violations": "0", "max_lvs_mismatches": "0", "min_fill_shapes": "1"}
    clean, clean_outcome = invoke(project, "pv.run", pv, tmp_path / "pv")
    cm = clean_outcome.data["result"]["metrics"]
    assert cm["drc_violations"] == 0 and cm["lvs_mismatches"] == 0 and cm["gds_empty_cells"] == 0, clean.summary
    assert cm["fill_shapes"] == m["fill_shapes"] and clean.succeeded, clean.summary

    # A cell moved 1 nm off the 5 nm manufacturing grid: its shapes are off grid and overlap its neighbour.
    layout = Path(out["def"]).read_text(encoding="utf-8")
    place = re.search(r"(- \S+ sky130_fd_sc_hd__dfxtp_\d \+ PLACED \( )(\d+) ", layout)
    broken_def = tmp_path / "broken.def"
    broken_def.write_text(layout[:place.start()] + place[1] + f"{int(place[2]) + 1} " + layout[place.end():],
                          encoding="utf-8")
    bad_drc, bad_outcome = invoke(project, "pv.run", {**pv, "def": str(broken_def)}, tmp_path / "pv_drc")
    assert not bad_drc.succeeded and bad_drc.id in project.state.tool_runs
    bm = bad_outcome.data["result"]["metrics"]
    assert bm["drc_violations"] > 0 and any("OFFGRID" in r for r in bm["drc_by_rule"]), bad_drc.summary
    assert "DRC violation" in bad_drc.summary

    # A flip-flop's D input rewired to another net in the netlist: the layout no longer matches it.
    pg = Path(out["pg_netlist"]).read_text(encoding="utf-8")
    d_pins = list(re.finditer(r"\.D\((\w+)\)", pg))
    broken_v = tmp_path / "broken.v"
    broken_v.write_text(pg[:d_pins[0].start()] + f".D({d_pins[1][1]})" + pg[d_pins[0].end():], encoding="utf-8")
    bad_lvs, lvs_outcome = invoke(project, "pv.run", {**pv, "netlist": str(broken_v)}, tmp_path / "pv_lvs")
    lm = lvs_outcome.data["result"]["metrics"]
    assert not bad_lvs.succeeded and bad_lvs.id in project.state.tool_runs
    assert lm["lvs_mismatches"] > 0 and lm["drc_violations"] == 0, bad_lvs.summary
    assert "LVS mismatch" in bad_lvs.summary

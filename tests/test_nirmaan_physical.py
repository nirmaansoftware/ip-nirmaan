"""Milestones 25 and 27 (physical design): OpenSTA and OpenROAD behind the broker.

* Parsers are tested against logs CAPTURED from real OpenROAD runs in CI
  (M27; each starts with a ``# CAPTURED:`` line naming the run).
* A missing executable or a missing PDK input is a refusal with a reason, and
  no run is recorded. Design-input problems, tool failures, and timeouts are
  recorded failed runs.
* Liberty-mapped synthesis (the netlist STA and place-and-route consume) runs
  for real with Yosys and a toy test library.
* The physical-implementation workflow plans synth, floorplan, place and
  route, then STA signoff.
* Crown jewel: a new physical-design backend needs zero core changes.
* Real OpenSTA and OpenROAD tests skip without the tools and Nangate45; the CI
  physical-design job requires them.
"""

from __future__ import annotations

import ast
import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import agent, tid
from test_nirmaan_eda import holder, needs

from nirmaan.integrations.eda import Backend, EdaResult, register_backend, unregister_backend
from nirmaan.integrations.pd_parsers import VIOLATOR_REPORT_LIMIT, parse_openroad, parse_opensta
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
    for tool in ("sta.run", "pnr.run"):
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
    assert [p.name for p in logs] == ["openroad_error.log", "openroad_route.log", "opensta_met.log",
                                      "opensta_violated.log"]
    for log in logs:
        first, second = log.read_text(encoding="utf-8").splitlines()[:2]
        assert first.startswith("# CAPTURED:") and "CI run" in first, log
        assert second.startswith("$ openroad -no_init -no_splash -exit "), log  # as eda.execute logs a step


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
    assert m["stages_completed"] == ["floorplan", "place", "route", "timing"] and m["failed_stage"] is None
    assert (m["design_area_um2"], m["utilization_pct"]) == (1665.0, 41.0)  # printed as um^2
    assert (m["wirelength_um"], m["drc_violations"]) == (10783.0, 0)  # the last iteration's figures
    assert (m["worst_slack"], m["worst_hold_slack"]) == (7.12, 0.103)
    assert [d.code for d in result.warnings] == ["IFP-0028", "DRT-0120", "DRT-0120"]
    assert result.summary == ("place and route passed: routed, 0 DRC violations, wirelength 10783 um, "
                              "utilization 41%, worst setup slack 7.120, worst hold slack 0.103, TNS 0.000")


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


def test_liberty_mapped_synthesis_without_a_liberty_is_refused(project, tmp_path):
    with pytest.raises(ToolAccessDenied, match="needs a Liberty file"):
        invoke(project, "synth.run", {"sources": str(AXI), "top": TOP, "backend": "yosys-liberty"}, tmp_path)


# --- The workflow -----------------------------------------------------------------------


def test_the_physical_implementation_workflow_plans_the_stages(project):
    assert project.state.project.workflows == ("physical-implementation",)
    tasks = {t.stage: t for t in project.state.tasks.values() if t.stage and t.kind is TaskKind.WORK}
    order = ["timing-constraints", "synthesis", "floorplan", "place-route", "sta-signoff"]
    assert set(order) <= set(tasks)
    for earlier, later in zip(order, order[1:]):
        assert tasks[earlier].id in tasks[later].depends_on, later
    tools = {stage: {t for r in tasks[stage].evidence_requirements for t in r.tools} for stage in order}
    assert tools["synthesis"] == {"synth.run"} and tools["floorplan"] == {"pnr.run"}
    assert tools["place-route"] == {"pnr.run"} and tools["sta-signoff"] == {"sta.run"}
    gates = [t for t in project.state.tasks.values() if t.kind is TaskKind.GATE and t.stage == "sta-signoff"]
    assert [g.gate for g in gates] == ["gate.implementation"] and tasks["sta-signoff"].id in gates[0].depends_on


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
                             lambda job: [["tinyroute", job.params["netlist"], job.params["lef"]]], parse,
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
NANGATE45_TIES = {"tie_high": "LOGIC1_X1/Z", "tie_low": "LOGIC0_X1/Z"}
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
    assert set(metrics["outputs"]) == {"def", "netlist"}


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
    assert set(m["outputs"]) == {"def", "netlist", "spef"} and run.succeeded, run.summary

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
    "routing_layers": "met1,met4",
    # The probe buffers have met5 pins the router cannot reach below met4 (GRT-0029 when repair chose one).
    "dont_use": "sky130_fd_sc_hd__probe_p_*,sky130_fd_sc_hd__probec_p_*,sky130_fd_sc_hd__lpflow_*",
    "tap_cell": "sky130_fd_sc_hd__tapvpwrvgnd_1", "tap_distance": "14",
    "pdn_tcl": "sky130hd/pdn.tcl", "rc_tcl": "sky130hd/setRC.tcl", "rcx_rules": "sky130hd/rcx_patterns.rules",
    "filler_cells": "sky130_fd_sc_hd__fill_1,sky130_fd_sc_hd__fill_2,sky130_fd_sc_hd__fill_4,sky130_fd_sc_hd__fill_8",
    "supply_voltage": "1.8",
}


@needs("openroad", "yosys")
def test_real_signoff_flow_on_sky130hd(project, tmp_path):
    root = os.environ.get(PDK_ROOT_ENV, "")
    if not (root and all((Path(root) / p).is_file() for p in SKY130HD.values())):
        if "openroad" in os.environ.get("NIRMAAN_REQUIRE_EDA", "").split():
            pytest.fail(f"{PDK_ROOT_ENV} has no sky130hd platform")
        pytest.skip(f"{PDK_ROOT_ENV} has no sky130hd platform")
    params = {"sources": str(AXI), "top": TOP, "backend": "yosys-liberty", "liberty": SKY130HD["liberty"],
              "tie_high": "sky130_fd_sc_hd__conb_1/HI", "tie_low": "sky130_fd_sc_hd__conb_1/LO"}
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

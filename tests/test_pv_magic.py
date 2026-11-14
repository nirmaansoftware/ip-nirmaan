"""Milestone 79: ``pv.run``'s ``magic-netgen`` backend (Magic DRC and Netgen LVS), without the tools.

The real run is the SKY130 pilot (tests/test_pd_sky130_pilot.py, in the ``pd-sky130``
workflow). Here stand-in executables exercise the runner: what runs, in what order, over which
files, and that a run which cannot show its counts is a recorded failed run. Stand-ins never
stand in for evidence of a real tool.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from test_nirmaan_physical import AXI, TOP, fake_pv_pdk, fake_tool, invoke, only_on_path

from nirmaan.integrations import pv_magic
from nirmaan.integrations.eda import RunRecord, backends_for
from nirmaan.integrations.pd_parsers import parse_klayout, parse_openroad
from nirmaan.integrations.pv_magic import BACKEND
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ToolAccessDenied

MAGIC_INPUTS = {"magic_tech": "sky130A.tech", "netgen_setup": "setup.tcl", "spice": "cells.spice"}


@pytest.fixture()
def project(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan("Place and route the AXI4-Lite register block.")


def magic_pdk(root: Path) -> dict[str, str]:
    """Stand-in PDK inputs: the stream's (as for KLayout, without its decks) and Magic's and Netgen's."""
    pdk = {k: v for k, v in fake_pv_pdk(root, lvs=False).items() if k != "drc_deck"}
    for key, name in MAGIC_INPUTS.items():
        (root / name).write_text("stand-in\n", encoding="utf-8")
        pdk[key] = str(root / name)
    return pdk


def test_the_backend_is_registered_and_its_inputs_declared(nirmaan_org):
    backend = next(b for b in backends_for("pv.run") if b.name == BACKEND)
    assert backend.executables == ("klayout", "magic", "netgen")
    assert [b.name for b in backends_for("pv.run")].index("klayout") == 0  # KLayout stays the default
    declared = {p.name for p in nirmaan_org.tools["pv.run"].params}
    assert set(MAGIC_INPUTS) <= declared


def test_it_runs_only_when_named_and_with_its_pdk_inputs(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    for exe in ("klayout", "magic", "netgen"):
        fake_tool(bin_dir, exe, 'echo "argv: $*"')
    only_on_path(monkeypatch, bin_dir)
    layout = tmp_path / "route.def"
    layout.write_text("stand-in\n", encoding="utf-8")
    params = {"def": str(layout), "netlist": str(AXI), "top": TOP, **magic_pdk(tmp_path / "pdk")}
    with pytest.raises(ToolAccessDenied, match=f"runs only when named \\(backend: {BACKEND}\\)"):
        invoke(project, "pv.run", params, tmp_path / "unnamed")
    for key, label in (("magic_tech", "Magic technology"), ("netgen_setup", "Netgen setup"), ("spice", "SPICE")):
        with pytest.raises(ToolAccessDenied, match=label):
            invoke(project, "pv.run", {**params, "backend": BACKEND, key: ""}, tmp_path / key)
    with pytest.raises(ToolAccessDenied, match="magic_tech not found"):
        invoke(project, "pv.run", {**params, "backend": BACKEND, "magic_tech": str(tmp_path / "no.tech")},
               tmp_path / "missing")


def test_it_streams_then_checks_in_magic_and_compares_in_netgen(project, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    for exe in ("klayout", "magic", "netgen"):
        fake_tool(bin_dir, exe, 'echo "argv: $*"')
    only_on_path(monkeypatch, bin_dir)
    layout = tmp_path / "route.def"
    layout.write_text("stand-in\n", encoding="utf-8")
    pdk = magic_pdk(tmp_path / "pdk")
    params = {"def": str(layout), "netlist": str(AXI), "top": TOP, "backend": BACKEND, **pdk}
    run, outcome = invoke(project, "pv.run", params, tmp_path / "w")
    # The stand-ins print no counts and Netgen wrote no comparison: a recorded failed run.
    assert not run.succeeded and run.id in project.state.tool_runs
    assert "no GDS written" in run.summary and "no DRC count" in run.summary, run.summary
    steps = outcome.data["commands"]
    assert [s[0] for s in steps[:4]] == ["klayout", "magic", "magic", "netgen"]
    assert steps[0][-1] == "stream.py" and steps[1][-1] == "magic_drc.tcl" and steps[2][-1] == "magic_extract.tcl"
    assert steps[3][-2:] == ["source", "netgen_lvs.tcl"] and steps[4][-3] == "lvs_count.py"
    work = tmp_path / "w"
    drc = (work / "magic_drc.tcl").read_text()
    assert drc.startswith(f'tech load "{pdk["magic_tech"]}"') and f"load {TOP}" in drc and "drc listall why" in drc
    for script in (drc, (work / "magic_extract.tcl").read_text()):  # M81: via cells flattened as Magic reads them
        assert script.index("gds flatglob VIA_*") < script.index("gds read")
    lvs = (work / "netgen_lvs.tcl").read_text()
    assert f'readnet spice "{pdk["spice"]}"' in lvs and f'readnet verilog "{AXI}" $source' in lvs
    assert f'"{pdk["netgen_setup"]}"' in lvs and "-json" in lvs
    # Every cell SPICE file given joins the reference, before the netlist is read over them.
    extra = tmp_path / "pdk" / "more.spice"
    extra.write_text("stand-in\n", encoding="utf-8")
    invoke(project, "pv.run", {**params, "spice": f"{pdk['spice']},{extra}"}, tmp_path / "two")
    two = (tmp_path / "two" / "netgen_lvs.tcl").read_text()
    assert two.index(f'readnet spice "{extra}" $source') < two.index("readnet verilog")


# --- Captured runs (CI, the pd-sky130 workflow) -----------------------------------------------

PD = Path(__file__).parent / "fixtures" / "pd"


def captured(name: str) -> str:
    log = (PD / name).read_text(encoding="utf-8")
    first, rest = log.split("\n", 1)
    assert first.startswith("# CAPTURED:") and "CI run" in first, first
    return rest


def parse(name: str):
    return pv_magic._parse(RunRecord(captured(name), (0, 0, 0, 0, 0), Path("/nonexistent")))


def test_a_clean_run_reports_its_counts_its_style_and_netgens_verdict():
    result = parse("magic_netgen_pv.log")
    m = result.metrics
    assert result.passed, result.summary
    assert m["drc_violations"] == 0 and m["lvs_mismatches"] == 0 and m["gds_empty_cells"] == 0
    assert m["magic_drc_style"] == "drc(full)" and m["gds_shapes_skipped"] == 0
    assert m["netgen_final"] == "Final result: Circuits match uniquely."
    assert result.summary.startswith("physical verification (Magic and Netgen) passed")


def test_a_moved_cell_fails_magic_drc_and_netgen_lvs():
    result = parse("magic_netgen_pv_drc.log")
    m = result.metrics
    assert not result.passed and m["drc_violations"] == 173, result.summary
    assert m["drc_by_rule"]["mcon.spacing_<_0.19um_(mcon.2)"] == 135
    assert m["lvs_mismatches"] > 0 and "sky130_fd_sc_hd__dfxtp_1" in m["lvs_unmatched_circuits"]


def test_a_rewired_netlist_fails_lvs_only():
    result = parse("magic_netgen_pv_lvs.log")
    m = result.metrics
    assert not result.passed and m["drc_violations"] == 0, result.summary
    assert m["lvs_mismatched"]["nets"] == 1 and m["lvs_unmatched_circuits"] == ["sync_fifo"]
    assert m["netgen_final"] == "Final result: Netlists do not match."


def test_shapes_magic_cannot_read_fail_the_run_even_when_the_counts_are_clean():
    """The platform's stream writes metal fill on layers Magic's technology does not read (datatype 28)."""
    result = parse("magic_netgen_pv_fill.log")
    m = result.metrics
    assert m["drc_violations"] == 0 and m["lvs_mismatches"] == 0  # the counts alone would pass it
    assert not result.passed and m["gds_shapes_skipped"] == 4, result.summary
    assert "4 GDS records Magic could not read" in result.summary and "layer=7 type=28" in result.summary



# --- Captured runs (CI, the pd-gf180 workflow, M81) -------------------------------------------


def test_gf180_the_pilot_routes_and_signs_off_clean():
    """The pilot on the ORFS gf180 platform with the open_pdks cell views (docs/PD_GF180_PILOT.md)."""
    pnr = parse_openroad(captured("gf180/openroad_gf180.log"), 0, "extract",
                         ["floorplan", "place", "cts", "route", "extract"])
    assert pnr.passed and pnr.metrics["drc_violations"] == 0, pnr.summary
    assert "worst setup slack 4.059" in pnr.summary and "TNS 0.000 on extracted parasitics" in pnr.summary
    clean = parse("gf180/magic_netgen_pv.log")
    m = clean.metrics
    assert clean.passed and m["drc_violations"] == 0 and m["lvs_mismatches"] == 0, clean.summary
    assert m["magic_drc_style"] == "drc(full)" and m["gds_shapes_skipped"] == 0
    assert m["netgen_final"] == "Final result: Circuits match uniquely."


def test_gf180_both_must_fail_runs_fail():
    overlap = parse("gf180/magic_netgen_pv_drc.log")
    assert not overlap.passed and overlap.metrics["drc_violations"] == 423, overlap.summary
    assert overlap.metrics["drc_by_rule"]["Metal1_spacing_<_0.23um_(M1.2a)"] == 116
    rewired = parse("gf180/magic_netgen_pv_lvs.log")
    assert not rewired.passed and rewired.metrics["drc_violations"] == 0, rewired.summary
    assert rewired.metrics["lvs_mismatched"]["nets"] == 1 and rewired.metrics["lvs_unmatched_circuits"] == ["sync_fifo"]


def test_gf180_what_the_earlier_runs_found():
    """The three findings the fixes answer, each a recorded failed run (docs/PD_GF180_PILOT.md, section 5)."""
    no_map = parse("gf180/magic_netgen_pv_no_layer_map.log")  # no layer_map, vendor cell views
    assert not no_map.passed and no_map.metrics["gds_shapes_skipped"] == 24, no_map.summary
    assert "VIA_" in no_map.summary and no_map.metrics["lvs_mismatched"]["pins"] == 80
    subcells = parse("gf180/magic_netgen_pv_via_subcells.log")  # via cells as subcells, DEF after extraction
    rules = subcells.metrics["drc_by_rule"]
    assert not subcells.passed and rules["This_layer_can't_abut_or_partially_overlap_between_subcells"] == 134240
    assert rules["Metal2_minimum_area_<_0.1444um^2_(M2.3)"] == 405 and subcells.metrics["lvs_mismatches"] == 0
    ir = parse_openroad(captured("gf180/openroad_gf180_ir_drop.log"), 1, "extract",
                        ["floorplan", "place", "cts", "route", "extract"])
    assert not ir.passed and "PSM-0021" in ir.summary, ir.summary  # why the pilot runs without IR drop
    patches = dict(line.removeprefix("diag ").split(" RECT in NETS: ")
                   for line in captured("gf180/patches_diagnostic.log").splitlines() if "RECT in NETS" in line)
    assert patches == {"d1.def": "252", "d2.def": "252", "d3.def": "252", "d4.def": "252", "d5.def": "0",
                       "route.def": "0"}  # the router's patches, until extract_parasitics


def test_gf180_the_pilot_ran_in_ci_with_its_must_fail_controls():
    """The pd-gf180 job's own records from the run on the head that added them (docs/PD_GF180_PILOT.md)."""
    import json

    text = captured("gf180/pilot_run_records.log")
    junit, *records = text.split("\n== ")
    assert 'tests="1"' in junit and 'failures="0"' in junit and 'errors="0"' in junit and 'skipped="0"' in junit
    assert "test_sync_fifo_from_rtl_to_drc_and_lvs_on_gf180mcu" in junit
    by_name = {r.split("\n", 1)[0]: json.loads(r.split("\n", 1)[1]) for r in records}
    pnr, clean, drc, lvs = (by_name[f"{n}.result.json"] for n in
                            ("pnr/openroad", "pv_magic/magic-netgen", "pv_magic_drc/magic-netgen",
                             "pv_magic_lvs/magic-netgen"))
    assert pnr["passed"] and "worst setup slack 4.059" in pnr["summary"]
    assert clean["passed"] and clean["metrics"]["drc_violations"] == 0 and clean["metrics"]["lvs_mismatches"] == 0
    assert not drc["passed"] and drc["metrics"]["drc_violations"] == 423
    assert not lvs["passed"] and lvs["metrics"]["drc_violations"] == 0 and lvs["metrics"]["lvs_mismatched"]["nets"] == 1


TOP_FIFO = "sync_fifo"


def run_count(tmp_path: Path, comparison: str, final: str) -> str:
    """Nirmaan's count script over a captured Netgen JSON, beside a report holding Netgen's final line.

    The JSON files are Netgen's, from CI run 43602071471 (clean and rewired), reserialised without whitespace.
    """
    (tmp_path / "lvs.json").write_text((PD / "netgen" / comparison).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "lvs.report").write_text(f"{final}\n", encoding="utf-8")
    (tmp_path / "lvs_count.py").write_text(pv_magic.LVS_COUNT_SCRIPT, encoding="utf-8")
    done = subprocess.run([sys.executable, "-I", "lvs_count.py", str(tmp_path / "lvs.report"), TOP_FIFO],
                          cwd=tmp_path, capture_output=True, text=True, check=True)
    return done.stdout


def test_the_count_script_reads_netgens_json_not_its_prose(tmp_path):
    clean = parse_klayout(run_count(tmp_path, "clean.json", "Final result: Circuits match uniquely."), 0, ["lvs"])
    assert clean.metrics["lvs_mismatches"] == 0
    rewired = parse_klayout(run_count(tmp_path, "rewired.json", "Final result: Netlists do not match."), 0, ["lvs"])
    assert rewired.metrics["lvs_mismatched"]["nets"] == 1 and rewired.metrics["lvs_mismatched"]["circuits"] == 1
    # Netgen's prose cannot pass a mismatched comparison, and a clean count without a unique match fails.
    forged = parse_klayout(run_count(tmp_path, "rewired.json", "Final result: Circuits match uniquely."), 0, ["lvs"])
    assert forged.metrics["lvs_mismatches"] > 0
    unsure = parse_klayout(run_count(tmp_path, "clean.json", "Final result: Netlists do not match."), 0, ["lvs"])
    assert unsure.metrics["lvs_mismatched"]["circuits"] == 1


# --- Crown jewel: Magic and Netgen need no core changes ------------------------------------------


def test_magic_and_netgen_are_one_backend_and_no_core_change():
    """The module registers one backend and reaches nothing in the engine, the broker, or the policy."""
    tree = ast.parse(Path(pv_magic.__file__).read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imported <= {"__future__", "pathlib", "nirmaan.integrations.eda", "nirmaan.integrations.eda_parsers",
                        "nirmaan.integrations.pd_parsers", "nirmaan.integrations.physical", "nirmaan.models",
                        "nirmaan.runtime.tools"}, imported
    calls = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    assert calls.count("register_backend") == 1

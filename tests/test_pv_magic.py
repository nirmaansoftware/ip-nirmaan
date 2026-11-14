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
from nirmaan.integrations.pd_parsers import parse_klayout
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
    lvs = (work / "netgen_lvs.tcl").read_text()
    assert f'readnet spice "{pdk["spice"]}"' in lvs and f'readnet verilog "{AXI}" $source' in lvs
    assert f'"{pdk["netgen_setup"]}"' in lvs and "-json" in lvs


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


TOP_FIFO = "sync_fifo"


def run_count(tmp_path: Path, comparison: str, final: str) -> str:
    """Nirmaan's count script over a captured Netgen JSON, beside a report holding Netgen's final line."""
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

"""Milestone 79: ``pv.run``'s ``magic-netgen`` backend (Magic DRC and Netgen LVS), without the tools.

The real run is the SKY130 pilot (tests/test_pd_sky130_pilot.py, in the ``pd-sky130``
workflow). Here stand-in executables exercise the runner: what runs, in what order, over which
files, and that a run which cannot show its counts is a recorded failed run. Stand-ins never
stand in for evidence of a real tool.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from test_nirmaan_physical import AXI, TOP, fake_pv_pdk, fake_tool, invoke, only_on_path

from nirmaan.integrations.eda import backends_for
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

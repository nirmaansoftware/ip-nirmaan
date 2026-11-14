"""Milestone 81: the GF180MCU physical design pilot, the M79 pilot block on a second open PDK, for real.

The M26 synchronous FIFO goes through the tool broker on the OpenROAD-flow-scripts ``gf180``
platform (5 metals with a 0.9 um top metal, the 9-track 5 V library): Liberty-mapped synthesis
(``synth.run``), place and route with the power grid, clock tree, and timing (``pnr.run``), then
Magic DRC and Netgen LVS over the open_pdks gf180mcuC files (``pv.run`` backend ``magic-netgen``).
The cells' LEF, GDS and SPICE are open_pdks' build of the same library, which adds the well pins.
Both must be clean. A flip-flop placed half a site over another and a netlist with a flip-flop
input rewired must each fail as recorded runs, so a clean result is not vacuous. The platform ships
no KLayout DRC or LVS deck, so the M34 KLayout backend has nothing to run here.

Collected only where ``NIRMAAN_PD_PILOT`` is set (tests/conftest.py): the ``pd-gf180`` workflow,
which installs the tools and the PDK files (CI only, never on the development machine).
Design: docs/PD_GF180_PILOT.md.
"""

from __future__ import annotations

import gzip
import os
import re
import shutil
from pathlib import Path

import pytest

from laws import needs
from test_nirmaan_physical import invoke

from nirmaan.integrations.physical import PDK_FILES, PDK_ROOT_ENV
from nirmaan.orchestrator import Orchestrator

FIXTURES = Path(__file__).parent / "fixtures"
FIFO = FIXTURES / "rtl" / "sync_fifo" / "sync_fifo.v"
TOP = "sync_fifo"
SDC = FIXTURES / "pd" / "sync_fifo.sdc"
CELL = "gf180mcu_fd_sc_mcu9t5v0__"
#: The platform as its config.mk selects it by default (METAL_OPTION 5LM_1TM, KVALUE 9, TRACK_OPTION
#: 9t, POWER_OPTION 5v0), at the typical corner (CORNER TC: the tt 25 C 5.0 V Liberty, the typical RCX).
#: The cells' views come from open_pdks' build of the same library (gf180mcuC, fetched by the workflow,
#: pinned by sha256): its LEF and GDS add the well and substrate pins VNW and VPW that the vendor files in
#: the platform lack (open_pdks fix_digital_lef.py and fix_stdcell_gds.py). With the platform's LEF and GDS
#: the routed netlist left VNW and VPW unconnected and Magic named the wells itself, so every cell's two well
#: pins went unpaired in LVS (CI run 43612313722).
LIB = "gf180mcuC/libs.ref/gf180mcu_fd_sc_mcu9t5v0"
GF180 = {"tech_lef": f"{LIB}/techlef/{CELL}nom.tlef", "lef": f"{LIB}/lef/gf180mcu_fd_sc_mcu9t5v0.lef"}
LIBERTY_GZ = f"gf180/lib/{CELL}tt_025C_5v00.lib.gz"
GF180_PNR = {
    "site": "GF018hv5v_green_sc9", "hor_layers": "Metal3", "ver_layers": "Metal4",
    "routing_layers": "Metal2,Metal5",
    "tap_cell": f"{CELL}filltie", "endcap_cell": f"{CELL}endcap", "tap_distance": "100",
    "pdn_tcl": "gf180/openROAD/pdn/pdn_grid_strategy_9t_6M.cfg", "rc_tcl": "gf180/setRC.tcl",
    "rcx_rules": "gf180/openROAD/rcx/gf180mcu_1p5m_1tm_9k_sp_smim_OPTB_typ.rules",
    "filler_cells": ",".join(f"{CELL}fill_{n}" for n in (64, 32, 16, 8, 4, 2, 1)),
    # No supply_voltage, so no IR-drop analysis: the technology LEF gives the via cut layers no resistance
    # and setRC.tcl sets one only at the BC and WC corners, so at TC PDNSim refuses the grid (PSM-0021,
    # CI run 43612057949). The grid's connectivity is still checked (check_power_grid).
}
#: The stream reads the DEF through the platform's LEF/DEF layer map file, as ORFS's def2stream does
#: (GDS_LAYER_MAP): the KLayout technology's own map leaves via geometry and pin labels on layers of
#: KLayout's numbering, which Magic skipped (CI run 43612313722).
GF180_PV = {"gds": f"{LIB}/gds/gf180mcu_fd_sc_mcu9t5v0.gds", "klayout_tech": "gf180/KLayout/gf180mcu_5LM_1TM_9K_9t.lyt",
            "layer_map": "gf180/gds/9t/gf180mcu_5LM_1TM_9K_9t_edi2gds.layermap"}
#: The open_pdks gf180mcuC files Magic and Netgen read, which the workflow fetches (pinned by sha256)
#: into the PDK root with their ciel paths.
GF180MCUC_MAGIC = {
    "magic_tech": "gf180mcuC/libs.tech/magic/gf180mcuC.tech",
    "netgen_setup": "gf180mcuC/libs.tech/netgen/gf180mcuC_setup.tcl",
    "spice": "gf180mcuC/libs.ref/gf180mcu_fd_sc_mcu9t5v0/spice/gf180mcu_fd_sc_mcu9t5v0.spice",
}
SIGNOFF = ("drc_violations<=0", "lvs_mismatches<=0")


@pytest.fixture()
def project(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan("Place and route the synchronous FIFO.")


def gf180(*extra: dict[str, str]) -> Path:
    """The PDK root; skip without the gf180 platform and the inputs named, or fail when CI requires OpenROAD."""
    root = Path(os.environ.get(PDK_ROOT_ENV, "") or "/nonexistent")
    paths = [LIBERTY_GZ, *(v for d in (GF180, *extra) for k, v in d.items() if k in PDK_FILES)]
    missing = [p for p in paths if not (root / p).is_file()]
    if missing:
        reason = f"{PDK_ROOT_ENV} has no gf180 platform with {', '.join(missing)}"
        if "openroad" in os.environ.get("NIRMAAN_REQUIRE_EDA", "").split():
            pytest.fail(reason)
        pytest.skip(reason)
    return root


@needs("openroad", "yosys", "klayout", "magic", "netgen")
def test_sync_fifo_from_rtl_to_drc_and_lvs_on_gf180mcu(project, tmp_path, monkeypatch):
    root = gf180(GF180_PNR, GF180_PV, GF180MCUC_MAGIC)
    # The platform's setRC.tcl reads the metal stack and the corner from the environment, as ORFS sets them.
    monkeypatch.setenv("METAL_OPTION", "5LM_1TM")
    monkeypatch.setenv("CORNER", "TC")
    # The platform ships its Liberty gzipped; Yosys's ABC reads plain text, so the run reads a copy.
    liberty = tmp_path / Path(LIBERTY_GZ).stem
    with gzip.open(root / LIBERTY_GZ, "rb") as src, liberty.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    synth, outcome = invoke(project, "synth.run", {
        "sources": str(FIFO), "top": TOP, "backend": "yosys-liberty", "liberty": str(liberty),
        "tie_high": f"{CELL}tieh/Z", "tie_low": f"{CELL}tiel/ZN", "buffer_cell": f"{CELL}buf_4/I/Z"},
        tmp_path / "synth")
    assert synth.succeeded, synth.summary
    netlist = outcome.data["result"]["metrics"]["netlist"]

    # No metal fill: ORFS fills only at chip level (USE_FILL=0 for a block), and the platform's KLayout
    # map would stream fill onto the drawing datatype; see docs/PD_GF180_PILOT.md.
    pnr, outcome = invoke(project, "pnr.run", {"netlist": netlist, "sdc": str(SDC), "top": TOP, **GF180,
                                               "liberty": str(liberty), **GF180_PNR, "utilization": "30",
                                               "timeout": "900"}, tmp_path / "pnr")
    m = outcome.data["result"]["metrics"]
    print(f"pilot pnr: {pnr.summary}")
    assert m["stages_completed"] == ["floorplan", "place", "cts", "route", "extract", "timing"], pnr.summary
    assert m["drc_violations"] == 0 and m["unconnected_supply_pins"] == 0 and pnr.succeeded, pnr.summary
    out = m["outputs"]

    magic_pv = {"def": out["def"], "netlist": out["pg_netlist"], "top": TOP, **GF180, **GF180_PV,
                "backend": "magic-netgen", **GF180MCUC_MAGIC, "timeout": "900"}
    clean, c_outcome = invoke(project, "pv.run", magic_pv, tmp_path / "pv_magic", bounds=SIGNOFF)
    cm = c_outcome.data["result"]["metrics"]
    print(f"pilot magic-netgen: {clean.summary}")
    if cm["drc_violations"]:  # TEMPORARY diagnostic, removed before review
        import subprocess
        work = tmp_path / "pv_magic"
        head = (f'tech load {root / GF180MCUC_MAGIC["magic_tech"]}\ngds flatglob VIA_*\ngds read {work / "layout.gds"}\n'
                f'load {TOP}\nselect top cell\nexpand\ndrc euclidean on\ndrc style drc(full)\ndrc check\ndrc catchup\n')
        (work / "diag.tcl").write_text(head + 'foreach {why boxes} [drc listall why] { foreach b [lrange $boxes 0 30] '
                                       '{ puts "diag-box: $b" } }\nquit -noprompt\n')
        boxes = [tuple(map(int, ln.split()[1:])) for ln in subprocess.run(
            ["magic", "-dnull", "-noconsole", str(work / "diag.tcl")], cwd=work, capture_output=True, text=True
        ).stdout.splitlines() if ln.startswith("diag-box:")]
        picks = [boxes[0], boxes[1], boxes[-1], boxes[-6], boxes[-11]]
        probe = "".join(f'puts "diag-probe {b}"\nbox values {b[0]} {b[1]} {b[2]} {b[3]}\nputs "diag-what [what -list]"\n'
                        f'box grow c 40\nputs "diag-what-grown [what -list]"\n' for b in picks)
        (work / "probe.tcl").write_text(head + probe + "quit -noprompt\n")
        print("\n".join(ln for ln in subprocess.run(["magic", "-dnull", "-noconsole", str(work / "probe.tcl")], cwd=work,
                                                    capture_output=True, text=True).stdout.splitlines() if "diag" in ln)[:6000])
        d = Path(out["def"]).read_text()
        for b in picks:
            cx, cy = (b[0] + b[2]) * 5, (b[1] + b[3]) * 5  # Magic units of 0.005 um to DEF units of 0.0005 um
            near = [ln.strip() for ln in d.splitlines() if any(abs(int(n) - cx) < 1200 for n in re.findall(r"\b\d{4,7}\b", ln))
                    and any(abs(int(n) - cy) < 1200 for n in re.findall(r"\b\d{4,7}\b", ln)) and ("NEW" in ln or "+ ROUTED" in ln or "+ FIXED" in ln or "PLACED" in ln)]
            print(f"diag-near {b} ({cx}, {cy}):\n" + "\n".join(near[:14]))
    assert cm["drc_violations"] == 0 and cm["lvs_mismatches"] == 0 and cm["gds_empty_cells"] == 0, clean.summary
    assert cm["magic_drc_style"] == "drc(full)" and cm["gds_shapes_skipped"] == 0, clean.summary
    assert cm["netgen_final"] == "Final result: Circuits match uniquely.", clean.summary
    assert clean.succeeded and clean.id in project.state.tool_runs, clean.summary

    # Must fail: a flip-flop placed half a site (0.28 um) to the right of another, in its row and
    # orientation, so the two cells' shapes overlap.
    layout = Path(out["def"]).read_text(encoding="utf-8")
    units = int(re.search(r"^UNITS DISTANCE MICRONS (\d+)", layout, re.M)[1])
    flops = list(re.finditer(rf"(- \S+ {CELL}dff\w+ \+ PLACED )\( (\d+) (\d+) \) (\w+)", layout))
    first, other = flops[0], flops[1]
    moved = f"{first[1]}( {int(other[2]) + round(0.28 * units)} {other[3]} ) {other[4]}"
    broken_def = tmp_path / "broken.def"
    broken_def.write_text(layout[:first.start()] + moved + layout[first.end():], encoding="utf-8")
    bad_drc, outcome = invoke(project, "pv.run", {**magic_pv, "def": str(broken_def)}, tmp_path / "pv_magic_drc",
                              bounds=SIGNOFF)
    print(f"pilot magic-netgen, overlapping cell: {bad_drc.summary}")
    assert not bad_drc.succeeded and bad_drc.id in project.state.tool_runs
    assert outcome.data["result"]["metrics"]["drc_violations"] > 0, bad_drc.summary

    # Must fail: a flip-flop's D input rewired to another net in the reference netlist.
    pg = Path(out["pg_netlist"]).read_text(encoding="utf-8")
    d_pins = list(re.finditer(r"\.D\((\w+)\)", pg))
    broken_v = tmp_path / "broken.v"
    broken_v.write_text(pg[:d_pins[0].start()] + f".D({d_pins[1][1]})" + pg[d_pins[0].end():], encoding="utf-8")
    bad_lvs, outcome = invoke(project, "pv.run", {**magic_pv, "netlist": str(broken_v)}, tmp_path / "pv_magic_lvs",
                              bounds=SIGNOFF)
    print(f"pilot magic-netgen, rewired netlist: {bad_lvs.summary}")
    lm = outcome.data["result"]["metrics"]
    assert not bad_lvs.succeeded and lm["lvs_mismatches"] > 0 and lm["drc_violations"] == 0, bad_lvs.summary

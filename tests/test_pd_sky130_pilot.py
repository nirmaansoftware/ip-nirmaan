"""Milestone 79: the SKY130 physical design pilot, one block from RTL to DRC and LVS, for real.

The M26 synchronous FIFO goes through the tool broker on the sky130hd platform: Liberty-mapped
synthesis (``synth.run``), place and route with the power grid, clock tree, fill, and timing
(``pnr.run``), then physical verification twice: with the platform's KLayout decks (M34) and
with Magic DRC and Netgen LVS over the open_pdks SKY130A files (``pv.run`` backend
``magic-netgen``). Both must be clean. A layout with a cell moved off the grid and a netlist
with a flip-flop input rewired must each fail Magic and Netgen as recorded runs, so a clean
result is not vacuous.

Collected only where ``NIRMAAN_PD_PILOT`` is set (tests/conftest.py): the
``pd-sky130`` workflow, which installs the tools and the PDK files (CI only, never on the
development machine). Design: docs/PD_SKY130_PILOT.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from laws import needs
from test_nirmaan_physical import SKY130HD, SKY130HD_PNR, SKY130HD_PV, invoke, sky130hd

from nirmaan.orchestrator import Orchestrator

FIXTURES = Path(__file__).parent / "fixtures"
FIFO = FIXTURES / "rtl" / "sync_fifo" / "sync_fifo.v"
TOP = "sync_fifo"
SDC = FIXTURES / "pd" / "sync_fifo.sdc"
#: The open_pdks SKY130A files Magic and Netgen read, which the workflow fetches (pinned by sha256)
#: into the PDK root with their ciel paths.
SKY130A_MAGIC = {
    "magic_tech": "sky130A/libs.tech/magic/sky130A.tech",
    "netgen_setup": "sky130A/libs.tech/netgen/sky130A_setup.tcl",
    "spice": "sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice",
}
SIGNOFF = ("drc_violations<=0", "lvs_mismatches<=0")


@pytest.fixture()
def project(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan("Place and route the synchronous FIFO.")


@needs("openroad", "yosys", "klayout", "magic", "netgen")
def test_sync_fifo_from_rtl_to_drc_and_lvs_on_sky130(project, tmp_path):
    sky130hd(SKY130HD_PV, SKY130A_MAGIC)
    synth, outcome = invoke(project, "synth.run", {
        "sources": str(FIFO), "top": TOP, "backend": "yosys-liberty", "liberty": SKY130HD["liberty"],
        "tie_high": "sky130_fd_sc_hd__conb_1/HI", "tie_low": "sky130_fd_sc_hd__conb_1/LO",
        "buffer_cell": "sky130_fd_sc_hd__buf_4/A/X"}, tmp_path / "synth")
    assert synth.succeeded, synth.summary
    netlist = outcome.data["result"]["metrics"]["netlist"]

    pnr, outcome = invoke(project, "pnr.run", {"netlist": netlist, "sdc": str(SDC), "top": TOP, **SKY130HD,
                                               **SKY130HD_PNR, "utilization": "30", "timeout": "900"},
                          tmp_path / "pnr")
    m = outcome.data["result"]["metrics"]
    print(f"pilot pnr: {pnr.summary}")
    assert m["stages_completed"] == ["floorplan", "place", "cts", "route", "extract", "timing"], pnr.summary
    assert m["drc_violations"] == 0 and m["unconnected_supply_pins"] == 0 and pnr.succeeded, pnr.summary
    out = m["outputs"]

    pv = {"def": out["def"], "netlist": out["pg_netlist"], "top": TOP, "tech_lef": SKY130HD["tech_lef"],
          "lef": SKY130HD["lef"], "timeout": "900"}
    klayout, k_outcome = invoke(project, "pv.run", {**pv, **SKY130HD_PV}, tmp_path / "pv_klayout", bounds=SIGNOFF)
    print(f"pilot klayout: {klayout.summary}")
    assert klayout.succeeded, klayout.summary

    magic_pv = {**pv, "backend": "magic-netgen", "gds": SKY130HD_PV["gds"],
                "klayout_tech": SKY130HD_PV["klayout_tech"], **SKY130A_MAGIC}
    clean, c_outcome = invoke(project, "pv.run", magic_pv, tmp_path / "pv_magic", bounds=SIGNOFF)
    cm = c_outcome.data["result"]["metrics"]
    print(f"pilot magic-netgen: {clean.summary}")
    assert cm["drc_violations"] == 0 and cm["lvs_mismatches"] == 0 and cm["gds_empty_cells"] == 0, clean.summary
    assert clean.succeeded and clean.id in project.state.tool_runs, clean.summary

    # Must fail: a flip-flop moved 1 nm off the 5 nm grid, so its shapes are off grid and overlap.
    layout = Path(out["def"]).read_text(encoding="utf-8")
    place = re.search(r"(- \S+ sky130_fd_sc_hd__dfxtp_\d \+ PLACED \( )(\d+) ", layout)
    broken_def = tmp_path / "broken.def"
    broken_def.write_text(layout[:place.start()] + place[1] + f"{int(place[2]) + 1} " + layout[place.end():],
                          encoding="utf-8")
    bad_drc, outcome = invoke(project, "pv.run", {**magic_pv, "def": str(broken_def)}, tmp_path / "pv_magic_drc",
                              bounds=SIGNOFF)
    print(f"pilot magic-netgen, moved cell: {bad_drc.summary}")
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

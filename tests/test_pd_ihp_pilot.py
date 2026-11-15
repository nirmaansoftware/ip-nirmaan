"""Milestone 82: the IHP SG13G2 physical design pilot, the M79 pilot block on a third open PDK, for real.

The M26 synchronous FIFO goes through the tool broker on the OpenROAD-flow-scripts ``ihp-sg13g2``
platform (Metal1 to Metal5 and the two thick top metals, the 1.2 V ``sg13g2_stdcell`` library):
Liberty-mapped synthesis (``synth.run``), place and route with the power grid, clock tree, metal fill
and timing (``pnr.run``), then Magic DRC and Netgen LVS over the IHP Open PDK's own Magic technology,
Netgen setup and cell SPICE (``pv.run`` backend ``magic-netgen``). Both must be clean. A flip-flop
placed half a site over another and a netlist with a flip-flop input rewired must each fail as
recorded runs, so a clean result is not vacuous.

Once this run's records are committed (``tests/fixtures/pd/ihp/pilot_run_records.log``), the test
also requires that the run reproduces each recorded result line exactly, so a green ``pd-ihp`` run on
a head is that head's own evidence for the figures the docs give.

Collected only where ``NIRMAAN_PD_PILOT`` is set (tests/conftest.py): the ``pd-ihp`` workflow,
which installs the tools and the PDK files (CI only, never on the development machine).
Design: docs/PD_IHP_PILOT.md.
"""

from __future__ import annotations

import json
import os
import re
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
RECORDS = FIXTURES / "pd" / "ihp" / "pilot_run_records.log"
PLATFORM = "ihp-sg13g2"
#: The platform's cell views and its typical corner (config.mk: TYP_LIB_FILES, the 1.2 V 25 C Liberty).
IHP = {"tech_lef": f"{PLATFORM}/lef/sg13g2_tech.lef", "lef": f"{PLATFORM}/lef/sg13g2_stdcell.lef"}
LIBERTY = f"{PLATFORM}/lib/sg13g2_stdcell_typ_1p20V_25C.lib"
#: As the platform's config.mk sets them: the site, the pin layers (IO_PLACER_H, IO_PLACER_V), the
#: signal layers, the core margin its power ring needs (CORE_MARGIN), its don't-use cells, fillers,
#: power grid, RC script, OpenRCX rules and fill rules. The platform has no tap or endcap cells.
IHP_PNR = {
    "site": "CoreSite", "hor_layers": "Metal3", "ver_layers": "Metal2", "routing_layers": "Metal2,Metal5",
    "core_space": "17.5", "dont_use": "sg13g2_lgcp_1,sg13g2_sighold,sg13g2_slgcp_1,sg13g2_dfrbp_2",
    "filler_cells": "sg13g2_decap_8,sg13g2_decap_4,sg13g2_fill_2,sg13g2_fill_1",
    "pdn_tcl": f"{PLATFORM}/pdn.tcl", "rc_tcl": f"{PLATFORM}/setRC.tcl",
    "rcx_rules": f"{PLATFORM}/rcx_patterns.rules", "fill_rules": f"{PLATFORM}/fill.json",
}
#: The stream reads the DEF through the platform's LEF/DEF layer map file, as ORFS's def2stream does
#: (GDS_LAYER_MAP); its FILL lines are then the fill targets the M80 guard checks (datatype 22).
IHP_PV = {"gds": f"{PLATFORM}/gds/sg13g2_stdcell.gds", "klayout_tech": f"{PLATFORM}/sg13g2.lyt",
          "layer_map": f"{PLATFORM}/sg13g2.map"}
#: The IHP Open PDK files Magic and Netgen read, which the workflow fetches (pinned by sha256) into the
#: PDK root under ihp-open-pdk/ with their paths in the PDK.
PDK = "ihp-open-pdk/ihp-sg13g2"
IHP_MAGIC = {
    "magic_tech": f"{PDK}/libs.tech/magic/ihp-sg13g2.tech",
    "netgen_setup": f"{PDK}/libs.tech/netgen/ihp-sg13g2_setup.tcl",
    "spice": f"{PDK}/libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice",
}
SIGNOFF = ("drc_violations<=0", "lvs_mismatches<=0")


@pytest.fixture()
def project(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan("Place and route the synchronous FIFO.")


def ihp(*extra: dict[str, str]) -> Path:
    """The PDK root; skip without the platform and the inputs named, or fail when CI requires OpenROAD."""
    root = Path(os.environ.get(PDK_ROOT_ENV, "") or "/nonexistent")
    paths = [LIBERTY, *(v for d in (IHP, *extra) for k, v in d.items() if k in PDK_FILES)]
    missing = [p for p in paths if not (root / p).is_file()]
    if missing:
        reason = f"{PDK_ROOT_ENV} has no ihp-sg13g2 platform with {', '.join(missing)}"
        if "openroad" in os.environ.get("NIRMAAN_REQUIRE_EDA", "").split():
            pytest.fail(reason)
        pytest.skip(reason)
    return root


def recorded_summaries() -> dict[str, str]:
    """Each tool run's result line in the committed records, by its run directory and backend."""
    if not RECORDS.is_file():
        return {}
    _header, _junit, *records = RECORDS.read_text(encoding="utf-8").split("\n== ")
    return {r.split("\n", 1)[0]: json.loads(r.split("\n", 1)[1])["result"]["summary"] for r in records}


@needs("openroad", "yosys", "klayout", "magic", "netgen")
def test_sync_fifo_from_rtl_to_drc_and_lvs_on_ihp_sg13g2(project, tmp_path):
    root = ihp(IHP_PNR, IHP_PV, IHP_MAGIC)
    liberty = str(root / LIBERTY)
    synth, outcome = invoke(project, "synth.run", {
        "sources": str(FIFO), "top": TOP, "backend": "yosys-liberty", "liberty": liberty,
        "tie_high": "sg13g2_tiehi/L_HI", "tie_low": "sg13g2_tielo/L_LO", "buffer_cell": "sg13g2_buf_1/A/X"},
        tmp_path / "synth")
    assert synth.succeeded, synth.summary
    netlist = outcome.data["result"]["metrics"]["netlist"]

    pnr, outcome = invoke(project, "pnr.run", {"netlist": netlist, "sdc": str(SDC), "top": TOP, **IHP,
                                               "liberty": liberty, **IHP_PNR, "utilization": "30",
                                               "timeout": "900"}, tmp_path / "pnr")
    m = outcome.data["result"]["metrics"]
    print(f"pilot pnr: {pnr.summary}")
    assert m["stages_completed"] == ["floorplan", "place", "cts", "route", "extract", "timing"], pnr.summary
    assert m["drc_violations"] == 0 and m["unconnected_supply_pins"] == 0 and pnr.succeeded, pnr.summary
    out = m["outputs"]

    magic_pv = {"def": out["def"], "netlist": out["pg_netlist"], "top": TOP, **IHP, **IHP_PV,
                "backend": "magic-netgen", **IHP_MAGIC, "timeout": "900"}
    clean, c_outcome = invoke(project, "pv.run", magic_pv, tmp_path / "pv_magic", bounds=SIGNOFF)
    cm = c_outcome.data["result"]["metrics"]
    print(f"pilot magic-netgen: {clean.summary}")
    assert cm["drc_violations"] == 0 and cm["lvs_mismatches"] == 0 and cm["gds_empty_cells"] == 0, clean.summary
    assert cm["magic_drc_style"] == "drc(full)" and cm["gds_shapes_skipped"] == 0, clean.summary
    assert cm["netgen_final"] == "Final result: Circuits match uniquely.", clean.summary
    assert clean.succeeded and clean.id in project.state.tool_runs, clean.summary

    # Must fail: a flip-flop placed half a site (0.24 um) to the right of another, in its row and
    # orientation, so the two cells' shapes overlap.
    layout = Path(out["def"]).read_text(encoding="utf-8")
    units = int(re.search(r"^UNITS DISTANCE MICRONS (\d+)", layout, re.M)[1])
    flops = list(re.finditer(r"(- \S+ sg13g2_df\w+ \+ PLACED )\( (\d+) (\d+) \) (\w+)", layout))
    first, other = flops[0], flops[1]
    moved = f"{first[1]}( {int(other[2]) + round(0.24 * units)} {other[3]} ) {other[4]}"
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

    # The committed records, once they exist, are this run's results: every result line reproduced.
    recorded = recorded_summaries()
    if recorded:
        runs = ("pnr/openroad", "pv_magic/magic-netgen", "pv_magic_drc/magic-netgen", "pv_magic_lvs/magic-netgen")
        assert recorded == {f"{r}.result.json": json.loads((tmp_path / f"{r}.result.json").read_text(
            encoding="utf-8"))["result"]["summary"] for r in runs}

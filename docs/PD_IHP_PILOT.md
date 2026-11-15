# The IHP SG13G2 physical design pilot (Milestone 82)

The M79 pilot (`docs/PD_SKY130_PILOT.md`) and the M81 pilot
(`docs/PD_GF180_PILOT.md`) on a third open PDK: the same block from RTL to DRC
and LVS, on GitHub-hosted runners only, on the OpenROAD-flow-scripts
`ihp-sg13g2` platform with Magic and Netgen over the IHP Open PDK's own Magic
technology, Netgen setup and cell SPICE. CI runners only, never a development
machine.

## 1. Decisions

**A sibling workflow.** `.github/workflows/pd-ihp.yml` is a sibling of
`pd-sky130.yml` and `pd-gf180.yml`, as M81 chose: a matrix would rewrite the
other two jobs' PDK steps and rename their checks. All three share the image
digest, the Magic and Netgen tags and commits, and the Magic and Netgen cache
key.

**No flow change.** `pnr.run`, `pv.run` and the `magic-netgen` backend run on
this PDK as M79 to M81 left them: this milestone changes no code under `src/`.
The pilot passes the platform's own settings as parameters (section 2).

**With metal fill.** Unlike M79 and M81, the pilot fills: the platform ships
fill rules (`fill.json`), and its LEF/DEF layer map file sends fill to the
PDK's fill datatype (its `FILL` lines, datatype 22), which the M80 guard takes
as the fill targets (`layer_map`, M81) and which Magic's GDS input reads as the
metal fill layers. The guard did not trip (section 5), so no fill mapping fix
was needed.

**The records are the run's own, and checked again on every run.** The
figures in section 5 come from the committed records in
`tests/fixtures/pd/ihp/` (each file's first line names its CI run and head),
read back through Nirmaan's own parsers by the `test_ihp_*` tests in
`tests/test_pv_magic.py`, which run in the required jobs. Once the records are
committed, the pilot test also requires its own run to reproduce each recorded
result line exactly, so a green `pd-ihp` run on a head shows the recorded
figures on that head. `pd-ihp` triggers on the records, this document and the
M82 history file as well as on the flow.

## 2. The platform and the PDK files

The platform is the image's `flow/platforms/ihp-sg13g2` with its `config.mk`
settings: the typical corner Liberty (`sg13g2_stdcell_typ_1p20V_25C.lib`), the
technology and cell LEF and the cell GDS, site `CoreSite`, pins on Metal3
(horizontal) and Metal2 (vertical), signals on Metal2 to Metal5, the core margin
its power ring needs (`CORE_MARGIN` 17.5 um, as `core_space`), its don't-use
cells (`sg13g2_lgcp_1`, `sg13g2_sighold`, `sg13g2_slgcp_1`, `sg13g2_dfrbp_2`),
its fillers and decaps, `pdn.tcl` (a TopMetal1 and TopMetal2 ring, Metal1
rails, TopMetal1 and TopMetal2 straps), `setRC.tcl`, the OpenRCX rules
(`rcx_patterns.rules`), the fill rules (`fill.json`), the KLayout technology
(`sg13g2.lyt`) and the LEF/DEF layer map file (`sg13g2.map`). The platform has
no tap or endcap cells, so the pilot places none. Synthesis uses its tie cells
(`sg13g2_tiehi`, `sg13g2_tielo`) and `sg13g2_buf_1` for port buffers, as its
`config.mk` names them.

The layer map file is passed as `layer_map` (M81): the technology names it by
a path relative to the technology file, and `pv.run` streams with its own copy
of the technology written in the run's directory.

Magic and Netgen read the IHP Open PDK's own files, which open_pdks does not
build for this PDK: `libs.tech/magic/ihp-sg13g2.tech` and the four files it
includes (GDS input and output, DRC, extraction), `libs.tech/netgen/
ihp-sg13g2_setup.tcl`, and `libs.ref/sg13g2_stdcell/spice/sg13g2_stdcell.spice`.
They come from the ciel release `ihp-sg13g2-5e6d592e4002946a4616f798c357f0f3c06cf3b6`
(IHP-GmbH/IHP-Open-PDK commit `5e6d592e`, 2026-09-01), the `common` and
`sg13g2_stdcell` archives, each checked by sha256 before it is read. The
workflow puts them under `ihp-open-pdk/` in the PDK root, because the platform
directory there is also named `ihp-sg13g2`. The archives are read with the
`zstandard` Python package pinned by version and by the sha256 of its wheel and
source archive (`uv pip install --require-hashes`).

## 3. The pilot

`tests/test_pd_ihp_pilot.py`, collected only under `NIRMAAN_PD_PILOT`
(`tests/conftest.py`), so the required jobs neither run nor skip it:

* `synth.run` (`yosys-liberty`) at the typical corner;
* `pnr.run` at 30% utilization with the power grid, CTS, metal fill,
  extraction and timing on the extracted parasitics;
* `pv.run` with `magic-netgen`: Magic DRC in `drc(full)` and Netgen LVS, both
  clean, every GDS record read, every fill shape on a mapped fill layer;
* must fail: a flip-flop placed half a site (0.24 um) to the right of
  another, in its row and orientation, must fail Magic DRC; a flip-flop's D
  input rewired in the reference netlist must fail Netgen LVS with DRC clean;
* once records are committed: each of the four tool runs' result lines equals
  the recorded one.

## 4. Licences

Each read from the project's own licence file or file header upstream. Nothing
of any of them is committed, so NOTICE does not change.

| What | Version | Licence (upstream file) |
|---|---|---|
| IHP Open PDK (`IHP-GmbH/IHP-Open-PDK`) | `5e6d592e`, ciel `ihp-sg13g2-5e6d592e` | Apache 2.0 (`LICENSE`) |
| ORFS `ihp-sg13g2` platform | in the image (`26Q3-687-gc63a606f9`) | no licence file in the platform directory; its `Readme.md` says the PDK is released under Apache 2.0, and its layer map file carries the IHP PDK Authors' Apache 2.0 header |
| `zstandard` (`indygreg/python-zstandard`) | 0.25.0 | BSD 3-Clause (`LICENSE`) |
| OpenROAD-flow-scripts, OpenROAD, KLayout, Magic, Netgen | as M79 | as M79 (`docs/PD_SKY130_PILOT.md`, section 4) |

## 5. Results

From CI run 43639949127 (head 1465f3e), the run whose code is the code that
merges (the commits after it add only these records, their tests and docs). The
record: `tests/fixtures/pd/ihp/` (`openroad_ihp.log` unedited; the three Magic
and Netgen logs as excerpts whose rule each file's first line states;
`pilot_run_records.log`, the junit report and the four tool result records as
the run wrote them).

| Run | Result |
|---|---|
| `pnr.run`, sync_fifo, ihp-sg13g2, 100 MHz (`openroad_ihp.log`) | routed, filled and extracted: 0 router DRC violations, wirelength 11646 um, utilization 34%, power grid connected, 3616 fill shapes, clock skew 0.010 ns, worst setup slack 6.052 ns, hold 0.431 ns, TNS 0 on extracted parasitics |
| `pv.run`, Magic and Netgen (`magic_netgen_pv.log`) | Magic `drc(full)`: 0 violations, every GDS record read; the 3616 fill shapes all on datatype 22 of Metal2 to Metal5, TopMetal1 and TopMetal2 (none unmapped); Netgen: "Circuits match uniquely", 0 mismatches |
| a flip-flop half a site over another (`magic_netgen_pv_drc.log`) | failed: 1524 Magic DRC violations (`M1.b` 652, `Cnt.b` 324, `Gat.b` 227, ...) and an LVS mismatch |
| a D input rewired (`magic_netgen_pv_lvs.log`) | failed: LVS, 1 mismatched net in `sync_fifo`; DRC 0 |

The pilot test took 354 s in that run (its junit report). The owners can decide
from this whether `pd-ihp` becomes required.

## 6. Not in this milestone

* KLayout DRC and LVS with the platform's own decks (`drc/sg13g2_minimal.lydrc`,
  `lvs/sg13g2.lvs`): not run here.
* Metal density: the PDK's Magic DRC rules (`ihp-sg13g2-drc.tech`) have no
  density rule, and the PDK's own density check (`check_density.py`) was not
  run, so density was not checked.
* IR drop: the pilot gives no `supply_voltage`, so no IR-drop analysis ran.
* Making `pd-ihp` a required check.

# The SKY130 physical design pilot (Milestone 79)

A physical design pilot in CI: one pilot block from RTL to DRC and LVS on an
open PDK, on GitHub-hosted runners only. The tools (OpenROAD-flow-scripts,
KLayout, Magic, Netgen) and the open PDKs (SKY130, GF180MCU, IHP SG13G2) are
pending the founder's decision; no committed record of that decision exists
yet. CI runners only, never a development machine. This milestone covers SKY130;
GF180MCU and IHP SG13G2 are follow-ups.

## 1. What already existed, and the gap

M27, M29 and M34 already run synthesis, place and route, signoff timing, and
KLayout DRC and LVS on the sky130hd platform in the required `physical-design`
job, over the AXI4-Lite register block (`docs/PHYSICAL_DESIGN.md`,
`docs/PD_SIGNOFF.md`, `docs/PD_FINAL.md`). Two things were missing:

* **Magic and Netgen**, the DRC and LVS tools the SKY130 open-source signoff
  flows use with the open_pdks rule files. M34 found neither in the image, so
  `pv.run` could judge a layout only with the platform's KLayout decks.
* **A pilot block of the product's own**, run end to end as its own job, so
  the flow can change without touching the required checks.

## 2. Decision: a second `pv.run` backend, not a new tool

Magic DRC and Netgen LVS answer the same question as the KLayout backend, so
they are a backend of `pv.run` (`magic-netgen`, `integrations/pv_magic.py`),
one `register_backend` call with no EDA core change. Its counts are printed
as the same `nirmaan-*` lines the KLayout scripts print, so `parse_klayout`
judges both and the physical-verification gate's bounds
(`drc_violations<=0`, `lvs_mismatches<=0`) read either. The tool stays
`AVAILABLE` (it was since M34), so no count changes.

It runs only when named (`backend: magic-netgen`): KLayout stays the default,
and every run records which tools judged it.

### Steps

| Step | Executable | What |
|---|---|---|
| stream | `klayout` | The routed DEF to GDS with the cells' GDS merged in: the M34 stream script, unchanged |
| DRC | `magic` | The PDK's Magic technology file; `gds read`, `drc check` in the full rule set (`drc(full)`, the open_pdks name; the style that ran is recorded as `magic_drc_style`), then Nirmaan's Tcl counts each rule `drc listall why` reports |
| extract | `magic` | The same GDS extracted to SPICE (`extract all`, `ext2spice lvs`) |
| LVS | `netgen` | The extracted layout against the routed netlist with supply pins (`pnr.run`'s `pg_netlist`), read over the cells' SPICE, under the PDK's Netgen setup, written as JSON |
| count | this Python | Nirmaan's own script reads Netgen's JSON and prints mismatched circuits, nets, devices and pins |

Pass means every step exited 0, the GDS has no empty cell, Magic read every
GDS record, DRC counted 0, and the LVS count found no mismatch and Netgen's
final result is a unique match (`netgen_final`). A run that cannot show a
count is a recorded failed run.

Two rules came from the first real runs:

* **Magic skips a shape it cannot read and goes on.** `Error while reading
  cell ...: Unknown layer/datatype` is not fatal to Magic, so its checks would
  judge a layout with shapes missing. Each such record fails the run
  (`gds_shapes_skipped`; captured: `magic_netgen_pv_fill.log`).
* **The count reads Netgen's JSON, not its prose.** Per circuit pair: nets that
  differ in number or that Netgen could not match (`badnets`), devices that
  differ in number per class or that it could not match (`badelements`), and
  pins that did not pair. A clean count without Netgen's unique match still
  fails, and Netgen's prose cannot pass a mismatched count (tested on the
  captured JSON). Netgen treats a cell instance as a device, so a wrong
  instance is counted under devices and `subcircuits` is always 0 here.

### Parameters (declared on `pv.run`)

`magic_tech` (the PDK's `.tech`), `netgen_setup` (the PDK's setup `.tcl`),
`spice` (the cells' SPICE), plus the stream's `tech_lef`, `lef`, `gds` and
`klayout_tech`. All are PDK files: relative paths resolve under
`NIRMAAN_PDK_ROOT`, a missing one is a refusal, and no PDK is bundled.

## 3. The pilot and its workflow

The block is the M26 synchronous FIFO (`tests/fixtures/rtl/sync_fifo`), the
smaller of the two the plan named (sync_fifo or timer), at 100 MHz
(`tests/fixtures/pd/sync_fifo.sdc`). `tests/test_pd_sky130_pilot.py` runs
it through the broker: `synth.run` (`yosys-liberty`), `pnr.run` on sky130hd
(power grid, CTS, extraction, timing; no metal fill, see section 6), then
`pv.run` with KLayout and with Magic and Netgen, both clean. Two must-fail
runs keep the clean result from being vacuous: a flip-flop moved 0.23 um
(half a site) into its neighbour must fail Magic DRC, and a flip-flop input
rewired in the reference netlist must fail Netgen LVS. (M34's 1 nm off-grid
move fails KLayout's off-grid rule; Magic snaps the GDS to its own grid and
found nothing, so the pilot moves the cell far enough to collide.)

`.github/workflows/pd-sky130.yml`, on `ubuntu-24.04`:

* in the same OpenROAD-flow-scripts image as `ci.yml`, pinned by digest
  (OpenROAD, Yosys, KLayout, the sky130hd platform);
* Magic and Netgen built from release tags, each checked against its commit,
  and cached by commit;
* the three open_pdks SKY130A files Magic and Netgen read
  (`sky130A.tech`, `sky130A_setup.tcl`, `sky130_fd_sc_hd.spice`), from the
  same ciel release `ci.yml` already pins, each archive checked by sha256;
* triggers: `workflow_dispatch`, and pull requests and pushes to `main` that
  touch the flow (`physical.py`, `pv_magic.py`, `pd_parsers.py`), the pilot
  test, its SDC, or the block's RTL;
* not a required check. The owners decide whether it becomes one from its
  measured time (section 5).

The pilot test is collected only where `NIRMAAN_PD_PILOT` is set
(`tests/conftest.py`), so the required jobs neither run nor skip it and
`test-union` is unchanged. The backend's own tests, with stand-in executables,
run everywhere (`tests/test_pv_magic.py`).

## 4. Tools, PDK and licences

Each licence is read from the project's own licence file upstream. Nothing of
any of them is committed here: the tools are built or pulled in CI, the PDK
files are fetched in CI, so NOTICE does not change.

| What | Version | Licence (upstream file) |
|---|---|---|
| OpenROAD-flow-scripts image | `26Q3-687-gc63a606f9`, by digest (as `ci.yml`) | BSD 3-Clause for the build and run scripts (`LICENSE_BUILD_RUN_SCRIPTS`) |
| OpenROAD (in the image) | submodule `c487fc70` | BSD 3-Clause (`LICENSE`) |
| KLayout (in the image) | 0.30.12 | GNU GPL version 3 (`LICENSE`) |
| Magic | 8.3.686 (`56319630`) | University of California permission notice (`LICENSE`) |
| Netgen | 1.5.325 (`85bddb8f`) | GNU GPL version 1 (`Copying`) |
| SKY130 PDK, open_pdks build | ciel release `sky130-ff08c23d` (`common`, `sky130_fd_sc_hd`) | Apache 2.0 (`google/skywater-pdk` and `skywater-pdk-libs-sky130_fd_sc_hd` `LICENSE`; `open_pdks` `LICENSE`) |

Magic's notice ends: "Export of this software outside of the United States of
America may require an export license." The runners only run it; nothing is
redistributed. That sentence is flagged for the owners in the pull request.

## 5. Results

From the pull request's own runs of `pd-sky130` (run 43602071471, head
294435a; excerpts of the logs in `tests/fixtures/pd/magic_netgen_pv*.log` and
Netgen's JSON in `tests/fixtures/pd/netgen/`):

| Run | Result |
|---|---|
| `pnr.run`, sync_fifo, sky130hd, 100 MHz | routed and extracted: 0 router DRC violations, wirelength 6111 um, utilization 34%, power grid connected, clock skew 0.002 ns, worst setup slack 6.006 ns, hold 0.628 ns, TNS 0 on extracted parasitics |
| `pv.run`, KLayout decks | DRC clean, LVS clean |
| `pv.run`, Magic and Netgen | Magic `drc(full)`: 0 violations; Netgen: "Circuits match uniquely" (the top and its 32 cell types, 0 mismatches) |
| a flip-flop moved 0.23 um | failed: 173 Magic DRC violations (`mcon.2` 135, `li.c2` 18, `li.3` 18), and an LVS mismatch |
| a D input rewired | failed: LVS, 1 mismatched net in `sync_fifo`; DRC 0 |

CI time, measured on the pull request's runs: about 2.3 minutes a run. Run
43602071471 (Magic and Netgen built, PDK files fetched) took 2 min 12 s; run
43602677980 (both restored from the cache) 2 min 19 s. Of that, pulling the
image takes about a minute and the pilot test 41 to 53 s, well inside the
45 minute limit and a GitHub-hosted runner's memory and disk.

## 6. Found, not fixed here: the sky130hd stream drops fill to unread layers

The platform's KLayout technology (`sky130hd.lyt` in the image) maps every
drawing, pin and label purpose to its SKY130 GDS layer, but has no entry for
the fill purpose (`.FILL`, datatype 28). So the M34 stream writes metal fill
on layers KLayout numbers itself (7/28, 9/28, 11/28, 13/28 in the first run),
which Magic reports as unknown and which, as far as this pilot can tell, the
KLayout DRC deck does not read either. M34's "DRC clean on the filled layout"
therefore most likely did not check the fill shapes. The pilot runs without
fill, so every shape it signs off is read; mapping fill to SKY130's fill
datatypes in the stream is a follow-up for the physical design owners.

## 7. Not in this milestone

* GF180MCU and IHP SG13G2 (pending the founder's decision; follow-ups, one PDK per pull request).
* The OpenROAD-flow-scripts `make` flow itself: `pnr.run` keeps its own
  script, and the image supplies the tools and the platform.
* Making `pd-sky130` a required check, or adding the backend to a workflow's
  gate (the physical-verification stage still names no backend).

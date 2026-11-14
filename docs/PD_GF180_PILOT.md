# The GF180MCU physical design pilot (Milestone 81)

The M79 pilot (`docs/PD_SKY130_PILOT.md`) on a second open PDK: the same
block from RTL to DRC and LVS, on GitHub-hosted runners only, on the
OpenROAD-flow-scripts `gf180` platform with Magic and Netgen over the open_pdks
GF180MCU files. Use of GF180MCU in CI is pending the founder's
decision; no committed record of that decision exists yet. CI runners only,
never a development machine. IHP SG13G2 is a
separate follow-up.

## 1. Decisions

**A sibling workflow.** `.github/workflows/pd-gf180.yml` is a sibling of
`pd-sky130.yml`, not one matrix over both. A matrix would rewrite the SKY130
job's PDK step (other archives, files and hashes) and rename its check; the
sibling leaves `pd-sky130` untouched. The two share the image digest, the
Magic and Netgen tags and commits, and the Magic and Netgen cache key.

**Three fixes at the root, each found by a CI run of this pilot** (section 5).
Every one applies to any PDK, and none loosens a check:

| Where | Change | Found by |
|---|---|---|
| `pnr.run` (`physical.py`) | The DEF and both netlists are written right after routing, before extraction | OpenRCX dropped the router's 252 minimum-area patches from the layout written after it |
| `pv.run` stream (`physical.py`) | Optional PDK file `layer_map`: the DEF is read through the PDK's LEF/DEF layer map file, as ORFS's `def2stream` reads `GDS_LAYER_MAP`; the M80 fill guard then checks the file's `FILL` layers | via geometry and pin labels landed on layers of KLayout's own numbering |
| `magic-netgen` (`pv_magic.py`) | Magic flattens the stream's via cells (`gds flatglob VIA_*`) as it reads the GDS, for DRC and extraction | 134240 "can't abut or partially overlap between subcells" errors between stacked via cells |

## 2. The platform and the PDK files

The platform is the image's `flow/platforms/gf180` as its `config.mk`
selects it by default: metal stack `5LM_1TM` with a 0.9 um top metal (`9K`),
the 9-track 5 V library `gf180mcu_fd_sc_mcu9t5v0`, the typical corner
(`tt_025C_5v00` Liberty, the `OPTB_typ` OpenRCX rules). From the platform:
the Liberty (gzipped; the test reads a decompressed copy in the run's
directory), the site, the power grid script (`pdn_grid_strategy_9t_6M.cfg`:
Metal1 rails, Metal4 and Metal5 straps), `setRC.tcl` (it reads
`METAL_OPTION` and `CORNER` from the environment, as ORFS sets them), the tap,
endcap and distance of its `tapcell.tcl`, its fillers, pins on Metal3 and
Metal4, signals on Metal2 to Metal5, its KLayout technology and its LEF/DEF
layer map file (`gf180mcu_5LM_1TM_9K_9t_edi2gds.layermap`).

**The cells' views are open_pdks', not the platform's.** The platform's LEF
and GDS are the vendor files, which have no well and substrate pins: its LEF
has no `VNW` or `VPW` pin and its GDS labels neither well. So the routed
netlist left them unconnected and Magic named the wells itself, and every
cell's two well pins went unpaired in LVS (run 43612313722: 80 pins). open_pdks
adds both (`fix_digital_lef.py`, `fix_stdcell_gds.py`). The pilot reads the
open_pdks build of the same library: its technology LEF
(`gf180mcu_fd_sc_mcu9t5v0__nom.tlef`, the vendor's with `Nwell` and `Pwell`
added), cell LEF, cell GDS and SPICE.

Magic and Netgen read the variant with the platform's stack, **gf180mcuC**
(open_pdks: `METALS5 | MIM | THICKMET0P9`, full stack `5LM_1TM_9K`):
`gf180mcuC.tech` and `gf180mcuC_setup.tcl`. All six open_pdks files come from
the ciel release `gf180mcu-792ef67037d74c8c51811eab3ce23cf793491296`
(open_pdks commit `792ef670`, 2026-10-19), the `common` and
`gf180mcu_fd_sc_mcu9t5v0` archives, each checked by sha256 before it is read,
as M79 fetched SKY130.

## 3. The pilot

`tests/test_pd_gf180_pilot.py`, collected only under `NIRMAAN_PD_PILOT`
(`tests/conftest.py`), so the required jobs neither run nor skip it:

* `synth.run` (`yosys-liberty`) with the platform's tie cells (`tieh`,
  `tiel`) and `buf_4` for port buffers;
* `pnr.run` at 30% utilization with the power grid, CTS, extraction and
  timing on the extracted parasitics; no metal fill and no IR-drop analysis
  (section 5);
* `pv.run` with `magic-netgen`: Magic DRC in `drc(full)` and Netgen LVS, both
  clean, every GDS record read;
* must fail: a flip-flop placed half a site (0.28 um) to the right of
  another, in its row and orientation, must fail Magic DRC; a flip-flop's D
  input rewired in the reference netlist must fail Netgen LVS with DRC clean.

The platform ships no KLayout DRC or LVS deck, so the M34 `klayout` backend
has nothing to run here (section 5).

## 4. Licences

Each read from the project's own licence file upstream. Nothing of any of them
is committed, so NOTICE does not change.

| What | Version | Licence (upstream file) |
|---|---|---|
| GF180MCU PDK (`google/gf180mcu-pdk`) | open_pdks build, ciel `gf180mcu-792ef670` | Apache 2.0 (`LICENSE`) |
| `gf180mcu_fd_sc_mcu9t5v0` (`google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu9t5v0`) | the same release | Apache 2.0 (`LICENSE`) |
| open_pdks (`RTimothyEdwards/open_pdks`) | `792ef670` | Apache 2.0 (`LICENSE`) |
| ORFS `gf180` platform | in the image (`26Q3-687-gc63a606f9`) | no licence file in the platform directory, where ORFS's README says platform licences are; its cell data is the library above |
| OpenROAD-flow-scripts, OpenROAD, KLayout, Magic, Netgen | as M79 | as M79 (`docs/PD_SKY130_PILOT.md`, section 4) |

## 5. Results, and what the runs found

From the pull request's own runs of `pd-gf180` (run 43616066140, head 65d619d):

| Run | Result |
|---|---|
| `pnr.run`, sync_fifo, gf180, 100 MHz | routed and extracted: 0 router DRC violations, wirelength 15268 um, utilization 34%, power grid connected, clock skew 0.010 ns, worst setup slack 4.059 ns, hold 1.000 ns, TNS 0 on extracted parasitics |
| `pv.run`, Magic and Netgen | Magic `drc(full)`: 0 violations, every GDS record read; Netgen: "Circuits match uniquely", 0 mismatches |
| a flip-flop half a site over another | failed: 423 Magic DRC violations (`M1.2a` 116, `CO.2a` 88, `CO.7` 58, ...) and an LVS mismatch |
| a D input rewired | failed: LVS, 1 mismatched net in `sync_fifo`; DRC 0 |

**CI time:** 2 min 19 s for the job (run 43616066140); pulling the image
takes about a minute, the open_pdks fetch 7 s, the pilot test 51 s. The owners
can decide from this whether it becomes required.

What the earlier runs of this pull request found, in order:

1. **IR drop** (run 43612057949). PDNSim refused the grid (`PSM-0021`,
   invalid resistance map): the technology LEF gives the via cut layers no
   resistance, and `setRC.tcl` sets one only at the BC and WC corners. The
   pilot runs at TC without `supply_voltage`, so without IR-drop analysis; the
   grid's connectivity is still checked (`check_power_grid`).
2. **Layer map** (run 43612313722). With the platform's KLayout technology
   alone, the stream left the via cells' geometry on layers of KLayout's own
   numbering (24 GDS records Magic could not read, which the M79 rule fails)
   and the pin labels too (Magic ignores labels on unknown layers, so the top
   cell's ports had no names). ORFS itself streams through the layer map file
   (`GDS_LAYER_MAP`), which `pv.run` now takes as `layer_map`. The same run
   found the well pins (section 2).
3. **Via cells in Magic** (run 43613127358). With the vias read, Magic counted
   134240 "This layer can't abut or partially overlap between subcells"
   errors: each via cell is a subcell, and stacked vias in separate subcells
   break its exact-overlap rules for contacts. Flattening the via cells as
   Magic reads them removed all of them; the geometry is the same.
4. **Minimum-area patches** (runs 43613534207 to 43615692267). Magic then found
   Metal2 and Metal3 islands under the minimum area (`M2.3`, `M3.3`,
   0.1444 um2), for example a 0.28 by 0.38 um Metal2 pad between a via1 and a
   via2 stacked on a cell pin. The router had patched them (252 patch
   rectangles in a DEF written right after `detailed_route`), but
   `extract_parasitics` reorders the wires and drops the patches, and
   `pnr.run` wrote its DEF after extraction. It now writes the layout before
   extraction, and the same routing is clean.

**Not changed, stated for the owners:**

* **No KLayout deck.** The ORFS `gf180` platform ships no KLayout DRC or LVS
  deck; the GF180MCU PDK's own KLayout DRC runs from its Python runner with
  options of its own, which `pv.run`'s `klayout` backend does not drive. So on
  GF180MCU, DRC and LVS are Magic's and Netgen's only.
* **Metal fill.** Not run, as ORFS fills only at chip level (`USE_FILL=0` for
  a block). Fill would not trip the M80 guard: with `layer_map` the targets
  are the file's `FILL` lines (datatype 4, the PDK's dummy metal), and the
  platform's KLayout map, used without the file, sends fill to the drawing
  datatype 0, also a mapped target. No fill was checked by either deck here.
* **Earlier pilots.** M29 and M34 wrote their DEF after extraction too, so
  their layouts lacked any minimum-area patches. M34's note that the KLayout
  deck found met3 islands under the minimum area where via2 and via3 stack
  (why sky130hd signals stop at met3) is most likely this cause. Not re-tested
  here: `pd-sky130` and `physical-design` stay green with the fix.

## 6. Not in this milestone

* IHP SG13G2 (approved; its own pull request).
* KLayout DRC and LVS on GF180MCU (section 5).
* Metal fill and IR drop on GF180MCU (section 5).
* Lifting sky130hd's met1 to met3 routing limit (section 5).
* Making `pd-gf180` a required check.

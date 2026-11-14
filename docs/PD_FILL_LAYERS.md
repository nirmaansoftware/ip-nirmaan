# Metal fill on the layers the DRC deck reads (M80)

M34 put metal fill into the routed sky130hd layout and reported "DRC clean on
the filled layout". M79 found that the stream to GDS wrote the fill to layers
no deck reads. This milestone confirms that in CI, streams the fill to layers
the KLayout deck checks, and adds a control that fails when the deck does not
see a broken fill shape. History: `docs/history/M80-pd-fill-layers.md`.

---

## 1. The finding, confirmed

KLayout's DEF reader names a fill shape's layer `<layer><fill suffix>` and
looks that name up in the technology's LEF/DEF layer map. The sky130hd
technology in the ORFS image (`sky130hd.lyt`) sets the fill suffix `.FILL` and
datatype 28, and maps every `.drawing`, `.pin` and `.label` name, but no
`.FILL` name. KLayout then gives each fill layer a number of its own, with
datatype 28.

The platform's DRC deck (`sky130hd.lydrc`) reads metal as `67/*` to `72/*`
(li1, met1 to met5, every datatype but labels and vias). Layers of KLayout's
own numbering are outside it, so the deck never saw the fill.

**Confirmed in CI** (run 43607383342, head 3bd6aa2, the `physical-design`
job, before the fix): the clean AXI4-Lite run's 12947 fill shapes were on
`7/28` (2969), `9/28` (4219), `11/28` (5114) and `13/28` (645), met2 to met5 in
order, and a met2 fill rectangle shrunk to 0.1 um square
(`- LAYER met2 RECT ( 33210 2720 ) ( 34210 3720 )`, now 100 by 100 database
units) still gave "physical verification passed: ... DRC clean". The deck had
checked the routing and the cells, never the fill. M34's "DRC 0 on the filled
layout" is corrected in its history file and in `docs/PD_FINAL.md`.

## 2. The fix

`physical.fill_layer_map`, applied where `pv.run` writes the run's copy of the
technology (`_klayout_tech`), adds one entry per routing layer that the map
leaves out: `<layer>.FILL : <the layer's drawing number>/<the technology's fill
datatype>`. On sky130hd that is `met1.FILL : 68/28` to `met5.FILL : 72/28` and
`li1.FILL : 67/28`. Both numbers come from the technology's own data (its
routing-suffix entries and its fill datatype), so no layer number is written in
the code. An
entry the map already has is kept. The routing layers come from the run's LEF
files (`TYPE ROUTING`).

The deck reads datatype 28 on the metal layers, so the fill is now checked by
every metal rule (width, spacing to routing and to other fill, area, holes).
The LVS deck reads metal drawing (datatype 20) only, so fill makes no net.

**A guard for every PDK.** The stream script now counts the fill shapes per GDS
layer (`nirmaan-gds-fill-layer`, metric `fill_layers`) and the shapes on a layer
that is not one of the map's fill targets (`nirmaan-gds-fill-unmapped`, metric
`fill_unmapped`). Any such shape fails `pv.run`: "N fill shapes on GDS layers
the technology does not map (...), which no check reads". A technology this
code cannot complete (no fill suffix, a per-mask fill datatype, no routing
entries) therefore fails a filled layout instead of passing it unread. Both
`pv.run` backends share the stream step (`physical.stream_step`).

**SKY130's own fill layers.** open_pdks' Magic technology writes and reads
SKY130 fill on the mask-numbered layers (met1 36/28, met2 41/28, met3 34/28,
met4 51/28, met5 59/28) and the drawing-numbered alternative datatype 99. The
ORFS KLayout deck reads neither, and Magic reads neither 68/28 nor KLayout's own
numbers. The fill therefore goes where the deck that judges it reads it. The
`magic-netgen` backend still cannot read a filled sky130hd layout (each skipped
shape fails its run, M79), so the M79 pilot keeps running without fill.

## 3. What the deck found in the fill

Once it read the fill (CI run 43608045086, head a0685e6), the deck found 543
violations on the AXI4-Lite block filled with the platform's `fill.json` as it
ships: `m4.4` 294 and `m3.6` 249, the minimum met4 and met3 area (0.24 um2).
That file allows 0.4 um fill sides on met3 and met4, and a 0.4 by 0.4 um (0.16
um2) or 0.4 by 0.58 um (0.232 um2) rectangle is under that area. The same run
refused the M44 factory line's physical-verification stage for the same
reason, so its "signed-off layout" had the same gap. `pv.run` failing that
layout is the correct result now that the fill is checked.

The PDK's file is not edited and not copied into the repository. The two tests
that fill a real sky130hd layout (`test_real_signoff_flow_on_sky130hd` and the
factory line's `test_one_request_runs_from_requirements_to_a_signed_off_layout`)
read it at run time and drop every fill side whose square is under 0.24 um2 on
met3 and met4 (`sky130hd_fill_rules` in `tests/test_nirmaan_physical.py`),
which leaves 0.58, 1 and 2 um. Anyone filling with the platform's file as it
ships gets these violations from `pv.run`, as they should.

## 4. The must-fail control

In `test_real_signoff_flow_on_sky130hd` (the `physical-design` CI job), after the
clean run: the first fill rectangle in the routed DEF's `FILLS` section is
shrunk to 0.1 um square at its own corner, under the layer's minimum width
(`mN.1`, 0.14 um) and area (`mN.6`). DRC must fail on that layer's width or
area rule, with LVS still clean. The clean run must have every fill shape on
`67/28` to `72/28`, and as many fill shapes in the GDS as in the DEF.

**Result** (CI run 43608976791, head 6ad04cb, the `physical-design` job): the
clean run is DRC 0 and LVS clean with every fill shape on 67/28 to 72/28 and as
many in the GDS as in the DEF; the shrunk fill rectangle fails DRC on its
layer's width or area rule with LVS clean; the factory line's layout signs off
again. The job's shard with the sky130hd test took 6.7 minutes against 6.2 on
`main` (one more `pv.run`).

## 5. Not in this milestone

* Streaming SKY130 fill to its mask-numbered layers for a tapeout GDS, with a
  deck that reads them. The ORFS deck is the PDK's file and is not edited here.
* Fill in the M79 pilot (Magic reads no fill layer the KLayout deck reads).
* Reporting the 0.4 um met3 and met4 fill sizes upstream to ORFS.

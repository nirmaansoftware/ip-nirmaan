# Milestone 80 - Metal fill on the layers the DRC deck reads, and a must-fail fill control

Follows the finding M79 recorded (`docs/PD_SKY130_PILOT.md`, section 6).
Design doc: `docs/PD_FILL_LAYERS.md`. No version bump, no count changes.

**Confirmed first, in CI.** A commit with the control and a per-layer fill
count but no fix (run 43607383342, head 3bd6aa2): the AXI4-Lite block's 12947
fill shapes were on 7/28, 9/28, 11/28 and 13/28 (KLayout's own numbers, as the
sky130hd layer map has no `.FILL` entry), and a met2 fill rectangle shrunk to
0.1 um square passed DRC. M34's "DRC 0 on the filled layout" never checked the
fill; correction notes are added to `M34-pd-final.md` and `docs/PD_FINAL.md`
(nothing deleted).

**Fix.** `physical.fill_layer_map` completes the run's copy of the KLayout
technology: `<layer>.FILL` for each LEF routing layer the map leaves out, at
the layer's drawing number and the technology's fill datatype (sky130hd: 67/28
to 72/28, read by the deck's metal inputs `67/*` to `72/*`; the LVS deck reads
datatype 20 only). Both `pv.run` backends share the stream step
(`physical.stream_step`). **Guard:** the stream counts fill per GDS layer
(`fill_layers`) and fill on a layer the map does not target (`fill_unmapped`);
any such shape fails `pv.run`, for any PDK.

**What the deck then found.** With the fill read (run 43608045086, head
a0685e6), the block filled with the platform's `fill.json` as shipped had 543
violations, `m4.4` 294 and `m3.6` 249 (met4 and met3 minimum area 0.24 um2,
from the file's 0.4 um fill sides), and the M44 factory line's
physical-verification stage was refused for the same reason. The PDK's file is
neither edited nor copied: the two real sky130hd tests read it and drop the
met3 and met4 sides whose square is under 0.24 um2 (`sky130hd_fill_rules`).

**Must-fail control** (`test_real_signoff_flow_on_sky130hd`): the first fill
rectangle shrunk to 0.1 um square must fail DRC on that layer's width or area
rule, with LVS clean; the clean run must have every fill shape on 67/28 to
72/28 and as many in the GDS as in the DEF.

**Result** (CI run 43608976791, head 6ad04cb, the `physical-design` job): the
clean run is DRC 0 and LVS clean with every fill shape on 67/28 to 72/28 and as
many in the GDS as in the DEF; the shrunk fill rectangle fails DRC on its
layer's width or area rule with LVS clean; the factory line's layout signs off
again. The job's shard with the sky130hd test took 6.7 minutes against 6.2 on
`main` (one more `pv.run`).

**Magic still reads no fill layer the KLayout deck reads** (open_pdks puts
SKY130 fill on mask-numbered 36/28 to 59/28, or datatype 99), so the M79 pilot
stays without fill. Tests: `tests/test_nirmaan_physical.py`
(`test_fill_layer_map_maps_each_routing_layer_to_its_drawing_number_and_the_fill_datatype`,
`test_fill_on_layers_the_technology_does_not_map_fails`, and the real flow).

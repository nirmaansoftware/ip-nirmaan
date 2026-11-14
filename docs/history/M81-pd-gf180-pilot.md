# Milestone 81 - The GF180MCU physical design pilot in CI, and three signoff fixes it found

The M79 pilot on a second open PDK, approved for CI use by the founder
(founder, in session, 2026-11-14). Design: `docs/PD_GF180_PILOT.md`. Tests:
`tests/test_pd_gf180_pilot.py` (in `pd-gf180` only), and in
`tests/test_nirmaan_physical.py` and `tests/test_pv_magic.py` for the fixes.
No version bump, no count changes (`pv.run` and `pnr.run` were already
`AVAILABLE`).

**Pilot.** The M26 synchronous FIFO at 100 MHz on the ORFS `gf180` platform
(5LM_1TM_9K, 9-track 5 V, typical corner): synthesis, place and route with
power grid, CTS and extraction, then Magic DRC and Netgen LVS over the
open_pdks gf180mcuC files. The cells' LEF, GDS and SPICE are open_pdks'
build of the library, which adds the `VNW` and `VPW` pins the vendor files
lack. Must fail: a flip-flop half a site over another (DRC) and a rewired D
input (LVS). Workflow `pd-gf180.yml`, a sibling of `pd-sky130.yml`: the same
image digest and Magic and Netgen build, the ciel release
`gf180mcu-792ef670` by sha256; not required.

**Result** (run 43616066140, head 65d619d): 0 router DRC, setup slack
4.059 ns, hold 1.000 ns; Magic DRC 0, Netgen unique match; the overlapping
cell fails with 423 DRC violations, the rewired input with 1 mismatched net.
The job took 2 min 19 s.

**Fixes, each found by a CI run of this pilot.**
- `pnr.run` writes the DEF and netlists right after routing: `extract_parasitics`
  dropped the router's minimum-area patches (252 here), and Magic found the
  unpatched via pads under the Metal2 and Metal3 minimum area.
- `pv.run` takes the PDK's LEF/DEF layer map file (`layer_map`) for the stream,
  as ORFS's `def2stream` reads `GDS_LAYER_MAP`; the M80 fill guard checks its
  `FILL` layers. Without it, via geometry and pin labels landed on layers of
  KLayout's own numbering.
- `magic-netgen` flattens the stream's via cells as Magic reads the GDS: as
  subcells, stacked vias broke Magic's exact-overlap rules (134240 errors).

**Gaps, stated.** No KLayout deck in the platform (DRC and LVS are Magic's and
Netgen's only); no IR drop (via cut layers have no resistance at TC); no fill
(ORFS fills only chips). M29 and M34 DEFs also lacked the patches; M34's met3
islands at stacked vias, why sky130hd signals stop at met3, are most likely
this cause, not re-tested.

# Milestone 34 - Multi-corner timing, KLayout DRC and LVS, and metal fill (after Stage 6)

Closes the four items M29 left open, on sky130hd in the `physical-design` CI
job. Design doc: `docs/PD_FINAL.md`. No version bump.

Key points worth not re-deriving:
- **What the image has** (probed first): KLayout 0.30.12, and in
  `platforms/sky130hd` a KLayout DRC deck, LVS deck, cell CDL, cell GDS, a
  `.lyt` template, and `fill.json`; no Magic or Netgen; one Liberty corner
  (tt); one OpenRCX model (one RC corner).
- **Corners**: `sta.run` takes `liberty_<corner>` (a prefix parameter) per
  corner and `corner` (the base `liberty`'s name, default `typical`); the
  script uses `define_corners` and `read_liberty -corner` (the newer
  `define_scene` form gave slightly different tt figures), reads the one SPEF
  into every corner, and prints a `report_checks -format end` pair per corner
  between `nirmaan-corner` markers. Parsed: `slack_by_corner`,
  `timing_corners` (1 for a single-corner run).
- **ss and ff Liberty** come from `fossi-foundation/ciel-releases`
  `sky130-ff08c23d...` (`sky130_fd_sc_hd.tar.zst`, sha256 `69500f75...`;
  open_pdks' assembled form of `google/skywater-pdk-libs-sky130_fd_sc_hd`,
  which holds per-cell JSON only): `ss_100C_1v60` and `ff_n40C_1v95`, each
  checked by sha256, cached by hash, copied into the platform's `lib/`.
- **`pv.run` is AVAILABLE** (backend `klayout`, executables `klayout` and
  `openroad`): CDL from the netlist (`write_cdl -masters`), Nirmaan's own
  stream script (the `def2stream` method), the PDK's DRC deck, the PDK's LVS
  deck, and two KLayout scripts that count the DRC database's items and the
  LVS cross-reference's mismatches, so no deck text is parsed. Refused without
  a DRC deck or an LVS deck with `cdl`.
- **LVS needs `final_pg.v`**: `write_verilog` leaves supply pins out, so LVS
  against `final.v` never matches; `pnr.run` now also writes
  `write_verilog -include_pwr_gnd final_pg.v` (output `pg_netlist`).
- **Fill**: `pnr.run` `fill_rules` runs `density_fill` in `route` after the
  fillers; `fill_shapes` is parsed.
- **Routing on met1 to met3 on sky130hd**: with met4, the deck found 3 `m3.6`
  (met3 min area) islands at via2/via3 stacks that the router counted as 0.
- **`min_<metric>`** limits in the runner (`eda._within_limits`), the mirror
  of `max_`. Workflow: a `physical-verification` stage (`pd.signoff_checks`,
  `pv.run` with `max_drc_violations=0`, `max_lvs_mismatches=0`,
  `min_fill_shapes=1`) between `place-route` and `sta-signoff`, which now also
  asks for `min_timing_corners=3`. `physical_verification_report` joins `04_rtl`.
- **Real numbers** (CI run 37913292574, 100 MHz, SPEF): setup / hold slack ss
  1.276 / 1.283, tt 4.428 / 0.629, ff 5.606 / 0.399 ns, the same through both
  STA backends; DRC 0 and LVS match on the filled layout (12947 fill shapes);
  a cell moved 1 nm gives 782 DRC violations (off-grid), a rewired `D` input
  an LVS mismatch (2 nets), both recorded failed runs.
- **Local OpenROAD on macOS arm64: not supported**, closed: no formula or
  arm64 package, Rosetta not installed, the last `osx-64` conda build is from
  2023, and a source build needs eight more Homebrew formulae on a shared
  prefix. The real tests run in CI only.

Fixtures: `opensta_corners.log`, `openroad_sky130_fill.log`, `klayout_pv.log`,
`klayout_pv_drc.log`, `klayout_pv_lvs.log`. CI: the `physical-design` job went
from 3.6 to 6.4 minutes, still inside the main jobs' time.
`tests/test_nirmaan_physical.py`; crown jewel
`test_physical_verification_needs_no_core_changes`; the M29 crown jewel's timer
now reports `timing_corners`.

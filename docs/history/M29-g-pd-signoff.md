# Milestone 29 (PD signoff) - Power grid, CTS, extraction, and signoff STA on the SPEF (after Stage 6)

`pnr.run` stopped at a routed layout with no power grid, an ideal clock, and
estimated parasitics (M27). It now runs the signoff steps in the same staged
OpenROAD session, for real on Nangate45 and sky130hd in the `physical-design`
CI job, and the workflow asks for their evidence as data. Design doc:
`docs/PD_SIGNOFF.md`. No version bump.

Key points worth not re-deriving:
- **Stages** are `floorplan`, `place`, `cts`, `route`, `extract` (then
  `timing`). Each optional step runs only when its PDK input is given:
  `tap_cell`/`endcap_cell`/`tap_distance`, `pdn_tcl` (sourced, then `pdngen`),
  `rc_tcl` (layer RC), `filler_cells`, `supply_voltage` (IR analysis),
  `rcx_rules` (enables `extract`, and is then the default `stop_after`),
  `dont_use`, `routing_layers` (`LOWEST,HIGHEST`; a `max_` name is read as a
  limit), `cts_buffers`, `place_density`. All declared in `company/tools.py`
  (M28). `synth.run` takes `buffer_cell` (`CELL/IN/OUT`, `insbuf`) so no
  output port drives another through an `assign`.
- **CTS needs `rc_tcl`** (`RSZ-0089` without it), so a run that reaches `cts`
  without it is refused like a missing PDK file.
- **Parsed**: `slack_by_stage` (place: ideal clock; cts: propagated; route:
  global-routing estimate; extract: SPEF), CTS buffers and sinks, skew,
  insertion delay, taps, endcaps, fillers, `power_grids`,
  `unconnected_supply_pins` (Nirmaan's own count after a second
  `global_connect`), antenna violations, worst IR drop per supply net, and
  `unannotated_nets`. Pass adds: every supply pin connected when a grid was
  built and the block routed, and no antenna violation.
- **`unannotated_nets`, not unannotated drivers**: the unused `QN`s (Yosys
  names their nets), CTS dummy loads, and the `inout` `VDD`/`VSS` ports drive
  nothing and have no wire; the scripts list them and the parser counts, by
  name, the unannotated drivers that do drive something.
- **Signoff STA on the SPEF is data**: `sta-signoff` asks for an `sta.run`
  made with `max_unannotated_nets=0`; a run without a SPEF never reports the
  metric and fails the limit. A new `power-grid` stage (`pd.power_plan`) asks
  for `max_unconnected_supply_pins=0`; `place-route` adds that and
  `max_drc_violations=0`. `ran()` takes keyword arguments; `power_grid` joins
  `04_rtl`. `sta.run` with a `spef` propagates clocks.
- **Standalone OpenSTA** is built in the job from the commit the image's
  OpenROAD embeds (`The-OpenROAD-Project/OpenSTA` `e983e15b`), cached by
  commit; `NIRMAAN_REQUIRE_EDA` there is `yosys openroad sta`.
- **Real numbers** (CI run 37632069804, 100 MHz, typical corner): Nangate45
  signoff routes with 0 DRC, 12562 um, 43%, every supply pin connected, IR
  drop 1.56 mV on VDD, 17 clock buffers for 206 sinks, skew 0.003 ns, insertion
  delay 0.111 ns, setup slack 7.471 (place), 7.449 (cts), 7.435 (estimated),
  7.449 ns (extracted), hold 0.155 ns; separate signoff STA on the SPEF gives
  7.449 / 0.155 through both STA backends. sky130hd: 0 DRC, 30569 um, 518 taps,
  skew -0.009 ns, insertion delay 0.456 ns, setup 4.197 estimated and 4.419 ns
  extracted. 5 GHz to `cts`: -0.249 ns after repair, a recorded failed run.
- **Not available**: multi-corner timing (both platforms ship one Liberty
  corner); a KLayout or Magic DRC/LVS deck; metal fill; an IR limit.

Fixtures (captured from that run): `openroad_route.log` (re-captured with
CTS), `openroad_signoff.log`, `opensta_spef.log` (standalone OpenSTA). CI time:
the `physical-design` job went from 2.5 to 7 minutes with an uncached OpenSTA
build (3.6 minutes cached), in parallel with the 5 to 7 minute main
jobs. Tests: `tests/test_nirmaan_physical.py`; crown jewel
`test_signoff_on_extracted_parasitics_needs_no_core_changes`, and the M25
crown jewel now meets the M29 limits.

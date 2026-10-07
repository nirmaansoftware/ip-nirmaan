# Physical-design signoff steps (Milestone 29)

M25 bound `pnr.run` to OpenROAD and M27 ran it for real in CI, but the flow
stopped at a routed layout with no power grid, no tap or filler cells, an
ideal clock, and estimated parasitics: its 0 DRC covered the signal wires
only, and the cells' power pins were not connected. This milestone adds the
steps a block needs before its timing and layout mean anything, runs them for
real on Nangate45 and sky130hd in the `physical-design` CI job, and makes the
`physical-implementation` workflow ask for their evidence as data.

Read `docs/PHYSICAL_DESIGN.md` first (M25 and M27): the bindings, the PDK
inputs, the parsers, and the CI job. Everything there still holds unless this
document says otherwise.

---

## 1. Decision: more stages in the one `pnr.run`, not new tools

M25 chose one staged `pnr.run` over one tool per step (one OpenROAD process,
one database, one log that shows every stage in order). The signoff steps
follow the same rule. Each runs inside the session, between the stage markers
the parser already reads:

| Stage | What it runs (M29 additions in bold) |
|---|---|
| (setup) | **`set_thread_count [cpu_count]`**, `read_lef`, `read_liberty`, `read_verilog`, `link_design`, `read_sdc`, **`source <rc_tcl>`** |
| `floorplan` | `initialize_floorplan`, `make_tracks`, **`tapcell`** (with `tap_cell`), **`source <pdn_tcl>` and `pdngen`** (with `pdn_tcl`), `place_pins`, `report_design_area` |
| `place` | `global_placement`, **`estimate_parasitics -placement`, `repair_design`**, `detailed_placement`, `check_placement -verbose`, **a slack checkpoint** |
| **`cts`** | **`clock_tree_synthesis`, `set_propagated_clock`, `repair_clock_nets`, `detailed_placement`, `repair_timing -setup -hold`, `detailed_placement`, `check_placement -verbose`, `report_cts`, `report_clock_skew`, `report_clock_latency`, a slack checkpoint** |
| `route` | **`set_routing_layers`** (with `routing_layers`), `global_route`, **a slack checkpoint on global-routing parasitics**, `detailed_route`, **`filler_placement`** (with `filler_cells`), **`check_placement`, `check_antennas`, `global_connect`, a count of unconnected supply pins, `check_power_grid` per supply net, `analyze_power_grid` per supply net** (with `supply_voltage`) |
| **`extract`** | **`define_process_corner`, `extract_parasitics -ext_model_file <rcx_rules>`, `write_spef route.spef`, `read_spef route.spef`, `report_parasitic_annotation`, a slack checkpoint** (only with `rcx_rules`) |
| `timing` | the full timing reports of M25, on the best parasitics the run has: extracted, else global-routing estimates, else placement estimates; clocks are propagated after `cts` |

`stop_after` now takes `floorplan`, `place`, `cts`, `route`, or `extract`. The
default is `extract` when `rcx_rules` is given, else `route`, so a run that
names the PDK's extraction rules goes to signoff parasitics without asking.
`stop_after=extract` without `rcx_rules` is a recorded failed run.

Each optional step runs only when the PDK input it needs is given, and the run
says which ran: a routed run with no power grid says "no power grid" in its
summary. Nothing is assumed from the platform's name.

**Clock-tree synthesis needs layer RC.** Without `set_layer_rc` the resizer
cannot size clock wires (`[ERROR RSZ-0089] Could not find a resistance value
for any corner`, from the first CI run). Since CTS is now on the default path,
a `pnr.run` that reaches `cts` without `rc_tcl` is refused, like any other
missing PDK input, with the reason and the way out (`stop_after=place`).

### 1.1 New parameters (declared in `company/tools.py`, M28)

| Parameter | Kind | Meaning |
|---|---|---|
| `rc_tcl` | PDK file | The platform's layer RC script (`setRC.tcl` in ORFS); needed from `cts` on |
| `tap_cell`, `endcap_cell`, `tap_distance` | settings | Well-tap and endcap masters, microns between tap columns (`tap_distance` is required with `tap_cell`) |
| `pdn_tcl` | PDK file | The platform's power-grid script (global connections, voltage domain, grid), sourced before `pdngen` |
| `place_density` | number | Global placement target density |
| `dont_use` | settings | Cells (names or `*` patterns) repair and CTS must not insert, applied with `set_dont_use` |
| `cts_buffers` | settings | Clock buffer masters; by default CTS picks from the Liberty |
| `routing_layers` | settings | Lowest and highest signal routing layers, `LOWEST,HIGHEST` (a `max_` name would be read as a limit) |
| `filler_cells` | settings | Filler masters, comma separated |
| `supply_voltage` | number | Volts on each power net (ground nets at 0) for IR-drop analysis |
| `rcx_rules` | PDK file | OpenRCX rules; enables `extract` |

A PDK file parameter that is given must exist, or the probe refuses the run,
as M25 does for the Liberty and LEFs.

`synth.run` (`yosys-liberty`) gains `buffer_cell` (`CELL/IN/OUT`, for example
`BUF_X1/A/Z`): Yosys's `insbuf` puts a buffer wherever one output port drives
another. Without it the AXI4-Lite netlist carries
`assign s_axil_rresp[0] = s_axil_bresp[0];`, OpenROAD writes the routed
netlist back the same way, and a timer reading that netlist with the SPEF
finds the shared net unannotated (section 3).

---

## 2. What is parsed

`parse_openroad` keeps every M25 metric and adds, each from a line format seen
in a captured log:

| Metric | From |
|---|---|
| `slack_by_stage` | per stage (`place`, `cts`, `route`, `extract`), the `worst slack max/min` and `tns max` its checkpoint printed: ideal clock on placement estimates, then propagated clock, then global-routing estimates, then extracted parasitics |
| `cts_buffers`, `cts_sinks` | `report_cts`: `Total number of Buffers Inserted`, `Total number of Sinks` |
| `clock_skew` | `report_clock_skew`: `<n> setup skew` (largest, in ns) |
| `clock_insertion_delay` | `report_clock_latency`: the largest max latency (`<min> <max> latency`) |
| `tap_cells`, `endcap_cells` | `TAP-0005 Inserted <n> tapcells`, `TAP-0004 Inserted <n> endcaps` |
| `power_grids` | `PDN-0001 Inserting grid: <name>` |
| `unconnected_supply_pins` | Nirmaan's own count, after a final `global_connect`, of instance POWER and GROUND pins with no net |
| `supply_nets` | the block's POWER and GROUND nets |
| `filler_cells` | `DPL-0001 Placed <n> filler instances` |
| `antenna_net_violations`, `antenna_pin_violations` | `ANT-0002`, `ANT-0001` |
| `worst_ir_drop_v` | per supply net, `Worstcase IR drop` from the IR report |
| `unannotated_drivers`, `floating_outputs`, `unannotated_nets` | `report_parasitic_annotation`, and Nirmaan's count of output pins that drive no net |
| `parasitics` | `extracted` when the `extract` stage finished, else `estimated` |

`check_power_grid` reports a disconnected grid as an `[ERROR PSM-...]`, which
fails the run like any other error.

**Pass** now also means: when a power grid was inserted, every supply pin is
connected; no antenna violation; and the final timing is met on the parasitics
the run has. The summary says which parasitics it timed on.

**Unannotated drivers are not unannotated nets.** On the first extracted run,
`report_parasitic_annotation` found 220 unannotated drivers on Nangate45. All
of them were outputs that drive no load: the unused `QN` of every flip-flop
(Yosys still gives each one a named net) and the outputs of the dummy loads
CTS inserts to balance the tree. Such a net has no wire, so there is nothing
to extract. The separate signoff run also listed the block's `VDD` and `VSS`
ports: the power grid gives the block supply pins, the routed netlist declares
them as `inout` ports, and no cell in Verilog has a supply pin to load them. The
script now also counts these drivers of nothing (a cell output with no net, or
with a net that reaches no other pin and no port, and an input or inout port whose net
reaches no cell pin), printed as `nirmaan-floating-outputs`, and
`unannotated_nets` is the difference: the loaded nets that should have
parasitics and do not.

`parse_opensta` reads the same annotation lines, so `sta.run` with a `spef`
reports `unannotated_nets` too.

---

## 3. Signoff STA uses the extracted parasitics

The `extract` stage writes `route.spef`, and the run's `outputs` gain `spef`
beside `def` and `netlist` (`final.v`). Signoff timing is a separate `sta.run`
over `final.v` with `spef=route.spef`; its script reads the SPEF, propagates
the clocks (a SPEF comes from a routed block, whose clock tree exists), lists
the unannotated drivers, and times on it.

The first separate run found 2 unannotated nets that the in-flow timing did
not: the routed netlist's `assign` between two output ports (section 1.1),
which `buffer_cell` removes. It also timed on an ideal clock (7.539 ns against
7.508 ns in the flow) until the script propagated the clocks.

The workflow states this as data. The `sta-signoff` stage's tool evidence is a
`sta.run` made with `max_unannotated_nets=0`. M21's limit rule does the rest:
a run without a SPEF never reports `unannotated_nets`, and a limit on a metric
the run did not report fails it. So signoff timing on estimated parasitics
cannot meet the requirement, and no core code names SPEF. A machine without
extraction rules can still meet it with a named human's attestation of an
extraction run elsewhere, as for every `ran(...)` requirement.

---

## 4. The workflow

`physical-implementation` gains a stage and limits, all in
`company/workflows.py`:

```
timing-constraints -> synthesis -> floorplan
  -> power-grid (pd.power_plan)    evidence: a pnr.run with max_unconnected_supply_pins=0, reviewed
  -> place-route (pd.place_route)  evidence: a pnr.run with max_drc_violations=0 and
                                   max_unconnected_supply_pins=0, reviewed (depends on floorplan and power-grid)
  -> sta-signoff (sta.analyze)     evidence: an sta.run with max_unannotated_nets=0, reviewed; gate.implementation
```

`pd.power_plan`, its `power_grid` output, and the `power_planning` skill
already existed; the `power_grid` artifact kind joins the `04_rtl` deliverable
folder with the other implementation views. `ran(...)` takes the same keyword
arguments as `checked(...)`, so the limits are plain `params`.

---

## 5. Standalone OpenSTA in CI

M27 found no standalone `sta` in any packaged OpenROAD. The ORFS image,
however, carries everything OpenSTA's build needs: CMake, GCC, SWIG, Bison,
Flex, Tcl, Eigen, and CUDD under `/usr/local`, and spdlog's bundled `fmt`
(GCC 11 has no `std::format`). So the `physical-design` job builds OpenSTA at
the commit the image's OpenROAD embeds (`The-OpenROAD-Project/OpenSTA`
`e983e15b`, the `src/sta` submodule of OpenROAD `c487fc70`), so both
backends are the same timer. The build takes about 1.5 minutes and is cached
by commit, so it runs once.

`NIRMAAN_REQUIRE_EDA` in that job now includes `sta`, so the `opensta`
backend's tests fail rather than skip. The signoff test times the extracted
SPEF through both backends, `openroad-sta` and `opensta`, and requires both to
agree that every net is annotated and timing is met.

---

## 6. sky130hd

The image's `flow/platforms` holds sky130hd as well as Nangate45 (tech LEF,
merged cell LEF, the `tt_025C_1v80` Liberty, `pdn.tcl`, `setRC.tcl`, and
`rcx_patterns.rules`, a link to sky130hs's). A real-tool test takes the
AXI4-Lite block through the whole signoff flow on it, with the platform's
taps (`sky130_fd_sc_hd__tapvpwrvgnd_1` every 14 um), grid, fillers, and RCX
rules, at 30% utilization and signals on met1 to met4.

The first sky130hd runs did not finish. With signals allowed on met5, where
`pdn.tcl` puts its power straps, the detailed router got down to four met5
shorts and spacing violations and never removed them, and the run timed out
(at 300 s, then at 900 s). Capping signals at met4 (`routing_layers=met1,met4`)
then stopped global routing on a probe buffer `repair_design` had chosen,
whose pin is on met5 (`[ERROR GRT-0029] Pin load_slew4/X does not have
geometries below the max routing layer`). ORFS keeps those cells out with its
`DONT_USE_CELLS`; `pnr.run` now takes `dont_use`, and the test passes the
probe and `lpflow` cells. The test gives the run 900 s; it takes about 2
minutes.

---

## 7. Multi-corner timing: not available

Neither platform in the image ships more than one Liberty corner for its
standard cells. Nangate45 has `NangateOpenCellLibrary_typical.lib` only.
sky130hd has `sky130_fd_sc_hd__tt_025C_1v80.lib` only (and a dummy I/O
library). gf180 ships ff, ss, and tt corners, but no place-and-route flow here
targets it. So every figure in this milestone is one corner, typical, and
`slack_by_stage` is per stage, not per corner. Multi-corner STA
(`define_corners`, one Liberty set per corner) is deferred until a platform
with corners is in the tests; making it up with copies of one library would
report corners that do not exist.

---

## 8. Real numbers (CI, AXI4-Lite block, 100 MHz)

See section 10 for the run they come from.

One typical corner, AXI4-Lite block, 100 MHz `aclk`, `buffer_cell` in
synthesis. Slack in ns; "place" is ideal clock on placement estimates, "cts"
propagated clock on placement estimates, "route" global-routing estimates
before detailed routing, "extract" the OpenRCX SPEF.

| | Nangate45 signoff | sky130hd signoff | Nangate45, no signoff inputs |
|---|---|---|---|
| Cell area, utilization | 2153 um^2, 43% | 13220 um^2, 34% (30% asked) | 2127 um^2, 43% |
| Taps, endcaps, fillers | 0 (one column per 120 um, wider than the die), 100, 1494 | 518, none named, 3911 | none |
| Power grid | `grid`, every supply pin connected, `check_power_grid` clean on VDD and VSS | the same | none: 2762 supply pins open, and the summary says "no power grid" |
| Worst IR drop at 1.1 V / 1.8 V | VDD 1.56 mV, VSS 0.59 mV | VDD 0.16 mV, VSS 0.14 mV | not run |
| CTS | 17 buffers, 206 sinks | 17 buffers, 206 sinks | 17 buffers, 206 sinks |
| Clock skew, insertion delay | 0.003, 0.111 | -0.009, 0.456 | -0.005, 0.115 |
| Setup / hold slack: place | 7.471 / 0.151 | 4.092 / 0.607 | 7.458 / 0.151 |
| cts | 7.449 / 0.155 | 4.547 / 0.632 | 7.446 / 0.156 |
| route (estimated) | 7.435 / 0.158 | 4.197 / 0.645 | 7.422 / 0.158 |
| extract (SPEF) | 7.449 / 0.155 | 4.419 / 0.629 | not run |
| Detailed routing | 0 DRC, 12562 um, 51 s | 0 DRC, 30569 um, 74 s | 0 DRC, 12645 um, 54 s |
| Antenna, placement checks | 0 net and 0 pin violations; `check_placement` clean | the same | the same |
| Unannotated drivers, of which drive nothing, unannotated nets | 219, all, 0 | 16, all, 0 | not run |

Signoff STA on `final.v` with `route.spef`, separately: 7.449 / 0.155 ns
through both `openroad-sta` and standalone `opensta`, the same figures as the
flow's extracted timing, with 0 unannotated nets (221 drivers that drive
nothing: the unused `QN`s, the CTS dummy loads, and the `VDD` and `VSS`
ports).

Extracted against estimated: on Nangate45 the extracted setup slack is 14 ps
better than the global-routing estimate and equal to the post-CTS figure; on
sky130hd it is 222 ps better than the estimate (4.419 against 4.197). The
estimates are pessimistic here, which is the safe direction, but they are not
the signoff numbers.

At 5 GHz (`axi4_lite_regs_fast.sdc`, `stop_after=cts`), repair halves the
damage and does not close it: setup slack -0.601 ns (TNS -105.684) after
placement, -0.249 ns (TNS -47.384) after CTS and `repair_timing`, and the
final report -0.262 ns, hold -0.001 ns: a recorded failed run ("timing
violated"). At 300% utilization placement still fails (`GPL-0301`).

---

## 9. Fixtures

`openroad_route.log` and the new `openroad_signoff.log` are captured from the
CI run in section 10, each with a `# CAPTURED:` line and the log unedited
below it. `opensta_spef.log` is standalone OpenSTA timing the extracted SPEF.
The M27 `openroad_error.log`, `opensta_met.log`, and `opensta_violated.log`
are unchanged: those flows did not change.

---

## 10. CI

The numbers above are from CI run 37632069804 (head `a278ac7`), whose four
jobs all passed; the `physical-design` job ran 29 tests, none skipped, with
`NIRMAAN_REQUIRE_EDA="yosys openroad sta"`.

| | M27 | M29 |
|---|---|---|
| `physical-design` job | 2 min 29 s | 7 min 0 s with the OpenSTA build (2 min 19 s, a cache miss); 3 min 34 s with the build cached (run 37634417200) |
| of which the tests | about 1 min | 3 min 26 s (three full signoff flows, a CTS-only failure run, and the M27 tests, now through CTS) |

The job runs in parallel with the two main test jobs (5 to 7 minutes), so
CI's wall time grows by little or nothing once OpenSTA is cached.
`set_thread_count [cpu_count]` (4 threads in CI) took the Nangate45 detailed
route from 90 s to about 50 s.

What the iterations found, in order: CTS needs layer RC (`RSZ-0089`); buffers,
the clock tree, and fillers inserted after `pdngen` need a second
`global_connect` (2288 open supply pins until then); on sky130hd, signal
routing on met5 against the straps never converged, and the probe buffers
(`sky130_fd_sc_hd__probe_p_*`, met5 pins) need `dont_use` (`GRT-0029`); a
`max_routing_layer` parameter would have been read as a `max_` limit, hence
`routing_layers`; the annotation counts of section 2; and the `assign` and
ideal-clock differences of section 3.

Warnings left in the logs, recorded and not failing: `PDN-1051` (no macros
for the platform's macro grids), `RCX-0514` (`-ext_model_file` is deprecated
in favor of `set_extraction_rules_file`), `DRT-0349` on sky130hd
(`LEF58_ENCLOSURE` without a cut class), and `RSZ-0062` in the 5 GHz run.

---

## 11. Not in this milestone

* Multi-corner, multi-mode timing (section 7).
* Physical verification with a signoff deck (`pv.run`: KLayout DRC and LVS,
  Magic). OpenROAD's own checks (`check_placement`, `check_antennas`,
  `check_power_grid`, the detailed router's DRC) are what this flow reports.
* Metal density fill, and IR-drop limits as workflow data (the drop is
  reported, not limited).
* A local OpenROAD on macOS: still CI only.

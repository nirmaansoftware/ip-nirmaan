# Physical design through OpenROAD and OpenSTA (Milestone 25, physical design part)

Stage 6 of the roadmap takes a block past synthesis: floorplan, placement,
routing, and signoff timing. Until now `sta.run` and `pnr.run` were
`CONTRACT_ONLY`: the organization planned timing and layout work, and the
broker refused every invocation. This milestone gives both tools real
bindings, built on the M21 backend registry (`docs/EDA_TOOLS.md`), and a
workflow that plans the physical stages as data.

| Tool ID | Backend | Executable | Needs from the PDK |
|---|---|---|---|
| `synth.run` | `yosys-liberty` (new, beside the M21 `yosys`) | `yosys` | a Liberty file |
| `sta.run` | `opensta` | `sta` (OpenSTA) | a Liberty file |
| `pnr.run` | `openroad` | `openroad` | a Liberty file, a technology LEF, a cell LEF, a site name, and the pin layers |

The bindings live in `src/nirmaan/integrations/physical.py`; the parsers in
`src/nirmaan/integrations/pd_parsers.py` (pure functions of captured text, like
`eda_parsers.py`).

**What ran for real in this milestone.** OpenROAD and OpenSTA are not
installed on the development machine or in CI, and neither is available from
Homebrew. No OpenSTA or OpenROAD run has happened in this repository. The
`yosys-liberty` backend does run for real, in CI, against a tiny test library.
Section 7 says exactly which fixtures are captured and which are synthetic.

---

## 1. The rules (unchanged from M21)

1. **A binding runs only when it can.** The broker asks the binding's probe
   before every invocation. A missing executable, or a missing PDK input, is a
   refusal (`ToolAccessDenied`) whose message names what is missing. No run is
   recorded, and nothing is simulated, stubbed, or replayed from a fixture.
2. **Failures are recorded runs.** A timing violation, DRC violations, an
   OpenROAD `[ERROR ...]`, a missing netlist, a timeout: each is a `ToolRun`
   with `succeeded=False` and a summary saying why.
3. **Output is parsed** into an `EdaResult` (pass or fail, diagnostics,
   metrics), and the raw log and the structured result are written to disk and
   cited by the run.

---

## 2. Decision: one staged `pnr.run`, not four tools

The catalog already declared a single `pnr.run` ("Floorplan, placement, CTS,
routing"), and the skills that do physical work (`floorplanning`,
`power_planning`, `place_and_route`) already name it. The choice was between
keeping that one tool with stages, and splitting it into `pnr.floorplan`,
`pnr.place`, `pnr.route`, and `pnr.timing`.

One staged tool wins:

* **OpenROAD is one process with one database.** Splitting the flow into four
  tools means four processes that hand a DEF (or an ODB) to each other. Each
  hand-off is a place where a run could cite a database it did not produce.
  One invocation that runs floorplan, then placement, then routing, in one
  session, has one log that shows every stage in order.
* **The workflow still sees the stages.** The `stop_after` parameter
  (`floorplan`, `place`, or `route`, default `route`) ends the run early, and
  the parser reports which stages finished. The floorplan task runs
  `pnr.run stop_after=floorplan`; the place-and-route task runs it to the end.
  Timing is reported after whichever stage ran last.
* **Permissions stay simple.** A role that may floorplan may run the tool that
  floorplans; there is no case where a role may place but not route.
* **No data churn.** The skills, capabilities, and evidence requirements that
  already name `pnr.run` keep working.

The cost is that a run to `route` repeats floorplan and placement. For the
block sizes this repository handles (the AXI4-Lite register block) that is
seconds. Resuming from a saved database is deferred (section 9).

---

## 3. PDK and library inputs

**No PDK is bundled, ever.** The PDK is an input, supplied per task:

| Parameter | Tools | Meaning |
|---|---|---|
| `liberty` | `synth.run` (`yosys-liberty`), `sta.run`, `pnr.run` | Liberty file(s), comma separated (`yosys-liberty` maps to the first) |
| `tech_lef` | `pnr.run` | Technology LEF |
| `lef` | `pnr.run` | Standard-cell LEF(s), comma separated |
| `site` | `pnr.run` | Placement site name (for example `unithd` in sky130 HD) |
| `hor_layers`, `ver_layers` | `pnr.run` | Routing layers for the I/O pins (for example `met3`, `met2`) |
| `pdk_root` | all three | Base directory for relative PDK paths |

A relative `liberty`, `tech_lef`, or `lef` path resolves against `pdk_root`,
else against the environment variable **`NIRMAAN_PDK_ROOT`**, else against the
current directory. So a machine with sky130 installed sets
`NIRMAAN_PDK_ROOT=/path/to/pdks/sky130A` once, and tasks pass
`liberty=libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib`.

**A missing PDK input is a refusal, not a failed run.** The PDK is part of the
machine's environment, like the executable: without it the tool cannot start,
so nothing ran and nothing is recorded. The probe says what is missing:

```
pnr.run cannot run here: openroad needs openroad on PATH, not found;
openroad: needs a Liberty file (liberty=PATH, absolute or under NIRMAAN_PDK_ROOT;
no PDK is bundled) (refused, never simulated)
```

Design inputs are different. A missing netlist or SDC file is the task's
problem, not the machine's, so it is a recorded failed run, exactly as a
missing Verilog source is for lint (M21).

To support this, `Backend` gained two optional fields in `eda.py`, both
generic:

* `environment(params) -> reason | None`: asked by the probe after the
  executables are found on `PATH`. Its reason joins the missing executables in
  the refusal.
* `files`: parameter names whose values are paths that must exist before any
  step runs (M21 checked only `sources` and `sby`).

---

## 4. The bindings

### 4.1 `synth.run`, backend `yosys-liberty`

STA and place-and-route need a netlist of library cells, and the M21 `yosys`
backend maps to Yosys's generic gates and writes no netlist. `yosys-liberty`
is a second backend for the same tool, selected with `backend=yosys-liberty`
(the default stays the generic one, so nothing that worked before changes):

```
read_verilog -sv <sources>
synth -top <top>
dfflibmap -liberty <lib>
abc -liberty <lib>
opt_clean -purge
tee -q -o stat.json stat -json -liberty <lib>
write_verilog -noattr -noexpr -nohex -nodec netlist.v
```

The result's metrics add `netlist` (the path to `netlist.v`) and, from
`stat -liberty`, the cell `area`. Constant-driver (tie) cells, buffering, and
multi-corner mapping are not done.

### 4.2 `sta.run`, backend `opensta`

Inputs: `netlist` (from `synth.run`, required), `sdc` (required), `top`
(required), `liberty` (PDK), and optionally `spef` (parasitics). Nirmaan
writes `sta.tcl` in the working directory and runs
`sta -no_init -no_splash -exit sta.tcl`:

```
read_liberty <lib>            ;# each one
read_verilog <netlist>
link_design <top>
read_sdc <sdc>
read_spef <spef>              ;# only when given
report_checks -path_delay max -digits 3
report_checks -path_delay min -digits 3
report_checks -path_delay min_max -slack_max 0 -group_count 100 -endpoint_count 1 -digits 3
report_worst_slack -max -digits 3
report_worst_slack -min -digits 3
report_tns -digits 3
report_wns -digits 3
```

Parsed (`parse_opensta`):

| Metric | From |
|---|---|
| `worst_slack` (setup) | the first `worst slack <n>` line |
| `worst_hold_slack` | the second `worst slack <n>` line |
| `tns`, `wns` | `tns <n>`, `wns <n>` |
| `violating_endpoints` | every path report ending `slack (VIOLATED)`: endpoint, check (`setup` for `Path Type: max`, `hold` for `min`), and slack, worst first, one per endpoint and check |
| diagnostics | `Error: ...`, `Warning: ...`, and OpenROAD-style `[ERROR STA-0000] ...` lines |

Pass means: every step exited 0, no error, a worst setup slack was reported
and is not negative, the hold slack (when reported) is not negative, and no
endpoint violates. A design with no constrained paths (`worst slack INF`, or no
figure at all) fails with "no constrained timing paths": an unconstrained
design has not met timing, it has not been timed.

### 4.3 `pnr.run`, backend `openroad`

Inputs: `netlist`, `sdc`, `top` (design, required), the PDK inputs of section
3, and optionally `utilization` (percent, default 40), `aspect_ratio` (default
1), `core_space` (microns, default 2), and `stop_after`. Nirmaan writes
`pnr.tcl` and runs `openroad -no_init -no_splash -exit pnr.tcl`. Each stage is
bracketed by `puts "nirmaan-stage: <stage>"` and
`puts "nirmaan-stage-done: <stage>"`, so the log itself shows how far the flow
got:

| Stage | Commands |
|---|---|
| (setup) | `read_lef` (technology, then cells), `read_liberty`, `read_verilog`, `link_design`, `read_sdc` |
| `floorplan` | `initialize_floorplan -utilization -aspect_ratio -core_space -site`, `make_tracks`, `place_pins -hor_layers -ver_layers`, `report_design_area` |
| `place` | `global_placement`, `detailed_placement`, `check_placement`, `report_design_area` |
| `route` | `global_route`, `detailed_route -output_drc route_drc.rpt` |
| `timing` | `estimate_parasitics` (`-placement` after place, `-global_routing` after route; none after floorplan), then the four timing reports of 4.2 |
| (outputs) | `write_def <last stage>.def`, and after routing `write_verilog final.v` |

Parsed (`parse_openroad`):

| Metric | From |
|---|---|
| `stages_completed`, `failed_stage` | the `nirmaan-stage` markers |
| `design_area_um2`, `utilization_pct` | the last `Design area <a> u^2 <u>% utilization.` |
| `wirelength_um` | the last `Total wire length = <n> um` (detailed routing) |
| `drc_violations` | the last `Number of violations = <n>` (detailed routing) |
| `worst_slack`, `worst_hold_slack`, `tns`, `wns` | as for OpenSTA (OpenROAD embeds it) |
| diagnostics | `[ERROR XXX-0000] ...`, `[WARNING XXX-0000] ...`, and `Error: ...` |

Pass means: exit 0, no `[ERROR]`, every requested stage and the timing stage
finished, zero DRC violations when routing ran, and timing met as for STA.

Power-grid generation (`pdngen`), tap and filler cells, clock-tree synthesis,
timing repair, and parasitic extraction are not in the flow (section 9). The
timing this run reports is therefore on ideal clocks with estimated
parasitics; signoff STA is the separate `sta.run`, which takes a SPEF when one
exists.

**The TCL has not run against a live OpenSTA or OpenROAD in this repository.**
Command and option names follow the tools' documentation; the first run on a
machine with the tools (see section 8) is the check, and any correction is a
change to `physical.py` alone.

---

## 5. Status honesty in the catalog

M21's rule stands: `AVAILABLE` means a real binding exists in the repository;
the probe decides, per machine and per invocation, whether it can run.
`sta.run` and `pnr.run` move to `AVAILABLE` because their bindings exist.

`nirmaan org tools` gained a column, **Here**, that asks each bound tool's
probe (with no task inputs) whether this machine could run it, and prints the
reason when not:

```
sta.run   eda  execute  available  yes  no: sta.run cannot run here: opensta needs sta on PATH, not found; ...
```

The runtime exposes this as `nirmaan.runtime.unavailable_reason(tool_id,
params)`, the same probe the broker uses, so the table and the broker cannot
disagree.

---

## 6. The workflow: `physical-implementation`

A new workflow, with a new intent `physical_implementation` (priority 50, ahead
of `block_design` and `new_ip`; phrases such as "place and route", "PnR",
"physical design", "physical implementation"). It names only capabilities that
already existed:

```
timing-constraints (sta.constraints)
  -> synthesis (synth.run)             evidence: a synth.run
  -> floorplan (pd.floorplan)          evidence: a pnr.run, reviewed (pd.review)
  -> place-route (pd.place_route)      evidence: a pnr.run, reviewed (pd.review)
  -> sta-signoff (sta.analyze)         evidence: an sta.run, reviewed (sta.review); gate.implementation
```

Tool evidence here is `ran(...)`: a real run, or a named human attesting to a
run made elsewhere. That keeps the workflow usable on a machine without
OpenROAD, which is every machine this repository is tested on today, without
pretending anything ran. The skills (`synthesis`, `floorplanning`,
`place_and_route`, `sta`) and capabilities already existed and already named
`synth.run`, `pnr.run`, and `sta.run`, so no skill or capability record was
added. The deliverable export files `floorplan` artifacts (and the
`pd.floorplan` capability) with the other implementation views in `04_rtl`.

---

## 7. Fixtures: captured and synthetic

`tests/fixtures/pd/`:

| File | Provenance |
|---|---|
| `axi4_lite_regs.sdc` | Written for this milestone: a 100 MHz `aclk`, I/O delays at 20% of the period, for `tests/fixtures/rtl/axi4_lite/` |
| `tiny_cells.lib` | Written for this milestone: a toy Liberty library (inverter, buffer, NAND2, NOR2, D flip-flop) with areas and functions but no timing. It exists so `yosys-liberty` can map for real in CI. It is not a PDK and cannot time anything |
| `synthetic_opensta_met.log`, `synthetic_opensta_violated.log`, `synthetic_openroad_route.log`, `synthetic_openroad_error.log` | **Synthetic.** Hand-written samples that follow the report formats in the OpenSTA and OpenROAD documentation, because neither tool could be run here. Each starts with a `# SYNTHETIC` line saying so |

The parser tests read the synthetic samples. They prove the parsers read the
documented formats; they do not prove the formats match a given tool version.
Replacing them with captured logs is the first task once the tools are
available (section 8).

---

## 8. Real-tool tests

`tests/test_nirmaan_physical.py` has real-tool tests for OpenSTA and OpenROAD
that use the M21 `needs(...)` marker: they skip when `sta` or `openroad` is not
on `PATH` (or when `NIRMAAN_PDK_ROOT` and the sky130 HD files under it are
absent), and fail instead of skipping only when `NIRMAAN_REQUIRE_EDA` names the
executable. CI does not name `sta` or `openroad`, and does not install them.
The `yosys-liberty` test runs in CI (Yosys is required there).

To run them on a machine with the tools and sky130:

```
export NIRMAAN_PDK_ROOT=/path/to/pdks/sky130A
NIRMAAN_REQUIRE_EDA="sta openroad" python -m pytest tests/test_nirmaan_physical.py
```

---

## 9. Not in this milestone

* Power-grid generation, tap and filler cells, clock-tree synthesis, repair
  (`repair_design`, `repair_timing`), and parasitic extraction (`extract_parasitics`
  and a SPEF handed to `sta.run`).
* Resuming a flow from a saved database instead of re-running earlier stages.
* Multi-corner, multi-mode timing (one Liberty set per run).
* Physical verification (`pv.run`: DRC and LVS with Magic, KLayout, or Netgen)
  and power analysis (`power.run`).
* Captured OpenSTA and OpenROAD logs in place of the synthetic samples.
* A deliverable folder of its own for physical views (they stay in `04_rtl`).
* Adopting `before_review` file checks (M23) in the physical workflow: the
  netlist and DEF are not yet recorded as artifact files.

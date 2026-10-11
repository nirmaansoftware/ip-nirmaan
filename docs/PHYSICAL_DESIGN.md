# Physical design through OpenROAD and OpenSTA (Milestones 25 and 27)

Stage 6 of the roadmap takes a block past synthesis: floorplan, placement,
routing, and signoff timing. Until now `sta.run` and `pnr.run` were
`CONTRACT_ONLY`: the organization planned timing and layout work, and the
broker refused every invocation. This milestone gives both tools real
bindings, built on the M21 backend registry (`docs/EDA_TOOLS.md`), and a
workflow that plans the physical stages as data.

| Tool ID | Backend | Executable | Needs from the PDK |
|---|---|---|---|
| `synth.run` | `yosys-liberty` (new, beside the M21 `yosys`) | `yosys` | a Liberty file |
| `sta.run` | `opensta`, else `openroad-sta` (M27) | `sta` (OpenSTA), else `openroad` (its embedded OpenSTA) | a Liberty file; for `openroad-sta` also the technology and cell LEFs |
| `pnr.run` | `openroad` | `openroad` | a Liberty file, a technology LEF, a cell LEF, a site name, and the pin layers |

The bindings live in `src/nirmaan/integrations/physical.py`; the parsers in
`src/nirmaan/integrations/pd_parsers.py` (pure functions of captured text, like
`eda_parsers.py`).

**What runs for real, and where (M27).** In CI, the `physical-design` job runs
inside a pinned OpenROAD-flow-scripts image and takes the AXI4-Lite register
block through `synth.run` (Nangate45-mapped), `sta.run` (through OpenROAD's
embedded OpenSTA), and `pnr.run` to a routed layout, for real; the job requires
`openroad` and `yosys`, so those tests fail rather than skip. On the macOS
development machine OpenROAD is not installed (no Homebrew formula, no Docker),
so the same tests skip there. M25 wrote the bindings without any run; section
10 lists what the first real run broke and how each was fixed. The parser
fixtures are now logs captured from those CI runs (section 7).

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
| `tech_lef` | `pnr.run`, `sta.run` through `openroad-sta` | Technology LEF |
| `lef` | `pnr.run`, `sta.run` through `openroad-sta` | Standard-cell LEF(s), comma separated |
| `tie_high`, `tie_low` | `synth.run` (`yosys-liberty`), optional | Tie cells as `CELL/PORT` (M27; for example `LOGIC1_X1/Z`, `LOGIC0_X1/Z` in Nangate45) |
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
hilomap -singleton -hicell <cell> <port> -locell <cell> <port>   ;# only with tie_high / tie_low (M27)
opt_clean -purge
tee -q -o stat.json stat -json -liberty <lib>
write_verilog -noattr -noexpr -nohex -nodec netlist.v
```

The result's metrics add `netlist` (the path to `netlist.v`) and, from
`stat -liberty`, the cell `area`. When the task names the PDK's tie cells
(`tie_high=LOGIC1_X1/Z`, `tie_low=LOGIC0_X1/Z` for Nangate45), constants are
driven by them (M27): OpenROAD's detailed router rejects a netlist whose
constant is a plain `1'b0` net (`DRT-0305`, a ground net it cannot route).
Buffering and multi-corner mapping are not done.

### 4.2 `sta.run`, backends `opensta` and `openroad-sta`

Inputs: `netlist` (from `synth.run`, required), `sdc` (required), `top`
(required), `liberty` (PDK), and optionally `spef` (parasitics). Nirmaan
writes `sta.tcl` in the working directory and runs
`sta -no_init -no_splash -exit sta.tcl`.

**`openroad-sta` (M27).** Packaged OpenROAD builds, including the
OpenROAD-flow-scripts image CI uses, ship `openroad` but no standalone `sta`,
and `openroad` has no OpenSTA-only mode. OpenROAD embeds OpenSTA and accepts
the same commands, so the second backend runs the same script with
`openroad -no_init -no_splash -exit sta.tcl`. OpenROAD links the netlist into
its database, which needs the LEFs first (`[ERROR ORD-2010] no technology has
been read` without them), so `openroad-sta` also needs `tech_lef` and `lef`
and adds `read_lef` lines ahead of `read_liberty`. The registry picks
`opensta` when `sta` is on `PATH`, else `openroad-sta`; the run records which.

```
read_lef <tech>, read_lef <cells> ;# openroad-sta only
read_liberty <lib>            ;# each one
read_verilog <netlist>
link_design <top>
read_sdc <sdc>
read_spef <spef>              ;# only when given
report_checks -path_delay max -digits 3
report_checks -path_delay min -digits 3
report_checks -path_delay min_max -slack_max 0 -group_path_count 100 -endpoint_path_count 1 -digits 3
report_worst_slack -max -digits 3
report_worst_slack -min -digits 3
report_tns -digits 3
report_wns -digits 3
```

Parsed (`parse_opensta`):

| Metric | From |
|---|---|
| `worst_slack` (setup) | `worst slack max <n>` (an unlabelled `worst slack <n>`: the first) |
| `worst_hold_slack` | `worst slack min <n>` (unlabelled: the second) |
| `tns`, `wns` | `tns max <n>`, `wns max <n>` (the label is optional) |
| `violating_endpoints` | every path report ending `slack (VIOLATED)`: endpoint, check (`setup` for `Path Type: max`, `hold` for `min`), and slack, worst first, one per endpoint and check. The report lists at most 100 paths per check (`VIOLATOR_REPORT_LIMIT`), so a summary at the cap says "at least 100" |
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
| `design_area_um2`, `utilization_pct` | the last `Design area <a> um^2 <u>% utilization.` (`u^2` also read) |
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

**The TCL runs against a live OpenROAD in CI (M27).** On Nangate45 the AXI4-Lite
block (862 instances, tie cell included) routes with 0 DRC violations after
detailed routing. Section 10 has the numbers. With no power grid and no tap
cells, those 0 DRC cover the signal routing only; the cells' power pins are
not connected.

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

## 7. Fixtures: captured logs

`tests/fixtures/pd/`:

| File | Provenance |
|---|---|
| `axi4_lite_regs.sdc` | Written for M25: a 100 MHz `aclk`, I/O delays at 20% of the period, for `tests/fixtures/rtl/axi4_lite/` |
| `axi4_lite_regs_fast.sdc` | Written for M27: the same constraints at 5 GHz, which no 45 nm library meets, so STA reports negative slack |
| `tiny_cells.lib` | Written for M25: a toy Liberty library (inverter, buffer, NAND2, NOR2, D flip-flop) with areas and functions but no timing, so `yosys-liberty` maps for real in the main test job. It is not a PDK and cannot time anything |
| `opensta_met.log`, `opensta_violated.log` | **Captured** (M27): `sta.run` through `openroad-sta` on the Nangate45-mapped AXI4-Lite block, under the 100 MHz and 5 GHz SDCs |
| `openroad_route.log`, `openroad_error.log` | **Captured** (M27): `pnr.run` to `route`, and at `utilization=300`, which fails in placement (`GPL-0301`) |

The captured logs come from CI run 36600440325 (openroad/orfs
`26Q3-687-gc63a606f9`). Each starts with one `# CAPTURED:` line naming the run;
everything after it is the log `eda.execute` wrote, unedited. The M25
hand-written `synthetic_*.log` samples are deleted. Two of their guesses were
wrong: the area unit (`u^2`, really `um^2`) and the `worst slack` format
(really `worst slack max <n>`).

---

## 8. Real-tool tests and CI

`tests/test_nirmaan_physical.py` has four real-tool tests that use the M21
`needs(...)` marker: Liberty-mapped synthesis on Nangate45 feeds STA (met at
100 MHz, violated at 5 GHz as a recorded failed run), a full place and route
(0 DRC, wirelength, positive slack, a DEF and a netlist written), and a place
and route at 300% utilization (a recorded failed run). They skip without
`openroad`, or without Nangate45 under `NIRMAAN_PDK_ROOT`, and fail instead of
skipping when `NIRMAAN_REQUIRE_EDA` names `openroad` (or `sta`).

**The CI job.** `physical-design` in `.github/workflows/ci.yml` runs in the
container `openroad/orfs:26Q3-687-gc63a606f9`, pinned by digest. The image
holds everything the tests need, built together:

| What | Source |
|---|---|
| OpenROAD (with OpenSTA embedded) | OpenROAD-flow-scripts `c63a606f9` (2026-09-29), OpenROAD submodule `c487fc70` (its `openroad -version` prints `unknown`) |
| Yosys | 0.68+post, from the same image |
| PDK | Nangate45 (`flow/platforms/nangate45`: `NangateOpenCellLibrary_typical.lib`, `.tech.lef`, `.macro.mod.lef`), pinned with the image |
| Python | 3.12 through `astral-sh/setup-uv` (the image's Ubuntu 22.04 has 3.10) |

Choices, and why:

* **The ORFS image, not packages.** Precision Innovations' GitHub releases
  stop at December 2024 and only for Ubuntu 20.04 and 22.04 (later releases
  moved off GitHub); building from source takes far longer than the test job.
  The image is about 1.6 GB compressed and pulls in about a minute. It carries
  a Yosys and a PDK matched to the OpenROAD it holds, so the platform files
  need no separate download or cache.
* **Nangate45, not sky130.** It is small, open, and ships in the image; sky130
  through `ciel` or `volare` is far larger and needs a cache.
* **A separate job.** The main `test` jobs are unchanged; only
  `tests/test_nirmaan_physical.py` runs in the container, with
  `NIRMAAN_REQUIRE_EDA="yosys openroad"`, and uploads every run's working
  directory (logs, scripts, results) as the `pd-logs` artifact.
* The job takes about 2.5 minutes, in parallel with the 4.5-minute main jobs,
  so the wall time of CI does not change.

To run the tests elsewhere, put `openroad` and `yosys` on `PATH` and point
`NIRMAAN_PDK_ROOT` at an OpenROAD-flow-scripts `flow/platforms` directory:

```
export NIRMAAN_PDK_ROOT=/path/to/OpenROAD-flow-scripts/flow/platforms
NIRMAAN_REQUIRE_EDA="yosys openroad" python -m pytest tests/test_nirmaan_physical.py
```

---

## 9. Not in this milestone

M29 added the power grid, tap and filler cells, clock-tree synthesis, repair,
parasitic extraction feeding signoff STA, standalone OpenSTA in CI, and
sky130hd: see `docs/PD_SIGNOFF.md`. The list below is as M25 and M27 left it.

* Power-grid generation, tap and filler cells, clock-tree synthesis, repair
  (`repair_design`, `repair_timing`), and parasitic extraction (`extract_parasitics`
  and a SPEF handed to `sta.run`).
* Resuming a flow from a saved database instead of re-running earlier stages.
* Multi-corner, multi-mode timing (one Liberty set per run).
* Physical verification (`pv.run`: DRC and LVS with Magic, KLayout, or Netgen)
  and power analysis (`power.run`).
* A run of standalone OpenSTA (`sta`): the image has none, so the `opensta`
  backend's script is exercised only through `openroad-sta`.
* sky130 in the real-tool tests, and any local OpenROAD run on macOS.
* A deliverable folder of its own for physical views (they stay in `04_rtl`).
* Adopting `before_review` file checks (M23) in the physical workflow: the
  netlist and DEF are not yet recorded as artifact files.

---

## 10. M27: what the first real run broke

| Found in CI | Fix |
|---|---|
| No `sta` in any packaged OpenROAD; `openroad` has no OpenSTA-only mode | `openroad-sta` backend for `sta.run` (4.2) |
| `[ERROR ORD-2010] no technology has been read`: OpenROAD links into its database | `openroad-sta` reads the LEFs, and needs them from the PDK |
| `[ERROR DRT-0305] Net zero_ of signal type GROUND is not routable`: Yosys left `assign ... = 1'b0` | `tie_high` and `tie_low` on `yosys-liberty` (`hilomap`) |
| `Design area 1665 um^2`: the parser expected `u^2`, so area and utilization were never read | the parser reads `um^2` (and `u^2`) |
| `worst slack max 7.120`, `tns max 0.000`: the parser expected unlabelled lines, so no slack was read and a clean route "failed" with "no constrained timing paths" | the parser reads the `max`/`min` label |
| `[WARNING STA-0502/0503] -endpoint_count / -group_count is deprecated` | `-endpoint_path_count`, `-group_path_count` |
| The 5 GHz violator report lists exactly 100 setup endpoints: the cap, not the count | "at least 100" in the summary |

The numbers from the captured runs (Nangate45, typical corner, ideal clock,
no CTS):

| Run | Result |
|---|---|
| STA, 100 MHz | met: worst setup slack 7.264 ns, worst hold slack 0.101 ns, TNS 0 |
| STA, 5 GHz | violated: worst setup slack -0.905 ns, TNS -157.481 ns, at least 100 setup endpoints; hold 0.060 ns |
| Place and route | routed: 1665 um^2 of cells at 41% utilization, 0 DRC violations (527 after the first detailed-routing iteration), wirelength 10783 um, worst setup slack 7.120 ns, hold 0.103 ns |
| Place and route at 300% | failed in place: `GPL-0301 Utilization 352.253 % exceeds 100%` |

M25 asked whether `pnr.run` needs `set_routing_layers`: on Nangate45 it does
not; the global and detailed routers ran with their defaults, and routing used
metal2 to metal5.


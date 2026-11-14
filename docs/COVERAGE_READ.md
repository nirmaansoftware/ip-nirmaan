# Code coverage: `coverage.read` through Verilator (M70)

Wave 2 of the capability build-out (council record
`council/records/2026-10-18-capability-buildout.md`, section 10: Verification;
the wave 2 plan's tool item T2). The founder's decision of 2026-11-13 in that
record ("Founder decisions (2026-10-30)", item "New tools for wave 2"): eqy,
verilator_coverage and cocotb may be wired into the tool broker, each in its own
milestone, with no spending. This is the verilator_coverage one.

## The gap

- `coverage.read` was `CONTRACT_ONLY` since the catalog began: the broker
  refused it, so every coverage requirement in every workflow (new-ip,
  feature-addition, parameter-change, rtl-change, signoff-preparation, block
  verification) could be met only by a VeriTriage session or a named human
  attesting to a run made elsewhere.
- Block verification's `coverage` stage (M68) gated nothing before review, so
  the `code_coverage` skill had no seat a tool judges.
- An engineering-graph `coverage_point` item could never be backed.

Verilator ships `verilator_coverage` beside `verilator` (Ubuntu's package in CI,
Homebrew on the Mac), and both are free, so no install, licence or spend is
added.

## The tool

| | |
|---|---|
| Tool | `coverage.read`, now `AVAILABLE`, risk `execute` (it builds and runs code; it was `read` as a contract) |
| Backend | `verilator-coverage`: `verilator` and `verilator_coverage` on `PATH` |
| Parameters | `sources` and `top` (as `simulator.run`), `design` (the files whose coverage counts), `backend`, `workdir`, `timeout` |
| Metrics | `line`, `toggle`, `branch` (percent of the design files' points hit at least once), `coverage` (covered and total points per type), and the simulation's own (`checks`, `finished`, ...) |
| Outputs | `log`, `coverage` (the data `verilator_coverage --write` wrote), `info` (the same as an lcov report) |

One run, four steps, in the run's own directory (M53):

1. `verilator --cc --exe --build --timing --coverage-line --coverage-toggle`
   over the sources, top module `top`, with the backend's own C++ main
   (`COVERAGE_MAIN`, written into the run's directory): Verilator's main
   loop, then the coverage data written to a path the backend names.
   Verilator 5.020, which CI installs from Ubuntu 24.04, has a `--binary`
   main that writes no coverage and no `+verilator+coverage+file+` argument,
   so the backend does not rely on either.
2. The model, with the run's nonce (`+nirmaan_nonce=`).
3. `verilator_coverage --write coverage.dat` reads that data and writes it back.
4. `verilator_coverage --write-info coverage.info` writes the lcov report.

A failing step stops the run, as for every backend.

## What a pass means

`parse_coverage` (`integrations/eda_parsers.py`), a pure function of the log
and the data file, tested on captured data with no tool installed:

1. The simulation passed exactly as `simulator.run` judges one: every step
   exited 0, `$finish` was reached, and the testbench printed its one verdict
   with this run's nonce, at least one check passed and none failed
   (`docs/GATE_INTEGRITY.md`). Coverage of a testbench whose checks fail is not
   read at all.
2. The run wrote coverage data.
3. Every design file has at least one coverage point. A file not built under
   the top module measured nothing, so the run fails rather than report 100
   percent of nothing.

Only points in the design files count, never the testbench's: by default every
source but the one that declares `top`; with `design`, exactly those files. A
type's percentage is rounded down to two places, so a run never rounds up into
a bound. A type with no point in the design files is not reported, so a bound
on it fails ("never reported", M48). The point's type is its `t` key, or the
`v_<type>/` prefix of its `page` in data from a Verilator that writes no `t`.

**The threshold is a bound, not a parameter.** M48 made limits a requirement's
own `bounds`, checked by the broker after a passing run; `coverage.read` takes
no `min_` parameter. A run made with bounds records them (`ToolRun.bounds`),
and a requirement counts only a run checked against each of its bounds.

## What the run refuses (nothing is simulated)

Before any step (`coverage_problem`), so a refusal records a failed run with no
log, the way a simulation's testbench-only check does:

- Everything `simulator.run` refuses: only the testbench may end the run, read
  plusargs, open files or reach outside the language (M53).
- A source that is not Verilog (`.v`, `.sv`, `.vh`, `.svh`): Verilator would
  also compile C++ or read a `.vlt` configuration given on its command line.
- `$fopen`, `$system`, `$c` or DPI in any source, the testbench included: each
  could write the data file the run reads or change its counts.
- A Verilator configuration (`` `verilator_config ``), a coverage pragma
  (`coverage_off`, `coverage_block_off`, read in comments too) or an
  `` `include `` in any file that is not a design file: each can turn points
  off in another file, or bring in text the check never read. In the design
  files (in a gate, the approved RTL) they are there for its reviewer to see.
- A `design` file that is not a source, a design file that is the testbench,
  or no design file at all.

## Block verification's coverage gate

The wave 2 plan (routing item R1) gives block verification's coverage stage
`coverage.read` as its before-review gate once the tool is wrapped. That stage
(planned when the request says "coverage") now:

- builds on `design-under-test` and `testbench` (both approved before it);
- writes a `testbench` and a `coverage_report`;
- must pass, before review, `coverage.read` over the approved RTL
  (`sources` and `design`, both upstream) and the seat's own testbench
  (`sources`, `top` from its entry), with the bounds `COVERAGE_TARGETS`:

| Metric | Bound | Why |
|---|---|---|
| `line` | at least 90 | a directed testbench that exercises a block reaches nearly every line (the W2-E1 `irq_ctrl` testbench reaches 100); the margin is for a line no stimulus can reach |
| `toggle` | at least 75 | wide buses and constant inputs leave toggles a good directed test never reaches (the W2-E1 `irq_ctrl` testbench reaches 79.7 with Verilator 5.052) |
| `branch` | not bounded | read and recorded; Verilator versions count branch points differently |

These replace the stage's recorded-evidence requirement (a coverage run, a
VeriTriage session or a human attestation). This is a gate-semantics change
that adds a gate: the stage that gated nothing before review now gates on a
real run. No other stage, workflow or requirement changes; the other
workflows' coverage requirements still accept recorded evidence and now can
also be met by a real `coverage.read` run.

**Grant.** The tool's risk is now `execute`, so, like every tool that runs
code, only roles at the working band or above that hold a skill naming it
(`code_coverage`, `functional_coverage`) may use it. The two coverage interns, who read it as a contract, no longer hold it.

## Tests

`tests/test_coverage_read.py`:

- the catalog entry, its parameters and its one backend;
- the parser on captured data (`tests/fixtures/eda/verilator_coverage_idle.dat`):
  types and files, design files only, rounding down, the `page` fallback, and
  five ways a run is no evidence (a failed check, a failed step, a forged
  verdict, no data, a design file not built);
- each refusal above, run without any tool;
- **the must-fail pair**, for real: on the M21 counter, `counter_full_tb.v`
  (counts through a wrap, holds, resets mid-count) reaches 100 percent line,
  toggle and branch and meets `COVERAGE_TARGETS`; `counter_idle_tb.v` holds the
  counter in reset, passes its own four checks, and reads 66.66 percent line
  and 18.75 percent toggle, so the same bounds fail it. Without bounds it
  passes: only the threshold fails it. A testbench whose own check fails reads
  no coverage;
- the coverage stage's gate, and, through the eval harness (`run_case`), a
  coverage seat that reaches review with the full testbench and does not with
  the idle one.

CI: `verilator_coverage` joins the test job's `NIRMAAN_REQUIRE_EDA`, so these
tests fail rather than skip there, and the `no-tools` job's list of executables
that must be absent.

## Not in this milestone

- Merging the data of several runs (a regression's) into one measurement.
- Expression, FSM and user coverage (`--coverage-expr`, covergroups): Verilator
  reports them, and `parse_coverage` counts any type it finds, but no build
  here enables them and no bound reads them.
- Exclusions a reviewer records outside the RTL.
- Bounds on an eval check's `cover_tool`: the must-fail scorer runs a cover tool
  without bounds, so `dv/coverage-irq-ctrl` (W2-E5) needs the scorer to carry
  the stated line and toggle thresholds.

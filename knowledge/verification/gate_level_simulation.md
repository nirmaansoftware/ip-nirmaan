---
id: verification/gate_level_simulation
skill: gate_level_simulation
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
  - open | lowRISC, OpenTitan DVSIM testplanner tool (Apache 2.0) [OTPlan] | https://opentitan.org/book/util/dvsim/doc/testplanner.html
  - open | Verilator manual: Input Languages (Unknown States, Gate Primitives, Specify blocks) [VLang] | https://verilator.org/guide/latest/languages.html
  - open | Verilator manual: Executable and Argument Reference (the --x-assign and --x-initial options) [VArg] | https://verilator.org/guide/latest/exe_verilator.html
  - open | Yosys manual: Mapping to cell libraries [YCell] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/using_yosys/synthesis/cell_libs.html
  - open | Yosys manual: command reference for backends, write_verilog [YWV] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_backends.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K4 session (wave 2 knowledge batch, plan row W2-K4, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# Gate-level simulation

Running the same tests on a synthesized netlist as on the RTL, and reading the
differences. Tags in brackets name the sources above; a line marked
"inference" is this document's own reasoning. This skill holds no tool, so no
gate line is cited, and nothing here has been run.

## Why it is run

- Ordinary RTL simulation ignores the uncertainty of unknown (X) control
  signals and gives predictable outputs, so it can miss a design problem that
  comes from an unknown value failing to propagate. Gate-level simulation can
  show such problems [OTDV].
- OpenTitan's alternative is to enable X propagation modes in the RTL
  simulator, so that these problems show without running gate-level
  simulation. Its optimistic mode is closer to real hardware; its pessimistic
  mode is more pessimistic than a standard gate-level simulation. OpenTitan
  picked the pessimistic mode, to keep X out of conditions [OTDV].
- OpenTitan's testplan lets an entry carry a `gls` tag, to run that planned
  test at gate level too [OTPlan]. The plan, not the netlist, decides which
  tests are repeated (inference).

## How the netlist is made and run

- Synthesis in Yosys ends with `write_verilog`, which writes a Verilog file
  another tool can load. Mapping to a cell library uses `dfflibmap` and `abc`
  with a Liberty file first [YCell].
- `write_verilog` has options that change what is in the netlist file. By
  default internal cells are converted to Verilog expressions; `-noexpr`
  keeps them as cells, and `-siminit` adds initial statements to set
  flip-flops in that mode [YWV]. Internal auto-generated names are shortened
  unless `-norename` is given [YWV]. So the signal names a testbench probes in
  the RTL may not exist in the netlist (inference).
- A netlist that keeps library cells needs a simulation model of each cell to
  run (inference). For a cell library the model comes from the library's
  vendor, so what a run can read is limited by what that library allows
  (inference; this repository uses no library and runs none).
- Run the RTL's self-checking tests unchanged on the netlist, with the same
  stimulus and the same expected values. Differences are then in the
  design, not in the tests (inference).

## What to expect in the differences

- X on an output at the start of a run usually points to a flip-flop that is
  not reset or initialised, or to a path from one. Trace it to that flop, and
  decide if reset is missing or the netlist adds the X (inference).
- X pessimism means a gate-level X where hardware would settle to a value;
  optimism means a simulator hiding an X that hardware would not settle.
  Neither is by itself a design bug or a pass; each needs the cause traced
  (inference). OpenTitan chose the pessimistic RTL mode to keep X out of
  conditions [OTDV].
- Verilator is mostly a two-state simulator. It substitutes constants for
  explicit X values and random constants for initial values, controlled by
  `--x-assign` and `--x-initial`, and its manual says setting all variables to
  one at startup finds the most problems, since control signals are usually active
  high [VLang] [VArg]. So a Verilator run of a netlist is not the same
  experiment as a four-state run (inference).
- Verilator converts the two-state gate primitives, does not support the
  three-state and MOS primitives, and ignores specify blocks and timing checks,
  using the typical value of any min:typ:max delay [VLang]. So Verilator
  results on a netlist carry no timing information from the library
  (inference).

## Common failure modes

- Reading every X as a design bug without tracing it to its source.
- Treating a netlist that matches RTL under a two-state simulator as evidence
  about unknown handling (inference).
- Running only the tests that are easy to rerun, so the netlist's reset and
  power-up paths are never exercised (inference).
- Comparing results from different stimulus or seeds, so a difference could be
  the test and not the netlist (inference).
- Calling a gate-level run timing evidence when the simulator ignored the
  timing data [VLang].

## How a result is checked

- Confirm the netlist is the one the synthesis step wrote, and the RTL tests
  are unchanged (inference).
- Confirm each difference from the RTL run is explained: a named flop, a
  reset, or an initial value (inference).
- State the simulator and its X handling next to the result, since the same
  netlist can pass in one and fail in another [VLang] [VArg].

## Sources

- [OTDV] X propagation and why gate-level runs reveal unknown problems.
- [OTPlan] The `gls` tag on a testplan entry.
- [VLang], [VArg] How Verilator handles X values, gate primitives and delays.
- [YCell], [YWV] How a Yosys netlist is written and what its options change.

---
id: verification/performance_verification
skill: performance_verification
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | EEMBC, CoreMark README: run rules, reporting rules and theory of operation (Apache 2.0) [CM] | https://github.com/eembc/coremark
  - open | Embench, README (code GPL-3.0, so no code is taken from it) [EmbR] | https://github.com/embench/embench-iot
  - open | Embench Task Group, Embench User Guide, issue 1.0 (GFDL 1.2): recording reliable results and statistics of benchmarks [EmbG] | https://github.com/embench/embench-iot/blob/master/doc/README.md
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K6 session (wave 2 knowledge batch, plan row W2-K6, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# Performance verification

Turning a throughput, latency or cycles-per-task claim into a measurement that
names its workload, and reporting it so another person can repeat it. Tags in
brackets name the sources above; a line marked "inference" is this document's
own reasoning. This skill's card holds no tool
(src/nirmaan/company/skills.py:460-466), and nothing here has been run. The
sources are software benchmark suites for processors; how they apply to an
accelerator or a bus is this document's reasoning (inference).

## A claim is a quantity plus a workload

- A claim such as "one result per cycle" or "N cycles for this task" means
  nothing without the program or stimulus that produced it and the conditions
  of the run (inference).
- CoreMark's reporting rule is a good model of the idea: a score is written
  with the iterations per second, the compiler version and flags, any data and
  code placement, and the parallel setup, and the memory placement may not be
  left out when a per-MHz score is given [CM].
- Embench says to record the platform and its clock speed, whether it is real
  or simulated, and for a simulated one how accurate it is (fully cycle
  accurate or cycle approximate) and its configuration, such as branch
  predictor and cache sizes. It also asks for the toolchain versions, the
  flags, and the suite version [EmbG]. The stated aim is that anyone with the
  same platform and toolchain can duplicate the result [EmbG].
- Embench adds that, for meaningful execution results, simulated hardware must
  be strictly cycle accurate [EmbR]. A functional simulation that has no
  timing model therefore cannot support a cycle claim (inference).

## Choosing the workload

- Embench's principle is a suite of real programs rather than one synthetic
  program, because a realistic workload is easier to represent that way and a
  suite is easier to evolve [EmbG]. It also says Dhrystone, CoreMark and
  Linpack are widely reported but not well regarded, possibly because they are
  free and easy to port [EmbG].
- CoreMark's design goals are simplicity and testing only a processor's core
  features [CM]. Its own theory section explains that the work must depend on
  values the compiler cannot know in advance (volatile inputs, run-time seeds),
  so the computation cannot be removed at compile time, and the printed
  results must be valid so the work is known to have run [CM].
- The same trap exists for RTL workloads: a test whose result is constant or
  unchecked may measure nothing (inference). A measured run should still check
  its functional result (inference).
- Embench measures with hot caches: each benchmark runs its whole code several
  times before the timing run starts, and a `warmup_heat` setting controls
  how many times [EmbR] [EmbG]. Whether a claim is for cold or warm state
  should be stated (inference).

## How to measure and report

- Embench times the region between a start trigger and a stop trigger using a
  hardware cycle counter or fast timer inside the device being measured, at a
  rate well above the benchmark's own run time [EmbG]. In an RTL simulation the
  matching idea is to count clock cycles between two observable events, and to
  state which events (inference).
- CoreMark requires at least 10 seconds of run time for a valid report, and it
  allows the iteration count to be set for cases such as a simulator [CM].
  Embench scales runs to about 4 seconds [EmbR]. In a cycle-accurate
  simulation, wall-clock time is not the quantity; the cycle count between the
  events is (inference).
- CoreMark runs a second pass with validation parameters and checks
  checksums, and a result is valid only if validation succeeds [CM].
- To summarise a suite, Embench computes each result relative to a reference
  platform, then takes the geometric mean with the geometric standard
  deviation, so one number summarises many programs and the spread is
  visible [EmbG]. A mean of cycles across unlike workloads is not meaningful
  by itself (inference).
- Embench speed and size use opposite directions: a larger speed value is
  better and a smaller size value is better [EmbG]. A report states which
  direction is good (inference).

## Common failure modes

- A throughput or latency claim with no workload (the card's own failure
  mode).
- Cycle counts taken from a non-representative test, such as a directed test
  of one corner (the card's second failure mode, src/nirmaan/company/skills.py:465).
- Comparing runs with different compiler flags, data placement or simulator
  configuration, which the reporting rules above are written to prevent [CM]
  [EmbG].
- A cycle claim from a simulator that has no timing model [EmbR].
- Mixing cold and warm results (inference).
- A workload the tool can optimise away, or a run whose functional result is
  not checked [CM].

## How a result is checked

- The record names the quantity, the workload and its version, the stimulus or
  program inputs and seeds, the design configuration, the simulator and its
  timing accuracy, and the two events that bound the count (inference, from
  [CM] and [EmbG]).
- The functional result of the measured run passes its own check (inference).
- A rerun with the same inputs gives the same count in a cycle-accurate
  simulation, and a difference is explained (inference).
- Each claim states how the measurement was made and what it does not cover,
  such as other workloads or other configurations (card check; inference).

## Sources

- [CM] Run rules, reporting syntax, validation passes and the controlled-output
  design.
- [EmbR], [EmbG] What to record, hot caches, cycle accuracy for simulation,
  relative scores and the geometric mean.

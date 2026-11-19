# The judge controls (M87, third pull request)

Gates WF4 and WF5 need each case's judge proven by replays with no model call,
run in CI, before the first trial. `evals/flow/controls.json` lists 27
controls. Each is a seat answer made of committed files and the whole-flow
case's own held-out checks it must pass or fail, sometimes with the RTL a
check runs on put in another's place. `tests/test_whole_flow_controls.py` runs
each as a single-seat case through the real runner, gates, scorers and broker
(`evaluate`), with no change to `runner.py`: the seat replays the files, its
own before-review checks run, and the judge rules. A control's seat reaches
review, so a failed check is the judge's verdict. The tool-backed tests need
the EDA tools; CI's test job names them in `NIRMAAN_REQUIRE_EDA`, so there they
run and never skip.

What they show:

- the reference passes: the timer's checks 1 and 2, the register block's
  checks 1 to 3, and checks 4, 6 and 7 for the reference driver;
- each planted fault fails: the reference testbench fails a flow ending in
  each register block mutant and in three of the timer mutants; the fourth,
  `decode_alias`, is refused by the seat's own lint gate, so that flow stops
  before review (the reference testbench catching it is shown by the must-fail
  check of `timer-reference`); the weak timer testbench and a testbench that
  checks next to nothing fail the must-fail checks; the held-out test fails
  the wrong map header under the map's name, the three wrong drivers, and the
  reference driver on `wstrb_ignored` and `okay_unmapped`;
- the conforming RTL (`axi4_lite_regs_lat2.v`) passes the checks that run on
  the flow's RTL (1 and 2; check 5 runs on it only in the strict driver's
  control, below), and the held-out test passes on it;
- the range-accepting reference tests pass on both RTLs, and the testbench
  written to the variant's one choice fails check 3 on the reference RTL.
  Known limit: check 3 runs the flow's testbench on the reference RTL alone,
  so a testbench strict about the reference's own choice (a response exactly
  1 cycle after its request) passes it, though it fails on the conforming
  RTL. No change: the council record accepts this, since checks 3, 6 and 7
  are "fair by the rule, which the fixed document states to the seats, and
  not by the conforming RTL alone"
  (`council/records/2026-11-17-g3-whole-flow-cases.md`, lines 301 to 303);
- `fw.test` works under the must-fail scorer (check 7: the clean run passes
  and `wstrb_ignored` and `okay_unmapped` are caught);
- `b_before_w` is not visible through the HAL: under the must-fail scorer
  with that mutant alone, the reference driver test passes on it. The ruling
  assumed so and left it out of check 7; this run records it;
- the reference driver test passes on both RTLs with the same bus transfers.
  That shows one test. That a driver test that uses only `read32`, `write32`
  and the driver interface cannot be strict about latency on this block rests
  on the harness's construction (the reach guard) and this run together;
- the wait probe (`driver-wait-probe`, gate WF14): a driver test that calls
  `nirmaan_irq_wait` between transfers passes on both RTLs with the same bus
  transfers, an attempt to see latency that does not;
- the strict fixtures (gate WF15, section below): a driver test and a driver
  that are strict about latency by address arithmetic pass on the conforming
  RTL and fail checks 7 and 6 on the reference RTL; their siblings on the
  simulator's clock are refused by the object screen (gate WF16) in checks 4
  to 7; and the SoC's cycle counter is refused before review.

Each control prints one `FLOW-CONTROL` line with its verdicts and run
summaries. `evals/flow/controls_record.json` keeps those lines from a named
CI run (the check record, not an eval record), and the test holds every later
run to the verdicts it records.

Left for the whole-flow runner: the reference flow replayed through every
seated stage, a flow with a planted upstream fault, and check 5, which takes
the RTL from another stage.

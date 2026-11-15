---
id: verification/python_verification
skill: python_verification
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | cocotb documentation: First Steps (BSD-3-Clause) [CocoFirst] | https://docs.cocotb.org/en/stable/first_steps.html
  - open | cocotb documentation: library reference (BSD-3-Clause) [CocoRef] | https://docs.cocotb.org/en/stable/library_reference.html
  - open | cocotb documentation: Troubleshooting (BSD-3-Clause) [CocoTrouble] | https://docs.cocotb.org/en/stable/troubleshooting.html
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K3 session (wave 2 knowledge batch, plan row W2-K3, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the simulator this skill holds is available; this document is knowledge, not evidence.

# Python-based verification

Writing cocotb tests that drive a design from Python and check it, and how this
repository's cocotb backend of `simulator.run` judges them. Tags in brackets
name the sources above; a line marked "inference" is this document's own
reasoning; a line marked "gate" names the repository code that backs it.

## What a cocotb test is

- A test is a coroutine function decorated with `@cocotb.test` that takes the
  design handle, conventionally `dut`; signals are read and written as
  attributes of that handle, with the `value` attribute [CocoFirst].
- cocotb runs on the simulator: the design is built and simulated by a
  supported Verilog simulator, and the Python tests are loaded into that run
  [CocoFirst].
- A write from Python is inertial, like a non-blocking assignment: reading the
  signal straight after writing it still shows the old value, and the new one
  appears only after simulation time passes [CocoFirst].
- Tasks started with `cocotb.start_soon` run concurrently with the test, but
  only one runs at a time, so there is no race inside the Python; when the main
  test coroutine ends, the other tasks are cancelled [CocoFirst].
- `Clock` is the library's reusable clock driver; the tutorial starts it before
  it awaits any edge [CocoFirst].

## How a test is written

- Reset first, with every input given a value, then hold reset for a few clock
  edges before the first check [CocoFirst].
- Check with plain `assert` statements. A failing assertion ends that test and
  the log shows the line, the observed value and the expected one
  [CocoFirst].
- After `await RisingEdge(clk)` the value you read is the one from the end of
  the previous time step, because the processes sensitive to the edge have not
  run yet. Wait a small time, or use `ReadOnly`, before sampling a registered
  output. `ReadOnly` is the phase where all signals are stable and no more
  events can be scheduled, so no further events can be scheduled in that step
  [CocoFirst] [CocoRef].
- Compute the expected value in Python from the specification and update it on
  every edge, as the counter example does with a running `expected_value`; the
  wrap-around case in that example is the one a naive model gets wrong
  [CocoFirst]. A model written by reading the RTL repeats the RTL's mistake
  (inference).
- Take stimulus from a seed. cocotb prints the seed it used for each run, and
  `COCOTB_RANDOM_SEED` set to that number recreates the stimulus [CocoRef].
- Give a test a `timeout_time`: the decorator offers it as protection against
  deadlock [CocoRef].
- Do not call an `async def` function, or build a trigger, without `await`;
  the simulation then hangs [CocoTrouble].
- A directed scenario list and an in-test random phase can share one module:
  directed scenarios for the corners the specification names, random traffic
  for the interactions between them. OpenTitan's IP-level environments take a constrained random
  approach and use directed tests for illegal and error stimulus [OTDV].

## What the cocotb gate demands

- cocotb is a backend of `simulator.run`, chosen by the parameter `backend`
  set to `cocotb`; without that name the backend refuses to run, and a run
  without it still means an HDL testbench (gate:
  src/nirmaan/integrations/cocotb_runner.py:64-65, 118-119; docs/COCOTB.md, section "The runner"). The call takes
  `sources` (the design), `top` and `cocotb` (the Python test modules), all
  required by the backend (gate: cocotb_runner.py:118-119;
  src/nirmaan/company/tools.py:131-132).
- The `expect` parameter takes `pass` here, or no value; any other value is
  refused and nothing runs, so a failure cannot be reproduced through cocotb
  (gate: cocotb_runner.py:66-68).
- Each test file must be a `.py` file whose name is a valid Python module name,
  and two files may not share a name; otherwise the run is refused before
  anything runs (gate: cocotb_runner.py:71-74).
- With cocotb every HDL source is design. A source that ends the simulation,
  reads its arguments, opens a file or reaches outside the language is
  refused (gate: cocotb_runner.py:75-86).
- The run passes only when cocotb wrote its results file, at least one test
  passed, none failed, its totals line was printed exactly once and agrees
  with the file, and the steps exited zero (gate:
  src/nirmaan/integrations/eda_parsers.py:620-672). Exit status alone is
  not read, since `vvp` exits zero on failed tests (gate: docs/COCOTB.md,
  section "What a run does").
- A run made with this backend answers a requirement only when the requirement
  fixes `backend: cocotb`, so it never stands in for an HDL testbench's
  verdict gate (gate: src/nirmaan/models/work.py:255, 296-305).
- cocotb counts tests, not checks, so a test that asserts nothing passes
  (gate: eda_parsers.py:620-627). The Python is not sandboxed and could write
  a passing results file itself, so a pass shows only that the author's Python
  reported success (gate: docs/COCOTB.md, section "Trust model"). The
  evidence that a testbench checks something is the must-fail scorer: it runs
  the same tests on a planted mutant of the RTL and requires them to fail
  (gate: src/nirmaan/evals/scorers.py:135-224).

## Common failure modes

- A test that never awaits a clock edge before it checks, so it reads
  the values from before the first edge [CocoFirst].
- A test with no `assert` after the clock starts: every mutant passes.
- Reading a registered output right after the edge trigger, so the check
  sees the previous cycle (inference from [CocoFirst]).
- A Python model copied from the RTL, so a wrong constant is in both
  (inference).
- Stimulus that never offers two events in the same cycle, or a reset in the
  middle of a frame (inference).
- Checking only at the end of a phase: the first wrong cycle is then lost.

## How a result is checked

- Read the totals line and the failing test's assertion text, not the exit
  status (gate: eda_parsers.py:620-672).
- Confirm the run named `backend: cocotb` and the test modules it ran are the
  ones submitted (gate: cocotb_runner.py:64-74).
- Run the same tests on a copy of the RTL with one behaviour changed. If they
  still pass, a check is missing, and the missing scenario is the one the change
  touched (inference).
- Record the seed from the log so the run can be repeated [CocoRef].

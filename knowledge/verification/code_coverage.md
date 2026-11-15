---
id: verification/code_coverage
skill: code_coverage
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | Verilator manual: Coverage Analysis (Simulating) [VCov] | https://verilator.org/guide/latest/simulating.html
  - open | Verilator manual: verilator_coverage [VCovExe] | https://verilator.org/guide/latest/exe_verilator_coverage.html
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K1 session (wave 2 knowledge batch, plan row W2-K1, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the coverage tool this skill holds is available; this document is knowledge, not evidence.

# Code coverage

Reading line, toggle and branch coverage from a self-checking simulation,
deciding what a gap means, and how this repository's coverage gate measures it.
Tags in brackets name the sources above; a line marked "inference" is this
document's own reasoning; a line marked "gate" names the repository code that
backs it.

## What each metric means

- Line coverage counts executions of each basic block; branch coverage adds a
  counter at each code flow change; toggle coverage puts a counter on every bit
  of every signal and counts edge changes [VCov].
- Toggle coverage in Verilator skips signals local to tasks or begin/end
  blocks, signals that start with an underscore, integers, and signals wider
  than 256 bits of storage; a module instantiated with different parameters
  counts separately [VCov].
- Edges near time zero, while the model settles, can be counted; Verilator
  suggests zeroing all coverage just before reset is released [VCov].
- OpenTitan lists line, toggle, FSM state and transition, conditional and
  branch coverage as the code metrics, and treats full toggle coverage of
  every bit as hard and of little use: it closes toggle on the block's ports
  [OTDV].
- Full code coverage is not a verdict on correctness. It shows code ran, not
  that its result was checked; it points at an incomplete test plan, and
  functional coverage answers whether the specified behaviour was seen [OTDV].

## What the coverage gate does

- `coverage.read` builds the testbench and design with Verilator's line and
  toggle coverage, runs it, and reads the data with `verilator_coverage`
  (gate: src/nirmaan/integrations/eda.py:588-599). Branch percentages in the
  result come from whatever points the data holds (gate:
  src/nirmaan/integrations/eda_parsers.py:544-583); the build asks for line and
  toggle only.
- The simulation is judged first as `simulator.run` judges it: one verdict with
  the run's nonce and no failed check. If it fails, coverage is not read (gate:
  eda_parsers.py:544-565).
- Only points in the design files count, never the testbench. By default the
  design is every source except the file that declares the top module, and a
  `design` parameter names them; each must be among the sources, and none may
  declare the top module (gate: eda.py:516-559).
- A percentage is points hit at least once over all points, rounded down to two
  places, so it never rounds up into a bound. A design file with no point at
  all fails the run, because coverage that measured nothing is not evidence
  (gate: eda_parsers.py:565-583).
- No source may use `$fopen`, `$system`, `$c` or DPI (gate: eda.py:506-509,
  552-555). A file that is not a design file, the testbench included, may not
  carry a Verilator configuration, an `include`, or a coverage on/off pragma,
  since each could change the counts from outside the design; a design file may
  carry them, left for its reviewer (gate: eda.py:511-513, 552-553). The gate
  sets no threshold; a requirement's bounds on `line`, `toggle` and `branch`
  are checked after a passing run (gate: eda_parsers.py:544-556).

## Closing a gap

- Read the annotated source: `verilator_coverage --annotate` marks each line
  below the minimum count, 10 by default, and `--annotate-points` shows each
  point; the console report forms are in the tool's usage list [VCovExe].
  The repository's gate writes the data and an lcov report instead
  (gate: eda.py:598-599).
- For each uncovered point choose one: add stimulus that reaches it; show it is
  unreachable under the design's constraints; or mark it out of scope
  (inference). OpenTitan records every exclusion with a category tag
  (unreachable, non-RTL, unsupported, external, low risk), requires a written
  reason for the last three kinds, and has the designer sign off in its own review [OTDV].
- Do not use `coverage_off` or an assertion `$stop` branch to hide a gap:
  Verilator drops lines with `$stop` from coverage on the assumption that they
  are error checks [VCov] [VCovExe], so such a branch is invisible, not covered
  (inference). The gate does not stop a design file from carrying
  `coverage_off` (gate: eda.py:552-553), so a reviewer must look for it.
- A fixed bound such as 90 percent is a requirement's choice, not a property of
  the tool. Report the number and the unexplained points together (inference).

## Common failure modes

- A testbench that only resets the block and reads registers: its checks pass
  and toggle coverage stays low.
- Counting dead code as covered, or excluding live code to reach a bound.
- Reading coverage from a run whose checks failed, or merging data from runs
  of different designs.
- Combinational blocks over-counted when `UNOPTFLAT` is disabled [VCov].
- Treating 100 percent code coverage as done without functional coverage [OTDV].

## How a result is checked

- Confirm the design files named in the result are the files under test, and
  the testbench is not among them (gate: eda.py:516-559).
- Check that the same run passed its checks, then list each uncovered point
  with its reason (inference).
- Re-run after adding stimulus; coverage only rises if the new test reaches
  new points, which the point counts show [VCovExe].

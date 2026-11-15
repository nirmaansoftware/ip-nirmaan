---
id: verification/directed_testing
skill: directed_testing
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
  - open | Verilator manual: Simulating (Verilated-Model Runtime) [VSim] | https://verilator.org/guide/latest/simulating.html
  - open | Verilator manual: Arguments (verilator executable) [VArg] | https://verilator.org/guide/latest/exe_verilator.html
  - open | Gisselquist, Building a Verilator test bench, ZipCPU blog, 2017 [ZVer] | https://zipcpu.com/blog/2017/06/21/looking-at-verilator.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K1 session (wave 2 knowledge batch, plan row W2-K1, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the test tool this skill holds is available; this document is knowledge, not evidence.

# Directed testing

Writing focused, self-checking tests for scenarios the specification names, and
how this repository's simulation gate reads their result. Tags in brackets name
the sources above; a line marked "inference" is this document's own reasoning;
a line marked "gate" names the repository code that backs it.

## When a directed test is the right tool

- OpenTitan starts a block with a smoke test: clock, bring the block out of
  reset, check outputs are not unknown, and drive one major datapath with simple
  checks. That test also stays in the quick sanity set [OTDV].
- Illegal and error stimulus is usually handled with directed tests, because a
  scoreboard that checks error behaviour under unconstrained random traffic is
  costly to write [OTDV].
- A directed test names its scenario in the specification. Anything the
  specification does not name has no test, so the list of scenarios is the
  coverage of the plan (inference).

## How a test is written

- One scenario per check group: set up state, apply stimulus, wait for the
  specified latency, compare against an expected value computed in the test
  from the specification, not copied from the RTL's own output (inference).
- Exercise the boundaries and the interactions the specification states: two
  events in the same cycle, the last and first legal values, a request while
  busy, a reset in the middle of an operation (inference).
- Compare every output the scenario can change. A test that reads only the
  field it just wrote cannot see a neighbouring field break (inference).
- For a block with arbitration or priority, drive more than one requester at a
  time. A test with one requester passes when the priority order is reversed
  (inference).
- Drive inputs away from the clock edge the design samples, and sample outputs
  after it, so the test does not race the design; with Verilator a C++ or
  SystemVerilog harness toggles the clock and calls eval for each edge [ZVer].

## What the simulation gate demands

- The testbench is the file that declares the run's top module. Only it may
  call `$finish`, `$stop` or `$exit`, read plusargs, open files, or reach out of
  the language (`$system`, `$c`, DPI); a design file using any of them is refused
  before anything runs (gate: src/nirmaan/integrations/eda.py:451-452, 476-497).
- The testbench must print one verdict line, `NIRMAAN-SIM <nonce> <n> passed,
  <m> failed`, with the nonce the run passed in as a plusarg, just before
  `$finish`. The run fails when the verdict is missing, repeated, carries
  another nonce, reports a failed check, or reports no passed check; and when
  `$finish` is not reached or any step exits nonzero (gate:
  src/nirmaan/integrations/eda_parsers.py:132-224). A test that checks nothing
  therefore fails the gate.
- The simulators are Icarus Verilog or Verilator with `--binary`, and the build
  runs with `-Wno-fatal`, so a warning does not stop the build
  (gate: src/nirmaan/integrations/eda.py:436-448). Lint is a separate tool.
- The `expect` parameter takes `pass` or `fail` only; `fail` is for a
  reproduction of a known failure and inverts the question (gate:
  src/nirmaan/integrations/eda.py:457-464).
- `--binary` makes Verilator build a runnable simulator binary, an alias for
  `--main --exe --build --timing` [VArg], so a SystemVerilog testbench with
  delays and `$finish` needs no C++ harness; the model's end-of-run behaviour
  is described in the runtime chapter [VSim].

## Common failure modes

- A test that cannot fail: expected values taken from the design, a check that
  compares a value with itself, or a loop that never reaches its compare
  (inference; the card lists "Tests that cannot fail").
- Priority and acknowledge paths exercised with one source pending.
- Only reset and register reads, which pass while the datapath is unused;
  coverage then exposes it (see the code coverage document).
- Printing a pass line unconditionally. The gate counts failed checks the
  testbench itself reports, so a testbench must increment its failure count in
  every compare (gate: eda_parsers.py:189-203).

## How a result is checked

- Run the test against the approved RTL and read the check count, not only
  pass. Then run it against a deliberately broken copy of the RTL (a mutant);
  a test that still passes is missing a check (inference).
- Keep a list of the specification statements each test covers, and confirm
  every statement has one (inference; OpenTitan maps tests to a testplan
  [OTDV]).
- Read coverage over the design files after the run to see what the test did
  not reach.

---
id: verification/constrained_random
skill: constrained_random
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
  - open | Verilator manual: Language reference, unknown states and random functions [VLang] | https://verilator.org/guide/latest/languages.html
  - open | Verilator manual: Simulating (Verilated-Model Runtime) [VSim] | https://verilator.org/guide/latest/simulating.html
  - open | Gisselquist, Building a Verilator test bench, ZipCPU blog, 2017 [ZVer] | https://zipcpu.com/blog/2017/06/21/looking-at-verilator.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K2 session (wave 2 knowledge batch, plan row W2-K2, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the test tool this skill holds is available; this document is knowledge, not evidence.

# Constrained-random verification

Driving a block with random stimulus that stays inside the legal space,
checking every cycle against a model written from the specification, and how
this repository's simulation gate reads the result. Tags in brackets name the
sources above; a line marked "inference" is this document's own reasoning; a
line marked "gate" names the repository code that backs it. The card also lists
`regression.run`, which is not available here, so nothing below depends on it.

## Why and when

- OpenTitan uses constrained random stimulus at block level to reach its
  coverage goals, with a model of the block that checks behaviour independently
  of the stimulus [OTDV].
- Random stimulus is poor at error handling: a scoreboard that judges error
  behaviour under unconstrained traffic is costly, so illegal stimulus is
  usually constrained or directed [OTDV].
- Random does not replace directed tests. A directed test is the quick way to
  show a named scenario works; random finds combinations nobody listed
  (inference).

## How a random testbench is built

- Stimulus has three parts: a generator, the constraints that keep it legal,
  and a knob for each constraint. OpenTitan builds stress tests with knobs that
  control how tight the constraints are, then eases them step by step to reach
  deeper states [OTDV].
- State each constraint as a rule of the interface specification, in the
  testbench's own words: which inputs may change together, which values are
  legal, how long a valid input may be held (inference).
- Bias the generator toward the boundaries and toward events that coincide: a
  uniform generator seldom raises two rare inputs in the same cycle, so give
  those inputs a probability that makes the coincidence common (inference).
- Check against a reference model of the specification that the testbench
  updates on every clock edge and compares after every edge. A check made only
  after the last item of a sequence lets a later item hide an earlier mistake
  (inference). A model copied from the RTL reproduces the RTL's mistakes
  (inference).
- Make a run repeatable. Verilator takes the seed for `$random` and `$urandom`
  either from an argument of the call or from the `+verilator+seed+<value>`
  runtime option; the seed is kept per C thread, not per module [VLang]. The
  simulation gate passes only its own nonce argument to the run (gate:
  src/nirmaan/integrations/eda.py:436-449), so a seed held in the testbench
  source is what makes a gate run repeat (inference). Print the seed in the log
  so a failure can be replayed.
- Verilator's `$urandom` and `$random` calls are described in the language
  chapter [VLang]; a SystemVerilog testbench with delays builds with
  `--binary` and needs no C++ harness [VSim] [ZVer].

## What the simulation gate demands

- The testbench is the file that declares the run's top module; only it may
  call `$finish`, read plusargs, or reach out of the language. A design file
  using any of them is refused before anything runs (gate:
  src/nirmaan/integrations/eda.py:451-497).
- The testbench prints one verdict line with the run's nonce, a count of
  passed checks and a count of failed ones. The run fails when the line is
  missing, repeated, carries another nonce, reports a failed check, or reports
  no passed check (gate: src/nirmaan/integrations/eda_parsers.py:132-224).
- Nothing in the gate measures how many random items ran or whether any rare
  case was reached. A random testbench that runs ten items and passes is a
  passing run (inference). The testbench must fail itself when its run was too
  short or a corner case was never produced, by counting those events and
  comparing the counts at the end (inference; the card lists "Over-constrained
  stimulus" and requires stimulus that "reaches coverage goals").
- Coverage over the design files can show what the run did not reach (see the
  code coverage document); it is a separate tool call, not part of the
  simulation verdict.

## Common failure modes

- Over-constraining: constraints so tight, or a run so short, that the corner
  never occurs, such as a clear that never lands on the same edge as a valid
  input.
- A generator that cannot produce the illegal-but-allowed cases the
  specification describes, which leaves error paths unexercised [OTDV].
- A reference model copied from the RTL, or one that checks only a summary of
  the outputs.
- No seed in the log, so a failing run cannot be replayed (inference).
- One fixed seed run once and counted as random verification. OpenTitan runs
  each constrained random test over many seeds, passing completely random seed
  values to the simulator [OTDV].
- A pass line printed regardless of the compares. The gate counts failures
  the testbench reports, so every compare must add to its failure count
  (gate: eda_parsers.py:132-224).
- Reset and initial values left to luck. Verilator's `--x-initial` setting
  chooses how variables start, and its manual suggests comparing runs that
  start from zeros, ones and random values: if the results match, reset works
  [VLang].

## How a result is checked

- Read the check count in the verdict, not only the word pass.
- Run the testbench against a broken copy of the RTL for each requirement:
  every one should fail the gate. A mutant that passes names a missing check or
  a corner the generator does not reach (inference).
- Count the corner events the run produced and compare with the plan. OpenTitan
  closes the loop with coverage, then eases constraints where holes remain
  [OTDV].
- Change the seed and run again; a testbench that passes at one seed only is a
  testbench that was tuned to that seed (inference).

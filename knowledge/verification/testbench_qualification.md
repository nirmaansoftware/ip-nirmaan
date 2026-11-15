---
id: verification/testbench_qualification
skill: testbench_qualification
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | YosysHQ, MCY (Mutation Cover with Yosys) documentation: overview [McyIndex] | https://yosyshq.readthedocs.io/projects/mcy/en/latest/
  - open | YosysHQ, MCY documentation: Methodology [McyMeth] | https://yosyshq.readthedocs.io/projects/mcy/en/latest/methodology.html
  - open | YosysHQ, MCY documentation: Mutation export options and the Yosys mutate command [McyMutate] | https://yosyshq.readthedocs.io/projects/mcy/en/latest/mutate.html
  - open | YosysHQ, MCY documentation: Writing a test script [McyTest] | https://yosyshq.readthedocs.io/projects/mcy/en/latest/testsetup.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K3 session (wave 2 knowledge batch, plan row W2-K3, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# Testbench qualification

Finding out whether a passing testbench would notice a broken design, by
planting single changes in a clean design and requiring the testbench to fail
each one. Tags in brackets name the sources above; a line marked "inference" is
this document's own reasoning; a line marked "gate" names the repository code
that backs it.

## Why a passing testbench is not enough

- A failing testbench shows a problem; a passing one shows nothing unless you
  know what it tests for. MCY states this as its starting point, and tests a
  self-checking testbench by running it against many mutated copies of the
  design [McyIndex].
- A mutation is a small change to one signal or bit. Not every mutation breaks
  the design: a change that only shows on cycles where a valid input is low
  leaves the design working as specified, and a testbench is right to pass it
  [McyMeth].
- Measuring this needs a testbench that passes on the original design; a
  failing baseline cannot show a mutation being caught [McyMeth].

## How a mutant set is made

- MCY picks mutations with heuristics that spread them over source locations,
  wires, bits and cells, so no part of the design is left out by chance
  [McyMutate]. By hand the same aim holds: cover each requirement, not the
  places the author expected bugs (inference).
- A hand-written mutant is a single change to the clean design: a comparison
  reversed, a boundary off by one, a reset term dropped, two priorities swapped,
  a saturation removed, a constant wrong, an output delayed one cycle, a flag
  not held (inference).
- One change per mutant. A mutant with two changes can be caught by either and
  says which one the testbench saw only if the other is irrelevant
  (inference).
- Write the mutant set from the specification and the clean design before
  reading the testbench's checks, then freeze it. A set written after seeing
  the checks tends to contain only what the checks already catch (the skill's
  own validation rule; inference for the reason).
- MCY's own test scripts need one mutated design per run, or several selectable
  with a control input, `mutsel`, when the testbench is expensive to build
  [McyMutate] [McyTest]. The same choice applies by hand: separate files are
  simpler, a selectable parameter is quicker to run (inference).

## Reading the outcome

- Killed: the testbench fails on the mutant. Check that it failed for the reason
  the mutation implies, not for a compile error or timeout; a mutant that was
  never run counts as unknown, not killed (inference; gate: the scorer below
  does the same).
- Survived: the testbench passes the mutant. Either the mutation does not
  change behaviour, or the testbench has a gap. MCY decides which with a formal
  equivalence check between the original and the mutant, which it treats as
  the reference standard against which the testbench is judged [McyMeth].
- MCY's example logic tags each mutation covered, uncovered, no change, or an
  equivalence gap. The last, where the equivalence check says there is no
  change but the testbench fails, means one of the two is wrong and has to be
  investigated first [McyMeth].
- Without an equivalence tool, explain each survivor in writing: why the change
  is not observable at the outputs, or which check is missing. "Equivalent" with
  no reason is not an explanation (inference).
- The equivalence check must not be written by blurring it with the testbench:
  MCY warns that when one author writes both, the distinction can be lost
  [McyMeth].

## What the repository does

- No tool in the tool catalog generates or runs mutations: the entries in
  `src/nirmaan/company/tools.py` name none, so mutants here are written by hand
  (gate: src/nirmaan/company/tools.py, searched for mutation tools, none
  found).
- The evaluation harness has a must-fail scorer that applies mutants of the
  design to a seat's testbench or assertions: the clean inputs must pass, any
  named cover check must be reached on the clean inputs, and each mutant must
  make the tool fail on a run that executed. A refusal, which ran nothing, is
  never counted as a mutant caught (gate: src/nirmaan/evals/scorers.py:135-224).
  That is how the harness judges a seat's work; it is not a tool the seat
  calls (inference).
- The cases that use it name their mutants in advance (files under
  `tests/fixtures/dv/<block>/mutants/`), so the mutant set predates the seat's checks (gate:
  evals/dv/scoreboard_mac.json:66-74).

## Common failure modes

- A mutant set written after seeing the checks.
- Survivors dismissed with no reason.
- A mutant that fails to compile or never reaches the changed code, counted as
  killed.
- Measuring a testbench that already fails on the clean design [McyMeth].
- A mutation count presented as a quality figure with no list of survivors
  (inference).

## How a result is checked

- The clean design passes the testbench, and the log shows it (inference).
- The mutant list is dated before the checks, names one change each, and covers
  the requirement list (inference).
- Every mutant is listed as killed with the failing check named, or as a
  survivor with its reason; none is unaccounted for (inference).
- A survivor claimed as equivalent has a reason a second reader can follow,
  or an equivalence result [McyMeth].

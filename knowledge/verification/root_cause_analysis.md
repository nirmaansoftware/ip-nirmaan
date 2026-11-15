---
id: verification/root_cause_analysis
skill: root_cause_analysis
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | Andreas Zeller, The Debugging Book: Introduction to Debugging (CC BY-NC-SA 4.0) [ZIntro] | https://www.debuggingbook.org/html/Intro_Debugging.html
  - open | Andreas Zeller, The Debugging Book: Reducing Failure-Inducing Inputs (CC BY-NC-SA 4.0) [ZDelta] | https://www.debuggingbook.org/html/DeltaDebugger.html
  - open | Glerum et al., Debugging in the (Very) Large: Ten Years of Implementation and Experience, SOSP 2009 (conference copy) [WER] | https://www.sigops.org/s/conferences/sosp/2009/papers/glerum-sosp09.pdf
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K5 session (wave 2 knowledge batch, plan row W2-K5, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the simulator and VeriTriage tools this skill holds are available; this document is knowledge, not evidence.

# Root-cause analysis

From a failing test to the defect that causes it, and how the reproduction
gate reads the result. Tags in brackets name the sources above; "inference"
marks this document's own reasoning; "gate" or "test" names the repository
code that backs a line; "run" names a tool run made while writing (listed in
the pull request).

## From failure back to defect

- In Zeller's terms a defect is an error in the code, a fault is an error in
  the program state, and a failure is an externally visible error in the
  behaviour; executing the defect creates a fault, which propagates until it
  becomes visible as a failure [ZIntro].
- Not every defect causes a failure, but every failure can be traced back to
  the defect that causes it [ZIntro].
- To find the defect, trace back from the failure, fault by fault, until a
  step takes in a correct state and puts out a faulty one [ZIntro].
- That search is hard: states are large, intermediate states often have no
  specification to judge them by, and runs have many steps [ZIntro].
- So focus the search, starting with the most likely causes; assertions on
  intermediate state help, as they shorten the cause-effect chain [ZIntro].
- A failed assertion makes the failure appear earlier, closer to the
  initial fault [ZIntro].
- In a simulation the failing check marks where a fault became visible, not
  where it began; the register written wrongly may have been written many
  cycles before it was read (inference).

## Competing hypotheses

- Zeller applies the scientific method: form a hypothesis that explains
  what was observed; derive a prediction that could support or refute it,
  ideally one that tells it apart from likely alternatives; test it in an
  experiment; repeat until hypothesis and observations agree [ZIntro].
- A rejected hypothesis is replaced by an alternative; a supported one is
  refined [ZIntro].
- Keep a log of every hypothesis, experiment and observation, and check
  each new hypothesis against all earlier observations [ZIntro].
- The same diagnosis can be reached from more than one starting
  hypothesis [ZIntro].
- Going straight to an interactive debugger narrows the view to the one
  execution being stepped through [ZIntro].
- A fix made before the problem is understood may be incomplete [ZIntro].
- WER's team tested a root-cause hypothesis by writing a check that
  evaluates it on one memory dump and running that check over thousands of
  dumps, to see whether any violated it [WER].
- When WER's bucketing blamed reputable code, the team searched the reports
  for other explanations; one strategy was to look for a seemingly innocent
  third party correlated with the error, often a driver or plug-in found more
  often in the error reports than in the general population [WER].
- For an RTL failure, the root-cause stage names one of four outcomes: an
  RTL bug, a testbench bug, infrastructure, or a specification question
  (gate: src/nirmaan/company/workflows.py:481-485). Keep all four open until
  an experiment rules each out, and write down the experiment that did it
  (inference).
- Experiments that separate them (inference): derive the expected value
  again from the specification, to test the check; rebuild from clean with
  no other change, to test the infrastructure; read the clause the check
  relies on, to see whether it fixes the behaviour at all.

## A diagnosis before a fix

- Fix only when the diagnosis shows causality (how the defect produced this
  failure, so the fix makes it disappear) and incorrectness (why the code is
  wrong, so the fix also covers related failures) [ZIntro].
- With causality alone the change may only hide the symptom; with
  incorrectness alone the change may not touch this failure [ZIntro].
- After the fix the failure should be gone and no new one should appear; if
  it persists, that is a surprise, and the failing case goes back into the
  observations [ZIntro].
- Afterwards, look for the same mistake elsewhere, add a test that would have
  caught the bug, and consider an assertion that guards against it [ZIntro].

## The minimal repro

- Usually only a small part of a failing input matters; reduce it to the
  smallest form that still reproduces the failure [ZDelta].
- Kernighan and Pike's advice, as Zeller gives it: check each circumstance of
  the problem for relevance and remove it if it is not; for inputs, throw
  away half and see whether the output is still wrong, and if not, go back
  and discard the other half instead [ZDelta].
- Delta debugging automates this; its result is 1-minimal, so removing any
  one remaining element makes the failure go away [ZDelta].
- A reduced case is quicker to understand and run, easier to communicate, and
  shows duplicates: bugs that reduce to the same cause are different symptoms
  of one underlying cause [ZDelta].
- Reduction needs a test that is deterministic and quick; one that fails
  only sometimes gives random results [ZDelta].
- In Zeller's example, code reduced until the function returned nothing
  still failed the test's assertion; once a check of normal behaviour was
  added, such a reduction raised a different error, which counts as
  unresolved, and the reduction kept the real function [ZDelta].
- His lesson: specifying the failure condition precisely helps avoid false
  diagnoses [ZDelta].
- For a repro testbench, the same holds in cycles and transactions: the
  fewest that still fail, with checks taken from the specification, not
  values copied from the failing RTL's output (inference).

## What the reproduction gate demands

- When a regression investigation asks for a reproduction, the root-cause and
  triage stages also write testbench files, and a before-review gate runs
  simulator.run with expect=fail over the approved RTL under investigation
  and one of those testbenches at a time, its top taken from that testbench
  (gate: src/nirmaan/company/workflows.py:449-460, 472-476, 481-485; test:
  tests/test_repro_gates.py::test_a_reproduction_hands_over_the_rtl_and_gates_triage_and_root_cause).
- expect is restricted to pass (the default) or fail; any other value is
  refused before anything runs (gate:
  src/nirmaan/integrations/eda.py:457-462; run G).
- With expect=fail the run passes only when the build succeeded, the
  simulation reached $finish, and the testbench printed exactly one verdict
  line `NIRMAAN-SIM <nonce> <n> passed, <m> failed` with this run's nonce and
  at least one failed check (gate:
  src/nirmaan/integrations/eda_parsers.py:128-129, 226-256). A testbench
  whose checks all pass, one that prints no verdict, and one that does not
  build all fail it (runs B, F, E).
- Only the file that declares the top module may end the run, read plusargs
  or open files: a design file that used $finish, $stop, $fopen or
  $value$plusargs was refused before anything was simulated (gate:
  src/nirmaan/integrations/eda.py:449-454, 476-497; runs H, W, U, V).
- A repro that passes on the RTL under investigation stops the work before
  review (test: tests/test_repro_gates.py::test_a_root_cause_whose_repro_passes_on_the_rtl_does_not_reach_review).
- The gate counts failed checks; it does not know which behaviour a check
  tests. A testbench with a wrong expected value reproduced "a failure" on
  the clean counter RTL (run O). In an evaluation the must-fail scorer also
  runs the repro on the clean inputs, which must pass, and on each mutant,
  which must fail (gate: src/nirmaan/evals/scorers.py:136-147).
- So write the repro as a self-checking test of the specified behaviour that
  happens to fail now: the same testbench failed with expect=pass on the
  buggy RTL and passed on the clean one (runs C, D).
- veritriage.investigate reports a classification with a confidence and a
  top hypothesis (gate: src/nirmaan/integrations/veritriage.py:58-68). On a
  plain Icarus failure log from simulator.run it reported unknown_failure at
  30% confidence, top hypothesis "Likely RTL bug" (run I). Treat the top
  hypothesis as one candidate to test (inference).

## Common failure modes

- Single-hypothesis tunnel vision (card: src/nirmaan/company/skills.py:509).
- Changing code at random until the test passes, or special-casing the
  failing input so the symptom goes away [ZIntro].
- A repro that fails for another reason: a wrong expectation, a missing
  reset, a check of an unspecified value (inference).
- A diagnosis naming the cycle where the check failed, not the earlier write
  that caused it, or a repro tied to one implementation's internal names
  (inference).

## How a result is checked

- The conclusion names its evidence and the alternatives it rejects (card:
  src/nirmaan/company/skills.py:510), with the experiment that rejected each
  (inference).
- The repro fails on the RTL under investigation and passes on the fixed RTL
  (inference); the reproduction gate runs it over the RTL under
  investigation, not over a fix (gate: src/nirmaan/company/workflows.py:450-454).
- The diagnosis states both causality and incorrectness [ZIntro].

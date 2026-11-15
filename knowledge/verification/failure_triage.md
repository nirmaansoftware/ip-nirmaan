---
id: verification/failure_triage
skill: failure_triage
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | Glerum et al., Debugging in the (Very) Large: Ten Years of Implementation and Experience, SOSP 2009 (conference copy) [WER] | https://www.sigops.org/s/conferences/sosp/2009/papers/glerum-sosp09.pdf
  - open | Andreas Zeller, The Debugging Book: Reducing Failure-Inducing Inputs (CC BY-NC-SA 4.0) [ZDelta] | https://www.debuggingbook.org/html/DeltaDebugger.html
  - open | Zhu et al., Tools and Benchmarks for Automated Log Parsing, ICSE-SEIP 2019 (arXiv 1811.03509) [LogParse] | https://arxiv.org/abs/1811.03509
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K5 session (wave 2 knowledge batch, plan row W2-K5, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the VeriTriage tools and the simulator this skill holds are available; this document is knowledge, not evidence.

# Failure triage

Sorting a set of failures into groups that each have one cause, ranking the
groups, and how the triage stage's gates read the result. Tags in brackets
name the sources above; "inference" marks this document's own reasoning;
"gate" or "test" names the repository code that backs a line; "run" names a
tool run made while writing (listed in the pull request).

## Buckets

- WER groups error reports likely caused by the same bug into a bucket; the
  ideal is one bug per bucket and one bucket per bug [WER].
- Collected with no organisation, WER's data would overwhelm programmers
  [WER].
- Good bucketing spares programmers redundant reports, ranks their work by
  how many reports a bucket holds, and can link users to a fix once a
  bucket's cause is corrected [WER].
- Programmers start with the largest bucket. A refinement is to add up the
  buckets of each function and work through the function with the most
  reports first, since errors at different places in one function often
  share a root cause [WER].
- In WER's experience a small number of bugs account for most reports [WER].
- In a regression the unit is a failing test run, not a report, and the
  counts are small; rank by how many runs a bucket holds and how severe the
  behaviour is, not by count alone (inference).

## Two ways to get buckets wrong

- An expanding heuristic splits reports into more buckets, so that no two bugs
  share one; a condensing heuristic merges buckets, so that no bug is spread
  over two [WER].
- The two should complement, not conflict: an expanding heuristic should
  not create a new bucket for the same bug, and a condensing one should not
  put two bugs in one bucket [WER].
- The two known weaknesses are the same pair: one bug mapped into too many
  buckets, and more than one bug mapped into one bucket [WER].
- WER assumes buckets holding exactly one report were wrongly bucketed,
  because ten years with large samples showed real bugs are always hit more
  than once [WER]. A nightly regression has too few runs for that rule;
  rerun a lone failure before giving it a bucket of its own (inference).
- At WER's scale a merge error corrects itself: once the first bug is fixed,
  reports from the second come back and dominate [WER]. In a regression the
  second bug stays hidden until the fix lands and the run is repeated, so
  a merged bucket costs a round trip (inference).
- WER's bucketing is progressive: as more data arrives, such as symbols that
  turn an offset into a function name, a report moves to a new bucket [WER].
  Re-sort the failures when a root cause is found (inference).

## Signatures

- WER's main client-side labels come from the faulting program, its module,
  and the offset of the program counter within that module [WER].
- On the server, the stack walk that picks the frame most likely to be the
  cause gives the lowest priority to functions known never to be a root
  cause, such as memcpy [WER].
- Office gives each assert in its source a permanent tag, and an assert
  failure is bucketed by that tag, so one assert stays one bucket as it moves
  in the source [WER].
- A log message's content is a constant part, its event template, plus
  variable parameters; parsing turns each message into its template and
  parameters [LogParse].
- Duplicate issue identification, in the Microsoft studies the paper cites,
  needs structured event data of that kind [LogParse].
- For simulation failures (inference): build the signature from the failing
  check's stable label and the first failing signal or field, with times,
  seeds, data values and addresses taken out, as a log parser takes out its
  parameters. Give every check a label that does not change when lines move,
  as the assert tags do.
- Reduction also finds duplicates: bugs that reduce to the same cause are
  different symptoms of one underlying cause [ZDelta]. Two failures that
  reduce to the same short stimulus are one bucket (inference).

## Flaky failures

- Delta debugging needs a deterministic test; one that fails only sometimes
  gives random results [ZDelta].
- Rerun a failure with the same seed and the same build before bucketing it.
  A failure that does not repeat is a bucket of its own about the test or the
  environment, not evidence for an RTL bucket (inference).

## What the triage gates demand

- The triage stage needs a VeriTriage session over the failing artifacts,
  from veritriage.investigate (gate: src/nirmaan/company/workflows.py:472-476).
- veritriage.investigate takes files: no paths, a missing path, or a directory
  is refused (gate: src/nirmaan/integrations/veritriage.py:49-57; runs K2, K,
  J).
- One call makes one session over all the paths it is given, with one
  classification (gate: src/nirmaan/integrations/veritriage.py:58-68). Given
  the UVM scoreboard fixture and a plain Icarus failure log together, it
  returned one class, testbench_failure, though the Icarus log alone gave
  unknown_failure (runs T, I). Run it on each failing log as well as on the
  set (inference).
- Its classification comes with a confidence: on the repository's UVM
  scoreboard fixture it reported testbench_failure at 80% with a matched
  pattern, and on a plain Icarus failure log unknown_failure at 30% with
  none (runs I, P). A class is a lead to test, not a bucket by itself
  (inference).
- When the investigation asks for a reproduction, the triage stage also
  writes testbench files, and the gate runs simulator.run with expect=fail
  over the approved RTL under investigation and each of those testbenches on
  its own, its top taken from that file (gate:
  src/nirmaan/company/workflows.py:449-460, 472-476).
- Every repro must reproduce on its own: one that does not stops the work,
  even beside one that does (test:
  tests/test_repro_gates.py::test_a_triage_repro_that_does_not_reproduce_stops_the_work_even_beside_one_that_does).
- With expect=fail a run passes only when the build succeeded, $finish was
  reached and the testbench's one verdict line, with this run's nonce, reports
  at least one failed check (gate:
  src/nirmaan/integrations/eda_parsers.py:226-256; runs A, B, E, F).
- In an evaluation the must-fail-each scorer judges a triage seat's repros:
  each must pass on the clean inputs, and every seeded bug must fail a different
  repro, so one repro that fails every bug cannot stand for two buckets (gate:
  src/nirmaan/evals/scorers.py:240-268, 337-339; test:
  tests/test_repro_gates.py::test_one_repro_that_fails_every_bug_cannot_stand_for_two_buckets).
- So each repro should check the one behaviour its bucket's cause breaks, and
  pass where that behaviour is right (inference).

## Common failure modes

- Classifying from the first error line only (card:
  src/nirmaan/company/skills.py:494).
- Bucketing by the error text with times and values still in it, so every
  run is its own bucket (inference).
- Merging two failures because they end in the same timeout or the same
  final check, when the first faults differ (inference).
- One repro written to fail every failure in the set (inference).
- A flaky failure counted as an RTL bucket (inference).

## How a result is checked

- Every failing run is in exactly one bucket, and each bucket names its
  signature and the evidence that its runs share one cause (inference).
- Each bucket has a repro that fails on the RTL under investigation, and no
  repro stands for two buckets (inference).
- The triage cites a VeriTriage session and its evidence nodes (card:
  src/nirmaan/company/skills.py:495).

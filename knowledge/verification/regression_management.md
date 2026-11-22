---
id: verification/regression_management
skill: regression_management
as_of: 2026-11-22
review_by: 2027-05-22
sources:
  - open | cocotb regression manager source listing, development build 2.2.0.dev49 (BSD-3-Clause, cocotb contributors) [COCO] | https://docs.cocotb.org/en/latest/_modules/cocotb/regression.html
  - open | lowRISC, Design Verification Methodology within OpenTitan (doc/ug/dv_methodology/index.md; the repository is Apache-2.0; read through a mirror of one commit, since the canonical book URL returned not found) [OTDV] | https://opensecura.googlesource.com/3p/lowrisc/opentitan/+/e7bc9e2fbbda697cb190ca166e331799ce1c1d01/doc/ug/dv_methodology/index.md
  - open | Poulos and Veneris (University of Toronto), Clustering-based Failure Triage for RTL Regression Debugging, ITC 2014 (author copy, IEEE copyright, no open licence stated) [POU] | https://www.eecg.utoronto.ca/~veneris/itc14.pdf
  - open | Phogat and Hamilton (Arm), mL: Shrinking the Verification volume using Machine Learning, DVCon proceedings (no licence stated) [PHO] | https://dvcon-proceedings.org/wp-content/uploads/1090-1.pdf
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source; the two permissively licensed sources are paraphrased, not quoted
export_screen: clear
writer: RX-K2 session (wave 2 close, 2026-11-22)
checker: pending, a different session reads the sources and writes the check record
---
Practising: the VeriTriage investigation tool this skill holds is available; this document is knowledge, not evidence.

# Regression management

Running sets of tests on a schedule, keeping each run reproducible, and
turning the failures into owned work. Tags in brackets name the sources above;
a line marked "inference" is this document's own reasoning; a line marked
"gate" names repository code that backs it. This document is only partly
sourced: no open source was found for flaky-test handling or for how a triage
queue is run, and the sections on them say so.

## What the repository gives this skill

- The card lists two tools. regression.run is CONTRACT_ONLY, so nothing here
  can launch or monitor a regression (gate: src/nirmaan/company/tools.py:5-8,
  135). veritriage.investigate is AVAILABLE and takes log file paths (gate:
  src/nirmaan/company/tools.py:112-115).
- Its binding refuses no paths, a missing path and a directory, and makes one
  investigation over all the files it is given (gate:
  src/nirmaan/integrations/veritriage.py:50-59; test:
  tests/test_nirmaan_gate_integrity.py::test_veritriage_refuses_a_directory_cleanly).
- The card asks that no flaky test be ignored and that every failure be
  triaged or tracked (gate: src/nirmaan/company/skills.py:495-499). A workflow
  stage asks for "regression results, failures triaged" and names
  regression.run as its tool (gate: src/nirmaan/company/workflows.py:256).
  Since that tool cannot run, such evidence has to be a pass rate and logs
  that came from outside, with the source stated (inference).

## Tiers of regression [OTDV]

- Sanity: a small set of simple tests per design that exercise a major
  datapath, with at least one per compile-time configuration. It gives people
  who touch shared code a fast way to check that nothing broke across designs.
  The project would like it in the check on every pull request, but cannot
  because its simulators are proprietary, so it runs daily from a scheduled
  job on the main branch.
- Nightly: everything, run when people are away. Its goals are to run each
  constrained-random test with many seeds (100, which the page calls
  arbitrary), pass completely random seeds to the simulator, spread jobs over a
  compute farm, collect and merge coverage, and publish results on a dashboard
  that maps each test to its planned test. It should finish overnight so that
  results can be analysed and triaged the next morning; a weekly run is the
  fallback for longer tests.
- A consistent 100 percent pass rate in the nightly run is described as key to
  calling verification complete [OTDV]. The page says the same of coverage:
  gaps are understood and either waived or closed, with waivers signed off by
  the designer and carrying a stated reason [OTDV].
- The page adds that X propagation is mandatory in the regressions used for
  coverage closure [OTDV].

## Seeds and reproduction [COCO]

This is one tool's policy, read from a development listing, so check the
version you use before relying on a detail.

- Each test's seed is the regression's base seed plus a SHA-1 of the test's
  full name. The generators are re-seeded at the start of the test and their
  previous state is restored when it ends.
- The base seed goes into the results file for passed, expected-fail, failed
  and failed-to-start tests. A failed test also writes a line naming the base
  seed in its error stream.
- A regression can be limited by name patterns that include tests, can shuffle
  the order of tests when an environment switch is set, and can stop after a
  set number of failures (default: no limit). The results file name comes
  from an environment variable.
- It follows that a failure is reproduced by the same base seed, the same
  test name and the same build; renaming a test changes its seed, and adding a
  test does not change the others' (inference from the seed rule).
- The names of the environment variables differ between versions, so read them
  from the version in use (inference: the listing is of a development build).

## Records a run should keep

For each result: test name, seed, build, outcome, and the log path. The cocotb
results file carries name, outcome and seed [COCO]; OpenTitan's dashboard
carries the test mapped to its plan item [OTDV]. A list that includes the
simulator, the commit and the flags is this document's suggestion (inference);
neither source lists them.

## Triage after a run

- OpenTitan files bugs in its public issue tracker, whether in the design, the
  DV code or the tools [OTDV]. How failures are ranked or assigned there is not
  described.
- [POU] defines triage as a coarse first look, binning of failures that share
  a cause, and distribution of bins to owners, and reports that practice was
  manual with failures reassigned until the owner was found. Its clustering
  method is in knowledge/verification/regression_intelligence.md and needs a
  SAT-based debugger.
- [PHO] shows the cost side: most random tests pass, so mature designs spend
  most of the compute on passing tests, and a model can pick the tests more
  likely to fail. It keeps ordinary random regressions running beside the model
  because designs change and the model goes stale.
- With the tool the card holds: run veritriage.investigate on each failing
  log, then on the set, and keep the session id with the record
  (inference; see the failure triage document for the gates).

## Not sourced here

- Flaky tests. No open source was found on detecting, quarantining or
  retiring them. The card's own failure is ignoring them. Inference only: a
  failure that does not repeat under the same base seed, test name and build
  points at the environment or at nondeterminism, and should be recorded as
  its own item rather than dropped or counted against the RTL.
- The triage queue: ownership, ageing, priorities and what closes an entry.
- Pass-rate targets other than the 100 percent nightly goal [OTDV].
- Selecting or ordering tests by change (survey papers exist, but no copy that
  may be read was found).

## Failure modes

- A regression run with no recorded seed, so a failure cannot be replayed.
- A red nightly accepted as noise (the card's failure).
- Reporting a pass rate with no statement of which tool produced it, since
  regression.run cannot run here (inference).
- A sanity suite that skips a compile-time configuration [OTDV].

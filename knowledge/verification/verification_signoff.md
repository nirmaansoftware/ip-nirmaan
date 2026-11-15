---
id: verification/verification_signoff
skill: verification_signoff
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | lowRISC, OpenTitan Signoff Checklist (Apache 2.0) [OTChk] | https://opentitan.org/book/doc/project_governance/checklist/index.html
  - open | lowRISC, OpenTitan Hardware Development Stages (Apache 2.0) [OTStage] | https://opentitan.org/book/doc/project_governance/development_stages.html
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K7 session (wave 2 knowledge batch, plan row W2-K7, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# Verification signoff

Deciding that verification is complete: which criteria, what evidence each
needs, and what to look at besides the percentages. The thresholds below are
one open project's policy (OpenTitan), not a general rule. Tags in brackets
name the sources above; "inference" marks this document's own reasoning. This
skill's card holds no tool (src/nirmaan/company/skills.py:546-551), and
nothing here has been run.

## Signoff is a list of items with evidence

- OpenTitan defines verification as complete when the checklist items for all
  stages are marked done [OTDV]. Each stage has a named list of items; the
  checklist says the items in each stage are expected to be completed
  [OTChk].
- The stages run V0 (initial work), V1 (under test), V2 (testing complete),
  V2S (security countermeasures verified) and V3 (verification complete)
  [OTStage]. The checklist and stage definitions apply to simulation and to
  formal approaches, with item prefixes for each [OTChk].
- A signoff therefore cites one piece of evidence per item: a document, a
  test result, a coverage number or a review (inference; the card's own check
  is "cites evidence for every criterion").

## Criteria at each stage (simulation)

- Under test (V1): the DV document drafted, the testplan complete and
  reviewed, a testbench with the DUT and the interface assertion monitors, a
  smoke test and the register test suite passing, and a smoke regression and
  a nightly regression set up [OTChk] [OTStage].
- Testing complete (V2): every test in the testplan written and passing; the
  functional coverage plan fully implemented; all high priority bugs closed and
  low priority ones root-caused; the nightly regression 90 percent passing;
  code coverage and functional coverage at 90 percent [OTChk].
- Verification complete (V3): the nightly regression 100 percent passing with
  at least a week of soak time; code coverage (line, toggle, FSM state and
  transition, branch, assertion) and functional coverage at 100 percent; no
  tool warnings; no TODOs left in the testbench; lint clean with waivers
  reviewed; X-propagation enabled with nothing the simulator reports as
  unsuitable; no bugs pending [OTChk].
- The stage page states 100 percent code and functional coverage "with
  waivers" for V3 [OTStage].
- For formal approaches V3 asks for every assertion proven with no
  undetermined or unreachable property, and branch, statement, functional
  code and cone of influence coverage at 100 percent [OTChk].
- Pre-verified sub-modules must already have reached the same stage, or meet
  its coverage level if they are not tracked [OTChk].
- The two OpenTitan pages disagree on one number: the methodology page says
  80 percent for V2 in its exclusions advice, while the checklist says 90
  percent [OTDV] [OTChk]. This document uses the checklist figure.

## Look at the holes, not just the percentages

- The methodology page argues that neither measure is enough. Two input
  combinations reach full code coverage of an AND gate, yet cannot tell it
  from an OR gate; functional coverage with a cross between inputs and output
  can. In the other direction, full functional coverage of a small cover
  set can leave part of a larger design never exercised, which code coverage
  would show [OTDV].
- Every gap in measured coverage must be understood and then waived or closed
  by more testing; the end goal is 100 percent of applicable metrics [OTDV].
  A signoff that quotes a percentage without the list of open holes is the
  card's named failure mode (the card; inference that it is the same point).

## Waivers

- Designers sign off on exclusions in a pull request review, every exclusion
  carries an annotation, and a category prefix is used [OTDV].
- The categories are unreachable code, simulation-only constructs, unsupported
  features, items covered in another bench, and low-risk items too hard to
  hit. Some require a written explanation; the last two always do [OTDV].
- The low-risk category is for features described in the specification where
  SW, architecture, design and DV agreed upfront not to verify them because of
  resource limits [OTDV].
- Adding exclusions to reach the V2 coverage level is called wrong, since the
  design is not yet stable then; after any RTL change the exclusion file is
  redone and re-reviewed; exclusion files and the coverage configuration are
  checked at signoff; the tool's checksum stays with the exclusions so a stale
  one is caught [OTDV].
- Exclusions are not reused from block level to top level, because each is
  closed independently [OTDV].

## Reviews

- The testplan and DV document are reviewed face to face with designers, DV
  peers, leads, software and architecture roles [OTDV] [OTChk].
- Stage transitions are reviewed in the pull request that updates the
  checklist and project status; a final signoff review confirms all items done
  "without any major exceptions or open issues" [OTDV].
- After signoff a design is frozen; a bug found later returns it to
  development [OTStage].

## What this repository measures

- The card holds no tool (src/nirmaan/company/skills.py:546-551).
- `coverage.read` is AVAILABLE and `regression.run` is contract only
  (src/nirmaan/company/tools.py:135-137). A signoff here can quote code coverage
  from the first, but a regression pass rate has no tool behind it (inference
  from the tool statuses).

## Common failure modes

- Quoting percentages with no list of open holes (the card; [OTDV]).
- Waivers with no annotation, no reviewer, or written before the design was
  stable [OTDV].
- Signing off on one coverage kind only [OTDV].
- A regression with fewer than all tests passing counted as done [OTChk].
- Items marked done with nothing cited (inference).

## How a result is checked

- Every criterion in the signoff names its evidence and its source of truth:
  the test or result, the coverage report and exclusion file with its
  checksum, the review record (the card's own check).
- Open holes and waivers are listed with their category and reviewer
  (inference from [OTDV]).
- The thresholds used are stated with the policy they come from (inference).

## Sources

- [OTChk] The stage items and numeric thresholds.
- [OTStage] The stage definitions and the signed-off life stage.
- [OTDV] The coverage argument, waiver practice and review flow.

---
id: verification/formal_coverage
skill: formal_coverage
as_of: 2026-11-22
review_by: 2027-05-22
sources:
  - open | Ranjan, Weber and Hanna (Jasper Design Automation), On Verification Coverage Metrics in Formal Verification and Speeding Verification Closure with UCIS Coverage Interoperability Standard, DVCon proceedings (vendor authors; no licence stated) [RAN] | https://dvcon-proceedings.org/wp-content/uploads/on-verification-coverage-metrics-in-formal-verification-and-speeding-verification-closure-with-ucis-coverage-interoperability-standard.pdf
  - open | US patent 8,826,201 B1, Formal verification coverage metrics for circuit design properties (Jasper Design Automation, granted 2014; public patent text, used for definitions only) [PAT] | https://patents.google.com/patent/US8826201
  - open | Devarajegowda, Vliegen, Petrovity and Fotouhi (Infineon, Cadence), A Mutually-Exclusive Deployment of Formal and Simulation Techniques Using Proof-Core Analysis, DVCon Europe 2017 (copyright Infineon on the page; no open licence stated) [PCP] | https://dvcon-proceedings.org/wp-content/uploads/a-mutually-exclusive-deployment-of-formal-and-simulation-techniques-using-proof-core-analysis-paper.pdf
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source; the patent is used only for its definitions and no claim language is reproduced
export_screen: clear
writer: RX-K2 session (wave 2 close, 2026-11-22)
checker: pending, a different session reads the sources and writes the check record
---
Knowledge only: the card lists no tool, so no tool run backs this.

# Formal coverage

Judging how much a set of formal results has actually checked: what the
properties reach, what the constraints leave out, and how far a proof got.
Tags in brackets name the sources above; a line marked "inference" is this
document's own reasoning; a line marked "gate" names repository code that
backs it. All three sources come from one vendor lineage (Jasper, later
Cadence; the third paper is by Infineon with Cadence co-authors), so their
definitions are the authors' and not independent.

## What the repository gives this skill

- The card lists no tool, only the pack formal; its procedure is to measure
  proof core and reachability, and it must explain every unreachable cover
  (gate: src/nirmaan/company/skills.py:539-542).
- A neighbouring check exists for a narrower question. formal.cover runs
  every cover in a proof setup, plus a cover derived for each assertion
  antecedent, and asks that each be reached under the assumptions (gate:
  src/nirmaan/company/tools.py:148-153). That tells whether an assertion's
  situation arises; it does not compute a proof core or the fraction of a
  design a property set reaches (inference from the tool's description). Its
  use is in knowledge/verification/assertion_coverage.md.
- This skill therefore reasons over proof reports a human or another tool
  supplies, and states what each metric does and does not show (inference).

## Why formal results need coverage

[RAN] says a formal result is only as complete as three things: the property
set, the constraints on legal stimuli, and whether the analysis finished or
stopped on time or memory. Its three coverage kinds answer these in turn. A
passing proof says nothing about any of them by itself (inference).

## Definitions the sources share

- A coverage model is a finite set of cover items. An item is an event in the
  design, implicit (a statement, branch or expression executes) or explicit
  (written by the user). Coverage is the share of items found reachable [RAN].
- The cone of influence (COI) of a property is the part of the design that can
  structurally affect the signals the property mentions. Items can be counted
  only inside the COI of the properties of interest [RAN] [PAT].
- The proof core is the part of the COI that is enough to prove the property;
  logic outside it does not affect the proof. It is found with SAT-based
  checking and unsatisfiable-core extraction [RAN] [PAT]. [PAT] also describes
  a minimal sufficient core, and gives a small shift-register example in which
  a register inside the COI is outside the proof core.
- The authors of [PAT] argue that counting the whole COI overstates coverage,
  because some of it is not needed for the proof [PAT]. [RAN] calls proof-core
  coverage the strongest of the metrics it lists, and notes two costs: the
  property must be fully proven, and the core can be expensive to compute
  [RAN].

## The three kinds [RAN]

- Stimuli coverage. Constraints rule out illegal inputs, so over-constraining
  can hide legal behaviour and give false confidence. The method starts from
  a baseline environment (clock, reset, tie-offs) with no behavioural
  constraints and adds constraints step by step, comparing which items stay
  reachable. Items that become unreachable are dead code, a parameter that
  disables the code, or the effect of the constraints. Its case study found a
  subtle over-constraint, a transaction whose two parts could not enter in
  either order, by listing the few extra unreachable items and asking the tool
  for the small set of assumptions behind one of them.
- Property completeness coverage. Logic outside the COI of every property is
  a visible hole in the property set; logic in the COI of only a few
  properties is a weak area. In its case study 4,655 of 38,633 items were
  outside every COI, and nearly 10,000 were in the COI of five or fewer
  properties, mostly data flow. A second approach injects faults, such as
  disconnecting a flop driver, and treats an undetected fault as a hole in the
  properties. [RAN] adds that earlier academic coverage methods it cites
  (Chockler et al., and Koen) had not been adopted in hardware flows because of
  cost.
- Proof coverage, full and bounded. For a full proof, use the proof core. For a
  bounded proof of depth k, count the COI items reachable within k, those
  reachable only beyond k (unconfirmed), those proven unreachable, and those
  undetermined. A bound well above the depth of the items gives good
  confidence; a bound far below it means a shallow analysis [RAN].
  [RAN] gives an illustrative 76 percent from 865 items inside the bound out
  of 1,200 less 55 unreachable ones.

## How to read a result

- First check the constraints: stimuli coverage before trusting any proof [RAN].
- Then check the property set against the design: items outside every COI are
  unchecked, not clean (inference from [RAN]).
- Then check the proof: full or bounded, and for a bounded one the unconfirmed
  and undetermined items [RAN].
- Treat 100 percent as a statement about the chosen model only: [RAN] says a
  full score is as good as the model.
- A cover that cannot be reached is a finding with three causes [RAN]: a
  design error that leaves code unreachable, a configuration that disables it
  on purpose, or constraints that block it. Explain which, as the card
  demands (gate: src/nirmaan/company/skills.py:539-542).
- Responses [RAN] lists for holes in a bounded proof: run the engines longer,
  abstract the design to cut its sequential depth, add a restricted mode
  environment, or pass the burden to simulation.

## Combining with simulation

- [RAN] describes merging formal and simulation coverage in one database
  through the UCIS interface, and warns that the two environments differ
  (stimulus models, and checkers not reusable across them), so merged
  numbers mean less than one environment's own.
- [PCP] avoids the merge problem by splitting the design so each block is
  checked by only one method, with a plan that assigns every checker to formal
  or simulation. It extracted proof-core coverage from the formal tool, merged
  it with simulation code coverage, and used it to find holes and add
  properties. Its test vehicle was small, and the authors say they did not
  tabulate the savings.
- [PCP] lists blocks that suit formal (control logic, arbiters, bridges,
  interrupt and memory controllers) and blocks that do not (heavy arithmetic,
  very deep sequential logic) as a general guide only.

## Failure modes

- Unreachable covers ignored (the card's own failure).
- Accepting a bounded result as a full proof [RAN].
- Heavy constraints with no stimuli check [RAN].
- Counting COI items as covered [PAT].
- Adding formal and simulation percentages together [RAN] [PCP].

## Not sourced here

- Vacuity beyond a cover on the antecedent. The standard papers (Kupferman and
  Vardi) could not be read as a legitimately free copy.
- The Chockler, Kupferman, Kurshan and Vardi paper on coverage in model
  checking is cited only as [RAN] describes it; its own text could not be read.
- Any numbers on how well these metrics predict missed bugs.

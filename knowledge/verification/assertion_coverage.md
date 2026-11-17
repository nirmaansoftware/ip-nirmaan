---
id: verification/assertion_coverage
skill: assertion_coverage
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | SymbiYosys documentation: Formal extensions to Verilog [SbyVerilog] | https://yosyshq.readthedocs.io/projects/sby/en/latest/verilog.html
  - open | SymbiYosys documentation: reference [SbyRef] | https://yosyshq.readthedocs.io/projects/sby/en/latest/reference.html
  - open | SymbiYosys documentation: SystemVerilog, VHDL, SVA [SbyVerific] | https://yosyshq.readthedocs.io/projects/sby/en/latest/verific.html
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K3 session (wave 2 knowledge batch, plan row W2-K3, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the formal cover tool this skill holds is available; this document is knowledge, not evidence.

# Assertion coverage

Showing that an assertion is evaluated on a non-trivial path, that its
scenarios are reached, and what the repository's cover check does and does
not say. The proof side of the same tool is in `knowledge/verification/formal_verification.md`.
Tags in brackets name the sources above; a line marked "inference" is this
document's own reasoning; a line marked "gate" names the repository code that
backs it.

## What assertion coverage asks

- An assertion that never has its precondition true passes without checking
  anything. Assertion coverage asks the opposite question to a proof: not
  whether the property can fail, but whether the situation it guards ever
  arises (inference).
- OpenTitan counts cover properties as a form of functional coverage: an SVA
  cover property observes an event or series of events, such as the valid and
  ready handshake on a bus, and it can reach signals that are not visible on
  output pins. An assertion's precondition counts as a cover point [OTDV].
- Code coverage and functional coverage answer different questions. Code
  coverage shows that code ran; it does not show the behaviour was checked,
  and 100 percent of either metric is not a verdict on correctness [OTDV].

## Cover statements in a formal setup

- In `cover` mode SymbiYosys looks for the shortest traces that reach all the
  cover statements [SbyRef].
- A cover run passes once every cover statement is reached, and fails if any
  cover statement cannot be reached within `depth` steps. It also fails if an
  assertion would have to be broken to reach the covered state [SbyVerilog].
  The reason that matters: a scenario reachable only by breaking a property is
  not a legal scenario (inference).
- The `cover_assert` option makes the run also check assertion properties
  during cover mode; its default is off [SbyRef].
- An immediate cover statement goes inside an `always` block [SbyVerilog].
  For concurrent assertions the same page points to the SVA page, which
  describes the subset supported when the design is read with the `verific`
  command [SbyVerilog] [SbyVerific]. Neither page says which concurrent forms
  the reader this repository uses accepts, so rely on the cover check's own
  refusal for that (inference).
- A cover for each behaviour the property must still allow (the full state, the
  underflow, the refusal) turns an over-constrained proof into a failing cover
  run. It cannot catch an assertion that never has its antecedent true unless
  the cover is written for that antecedent (inference).

## What the repository's cover check does

- `formal.cover` takes the proof's own setup file and runs it in cover mode
  from a copy, so the script, engines, depth and assumptions are the proof's
  (gate: src/nirmaan/integrations/eda.py:707-749).
- It writes a cover for the antecedent of each assertion into a copy of the
  design file, and fails a run in which one is never reached. An assertion
  with no implication has no antecedent and is counted as always checked (gate:
  src/nirmaan/integrations/eda_antecedents.py:1-32, eda_parsers.py:369-449).
- It refuses to run, before anything is executed, when an antecedent cannot be
  derived. The forms listed there as not derived are a sequence operator, a
  nested implication, a named property inside an expression, a named sequence,
  an action block, a deferred assertion, and a macro that asserts and cannot be
  expanded. Write the property as a single top-level `|->` or `|=>`, or as a
  procedural assertion, if it must pass this check (gate: eda_antecedents.py:23-27;
  src/nirmaan/integrations/eda.py:752-773).
- A setup with no cover at all fails, as does one whose covers are all
  unreached (gate: eda_parsers.py:369-449).
- The tool takes `sby` (required) and `sources`; it runs single-task setups
  only and refuses a setup that has no options section (gate:
  src/nirmaan/company/tools.py:148-153; eda.py:752-773). A pass says the
  antecedents and covers are reachable under the assumptions; it does not say
  the properties hold (inference).
- The must-fail scorer can require this check on the clean files before it
  tries any mutant, so every cover is reached and the pass is not vacuous
  (gate: src/nirmaan/evals/scorers.py:135-143, 200-205).

## What to do with a result

- A cover that is never reached: first look for assumptions that contradict
  each other or remove the interesting inputs, then for a depth below the
  length of the scenario, then for a cover that really is unreachable and
  should be removed with its reason (inference from [SbyVerilog]).
- An antecedent never reached: the assertion is never checked under the
  assumptions. Relax the assumption or add the scenario; do not delete the
  assertion to get a pass (inference).
- In simulation, collect the same questions with SVA cover properties or with
  functional coverage, and read them alongside the assertion failures
  [OTDV]. A simulation assertion that stays silent over a whole run, with no
  cover for its precondition, has said nothing (inference).

## Common failure modes

- An assertion whose antecedent is always false in the testbench.
- Assumptions that leave the interesting cases out, so every cover is
  unreachable while the proof passes [SbyVerilog].
- A cover that is reached by breaking an assertion [SbyVerilog].
- A property in a form the antecedent derivation cannot handle, so the cover
  check refuses and the author drops the cover check instead of rewriting the
  property (gate: eda.py:752-773).
- Treating a reached cover as evidence that the property is correct.
- Treating full coverage as a statement about the specification: coverage
  addresses an incomplete test plan [OTDV]. It does not show that the
  requirements themselves are complete (this document's inference, not a
  claim of that source).

## How a result is checked

- Read the summary line: it states whether every cover and antecedent was
  reached, with counts (gate: eda_parsers.py:369-449).
- Confirm the setup run is the proof's own, with the same files, depth and
  assumptions (gate: eda.py:707-749).
- For each unreached item, find the reason in the diagnostics, which carry the
  file and line of the cover (gate: eda_parsers.py:369-449).

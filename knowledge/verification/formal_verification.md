---
id: verification/formal_verification
skill: formal_verification
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | SymbiYosys documentation: reference [SbyRef] | https://symbiyosys.readthedocs.io/en/latest/reference.html
  - open | SymbiYosys documentation: quickstart [SbyQuick] | https://symbiyosys.readthedocs.io/en/latest/quickstart.html
  - open | Gisselquist, Introduction to formal verification, ZipCPU blog, 2017 [ZFormal] | https://zipcpu.com/blog/2017/10/19/formal-intro.html
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K1 session (wave 2 knowledge batch, plan row W2-K1, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the formal tools this skill holds are available; this document is knowledge, not evidence.

# Formal verification

Proving properties of a block with SymbiYosys, avoiding proofs that pass for
the wrong reason, and how this repository's formal gates read the result.
Tags in brackets name the sources above; a line marked "inference" is this
document's own reasoning; a line marked "gate" names the repository code that
backs it.

## Modes and what a pass means

- SymbiYosys needs a `mode` in `[options]`: `bmc` is a bounded check of
  assertions, `prove` an unbounded check, `cover` finds traces to cover
  statements [SbyRef]. In `bmc` and `cover` the `depth` option is the number of
  cycles considered, default 20; in `prove` it is the induction depth of the
  smtbmc engine [SbyRef].
- A bounded check can miss a state reached only after more steps than its
  depth [ZFormal]. Induction needs every unreachable state to be ruled
  invalid, or it can start from a state the design never reaches and report a
  false failure [ZFormal].
- The gate reads the mode the setup ran: `prove` passing reports every
  property proven; `bmc` passing reports no counterexample within the depth,
  "not a proof"; another mode reports a pass that is not a proof (gate:
  src/nirmaan/integrations/eda_parsers.py:310-345). The depth defaults to 20
  there as in sby (gate: src/nirmaan/integrations/eda.py:616).
- So a completeness claim needs a `prove` run. A `bmc` result must be reported
  with its depth (inference).

## How a proof is written

- Assert the specification's behaviour, not the RTL's internals: state each
  requirement as a property of the interface (inference). Assert at the
  conditions the specification names, including two inputs at once and error
  or refusal cases (inference).
- `assume` removes input behaviour from the search; the solver is forced to
  keep the assumption true and does not prove it [ZFormal]. Use the fewest
  assumptions that the interface specification justifies (card procedure:
  "Constrain inputs minimally"). Each assumption is a claim about the
  environment that the system must make true.
- A first-cycle past-value guard is needed before using `$past`, since the
  value before the first clock is undefined [ZFormal].
- Add cover statements for the scenarios the proof must still allow:
  reaching a full state, an underflow, a refusal. SymbiYosys writes a trace for
  each reached cover [SbyQuick].
- Put the helper properties that make induction succeed (bounds on counters,
  relations between registers) into the property file as assertions, so the
  reachable state is described fully [ZFormal].

## What the formal gates demand

- `formal.run` takes a single-task setup. A setup that declares `[tasks]` is
  refused and nothing runs; the gate runs one setup, so no task would be the
  one judged (gate: eda.py:644-649).
- When sources are given, each must be listed in the setup's `[files]`, so the
  proof reads the very files submitted (gate: eda.py:657-672).
- `formal.cover` re-runs the same setup with `mode cover` and the same
  script, engines and depth, and fails when a cover in the setup is never
  reached (gate: eda.py:702-740, eda_parsers.py:369-458). It is the vacuity
  check: a proof whose assumptions contradict each other still passes in `prove`
  mode.
- It also derives a cover for the antecedent of every assertion. An assertion
  whose antecedent is never reached under the assumptions is reported as never
  checked, and the run fails; a setup with no cover at all fails too (gate:
  eda_parsers.py:406-440). An assertion whose antecedent cannot be derived
  refuses the cover check before it runs (gate: eda.py:743-764).
- The cover check is not a proof of the properties; it shows only that the
  assertions are exercised (inference).

## Common failure modes

- Over-constraining: an assumption that removes the interesting inputs, or two
  that contradict. The proof passes and the cover check fails.
- Vacuous passes: an implication whose antecedent never fires.
- A bounded check reported as a proof, or a depth below the block's
  longest sequence.
- Properties that restate the RTL, so a bug in the RTL is also in the
  property.
- A missing property for the simultaneous case or an error output on only one
  condition, so a mutant that breaks it still passes.
- Induction failing from an unreachable state because a helper invariant is
  missing [ZFormal].

## How a result is checked

- Confirm the mode in the log and the summary line; report depth for `bmc`
  (gate: eda_parsers.py:310-345).
- Run `formal.cover` on the same setup and require every cover and antecedent
  reached (gate: eda_parsers.py:369-458).
- Run the proof against a mutant of the RTL with one behaviour broken; if it
  still passes, a property is missing (inference).
- OpenTitan's DV document for a block also covers its formal property
  verification goals [OTDV]; a proof does not replace the other tests where
  assumptions leave behaviour unchecked (inference).

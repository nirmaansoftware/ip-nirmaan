---
id: verification/model_checking
skill: model_checking
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | SymbiYosys documentation: reference [SbyRef] | https://symbiyosys.readthedocs.io/en/latest/reference.html
  - open | SymbiYosys documentation: formal extensions to Verilog [SbyVerilog] | https://symbiyosys.readthedocs.io/en/latest/verilog.html
  - open | Gisselquist, Introduction to formal verification, ZipCPU blog, 2017 [ZFormal] | https://zipcpu.com/blog/2017/10/19/formal-intro.html
  - open | Gisselquist, An exercise in using formal induction, ZipCPU blog, 2018 [ZInduct] | https://zipcpu.com/blog/2018/03/10/induction-exercise.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K2 session (wave 2 knowledge batch, plan row W2-K2, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the formal tool this skill holds is available; this document is knowledge, not evidence.

# Model checking

Getting an unbounded proof of a block's properties, why a proof stalls, and how
this repository's formal gate tells a proof from a bounded check. It builds on
the formal verification document, which covers modes, vacuity and the cover
gate. Tags in brackets name the sources above; a line marked "inference" is
this document's own reasoning; a line marked "gate" names the repository code
that backs it.

## Bounded and unbounded

- A bounded check (`mode bmc`) examines only the first `depth` cycles from the
  initial state; a state reached only later is not seen [SbyRef] [ZFormal].
- An unbounded proof has two parts, a base case and an induction step. The base
  case shows the property over the first steps from reset. The induction step
  assumes the property holds in some state and shows it holds in the next
  [ZFormal]. In SymbiYosys `mode prove` runs both [ZInduct].
- Where a check should hold for all time, such as a counter that must carry
  after a long count, only `prove` mode can say so. A bounded run shorter than
  the count never sees the carry (inference).

## What a pass means to the gate

- With `mode prove`, a pass is reported as every property proven; with `bmc`,
  as no counterexample within the depth, "not a proof"; the metrics carry a
  `proven` flag that is 1 only for a passing proof (gate:
  src/nirmaan/integrations/eda_parsers.py:310-352).
- The setup is read for its `mode` and `depth`; the depth is 20 when the setup
  gives none, as in SymbiYosys [SbyRef] (gate:
  src/nirmaan/integrations/eda.py:616-631).
- `formal.run` takes a single-task setup: a setup that declares `[tasks]` is
  refused and nothing runs (gate: eda.py:644-655).
- This skill holds `formal.run` only. The vacuity check is `formal.cover`, held
  by the formal verification skill; a proof that passes here can still be
  vacuous (see the formal verification document).

## Why a proof stalls

- In `prove` mode the induction step starts from any state that satisfies the
  assumptions and the assertions of the earlier steps, whether or not the
  design can reach it [ZFormal] [ZInduct].
- When induction fails the run ends UNKNOWN, not FAIL: the base case passed, but
  the induction step found a start state that breaks the property [SbyVerilog] [ZInduct]. A bounded run on the same design passes
  [ZInduct]. The gate reports a run that did not pass as not finished or
  failed, never as a proof (gate: eda_parsers.py:345-349).
- The usual cause is a missing relation between registers. In the ZipCPU
  example, two identical shift registers are asserted to give equal outputs;
  the proof passes the bounded check and fails induction until the property
  also says the two registers are equal [ZInduct].
- The depth matters: in `prove` mode with the `smtbmc` engine it is the
  induction depth, and other engines ignore it [SbyRef]. A trace written by a
  failed induction step shows the start state the engine chose [ZInduct].

## How to get the proof through

- Read the failed induction trace and find the registers whose values it chose
  freely. Add an assertion that relates them, so the unreachable start state is
  excluded [ZFormal] [ZInduct].
- Bound counters and relate paired registers as assertions in the property
  file, not as assumptions. An assumption about an internal register is not
  checked, so a wrong one hides a bug (inference; see [ZFormal] for what
  `assume` does).
- Raise the depth when the property needs several steps of history to be
  inductive; each extra step costs solver time [ZInduct].
- Choose an engine that suits the property. SymbiYosys lists the combinations
  for `prove`: `smtbmc` with any solver, `abc pdr`, and several `aiger` and
  `btor` engines [SbyRef]. `abc pdr` ignores `depth` in prove mode, so it
  does not depend on a chosen induction depth [SbyRef]. Several engines may be
  listed; the first to return decides [SbyRef].
- Where the state space is too large for a proof, reduce it by abstraction:
  cut or constrain a wide datapath or a long counter to a smaller one that
  keeps the behaviour under test, then say in the report what was abstracted
  (inference; the card requires abstractions to be reviewed). A property proved
  of the abstraction is a claim about the abstraction. SymbiYosys also lets a
  setup mark a value as solver-chosen with `anyconst` or `anyseq` attributes
  [SbyVerilog].

## Common failure modes

- A bounded run reported as a proof, or a depth set below the longest sequence
  the property needs [ZFormal].
- A property that is true but not inductive, so the proof stalls on
  UNKNOWN.
- A property that only bounds a value, such as a count never above its limit,
  and so cannot see a lost carry that keeps the value in range (inference).
- Assumptions added until the proof passes, which turn the claim into one
  about a narrower design than the one built.
- An abstraction that removes the very behaviour a mutant breaks.
- State explosion: a proof that does not finish within its time. The card names
  this failure; report it as not proved, with the engine and depth tried.

## How a result is checked

- Confirm `mode prove` in the log and the "every property proven" summary
  (gate: eda_parsers.py:336-344).
- Run `formal.cover` on the same setup so that the properties are exercised
  (see the formal verification document).
- Run the proof on a mutant of the RTL that goes wrong only after a long
  count; a proof that passes it is bounded in effect (inference).
- State what was assumed and abstracted next to the result, so a reader can
  tell what the proof covers (card: "Abstractions are reviewed").

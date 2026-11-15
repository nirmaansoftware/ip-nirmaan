---
id: verification/sva
skill: sva
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | SymbiYosys documentation: formal extensions to Verilog [SbyVerilog] | https://symbiyosys.readthedocs.io/en/latest/verilog.html
  - open | YosysHQ, Yosys documentation: Notes on Verilog support in Yosys [YVerilog] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/using_yosys/verilog.html
  - open | SymbiYosys documentation: SystemVerilog, VHDL, SVA [SbyVerific] | https://symbiyosys.readthedocs.io/en/latest/verific.html
  - open | Gisselquist, Introduction to formal verification, ZipCPU blog, 2017 [ZFormal] | https://zipcpu.com/blog/2017/10/19/formal-intro.html
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K2 session (wave 2 knowledge batch, plan row W2-K2, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the formal tools this skill holds are available; this document is knowledge, not evidence.

# SystemVerilog Assertions

Writing assertions and cover properties that the open-source formal flow in
this repository reads, and why the assertion style is chosen by the front end,
not by taste. Tags in brackets name the sources above; a line marked
"inference" is this document's own reasoning; a line marked "gate" names the
repository code that backs it.

## Which assertion forms the tools read

- SymbiYosys supports three immediate statements: `assume`, `assert` and
  `cover`. Each must sit inside an `always` block, either `always @(*)`, checked
  at every time step, or a clocked block, checked on the clock edge [SbyVerilog].
- `$past`, `$stable`, `$changed`, `$rose` and `$fell` are supported, and only
  inside a clocked block; `$past` has no value in the first cycle [SbyVerilog]
  [YVerilog]. A clocked assertion is checked at the clock edge after the period
  it describes, so a failure shows one step earlier than a newcomer expects
  [SbyVerilog].
- Yosys's `read_verilog -sv` accepts the `assert` statement "in its most basic
  form": `assert property (<expression>)` in module scope and `assert(<expression>)`
  in an always block; `assume`, `restrict` and `cover` have the same limits
  [YVerilog].
- Sequences, the implication operators and clocked property syntax belong to the
  richer SVA support that SymbiYosys documents for the Verific front end, which
  is part of the commercial Tabby CAD Suite and not of the open tools
  [SbyVerific]. Whether a given open build accepts a clocked
  `assert property (@(posedge clk) a |-> b)` is decided by its front end, not by
  the gate, and no run is recorded here.
- Write assertions in the immediate subset the open front end reads: guard an
  implication with an `if` inside a clocked block and use `$past` for history
  (inference). An eval case for this skill states the same constraint in its
  own words.

## How an assertion set is written

- State the requirement as an interface property: "when a request is refused,
  the error flag is set on the next cycle and stays set" is one assertion on
  outputs, not a reproduction of the RTL's internals (inference).
- Cover what each assertion needs to fire. An assertion whose guard is never
  true passes forever; add a `cover` of the guard, and a `cover` of the
  interesting end states such as full, empty and refusal [SbyVerilog] (inference
  for the pairing).
- Use `assume` for the environment only, and keep each assumption to something
  the interface specification promises. An assumption removes behaviour from
  the search and is not proved [ZFormal] [SbyVerilog].
- Guard `$past` with a first-cycle flag, or the assertion checks an undefined
  value in cycle zero [SbyVerilog] [ZFormal].
- Check the parts of a requirement separately, so a failure names one rule:
  one assertion for "no underflow", another for "error is sticky" (inference).
- Run the same assertions in simulation if the testbench can use them; OpenTitan
  places assertions in the same testplan as its tests [OTDV].

## What the formal gates demand

- `formal.run` runs a single-task setup and refuses one with `[tasks]`; given
  `sources`, every source must be listed under `[files]` (gate:
  src/nirmaan/integrations/eda.py:644-672).
- The mode decides what a pass means: `prove` proves every property, `bmc` shows
  no counterexample within the depth only (gate:
  src/nirmaan/integrations/eda_parsers.py:310-352).
- `formal.cover` runs the same setup in `mode cover`. It fails when any `cover`
  is never reached, and when a setup has none, since a setup with nothing to
  reach says nothing about its assumptions (gate: eda_parsers.py:369-458).
- It also derives a cover for the guard of each assertion, and fails a run in
  which an assertion's guard is never reached, since the assertion is then
  never checked. For an assertion inside procedural code, the derived cover
  sits on the same path as the assertion, under every enclosing `if`, `case`
  arm and loop; for a module-scope `A |-> B` or `A |=> B`, it covers `A`
  (gate: src/nirmaan/integrations/eda_antecedents.py:1-28).
- The derivation refuses what it cannot derive: a sequence operator, a nested
  implication, a named sequence, an action block, a deferred assertion, or a
  macro that asserts and cannot be expanded. The cover run is then refused and
  lists each place (gate: eda_antecedents.py:1-28; eda.py:743-764). So a
  setup that passes `formal.run` can still be refused by `formal.cover`.
- An assertion that is not in the elaborated design (a generate branch not
  taken) draws a warning that no proof checks it (gate: eda_parsers.py:369-458).

## Common failure modes

- Vacuous assertions: the guard never fires under the assumptions, and the
  proof passes (the card lists "Vacuous assertions").
- Assertions that restate the RTL, so the RTL's bug is also in the assertion.
- Over-assumption: an `assume` that blocks the input the assertion is about.
- A missing assertion for the two-events-at-once case or for the error output
  on one of several conditions, so a mutant that breaks it still passes.
- Writing concurrent-assertion syntax that the open front end rejects and
  finding out only at run time.
- `$past` unguarded in the first cycle [SbyVerilog].

## How a result is checked

- Run the setup in `prove` mode and `formal.cover`, and require every cover and
  every guard reached (gate: eda_parsers.py:369-458).
- Run the assertions against a copy of the RTL with one behaviour broken; an
  assertion set that still passes is missing a rule (inference).
- Read which assertion failed and at which step in the log before changing
  anything (gate: eda_parsers.py:310-352 records the failing assertion and
  step).

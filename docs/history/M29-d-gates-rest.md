# Milestone 29 (gates) - The RTL gates on the remaining workflows, and automatic antecedent covers (after Stage 6)

Every stage that produces `rtl_source` now carries `RTL_GATES`: M29 adds
`parameter-change` `rtl-change`, `regression-investigation` `rtl-fix`,
`timing-closure` `rtl-fix`, and `new-ip` `cdc-design` (each also produces a
`testbench`; a test enumerates `WORKFLOWS` so no RTL stage is ungated). And
the `formal.cover` run behind `NOT_VACUOUS` now derives a cover for every
assertion's antecedent, so a proof whose assertions sit under guards that
never hold is refused. Design doc: `docs/GATES_REST.md`.

Key design points worth not re-deriving:
- **`cdc-design` needed two data edits.** `rtl.cdc_design` gains
  `approved_inputs=True`, and the `cdc_design` skill gains the five gate tools:
  the runtime runs before-review checks as the seat, and the broker refuses a
  tool the role may not use. The skill does not include `rtl_design`, so
  routing is unchanged.
- **No STA before review on the timing fix.** `reanalysis` already re-runs
  `sta.run` after the fix and is the implementation gate; STA needs a Liberty
  netlist, SDC, and PDK the RTL seat does not produce; and it runs only in CI's
  `physical-design` job, so a before-review STA would either silently not
  apply or block every timing fix on most machines. Tightening `reanalysis` to
  a real run is deferred to the PD signoff work.
- **Antecedent covers are derived by elaboration, not by parsing guards.**
  `integrations/eda_antecedents.py` (imports nothing of Nirmaan) wraps each
  procedural assertion as `begin cover (1'b1); <assertion> end`, so Yosys
  gives the cover exactly the assertion's path condition: every `if`, `else`,
  `case` arm, loop iteration, generate instance, and task call. A top-level
  `A |-> B` covers `A` (module scope: `cover property (A);` after it); a
  module-scope assertion with no implication is `unguarded`. Inserted text
  never adds a newline; the manifest `<run>/antecedents.json` records each
  derived cover's file, line, and column, and `parse_sby_cover` counts those
  apart from the seat's covers (`antecedents_reached`, `_unreached`,
  `_unelaborated`; `covers_*` stay the seat's).
- **Never silently skipped.** Sequence operators, nested or chained
  implications, named properties, action blocks, deferred assertions, and
  macros whose body asserts are refused by the backend's precheck, as a
  recorded failed run listing each file, line, and reason. A derived cover
  missing from the elaborated design (generate branch not taken, task never
  called) is a warning, not a failure.
- **The seat's files are never edited.** The cover `.sby`'s `[files]` names
  the instrumented copies in `<run>/antecedents/`. All seven fixture setups
  pass unchanged: counter 1, AXI4-Lite 14, FIFO 18, arbiter 33 (N=5: 45), APB
  38 derived covers reached.

Tests: `tests/test_nirmaan_gates_rest.py` (47): the stages as data and
the registry-wide law; the CDC seat's data; on each of the four stages a latch
and a failing self-check refused, clean RTL with a proof approved, and a
never-checked assertion refused while `formal.run` passes; derivation on every
fixture (same lines, nothing else changed) and every fixture antecedent
reached; an unreachable antecedent and an underivable assertion as recorded
failed runs; the deriver and parser on text; crown jewel
`test_a_new_workflow_with_the_gates_refuses_a_never_checked_assertion_with_no_core_changes`;
`drive` on a newly gated stage; the core never names antecedents; CI requires
the formal tools. Migrated (design doc, section 4): one M27 test, which now checks that the
cover run reads an instrumented copy differing only by the derived cover; the
bridge plans that reach `cdc-design` already drove the gated
`rtl-implementation` first and pass unchanged. `formal.cover` gains no
parameter, so its M28 contract is unchanged. The standard run, merged with
main (M28 contracts, M29 auto loop), is 1297 passed and 3 skipped (OpenROAD).

Deferred: a real `sta.run` on `timing-closure` `reanalysis`; antecedents of
boolean implications inside an immediate assertion; expanding named
properties and macros; multi-task setups in the cover check.

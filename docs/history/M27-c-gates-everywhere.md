# Milestone 27 (gates everywhere) - The design gates on every RTL workflow, and non-vacuous proofs (after Stage 6)

The `new-ip` `rtl-implementation`, `feature-addition` `rtl-change`, and
`rtl-change` `change` stages now carry `RTL_GATES` (in `company/workflows.py`):
the `block-design` checks (lint, simulation, synthesis with `max_latches=0`,
formal when a `formal_spec` is produced) plus `NOT_VACUOUS`, a `formal.cover`
run over the same `.sby`, also tied to `formal_spec`. Each of the three stages
now produces a `testbench` too, and a human attestation no longer meets them.
`block-design` gains `NOT_VACUOUS` as one added line. Design doc:
`docs/GATES_EVERYWHERE.md`.

Key design points worth not re-deriving:
- **Non-vacuity is a cover run of the seat's own setup.** The
  `symbiyosys-cover` backend (`integrations/eda.py`) writes a copy of the
  `.sby` into the run's directory with `mode cover` and absolute `[files]`
  paths; script, engines, depth, and assumptions are the proof's.
  `parse_sby_cover` passes only on `DONE (PASS)`, exit 0, at least one reached
  cover, and none unreached (SymbiYosys itself calls a setup with no covers a
  pass). `[tasks]` setups are a recorded failure. A separate tool, not a
  `formal.run` mode, so a cover run can never meet "Formal properties are
  proven".
- **What it catches:** over-constrained inputs, assumptions contradictory on
  the path to a covered state, antecedents the seat covers. A plain
  `assume (1'b0)` already fails `formal.run` (smtbmc `--presat`). Covers the
  seat did not write, or trivial ones, are the reviewer's to catch.
- **Approved inputs through gates.** On `new-ip` and `feature-addition` the RTL
  task depends on `microarchitecture.gate`, which has no artifacts, so the seat
  saw no upstream and the M23 approved-inputs check held vacuously.
  `upstream_artifacts(state, task)` in `work/policy.py` looks through gate
  tasks; the context packet, the `approved-inputs` check, and the upstream
  bindings of `evidence-before-review` all use it.
- **`drive` follows the gated order.** `tests/nirmaan_helpers.py`
  `gated_submit` writes `counter.v` and `counter_tb.v`, runs each applicable
  before-review check through the broker from the requirement's own data,
  records the runs, then submits. Tests that drive through these stages need
  `GATE_TOOLS` (`verilator iverilog vvp yosys`) and are marked so.
- **Fixture covers** in `counter`, AXI4-Lite (8), FIFO (6), arbiter (2 per
  requester, including the tight fairness bound), and APB (4), under
  `` `ifdef FORMAL ``. The APB proof depth rose from 4 to 8 so a write and read
  back is reachable.

Tests: `tests/test_nirmaan_gates_everywhere.py` (34): the stages as data; the
planned tasks gated and on approved inputs (through a gate, and a cancelled
impact analysis refusing an `rtl-change`); on each of the three workflows a
latch and a failing self-check refused and clean RTL with a proof approved;
two vacuous proofs refused while `formal.run` passes; `assume (1'b0)` failing
both runs; no covers refused; all
seven fixture setups reach every cover; the cover run's isolation and
prechecks; the parser on captured logs; crown jewel
`test_a_fourth_workflow_is_gated_with_no_core_changes`; `drive`'s order; the
core never names `formal.cover`; CI requires the formal tools. Migrated (each
listed in the design doc, section 5): two `test_nirmaan_work.py` tests and one
each in `test_nirmaan_eda.py` and `test_nirmaan_export.py` gained
`GATE_TOOLS`; three exact tool-set assertions gained `formal.cover`. The
standard run, merged with the review-repair milestone, is 1160 tests with 2
skipped (OpenSTA, OpenROAD).

Deferred: the same gates on `parameter-change` and the fix stages
(`regression-investigation`, `timing-closure`) and on `cdc-design`; automatic
antecedent covers; multi-task setups in the cover check.

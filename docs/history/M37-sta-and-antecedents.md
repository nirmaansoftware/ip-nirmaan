# Milestone 37 - Real STA on timing re-analysis, and antecedents of named properties and macros (after Stage 6)

Closes the roadmap cell "A real `sta.run` (not an attestation) on
`timing-closure` `reanalysis`; antecedents of named properties and macros".
Design doc: `docs/STA_AND_ANTECEDENTS.md`. No version bump.

Key design points worth not re-deriving:
- **`RETIMED` on `reanalysis`, as data** (`company/workflows.py`): a
  before-review `sta.run` (tool run only, no attestation) whose `sources` are
  the approved upstream `rtl_source`, with the task's `sdc`, `top`, and PDK
  inputs. The old `ran("Clean timing report", ...)` stays only on the
  constraint and physical branches.
- **`EvidenceRequirement.when_upstream`**: a requirement applies only when the
  task builds on an upstream artifact of one of those kinds. Branch decisions
  are known after planning, so `when` (request features) cannot express it.
  `applies(kinds, upstream)`; the policy uses `upstream_kinds`, the runtime
  checks the packet's upstream list before and after the answer.
- **`sta.run` takes `sources`**: one recorded run synthesizes to the Liberty
  (the `yosys-liberty` script), then times the `netlist.v` it wrote. `netlist`
  and `sources` together, or neither, is a recorded failed run; `sources`
  without Yosys is refused by the probe. Without `sta` and `openroad` a
  reanalysis answer is BLOCKED with the broker's reasons.
- **Named properties are inlined, macros expanded, in the cover copy**
  (`eda_antecedents.py`): `definitions(texts)` collects macros, properties,
  and sequences across every file the setup reads; the deriver then derives
  covers as for written assertions. Lines never move, and line numbers are
  counted after expansion. Yosys's frontend rejects `property` declarations,
  so with today's tools a seat's named properties fail `formal.run` first; the
  cover check is real and tested on the inlined copy. Refused, with a line and
  a reason: a property inside an expression, named or wrong-count arguments,
  two clocks, a named sequence, nesting deeper than 8, a macro defined twice,
  token pasting, and a wrong argument count.
- **CI**: the `physical-design` job takes Verilator, Icarus, and vvp from the
  pinned OSS CAD Suite (the image's Ubuntu 22.04 Icarus 11 prints no
  "$finish called" line) and runs `tests/test_nirmaan_sta_antecedents.py`,
  including a real timing-closure project on Nangate45 at 2.2 ns:
  before the fix setup slack -0.340 ns (TNS -1.814, 10 endpoints), after the
  approved pipelined fix +0.452 ns (TNS 0), hold +0.075 ns both (CI run
  37924965528).

`tests/test_nirmaan_sta_antecedents.py` (30); crown jewel
`test_a_new_workflow_scopes_a_requirement_to_one_branch_with_no_core_changes`.
One M29 test migrated (`test_unguarded_and_unsupported_assertions_are_listed`:
an unused asserting macro asserts nothing, and a named property is inlined).
The standard local run is 1465 passed, 7 skipped.

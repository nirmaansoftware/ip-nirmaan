# Milestone 58 - Eval cases name skills; must-fail scorer

Item P1-08 of the capability build-out council record of 2026-10-18 (section 9:
the capability model). Design doc: `docs/EVAL_SKILLS_MUST_FAIL.md`. No version
bump. No model was called and no `evals/results/` record was created.

Key design points worth not re-deriving:
- **`EvalCase.skills`** names the skill IDs a case judges; `validate_case`
  refuses one not in the catalog or named twice. Only these skills get credit
  from a result. The six shipped cases name theirs in a separate commit:
  `rtl_design` on the four RTL cases (plus `axi` and `apb` on the two bus
  cases), `interface_specification` on the spec case, `device_drivers` on the
  firmware case.
- **The run record** gains each trial's `skills` (skill ID -> sha256 over the
  catalog entry and `knowledge/<division>/<skill_id>.md` when it exists) and the
  manifest's `head_sha` (the CLI reads it with `git rev-parse HEAD`; the
  evaluation package never runs a command). The format is in
  `evals/README.md`, "Result records".
- **`must-fail` scorer**: the clean run must pass, an optional `cover_tool` must
  pass over the clean inputs, and each mutant (a case file standing in for
  another, `mutants`) must fail on a run that executed. A refusal is never a
  mutant caught. Inputs are staged under their own names so a `.sby` reads the
  mutant. `seat_entries` fills a parameter (the testbench top) from the seat's
  own passing gate run.
- **Runner**: `Score.failed_runs` must all be recorded failed runs, or a
  claimed pass is overturned; the record keeps them in `judge_runs`.
- **`load_evidence`** refuses a replay and a trial with a human attestation
  (`EvalResult.attestations`, the evidence a `dv_ran` requirement accepts
  instead of a tool run). `load_record` is unchanged.
- **Fixtures**: `tests/fixtures/rtl/sync_fifo/mutants/` (overflow, power-of-two
  wrap). The power-of-two mutant passes the DEPTH 8 proof and fails the DEPTH 5
  one: formal at each parameter point.
- Tests: `tests/test_nirmaan_eval_must_fail.py`.

Follow-up from the review of #122: the must-fail scorer stages its inputs
inside the evaluation's sandbox (`ScoreContext.work`), so each run's
parameters name files kept with the record, and a caller with no sandbox
folder gets a temporary one that is removed; the pass summary counts the
mutants from the check; the runner's attestation list has a test of its own.

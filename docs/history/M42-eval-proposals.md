# Milestone 42 - Learning proposals from evaluation results (after Stage 6)

Closes the M33 deferral "Proposals from evaluation results". Design doc:
`docs/EVAL_PROPOSALS.md`. No version bump.

Key design points worth not re-deriving:
- **Recorded results only.** `eval_proposals.load_results(root)` reads every
  `EvalResult` JSON under a directory (one per file, or a list as `eval run
  --json` prints); replays and results whose audit chain failed are not read.
  A run's ID is `ev-` plus a hash of case, runtime, start time, and case digest.
  `nirmaan eval run` overwrites `<runtime>/<case>.json`, so a history is one
  `--out` per run; the real #57 results were never committed, so the fixtures
  (`tests/fixtures/eval_results_synthetic/`, runtimes `fixture-model-a`/`-b`)
  are synthetic and labelled so in every file.
- **Rules are a registry** (`register_eval_rule`) over an `EvalHistory`
  (runs grouped by case and runtime, the thresholds, each case's capability
  from the workflows). `recurring-eval-failure`: `min_failures` (2) of the
  latest `within_runs` (5); suggests a different model (another runtime's
  latest run passed: M31 selection), a procedure (no failing run reached
  review: run the failed gate tools), or a check (a held-out judge caught what
  the gates missed). `eval-pass-rate-regression`: two windows of `window` (4)
  runs, a drop of at least `min_drop` (0.25), naming the versions in each.
  Thresholds: `EvalProposalThresholds` (models), data in `company/learning.py`.
- **The M33 `Proposal`** gains `source` (`failures` or `evaluation`); subject
  `<case>@<runtime>`, `projects` 0. `decide_proposal` records an evaluation
  proposal in any project the person names (it rests on files, not project
  records); human only, authority matrix, adopting edits nothing.
- `nirmaan learn [PROJECT...] [--evals DIR] [--cases DIR]`: projects optional
  when `--evals` is given; each evaluation proposal prints every cited run.

`tests/test_nirmaan_eval_proposals.py` (17), crown jewel
`test_a_new_eval_rule_needs_no_core_changes`.

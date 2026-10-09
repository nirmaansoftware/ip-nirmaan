# Evaluation cases

Each JSON file here is one evaluation case for `nirmaan eval` (M27). A case
fixes everything except the seat under evaluation, and judges the seat's work
with deterministic tool runs it never saw. Design: `docs/SEAT_EVALUATION.md`.

```
nirmaan eval list
nirmaan eval run --replay                      # the reference answers: proves the cases and their judges
nirmaan eval run rtl/axi4-lite-regs --runtime anthropic --attempts 2   # a live model (needs the ai extra and credentials)
NIRMAAN_CLAUDE_CODE=/path/to/claude nirmaan eval run --runtime claude-code   # a live model on your Claude plan
```

Run from the repository root (case paths are relative to it, or pass
`--repo`). Results are written to `.nirmaan/evals/<runtime>/<case>.json`
(`--out` to change), and the command exits 1 when any case fails.

## Fields

| Field | Meaning |
|---|---|
| `id` | Unique case ID, e.g. `rtl/axi4-lite-regs`. |
| `request` | The requirement as a person would type it. It must plan a workflow with `seat` as one work task. |
| `seat` | The stage whose seat is evaluated. |
| `expected_behavior`, `constraints`, `known_failure_modes` | What good work looks like and how it tends to go wrong. For people; not scored. |
| `upstream` | Stage ID to reference documents (`path`, `kind`). They stand in for that stage's approved output. Upstream stages not listed get the request text. |
| `reference` | The reference answer's files (`path`, `kind`, optional `entry`), used by `--replay`. |
| `held_out` | Checks the seat never sees. The built-in scorer `held-out-run` runs `tool` with `params`, filling each parameter from the seat's submitted files of the kinds in `seat_files`, then the files in `case_files`. |
| `attempts` | Attempts per run when the engine refuses a submission (default 1). |

## Rules

- A case passes only when the seat's work reached review (its own
  before-review checks passed) and every held-out check passed.
- A held-out pass must cite a passing tool run recorded in the evaluation's
  sandbox project. A check whose tool cannot run is `not_run`, never a pass.
- A gate or decision before the seat stops the run: the harness fixes work
  stages only.
- Keep held-out inputs out of the documents the seat is given; otherwise the
  check is no longer held out.

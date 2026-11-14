# Evaluation cases

Each JSON file here is one evaluation case for `nirmaan eval` (M27). A case
fixes everything except the seat under evaluation, and judges the seat's work
with deterministic tool runs it never saw. Design: `docs/SEAT_EVALUATION.md`.

```
nirmaan eval list
nirmaan eval run --replay                      # the reference answers: proves the cases and their judges
nirmaan eval run rtl/axi4-lite-regs --runtime anthropic --attempts 2   # a live model (needs the ai extra and credentials)
NIRMAAN_CLAUDE_CODE=/path/to/claude nirmaan eval run --runtime claude-code --trials 5 --seats rtl,spec,firmware
nirmaan eval history                           # every committed run record, with pass rates and intervals
nirmaan eval rejudge evals/results/<record>    # replay a record's answers through the real judges
```

Run from the repository root (case paths are relative to it, or pass
`--repo`). Each run writes a run record (M45, `docs/LIVE_EVAL_EVIDENCE.md`):
a live run under `evals/results/<date>-<runtime>-<model>/`, which is
committed, and a replay under `.nirmaan/evals/`, which is not (`--out` to
change). The command exits 1 when any trial fails.

Cases live in groups (`rtl/`, `spec/`, `firmware/`, and `dv/` for verification
seats); `--seats` selects by group or by seat stage. A JSON file with a `format` field (a run record, a checks
file such as `spec/axi4_lite/interface_checks.json`) is data, never a case.

## Fields

| Field | Meaning |
|---|---|
| `id` | Unique case ID, e.g. `rtl/axi4-lite-regs`. |
| `request` | The requirement as a person would type it. It must plan a workflow with `seat` as one work or decision task. |
| `seat` | The stage whose seat is evaluated. |
| `skills` | The skill IDs the case judges (M58), each in the skill catalog (`nirmaan org skills`). Only these skills get credit from its results; a stage pass never credits every skill of the stage. |
| `expected_behavior`, `constraints`, `known_failure_modes` | What good work looks like and how it tends to go wrong. For people; not scored. |
| `upstream` | Stage ID to reference documents (`path`, `kind`). They stand in for that stage's approved output. Upstream stages not listed get the request text. |
| `reference` | The reference answer's files (`path`, `kind`, optional `entry`), used by `--replay`. |
| `outcome` | A decision seat's reference outcome (M71: root cause, e.g. `rtl_bug`), required for a decision seat and refused for any other. |
| `inputs` | Stage ID to task input to case files (M71), given to that stage, seat or upstream, as a comma-joined list: the failing logs a triage investigates (`{"triage": {"paths": [...]}}`). The files are part of the case digest. |
| `held_out` | Checks the seat never sees. The built-in scorer `held-out-run` runs `tool` with `params`, filling each parameter from the seat's submitted files of the kinds in `seat_files`, then the files in `case_files`. The scorer `must-fail` is a negative control (below). |
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

## Negative controls: the `must-fail` scorer (M58)

A check with `"scorer": "must-fail"` proves that a testbench or a set of
assertions can tell wrong RTL from right. Its fields beyond `held-out-run`'s:

| Field | Meaning |
|---|---|
| `mutants` | Case file -> files that each stand in for it. Each mutant is one run of `tool` that must fail. A mutant must replace one of the check's `case_files`. |
| `seat_entries` | Tool parameter -> artifact kinds whose declared entry fills it, as the seat's own passing runs of that file gave it (the seat's testbench top, for example). |
| `cover_tool` | Optional. A tool that must also pass over the clean inputs, so the clean pass is not vacuous (`formal.cover`: every cover reached). |

The check passes only when the clean run (the seat's files with the case
files) passes, the `cover_tool` passes, and every mutant makes `tool` fail on a
run that executed and wrote its log. A refusal, which ran nothing, is never a
mutant caught. Each run reads a staged copy of its inputs under their own file
names, so a mutant takes the name of the file it replaces and a proof setup
that names its files reads it in place. Run each proof at each parameter point:
a mutant that is wrong only for a DEPTH that is not a power of two passes a
DEPTH 8 proof and fails a DEPTH 5 one. A prove-mode mutant run that passes
its basecase and fails its induction step (sby reports UNKNOWN with the failed
assertion) executed and wrote its log, so it counts as a mutant caught
(`dv/prove-deep-counter`). An equivalence seat's control runs
`equivalence.run` over the seat's eqy setup with a non-equivalent refactor in
place of the approved one (`dv/equiv-gray`); a random-stimulus testbench's
control is the ordinary `simulator.run` one (`dv/random-crc`), and a run that
is too short or whose constraints never reach a corner lets a mutant survive.

A debug seat's control judges its repro testbenches. A root-cause repro has
`must-fail` checks like a testbench (`debug/root-cause-uart-tx`: it passes the
fixed RTL and fails the RTL under investigation and a variant, on two
independent implementations); a triage seat's repros are judged by
`must-fail-each`, one repro per seeded bug (`debug/triage-three-bugs`). Both
cases give the failing logs through `inputs` and run against RTL the case
hands over as `design-under-investigation`.

```json
{
  "name": "The seat's testbench fails each mutant",
  "scorer": "must-fail",
  "tool": "simulator.run",
  "seat_files": {"sources": ["testbench"]},
  "seat_entries": {"top": ["testbench"]},
  "case_files": {"sources": ["tests/fixtures/rtl/sync_fifo/sync_fifo.v"]},
  "mutants": {"tests/fixtures/rtl/sync_fifo/sync_fifo.v": [
    "tests/fixtures/rtl/sync_fifo/mutants/sync_fifo_overflow.v",
    "tests/fixtures/rtl/sync_fifo/mutants/sync_fifo_pow2_wrap.v"]}
}
```

## One repro per bucket: the `must-fail-each` scorer (M71)

For a seat that writes several files of one kind (a triage seat's repro
testbenches, one per failure bucket), `must-fail-each` judges each file on its
own: `seat_files` names one parameter, each seat file of those kinds runs alone
with the `case_files` (its `seat_entries` from the seat's own passing run over
that file alone), each must pass on the clean inputs, and every mutant (one
seeded bug per bucket) must fail a different file. One repro that fails every
bug cannot stand for two buckets. Design: `docs/REPRO_GATES.md`.

## Result records (M58)

A live run record under `evals/results/` is the only thing that can show a
skill was practised (M45 wrote the record; `docs/LIVE_EVAL_EVIDENCE.md` has the
full layout). Each record names:

| What | Where in the record |
|---|---|
| Model ID | `manifest.json` `model`, and each trial's `model` (what the answers reported) |
| Skill digest | each trial's `skills`: skill ID -> `sha256:` over the skill's catalog entry (its card) and its knowledge document `knowledge/<division>/<skill_id>.md` when one exists |
| Case ID | each trial's `result.case`, with `result.case_digest` over the case and every file it names |
| Trials | `manifest.json` `trials` (per case), and each trial file's `trial` number |
| Judge tool | each trial's `judge_runs[].tool`, with the run, its parameters, and whether it succeeded; a must-fail control's mutant runs are there too, as failed runs |
| Head SHA | `manifest.json` `head_sha`: the commit the run was made on |
| Outcome | each trial's `result.passed`, with every judge's `result.scores[].status` |

`nirmaan.evals.load_evidence` reads a record only if it may count as evidence
about a model. It refuses:

- a **replay** (the manifest or any trial says `replay`, or its runtime is
  `replay`): a replay proves the case, never a model;
- a trial whose `result.attestations` is not empty: a human attestation on the
  seat's task (what a `dv_ran` verification requirement accepts in place of a
  tool run) is never a tool-judged result.

No record is committed yet. A case and the skill content it grades (a skill
card or a knowledge document) never change in one pull request.

# Learning proposals from evaluation results (M42)

M33 (`docs/LEARNING_PROPOSALS.md`) proposes skill changes from failures that
recur across projects, and deferred one input: seat evaluation results (M27,
`docs/SEAT_EVALUATION.md`). M42 adds it. A seat that keeps failing a case, or
whose pass rate on a case drops, now produces a proposal with the same model,
the same rule that only a person decides, and the same rule that adopting
changes nothing by itself.

## Inputs: recorded results, never a model call

`nirmaan.eval_proposals.load_results(root)` reads every `*.json` under a
directory: each file is one `EvalResult` (what `nirmaan eval run` writes) or a
list of them (what `nirmaan eval run --json` prints). An unreadable file is an
error, not a silent skip. Nothing here runs a case or calls a model.

`nirmaan eval run` writes `.nirmaan/evals/<runtime>/<case>.json`, so a second
run into the same directory replaces the first. To keep a history, give each
run its own `--out` (for example `.nirmaan/evals/2026-10-09`) and read the
parent directory. Changing that layout is out of scope here.

What is read, and what is not:

- **Replays are left out.** A replay is the case's own reference answer; it
  proves the case, not a model.
- **A result whose audit chain did not verify is left out.** Its sandbox
  cannot back what it says.
- **Each run has an ID**, `ev-` and 10 hex digits of SHA-256 over case,
  runtime, start time, and case digest. The same file read twice is one run.

A run is a failure when `passed` is false. Its evidence keeps everything the
result recorded about why: the seat status, whether the work reached review,
the failed gate runs, and every judge verdict (check name, scorer, status,
summary, and the tool runs that back it).

## Rules and thresholds

Rules are a registry (`register_eval_rule`, `unregister_eval_rule`). Each reads
the runs of one case on one runtime, oldest first. Two ship:

| Rule | Fires when | Default |
|---|---|---|
| `recurring-eval-failure` | At least `min_failures` of the latest `within_runs` runs failed | 2 of the latest 5 |
| `eval-pass-rate-regression` | The pass rate over the latest `window` runs is at least `min_drop` below the pass rate over the `window` runs before them | windows of 4, a drop of 0.25 |

The thresholds are company data: `EVAL_PROPOSAL_THRESHOLDS` in
`src/nirmaan/company/learning.py`, an `EvalProposalThresholds` (frozen,
validated). A caller may pass other thresholds; the CLI uses the company's. One
failure, or failures below the threshold, propose nothing. A regression needs
two full windows: with fewer runs there is no earlier rate to fall from.

## What a proposal suggests

A proposal is the M33 `Proposal` with `source="evaluation"` (M33's are
`source="failures"`). Its capability is the one the case's seat stage needs
(read from the workflows), and its targets are the skills that provide it. Its
subject is `<case>@<runtime>`, so the ID (rule, capability, subject) is stable
as runs accumulate. `count` is the number of failing runs cited; `projects` is
0, because evaluation runs live in sandboxes, not in projects.

The recurring-failure suggestion depends on the evidence:

1. **A different model**, when another runtime's latest run of the same case
   passed: seat the capability with that model through M31 model selection
   (a model profile, or the `auto` runtime's choice).
2. **A procedure change**, when no failing run reached review: the seat's own
   before-review gates failed, so run those tools (named from the failed gate
   runs) on one's own files before submitting.
3. **A new check**, when the work reached review and a held-out judge failed it:
   the seat's own gates missed what the judge caught, so add a before-review
   check covering that judge, with the judges' summaries quoted as the
   validation criterion.

The regression suggestion names the versions in each window and asks a person
to compare what changed between them (skill text, model, or the case digest)
before deciding.

## Deciding

Unchanged from M33 except where the decision is recorded. An M33 proposal rests
on records in projects, so its decision is recorded in one of them. An
evaluation proposal rests on result files, so `decide_proposal` records it in
whichever project the person names: still a cross-team decision of medium
criticality through `TaskEngine.record_decision`, still the authority matrix
(a manager or above), still refused for an AI agent, and still shown by
`nirmaan decisions`. Its status is read from those decisions as in M33.

**Adopting changes nothing.** No skill, model profile, check, or case is
edited. An adopted proposal is the recorded reason for a person's pull request.

## Surfaces

```
nirmaan learn [PROJECT...] [--evals DIR] [--cases DIR] [--json]
nirmaan learn PROJECT... --evals DIR --decide ID --in PROJECT --as ROLE (--adopt | --reject) --reason TEXT
```

`--evals` adds evaluation proposals; `--cases` (default `evals`) is where the
case files are, to find each seat's capability. Each evaluation proposal prints
its provenance: every cited run with its ID, case, runtime, version, and the
judge verdicts. With `--evals`, projects are optional for listing; deciding
still needs a project to record in.

## Fixtures

The real results of the first live evaluation (#57) were not committed: only
the summary table in `docs/SEAT_EVALUATION.md` was. M42 does not reconstruct
them. The tests use synthetic recorded runs under
`tests/fixtures/eval_results_synthetic/`, each labelled in its `detail` and
`sandbox` fields and in a README as a synthetic test fixture, with runtimes named
`fixture-model-a` and `fixture-model-b` so no one mistakes them for a real
model's results. Tests that need other histories write synthetic results into
a temporary directory.

## Tests (`tests/test_nirmaan_eval_proposals.py`)

- A recurring failure proposes, citing each failing run's ID, case, runtime, and
  judge verdicts; the ID is stable as runs accumulate.
- One failure, or failures below the threshold, propose nothing; replays and
  results with a broken audit chain are not read.
- A pass-rate regression proposes; thresholds passed as data change the outcome.
- The suggestion is a model, a procedure, or a check, from the evidence.
- Reading changes no organization data; adopting edits no skill.
- Only a human with authority decides; the decision shows in `nirmaan decisions`.
- The CLI lists evaluation proposals with provenance, and decides one.
- `eval_proposals.py` names no stage, tool, artifact kind, or role, and does
  not import VeriTriage.
- Crown jewel `test_a_new_eval_rule_needs_no_core_changes`: a rule registered in
  the test proposes from judges that keep not running.

## Deferred

- A run history kept by `nirmaan eval run` itself (today: one `--out` per run).
- Committing raw live results, so real runs can be inputs without a rerun.
- Rules across cases (a seat failing several cases on one judge kind).

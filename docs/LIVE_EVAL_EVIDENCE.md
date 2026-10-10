# Live evaluation as recorded, repeatable evidence (M45)

M27 (`docs/SEAT_EVALUATION.md`) made seat evaluation possible: cases as data,
judges that are real tool runs. What it did not make was evidence. The one
live run (#57: Claude Opus 5.5 in the RTL seat, four cases, once each, outside
CI) left a summary table in a document and nothing else: no raw answers, no
judge records, no way to check the table, and n=1 per case. M42's learning
proposals have only ever read synthetic results. The structural review ranked
this the top risk: the product's thesis is model seats checked by tools, and
the claim that models do the work rested on a run nobody can re-examine.

M45 turns a live evaluation into a committed run record that anyone can
re-judge, runs each case several times and reports pass rates with honest
intervals, adds cases for the spec and firmware seats, and feeds the records
to M42.

## 1. The run record

`nirmaan eval run` writes one directory per invocation:

```
evals/results/<date>-<runtime>-<model>/      e.g. 2026-10-12-claude-code-claude-opus-5-5
  manifest.json                              format nirmaan.eval-run
  summary.json                               format nirmaan.eval-summary
  <case>/trial-01.json ... trial-NN.json     format nirmaan.eval-trial
```

A live run (`--runtime`) writes under `evals/results/`, which is committed. A
replay (`--replay`, the case's own reference answer) writes under
`.nirmaan/evals/`, which is not: a replay proves the case, not a model, and
must never be mistaken for evidence about one. `--out` overrides either. A
directory that already exists is never overwritten: the next free `-2`, `-3`
suffix is used.

**The manifest** (`EvalRunManifest`): record ID (the directory name), runtime,
model, replay flag, Nirmaan version, start and finish time, trials per case,
the case IDs and the seats they evaluate, and the command line.

**A trial** (`EvalTrial`), one per case per trial:

| Field | What it holds |
|---|---|
| `result` | The M27 `EvalResult`, unchanged: case digest, seat status, attempts, the seat's own gate runs, judge scores, `passed`, audit check, and the M31 accounting (model calls, input and output tokens, cost or `null` when unknown). |
| `answers` | Every raw model answer, in order: mode (work or review), provider, model, the SHA-256 of the prompt as sent (system and user parts), the SHA-256 of the work packet the prompt carries (task, sections, citations, outputs, needs, before rendering), the full text, the error if any, and the token counts as reported. |
| `judge_runs` | Every tool run behind a judge verdict: the check it judged, run ID, tool, succeeded, summary, and the parameters it ran with. |
| `model` | The model the answers report (or the runtime's configured model when no answer reported one). |

**The summary**: per case and per seat, trials `n`, passes `k`, the pass rate,
and its 95% Wilson interval; totals of model calls, tokens, duration, and cost
(`null` when any call had no price, as on a subscription).

Answers are captured by wrapping the runtime's model (`ModelRuntime.llm`) in
a recorder for the duration of a trial. Nothing about the seat changes: the
same `run_task`, gates, grounding, repair loop, and judges.

## 2. Re-judging a record

`nirmaan eval rejudge <record>` replays each trial's stored answers, in order,
through a scripted model in a fresh sandbox, with the clock set to the trial's
recorded start, and runs the seat's gates and the held-out judges again for
real. It compares what it gets with what was recorded: work reached review or
not, the seat status, each judge's status, and `passed`. It exits 1 on any
difference.

- **Same inputs or no comparison.** If the case's digest (the case file and
  every file it names) differs from the recorded one, the trial is reported as
  not comparable and counts as a difference: the judges are no longer the ones
  that ruled.
- **No invented answers.** When the replay asks for more answers than were
  recorded, the scripted model answers with an error that is not a model call,
  so the seat declines and the difference shows.
- **Why it reproduces.** Planning is deterministic (project and artifact IDs
  are digests and counters, not random), so the citation tokens in a stored
  answer resolve in the replayed prompt exactly as they did in the original.
  The tools are deterministic on the same files. A difference therefore means a
  tool, a judge, or a case file changed, which is what re-judging is for.

## 3. Repeated trials and intervals

`--trials N` runs each case `N` times, each in its own sandbox with a fresh
runtime. The convention is at least 5 for a model, so `N` defaults to 5 with
`--runtime` and to 1 with `--replay` (the reference answer is deterministic).
The CLI prints a warning when a live run uses fewer than 5.

Pass rates are reported per case and per seat, each with a 95% Wilson score
interval, `k/n (rate, 95% CI low to high)`. Wilson is used rather than the
normal approximation because it stays inside 0 to 1 and is honest at small n:
5 of 5 passes gives roughly 57% to 100%, not 100%. The report always prints
`n`, and says plainly when n is below 5 that the interval is wide. Nothing
averages across cases into a single headline number; per seat is the coarsest
summary.

## 4. More cases: the spec seat and the firmware seat

Six cases ship (four RTL from M27, and two new):

| Case | Seat | Fixed upstream | Held-out judges |
|---|---|---|---|
| `spec/axi4-lite-interface` | `interface-spec` | a requirements spec that tags eight requirements | `spec.check`: every tagged requirement carried with its tag and its key terms; every port and parameter named |
| `firmware/axi4-lite-driver` | `firmware` | interface spec and a driver API note; microarchitecture; the reference RTL, run through its real gates | `fw.build` of the seat's driver alone; `fw.test` of a held-out test program against the approved RTL |

**`spec.check`** is a new `AVAILABLE` in-process tool (it reads files only).
It takes the seat's spec files and a case's checks file (format
`nirmaan.spec-checks`): a list of requirement IDs, each with terms its tagged
text must contain, and a list of names that must appear in the spec as whole
words. It passes only when every listed requirement is tagged exactly once
(`[req:ID]`, the M29 tag grammar, parsed by `nirmaan.vplan.spec_requirements`),
each tagged text contains its terms (case-insensitive), and every name
appears. It is granted through the `interface_specification` skill, so the
spec seat's own role can run it, which is the role the judge acts in.

Why requirement tags: they are already how this project traces a spec to its
requirements (M29, M38), the verification plan seat is checked against the
same tags, and a spec that drops a requirement or renames a port breaks every
stage after it. The #57 run found exactly that class of failure (ports named
without the `s_axil_` prefix), one stage later.

**The firmware case** fixes the RTL stage to the reference RTL. A stage with
before-review checks cannot be fixed by a submission alone, so the harness now
puts the case's reference files in that stage through the unchanged `run_task`
with a replayed answer (runtime ID `eval-fixture`): its lint, simulation, and
synthesis run for real, and only then is it reviewed and approved by the
`eval-fixture` system actor. The firmware seat then sees approved RTL, as it
would in a project. The driver API is fixed by an upstream note (header names
and declarations) so that a held-out test program can call any seat's driver.

**Proving the judges fail bad answers** (tests, not only the reference):

- spec: a spec that drops the SLVERR requirement's tag, and one that names the
  ports without their prefix, both reach review and both fail `spec.check`;
- firmware: the deliberately wrong register map header (REG2 at REG1's offset)
  with a test program that only reads reset values passes the seat's own
  `fw.build` and `fw.test`, reaches review, and fails the held-out test.

## 5. Real results into M42

`eval_proposals.load_results` now reads run records as well as plain result
files: a trial file contributes its `result`, a manifest or summary is skipped,
and each run is labelled with its **source**: `record:<record ID>` for a trial
of a committed run record, `file` for a plain `EvalResult` file such as the
synthetic fixtures. The source is part of every proposal's evidence and of the
CLI's provenance lines. `nirmaan learn --evals` may be given more than once,
so `--evals evals/results --evals tests/fixtures/eval_results_synthetic` reads
both, each labelled. Replays and broken audit chains stay excluded, as in M42.

## 6. The scheduled workflow (disabled until a secret exists)

`.github/workflows/live-eval.yml` runs weekly (and on manual dispatch), never
on a pull request or a push. Its first step, `scripts/live_eval_gate.py`,
checks for the `CLAUDE_CODE_OAUTH_TOKEN` secret (from `claude setup-token`, so
the run uses the owner's plan through the `claude-code` runtime). Without it
the gate writes `enabled=false` and a notice, and every later step is skipped:
the job is green and spends nothing. With it, the job installs the EDA tools
and Claude Code, runs the batch, and uploads the run record as a workflow
artifact. It never commits: the owner reviews the record and commits it in a
pull request, as with any evidence.

To enable it: add the repository secret `CLAUDE_CODE_OAUTH_TOKEN`. To disable
it again: delete the secret.

## 7. The owner's first recorded batch

From the repository root, with Claude Code signed in to the owner's plan and
the EDA tools on PATH:

```
NIRMAAN_CLAUDE_CODE="$(which claude)" nirmaan eval run --runtime claude-code --trials 5 --seats rtl,spec,firmware
```

`--seats` selects cases by their group (the part of the ID before `/`) or by
their seat stage, so this runs all six cases, 30 trials in all. Then:

```
nirmaan eval history
nirmaan eval rejudge evals/results/<the new directory>
nirmaan learn --evals evals/results
```

and commit `evals/results/<the new directory>` in a pull request.

**Expected usage**, estimated from #57's measured RTL runs (12,854 to 29,205
output tokens and 114 to 246 s per call; mean about 20,600 tokens and 180 s):

| Seat | Trials | Output tokens (est.) | Time (est.) |
|---|---|---|---|
| RTL (4 cases) | 20 | about 410,000 | about 60 min |
| Spec (1 case) | 5 | about 40,000 to 60,000 | about 8 min |
| Firmware (1 case) | 5 | about 50,000 to 80,000 | about 12 min |
| **Total** | **30 calls** | **about 0.5 to 0.55 million** | **about 1.3 to 1.6 hours** |

On a Claude subscription there is no per-call charge: it spends plan usage
(30 Opus 5.5 calls of that size may hit a usage window on smaller plans; the
run can be split with `--seats` across windows). The record keeps the cost as
`null`, because the plan has no per-call price. For scale only, at the API
prices in `company/model_profiles.py` ($20 per million output tokens, $4 input,
$5 cache writes) the same batch would be about $11 output plus a few dollars of
input, so roughly $13 to $20. Results land in
`evals/results/<date>-claude-code-claude-opus-5-5/`.

## 8. Laws and tests

- `nirmaan.evals` still names no stage, tool, artifact kind, or role (the M27
  vocabulary test now also reads `records.py`).
- VeriTriage never imports Nirmaan; only `integrations/veritriage.py` imports
  VeriTriage (the prompt digest goes through its `render_parts`).
- No test calls a model. The record, trial, rejudge, and CLI tests use
  `MockLLM`, `ReplayLLM`, and the fake `claude` executable from #57.

`tests/test_nirmaan_live_eval.py`:

- a run record is written with every field, and a fake `claude` run records
  its answers, hashes, model, and tokens;
- re-judging a record reproduces its verdicts, and a changed case is reported;
- Wilson intervals and per case and per seat rates are computed correctly;
- each new case passes with its reference answer and fails with a bad one;
- M42 reads a run record, labelled by source, alongside the synthetic fixtures;
- the scheduled workflow never runs on pull requests and skips without its
  secret;
- crown jewel `test_a_new_seat_group_is_recorded_and_rejudged_with_no_core_changes`:
  a case and a scorer written in the test run with trials, are recorded,
  summarized, shown in history, and re-judged with no core change;
- `spec.check` passes and fails on its own, from data.

## Deferred

- Live runs themselves: the owner runs the batch above; nothing in CI calls a
  model until the secret is added.
- Mutation scoring of a seat's own testbench, and held-out formal proofs.
- Cases for the requirements, microarchitecture, and verification plan seats.
- Grouping M42's rules by model as well as runtime (today a runtime with two
  models in its history is one group; the record keeps the model, so this is a
  rule change, not a data change).

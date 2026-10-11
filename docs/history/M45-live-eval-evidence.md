# Milestone 45 - Live evaluation as recorded, repeatable evidence

The structural review's top risk (section 6, risk 1; recommendation 1): the
AI-quality claim rested on one unrecorded run (#57, Opus 5.5 in the RTL seat,
four cases, once each, outside CI), and M42's proposals had only ever read
synthetic results. Design doc: `docs/LIVE_EVAL_EVIDENCE.md`. No version bump.
No live model was called in this milestone; the owner runs the first batch.

Key design points worth not re-deriving:
- **The run record.** `nirmaan eval run` writes
  `evals/results/<date>-<runtime>-<model>/` for a live runtime (committed) and
  `.nirmaan/evals/...` for a replay (not committed; `--out` overrides): a
  `manifest.json` (`EvalRunManifest`: runtime, model, replay, version, times,
  trials, cases, seats, command), one `<case>/trial-NN.json` per trial
  (`EvalTrial`: the unchanged `EvalResult`, every raw answer as
  `RecordedAnswer` with mode, provider, model, `prompt_sha256` over system NUL
  user, `packet_sha256` over the work prompt's structured fields, text, error,
  tokens; and `JudgeRun`s with tool, run, params, summary), and `summary.json`.
  A record is never overwritten (`-2`, `-3`); the manifest is written first so
  an interrupted run is still readable. Answers are captured by wrapping
  `ModelRuntime.llm` for one trial; nothing about the seat changes.
- **Re-judging** (`nirmaan eval rejudge RECORD`, `evals.rejudge`): the stored
  answers replay in order through `RecordedAnswers` with the clock at the
  trial's recorded start; planning is deterministic, so citation tokens resolve
  again. It compares submitted, seat status, each judge, and `passed`. A changed
  case digest is reported as not comparable without a rerun; running out of
  answers is an error that is not a model call.
- **Trials** (`--trials N`, default 5 with `--runtime`, 1 with `--replay`; a
  warning below 5) and **Wilson** 95% intervals per case and per seat
  (`evals.wilson`, `summarize`, `rate_text`); n is always printed; there is no
  cross-seat headline. `--seats` selects by case group (`rtl`, `spec`,
  `firmware`) or seat stage. `nirmaan eval history` lists records.
- **New cases.** `spec/axi4-lite-interface` (seat `interface-spec`, upstream
  `evals/spec/axi4_lite/requirements.md` tagging eight requirements) is judged
  by the new `AVAILABLE` in-process tool `spec.check`
  (`integrations/spec_check.py`, granted through `interface_specification`):
  every listed `[req:ID]` tagged once with its terms, every port, parameter,
  and register named. `firmware/axi4-lite-driver` (seat `firmware`) is judged
  by `fw.build` of the driver alone and `fw.test` of a held-out test program
  (`evals/firmware/axi4_lite/held_out_test.c`, written to the upstream
  `driver_api.md`) against the approved RTL. The judges fail a spec with a tag
  dropped, unprefixed ports, or DECERR for SLVERR, and a driver with REG2 at
  REG1's offset whose own weak test passes.
- **Gated upstream.** `_fix_upstream` now fixes a stage with before-review
  checks through the unchanged `run_task` with a `ReplayLLM` of the case's
  files (runtime `eval-fixture`), so the firmware case's RTL passed real lint,
  simulation, and synthesis before the fixture approved it.
- **Case loader.** A JSON file with a `format` field (records, checks files)
  is data and is skipped by `load_cases`.
- **M42.** `load_results` reads trial files (skipping manifests and summaries);
  each `EvalRun` has `source` (`record:<id>` or `file`), shown in evidence and
  in `nirmaan learn`; a trial's run ID includes its record and number;
  `--evals` may repeat.
- **Scheduled workflow** `.github/workflows/live-eval.yml`: weekly and manual
  only, never on PRs or pushes; `scripts/live_eval_gate.py` writes
  `enabled=false` without the `CLAUDE_CODE_OAUTH_TOKEN` secret and every later
  step is skipped. With it: EDA tools, Claude Code, the batch, upload, rejudge.
  It never commits.

**The owner's first recorded batch** (repository root, Claude Code signed in
to the plan, EDA tools on PATH):

```
NIRMAAN_CLAUDE_CODE="$(which claude)" nirmaan eval run --runtime claude-code --trials 5 --seats rtl,spec,firmware
```

Six cases, 30 Opus 5.5 calls; estimated from #57 at about 0.5 to 0.55 million
output tokens and 1.3 to 1.6 hours. No per-call charge on a subscription (plan
usage; cost recorded as `null`); about $13 to $20 at API prices for scale.
Results land in `evals/results/<date>-claude-code-claude-opus-5-5/`; then
`nirmaan eval rejudge` on it, `nirmaan learn --evals evals/results`, and commit
the directory in a PR.

`tests/test_nirmaan_live_eval.py` (24 with parameters), crown jewel
`test_a_new_seat_group_is_recorded_and_rejudged_with_no_core_changes`. The M27
tests now list six shipped cases and read the record layout. Tools `AVAILABLE`
went from 35 to 36 (`scripts/status.py --write`).

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
the case IDs and the seats they evaluate, and the command line. Its `purpose`
is `evidence` unless the run was `eval run --purpose calibration` (or `eval
outside`): a calibration record never counts toward a level
(`docs/CAPABILITY_LEVELS.md`).

**A trial** (`EvalTrial`), one per case per trial:

| Field | What it holds |
|---|---|
| `result` | The M27 `EvalResult`, unchanged: case digest, seat status, attempts, the seat's own gate runs, judge scores, `passed`, audit check, and the M31 accounting (model calls, input and output tokens, cost or `null` when unknown). |
| `answers` | Every raw model answer, in order: mode (work or review), provider, model, the SHA-256 of the prompt as sent (system and user parts), the SHA-256 of the work packet the prompt carries (task, sections, citations, outputs, needs, before rendering), the full text, the error if any, and the token counts as reported. |
| `judge_runs` | Every tool run behind a judge verdict: the check it judged, run ID, tool, succeeded, summary, and the parameters it ran with. |
| `model` | The model the answers report (or the runtime's configured model when no answer reported one). |

The claude-code runtime reports the model from Claude Code's `modelUsage`.
Claude Code also makes a small side call on another model (claude-haiku-5-5
today) on every `-p` run and may list it first, so the first key is never taken
on its own: the model asked for (`--model`) is recorded when `modelUsage` names
it; otherwise the one with the most output tokens, and a tie for most is
recorded as every tied model joined with `+` (`answered_by` in
`runtime/claude_code.py`). The token counts are the top-level `usage`, which is
the seat's own call. Before this fix every claude-code trial would have been
recorded as claude-haiku-5-5; the pilot's first live case showed it, and
nothing from that case was committed.

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
- **A committed re-judge (M63).** `--write` also writes `rejudge.json` into
  the record: each trial, same or with its differences. A skill's Practised
  level counts only trials that file shows re-judged clean
  (`docs/CAPABILITY_LEVELS.md`). A trial whose work never reached review has
  no judge run; on a tool-judged case it still counts, as a failure.
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

**A run stops at a trial with no model answer (RR5).** A live `eval run`
stops right after the first trial whose model calls all failed with no
answer: at least one call is recorded, and every recorded answer has no text
and an error. A plan or usage limit looks like this (on 2026-11-15 nine trials
failed in two seconds each, "You've hit your 5-hour limit", because the run
went on), and so does a model that cannot be reached. The rule reads the
trial's structure, never the wording of the error. A model that answers,
however wrongly, never stops a run. The stopped trial is written like any
other and counts as failed (decision 11 of the pilot retrospective); no later
trial starts; the record gets its summary and finished manifest, whose
`trials` stays the planned count. The CLI prints `run stopped: <case> trial
<n> got no model answer, as on a plan or usage limit (<the error>)` and exits
**3** (1 still means a trial failed). Resuming after the limit resets is the
batch plan's matter; the stopped trial is never re-run as a replacement
without a council ruling (council record 2026-11-15-pilot-topup-reruns).
`record_run(stop_on_no_answer=True)` is the
library form; `eval outside` does not set it. The test is
`tests/test_nirmaan_eval_run_stop.py`.

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

## 6. The workflow in GitHub Actions (dispatch only)

`.github/workflows/live-eval.yml` runs only on manual dispatch, never on a
schedule, a pull request or a push. Cases whose seat output is executable code
by design (cocotb tests, firmware) run only here, never on the owner's
machine. One dispatch runs one case with these inputs: `case`, `trials` (1 to
20), `knowledge` (`on`, or `off` for `--without-knowledge`), `purpose`
(`evidence` or `calibration`), `harness` (the `--harness` variant),
`expected_harness` (a `harness_sha256` value) and `replay`.

- **Live trials** (the `live-eval` job) run only from `main`, in the GitHub
  environment `live-eval`, which only `main` may deploy to. Its secret
  `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`, so the run uses the
  owner's plan) is the only credential the job is given, and only the gate step
  and the trials step get it; there is no repository secret. Without it,
  `scripts/live_eval_gate.py` writes `enabled=false` and the job stops before
  anything is installed or spent.
- **The tools** come from `.github/actions/live-eval-setup`: the EDA tools,
  SymbiYosys and Yices from the pinned OSS CAD Suite, Claude Code from
  `.github/live-eval` (version 2.1.325, each package checked against the sha512
  in its lockfile by `npm ci`), and the package with the `cocotb` extra.
- **The fingerprint**: `scripts/live_eval_ci.py check` prints the
  `harness_sha256` the trials will run in, from the installed CLI's version,
  and refuses a CLI other than the pin or a fingerprint other than
  `expected_harness`. No trial runs on a mismatch.
- **The trials**: `scripts/live_eval_ci.py trials` runs `nirmaan eval run
  <case> --trials 1` once per trial, in order, so each trial is its own record.
  It stops at once on exit 3 (a trial with no model answer, as on a plan or
  usage limit) or a limit line in the output, on any exit other than 0 or 1,
  and when a record's purpose, knowledge label, harness variant, fingerprint or
  CLI is not what was asked for. A stopped or failed trial stays as it is and
  is never run again; no later trial of the dispatch starts. One dispatch runs
  at a time (the `live-eval` concurrency group).
- **Seat code runs as an account of its own** (gates WF9 and WF17 of the G3
  council record, `council/records/2026-11-17-g3-whole-flow-cases.md`). The
  runner user has passwordless sudo, owns the checkout, the installed package
  and the records, and its `nirmaan` process holds the token, which any process
  of the same user can read in `/proc/<pid>/environ`. A cocotb test module is
  code by design and runs inside `vvp`. So every job first runs
  `.github/actions/live-eval-seat` (`scripts/live_eval_seat.py`): it makes the
  account `nirmaan-seat` (no password, no sudo rule, no group but its own) and
  puts a `vvp` first on `PATH` that runs the real one as that account, with
  `no_new_privs` (no setuid program, sudo included, gives it more), an
  environment holding only cocotb's own settings, and write access to the
  run's own directory only. When the run ends, every process of the account is
  killed, what it made in the run's directory goes back to the runner (a link,
  pipe or other non-regular file it made there is removed first), every grant
  is taken back, and what it left in `/tmp`, `/var/tmp` and `/dev/shm` is
  removed. The account has no read access to the runner's home, the checkout
  and the runner's temporary folder (an ACL entry with no permission, whatever
  their modes allow), and no network: its TCP connections are refused at once
  with an ICMP "prohibited" answer and its other packets are dropped
  (`owner` rules first in `OUTPUT`, IPv4 and IPv6). The reach test of
  [run 44553476118](https://github.com/nirmaansoftware/ip-nirmaan/actions/runs/44553476118),
  before either, recorded every read denied (by the home folder's own mode)
  and the network open: `REACH NOT DENIED` on TCP to 1.1.1.1 port 443
  (connected), TCP to 127.0.0.1 port 9 (refused by the closed port, so
  reached) and UDP to 127.0.0.53 port 53 (sent). The replay job of
  [run 44555981466](https://github.com/nirmaansoftware/ip-nirmaan/actions/runs/44555981466)
  shows every probe denied: 130 files not read, 4 folders not listed, both
  read canaries denied, TCP refused (errno 113) and UDP refused (errno 1), and
  IPv6 with no route (errno 101). Since a TCP probe of `::1` was added, which
  has a route, the IPv6 rule itself is shown: the replay job of
  [run 44563164453](https://github.com/nirmaansoftware/ip-nirmaan/actions/runs/44563164453)
  records it refused (errno 13), with every other probe denied as before. The hosted runner's tool cache (the Python the package is installed
  in, with its `site-packages` and console scripts) and its global
  `node_modules` (npm) are writable by every account on the hosted runner.
  Two replays of this change, before the action took that away, recorded it
  in their reach tests: [run 44325101430](https://github.com/nirmaansoftware/ip-nirmaan/actions/runs/44325101430)
  (`REACH NOT DENIED` on `site-packages`, the Python's `bin`, cocotb, the
  editable install's `_editable_impl_ip_nirmaan.pth` and the `nirmaan`
  console script) and [run 44326711465](https://github.com/nirmaansoftware/ip-nirmaan/actions/runs/44326711465)
  (`REACH NOT DENIED` on `/usr/local/lib/node_modules/npm/bin/npm-cli.js`).
  The action now takes other accounts' write access from both trees and from
  every folder on `PATH`, and the reach test of
  [run 44327170136](https://github.com/nirmaansoftware/ip-nirmaan/actions/runs/44327170136)
  shows every one denied. The harness code
  is unchanged: the wrapper is `/opt/nirmaan-seat/bin/vvp`, first on `PATH`,
  and a tool run's own result file names it among its `executables`.
- **The reach test** (`scripts/live_eval_reach.py`) runs in every job that runs
  seat code, before any trial or re-judge, through the real path: a cocotb
  test module run by `simulator.run`'s cocotb backend, so through the same
  `vvp`. Its tests try, as the seat account, to run as the runner or in another
  group; to run `sudo -n` as root or as the runner; to write to the checkout,
  the installed package, every folder on `PATH`, every program a gate runs,
  the account's own wrapper, the records folder, the runner's temporary folder
  and the step's command files (`GITHUB_ENV`, `GITHUB_OUTPUT`, `GITHUB_PATH`,
  `GITHUB_STEP_SUMMARY`); to find either of two canary values the test puts in
  the harness's environment (one under a credential's name, one under a plain
  name) in its own environment or in any process's `/proc/<pid>/environ`, or
  to read a file only the runner may read; to signal the harness; to read
  what the judge keeps from the seat (READ probes: every reference answer,
  held-out case file and mutant the eval cases name, all in the checkout, a
  canary file the test writes, readable by every account by its mode, into
  the checkout and into the runner's temporary folder, and a listing of the
  checkout, its `.git`, the runner's home and its temporary folder); and to
  reach the network (TCP out over IPv4 and IPv6, TCP on the loopback address
  over IPv4 and IPv6,
  and a UDP packet to the local name server). A canary value in the run's log
  or results fails it too. A last
  test, the control, writes the run's own directory. Each target must exist
  first, so a refusal proves something. The job fails before any trial unless
  cocotb's verdict is a pass with every probe test in its results.
- **Seat C runs as the account too (M90).** `fw.test` runs the program it
  builds (the seat's C linked with the harness and the Verilated model) by
  path, not through `PATH`, so it has a wrapper of its own:
  `/opt/nirmaan-seat/bin/nirmaan-seat-exec`, root's, made by the same action.
  Where it is on `PATH`, `fw.test`'s last step runs the program through it
  (`nirmaan.integrations.firmware.SEAT_EXEC`), in a new folder `seat` inside
  the run's directory: as `nirmaan-seat`, with `no_new_privs`, an empty
  environment, write access to that folder only (the run's directory, which
  holds the requirements file and the log the harness reads, is not
  writable), and the same cleanup. The program must be a regular file the
  runner built in the same run directory, reached through no link, not
  writable by others and not set-id. A run killed by a signal ends the
  wrapper by the same signal, so `fw.test` reports it as it would without the
  account. Elsewhere (the owner's machine, CI's test job) there is no wrapper
  and nothing changes. In the live evaluation's jobs (`replay`, `live-eval`,
  `rejudge`) the workflow names the wrapper (`NIRMAAN_SEAT_EXEC`), and there
  `fw.test` never falls back (gate SC2 of
  `council/records/2026-11-19-seat-c-live-refusal.md`): a wrapper that is not
  there, not root's, or writable by another account refuses every `fw.test`
  run before anything is compiled, so each run of each of up to 20 trials
  uses it, not only the credential test's run at the start of the job. The
  trials step also reads that job's credential test record (`FW_REACH`) and
  exits 6 on a missing record, one of another run or job, one not written in
  gate mode, or one with a probe not denied (gate SC4); with a record that
  counts it still exits 6, for the refusal below. The compile and link steps of `fw.build` and `fw.test`
  still run the compiler as the runner over the seat's C; they run none of it.
  Other backends build or run host code over seat files, and none of them runs
  seat-written host code: `regmap.verify` builds a test the harness generates
  from the seat's register map (`nirmaan.regmap.c_test`, after `validate`),
  and the seat's RTL reaches its Verilator model only as HDL; `fw.soc_test`
  cross-builds the seat's firmware for RV32I and runs it inside the simulated
  PicoRV32, freestanding, with no host call (G3 record, second addendum, fact
  8), and no case today uses it; the Verilator `--binary` simulator compiles
  seat HDL, and every gate refuses, before it runs, HDL with a way out to
  the host: a system task outside an allow list (so `$system`, `$fopen` and
  `$c`), DPI, or a `` `systemc_ `` block (`eda_guard.verilog_uses`;
  `docs/GATE_INPUTS.md`, section 2). Those runs stay with the runner account,
  as before; if a case ever hands one of them seat-written host code, it joins
  `SEAT_C_TOOLS` in `scripts/live_eval_ci.py`. `check
  --require-expected` and `trials` refuse a case that runs seat C (one whose
  seat is `firmware`, whose held-out checks use `fw.build` or `fw.test`, or a
  whole flow with a `firmware` stage) with exit 6 before any trial. Since
  M90 seat C executes as the seat account and is compiled as the runner; that
  does not lift this refusal. The council record `council/records/2026-11-19-seat-c-live-refusal.md` keeps it, and sets
  gates SC1 to SC7 for a lift of the single-seat case in a pull request of its
  own; the register block flow also waits for gates WF15 to WF19 of the G3
  council record. A replay of such a case still runs: its code is the
  reference answer.
- **The compile residual, and the compile screen** (M91, gate SC1 of
  `council/records/2026-11-19-seat-c-live-refusal.md`, fact 9 and decision 4).
  Seat C executes as the seat account, but `fw.build` and `fw.test` compile
  and assemble it as the runner. The record found (compiled locally, not in
  CI) that seat files including the committed reference driver by an
  absolute or `..` path compile clean, and so does a top-level asm line that
  makes the assembler copy a file into the object. Since M91, before anything
  of a job is compiled, every backend that compiles its C refuses `#line` and
  line markers, an include written with an absolute or `..` path, a file the
  compiler pulls in from outside the run's folders and its own include
  folders, and an asm statement or a file-reading assembler directive in the
  compiler's assembly; each route is recorded refused in CI
  (`docs/COMPILE_SCREEN.md`). The re-judge goes through the same backends, so
  it refuses such stored seat C too. What stays, as that document lists: the
  screen's own preprocessor opens what the seat names before the list is
  checked (only file names come back); a seat header can break the held-out
  test's own compile so that a diagnostic quotes its lines (inference); the
  program `fw.test` builds holds the held-out test it is linked with; and the
  M53 redaction replaces only the exact value of a credential-named variable
  (fact). The live refusal above stays until gate SC7.
- **The credential test for seat C** (`scripts/live_eval_fw_reach.py`, G3
  record, decision 4 and second addendum, decision 2, item 1) runs in the
  `replay`, `live-eval` and `rejudge` jobs of a whole-flow or firmware case,
  after the reach test and before the checkout is hashed. It runs a C driver test through `fw.test`
  under a parent holding two canaries in its real environment and records
  whether that C can run as the runner or in another group, run `sudo -n`,
  write the checkout, the package, the records folder or any other target of
  the reach test above, read any process's environment or a runner-only file,
  or signal the harness; and (gate SC6) read the reach test's read targets
  (every reference answer, held-out case file and mutant, two canary files
  readable by every account by their mode, listings of the checkout, its
  `.git`, the runner's home and its temporary folder) or reach its network
  targets. Reading files every account may read outside those targets is not
  probed. Since M90 the workflow runs it with
  `--require-denied`: the job stops unless every probe is denied and
  `fw.test` found its wrapper. Gate WF17 covers every job that runs seat
  code, so every step that runs seat code of a case that runs seat C (the
  replay, the re-judge) first runs `scripts/live_eval_ci.py confined`, which
  stops it with exit 6 unless that job's own record (written with
  `--require-denied`, of that run, attempt, job and commit) shows every
  probe denied, so seat C never executes after a skipped or failed credential
  test. Before M90 it only
  recorded; that result
  (run 44401041085, as the runner) was every probe not denied, the parent's
  environment with the credential-named canary in it readable. Its record is
  `evals/flow/credential_test_record.json`.
- **The judge fails a wrong driver as the seat account** (gate SC5). The
  `replay` job of `firmware/axi4-lite-driver` runs
  `scripts/live_eval_fw_broken.py --require-seat`: the four committed broken
  fixtures (the wrong map header, and the swallowed-error, all-strobes and
  sticky-response drivers) and the reference driver, each through every
  held-out check of the case, every `fw.test` run through the wrapper. The job
  fails unless the reference passes every check and each fixture fails one by
  a run that ran. The result is uploaded with the credential test's record.
- **Whole-flow cases** (`docs/WHOLE_FLOW.md`, "The CI path") run in these
  jobs when named: one trial per dispatch, on the default harness, in the
  whole-flow fingerprint, each record checked for `flow: whole`; a `flow/`
  case adds the RISC-V cross compiler and requires every tool.
- **The checkout is hashed** before and after the trials
  (`scripts/live_eval_ci.py tree`): the commit, then every file git tracks or
  would add, and every file under `src/`, `scripts/` and `evals/` (ignored
  files included), by path, type, mode and content. Bytecode is not written
  (`PYTHONDONTWRITEBYTECODE`). On any change the job fails and prints the
  difference.
- **The records** are uploaded as a workflow artifact. Nothing here commits:
  the records are downloaded and committed by pull request like any other
  evidence.
- **The counting re-judge** runs in the `rejudge` job, which ran no seat code
  before it. It refuses the records unless the trial job hashed its checkout
  after the trials with the same result as before and ran this run's commit.
  It then checks out that commit afresh, installs the tools, makes the seat
  account, downloads the records (the artifact is the only way they reach it),
  runs the reach test with the records folder as its target, and for a
  whole-flow or firmware case the credential test for seat C (since M90),
  hashes the checkout, runs `nirmaan eval rejudge <record>
  --write` on every record after `live_eval_ci.py confined`, and hashes the
  checkout again. Re-judging replays the recorded answers through the real
  gates, so seat code runs again there, as the seat account. Any difference,
  a changed checkout or a failed reach or credential test fails the job.
  **The council's reading of WF17** (`council/records/2026-11-19-seat-c-live-refusal.md`, decision 3). The G3 record
  asks that "the re-judge that counts runs in a job that ran no seat code".
  Re-judging replays the recorded answers through the real gates, so the
  council reads the gate as: the job ran no seat code before the re-judge;
  the seat code the re-judge itself runs executes as the seat account, after
  that job's own reach and credential tests showed every probe denied,
  between two hashes of its checkout; seat C is compiled as the runner. A
  re-judge compiles stored seat C the way the trial did; since gate SC1 (the
  compile screen, M91) both refuse an include of a file outside the run's
  folders before anything is compiled, so an included reference answer is
  refused, not repeated. The
  re-judged records, each with its `rejudge.json`, are uploaded as
  `live-eval-rejudged-<run id>`; that is the re-judge a record is committed
  with.
- **A replay** (`replay: true`, the `replay` job) runs the case's reference
  answer with no model, no token and no environment, from any branch, and
  prints the fingerprint. It goes through the same account, reach test, tree
  hashes and `rejudge` job, so it checks the tools and the whole path before
  trials are spent.

To enable live trials: create the `live-eval` environment, allow only `main`
to deploy to it, and add the environment secret `CLAUDE_CODE_OAUTH_TOKEN`. To
disable them: delete the secret.

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
nirmaan eval rejudge evals/results/<the new directory> --write
python scripts/capability_levels.py --write
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
- `tests/test_nirmaan_claude_code.py`: with a side call listed first in
  `modelUsage`, the model asked for is recorded, on a reply and on a failed
  call; without it, the model that wrote most, a tie as every tied model, and
  with nothing reported, the model asked for;
- re-judging a record reproduces its verdicts, and a changed case is reported;
- Wilson intervals and per case and per seat rates are computed correctly;
- each new case passes with its reference answer and fails with a bad one;
- M42 reads a run record, labelled by source, alongside the synthetic fixtures;
- the workflow runs only on dispatch, gives the token only to two steps of
  a job that runs from `main` in the `live-eval` environment, and stops
  without its secret; its trials run one at a time and stop on a limit, an
  odd exit or a record that is not the trial asked for, and none runs again
  (`tests/test_live_eval_ci.py`);
- gate WF17: every trial job makes the seat account and runs the reach test
  before the trials, between two tree hashes; the counting re-judge is a job of
  its own, on a fresh checkout of the trial job's commit, from the artifact
  only; the seat's environment keeps cocotb's settings and nothing else; a run
  directory must be one the harness made in `/tmp`; links the seat made there
  are removed; the tree hash sees an edit, a new file, a mode, a deletion, a
  link and a bytecode file; a live trial of a case that runs seat C is refused
  before any trial (`tests/test_live_eval_seat.py`,
  `tests/test_live_eval_ci.py`). What the account denies is shown only by the
  reach test in Actions, where the account exists;
- whole-flow cases: known only when named, one trial per dispatch on the
  default harness, checked in the whole-flow fingerprint and for the
  `flow: whole` label; the register block flow refused live and the timer
  flow not; the RISC-V compiler and every tool required for a `flow/` case;
  the credential test for seat C compiles as `fw.test` compiles a driver test,
  counts a probe denied only when every line of it is and never when it is
  missing, and fails only in its gate mode (`tests/test_live_eval_ci.py`,
  `tests/test_nirmaan_live_eval.py`). It runs only in Actions;
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

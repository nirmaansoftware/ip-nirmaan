# Test and CI hardening (M46)

The principal-engineer review found two test defects, duplicated test helpers,
and a CI that downloaded a 745 MB tarball uncached twice per run and ran the
full real-EDA suite twice (sections 4.2, 5.2, 5.3; risks 5 and 6;
recommendations 4 and 6). M46 fixes the tests, consolidates the helpers, adds
a job that keeps "skips when absent" true, and hardens the workflow. It adds
no product behavior.

## 1. The two test defects

**Unguarded fixtures.** With `PATH=/usr/bin:/bin`, 21 tests errored instead of
skipping: 15 in `tests/test_nirmaan_export.py` (fixture `midway`) and 6 in
`tests/test_nirmaan_records.py` (fixture `decided`). Both fixtures call
`drive`, which since M38 runs real lint on gated RTL work, so the broker
refused with `ToolAccessDenied` ("verilator-lint needs verilator on PATH").
Each test that takes one of those fixtures now carries `@needs(*GATE_TOOLS)`.
A pytest mark on a fixture has no effect, so the mark goes on the tests.
Without the tools they skip; with `NIRMAAN_REQUIRE_EDA` naming a tool they run,
and they fail if the tool is missing.

**Terminal width.** `test_the_cli_imports_and_exports` failed when the temp
path was long. rich sizes a console from `COLUMNS` or the terminal (else 80)
when the console is built, and wraps output to fit. The vplan error line is
`<path>: line 3: ...`, so for some path lengths "line" and "3:" landed on
different lines. A session fixture in `tests/conftest.py` now sets the four
CLI consoles (`nirmaan.cli` and `veritriage.cli.main`, stdout and stderr) to
1000 columns, so no CLI assertion depends on the terminal or the path. The
regression test `test_cli_output_does_not_depend_on_the_path_length` walks
every wrap position of an 80-column console (80 path lengths). It failed
before the fix and passes after it. Setting `COLUMNS` for the whole process
was rejected because pytest's own progress output then spreads over 1000
columns.

## 2. One copy of each helper

`tests/laws.py` holds the helpers that the laws share:

- **`imports(path)`.** Every module a file imports, plus `module.name` for
  each `from module import name`, read from the AST. It replaces 14
  `_imports()` copies. Five copies listed modules only. Every caller checks
  prefixes ("no import starts with `veritriage.`"), and `module.name` starts
  with a prefix exactly when `module` does, so the extra entries change no
  outcome.
- **`needs(*executables, any_of=())`.** It replaces 9 `needs()` copies,
  `_needs` in the export tests, and the RISC-V variant
  (`needs(riscv=True)` is now `needs(any_of=RISCV_GCC)`).

Test modules import both from `laws`, not from each other.
`tests/test_laws.py` fails if any other test module defines `_imports`,
`imports`, `needs`, or `_needs`, and pins the `needs` contract: skip when
missing, run (and so fail) when required, and treat `any_of` as one tool named
by its first entry.

## 3. The jobs

| Job | Python | Tools | Runs | Purpose |
|---|---|---|---|---|
| `test` | 3.12 | apt Verilator, Icarus, Yosys, RISC-V GCC; OSS CAD Suite `sby`, Yices | whole suite, tools required | the real-EDA gate |
| `no-tools` | 3.11 | none, and no `anthropic` SDK | whole suite | every test passes or skips, none errors; the missing-SDK test runs |
| `physical-design` | 3.12 | pinned ORFS image | PD and STA tests | unchanged, apart from pins, caches, and a JUnit report |
| `test-union` | system | none | `scripts/check_test_union.py` | fails if a test was skipped in every job |
| `dashes` | 3.12 | none | `scripts/check_dashes.py` | unchanged, pinned to ubuntu-24.04 |

**Nothing disappears.** The real-EDA suite now runs once, and 3.11 runs only
what needs no tool, so a test could in principle skip everywhere. Each test
job writes a JUnit report, and `test-union` reads all three. It fails and
names any test that no job ran. On the first run every test ran somewhere:
`test_missing_sdk_raises_clean_error` skips in `test` and runs in `no-tools`,
and the openroad and klayout tests skip in `test` and run in `physical-design`.
`no-tools` also checks first that no EDA tool is on PATH and that `anthropic`
is not importable, so it cannot pass vacuously. `cc` and `make` are part of
the runner image, so tests that need only those run there.

## 4. Caching and pinning

- **OSS CAD Suite.** The local composite action `.github/actions/oss-cad-suite`
  caches the tarball under a key holding the release and a sha256 prefix. On a
  miss it downloads with `curl --retry 5 --retry-all-errors`. It checks the
  sha256 on every use, cached or not, then unpacks and puts only the named
  tools on PATH as wrappers, exactly as before. `test` wraps `sby yices-smt2`
  and `physical-design` wraps `verilator iverilog vvp`. The cache path is the
  fixed `/tmp/oss-cad-suite.tgz` in both jobs, but actions/cache still keeps
  a separate entry for the container job (about 715 MB each, of the 10 GB
  repository cache). Caches made on a PR branch are not visible to `main`, so
  the first run on `main` after a merge fetches once. To bump the release, change the URL, the key, and the
  sha256 in that one file.
- **pip and uv.** `setup-python` caches pip (keyed on `pyproject.toml`), and
  `setup-uv` caches uv in the PD job.
- **Pins.** Every action is pinned by full commit SHA, with the release in a
  comment (`@11d5960... # v4.4.0`). Every runner is `ubuntu-24.04`.
  `tests/test_ci.py` enforces both and reads every YAML file under `.github/`.
- **Concurrency.** `cancel-in-progress` is on for pull requests only. A newer
  push to a PR cancels the older run; runs on `main` always finish.
- **Left as is.** `apt-get update` still runs in `test`. Caching apt packages
  is fragile, and taking Verilator, Icarus, and Yosys from the CAD Suite would
  change tool versions under the whole suite, so that is a separate decision.

## 5. CI time

Measured from the GitHub API (job start to job end, queue time excluded).
"Before" is the mean of the last 10 successful CI runs before M46 (5 pushes to
`main` and 5 pull requests, ending at be26485). "After" is this PR's two runs.

| | Wall (first job start to last job end) | Job time summed |
|---|---|---|
| Before (10 runs) | 520 s (8.7 min) | 1302 s (21.7 min) |
| After, cold cache (run 38081906567) | 575 s (9.6 min) | 1041 s (17.4 min) |
| After, warm cache (run 38082661168) | 577 s (9.6 min) | 1142 s (19.0 min) |

Job time fell by 12 to 20 percent: the second full real-EDA run (5 to 9
minutes) became a 2.5 minute `no-tools` run. Wall time did not fall. It is
bounded by the single real-EDA `pytest` run in `test`, whose Test step took
277 to 571 s across the 10 baseline runs and 500 and 517 s in the two runs
here, so the difference is within runner variance. The cached tarball
restores in 20 to 30 s, about what the download took, so caching buys
reliability (no repeat of run 37923805038's "tar: Error is not recoverable"),
not speed. Shortening the wall time would mean splitting the real-EDA suite
across runners or adding pytest-xdist. Both are deferred, because the suite's
module-level registries (M36) are not yet proven safe under xdist.

## 6. Required checks: the owner's call

M46 creates no ruleset and no branch protection. To require the checks on
`main`, the owner can run:

```
gh api -X POST repos/nirmaansoftware/ip-nirmaan/rulesets --input - <<'JSON'
{
  "name": "main: required checks",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": false,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": false}},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": false,
      "required_status_checks": [
        {"context": "test", "integration_id": 15368},
        {"context": "no-tools", "integration_id": 15368},
        {"context": "physical-design", "integration_id": 15368},
        {"context": "test-union", "integration_id": 15368},
        {"context": "dashes", "integration_id": 15368}]}}
  ]
}
JSON
```

Or, in the web UI: Settings, Rules, Rulesets, New branch ruleset. Set the
target to the default branch and turn on "Restrict deletions", "Block force
pushes", "Require a pull request before merging" (0 approvals, since the
owner merges alone), and "Require status checks to pass" with the five checks
above, each from GitHub Actions. Leave the bypass list empty, or add the
repository admin role if the owner wants an emergency override. If a later
milestone renames a job or adds one (M44, M45), update the list to match:
a required check that never reports blocks every merge.

## 7. Permissions and timeouts (2026-10-17)

Added after M46, as rollout step R2 of the council record
`council/records/2026-10-17-teams-and-pr-review.md`, before any review status
can be required:

- **Read-only token.** Every workflow declares `permissions: contents: read` at
  the top. `live-eval.yml` already did; `ci.yml` had no block, so its token had
  the repository's default scope. A step that a pull request adds can no
  longer post a commit status, comment or push with the workflow token.
- **Timeouts.** Every job sets `timeout-minutes` (the default is six hours).
  The ten most recent successful CI runs took at most 779 s (`test`), 117 s
  (`no-tools`), 794 s (`physical-design`), 8 s (`test-union`) and 8 s
  (`dashes`). The limits are 45, 20, 60, 10 and 10 minutes, room for a cold
  cache (the standalone OpenSTA build) and a slow runner. `live-eval` keeps
  300.
- **Tests** (`tests/test_ci.py`): every workflow has exactly that top-level
  block and no write permission; every job has a timeout; no file under
  `.github/` uses `pull_request_target` or expands `github.event.*` or
  `github.head_ref` inside `run:`; container images are pinned by digest;
  the five required jobs run on every pull request with no path or branch
  filter and no job-level `if:` other than `always()` (section 8). A synthetic bad workflow proves each check
  fires. Action pinning by SHA was already tested (section 4).

Not done here: moving a plan token secret to an environment only `main` can
use. The repository has no Actions secret today (`CLAUDE_CODE_OAUTH_TOKEN` is
not set), so the live evaluation stays off; creating the secret and the
environment is the owner's account action.

## 8. Shards (2026-10-18)

Wall time was bounded by two single `pytest` runs: the Test step of `test`
(448 and 728 s of test time in runs 39133510901 and 39132163503) and of
`physical-design` (465 and 545 s), with whole runs of 8 to 14 minutes. Both
jobs now run as shards on separate runners, so section 5's deferral of
splitting the suite across runners is closed (pytest-xdist is still not used,
so no two tests share a process they did not share before):

- `test-shard` runs as three shards (`test (shard K/3)`) and
  `physical-design-shard` as two (`physical-design (shard K/2)`), with the
  same tools, Python, environment and `NIRMAAN_REQUIRE_EDA` as before.
  `pytest --shard K/N` (`tests/conftest.py`) keeps whole test files, so a
  module fixture or a file's own order is never split. `scripts/shards.py`
  places files heaviest first on the least loaded shard, by the seconds per
  file in `scripts/shard_weights.json` (measured from the two runs above; an
  unlisted file counts 0.5 s). The weights only balance the shards: every
  shard collects the same tests and computes the same split, so a stale
  number never drops or repeats a test.
- The jobs `test` and `physical-design` keep the required names. Each needs
  its shards, runs with `if: always()` (a job skipped after a failed
  dependency reports as passing, so it would not block a merge), and fails
  unless every shard succeeded and `python3 scripts/shards.py` confirms from
  the shards' manifests that they came from one collection, named every
  shard once, and together kept every collected test exactly once.
- `test-union` is unchanged: it reads every shard's JUnit report
  (`junit-test-K`, `junit-physical-design-K`) with `no-tools`.
- **Tests** (`tests/test_ci.py`): the split keeps whole files, covers the suite
  exactly once for one to four shards and is the same whatever the input
  order; the check fails on a missing, repeated or disagreeing shard; a real
  `pytest --collect-only --shard` run splits two files exactly and rejects a
  bad `--shard`; the workflow's shard counts, profiles, artifact names and
  aggregate jobs agree.

## 8. CI wall time (2026-11-19)

Measured over the last 30 pull request CI runs, the wall time is set by the three
`test (shard K/3)` jobs (median 14 to 19 minutes, worst 37), not by the other jobs
(`no-tools` 4 minutes, `physical-design` shards 6 minutes, the aggregate jobs 10
seconds). Two things made them slow, and neither tests less:

- **apt download.** The Ubuntu mirror is sometimes throttled to about 70 kB/s, so
  the same 84 MB install took up to 25 minutes (median 4). The downloaded `.deb`
  files are now cached by ISO week (`apt-eda-noble-<week>`), copied into apt's
  archive before `apt-get install`, and apt still resolves versions from a fresh
  index. The tool set and versions are unchanged.
- **Shard balance.** `scripts/shard_weights.json` listed 60 files (575 s) for a suite
  that takes about 1630 s, so the unlisted files counted 0.5 s each and the shards
  ran 745, 481 and 402 s of tests. The weights are regenerated from three recent
  JUnit reports; the split is now 544, 542 and 543 s. Same shard count and names.

Not changed, and why: the physical-design jobs cannot start only on relevant paths,
because `test-union` reads their reports to prove every test ran, and a required
check that does not report blocks the merge; they run in parallel with the test
shards, so they are not on the critical path.

### Four test shards (2026-11-19)

The balance above did not last. The flow testbench copies grew (the timer copy to 44,959
checks, the register block to 8,357), so the same suite went from about 1630 s to 2030 s of
tests (CI run 44460935888, main at 7d1cb0e), and the old weights, which did not know the new
costs, left shard 1/3 at 24.5 minutes on one pull request run against 11 for shard 2/3. Same
fix as before, with one more shard, and nothing is tested less:

- `scripts/shard_weights.json` is regenerated from that run's JUnit reports (the three test
  shards and the two physical-design shards). The biggest changes: `test_whole_flow_cases.py`
  100 to 154 s, `test_whole_flow_controls.py` 133 to 197 s, `test_nirmaan_factory_e2e.py` 91 to 137 s.
- `test-shard` runs as four shards (`test (shard K/4)`). Three balanced shards would still keep
  about 680 s of tests each (over 11 minutes, before the 3 to 4 minute setup); four keep
  about 510 s each. The required check names are unchanged: the branch ruleset requires
  `test`, `no-tools`, `physical-design`, `test-union`, `dashes` and the two review contexts,
  never an individual shard, so no required name is dropped or added. `test` still fails
  unless all four shards passed and `scripts/shards.py` finds they kept every collected
  test exactly once, and `test-union` reads all four JUnit reports (`junit-test-*`).
- No file or test dominates: the largest file is `test_seat_tools.py` (253 s, an eighth of the
  suite) and the largest single test is the per-tag mutant sweep (153 s), both well under one
  shard's 510 s, so the split stays by whole file and no test is moved to its own job.
- The review loop's own local run of `test` keeps its three shards (`scripts/pr_loop.py`, one
  machine); it reads the same weights.

## 9. Verilator build jobs in the loop's check (2026-11-19)

The review loop runs its `test` check as up to three shards at once, on the machine that also
runs reviews (`scripts/pr_loop.py`, `LOOP["checks"]`). A Verilator build given `-j 0` starts one
job per core, so three shards that each build a Verilator model at the same moment start three
jobs per core. The check's environment sets `NIRMAAN_VERILATOR_JOBS=2`, and the builds that read
it (`simulator.run`'s Verilator backend, coverage and `fw.soc_test`;
`nirmaan.integrations.eda.verilator_jobs`) start at most two jobs each. Unset, as in CI's own test
jobs and on a developer's machine, it is `-j 0` as before. `fw.test`'s co-simulation build keeps
`-j 0`: gate WF14's guard pins its options word for word (`tests/test_nirmaan_firmware_reach.py`).
Since section 10 every Verilator model build, `fw.test`'s co-simulation build included (the one `regmap.verify`
uses too), also passes `--verilate-jobs 1`; the `make` jobs stay as this section says, and the co-simulation build
still passes `-j 0`.

## 10. Verilator verilates on one thread (2026-11-23)

Verilator 5.020, the one Ubuntu 24.04 installs (CI's test jobs, and the live evaluation's jobs: `5.020-1` in
`evals/plans/2026-11-23-w2-remeasure.md`, section 5, from run 45073595509), can abort as it exits
with "Internal Error: attempted to destroy locked Thread Pool" when it verilated on more than one thread: a race in
the teardown of its own thread pool (verilator/verilator#4931, closed upstream on 2024-03-01, after 5.020's release;
which release first carries the fix is not checked here). `-j N` sets both the `make` jobs of a build and Verilator's
verilation threads, so `-j 0` gave every build one verilation thread per core. The `verilator` script then exits 255
and the build fails, though nothing in the design or the test is wrong. CI's test shards have hit it; the pull
request that added this section names the runs it found.

Every Verilator model build now passes `--verilate-jobs 1`. There are four, and `tests/test_nirmaan_eda.py` checks
that each passes it: `simulator.run`'s Verilator backend and `coverage.read` (`eda.py`), `fw.test`'s co-simulation
build (`firmware.py`; `regmap.verify` runs the same build) and `fw.soc_test` (`firmware_riscv.py`). The `make` jobs
stay as `-j` says (`NIRMAAN_VERILATOR_JOBS`, section 9). A lint passes no `-j` and already verilated on one thread.

That the abort no longer happens is an inference, not a measurement: from Verilator 5.020's source (open, the
thread pool in `src/V3ThreadPool.cpp`), with one verilation thread it starts no worker thread and leaves its locks
off, so the teardown race should not arise. No run can show that it is gone.

`fw.test`'s build is the one whose option list gate WF14's guard pins (`tests/test_nirmaan_firmware_reach.py`), so
the guard's list gained the same two words, and before it merged the guard's return condition is checked as gate ET20 of
`council/records/2026-11-22-eda-tools-seat-account.md` (third addendum, decision V1) asks: the guard passes, the
simulator-clock probe gives the counts it is recorded with, the wait probe and the strict fixtures of gate WF15 give
their recorded results, and, on the Verilator CI installs, for both registered buses, the co-simulation image has
the same external symbols with and without the two words (the guard file's
`test_the_cosim_images_external_symbols_are_the_same_with_and_without_verilate_jobs`). The pull request names the
CI run and job of each. No record of gate ET5 was made on a build with these words, and none covers one.

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
"Before" is the mean of the last 10 successful runs on `main` (be26485 and
the nine before it). "After" is this PR's runs.

| | Wall (first job start to last job end) | Job time summed |
|---|---|---|
| Before (10 runs) | 520 s (8.7 min) | 1302 s (21.7 min) |
| After, cold cache | 575 s (9.6 min) | 1041 s (17.4 min) |
| After, warm cache (run 38081906567's successor) | measured next | measured next |

AFTER_NOTE

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

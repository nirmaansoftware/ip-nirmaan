# Milestone 46 - Test guards, one copy of each test helper, and a hardened CI

From the principal-engineer review (sections 4.2, 5.2, 5.3; risks 5 and 6;
recommendations 4 and 6). It adds no product behavior. Design:
`docs/TEST_CI_HARDENING.md`.

**Two test defects, reproduced and fixed.** With `PATH=/usr/bin:/bin`, 21
tests errored with `ToolAccessDenied` instead of skipping (reproduced: 8
passed, 1 skipped, 21 errors over the two files). The export fixture `midway`
(15 tests) and the records fixture `decided` (6) drive gated RTL work, so real
lint runs. Those tests now carry `@needs(*GATE_TOOLS)`; the same run gives 8
passed, 22 skipped. The vplan CLI test failed when the temp path was long,
because rich wrapped "line 3:" at 80 columns (reproduced with three basetemp
lengths). A session fixture now fixes the CLI consoles at 1000 columns, and a
new test walks all 80 wrap positions; it failed before the fix.

**One copy of each helper.** `tests/laws.py` holds `imports()` (it replaces
14 `_imports()` copies) and `needs()` (9 copies, `_needs`, and the RISC-V
variant, now `needs(any_of=RISCV_GCC)`). Behavior is unchanged: every import
law checks prefixes, which the extra `module.name` entries cannot change.
`tests/test_laws.py` fails if a copy comes back.

**CI.**
- `test` runs the real-EDA suite once, on Python 3.12.
- The new `no-tools` job runs the whole suite on 3.11 with no EDA tool and no
  `anthropic`. On its first run: 1373 ran, 263 skipped, 0 errors. That
  includes `test_missing_sdk_raises_clean_error`, which no CI job had run
  before.
- The new `test-union` job reads the three JUnit reports and fails if a test
  ran in no job. On its first run every one of the 1636 tests ran somewhere.
- The OSS CAD Suite comes from a local composite action: cached by version,
  fetched with retries on a miss, and checked by sha256 on every use. It
  replaces two uncached downloads per run.
- pip and uv caches; every action pinned by commit SHA with its version;
  `dashes` on ubuntu-24.04; `cancel-in-progress` for pull requests.
- `tests/test_ci.py` enforces the pins, the runners, the concurrency, and the
  union check.

CI time is in the design doc, section 5. The ruleset that would require the
five checks is written out there for the owner and was not created.

**Deferred.** `apt-get update` still runs in `test`. The tarball is cached
twice (about 715 MB each): actions/cache keeps a separate entry for the
container job, even under the same key and path. A macOS job, coverage, a
linter, and pytest-xdist are not added.

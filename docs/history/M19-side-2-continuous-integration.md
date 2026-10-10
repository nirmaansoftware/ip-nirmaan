# Continuous integration (side work, Stage 0) - `.github/workflows/ci.yml`

GitHub Actions runs the full suite on Python 3.11 and 3.12 for every PR and
every push to `main`, installing with `pip install -e ".[ai,dev]"`. Because the
`ai` extra installs `anthropic`, `test_missing_sdk_raises_clean_error` skips in
CI (it covers the missing-SDK path); locally it is deselected, where iCloud
eviction stalls the `anthropic` import. A second job runs
`scripts/check_dashes.py`, which fails on U+2014 or U+2013 in any tracked text
file except the vendored nirmaan.online files (`site/nirmaan.css`,
`site/site.js`, `site/hero.js`). The README carries the CI badge.
Since v1.17.0 the test job runs on ubuntu-24.04 with `verilator iverilog yosys`
from apt and `NIRMAAN_REQUIRE_EDA` set, so the M21 real-tool tests run in CI
rather than skip (formal still skips: apt has no `sby`). v1.17.0 is the one
version bump covering Stage 0 and M20 to M22, which were built in parallel.

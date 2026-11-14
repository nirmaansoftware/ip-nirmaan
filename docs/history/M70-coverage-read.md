# Milestone 70 - Code coverage: `coverage.read` runs through Verilator and verilator_coverage, and block verification's coverage stage gates on it

Wave 2 (Verification, W2-T2) of the capability build-out (council record
`council/records/2026-10-18-capability-buildout.md`, section 10), under the
founder's decision of 2026-11-13 in that record ("New tools for wave 2": eqy,
verilator_coverage and cocotb, each in its own milestone, no spending). Design:
`docs/COVERAGE_READ.md`. Tests: `tests/test_coverage_read.py`.

**The gap.** `coverage.read` was a contract, so no coverage requirement could
be met by a run, and block verification's coverage stage gated nothing.

**The tool.** `coverage.read` is `AVAILABLE` (risk `execute`) through the
`verilator-coverage` backend: a Verilator build with line and toggle coverage,
the testbench run with the run's nonce, and `verilator_coverage` reading the
data the run wrote. `parse_coverage` reports `line`, `toggle` and `branch`
percentages over the design files only (every source but the testbench, or
`design`), rounded down, and passes only when the simulation passed as
`simulator.run` judges one and every design file has points. The threshold is a
requirement's bounds (M48). Sources that could forge the counts are refused
before anything runs.

**The gate.** Block verification's `coverage` stage builds on the approved RTL
and testbench, writes a testbench, and must pass `coverage.read` over the
approved RTL and its own testbench with line at least 90 and toggle at least 75
percent before review. It replaces the stage's recorded-evidence requirement.

**The must-fail pair.** On the M21 counter, a testbench that exercises it reads
100 percent and meets the bounds; one that holds it in reset passes its own
checks and fails them.

**CI.** `verilator_coverage` (apt's verilator package) joins
`NIRMAAN_REQUIRE_EDA` and the `no-tools` job's absent list.

**Counts.** One tool moves from `CONTRACT_ONLY` to `AVAILABLE`
(`scripts/status.py --write`).

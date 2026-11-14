# Milestone 72 - Python testbenches through cocotb: simulator.run's cocotb backend, judged by cocotb's own results

Wave 2 (Verification) of the capability build-out, item W2-T3, under the
founder's decision of 2026-10-30 ("New tools for wave 2 (2026-11-13)" in
`council/records/2026-10-18-capability-buildout.md`). Design:
`docs/COCOTB.md`. Tests: `tests/test_cocotb_runner.py`, `tests/test_laws.py`,
`tests/test_nirmaan_gate_integrity.py`.

**The gap.** A testbench had to be HDL; nothing could run a Python one, so
`python_verification` had no judge.

**Runner.** cocotb is a backend of `simulator.run` (`cocotb`, chosen by name),
one `register_backend` call in `integrations/cocotb_runner.py` with no EDA
core change. It compiles the design with Icarus and runs it under `vvp` with
cocotb driving the given test modules, copied into the run's own directory.
A run passes only on cocotb's own verdict: its JUnit results file lists at
least one test, all passed, and its one totals line agrees. Every HDL source
is design, so one that could stand in for the verdict is refused, as are
`expect: fail` and test files that are not Python modules.

**Gate.** A cocotb pass is cocotb's count of passing tests, not the HDL
testbench's nonce verdict, so `ToolRun.answers` lets a run made with a backend
in `VERDICT_BACKENDS` (`cocotb`) meet only a requirement that fixes that
backend: no existing simulation gate accepts it.

**Timeout.** The Python runs inside the run's `vvp` step, so the run's one
deadline (M53) stops a Python test that never returns (tested).
`test_the_timeout_covers_the_whole_run` keeps its assertions with wider
timing, since 0.4 s of slack failed on a loaded shared machine.

**Must fail.** `tests/fixtures/cocotb/counter_cocotb.py` passes on the M21
counter and fails each of M69's two single-change mutants, one test each.

**Dependency.** The `cocotb` extra pins `cocotb==2.1.0` (BSD-3-Clause), from
PyPI and never vendored, so NOTICE does not change.

**CI.** The test job installs the extra and names `cocotb` in
`NIRMAAN_REQUIRE_EDA` (`needs` gained `modules`); the `no-tools` job checks it
is absent.

**Counts.** None change: the tool was already `AVAILABLE`.

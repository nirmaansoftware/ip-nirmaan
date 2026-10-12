# Milestone 53 - Gate integrity: verdicts the work under test cannot forge

Findings F1 to F22 of audit B, against v1.24.0. Design:
`docs/GATE_INTEGRITY.md`. Tests: `tests/test_nirmaan_gate_integrity.py`, each
an audit probe turned into a test that failed on `main`.

**Simulation passes on the testbench's verdict.** A run passes only when the
testbench prints `NIRMAAN-SIM <nonce> <n> passed, <m> failed` once, with the
128-bit nonce the runner passed as `+nirmaan_nonce=`, `n > 0` and `m = 0`.
Only the file that declares the top module may end the run or read plusargs,
so RTL with `initial $finish` in `translate_off` (F14) is refused before
anything is simulated, and a testbench that reports failure only in words
(F1) fails. `$finish` is read only in the simulators' own formats (F2). Every
fixture and eval reference testbench prints the verdict; the `rtl_design`
skill tells seats to.

**A bounded check is not a proof.** `formal.run` reports `mode bmc` as "no
counterexample within N steps" with `proven = 0`; the RTL gate "Formal
properties are proven" carries the bound `proven >= 1` (F15). A multi-task
`.sby` is refused with a reason (F17).

**The firmware verdict is the harness's.** Records carry the run's nonce,
which the host harness takes out of `argv` before test code runs and the SoC
firmware cannot read; the SoC's runtime reports through a new `REPORT`
register. The harness counts bus transfers itself; its summary and transfer
count must agree with the records, and a run needs a transfer per passing
check (F4).

**The runner.** One deadline per run, a timeout that freezes and kills the
whole process tree (F16; `sby`'s solvers no longer survive), `timeout >= 1`
(F3), a run's own directory under `workdir` (F22), and no
credential in a step's environment, with any credential value redacted from
logs and records (F9). Two Verilator builds in one directory reproduced the
parallel-run flake on `main`; they now pass.

**Smaller fixes.** MBIST checks exit statuses and controller counts (F5);
half an LVS setup is refused (F6); engine operations are named (F8); CI
`cmake | tail` fails with cmake (F10); empty spec checks fail (F18); partial
KLayout and OpenSTA reports fail (F19); a directory given to VeriTriage is
refused (F20); one RISC-V GCC definition (F21). `live-eval.yml` reuses the
checked OSS CAD Suite action and pins Claude Code (F9).

Deferred: out-of-process firmware tests, the token in the live evaluation's
own process environment, a retention policy for run directories, F7, F13, and
F21's duplicated helpers.

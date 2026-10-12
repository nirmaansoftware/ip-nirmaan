# Gate integrity (M53)

Audit B (2026-10, against v1.24.0) found no tool that claims a run that did
not happen. It found real runs whose pass did not mean what the gate says:
broken RTL that passed the reference testbench, a bounded check reported as a
proof, a firmware verdict any program could print, and a timeout that left
solvers running. The thesis of IP Nirmaan is that real tools judge AI work, so
a gate that broken work can pass is the most serious kind of bug here. This
milestone makes each verdict rest on evidence the work under test cannot
produce.

Tests: `tests/test_nirmaan_gate_integrity.py`. Each audit probe is a test that
failed on `main` before this change.

---

## 1. The simulation verdict (F14, F1, F2)

**Before.** A simulation passed when every step exited 0, no error line was
printed, and a `$finish` line appeared. RTL with
`// synthesis translate_off  initial $finish;  // synthesis translate_on`
ended every simulation at time 0, before the testbench checked anything, and
passed lint, synthesis, the RTL simulation gate, and the held-out reference
testbench. A testbench that printed `FAIL` with `$display` and then called
`$finish` passed too.

**The contract.** A `simulator.run` or `test.run` passes only when the
testbench positively reports its checks:

```
NIRMAAN-SIM <nonce> <passed> passed, <failed> failed
```

printed exactly once, just before `$finish`, with `passed > 0` and
`failed = 0`, plus the old conditions (every step exits 0, no error, `$finish`
reached). The nonce is 128 random bits the runner generates for each run and
passes to the simulator as `+nirmaan_nonce=<hex>`; the testbench reads it with
`$value$plusargs("nirmaan_nonce=%s", nonce)`. A verdict line with another
nonce fails the run, as does a second verdict.

**Why the design under test cannot forge it.** Two layers:

1. *A nonce.* The verdict line must carry a value the RTL author could not
   know when writing the RTL, so a canned `$display` of a passing verdict is
   useless.
2. *Only the testbench may reach the run.* Before anything is simulated, every
   source file other than the one that declares the top module (the
   testbench) is checked for `$finish`, `$stop`, `$exit`, `$value$plusargs`,
   `$test$plusargs`, `$fopen`, `$system`, `$c`, `DPI`, and token pasting
   (`` `` ``, which could build any of them). Any of them is a recorded failed
   run that names the file and what it used. So the RTL can neither end the
   run before the testbench reports nor read the nonce to print a verdict of
   its own. Comments are stripped first; a mention inside a string still
   counts, which errs on the side of refusing.

Running the testbench's own top and confirming it reached its end was the
alternative. It needs no change to testbenches but cannot tell a testbench
that reached its end from one that checked nothing, which is F1. The verdict
line answers both.

The parser also reads `$finish` only in the simulators' own formats: Icarus's
`<file>:<line>: $finish called at` (and `$finish(2)`), and Verilator's
`- <file>:<line>: Verilog $finish`. Icarus's `$stop called at` is an error,
not a finish (F2).

**What moved.** Every fixture testbench and every eval reference testbench
(`tests/fixtures/rtl/**/*_tb*.v`) counts its checks and prints the verdict.
The `rtl_design` skill tells seats to report failures with `$error` or
`$fatal`, to count passing checks, to print the verdict, and to keep `$finish`
and plusargs in the testbench; the prompt goldens show it. DFT's generated
testbenches have their own result lines and are parsed without a nonce.

---

## 2. The formal gate (F15, F17)

**Before.** `formal.run` reported "every property proven" for any
`DONE (PASS)`, including `mode bmc depth 3`, which only shows that no
counterexample exists in three steps. A false assertion that fails at step 6
passed both RTL formal gates.

**Now.** `formal.run` records the setup's `mode` and `depth` and reports a
`bmc` pass as "no counterexample within N steps (a bounded model check, not a
proof)". Its metrics carry `mode`, `depth`, and `proven` (1 only for a passing
`mode prove`).

**Policy.** The RTL gate "Formal properties are proven" (on every RTL stage
and on `block-design`) requires a proof, as data: the bound `proven >= 1`
(M48). A BMC run is still recorded honestly and can be evidence where a
requirement accepts a bounded result ("Proof results with vacuity and
bounds"), but it never meets "proven". A minimum BMC depth was the
alternative; no depth makes a bounded check a proof, and the gate's name
promises one.

`formal.cover` is unchanged: it answers whether the setup is vacuous, not
whether it is true, and the false property now fails the gate at `formal.run`.
A setup with `[tasks]` is refused by `formal.run` with a reason, as
`formal.cover` already did.

---

## 3. The firmware verdict (F4)

**Before.** `fw.test`, `fw.soc_test`, and `regmap.verify` passed on whatever
`FWTEST` lines appeared on stdout. The driver and its tests link into the same
process as the host harness, so `printf("FWTEST PASS x\nFWTEST SUMMARY ...");
exit(0);` passed with zero bus transfers. On the SoC, the firmware wrote the
verdict through the console register, so any code in the image could print it.

**The verdict source.** The verdict is the harness's, which sees the bus:

* Every record the gate counts starts with `FWTEST:<nonce> `, the run's nonce
  from `+nirmaan_nonce=`. Any other line that claims to be a record (an
  untagged `FWTEST ...`, or another nonce) fails the run.
* *Host co-simulation* (`axil_manager.cpp`, `apb_manager.cpp`,
  `harness_report.h`): the harness takes the nonce out of `argv`, and
  overwrites it there, before any driver or test code runs. It counts the bus
  transfers it performs and ends with `SUMMARY <p> passed, <f> failed, <c>
  cycles` and `END <t> bus transfers`.
* *SoC* (`nirmaan_soc.v`, `soc_main.cpp`, `soc_runtime.c`): the firmware runs
  in the simulated CPU and cannot read plusargs. The SoC's Verilog prints the
  BUS records and, when the firmware writes `EXIT`, `END <t> bus transfers`
  from its own counter. The runtime writes PASS, FAIL, IRQ, TRAP, and SUMMARY
  through a new `REPORT` register (`0x2000_001C`), which the SoC prefixes with
  the nonce. `CONSOLE` text is printed as written and is never a record.
* The parser requires SUMMARY and END, requires the summary's counts to equal
  the PASS and FAIL records, and END's count to equal the BUS records.
* At least one real bus transfer per passing check, counted over the run. A
  per-check rule (a transfer since the previous check) was tried and rejected:
  the fixture and held-out tests have legitimate checks that a driver refuses
  a bad argument without touching the bus.

**Residual.** Code linked into the host harness shares its address space; it
could find the nonce by scanning memory, or call `nirmaan_test_result`
directly, which is the reporting API itself. The SoC's `REPORT` register can
likewise be written by any firmware. Neither can make transfers happen that
did not, and a check cannot pass with fewer transfers than checks. Running
test code out of process is the complete answer and is deferred.

---

## 4. The runner (F16, F3, F22, F9, and the parallel-build flake)

`integrations/eda.py` runs every backend's steps; these apply to every tool.

* **One deadline per run.** `timeout` covers all steps together, as its
  contract says; it must be at least 1 second (0 and negatives are refused by
  the probe, nothing runs).
* **A timeout stops everything.** Each step leads a new process group. On a
  timeout the whole process tree is frozen (`SIGSTOP`) while every process
  still has its parent, then every process and process group in it is killed.
  `sby` puts each solver in a group of its own, which is why killing the
  step's group alone was not enough: before, `yosys-smtbmc` and `yices-smt2`
  were left running (three such orphans ran for four hours on the owner's
  machine).
* **A run's own directory.** Given a `workdir` that is new or empty, a run
  claims it with an exclusive create of `.nirmaan-run`; otherwise it works in
  a new directory inside it. Steps that remove fixed names (`stat.json`,
  `netlist.v`, `layout.gds`) can no longer touch a file the run did not write,
  and two runs given the same directory never share one.
* **A private temporary directory.** `TMPDIR`, `TMP`, and `TEMP` point into
  the run's directory, so compilers' scratch files and caches such as macOS's
  `xcrun_db` are not shared with other runs.
* **No credential in a run.** Steps get this process's environment without any
  variable whose name looks like a credential (`TOKEN`, `SECRET`, `PASSWORD`,
  `API_KEY`, `PRIVATE_KEY`, `ANTHROPIC_*`, ...). Anything a run prints that
  equals such a value (16 characters or more) is replaced with
  `[<NAME> redacted]` before it reaches the log, the summary, or a record.

**The parallel-build flake.** `test_real_verilator_simulation_passes` and
`test_the_interrupt_fires...` failed with `'make -C obj ...' exited with 2`
while another agent's suite ran on the same machine. Two Verilator builds
started at once in one working directory reproduce exactly that signature on
`main` (`cat: ...verilator_deplist.tmp: No such file or directory`, then the
link fails): `test_two_builds_at_once_in_one_workdir_are_isolated` fails there
and passes here. Inside the suite each test has its own `tmp_path`, so the
remaining shared state between two suites was machine-wide: the shared
`TMPDIR` (now per run), and solvers orphaned by earlier timeouts (now killed).
The machine's `TMPDIR` also held about 35,000 run directories (8.8 GB) from
runs without a `workdir`, with the disk 98% full; that leak is listed below.

**The live evaluation** (`live-eval.yml`): the OSS CAD Suite comes from the
same composite action as `ci.yml` (pinned, cached, sha256-checked), Claude
Code is pinned (`@anthropic-ai/claude-code@2.1.283`), and the token is set only
on the gate step and the evaluation step. Inside the evaluation every gate
and judge runs through the runner above, so model-written code compiles and
runs with no credential in its environment, and a credential value it prints
anyway is redacted from logs and from the uploaded record.

---

## 5. The smaller findings

| ID | Fix |
|---|---|
| F5 | MBIST's pass path checks every exit status, every simulator error, and one result line per generated controller (`DFT-MBIST-GEN`). |
| F6 | `pv.run` with `lvs_deck` and no `cdl` (or the reverse) is refused with a reason. |
| F8 | The six engine operations (`task.create`, `review.create`, ...) are `ENGINE_OPERATIONS` in `company/tools.py`; the catalog says AVAILABLE means a broker binding or an engine operation, and a test holds the two lists equal. |
| F10 | CI's OpenSTA build sets `pipefail`, so `cmake | tail` fails when cmake does. |
| F18 | `spec.check` fails on a checks file with no requirement and no name. |
| F19 | KLayout LVS needs all five mismatch counts; OpenSTA needs the hold, TNS, and WNS figures its script asks for. |
| F20 | `veritriage.investigate` refuses a directory with a reason. |
| F21 | `fw.build`'s `riscv-gcc` backend uses `firmware_riscv.py`'s one RISC-V GCC definition (either name, the same RV32I flags). |
| F22 | See section 4, a run's own directory. |

## 6. Deferred

* **Out-of-process firmware tests.** The complete answer to section 3's
  residual: run the driver and its tests in a separate process from the
  harness, talking over a pipe.
* **The token and same-user processes.** On Linux a process can read the
  initial environment of its parent (`/proc/<ppid>/environ`) when both run as
  the same user. The live evaluation's `nirmaan` process starts with the token
  in its environment, so model-written code could still read it there. The fix
  is to pass the token to `nirmaan` through a file it reads and deletes, and
  hand it only to the `claude` subprocess, or to run tool steps as another
  user. Not done here; the runtime is outside this milestone's scope.
* **Leaked run directories.** A run with no `workdir` keeps its directory (its
  log is the run's reference). Nothing removes them; a retention policy is a
  product decision.
* **F7** (`pv.run` needs `openroad` for DRC only), **F13** (cover runs read a
  rewritten copy), and the rest of F21: the duplicated `_plural` and `_first`
  helpers, the two `_VERILATOR_NOISE` lists, and the unused `unregister_bus`.
  (F21's docstring counts are fixed, and `_MBIST_GEN_RE` is now used, by F5.)

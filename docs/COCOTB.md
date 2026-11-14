# Python testbenches through cocotb (M72)

Wave 2 (Verification) of the capability build-out, item W2-T3, under the
founder's decision of 2026-10-30 (council record
`council/records/2026-10-18-capability-buildout.md`, "Founder decisions
(2026-10-30)", item "New tools for wave 2 (2026-11-13)": eqy,
verilator_coverage and cocotb may be wired into the tool broker, each in its
own milestone, no spending).

Until this milestone a testbench had to be HDL: `simulator.run` compiled a
Verilog or SystemVerilog testbench and read its own verdict line (M53).
cocotb runs testbenches written in Python against the design in the
simulator, so a seat can write one, and `python_verification` has something
to judge it.

## The runner

cocotb is a backend of `simulator.run`, not a new tool. It is a simulation:
the roles that may simulate may run it, a gate can name it with the fixed
parameter `backend: cocotb` (M26), and the tool's status (`AVAILABLE`) and
the catalog counts do not change. What is new is the backend, and it is
registered only because it really runs and is tested here, in CI too.

| Tool ID | Backend | Executables | Parameters |
|---|---|---|---|
| `simulator.run` | `cocotb` (`nirmaan/integrations/cocotb_runner.py`), chosen by name | `iverilog`, `vvp`, and cocotb importable in this Python | `sources` (the design), `top` (its top module), `cocotb` (the Python test modules), all required; `workdir`, `timeout`, `backend` |

The backend is one `register_backend` call in its own module; the EDA core,
the broker and the engine do not change (a test checks the EDA core never
names cocotb). It comes after `icarus` and `verilator-sim`, so a
`simulator.run` without `backend` still runs an HDL testbench, and it refuses
to run unless named, so every cocotb run records `backend: cocotb`. Those backends
ignore `cocotb`; given only a design, they find no testbench verdict and the
run fails, never passes.

## Gates (gate semantics)

Every simulation gate in the workflows today reads an HDL testbench's verdict:
the testbench prints `NIRMAAN-SIM <nonce> <n> passed, <m> failed`, counted
checks with the run's nonce (M53, `docs/GATE_INTEGRITY.md` section 1). A cocotb
pass is judged another way (cocotb's count of passing Python tests), so it
must not meet those gates. The policy changes in one place for this:
`ToolRun.answers` (M71) reads `VERDICT_BACKENDS` (`models/work.py`, today
`cocotb`), and a run made with such a backend answers a requirement only when
the requirement fixes that very backend (`params: (("backend", "cocotb"),)`).
So no existing gate is met by a cocotb run (a test walks every `simulator.run`
requirement in every workflow), and a gate that wants cocotb says so. No
existing gate changes; none names cocotb yet.

## What a run does

1. **Refuses what it cannot judge, before anything runs** (a recorded failed
   run):
   - `expect` other than `pass`: the reproduction mode (M71) reads an HDL
     testbench's verdict of a failed check, and cocotb reports failed tests,
     not checks;
   - a test file that is not a `.py` file named as a Python module, or two
     with the same name;
   - an HDL source that ends the simulation, reads its arguments, opens a
     file or reaches outside the language (M53's testbench-only constructs,
     and token pasting). With cocotb the testbench is the Python, so every HDL
     source is design, and none may stand in for the verdict.
2. **Runs over copies.** The test modules are copied into `cocotb_tests/` in
   the run's own directory (M53), the only folder on the testbench's
   `PYTHONPATH`, so nothing is written next to the submitted files.
3. **Compiles and runs with Icarus**, as cocotb's own Icarus runner does:
   `iverilog -g2012 -s <top> -f cmds.f <sources>` (`cmds.f` sets
   `+timescale+1ns/1ps` for a source that declares none), then
   `vvp -m <cocotb's VPI library> sim.vvp -none` under `env` with the
   variables cocotb reads: the libpython and entry point it embeds, this
   Python, the top level, the test modules, and `COCOTB_RESULTS_FILE`, the
   JUnit file it writes into the run's directory. The log shows both commands
   exactly as they ran.
4. **Reads cocotb's own verdict** (`eda_parsers.parse_cocotb`). A run passes
   only when cocotb wrote its results file, the file lists at least one test,
   every test passed (skipped ones aside) and none failed or errored, cocotb's
   totals line (`** TESTS=n PASS=p FAIL=f SKIP=s`) was printed exactly once
   and agrees with the file, and both steps exited 0. The exit status alone
   says nothing: `vvp` exits 0 when tests fail, and when cocotb never
   started. The HDL design cannot write the file (it may not open a file), and
   a totals line it prints makes two, which fails the run: a forged line from
   the design can only fail a run. The Python testbench is not so bound (see
   "Trust model" below). A results file with a DOCTYPE or an entity is refused
   unread.

The result's metrics: `tests`, `tests_passed`, `tests_failed`,
`tests_skipped`, `failing` (the failed tests' names), `cocotb` (its version,
from its own start-up line), `simulator`, `seed` (the random seed, to repeat
a run with `COCOTB_RANDOM_SEED`) and `exit_statuses`. The summary reads
"2 of 2 tests passed; cocotb 2.1.0 on Icarus Verilog version 13.0 (stable)",
or names the first failed test and its assertion. Each failed test is an
error diagnostic (`TEST_FAILED`). The log and the result JSON are the run's
references, as for every EDA tool (`docs/EDA_TOOLS.md`), and cocotb's results
file is one of its outputs (`results`, M44).

## Trust model: the Python testbench is not sandboxed

The test modules are Python that runs inside the host's `vvp` process, with
that process's full rights. This backend contains none of it: there is no
sandbox, no import filter and no limit on what the Python can do (read or write
files, spawn processes, use the network). The HDL check in step 1 refuses HDL
constructs only; it says nothing about the Python.

What is true instead:

- **The Python is the testbench author's code, trusted as the host's own.** It
  is as trusted as a `pytest` file a seat runs in the same checkout. The
  controls are the ones around the tool, not inside the run: only roles that
  may simulate can call `simulator.run`, the broker records every call, and the
  run has a `timeout` and its own working directory. The Python runs inside
  the run's `vvp` step, so the run's one deadline (M53) stops it too: a test
  gives it a Python test that never returns. Running cocotb on text
  from an untrusted source is outside this milestone and must not be done
  without a container or VM boundary, which this repository does not provide.
- **The Python can forge the verdict.** It could write `results.xml` or print a
  totals line itself, as an HDL testbench can print a passing verdict line.
  "The design cannot write the file" in step 4 holds for the HDL only, since
  the HDL check forbids opening a file. A passing cocotb run therefore proves
  "the testbench author's Python reported success", never "an independent
  check passed".
- **No credential reaches it.** The run's environment has every credential
  removed (M53, `run_environment`), as for every EDA run.
- **What backs the verdict is not the run but the scorer.** The must-fail
  scorer (M58) runs the same testbench on broken RTL and requires it to fail;
  a testbench that always reports success is caught there, not by this parser.
  Nothing here claims otherwise.

**A limit, stated.** cocotb counts tests, not checks: a test that asserts
nothing passes. An HDL testbench's verdict counts checks and fails at zero
(M53); cocotb gives nothing to count. What shows a cocotb testbench checks
something is the must-fail scorer (M58): it must fail on broken RTL.

## The pinned dependency, and NOTICE

cocotb is the `cocotb` extra in `pyproject.toml`, pinned to one release,
`cocotb==2.1.0`, since its runner, its start-up and totals lines
and its results file are what a run is judged by. It is not a base
dependency: installing IP Nirmaan never needs it, and the backend refuses
honestly ("cocotb is not installed in this Python") without it. Its one
dependency, `find_libpython` (MIT), comes with it.

cocotb is BSD-3-Clause. **NOTICE does not change**, because nothing of cocotb
is vendored, copied or redistributed: the repository and its wheel hold no
cocotb file, the pin names the package, and pip fetches it from PyPI into the
user's or CI's own environment. The fixture testbench imports cocotb, which
uses it and copies nothing. NOTICE lists third-party files this product
includes (SERV, PicoRV32, fonts), and cocotb is not one; it would be added the
day a cocotb file is copied in.

## Tests

`tests/test_cocotb_runner.py`: the catalog and backend order; a refusal
without cocotb; the core never naming cocotb; the parser against captured
output (`tests/fixtures/eda/cocotb_{pass,fail}.{log,xml}`), including forged
and disagreeing totals lines, a missing results file with the compile error,
unreadable, empty and all-skipped results, and a non-zero exit; each refused
input; and real runs. `tests/fixtures/cocotb/counter_cocotb.py` (two tests)
passes on the M21 counter over copies, writing nothing beside itself, and
must fail on each of the two single-change mutants M69 wrote
(`tests/fixtures/eqy`): `counter_wraps_early.v` fails `counts_and_wraps`, and
`counter_reset_ignored.v` fails `reset_clears_while_idle`, each with an
`AssertionError` and the other test still passing. A design that prints
cocotb's totals line fails; and without `backend: cocotb` the tests are not
run and nothing passes. `tests/test_laws.py`: `needs(modules=...)` skips
without a Python package unless CI requires it.

## CI and install

The `test` job installs `.[ai,dev,cocotb]`, prints `cocotb-config --version`,
and names `cocotb` in `NIRMAAN_REQUIRE_EDA` (with `iverilog` and `vvp`, there
already), so the real runs fail rather than skip; they use apt's Icarus on
Ubuntu 24.04. The `no-tools` job installs `.[dev]` and checks cocotb is not
importable, so those tests skip there. Locally: `pip install 'cocotb==2.1.0'`
into the venv (or `pip install -e '.[cocotb]'`), with Icarus on PATH.

## Not in this milestone

- cocotb on Verilator: cocotb 2.1 needs Verilator 5.036 or later
  (`VLT_MIN := 5.036` in its `cocotb_tools/makefiles/simulators/Makefile.verilator`),
  and CI's apt Verilator on Ubuntu 24.04 is 5.020 (`docs/COVERAGE_READ.md`).
- VHDL, mixed-language designs, and simulator parameters as inputs.
- `expect: fail` for cocotb reproductions (M71).
- A gate that names the backend, and the `dv/cocotb-crc` eval case (W2-E6),
  with the `python_verification` skill card (wave 2's skill batch).

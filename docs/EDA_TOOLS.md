# Real design tools through open-source EDA (Milestone 21)

Until this milestone every EDA tool in the catalog was `CONTRACT_ONLY`: the
organization planned around lint, simulation, synthesis, and formal, but the
broker refused them, so an evidence requirement such as "Lint run with waivers
dispositioned" could only be met by a named human attesting to a run made
somewhere else. Open-source EDA makes these requirements real without a
license server.

This milestone binds five tools to open-source backends:

| Tool ID | Backends, in preference order | Executables |
|---|---|---|
| `lint.run` | `verilator-lint` | `verilator` |
| `simulator.run` | `icarus`, `verilator-sim` | `iverilog` and `vvp`; or `verilator` |
| `test.run` | `icarus`, `verilator-sim` | as above |
| `synth.run` | `yosys` | `yosys` |
| `formal.run` | `symbiyosys` | `sby` (plus `yosys` and a solver, which `sby` finds itself) |

`sta.run` (OpenSTA) is not bound. It needs a liberty file and constraints that
the fixture flow does not have yet, so it stays `CONTRACT_ONLY` for Stage 6.

(M25 bound it, and `pnr.run`, through OpenSTA and OpenROAD: see `docs/PHYSICAL_DESIGN.md`.)

```
nirmaan org tools          # the five tools now show a binding
```

---

## 1. The rules

1. **A binding runs only when its executable is on `PATH`.** Otherwise the
   broker refuses the invocation, exactly as it refuses a contract-only tool,
   and the refusal names what is missing (`lint.run needs verilator on PATH;
   not found`). Nothing is simulated, stubbed, or replayed from a fixture.
2. **Failures are recorded runs, never exceptions.** A lint error, a failing
   simulation, a synthesis error, a counterexample, a missing source file, a
   timeout: each is a `ToolRun` with `succeeded=False` and a summary saying
   why. Only a refusal (the tool could not be started at all) raises.
3. **Output is parsed into a structured result**: pass or fail, diagnostics
   (severity, file, line, code, message), and metrics (cell counts, proof
   status). The raw log and the structured result are both written to disk and
   cited by the run.
4. **Simulation logs feed VeriTriage.** A simulation run's log path is its
   first reference, and `triage_simulation()` hands it to
   `veritriage.investigate` through the same broker, as its own recorded run.

---

## 2. How a binding declares its executable

The extension point is one registry in `nirmaan/integrations/eda.py`:

```python
register_backend(Backend(
    name="verilator-lint",
    tool="lint.run",
    executables=("verilator",),
    steps=lambda job: [["verilator", "--lint-only", "-Wall", *job.top_args("--top-module"), *job.sources]],
    parse=lambda run: parse_verilator_lint(run.log, run.returncode),
))
```

* `executables` are all required; `shutil.which` decides, at invocation time.
* `steps` turns a `Job` (sources, top module, working directory, parameters)
  into the argument vectors to run, in order. A failing step stops the job.
  Steps never go through a shell.
* `parse` turns the finished run (combined log, exit statuses, working
  directory) into an `EdaResult`.
* `required` names the parameters the backend cannot run without (default
  `sources`), and `cwd` optionally moves the steps out of the working
  directory (SymbiYosys resolves its `[files]` against the directory it runs
  in, so it runs next to its `.sby` file and writes only under `-d`).

`register_backend` also registers the broker binding for the tool the first
time a backend names it, so a new backend (or a new tool, once the catalog
lists it as `AVAILABLE`) needs no change to the broker, the engine, or the
policy. `tests/test_nirmaan_eda.py::test_a_new_backend_needs_no_core_changes`
proves it with a backend whose executable is a script the test writes.

The broker gained one generic hook to support this: `register_binding` takes
an optional `probe(params) -> reason | None`. The broker calls it after the
authority and catalog checks and refuses with the reason when it returns one.
The EDA module's probe asks whether any backend for the tool (or the one named
by the `backend` parameter) has every executable on `PATH`.

---

## 3. How availability is decided

There are two separate facts, and they are kept separate:

| Fact | Where it lives | Decided |
|---|---|---|
| This repository contains a real implementation | `company/tools.py`: `AVAILABLE` | when the code is written |
| This machine can run it now | the binding's probe | at every invocation |

The catalog status says what the installation *can* do; it moves from
`CONTRACT_ONLY` to `AVAILABLE` only because a real binding now exists. The
probe says what this machine can do right now. A machine without Verilator
still refuses `lint.run`, with a reason, and records no run: the evidence
requirement stays unmet, and a human attestation remains the only way to
meet it there.

Backend selection: the `backend` parameter picks one by name; otherwise the
first registered backend whose executables are all present is used.

---

## 4. Parameters

All values are strings, as for every brokered tool.

| Parameter | Tools | Meaning |
|---|---|---|
| `sources` | lint, simulator, test, synth | Comma-separated Verilog or SystemVerilog files (required) |
| `top` | lint, simulator, test, synth | Top module (required for simulation and synthesis; optional for lint) |
| `sby` | formal | Path to a `.sby` file (required); its `[files]` are resolved by `sby` |
| `workdir` | all | Where logs and outputs go; a fresh temporary directory when absent |
| `backend` | all | Force one backend by name |
| `timeout` | all | Seconds per step (default 300) |

---

## 5. Result parsing

Parsers are pure functions of captured text, so they are tested against
captured outputs in `tests/fixtures/eda/` with no tool installed.

| Parser | Pass means | Structured content |
|---|---|---|
| `parse_verilator_lint` | exit code 0, no `%Error`, no `%Warning` | diagnostics with code (`UNUSEDSIGNAL`, `WIDTHTRUNC`, ...), file, line, column |
| `parse_simulation` | every step exited 0, no error or fatal message (Icarus `ERROR:`/`FATAL:`, Verilator `%Error`), and `$finish` was reached | diagnostics, `finished`, the simulation end time when printed |
| `parse_yosys` | exit code 0, no `ERROR:` | warnings, and from `stat -json`: cells, wires, and cell counts by type |
| `parse_sby` | `DONE (PASS, ...)` | status (`PASS`, `FAIL`, `ERROR`, `UNKNOWN`, `TIMEOUT`), failed assertions with location, trace files |

Lint warnings fail lint: the RTL lint requirement means lint-clean. Waivers
are the RTL's business (`/* verilator lint_off ... */`), where a reviewer can
see them.

---

## 6. How a run becomes evidence

Nothing changes in the engine. The chain is the one M19 built:

```
broker.invoke(actor, "lint.run", {...}, task)   -> ToolRun (recorded, audited)
engine.record_evidence(task, actor, TOOL_RUN, ..., tool_run=run.id)
    substantiated  <=> the run succeeded
    satisfies      <=> the requirement accepts TOOL_RUN and names lint.run
```

The run's references are the log path and the result JSON path, so a reviewer
can open exactly what the tool printed. A failed lint run can be recorded as
evidence, and it is recorded unsubstantiated, so it satisfies nothing. The
`tool-claims-need-runs` check still refuses evidence citing a run that never
happened.

`tests/test_nirmaan_eda.py::test_real_lint_substantiates_the_rtl_lint_requirement`
plans the AXI-to-NoC bridge, runs real Verilator lint over the fixture module
as the lint task's owner (an AI agent), and shows the requirement met with no
human attestation anywhere on the task.

---

## 7. Simulation logs into VeriTriage

The import law holds: only `integrations/veritriage.py` imports VeriTriage. The
EDA module never does. `triage_simulation(broker, actor, run, task)` takes a
recorded `simulator.run` or `test.run` and invokes `veritriage.investigate`
through the broker with the run's log path. The result is a second recorded
run whose reference is a VeriTriage session ID, which a
`VERITRIAGE_SESSION` evidence record can cite. Both runs are in the audit
trail; neither is inferred from the other.

VeriTriage's simulation-log parser already reads the generic `ERROR:` and
`FATAL:` lines Icarus prints for `$error` and `$fatal`, which is why the log is
passed as written rather than translated.

---

## 8. The fixture

`tests/fixtures/rtl/` holds a 4-bit counter with a synchronous reset
(`counter.v`), a self-checking testbench (`counter_tb.v`), a deliberately
broken testbench (`counter_tb_fail.v`), and a SymbiYosys job
(`counter.sby`) proving the counter never exceeds its limit. The lint,
synthesis, simulation, and formal tests run the real tools over them and
`pytest.skip` when an executable is absent. `tests/fixtures/eda/` holds the
captured outputs (Verilator 5.052, Icarus 13.0, Yosys 0.69, SymbiYosys 0.69)
that the parser tests read.

CI (the Stage 0 workflow) should install `verilator`, `iverilog`, and `yosys`
from apt so the lint, synthesis, and simulation tests run for real, and set
`NIRMAAN_REQUIRE_EDA="verilator iverilog vvp yosys"`: a test that needs an
executable named there fails instead of skipping, so a broken install cannot
pass silently. The `verilator-sim` backend needs Verilator 5 (`--binary`,
Ubuntu 24.04 or later); on Ubuntu 22.04 (Verilator 4) that one test fails, and
`icarus` still serves `simulator.run`. Ubuntu's `yosys` package does not ship
`sby`, so the formal test skips there unless the workflow installs the OSS CAD
Suite.

---

## 9. Not in this milestone

* `sta.run` (OpenSTA), `equivalence.run`, `cdc.run`, and the physical design
  tools remain `CONTRACT_ONLY`.
* Coverage collection from simulation (`coverage.read`).
* Waveform capture into the VeriTriage waveform engine.
* Version pinning of the backends: a run records which executable ran (its
  resolved path), not its version.

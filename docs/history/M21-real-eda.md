# Milestone 21 - Real design tools through open-source EDA (roadmap Stage 2)

`lint.run` (Verilator `--lint-only -Wall`), `simulator.run` and `test.run`
(Icarus Verilog, else Verilator `--binary`), `synth.run` (Yosys), and
`formal.run` (SymbiYosys) moved from `CONTRACT_ONLY` to `AVAILABLE`, backed by
`nirmaan/integrations/eda.py` (runner, backends) and `eda_parsers.py` (pure
parsers). `sta.run` stays a contract.

Key design points worth not re-deriving:
- Two facts, kept apart: the catalog status says a real implementation exists
  in the repo; a binding **probe** says this machine can run it now. The broker
  gained one generic hook, `register_binding(tool, probe=...)`; a probe
  returning a reason makes the broker refuse (`ToolAccessDenied`), so a missing
  executable is never a run, simulated or otherwise.
- `register_backend(Backend(...))` is the extension point (executables, steps
  as argv lists, parser, required params, optional cwd); the first backend for
  a tool also binds it. Crown jewel
  `test_a_new_backend_needs_no_core_changes` adds a lint backend whose
  executable is a script the test writes, and its run substantiates the lint
  requirement.
- Tool failures (lint warnings, `$error`, counterexamples, missing sources,
  timeouts) are recorded runs with `succeeded=False`. Each run writes
  `<backend>.log` and `<backend>.result.json`; those paths are its references.
- Lint warnings fail lint (lint-clean means clean; waivers live in the RTL).
  Icarus exits 0 on `$error`, so simulation passes only with exit 0, no error
  message, and `$finish` reached.
- `triage_simulation()` hands a simulation log to `veritriage.investigate`
  through the broker, as its own recorded run. `eda.py` never imports
  VeriTriage.
- Existing tests that used `simulator.run` as the example contract-only tool
  now use `git.write`.

Fixtures: `tests/fixtures/rtl/` (4-bit counter, passing and failing
testbenches, a `.sby` proof) and `tests/fixtures/eda/` (captured outputs).
`tests/test_nirmaan_eda.py` (24 tests): parsers against captured output, real
tools (skipped when absent, or failing when named in `NIRMAAN_REQUIRE_EDA`),
refusal with a reason, and a real lint run substantiating the RTL lint
requirement with no human attestation. Design doc: `docs/EDA_TOOLS.md`.

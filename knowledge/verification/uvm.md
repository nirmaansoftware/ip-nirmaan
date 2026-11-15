---
id: verification/uvm
skill: uvm
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
  - open | lowRISC, OpenTitan Signoff Checklist (Apache 2.0) [OTChk] | https://opentitan.org/book/doc/project_governance/checklist/index.html
  - open | lowRISC, OpenTitan DV library classes (Apache 2.0) [OTLib] | https://opentitan.org/book/hw/dv/sv/dv_lib/index.html
  - open | lowRISC, OpenTitan CSR utilities (Apache 2.0) [OTCsr] | https://opentitan.org/book/hw/dv/sv/csr_utils/index.html
  - open | pyuvm project, pyuvm documentation: Introduction and TinyALU example (Apache 2.0) [PyUVM] | https://pyuvm.readthedocs.io/en/latest/docsources/README.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K7 session (wave 2 knowledge batch, plan row W2-K7, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# UVM

How a UVM environment is put together and checked, from one open project's
practice (OpenTitan, SystemVerilog) and one open Python port (pyuvm). Tags in
brackets name the sources above; "inference" marks this document's own
reasoning. This skill's card holds no tool
(src/nirmaan/company/skills.py:370-375), and nothing here has been run.

## What the environment holds

- OpenTitan's strategy for simulation is UVM 1.2 on a base of SystemVerilog
  verification, with constrained-random functional tests. Each design carries
  a UVM testbench, a testplan, a DV document, a test suite and a way to build,
  run and report [OTDV].
- The pyuvm TinyALU example has a test, an environment, two monitors, a
  scoreboard, a coverage subscriber, a driver and a sequencer [PyUVM].
- Components are created in the build phase, which runs top down, and
  connected in the connect phase, which runs bottom up [PyUVM]. In pyuvm's
  ALU example the driver's item port connects to the sequencer's export. The
  command monitor's analysis port connects to the scoreboard's command export
  and to the coverage subscriber. The driver's own analysis port, which
  carries each result, connects to the scoreboard's result export [PyUVM].
- Each interface monitor must reach the scoreboard through a TLM connection.
  OpenTitan lists "TLM port connections ... from UVC monitors to the
  scoreboard" as part of creating the environment [OTChk].
- In the pyuvm scoreboard, analysis FIFOs hold commands and results, and the
  check phase predicts each result and compares it with the observed one
  [PyUVM]. A result with no matching command is logged as critical [PyUVM].
- A reusable component pattern: OpenTitan builds a base library of classes,
  then a layer for its standard IP, then the testbench on top; plug-and-play
  verification components (such as the TileLink and UART agents) sit beside
  them [OTDV].

## Objections and phases

- In pyuvm the test raises an objection with a description at the start of
  its run phase, waits for the sequence, then drops the objection
  [PyUVM]. The driver's run phase loops forever, and cocotb ends it at the end
  of the simulation [PyUVM].
- The card names "objection leaks" as a failure mode. No open source read for
  this document explains what an unbalanced objection does, and this is
  recorded in the wanted-sources list. The reading to check is that every raise
  has a matching drop on every path out of the run phase (inference).
- pyuvm implements only the common phasing, not the custom phasing the
  standard also describes [PyUVM].

## Registers (RAL)

- OpenTitan generates its RAL model from the register description with a tool
  and checks the generated model in, relying on CI checks for consistency
  [OTDV]. Its checklist asks for the generation to be automated [OTChk].
- The DV library's register block class has a build function that is a
  pseudo pure virtual: calling it directly returns a fatal error, and the
  design's own block class is built through it [OTLib].
- `csr_rd_check` reads a register or field and compares the value with a
  prediction, either passed in or taken from the register model [OTCsr]. The
  register-write test's predictions come from the sequence or from an external
  scoreboard [OTCsr]. A model and a scoreboard that disagree about the
  prediction is how a mirror mismatch shows (inference; no source read
  defines "mirror").
- Reading every CSR and checking it against its prediction is intended mainly
  for after reset, to confirm the reset values [OTCsr]. OpenTitan's standard suite is hardware reset,
  read/write, bit bash, aliasing, and for memories a walk, with back to back
  accesses and partial reads and writes [OTChk]. The utilities issue these
  accesses non-blocking so they are back to back [OTCsr].
- pyuvm's register support is partial: the register model and adapter exist,
  the predictor "should be disabled if auto_prediction is not set", the memory
  class is not implemented, and backdoor access is incomplete [PyUVM].

## Stage evidence

- First stage (V1): a top-level testbench with the DUT; a UVM environment with
  the major agents connected; a smoke test passing; the register test suite
  passing [OTChk].
- The smoke test drives the clock, brings the DUT out of reset, checks that
  outputs are not unknown, and exercises a major datapath [OTDV].
- Second stage (V2): an environment "fully developed with end-to-end checks
  in the scoreboard enabled"; every test in the testplan written and passing
  with at least one seed [OTChk].
- Coverage is sampled in reactive components such as monitors and scoreboards
  [OTChk].
- With Synopsys VCS, calling tasks or functions with side effects, notably the
  `uvm_info` macro, blocks X-propagation instrumentation of that logic
  [OTDV]. That is simulator specific.

## Common failure modes

- An objection raised and not dropped on some path (the card; unsourced here).
- A monitor's analysis port left unconnected, so the scoreboard sees nothing
  and checks nothing. A passing run with no compared items is the sign
  (inference).
- A register model out of step with the design's register description.
  OpenTitan's check-in plus CI consistency check exists for this reason
  (inference from [OTDV]).
- A smoke test that does not check outputs, so the environment compiles and
  runs but proves nothing (inference from [OTDV]).

## How a result is checked

- The environment compiles, a smoke test runs, and every interface has a
  monitor connected to the scoreboard (the card's own check).
- A smoke test result is read with the number of items the scoreboard
  compared; zero compared items is not a pass (inference).
- pyuvm's reporting example ends with a summary of report counts by severity
  and a test status line, and its documentation shows it run on Verilator
  through cocotb [PyUVM]. A final status read from such a summary is the
  result to record (inference).
- Whether a Python UVM port runs on this repository's cocotb backend
  (src/nirmaan/company/tools.py:24-26, M72) is not claimed here.

## Sources

- [OTDV] UVM 1.2 strategy, testbench contents, reuse layers, the smoke test.
- [OTChk] The stage items for environment, register model and register tests.
- [OTLib], [OTCsr] The register block base class and the CSR checking tasks.
- [PyUVM] A complete small environment, phases, objections, TLM, and which
  register parts are implemented.

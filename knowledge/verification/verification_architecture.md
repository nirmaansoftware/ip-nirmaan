---
id: verification/verification_architecture
skill: verification_architecture
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
  - open | lowRISC, OpenTitan Assertions and formal property verification (Apache 2.0) [OTFpv] | https://opentitan.org/book/hw/formal/index.html
  - open | lowRISC, OpenTitan Comportable IP Testbench Architecture, cip_lib (Apache 2.0) [OTCip] | https://opentitan.org/book/hw/dv/sv/cip_lib/index.html
  - open | lowRISC, OpenTitan UART DV document (Apache 2.0) [OTUart] | https://opentitan.org/book/hw/ip/uart/dv/index.html
  - open | lowRISC, OpenTitan Earl Grey Chip DV Document (Apache 2.0) [OTChip] | https://opentitan.org/book/hw/top_earlgrey/dv/index.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K8 session (wave 2 knowledge batch, plan row W2-K8, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# Verification architecture

How the verification of a design is divided: which features go to simulation,
which to formal, which level (block, core, chip) checks what, and what is
reused. The source is one open project (OpenTitan), so this is one project's
architecture and not a general rule. Tags in brackets name the sources above;
"inference" marks this document's own reasoning. This skill's card holds no
tool (src/nirmaan/company/skills.py:376-380), and nothing here has been run.
No source read states a rule for deciding the simulation and formal split;
the split below is read from what the project does.

## The techniques and the artefacts

- The project uses two techniques: dynamic simulation with constrained-random
  tests on UVM 1.2 over SystemVerilog, and formal property verification (FPV)
  with SystemVerilog assertions [OTDV].
- Each design carries a testbench, a testplan, a DV document, a test suite,
  and a way to build, run and report [OTDV]. FPV, where used, adds an SV
  testbench and properties [OTDV].
- The testplan has two parts: tests planned to verify every feature in the
  design specification, and a functional coverage plan to show the tests
  reach them. It is written in a machine-readable format so regression
  results can be annotated against it [OTDV].
- The DV document records the strategy, the testbench diagram, interfaces and
  agents, reference models, the coverage model, assertions and checkers, and
  the FPV goals [OTDV].

## Three levels

- Block level: small testbenches with fine control of stimulus and corner
  cases, quick to run, and more coverage work because there are usually no
  verified sub-blocks. They use constrained-random stimulus and model the
  design's behaviour for checking in the scoreboard or in assertions,
  independently of the stimulus [OTDV]. Some cryptographic blocks use open
  third-party C libraries as reference models through DPI-C [OTDV].
- Core level: the project's CPU core has its own testbench and is verified
  separately [OTDV].
- Chip level: aims to show the blocks are integrated correctly. For blocks
  already verified, it runs simple C tests on the CPU, with a way for the
  software to signal pass or fail to the testbench [OTDV]. A knob stubs the
  CPU and uses a bus agent instead where heavier testing is needed [OTDV].
- The chip document's goals add system scenarios, the memory map by automated
  tests, and stress on the interconnect; for formal, signal connectivity, and
  a secure-verification check for leakage of secure data [OTChip]. It lists
  three configurations: stub CPU, bare-metal software tests and interconnect
  integration [OTChip]. Parts of that page are template placeholders [OTChip].

## Reuse

- A base library of UVM classes sits under all testbenches; a second library
  for the project's standard IP interface sits on it; the block testbench is
  the third layer; plug-and-play components (interface agents, utilities,
  memory models) sit beside them [OTDV].
- The second library supplies an environment, configuration, scoreboard,
  coverage, virtual sequencer and base sequence as type-parameterised
  classes that a block extends [OTCip]. The base sequence carries common
  tests: register tests, bus error tests, bus integrity errors and reset with
  traffic in flight [OTCip]. The UART bench is built this way [OTUart].
- Common security countermeasures are checked by shared framework code, and
  custom countermeasures case by case [OTDV]. In simulation the library finds
  the common primitives, injects a fault into each and checks a fatal alert
  fires [OTCip].
- Assertion monitors written for FPV are reused in simulation where possible;
  an example is the bus protocol checker [OTDV]. In DV, assertions live in
  interfaces bound to the design so they do not change it [OTDV].
- A generic testbench plus generated parameter sets is the plan for blocks
  with many instantiated flavours; the interconnect is the planned example
  [OTDV].
- Coverage: pre-verified sub-blocks are black boxed, with toggle coverage on
  their IO only, and exclusions are not reused from block to chip because each
  closes separately [OTDV].

## What goes to formal, what to simulation

Read from the sources, one case each:

- Bus protocol compliance of a block: the UART page gives simulation the
  feature verification and FPV the TileLink device protocol compliance
  [OTUart]. The bus protocol checker is bound into the simulation bench
  too [OTUart].
- Chip connectivity: the chip page puts signal connectivity "excluded from
  functional DV" under FPV [OTChip]. Connectivity tests check system-level
  connections exhaustively from a table, run through the same simulation-
  management tool [OTFpv].
- Security primitive faults: both. Simulation injects faults and checks the
  alert [OTCip]. FPV does the same by cutting the output of a state machine,
  or black-boxing a counter or a second state generator, and letting the tool
  drive it, so alert assertions that are unreachable in normal runs become
  reachable [OTFpv].
- Everything else the sources assign to simulation: register tests, smoke and
  stress tests, system scenarios, coverage closure [OTDV] [OTChip].
- Why a feature fits one technique better is not stated by the sources
  (inference: formal suits exhaustive local properties and connectivity;
  simulation suits end-to-end data checking and software-driven scenarios).

## Features with no method

- The project's coverage exclusions have a category for features the design
  does not support, and one for low risk items that a collective upfront
  decision, with software, architecture, design and DV agreement, leaves
  unverified because of resources. The explanation is mandatory for both
  [OTDV]. This is how the project records a feature with no verification
  method (inference from that rule).
- A feature already covered in another bench is excluded as EXTERNAL, with a
  mandatory explanation [OTDV].
- In the first review the DV document and testplan are reviewed with the
  designer, DV peers, leads, the chip-level team, software and the architect.
  The source says the review can find missing items in the specification and
  the testplan [OTDV].

## Common failure modes

- A feature in the specification with no test, assertion or coverage item
  (the card). The testplan's purpose is to list tests for all listed
  features [OTDV].
- Reuse by copying: a block bench that rebuilds common checks instead of
  extending the library. The library's stated aim is to maximise code reuse
  [OTCip].
- Closing coverage at chip level on blocks already verified. The source
  reduces the goal to IO toggle and connection tests [OTDV].
- An FPV result taken as covering a simulation feature: the two documents
  assign different features to each (inference from [OTUart]).

## How a result is checked

- Every feature has a verification method (the card's own check). A table of
  feature, method (simulation test, assertion, formal property, excluded with
  reason) and evidence is one way to state it (inference); the project's
  testplan is the nearest open example [OTDV].
- Each exclusion carries its category and reason [OTDV].
- The split is reviewed with the people who consume the block [OTDV].

## Sources

- [OTDV] Techniques, artefacts, levels, reuse layers and exclusions.
- [OTFpv] Formal runs, connectivity tests and security fault injection.
- [OTCip], [OTUart], [OTChip] Library structure, a block bench and a chip bench.

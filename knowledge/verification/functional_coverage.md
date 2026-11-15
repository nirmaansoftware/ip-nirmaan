---
id: verification/functional_coverage
skill: functional_coverage
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
  - open | lowRISC, OpenTitan DVSIM testplanner tool (Apache 2.0) [OTPlan] | https://opentitan.org/book/util/dvsim/doc/testplanner.html
  - open | lowRISC, OpenTitan Hardware Development Stages (Apache 2.0) [OTStage] | https://opentitan.org/book/doc/project_governance/development_stages.html
  - open | Verilator manual: Simulating, Coverage Analysis [VCov] | https://verilator.org/guide/latest/simulating.html
  - open | Verilator manual: Input Languages [VLang] | https://verilator.org/guide/latest/languages.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K4 session (wave 2 knowledge batch, plan row W2-K4, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the coverage tool this skill holds is available; this document is knowledge, not evidence.

# Functional coverage

Planning and reading coverage that says which specified behaviours the tests
reached, and what this repository's coverage tool does and does not measure.
Tags in brackets name the sources above; a line marked "inference" is this
document's own reasoning; a line marked "gate" names the repository code that
backs it.

## What it is and why it is separate from code coverage

- Functional coverage needs cover points and covergroups written by the
  designer or verification engineer, so it is called explicit coverage. Code
  coverage is generated from the RTL and costs no extra writing [OTDV].
- A cover point records that a signal met an interesting value or sequence of
  values. A cross records that several points were hit together, for example a
  FIFO full while a write is requested. Cover properties written in SVA record
  events and sequences, for example a valid and ready handshake [OTDV].
- These are sampled in the testbench's reactive parts, such as monitors and
  scoreboards, or embedded in the RTL [OTDV].
- OpenTitan's AND gate example shows why both kinds are needed. Two input
  combinations give full code coverage of an AND gate, yet the design could be
  an OR gate; a cross of inputs and output tells them apart. In the other
  direction, functional coverage written for one gate does not notice that a
  second gate was added and never exercised, which code coverage shows [OTDV].
- OpenTitan's ranking of what each metric says: functional coverage speaks to
  whether the design works as specified, and code coverage to whether the plan
  or the design has gaps [OTDV].

## How it is planned and written

- List the covergroups in the verification plan with a name and a description
  of the behaviour captured, ideally with the points and crosses, so reviewers
  can read it. The name must match the written covergroup, and OpenTitan's
  style suffixes it with `_cg` [OTPlan].
- Derive each point from a feature or corner case the specification names,
  not from what the RTL happens to do (inference).
- Cross only the points whose combinations matter. A cross grows as the
  product of its points, so an unbounded cross is slow to close and mostly
  holds illegal or impossible combinations (inference).
- Mark illegal values so that the simulator reports an error if one is seen
  [OTDV]. That makes a covergroup a checker as well as a counter (inference).
- OpenTitan's second verification stage asks for all planned covergroups to
  be written, and its last for 100 percent functional coverage with waivers
  [OTStage].

## Closing a gap

- A hole is closed in one of three ways: add stimulus, change the design to
  remove logic that cannot be reached, or waive it [OTDV].
- OpenTitan waivers carry a category tag (unreachable, non-RTL, unsupported,
  external, low risk) and a written reason for the last three; the designer
  signs off each in review [OTDV].
- OpenTitan's unreachability tool does not support assertion or functional
  coverage [OTDV], so a functional hole needs a human argument that the
  combination cannot occur (inference).
- Do not close a hole by writing the bin out of the covergroup. Keep the bin
  and record the waiver where a reviewer sees it (inference).

## What this repository measures

- `coverage.read` builds the run with Verilator's line and toggle coverage
  only and reads line, toggle and branch percentages over the design files
  (gate: src/nirmaan/integrations/eda.py:595;
  src/nirmaan/integrations/eda_parsers.py:544-590; src/nirmaan/company/tools.py:137-143).
- Verilator translates covergroups only when built with `--coverage` or
  `--coverage-user` [VCov]. The gate passes neither, so a covergroup in a
  testbench is not read by this tool (inference from eda.py:595 and [VCov]).
  The same applies to cover properties, which [VCov] places under the same
  two options.
- Verilator's own language page calls its functional coverage partial: it
  lists covergroup, coverpoint, bins, cross coverage and transition bins as
  supported [VLang]. Anything else a testbench uses may not be read, even
  under those options (inference).
- The tool states its numbers as percentages of points hit at least once,
  never rounded up, and it fails a run whose testbench fails or whose design
  files hold no point (gate: src/nirmaan/integrations/eda_parsers.py:544-590).
- The plan format treats a `coverage_point` item as proven only by a coverage
  measurement (gate: src/nirmaan/company/traceability.py:52-53). With this tool
  that measurement is code coverage (inference), so a functional claim needs
  a checker in the testbench as well: a self-checking test that tallies each
  scenario and fails if one never happens (inference).

## Common failure modes

- Cover points written from the RTL's signals and so true by construction,
  which proves nothing about the specification (inference).
- Reporting the count of bins hit without the bins that were waived or
  excluded (inference).
- Reading a covergroup percent with a different `at_least` threshold than the
  plan meant; Verilator records the threshold and `verilator_coverage` uses it
  to decide whether a bin is covered [VCov].
- A cross with no bins for illegal combinations, so an illegal value looks like
  an uncovered hole (inference).
- Treating 100 percent functional coverage as done while code coverage shows a
  block untouched [OTDV].

## How a result is checked

- Ask which tool measured it and with which options. Percentages from this
  repository's `coverage.read` are code coverage, not functional coverage
  (inference from the gate lines above).
- List every cover point in the plan, with the test that reaches it and the
  scenario it stands for (inference).
- Read each waiver and its category tag [OTDV].

## Sources

- [OTDV] Functional coverage, exclusions, and why both kinds are needed.
- [OTPlan] Covergroups in the testplan and the naming rule.
- [OTStage] The verification stages and their coverage criteria.
- [VCov], [VLang] What Verilator's coverage options and language page say.

---
id: verification/hardware_fuzzing
skill: hardware_fuzzing
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | Trippel, Shin, Chernyakhovsky, Kelly, Rizzo and Hicks, Fuzzing Hardware Like Software (arXiv 2102.02308, open access) [HWF] | https://arxiv.org/abs/2102.02308
  - open | Verilator manual: Executable and Argument Reference (the --x-assign and --x-initial options) [VArg] | https://verilator.org/guide/latest/exe_verilator.html
  - open | Verilator manual: Input Languages (Unknown States) [VLang] | https://verilator.org/guide/latest/languages.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K4 session (wave 2 knowledge batch, plan row W2-K4, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# Hardware fuzzing

Using a coverage-guided software fuzzer to generate test inputs for an RTL
design, and what the fuzzer needs from the testbench to find anything. Tags in
brackets name the sources above; a line marked "inference" is this document's
own reasoning. No repository tool runs a fuzzer, so no gate line is cited.

## What it is

- Fuzzing here means translating the RTL to a software model and fuzzing that
  model. The design is turned into a C++ model with Verilator, compiled with a
  testbench and instrumented for coverage, and a coverage-guided software
  fuzzer then mutates input files, keeps the ones that reach new coverage,
  discards the rest and saves the ones that crash [HWF].
- It is a coverage-directed alternative to constrained random stimulus. Random
  stimulus has no knowledge of what it has already reached; the fuzzer mutates
  inputs that reached new regions of the design [HWF].
- The paper's claim is that coverage of the software model tracks coverage of
  the hardware: it reports software line and basic block coverage and HDL line
  coverage rising together over time on four OpenTitan blocks [HWF].

## What the fuzzer needs

- An oracle. The paper states that there is no hardware sanitizer, so the
  engineer must supply invariants or a golden model for the fuzzer to find
  crashing inputs [HWF]. A crash is made when an assertion fires (the process
  is sent an abort signal) or when the golden model and the design disagree
  [HWF]. A fuzz target with no oracle only grows coverage and finds nothing.
- A harness that turns a file of bytes into a sequence of inputs over time.
  Hardware needs many inputs in order to change state, so one input per file
  does not work; the paper's harness reads bytes, maps them to input ports and
  advances the clock, repeating until the file is empty [HWF].
- For a block on a bus, the paper decodes the file as bus transactions with a
  small instruction format: an opcode, then an address and data where the
  opcode needs them, for wait, read and write. Variable length instructions
  did better with its fuzzer, which favours small files and so longer
  sequences from the same bytes [HWF].
- A reset. The model must be reset before each input. The paper measured the
  cost of repeated resets and found it matters mostly for very small designs
  [HWF].
- Coverage instrumentation only on the design. In the paper's lock designs,
  instrumenting only the design was never slower than instrumenting the
  testbench and simulation engine too, and was faster for the smaller ones
  [HWF].

## Making a finding useful

- Replay needs the same random choices. Verilator replaces unknown values and
  initial values with chosen constants, and with the `unique` setting of
  `--x-assign` and `--x-initial` the choice follows a seed given at run time;
  the manual says to print the seeds used so a failure can be rerun [VArg].
  Record the input file, the seed and the build options with each finding
  (inference).
- Verilator is mostly a two-state simulator [VLang], so a fuzz run does not see
  unknown propagation. A bug that shows only as an X in a four-state simulator
  can be missed (inference).
- A saved crash is an input, not yet a bug report. Reduce it, replay it, name
  the assertion or model mismatch that fired, and decide if it is a design
  bug, a harness bug or an input the specification does not allow (inference).

## What it does not find

- The paper lists limits: RTL has no analog behaviour, so side-channel
  leakage that depends on it is outside what this approach finds [HWF].
- A property that holds only after input patterns the fuzzer cannot build
  from the grammar. If the grammar cannot express an operation, no input
  reaches it (inference).
- Anything the oracle does not check (inference).

## Evidence the source reports

- On a family of configurable lock state machines, fuzzing reached the unlock
  state two orders of magnitude faster than the constrained random testbench
  the authors wrote for comparison, for medium and large locks [HWF].
- On four OpenTitan blocks (AES, HMAC, KMAC, and the RISC-V timer), with an
  empty seed and one hour of fuzzing, it reached over 88 percent HDL line
  coverage on three of the four [HWF].
- Both are results on the authors' designs and harness. They do not say what
  a fuzzer would find on another design, or that its coverage means the
  specification was checked (inference).

## Common failure modes

- Counting coverage reached as bugs found.
- A harness that resets the design through inputs the fuzzer can also mutate,
  so it fuzzes the reset rather than the block (inference).
- Findings that cannot be replayed because the seed or build options were not
  saved.
- Fuzzing a design whose invalid inputs are silently ignored, so most mutated
  files exercise nothing new (inference).

## How a result is checked

- Replay each finding from its saved input and confirm the same oracle fires
  (inference).
- Ask what the oracle covers: list the assertions or the model's compared
  outputs (inference).
- Compare the coverage reached with the verification plan's list of scenarios;
  fuzzing adds stimulus and does not replace the plan (inference).

## Sources

- [HWF] The pipeline, the harness and grammar, the limits and the results.
- [VArg], [VLang] How Verilator sets unknown and initial values and why a seed
  is needed to replay.

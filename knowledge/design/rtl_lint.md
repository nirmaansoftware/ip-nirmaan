---
id: design/rtl_lint
skill: rtl_lint
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | Verilator manual: Warnings [VLW] | https://verilator.org/guide/latest/warnings.html
  - open | Verilator manual: Arguments (verilator executable) [VLA] | https://verilator.org/guide/latest/exe_verilator.html
  - open | lowRISC, Verilog Coding Style Guide (CC BY 4.0) [lowRISC] | https://github.com/lowRISC/style-guides/blob/master/VerilogCodingStyle.md
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: RETRO-A5 session (retrospective action A5, item P3-K3, 2026-11-15)
checker: pending, a different session reads the sources in P3-C3 and writes the check record
---
Practising: the lint tool this skill holds is available; this document is knowledge, not evidence.

# RTL lint

Static checks on synthesizable RTL with Verilator, how this repository's lint
gate reads their result, and how to fix or waive a finding. Tags in brackets
name the sources above; a line marked "inference" is this document's own
reasoning; a line marked "gate" names the repository code that backs it.

## What the gate runs

- `lint.run` runs `verilator --lint-only -Wall`, adding `--top-module <top>`
  when a top is given, over the listed sources (gate: src/nirmaan/integrations/eda.py:427-428;
  backend registered at eda.py:803). It is the only lint backend the tool
  has, so a rule Verilator does not have is not checked (inference).
- `--lint-only` checks the files and makes no other output [VLA]. `-Wall`
  enables the style warnings that are off by default, together with the lint
  warnings, but "excludes some specialty warnings" [VLA]; a clean run is
  therefore not every possible check (inference).
- The result passes only when Verilator exits 0 with no error and no
  warning; the summary then reads "lint clean: 0 errors, 0 warnings" (gate:
  eda_parsers.py:92-103). One warning fails the run. There is no severity
  threshold and no accepted-warning list in the gate.
- The tool's inputs are the sources, an optional top, and the runner's backend,
  workdir and timeout; it takes no warning option (gate:
  src/nirmaan/company/tools.py:55-56, 68-72, 129-130). So `-Wno-<message>`, `-Wno-lint`
  and `-Wno-fatal` cannot be passed to it; a waiver can only be written in the
  RTL (see Waivers).

## What -Wall turns on that surprises a first run

Each warning below is in Verilator's list [VLW]; because the gate runs
`-Wall`, each one fails `lint.run` (inference from the gate lines above).
Checked on Verilator 5.052 with small files on 2026-11-15: an unused input
bit, a module whose name differs from its file name, a 4-bit value assigned to
a 2-bit register and an incomplete combinational `if` each failed the gate's
parser.

- DECLFILENAME: a module name must match its file name, with path and
  extension stripped [VLW]. A file `foo.v` holding module `bar` fails.
- UNUSEDSIGNAL and UNDRIVEN: a signal or bits of one that are never used, or
  have no source, are style warnings [VLW] [VLA]. An unused input bit fails.
  An intentionally unused signal is better named so the tool's unused-name
  pattern matches (default `*unused*`) than waived [VLW].
- WIDTH (WIDTHTRUNC, WIDTHEXPAND and kin): operands or part selects of
  different widths. The fix is to resize the constant, use `'0` or `'1`, take
  a part select to narrow, or concatenate to widen [VLW]. The lowRISC guide
  asks for explicit widths on number literals and matching widths on
  port connections [lowRISC].
- LATCH: a signal not assigned on every path of a combinational block infers
  a latch; for an intended latch use `always_latch` [VLW]. lowRISC discourages
  latches and says never to infer one inside a function [lowRISC].
- BLKSEQ and COMBDLY: a blocking assignment in a clocked block, and a delayed
  (non-blocking) assignment in a combinational block. A clocked block uses
  `<=` only and a combinational block `=` only, never mixed [VLW] [lowRISC].
- BLKANDNBLK: one variable driven by both kinds of assignment is reported as
  an error [VLW].
- CASEINCOMPLETE, CASEOVERLAP and CASEX: a case with an unmatched value,
  overlapping items, or `casex`. Add a default, or cover every value; use
  `casez` with `?` rather than `x` [VLW]. lowRISC says to avoid
  case-modifying pragmas [lowRISC].
- IMPLICIT and PINMISSING: a net implicitly declared by an instance, and an
  instance that omits a pin. Connect every pin, with `.pin()` for an empty one
  [VLW].
- SYNCASYNCNET: the same net used as an asynchronous reset in one flop and as a
  synchronous reset in another. Mixing them is usually a mistake [VLW].
- MULTIDRIVEN: a signal driven from several procedural blocks, for example
  with different clocking [VLW].
- UNOPTFLAT: a signal that is circular as the simulator sees it though not per
  bit, such as a vector that feeds itself; split it into separate signals
  [VLW].
- SELRANGE: an index that can run outside the vector [VLW].

## Fix or waive

- Fix at the cause first. Verilator itself advises cleaning code, using inline
  `lint_off`, or using `-Wno-...` rather than `-Wno-fatal` [VLA].
- A waiver is a `// verilator lint_off <WARNING>` comment, paired with a
  `lint_on`, around the smallest region [VLW] (the repository's own bridge RTL
  waives WIDTH this way, for example src/nirmaan/integrations/firmware_soc/bridge_apb.v:34-44).
  Verilator advises against global disables, which remove all checking across the
  sources [VLW]. A misspelled metacomment is itself an error (BADVLTPRAGMA)
  [VLW], so a typo in a waiver fails the run.
  A `-Wno-<message>` option overrides any `lint_on` in the source [VLA]; the gate
  passes none.
- The gate only sees the log. A `lint_off` comment makes a warning vanish
  from the log, and the gate does not read the comment or its reason
  (gate: eda_parsers.py:92-103, docstring "waivers live in the RTL"). Whether
  a waiver has a rationale is a review question, not a gate result. lowRISC
  asks that every deviation carry a brief comment of justification, and a waiver
  pragma where appropriate [lowRISC].
- A blanket waiver (a whole file, or a warning off for the whole design) hides
  real findings. Waive one warning code over the lines that need it and
  say why in the comment (inference from [VLW] [lowRISC]).
- Do not hand-wave a warning as "only style": Verilator marks many as correct
  in simulation, but a latch, a width truncation or a race still changes the
  hardware [VLW].

## Common failure modes

- Treating a green lint as a design review: it finds nothing about function,
  protocol or timing (inference).
- Waiving a width or latch warning that is a real bug.
- A waiver left on after the code beneath it changed.
- A module renamed without its file, or an unused port kept for later.
- Fixing a warning by adding a signal that is itself unused.

## How a result is checked

- Run the tool on the final sources, with the same top, and read the log, not
  only the pass line: count waivers (`grep` for `lint_off`) and check each
  has a reason (inference).
- After any waiver or fix, run again; a fix can expose another warning
  [VLW].
- Run the simulator after a lint fix that changes behaviour, for instance a
  default case, a width or a latch (inference).

# Milestone 84 - Gate inputs that reach the host

A security fix. Design: `docs/GATE_INPUTS.md`. Tests:
`tests/test_gate_inputs.py`.

**The gap.** The M75 author found (#296) that the default harness's gates ran
content the eval seat wrote: a file's `entry` reached Yosys scripts as text, so
a new line or a `;` started a shell command; a testbench's `$system`, `$fopen`
and `$c` ran when it was simulated; an `.sby` could run `!` lines, `exec`,
embedded Python and shell words in its engines and options; constraints are
Tcl. Confirmed with marker files on the development machine's tools.

**The fix.** One module, `integrations/eda_guard.py`, of allow lists, called
from `eda.execute` for every run (`top`, paths, and the Verilog in `sources`,
`rtl` and `design`) and from the formal, equivalence and timing backends' own
checks. Refused input is a recorded failed run, "(refused, nothing ran)".

**The history.** `scripts/gate_input_history.py` found no committed trial or
fixture that used any of these constructs (209 seat files, 202 entries, every
one a plain name; the only refusals are 7 `.sby` with `[tasks]`, already
refused).

**Not changed.** Code by design (cocotb tests, firmware drivers) still runs as
the gate's own account with M53's isolation; `docs/GATE_INPUTS.md`, section 4,
says why that is not enough on a personal machine. The harness fingerprint is
unchanged. No count changes.

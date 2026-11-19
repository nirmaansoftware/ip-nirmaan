# Milestone 91 - The compile screen

Gate SC1 of the council record `council/records/2026-11-19-seat-c-live-refusal.md`
(decision 4). Seat C is compiled, assembled and linked as the runner in
`fw.build` and `fw.test`. The record found that a seat file including the
committed reference driver by an absolute or `..` path compiles clean, and so
does a file-scope `.incbin` of any file the runner can read, and it closed
that before any live trial of a case that compiles seat C, by a screen or by
compiling as the seat account. Design: `docs/COMPILE_SCREEN.md`. Tests:
`tests/test_compile_screen.py`.

**The choice.** The screen. Compiling as the seat account cannot meet its own
condition for the held-out test, which is compiled together with the seat's
header and so would have to be read by the seat account; and the account
alone does not stop an include of a file it may read.

**The screen.** `src/nirmaan/integrations/compile_screen.py`, run in the check
of every backend that compiles a job's C (`fw.build` on the host and for
RISC-V, `fw.test`, `fw.cross_build`, `fw.soc_test`) and by the object screen
of gate WF16 before it compiles. It refuses, before anything compiles, a
directive outside a short list (`#line`, line markers, `#include_next`,
`#embed`, pragmas other than `#pragma once`), trigraphs, `__has_include` and
`_Pragma`, an include written with an absolute or `..` path, any file the
compiler's own dependency list (`-M -MG`) places outside the run's source
folders, the harness, the run's directory and the compiler's include
folders, and, in the compiler's assembly of each C file, an asm statement or
an assembler directive that reads a file (`.incbin`, `.include`) or could
spell one. `firmware.compile_flags` is the one place the strict compile's
flags are built, so the screen sees exactly the build's include path.

**What is recorded.** Nine must-refuse fixtures and two absolute includes,
each refused by the backends with nothing compiled, `fw.test` among them,
and a canary run (a runner-only file reached by an absolute include, a
macro-built include and `.incbin`) whose value is in no file the run left and
not in its record; every committed C file the backends compile passes the
screen, so no committed result changes. The fingerprints are unchanged
(default `sha256:0ef27db1...`, whole flow `sha256:d90b3c18...`): no file a
fingerprint digests and no tool definition changed, and `docs/GATE_INTEGRITY.md`
says the gate changed without a fingerprint change.

**Not changed.** The live refusal of every case that runs seat C (exit 6,
`scripts/live_eval_ci.py`) stays; lifting it is gate SC7, after SC1 to SC6.

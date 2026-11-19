# The compile screen (M91, gate SC1)

Council record `council/records/2026-11-19-seat-c-live-refusal.md`, decision 4
and gate SC1. Seat C is compiled, assembled and linked as the runner in
`fw.build` and `fw.test`, so whatever the compiler or the assembler reads for
it, it reads as the runner. The record found (fact 9) that a seat file that
includes the committed reference driver by an absolute path or a path with
`..` compiles clean under the strict flags, and so does a file-scope asm line
that makes the assembler copy any file the runner can read into the program.
Decision 4 closes that before any live trial of a case that compiles seat C,
by one of two measures. This milestone is the first: a screen before anything
of the job is compiled.

Code: `src/nirmaan/integrations/compile_screen.py`. Tests and the record:
`tests/test_compile_screen.py`, whose outcomes the CI test job keeps in its
JUnit file (each fixture's test by name; each tool-backed test also prints a
`COMPILE-SCREEN-` line under `pytest -s`). Must-refuse fixtures:
`tests/fixtures/fw/compile_screen/`. First recorded: CI run 44557443798 (head
636b02d), artifact `junit-test-1`: all 42 tests passed, none skipped.

## Why a screen, not the compile as the seat account

The other measure runs every compile step whose input holds seat text as the
seat account, with a recorded reach test showing that account cannot read the
reference answer, the held-out test or a runner-only canary. It cannot meet
its own condition for the held-out test. The held-out test is compiled
together with the seat's header (`#include "axi4_lite_regs_drv.h"`), so its
compile step holds seat text and would run as the seat account, which must
then read the held-out test to compile it; a seat header compiled in that same
step can include it again by name. The account alone also does not stop an
include of a file the account may read (the record's fact 9, eda-tooling). The
screen refuses by what the C pulls in, whoever compiles it, needs no change
to the job's grants, and is the smaller change (eda-tooling's position).
Decision 4, item 5 still asks, before the first register block trial, for the
compile as the seat account or security's recorded reason for staying with
the screen; that choice is not made here.

## What it refuses

Every backend that compiles the C a job names runs the screen in its check,
before any step: `fw.build` (host `cc` and RISC-V GCC), `fw.test`,
`fw.cross_build` and `fw.soc_test`. It screens the job's C files and headers
and the agreement unit of a `map`, the seat's and the case's alike (the
backend cannot tell them apart, and a case file is committed C that passes).
The object screen of gate WF16 runs it before its own compile, without the
asm statement rule, since it refuses asm in the seat's lines itself. A
refusal is the check's reason: the run is recorded as failed with it, and
nothing of the job is compiled (`eda.execute` returns before the first step).

1. **The written text** of each file the job names, and of each file it pulls
   in from the run's source folders or the run's own directory, read as the
   preprocessor reads it (lines joined at a backslash and a newline, comments
   removed, `%:` counted as `#`): a directive other than `#include`,
   `#define`, `#undef`, `#if`, `#ifdef`, `#ifndef`, `#elif`, `#else`,
   `#endif`, `#error` and `#pragma once` (so `#line`, a line marker such as
   `# 1 "file" 1 3`, `#include_next`, `#import`, `#embed`, `#ident`, any
   other `#pragma`); a trigraph; `__has_include`, `__has_include_next`,
   `__has_embed` or `_Pragma`; an `#include` whose written name is absolute
   or has a `..` part. The written names of the job's own files are checked
   before the compiler opens anything.
2. **What the compiler pulls in**, from its own list (`-M -MG`, so a name a
   macro builds is listed too): every file must resolve inside the run's
   source folders (the folder of each file the job names), the harness, the
   run's own directory (the harness copy, the header generated from a map) or
   the compiler's own include folders (and, on macOS, its SDK).
3. **The compiler's assembly** of each C file (`-S`, with the build's own
   flags, so it is what the build would assemble): an asm statement, inline
   or at file scope, however it was written (the compiler marks each one, so
   asm built by token pasting is caught), or an assembler directive that
   reads a file or could spell one (`.incbin`, `.include`, and the macro
   directives `.macro`, `.irp`, `.irpc`, `.rept`, `.altmacro`, `.purgem`,
   `.exitm`, `.endm`, `.endr`), anywhere in the text, so an asm label that
   carries one into the assembly is caught.

An asm label that only renames a symbol (`__asm__("name")` on a declaration)
reads no file and is not refused here. Two committed fixtures use one and
pass `fw.test` today (`axi4_lite_regs_test_strict_latency.c`,
`axi4_lite_regs_drv_strict_latency.c`, the route of
`tests/fixtures/fw/reach/simulator_clock_probe.c`); decision 4, item 4 keeps
every committed fixture's result, and the object screen refuses that route in
the whole-flow checks.

## What is recorded

Decision 4, item 3: the measure is claimed only for what a recorded
must-refuse fixture shows it stops. Recorded refused, by the backends, in the
test job of CI (GCC on ubuntu-24.04): an include by an absolute path of the
reference driver (written by the test, since the checkout's path differs
from machine to machine, with quotes and with angle brackets), an include
with `..` of it (`include_dotdot.c`), the same named by a macro
(`include_computed.c`), the assembler route at file scope (`incbin.c`), with
the asm keyword built by token pasting (`incbin_pasted.c`) and carried by an
asm label (`incbin_label.c`, GCC only: Clang writes such a label as a quoted
symbol name, which never reaches the assembler as a directive), and `#line`
written plainly (`line_directive.c`), as a line marker (`line_marker.c`),
spelled with a digraph, a comment and a line splice (`line_spelled.c`) and
with a trigraph (`line_trigraph.c`). `fw.test` refuses before it compiles or
runs anything. The canary run: a runner-only file (mode 0600) with a random
value, reached by an absolute include, a macro-built include and `.incbin`;
each is refused, and the value is in no file the run left and not in its
record. No fixture that reaches for a credential is committed; the canary
stands in for it (decision 4, item 3 leaves that choice to security).

Decision 4, item 4: `test_every_committed_c_file_passes_the_screen` screens
every committed C file and header the backends compile (each fixture folder
together, each held-out test with the reference driver it is built with), and
none is refused, so each build runs exactly the steps it ran before and gets
the result it got before. The screen sits in no file a fingerprint digests
and in no tool definition (`test_the_screen_changes_no_fingerprint`): the gate
changed without a fingerprint change (`docs/GATE_INTEGRITY.md`, section 3).

## What it is not

It is not confinement, and it is claimed for nothing beyond the fixtures
above.

- The screen's own preprocessor and compiler runs are the runner's. Before the
  list of item 2 is checked, the preprocessor has opened what the seat named
  (the written names of item 1 are checked first, so a plain absolute or `..`
  include is never opened). Only file names are read back; a failure there is
  refused with the seat file's own first error and nothing of another file,
  and the screen's assembly is deleted whatever it found (Clang copies an
  `.incbin` file into it).
- A seat header can break the compile of the held-out test it is included
  in, so that a compiler diagnostic quotes the held-out test's own lines.
- The program `fw.test` builds holds the held-out test it is linked with,
  and executes in the same process (gate WF18 of the G3 record is the
  register block's answer).
- A seat could name a file inside the allowed folders that it was not meant
  to read: the folder of every file the job names is allowed, the held-out
  test's folder included (the held-out test and `driver_api.md`, which the
  seat is given).
- Measured with GCC on ubuntu-24.04, the toolchain of the live evaluation
  jobs; with another compiler the markers the assembly rule reads may differ.

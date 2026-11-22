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
Decision 4, item 5 asks, before the first register block trial, for the
compile as the seat account or security's recorded reason for staying with
the screen. This pull request proposes the screen; the proposed reason is
below ("Decision 4, item 5: the register block"), pending a security record.

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

## Decision 4, item 5: the register block (gate SC9)

The record (decision 4, item 5, and gate SC9) asks, before the first trial of
`flow/axi4-lite-regs-driver`, that the compile of seat text run as the seat
account, or that security record its reason for staying with the screen.
This pull request proposes **the screen**, with the compile left with the
runner. No security seat record backs this choice yet: the security seat
(`council/security.md`) has not recorded a decision here, and gate SC9 stays
open until it does. The reasons below are the author's proposal for that
seat to confirm or reject:

1. The account route cannot meet its own condition in checks 5 and 6 (fact).
   The flow's held-out test includes the seat's header
   (`evals/flow/axi4_lite/held_out_test.c`, `#include "axi4_lite_regs_drv.h"`),
   the held-out scorers pass it from the checkout in place, and the seat
   account may not read the checkout (`--deny-read`,
   `.github/actions/live-eval-seat/action.yml`). Compiled as the seat
   account, that step must be given the held-out test to read, which breaks
   the condition that the account cannot read it, and a seat header
   compiled in the same step can include the test again by name.
2. Once built, the held-out test is linked into the program and executes in
   the same process as seat C, as the seat account (`_cosim_steps` in
   `src/nirmaan/integrations/firmware.py`). So keeping the held-out test from
   the compile step would gain no secrecy for checks 5 and 6 (inference);
   gate WF18 of the G3 record is the answer there, not the account.
3. The routes decision 4, item 3 counts are recorded refused by the screen,
   in every backend the register block uses (fact: the fixtures above, and
   the gate SC9 tests below). The account alone stops neither the `#line`
   route nor asm itself, so the screen would be needed under the account
   route anyway.
4. What the account would add (inference): the files the screen's own
   preprocessor opens as the runner before its list is checked (only file
   names come back, and only the seat file's own first error), and any
   file-reading route the screen does not name, for files in the folders the
   seat account may not read. That is real defence in depth; it is not a
   route the record found, and it is declined on purpose, not because it
   adds nothing.
5. Neither measure stops a seat header breaking the held-out test's compile
   so that a diagnostic quotes it, an include of a file in an allowed folder
   (the held-out test's folder also holds `axi4_lite_regs_tb.v`), or address
   arithmetic inside the program (fact; "What it is not", below, and
   `docs/GATE_INTEGRITY.md`, section 3).
6. The account route needs a new root mode that takes a compiler's argument
   list from the runner: the wrapper's `run-built` accepts only a program the
   runner built in the run's directory (`scripts/live_eval_seat.py`), which a
   system compiler is not. It would also need read grants on the seat's
   files, the harness (which lives in the checkout the account may not read)
   and the generated map header, and objects written by the seat account
   handed back to the runner's link step and to the object screen. Security
   The author's own assessment, pending a security seat record, is a
   moderate added risk in code that runs as root, for little beyond reason 4.

Proposed conditions, each before the first register block trial:

1. A CI record, on the build the trials will use, shows every must-refuse
   fixture refused. Run 44557443798 (636b02d) no longer is that build:
   `firmware.py` changed after it (gates SC2 and SC4). The test job of the
   pull request that recorded this choice is the record on its head; a later
   change to `compile_screen.py`, `firmware.py`, `firmware_riscv.py` or
   `object_screen.py` before the first register block trial needs its own.
2. The `#line` route recorded refused through the object screen (decision 2,
   item 2): `line_asm.c`, a `#line` line followed by an asm statement, is
   refused by the compile screen the object screen runs first, and nothing
   is compiled (`test_the_line_route_of_fact_9_is_refused_before_the_object_screen_compiles`).
3. Each of the two routes a seat header can carry into the held-out test's
   own compile (`seat_header_incbin.h`, `seat_header_line.h`, each copied in
   as the seat's `axi4_lite_regs_drv.h` beside the reference driver and map)
   is refused by `fw.test` before it compiles or runs anything, by the object
   screen, and in the compile of the header, the map and the held-out test
   alone (`test_a_seat_header_route_into_the_held_out_tests_compile_is_refused`).
4. The pull request that closes gate WF17 for the register block records
   this reason (by citing this section), and the documents keep the limits
   of reasons 4 and 5.
5. The choice is revisited if any fixture stops being refused or the
   toolchain changes from GCC on ubuntu-24.04.

Decision 2, item 1 (gate SC9): every check that compiles seat C in the
register block flow runs the screen.
`test_every_check_that_compiles_seat_c_in_the_register_block_flow_runs_the_screen`
reads the tools from the data (the case's held-out checks and the firmware
stage's before-review checks of the planned workflow): `fw.build`, `fw.test`,
`fw.cross_build` and `fw.soc_test`, and every backend of each (host `cc`,
RISC-V GCC, Verilator co-simulation, the RV32I cross build, the PicoRV32 SoC)
refuses an include of the reference driver by an absolute path in its check,
before any step. The other tools of the flow (`simulator.run`,
`regmap.verify`) compile no seat-written C.

Never claimed: that seat C is confined, sandboxed, isolated or "built and run
as another account" (it is compiled as the runner after the screen); that the
screen stops anything beyond its recorded fixtures, or that its own runs read
nothing as the runner; that the held-out test or its folder is unreachable by
seat C; anything about the plan credential beyond the recorded probes
(`evals/flow/credential_test_record.json`); any result for Clang or macOS.

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

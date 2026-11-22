# Gate inputs that reach the host (M84)

A gate runs open-source tools over files a seat wrote. Seats are model output,
so a gate must not run anything a file asks of the machine outside the run:
the founder's Mac, or a CI runner. Before M84 several gates did. M84 refuses
such input before any step runs, in one module,
`src/nirmaan/integrations/eda_guard.py`, called from `eda.execute` (every
backend) and from the formal, equivalence and timing backends' own checks. A
refused input is a recorded failed run whose summary says why and ends
"(refused, nothing ran)"; no step runs and no log is written.

Every check is an allow list: what it does not name is refused, so a tool
release that adds a way out does not open one here.

Tests: `tests/test_gate_inputs.py`. Each must-fail test gives a real backend a
file whose payload would create a marker file in the test's own temporary
directory, and asserts the run is refused and the marker is not there. Three
controls bypass the check and assert the marker does appear (Yosys through
`top`, Verilator through `$system`, SBY through a `!` line), so the payloads
are live. Must-pass tests run every committed Verilog file, single-task `.sby`,
`.eqy` and `.sdc` under `tests/fixtures/` and `evals/` through the checks, and an
ordinary testbench, setup and synthesis through the real tools.

## 1. What was exposed

Found by the M75 author (#296); confirmed on Yosys 0.69, SBY 0.69,
Verilator 5.052 and Icarus Verilog 13 with marker files.

| Gate | Seat-controlled input | What ran |
|---|---|---|
| `synth.run` (yosys, yosys-liberty), `dft.*`, `sta.run` with `sources` | a file's `entry`, passed as `top`, written into the Yosys script as `synth -top <top>` | a new line then `!cmd`, or `; exec -- cmd`: a shell command |
| `simulator.run` (icarus, verilator-sim), `test.run` | the testbench, which the M53 testbench rule let use `$system`, `$fopen`, `$c` and DPI | `$system` (Verilator; Icarus builds that define it), `$fopen`/`$fwrite` to any path, `$c` C++ (Verilator), a C++ source beside the Verilog (Verilator compiles it in) |
| `regmap.verify`, `fw.test`, `fw.soc_test` | the RTL (`rtl`), compiled by Verilator into the program it runs | the same constructs in the RTL, and a C or C++ file given as RTL (Verilator compiles it in) |
| `formal.run`, `formal.cover` | the `.sby` | `[script]` lines starting with `!`, or calling `exec`, `script`, `tcl`; a `--pycode-begin--` block (Python SBY runs as it reads the file); engine words and option values (SBY joins them into shell command lines unquoted); `[files]` destinations outside the run |
| `equivalence.run` | the `.eqy` | M69 refused `!`, `exec`, `tcl`, `python`, `script`, `plugin` and writes; other Yosys commands that run programs (`abc -exe`, `show -viewer`) and a strategy's engine words were not refused |
| `sta.run`, `pnr.run` | the constraints (`sdc`), which OpenSTA and OpenROAD read as Tcl | any Tcl, `exec` included |

`lint.run` runs nothing from its sources, but its `top` is checked too, as is
every run's. M75's screen (`runtime/seat_tools.py`, `screen`) refuses such
files on the `tools-in-loop` variant's in-loop calls only; it is unchanged,
and the runs behind it now get these checks too, as every run does. `coverage.read` (M70) and the cocotb backend's HDL (M72) already
refused `$system`, `$fopen`, `$c` and DPI in every source.

## 2. The checks

- **`top`** is a plain module name (`[A-Za-z_][A-Za-z0-9_$]*`), and no file in
  `sources`, `rtl` or `design` has a quote or a control character in its path.
- **Verilog**: every file in `sources`, `rtl` and `design`, whatever its name
  (Icarus and Verilator read a file of any other name as Verilog), and every
  file a `.sby`'s `[files]` names, is checked as Verilog; `rtl` and `design`
  take files with a Verilog suffix only. A firmware driver in `sources` is
  checked too; every committed C file passes (no `$` name, no backtick). The checks: the system tasks and functions in `SAFE_SYSTEM` only
  (display, severity, time, arithmetic, random, plusargs, assertions and
  formal, waveform control); `$dumpfile` only with a plain file name, which
  lands in the run's own directory. Refused: any other `$` name (`$system`,
  `$fopen`, `$readmem*`, `$writemem*`, `$c`), DPI, `` `systemc_* `` blocks,
  token pasting, and an `` `include `` of anything but a relative file in the
  includer's folder; an included file is checked whatever its name.
  An included file is read only when, through any link, it is inside the
  folder of one of the files checked: an include that leads
  anywhere else (a link to a file or a folder of the host) is refused by
  the name it is included as, "leads outside the sandbox", and is never
  read (ip#309's follow-up).
  Strings and comments are skipped, in a file written in forms every tool
  splits into code, comments and strings the same way (section 7). Which file may end a simulation or read a
  plusarg is still the M53 testbench rule's matter. `simulator.run` and
  `test.run` take Verilog sources only.
- **Yosys scripts** (a `.sby`'s `[script]`, an `.eqy`'s `[gold]`, `[gate]` and
  `[script]`): no line starting with `!`, and every command in `YOSYS_SAFE`
  (reading designs and transforming the one in memory). M85: every file a read
  command (`read`, `read_verilog`, `verilog_defaults`, `verilog_defines`)
  names, every `-I` or `-incdir` include folder, and a `hierarchy -libdir`
  folder is a relative name of ordinary characters with no `..`
  (`relative_problem`): so no absolute path, no `~/` (Yosys reads it as the
  home folder), no `+/` (its share folder), no glob and no quote. A command
  file (`read -f`, `-F`) is refused, since it names files the check never
  reads. The values of `-D`, `-U`, `-setattr`, `-define` and `-undef` are not
  files and are not checked as such.
- **SBY setups**: the sections `[options]`, `[engines]`, `[script]`, `[files]`
  (and `[tasks]`, which the formal backends refuse themselves); the options in
  `SBY_OPTIONS`, each with a plain value; engines in `SBY_ENGINES`, each word a
  known solver or option; no `--pycode` line; no `[files]` destination
  outside the run's folder and no folder copied. M85: each `[files]` name, the
  source and the destination, is a relative name as above, and the source,
  through any link, is in the setup's folder or is one of the files the run
  was given (`sources`: an approved file the platform links beside the setup,
  M68's `beside`, is one); a link to anything else is refused
  (`inside_problem`). This is checked before the Verilog check reads any file
  the setup names, and an include is read only inside the run (the
  Verilog check above), so a refusal never quotes a file of the host.
- **eqy setups**: the sections in `EQY_SECTIONS`, eqy's own options on or off,
  a strategy's `use`, `depth`, `timeout` and `xprop` with plain values and its
  `engine` line checked as an SBY engine line (a strategy's `option` lines,
  which eqy writes into the `.sby` it runs, are refused), and the Yosys
  allow list in `[gold]`, `[gate]` and `[script]`. M85: every file a script
  reads is, through any link, in the setup's folder or one of the run's
  `sources`, and is checked as Verilog (a `$readmemh` in it would read any
  path while Yosys elaborates).
- **Constraints**: no quote, no backslash but a line continuation, no brace
  inside a word (so braces are the only quoting, and the check reads the
  commands Tcl would run), and every command, at a line's start, after a `;`
  or inside a `[...]` anywhere, in `SDC_COMMANDS`.

## 3. The history

`scripts/gate_input_history.py` (its logic tested in `tests/test_gate_inputs.py`,
`test_the_history_scan_counts_and_reports_what_the_checks_refuse`) takes every
seat-written file and every `entry` from the answers in the committed eval
records (`evals/results/`) and the JSON fixtures (`tests/fixtures/`) and runs
them through these checks. Run with `PYTHONPATH=src python
scripts/gate_input_history.py` at `main` fe58379 plus this change, it printed:

```
records 259, answers with files 95, seat files 209 (194 checked as Verilog, 15 .sby), entries 202, refused 7
```

The 7 refused are `.sby` setups that declare `[tasks]` (`sync_fifo.sby` in
two trials of run `-4`, `apb_regs.sby` in two of run `-5`, `axi4_lite_regs.sby`
in runs `-7`, `-8` and `without-knowledge-7`), which `formal.run` already
refused for the `[tasks]` itself; that reason still comes first. Every `entry`
is a plain module name, and no seat file used a construct of section 1. So no
committed trial reached the host through a gate. Anyone can rerun the script
on a later `main`.

## 4. Code by design

A cocotb test module (Python, M72) and a firmware driver (C, `fw.build`,
`fw.test`) are code by design, and no check can make them safe. They run as
the account that runs the gate, with the M53 isolation only: a new directory
per run, no credential in the environment, and the deadline that stops every
process. The PR review loop's check account (`NIRMAAN_LOOP_CHECK_USER`,
`scripts/pr_loop.py`, `check_argv`) runs the repository's checks as another
user in GitHub Actions; `nirmaan eval run` on a development machine does not
use it. That is not enough for a seat's code: on the founder's Mac it can read
and write what the founder's account can. Until those runs get an account or
sandbox of their own, run cocotb and firmware cases in CI, not on a personal
machine. This milestone does not change them. In the live evaluation's CI jobs
a cocotb test module now runs as an account of its own, and a live trial of a
case that runs seat C is refused until `fw.test` does too
(`docs/LIVE_EVAL_EVIDENCE.md`, section 6).

Reading was not covered by M84: an `.sby` `[files]` source could name an
absolute path or one outside its folder, and a Yosys read command a file or
include folder anywhere, so a seat's setup could copy a file of the host into
its run, where Yosys printed part of it to the log and the summary. M85 closes
that (section 6).

## 5. The harness

No file in `harness.CODE` or `harness.LOOP_CODE` changes
(`test_no_file_this_milestone_changes_is_harness_code`), and no tool definition
in `company/tools.py` does, so the harness fingerprint is unchanged: on the
development machine `harness_sha256()` was
`sha256:69d8ae47d1b3f44b9e49a2d8b539edbcbcb8a3a50f10774998ba7219ac7481d9` on
`main` fe58379 and on this change, and the `tools-in-loop` variant's was the
same on both too. What changes is which
inputs a gate refuses: a seat file using a refused construct now fails its gate
with the reason, where before it ran.

## 6. Reads (M85)

M85 found, with a marker file outside the run on Yosys 0.69 and SBY 0.69,
that a seat's `.sby` could read a file of the host, and that its content
reached the run's summary and log: a `[files]` entry naming the file by
absolute path (`leak.vh /<host>/leak.vh`), by `..`, or through a link; a
`[script]` read of an absolute path; an include folder (`read -formal
-I/<host> m.v`, where `m.v` includes `leak.vh`). A design that puts the
included text where an expression goes, under `default_nettype none`, makes
Yosys name it in an error, which became the summary ("Identifier
`\<marker>` is implicitly declared"). The M84 Verilog check itself read a
`[files]` source wherever it was and named the `$` words it found in the
refusal. An eqy setup could do the same through `-I`, `hierarchy -libdir`, a
link, or a `$readmemh` path in a file it reads.

In the `tools-in-loop` variant (M75) that summary, and a failed run's log
excerpt, go back to the seat. The M75 screen (`seat_tools.screen`) refuses a
word that starts with `/` or `~`, but not `-I/<host>`, so the read above
passed it, and the seat read the marker in its call's result
(`tests/test_gate_reads.py`, `test_a_seat_in_the_loop_never_reads_a_host_file`,
fails without this change). The checks of section 2 now refuse every one of
these before any step runs, behind the screen as for every run, so the screen
and the broker are unchanged.

What the broker passes back (`SeatTools._report`): each run's summary (the
backend's parsed result, with credentials redacted, M53) and, for a failed
run, an excerpt of its log (`runtime/files.py`, `excerpt`: the first 20
notable lines, else the last 20, each cut at 240 characters). Those can name
the run's own paths (its temporary directory, the tools' install paths), and
show the content of files in the run: the seat's own and the approved files
it was given. With the reads refused they carry no other file's content.
Redacting paths there would change `harness.CODE` and `harness.LOOP_CODE`, so
M85 leaves it.

ip#309's follow-up: the Verilog check followed an `` `include `` through a
link, so a refusal could name the `$` words of a host file reached that
way, and that refusal is what the attempts-3 repair text (M74,
`prompt._repair`) and the broker's report (M75, `SeatTools._report`)
pass to the seat. The check now refuses such an include unread
(section 2), so both carry the include's name only. Neither path is
changed: a refused run writes no log, so neither has an excerpt to
redact. `tests/test_gate_reads.py`,
`test_an_include_linked_out_of_the_run_is_refused_unread_and_quoted_nowhere`,
checks the refusal, the repair text and the broker's report for the marker.

Tests: `tests/test_gate_reads.py`. Must-fail: each read above, for
`formal.run` and `formal.cover`, is refused before any step, and the marker's
content is in no output (the summary, the run's data, any file under the
test's directory but the host folder, or the seat's call result); two
controls bypass the check and find the content in the summary. Must-pass: an
ordinary setup proves, a setup over an approved file linked beside it and
given as `sources` proves, ordinary read commands pass, and every committed
setup still passes (`tests/test_gate_inputs.py`). The history scan of
section 3, rerun at `main` 05bc78d plus this change, prints the same counts
and the same 7 refusals: no committed seat setup names a file outside its
folder.

No file in `harness.CODE` or `harness.LOOP_CODE` changes
(`test_gate_reads.py`, `test_no_file_this_milestone_changes_is_harness_code`):
on the development machine `harness_sha256()` was
`sha256:69d8ae47d1b3f44b9e49a2d8b539edbcbcb8a3a50f10774998ba7219ac7481d9`
and the `tools-in-loop` variant's
`sha256:d1fb57c9524e68570a38b7ce4b6ae5eacc48b2b54dcf22a235de44dc2664d067`,
the same with and without this change.

## 7. Where the check and a tool read the text differently (ET1)

Council record `council/records/2026-11-22-eda-tools-seat-account.md`
(decision 4, gate ET1). The checks of section 2 read a file's comments and
strings with a regular expression of their own (`eda_guard._TEXT_RE`), and
skip them; Icarus, Verilator and Yosys read them by their own rules. Where
the two readings differ, text the check skipped is code to the tool. The
record's fact 9 names two classes, found on a local machine during the
meeting, and building the repair found more files of the same two:

- **A comment or a string to the check, code to a tool.** An escaped
  identifier holding a comment or quote mark (`\/*`, `\//`, `\"`), which
  every tool reads as a name and the check as the start of a comment or a
  string; a quote in a branch of `` `ifdef `` that is not taken (Icarus skips
  that text without reading its strings, the check pairs the quote with a
  later one); a quote left open on its line (Yosys reads a string on across
  the line break); a block comment opened on a directive's line (Icarus ends
  it there: `` `define C /* `` is "Unterminated comment in define", and after
  `` `undef X /* `` the next lines are code).
- **A name the preprocessor assembles.** A bare `$` before a macro
  (`` $`N(...) ``, or `` `D`E `` with `D` defined as `$`), and a macro call glued
  to the name after it: `` `P($write)memh(...) `` is `$writememh` to Icarus and
  Verilator, and the check saw only `$write`, which it allows.

With the check bypassed, the tools acted on these files: an include of a
file outside the run, a `$readmemh` of one, or a `$writememh` to one.

The repair (`_lexical`) is an allow list of forms; a file outside it is
refused, with the reason, before any step runs:

- every string closes on its own line; a quote that does not is refused;
- no backslash outside a string but one that continues a line (so no escaped
  identifier);
- a conditional directive (`` `ifdef ``, `` `ifndef ``, `` `elsif ``,
  `` `else ``, `` `endif ``) stands alone on its line, a `//` comment aside, and
  none is inside a comment or a string;
- a block comment that spans lines does not open on a directive's line or on a
  line a backslash continues, and a macro call's arguments hold no comment;
- no `$` that does not start a name, no macro glued to the name before it, no
  macro call glued to the name after it, and no macro quote (`` `" ``,
  `` `\ ``);
- a backtick name with a lower case letter is a directive of `DIRECTIVES`
  (so no `` `line ``, `` `uselib `` or `` `pragma ``) or a macro the run's own
  files define; every directive of IEEE 1800 and of the three tools is lower
  case but `` `__FILE__ `` and `` `__LINE__ ``, so a name with no lower case
  letter is a macro;
- no control character but tab, line feed, and a carriage return before a
  line feed.

A C source (a firmware driver in `sources`) is checked too. A C character
literal (`'\0'`) breaks the first two rules, so a file with a suffix Verilator
compiles as C++ (`.c`, `.cc`, `.cpp`, `.cxx`), with no `$` or `DPI` in it and a
backtick only around a word, is left to the compiler for those two: it holds
nothing a Verilog tool acts on to read a file or run anything.

Tests: `tests/test_gate_inputs.py`, ET1 section. The fixtures are in
`tests/fixtures/screen_bypass/` as templates, each reaching a canary file
outside the run's folder (or, for `glued_macro_call`, writing a marker
there). Must-fail: every fixture is refused through `lint.run`,
`simulator.run` (icarus and verilator-sim), `synth.run` and `dft.scan_sim`,
and in a setup through `formal.run` and `formal.cover`, with the canary's
content in no summary; a seat file that reaches the timer's reference RTL,
its held-out testbench and a mutant through two of the fixtures' forms is
refused through each of the four gates. Controls, with the check bypassed:
for each fixture the tools that act on it (the canary's name or content in
the run's output, a synthesized result that changes with the canary's
content, or the marker written), and for each judge file a tool that
compiles it in. Each rule has a unit test, and an ordinary file using every
allowed form passes. Every committed Verilog and C file still passes, and
the history scan of section 3 refuses the same seat files as without the
repair: no committed trial's re-judge changes.

What is claimed: the check refuses, before any step, the forms its recorded
fixtures name. What is not: that its reading matches any tool's
preprocessor, that no third class exists, or that it covers a fault in a
tool's own parser; it screens input and confines nothing. The record makes
the seat account, not this check, the control for the runner-account tools
of the timer path (gates ET2 to ET4).

No file in `harness.CODE`, `harness.LOOP_CODE` or `FLOW_CODE` changes, so the
single-seat and whole-flow fingerprints are unchanged; the whole-flow plan's
"Gate backends" group digest moves (`evals/plans/2026-11-22-g3-whole-flow.md`,
section 6), for the plan amendment of gate ET6.

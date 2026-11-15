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
| `regmap.verify`, `fw.test` | the RTL (`rtl`), compiled by Verilator into the program it runs | the same constructs in the RTL |
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
- **Verilog** in `sources`, `rtl` and `design`, and every file a `.sby`'s
  `[files]` names: the system tasks and functions in `SAFE_SYSTEM` only
  (display, severity, time, arithmetic, random, plusargs, assertions and
  formal, waveform control); `$dumpfile` only with a plain file name, which
  lands in the run's own directory. Refused: any other `$` name (`$system`,
  `$fopen`, `$readmem*`, `$writemem*`, `$c`), DPI, `` `systemc_* `` blocks,
  token pasting, and an `` `include `` of anything but a relative file in the
  includer's folder; an included file is checked whatever its name.
  Strings and comments are skipped. Which file may end a simulation or read a
  plusarg is still the M53 testbench rule's matter. Simulations take Verilog
  sources only.
- **Yosys scripts** (a `.sby`'s `[script]`, an `.eqy`'s `[gold]`, `[gate]` and
  `[script]`): no line starting with `!`, and every command in `YOSYS_SAFE`
  (reading designs and transforming the one in memory).
- **SBY setups**: the sections `[options]`, `[engines]`, `[script]`, `[files]`
  (and `[tasks]`, which the formal backends refuse themselves); the options in
  `SBY_OPTIONS`, each with a plain value; engines in `SBY_ENGINES`, each word a
  known solver or option; no `--pycode` line; no `[files]` destination
  outside the run's folder and no folder copied.
- **eqy setups**: the sections in `EQY_SECTIONS`, eqy's own options on or off,
  a strategy's `use`, `depth`, `timeout` and `xprop` with plain values and its
  `engine` line checked as an SBY engine line (a strategy's `option` lines,
  which eqy writes into the `.sby` it runs, are refused), and the Yosys
  allow list in `[gold]`, `[gate]` and `[script]`.
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
records 259, answers with files 95, seat files 209 (194 Verilog, 15 .sby), entries 202, refused 7
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
machine. This milestone does not change them.

Reading is not covered either: an `.sby` `[files]` source may still name an
absolute path or one outside its folder, so a seat's setup can copy a file of
the host into its run, where Yosys may print part of it to a log. That is a read,
not a run, and a follow-up for the platform's security owner.

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

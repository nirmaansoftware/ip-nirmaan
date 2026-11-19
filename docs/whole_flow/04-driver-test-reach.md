# What a driver test can reach (gate WF14)

The council record's addendum of 2026-11-18 replaced decision 2's fixture
driver test for the register block with three things, which gate WF14 asks
for before the first register block trial:

- **The reach guard.** The guard tests in
  `tests/test_nirmaan_firmware_reach.py` need no tool. They pin, as exact
  lists: the members of `nirmaan_hal` and every declaration of
  `nirmaan_hal.h` and `nirmaan_irq.h`; the external definitions of each
  host manager (`axil_manager.cpp`, `apb_manager.cpp`: the six `extern "C"`
  functions and `main`; everything else, and all of `harness_report.h`, is in
  an anonymous namespace); the files in the harness directory, which is on a
  driver test's include path; the registered managers; the headers each
  harness file includes; and the literal options of the Verilator build. Any
  addition, or an edit to a listed declaration, fails with the return
  condition in its message. (The same file's simulator test, below, needs the
  firmware tools and runs in CI.)
- **The wait probe**, the control above, recorded in
  `evals/flow/controls_record.json`.
- **The return condition.** The fixture driver test is required again, before
  the next trial, for any case where the HAL or the harness gains a cycle
  count, a timeout or a non-blocking access that a driver test can read, or
  where the block has a register whose value depends on elapsed cycles, or
  where the fixed document leaves open a choice visible in data or response
  codes.

The addendum left open whether a simulator symbol is reachable from a test's
C. It is. Under `fw.test` a driver test is host C linked into one image with
the harness and Verilator's runtime, and C can name a C++ symbol by its
mangled name. `tests/fixtures/fw/reach/simulator_clock_probe.c` reads
`Verilated::s_lastContextp`, the harness's own simulation context, finds the
simulation time in it, and times a `read32` and a `write32` in cycles: each
takes more cycles on `axi4_lite_regs_lat2.v` than on the reference RTL. The
tool-backed test in the guard file runs it on both RTLs, in CI only. This is
neither a HAL call nor the driver interface. The guard pins the files,
declarations and build options it lists; it closes nothing, and it does not
pin the simulator's version, which also decides the symbols. The second
addendum decided what follows: the fixture control is owed again (gate WF15,
below), and what a driver test's host C may reach is for gates WF16 to WF18.

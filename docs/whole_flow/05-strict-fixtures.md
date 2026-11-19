# The strict fixtures (gate WF15)

The record's second addendum of 2026-11-18 (decision 1) withdrew the first
addendum's "the control is empty for this block" and requires, before the
first register block trial, a strict fixture driver test and a strict fixture
driver, and for each route by which a recorded probe reads a cycle count
either the route refused or a strict fixture using it recorded failing. Six
controls in `evals/flow/controls.json` do this, one or two per route. Each is a flow whose RTL stage
ended in the conforming RTL: the control's `upstream_rtl` replaces the base
case's upstream RTL with a copy of `axi4_lite_regs_lat2.v` under the
reference's file name, so the seat's own checks run on it before review, as
they would in a whole flow, and check 5 runs on it.

- `driver-strict-latency-test`: the reference driver with
  `tests/fixtures/fw/axi4_lite/axi4_lite_regs_test_strict_latency.c`, the
  reference driver test plus one named check,
  `read32_and_write32_take_the_conforming_rtls_cycles`. It reads the
  simulation time through `Verilated::s_lastContextp`, as the reach probe
  does, times one `read32` and one `write32`, and passes only at the
  conforming RTL's counts. It still passes on that RTL outside the screened
  checks, but with the object screen in force (gate WF16) check 7 refuses it
  before any link, with nothing run: this route, the simulator's clock, is
  CLOSED in the screened checks. The file stays.
- `driver-strict-latency-driver`: `axi4_lite_regs_drv_strict_latency.c`, the
  reference driver except that it times every transfer the same way and
  reports one that took other than the conforming RTL's count as a bus error,
  with the reference driver test. Checks 4, 5 and 6 each refuse it by the
  screen, with nothing run. The file stays.
- `driver-strict-address-test`: the reference driver with
  `axi4_lite_regs_test_strict_address.c`, the same strict test on the route
  the screen leaves OPEN: address arithmetic. It names nothing the screen
  refuses and finds the harness's own cycle count from `hal->read32` and
  `hal->write32`, as the address-arithmetic probe does. It passes on the
  conforming RTL, and check 7 fails it on the reference RTL by that one check:
  the test asserts the run built, finished with the harness's summary,
  reported no harness error, and failed no other check, and that its bus
  transfers equal those of the run on the conforming RTL.
- `driver-strict-address-driver`: `axi4_lite_regs_drv_strict_address.c`, the
  strict driver on the same open route, with the reference driver test. It
  passes the screen and builds alone (check 4), passes check 5 on the
  conforming RTL and fails check 6.
- `driver-strict-soc-cycles` and `driver-strict-soc-address`: the same
  strict test on the other route, the SoC run's `NIRMAAN_SOC_CYCLES`
  register, once named through `nirmaan_soc.h` and once by its address
  copied into the test. The case's checks run on host co-simulation
  (`fw.test`); its request names no RISC-V, so no `fw.soc_test` check runs.
  The first is refused when the seat's own `fw.test` check builds it (the
  header is not on the include path); the second kills the co-simulation
  with signal 11 before any harness record is written out, which `fw.test`
  reports as "co-simulation was killed by signal 11 before it reported
  anything; the build was clean: 0 errors (exit status -11)" (before this
  wording it read "build failed before co-simulation: 0 errors (exit status
  -11)", as in the controls record's run; the control's `refused_by` matches
  the tail both share). Neither reaches review.

Each strict fixture on the simulator's clock prints what it timed on a line of
its own (`STRICT-FIXTURE ...`); the address-route fixtures print nothing
(`printf` is off the screen's allow list), and their counts are in the
failed check's detail. The `FLOW-CONTROL` line carries those lines per
check, a control that never reaches review carries its gate runs, and the
record keeps both; the counts are in the manifest as expected values, and
every later run is held to them. The fixture files stay when a route is
closed; their expected result then changes to the refusal, in a recorded run,
as it did for the simulator's clock when the screen came in. The
address-arithmetic route stays OPEN: the screen does not close it, so its strict
fixtures are the live controls on it until the driver and its tests run in a
process of their own (gate WF18). These are judge controls written by the
platform. No model-written driver test has used any of these routes.

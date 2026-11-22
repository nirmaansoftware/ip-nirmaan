# Coverage report: `tick_timer_tb`

The reference answer of the eval case `dv/coverage-tick-timer`. It extends the
approved idle testbench (reset values and one register read back) into a
directed testbench with two lanes, `W` 16 and `W` 5, that start the timer,
count it down, run both modes through an expiry, set and clear the flag, mask
the interrupt with `IE` in each mode, stop it, write `LOAD` while it runs, and
reset it from a busy state.

Coverage is read by `coverage.read` over the approved `tick_timer.v` (the
testbench's own points never count). The bounds are line at least 90 percent
and toggle at least 75 percent; branch is not bounded. No measured figure is
stated here: the eval's tests run the tool and assert the bounds are met, so
the record is the test run.

Toggle is the tighter bound: the upper bits of `wdata` and `rdata` never move
in a directed test of a 16-bit and a 5-bit timer.

The mode-qualified mutant `tick_timer_irq_ie_ignored_periodic` is the case's
answer to a surviving-mutant failure of the first coverage case: coverage was
met there while the masked path was not checked. Here the masked interrupt is
checked in one-shot and in periodic mode separately, so the same slip in one
mode is caught.

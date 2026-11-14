# Coverage report: `irq_ctrl_tb`

The reference answer of the eval case `dv/coverage-irq-ctrl`. It extends the
approved idle testbench (reset values and one register read back) into the
directed testbench of `dv/directed-irq-ctrl`: two lanes, `N` 8 and `N` 5, that
raise level and rising-edge sources, mask and unmask them, clear by write and
by acknowledge, and claim by priority.

Coverage is read by `coverage.read` over the approved `irq_ctrl.v` (the
testbench's own points never count). The bounds are line at least 90 percent
and toggle at least 75 percent; branch is not bounded. No measured figure is
stated here: the eval's tests run the tool and assert the bounds are met, so
the record is the test run.

Toggle is the tighter bound: the wide `wdata` and `rdata` buses and the
high bits of the `N` 5 lane's registers never move in a directed test.

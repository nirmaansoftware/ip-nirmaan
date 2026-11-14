# Coverage report: `irq_ctrl_tb`

The reference answer of the eval case `dv/coverage-irq-ctrl`. It extends the
approved idle testbench (reset values and one register read back) into the
directed testbench of `dv/directed-irq-ctrl`: two lanes, `N` 8 and `N` 5, that
raise level and rising-edge sources, mask and unmask them, clear by write and
by acknowledge, and claim by priority.

Measured by `coverage.read` over the approved `irq_ctrl.v` (the testbench's own
points never count):

| Metric | Result | Bound |
|---|---|---|
| line | 100 percent | at least 90 |
| toggle | 79.7 percent | at least 75 |
| branch | 100 percent | not bounded |

Toggle is the tighter bound: the wide `wdata` and `rdata` buses and the
high bits of the `N` 5 lane's registers never move in a directed test. The
figures are Verilator 5.052's; a Verilator that counts toggle points
differently reads a different percentage.

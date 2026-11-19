**The coverage matrix.** Another independent check (the timer document's
fourth, the register block's third) failed both
flow documents again (timer 7 findings, register block 5), each a single point
in a class the copies sampled: held write addresses, `SLVERR` with partial or
no strobes, periodic `LOAD` 1 and 2 and the 32-bit reload, a periodic restart
and stop, a `LOAD` write mid-count, `CTRL` strobes with `EN` 0, ready timing
after `SLVERR`, and latency with the other direction busy. One round closes the
classes: each testbench copy ends with a coverage matrix (ordering by address
class by strobe for writes, reads with backpressure, back to back after each
response kind, overlapped reads and writes; for the timer a protocol monitor
on every edge, counts traced edge by edge at `LOAD` 0, 1, 2, 37 and
`0x0001_0005` in both modes, mid-count restarts, stops and `LOAD` writes, and
`CTRL` by strobe and `EN`). `TMR-READY`, `TMR-LOAD-ZERO-PERIODIC` and
`TMR-IRQ-EDGE` move to judged; "no other ports" is split out of `AXIL-PORTS`
as `AXIL-PORTS-ONLY`, not judged. `tests/flow_mutants.py` gains the checker's
passing mutants and one per new dimension (99 timer, 40 register block, all
failing), and the sweep records are rerun. Both documents still wait for a
fresh check.

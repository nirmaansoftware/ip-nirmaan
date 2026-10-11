# Milestone 26 (blocks) - FIFO, arbiter, and APB register block on the design flow (post-roadmap)

Three more fixture sets, in the AXI4-Lite set's shape, each proven through the
broker by real tools and each run end to end through `block-design`. No
runtime, policy, workflow, or vocabulary change: the requests already match
`block_design`. Design doc: `docs/IP_BLOCKS.md`.

- `tests/fixtures/rtl/sync_fifo/`: module `sync_fifo`, `DEPTH` 8, `WIDTH` 8,
  ports `clk rst_n wr_en wr_data full rd_en rd_data empty count`. Explicit
  `count` register (any `DEPTH` of 2 or more), first-word fall-through, a
  write while full and a read while empty dropped, full with a write and a read
  accepts only the read. Proofs `sync_fifo.sby` and `sync_fifo_depth5.sby`.
  Wrong testbench: a full FIFO of depth 8 "holds 9" (`count when full`).
- `tests/fixtures/rtl/rr_arbiter/`: module `rr_arbiter`, `N` 4, ports
  `clk rst_n req grant`. Index pointer, combinational same-cycle grant,
  pointer to one past the winner, wait at most `N-1`. Proofs `rr_arbiter.sby`
  and `rr_arbiter_n5.sby`. Wrong testbench: the winner "keeps" top priority
  (`rotation with everyone requesting`).
- `tests/fixtures/rtl/apb_regs/`: module `apb_regs`, APB4, `ADDR_WIDTH` 8,
  `DATA_WIDTH` 32, ports `pclk presetn paddr psel penable pwrite pwdata pstrb
  prdata pready pslverr`, four registers at 0x0 to 0xC, zero wait states.
  **Unmapped policy: PSLVERR**, the AXI4-Lite block's SLVERR (misaligned, or
  0x10 and above: a write changes nothing, a read returns zero). Proof
  `apb_regs.sby`. Wrong testbench: `pstrb 0101`, as the AXI4-Lite one.
- The FIFO and arbiter testbenches run a default and a non-power-of-two
  instance side by side against reference models, with coverage counters that
  fail the run if a corner case was never reached. Two `.sby` files each
  because the broker's `sby -d` takes one task per file.
- Mutation check (not committed): 19 mutants; simulation caught 18, formal 19.
  The one simulation misses is an APB write in the setup phase too, invisible
  at the ports. It also showed that APB properties reusing the design's
  `is_mapped` and `merge` hid bugs in them, so the properties now have their
  own decode and byte merge.

Tests: `tests/test_sync_fifo_fixture.py`, `tests/test_rr_arbiter_fixture.py`,
`tests/test_apb_regs_fixture.py` (lint, both simulators, the wrong testbench
as a recorded failed run, synthesis with no latches, formal skipping without
`sby`) and `tests/test_nirmaan_more_blocks.py` (six natural requests plan
`block-design`; `test_the_block_is_designed_by_agents` per block). 35 tests.

Deferred: lint at non-default parameters through the broker (checked by hand),
and richer variants (registered FIFO read, weighted arbiter, APB wait states).

# More IP blocks on the design flow (Milestone 26, blocks part)

Status: implemented on branch `m26/more-blocks`, for the owner's review. Prose
here is free of em and en dashes per the standing style law.

M23 proved the design-agent flow (`docs/DESIGN_AGENTS.md`) on one block, the
AXI4-Lite register block. M26 runs the same flow, unchanged, on three more: a
synchronous FIFO, a round-robin arbiter, and an APB register block. Each has
real RTL and testbenches proven by real tools, and each runs end to end through
the `block-design` workflow. This settles the "FIFO, arbiter, and APB register
blocks on the block workflow" item deferred in `docs/DESIGN_AGENTS.md` section 9.

No runtime, policy, workflow, or vocabulary code changed. The requests
"Create a parameterizable synchronous FIFO.", "Create a round-robin arbiter
for four requesters." and "Create an APB register block with four 32-bit
registers." already match the `block_design` intent (its pattern names FIFO,
arbiter, and register block), so the vocabulary needed no edit. A test pins
that, with three more phrasings.

---

## 1. The fixture sets

Each block has its own folder under `tests/fixtures/rtl/`, in the AXI4-Lite
set's shape: `interface_spec.md`, `microarchitecture.md`, the RTL with its
properties in an `ifdef FORMAL` block, a self-checking `_tb.v`, a `_tb_fail.v`
with one deliberately wrong expectation, and SymbiYosys files.

| Block | Module | Parameters | Key choices |
|---|---|---|---|
| `sync_fifo/` | `sync_fifo` | `DEPTH` 8, `WIDTH` 8 | Explicit `count` register (so any `DEPTH` of 2 or more works, not only powers of two); `full` and `empty` compare on it; first-word fall-through read; a write while full and a read while empty are dropped; when full, a write and read together accept only the read. |
| `rr_arbiter/` | `rr_arbiter` | `N` 4 | Index priority pointer; combinational same-cycle grant, one-hot or zero, work conserving; pointer moves to one past the winner; a held request waits at most `N-1` cycles. |
| `apb_regs/` | `apb_regs` | `ADDR_WIDTH` 8, `DATA_WIDTH` 32 | APB4 with `pstrb` (no `pprot`, as the AXI4-Lite block has no `prot`); zero wait states (`pready` high); four registers at 0x0 to 0xC; `prdata` and `pslverr` zero outside the access phase. |

**APB unmapped policy.** The AXI4-Lite block answers an unmapped address with
SLVERR; the APB block does the same with PSLVERR. An address is mapped when it
is word aligned and in 0x0 to 0xC (the AXI4-Lite decode, unchanged). With an
8-bit address, both misaligned addresses and 0x10 to 0xFF are unmapped. An
unmapped write changes nothing; an unmapped read returns zero; both complete
with `pslverr` high in the access phase.

**Two parameter points each.** The FIFO and arbiter testbenches run the
default instance and a non-power-of-two one side by side (DEPTH 5 by WIDTH
12; N 5), each lane against its own reference model, checked on every rising
edge, with coverage counters that fail the run if a corner case listed in the
interface spec was never reached. Each has two `.sby` files for the same
reason (`sync_fifo.sby` and `sync_fifo_depth5.sby`; `rr_arbiter.sby` and
`rr_arbiter_n5.sby`): the broker runs `sby -d`, which takes one task per
file. Both proofs matter: the "pointer never wraps early" mutants below pass
the power-of-two proof and fail only the other one.

## 2. The formal properties

All proofs are unbounded (`mode prove`, smtbmc with yices).

* **FIFO:** empty after reset; `full` and `empty` follow `count` and are
  never both high; `count` and pointers in range; `wr_ptr` is `count` slots
  after `rd_ptr`; `count` moves by exactly the accepted requests; a write while
  full and a read while empty change nothing on their side; for one slot the
  solver picks, the word written stays until read and is what `rd_data` shows.
* **Arbiter:** pointer in range and zero after reset; grant one-hot or zero,
  only to a requester, work conserving; no requester between the pointer and
  the winner; after a grant the pointer sits one past the winner; bounded
  wait, with the induction invariant that wait plus the pointer's distance to
  the requester stays within `N-1`.
* **APB:** the manager is assumed to follow APB (setup then access, stable
  request, `penable` only after setup, nothing in reset). Asserted: `pready`
  high; responses quiet outside the access phase; `pslverr` and `prdata` by the
  address policy; registers zero after reset; each byte of each register
  changes only in a mapped write access to it with its strobe set, to the
  written byte. The decode and byte merge in the properties are written
  independently of the design's `is_mapped` and `merge`. The first version
  reused them, and the mutation check below showed that a broken decode or a
  broken merge then passed the proof.

## 3. Mutation check

Each RTL was broken in six or seven ways, one at a time (script outside the
repository; the mutants are not committed), and run against both simulators
and every proof.

| Block | Mutants | Caught by simulation | Caught by formal | Caught by either |
|---|---|---|---|---|
| `sync_fifo` | 6 | 6 | 6 | 6 |
| `rr_arbiter` | 6 | 6 | 6 | 6 |
| `apb_regs` | 7 | 6 | 7 | 7 |

The mutants: FIFO (write ignores full, read ignores empty, pointer never
wraps early, count grows on a write and read together, read from the write
pointer, full one entry early); arbiter (winner keeps top priority, fixed
priority from 0, every requester granted, pointer steps by one instead of
past the winner, search never wraps early, pointer skips one extra); APB (no
range check in the decode, `pslverr` outside the access phase, `pstrb`
ignored, write in the setup phase too, wrong read index bits, unmapped writes
land, `pready` low). The one mutant simulation cannot catch is the APB write
in the setup phase too: APB holds the request stable, so writing the same data
one cycle early is invisible at the ports, and only the formal register rule
sees it.

## 4. Tests

* `tests/test_sync_fifo_fixture.py`, `tests/test_rr_arbiter_fixture.py`,
  `tests/test_apb_regs_fixture.py`: through the broker, as
  `tests/test_axi4_lite_fixture.py` does: completeness, Verilator lint (`-Wall`,
  no waivers), simulation under Icarus and Verilator, the wrong testbench as a
  recorded failed run, Yosys synthesis with no latches, and formal (skips
  without `sby`).
* `tests/test_nirmaan_more_blocks.py`: natural requests plan `block-design`;
  and, per block, the AXI4-Lite end-to-end test's shape: spec,
  microarchitecture, and RTL seats over a scripted `MockLLM` answering with the
  fixture files, real lint and simulation before review, review, human
  approval, files byte for byte the fixtures, and every claim backed.

Tool versions: developed on Verilator 5.052, Icarus 13, Yosys 0.69, and sby
with yices; CI runs Verilator 5.020, Icarus 12, and Yosys 0.33 (no `sby`, so
formal skips there).

## 5. Deferred

* Lint at non-default parameters through the broker (`lint.run` takes no
  parameter overrides). It was checked by hand: FIFO at DEPTH 5 and 2, arbiter
  at N 2, 5 and 8, APB at ADDR_WIDTH 4, all clean.
* A FIFO with registered read data, almost-full and almost-empty thresholds,
  or two clocks; an arbiter with weights or grant hold; APB wait states.

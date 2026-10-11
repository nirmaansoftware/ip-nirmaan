# Microarchitecture: `sync_fifo`

The implementation plan for the interface in `interface_spec.md`. The RTL is
`sync_fifo.v`.

## 1. Storage and pointers

* **Storage** is an array `mem` of `DEPTH` words of `WIDTH` bits. It is
  datapath: not reset, and written only outside reset. With no memory macro
  in the flow, Yosys maps it to flip-flops and multiplexers.
* **Pointers.** `wr_ptr` names the next slot to write and `rd_ptr` the oldest
  entry. Each is `$clog2(DEPTH)` bits and advances by one on an accepted
  request, wrapping from `DEPTH-1` to 0. The wrap compares against `LAST`
  (`DEPTH-1`) rather than relying on overflow, so a `DEPTH` that is not a
  power of two works.

## 2. Occupancy: an explicit counter

The classic alternative, one extra pointer bit to tell full from empty, only
works for a power-of-two `DEPTH`. Instead the FIFO keeps `count`, the number
of entries, as a register of `$clog2(DEPTH+1)` bits:

* `count` rises by one on a write without a read, falls by one on a read
  without a write, and holds otherwise.
* `full = (count == DEPTH)` and `empty = (count == 0)`: both are a compare
  on a register, so neither depends combinationally on an input.
* `count` is also the `count` port: no extra logic.

## 3. Accepting requests

* `wr_acc = wr_en && !full` and `rd_acc = rd_en && !empty`. The flags gate
  the requests, which is the whole overflow and underflow policy: a write
  while full and a read while empty are dropped, with no side effect.
* When full, a simultaneous write and read accepts only the read, because
  `full` is the state before the edge. That keeps the write path free of any
  dependence on `rd_en` (no read-to-write combinational path).

## 4. Read port: first-word fall-through

`rd_data = mem[rd_ptr]`, a combinational read of the oldest slot. It shows
the oldest entry as soon as it is written (1 cycle after the write), and the
reader consumes it by raising `rd_en`. When empty, `rd_ptr` points at a
stale or never-written slot, which is why `rd_data` is undefined then.

## 5. Reset behavior

`rst_n` is synchronous and active low. On reset `wr_ptr`, `rd_ptr` and
`count` clear; the storage keeps whatever it held, which is harmless because
`count` says no slot is valid.

## 6. Verification plan

| Check | Tool | File |
|---|---|---|
| Lint, `-Wall`, no waivers | Verilator | `sync_fifo.v` |
| Directed and random self-checking simulation | Icarus and Verilator | `sync_fifo_tb.v` |
| Failure path is a failed run | Icarus and Verilator | `sync_fifo_tb_fail.v` |
| Synthesis, no latches | Yosys | `sync_fifo.v` |
| FIFO properties, unbounded proof, DEPTH 8 | SymbiYosys | `sync_fifo.sby` |
| The same proof at DEPTH 5 | SymbiYosys | `sync_fifo_depth5.sby` |

The testbench runs two FIFOs on the same stimulus, DEPTH 8 by WIDTH 8 and
DEPTH 5 by WIDTH 12, each with a reference queue checked on every rising
edge. Coverage counters fail the run if any corner case in the interface
spec was not reached.

The formal block (under `ifdef FORMAL` in the RTL) asserts: empty after
reset; `full` and `empty` follow `count` and are never both high; `count`
and the pointers stay in range; `wr_ptr` is always `count` slots after
`rd_ptr`; `count` moves by exactly the accepted requests; a write while full
and a read while empty change nothing on their side; and, for one slot chosen
by the solver, the word written there stays unchanged until it is read and is
what `rd_data` shows.

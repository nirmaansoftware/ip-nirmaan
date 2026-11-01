# Microarchitecture: `axil_timer`

The implementation plan for the interface in `interface_spec.md`. The RTL is
`axil_timer.v`.

## 1. Channels

The AXI4-Lite channel logic is the register block's (`../axi4_lite/`):

* `aw_held` and `w_held` keep a write address or data that arrived alone;
  `awready = !aw_held && !bvalid`, `wready = !w_held && !bvalid`.
* `do_write` is true in the cycle both halves are present (held or arriving).
  On that edge the write takes effect, `bvalid` rises and the holding flags
  clear. `bresp` is SLVERR unless the address is mapped and is not `COUNT`.
* `arready = !rvalid`. On a read handshake `rdata` and `rresp` are loaded and
  `rvalid` rises; they hold until `rready`.

## 2. The timer as a state machine

The state is four flops and two 32-bit registers: `en`, `ie`, `mode`,
`expired`, `load`, `count`. `en` and `mode` give three states:

| State | `en` | What each edge does |
|---|---|---|
| Idle | 0 | nothing; `count` holds |
| Counting | 1 | `count - 1`, or, on the last cycle, the end |
| End (one edge) | 1, `count` at 1 or 0 | one-shot: `count` to 0, `en` to 0 (back to Idle); periodic: `count` to `load`, `en` stays 1 |

`count_end = en && count <= 1` marks the last cycle. Treating 0 like 1 makes
a `LOAD` of 0 a one-cycle count instead of a wrap to 2^32 - 1.

Order inside the clocked block, so the priorities of the specification fall
out of last-assignment-wins:

1. The count step (decrement, reload or stop).
2. `expired`: cleared by an acknowledgement, then set by `count_end`. The set
   comes second, so a count that ends in the cycle of the clear wins.
3. A `CTRL` write (only with `wstrb[0]`): `ie` and `mode` take the written
   bits; `EN` 1 sets `en` and `count <= load`, `EN` 0 clears `en`. Coming
   after the count step, a start or stop on the edge of a count end wins for
   `en` and `count`.
4. A `LOAD` write merges the strobed bytes.

`irq = expired && ie`, a plain AND of two flops: no glitch, and it follows
`ie` in the same cycle.

## 3. Address decode

`is_mapped(addr)` is `addr[1:0] == 0 && (addr >> 4) == 0`. The second term
is what keeps offsets from `0x10` up from aliasing the registers when
`ADDR_WIDTH` is above 4; at `ADDR_WIDTH` 4 it is always true. The register
index is `addr[3:2]`.

## 4. Reset

`aresetn` is synchronous and active low. Every timer flop, `bvalid`,
`rvalid` and the holding flags reset; the held address and data need no
reset, since nothing reads them unless a holding flag is set.

## 5. Verification plan

| Check | Tool | File |
|---|---|---|
| Lint, `-Wall`, no waivers | Verilator | `axil_timer.v` |
| Directed self-checking simulation, lanes at `ADDR_WIDTH` 4 and 8 | Icarus and Verilator | `axil_timer_tb.v` |
| Synthesis, no latches | Yosys | `axil_timer.v` |
| Channel and timer properties, unbounded proof, `ADDR_WIDTH` 4 | SymbiYosys | `axil_timer.sby` |
| The same properties at `ADDR_WIDTH` 8 | SymbiYosys | `axil_timer_aw8.sby` |

The testbench counts rising edges and times each count from the edge the
starting write took effect to the edge after which `irq` rose, so a count
that is one cycle long or short fails. It acknowledges one periodic expiry on
the very edge the next count ends, to check that the expiry is kept.

The formal block (under `ifdef FORMAL`) assumes a manager that follows the
AXI rules and asserts the channel properties of the register block, the
response codes by the address policy, the read data, and that every timer
register equals a model of the specification after every edge. The model's
decode, byte merge and count are written independently of the design's, so a
bug in one cannot hide behind itself. Running the proof at both address
widths matters: a decode that ignores the bits above `0xC` is right at
`ADDR_WIDTH` 4 and wrong at 8.

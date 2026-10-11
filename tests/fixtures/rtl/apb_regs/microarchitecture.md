# Microarchitecture: `apb_regs`

The implementation plan for the interface in `interface_spec.md`. The RTL is
`apb_regs.v`.

## 1. Zero wait states, no state machine

APB carries one transfer at a time and the manager holds the request stable
through the access phase, so a register block needs no request capture and
no state machine of its own:

* `pready` is tied high. Every access phase completes in its first cycle.
* `access = psel && penable` marks the one cycle in which the response is
  sampled and the write takes effect. The setup phase needs no action.
* The only state is the four registers.

## 2. Register file

* Four registers, `reg0` to `reg3`, as separate flops rather than a memory
  array, so every tool (Verilator, Icarus, Yosys) sees plain flip-flops.
* A write updates one register through `merge(old, data, strb)`, which copies
  each byte of `data` whose strobe bit is set and keeps the other bytes: the
  same function as the AXI4-Lite block.
* The register index is `paddr[3:2]`.

## 3. Address decode and the PSLVERR policy

`is_mapped(addr)` is true when `addr[1:0] == 0` and `addr >> 4 == 0`: word
aligned and inside `0x0` to `0xC`. This is the AXI4-Lite block's decode; with
an 8-bit address the second term matters (`0x10` to `0xFF` are unmapped).

* `pslverr = access && !mapped`: high only in the access phase of an unmapped
  transfer, so it is zero whenever APB4 does not define it.
* A write to an unmapped address updates no register.
* A read from an unmapped address returns zero.

## 4. Read data

`prdata` is a combinational 4:1 multiplexer of the registers, forced to zero
unless the cycle is a mapped read access. The address is stable from the setup
phase, so the multiplexer has a whole cycle to settle before the access
phase is sampled. A registered `prdata` loaded in the setup phase would give
the same timing to the manager but cost 32 flops.

## 5. Reset behavior

`presetn` is synchronous and active low. On reset all four registers go to
zero. `pready` is high in reset too; the manager does not select the block
until reset is released.

## 6. Verification plan

| Check | Tool | File |
|---|---|---|
| Lint, `-Wall`, no waivers | Verilator | `apb_regs.v` |
| Directed self-checking simulation | Icarus and Verilator | `apb_regs_tb.v` |
| Failure path is a failed run | Icarus and Verilator | `apb_regs_tb_fail.v` |
| Synthesis, no latches | Yosys | `apb_regs.v` |
| Protocol and register properties, unbounded proof | SymbiYosys | `apb_regs.sby` |

The testbench drives inputs after the falling edge and samples before the
rising edge, so it has no race with the design. Every transfer checks that it
had zero wait states, and every setup and idle cycle checks that `prdata` and
`pslverr` are zero.

The formal block (under `ifdef FORMAL` in the RTL) assumes a manager that
follows the APB rules (setup then access, stable request, `penable` only
after setup, no transfer in reset) and asserts: `pready` is high; `prdata` and
`pslverr` are zero outside the access phase; in the access phase `pslverr`
and `prdata` follow the address policy; registers are zero after reset; and
each byte of each register changes only in a mapped write access to that
register with its strobe set, to the written byte. The decode and byte merge
in the properties are written independently of the design's `is_mapped` and
`merge`, so a bug in either cannot hide behind itself.

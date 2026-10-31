# Microarchitecture: `apb_gpio`

The implementation plan for the interface in `interface_spec.md`. The RTL is
`apb_gpio.v`.

## 1. APB side: zero wait states, no state machine

As in `../apb_regs/`: `pready` is tied high, `access = psel && penable` marks
the cycle a transfer completes, and the setup phase needs no action.

* `is_mapped(addr)`: `addr[1:0] == 0`, nothing set above bit 5, and the
  register index `addr[5:2]` at most 8 (`INTR_STATUS`).
* `pslverr = access && (!mapped || (pwrite && index == DATA_IN))`.
* `prdata` is a combinational multiplexer of the registers, forced to zero
  unless the cycle is a mapped read access.

## 2. Registers

Every register is 32 bits wide. The pins that do not exist are held at zero
by a constant mask, `PINS`, with bits `0` to `N-1` set:

* the write mask is the byte strobes, expanded to 32 bits, AND `PINS`, so a
  write never sets a bit above `N`;
* the input sample is `gpio_in` widened to 32 bits with zeros above `N`.

Keeping the registers 32 bits wide at every `N` means no zero-width
replication at `N` 32 and no unused write-data bits at `N` below 32, so the
block is lint clean at every `N` without waivers. Synthesis removes the
constant-zero flops.

A write to a read/write register merges: `(old & ~mask) | (pwdata & mask)`.

## 3. Detection and status

Two sample registers: `in_q <= gpio_in` (read as `DATA_IN`) and
`in_prev <= in_q`. All of detection is combinational from these and the four
enable registers:

```
rise     = in_q & ~in_prev
fall     = ~in_q & in_prev
detected = ((rise & INTR_RISE) | (fall & INTR_FALL)
           | (in_q & INTR_HIGH) | (~in_q & INTR_LOW)) & PINS
clear    = (mapped write to INTR_STATUS) ? (pwdata & mask) : 0
status  <= (status & ~clear) | detected
```

The OR with `detected` comes last, so a detection on the edge of a clear
keeps the bit set, and a level condition sets its bit again on every edge
while it holds. `irq = |(status & INTR_ENABLE)`: a reduction of flops, with
no glitch.

The sample adds one cycle between a pin change and its detection; the
integrator puts a synchronizer in front of any pin that is not already in the
`pclk` domain.

## 4. Reset

`presetn` is synchronous and active low; every register, both samples and so
the status reset to zero.

## 5. Verification plan

| Check | Tool | File |
|---|---|---|
| Lint, `-Wall`, no waivers, `N` 8 and 32 | Verilator | `apb_gpio.v` |
| Directed self-checking simulation, lanes at `N` 8 and 32 | Icarus and Verilator | `apb_gpio_tb.v` |
| Synthesis, no latches | Yosys | `apb_gpio.v` |
| Protocol and register properties, unbounded proof, `N` 8 | SymbiYosys | `apb_gpio.sby` |
| The same properties at `N` 32 | SymbiYosys | `apb_gpio_n32.sby` |

The testbench drives pins after the falling edge and waits the two edges a
detection takes. It clears one pending bit of several, holds a pin high past
a clear (an edge must not fire again, a level must), and clears a bit on the
very edge a new rising edge on its pin is detected.

The formal block (under `ifdef FORMAL`) assumes a manager that follows the
APB rules and asserts the response rules, the read data, and that every
register, both samples, the pins and `irq` equal a model of the
specification after every edge. The model's decode, strobe expansion (bit by
bit, from `N` and `pstrb`) and detection are written independently of the
design's.

# Requirements: `axil_timer`

The customer's requirements for a timer peripheral, given with the request
"Create an AXI4-Lite timer peripheral with an interrupt." to the whole-flow
case `flow/axil-timer` (council record 2026-11-17, decision 2). It is written
before the flow and is no stage's output. Every requirement states behaviour
at the block's ports and ends with its tag. The requirements specification
carries every requirement forward, and every later document restates each one
where it belongs, with the same tag.

Words used for time: an edge is a rising edge of `aclk`. A value "after edge
`E`" is the value in the clock cycle that follows `E`; a value "before edge
`E`" is the value in the clock cycle that ends at `E`. A transfer is accepted
on an edge on which its VALID and READY are both high.

## 1. The block

* One Verilog module named `axil_timer`: a 32-bit down-counting timer with a
  one-shot and a periodic mode and a level interrupt, behind an AXI4-Lite
  subordinate port. [req:TMR-MODULE]
* One parameter, `ADDR_WIDTH`, the byte address width: default 4, and the
  block works at every value from 4 to 8. With a width above 4, every offset
  from `0x10` up is unmapped (section 5). [req:TMR-ADDR-WIDTH]
* The ports, all synchronous to the rising edge of `aclk`: `aclk`;
  `aresetn` (active low; section 6); `s_axil_awaddr` (`ADDR_WIDTH` bits),
  `s_axil_awvalid`, `s_axil_awready`; `s_axil_wdata` (32 bits),
  `s_axil_wstrb` (4 bits, bit `n` enables bits `8n+7:8n`), `s_axil_wvalid`,
  `s_axil_wready`; `s_axil_bresp` (2 bits), `s_axil_bvalid`, `s_axil_bready`;
  `s_axil_araddr` (`ADDR_WIDTH` bits), `s_axil_arvalid`, `s_axil_arready`;
  `s_axil_rdata` (32 bits), `s_axil_rresp` (2 bits), `s_axil_rvalid`,
  `s_axil_rready`; and `irq` (1 bit, active high). The responses are `00`
  OKAY and `10` SLVERR. There are no other ports. [req:TMR-PORTS]

## 2. Registers

| Offset | Name | Access | Reset value | Fields |
|---|---|---|---|---|
| `0x0` | `CTRL` | read/write | `0x0` | bit 0 `EN`, bit 1 `IE`, bit 2 `MODE`; bits 31:3 read as zero |
| `0x4` | `LOAD` | read/write | `0x0` | the count length, in clock cycles |
| `0x8` | `COUNT` | read only | `0x0` | the cycles left in the current count |
| `0xC` | `STATUS` | write 1 to clear | `0x0` | bit 0 `EXPIRED`; bits 31:1 read as zero |

* The four registers sit at the offsets above, with the access types and
  reset values above. [req:TMR-MAP]
* `CTRL` is written only when `wstrb[0]` is set; a `CTRL` write without it
  changes nothing and still answers OKAY. `IE` is the interrupt enable;
  `MODE` is 0 for one-shot and 1 for periodic. [req:TMR-CTRL-STRB]
* `LOAD` is written byte by byte as `wstrb` enables, and reads back what was
  written. [req:TMR-LOAD]
* `STATUS`: a write of 1 to bit 0 with `wstrb[0]` set clears `EXPIRED`. A
  write of 0, or a write without `wstrb[0]`, leaves it as it is.
  [req:TMR-STATUS-CLEAR]

## 3. The timer

* `EN` written 1 starts a count: on the edge the write takes effect
  (`TMR-COUNT-LENGTH`), `COUNT` takes the value of `LOAD`. Written 1 while a count runs, it restarts the
  count from `LOAD` in the same way. [req:TMR-START]
* A `LOAD` of 0 counts as 1: a one-shot count started on edge `E` with
  `LOAD` 0 ends on edge `E + 1`. [req:TMR-LOAD-ZERO]
* In periodic mode a `LOAD` of 0 counts as 1 as well: a count started on
  edge `E` with `LOAD` 0 ends on every edge `E + 1`, `E + 2`, and so on.
  [req:TMR-LOAD-ZERO-PERIODIC]
* While `EN` is 1, `COUNT` goes down by one on every edge, except on two
  kinds of edge: the edge that ends the count (an edge with `EN` 1 and
  `COUNT` 1 or 0 before it), which sets `EXPIRED`; and the restart edge, an
  edge on which a `CTRL` write with `EN` 1 takes effect, on which `COUNT`
  takes the value of `LOAD` instead. [req:TMR-COUNT]
* Count length, exactly: a write takes effect on the edge that completes it
  (section 4), the edge after which `s_axil_bvalid` is first high for it. A
  count started on edge `E` with `LOAD` of `N` (at least 1) ends on edge
  `E + N`, and in periodic mode again on `E + 2N`, `E + 3N`, and so on. `irq` (when `IE` is 1) is high after the edge that
  ends the count. [req:TMR-COUNT-LENGTH]
* `COUNT` while a count runs: after the start edge `E` of a count with
  `LOAD` `N` (at least 1), `COUNT` is `N - k` after edge `E + k`, for `k`
  from 0 to `N - 1`. With `LOAD` 0, `COUNT` takes 0 on the start edge, not
  1, and stays 0. [req:TMR-COUNT-READ]
* One-shot (`MODE` 0): the edge that ends the count sets `COUNT` to 0 and
  clears `EN` itself, so `CTRL` reads `EN` 0 afterwards and nothing more
  happens, and no second interrupt comes, until `EN` is written 1 again.
  [req:TMR-ONESHOT]
* Periodic (`MODE` 1): the edge that ends the count loads `COUNT` from `LOAD`
  again and `EN` stays 1. With `LOAD` at least 1, every period is exactly
  `LOAD` cycles (a `LOAD` of 0: `TMR-LOAD-ZERO-PERIODIC`).
  [req:TMR-PERIODIC]
* `EN` written 0 stops the count: after the edge the write takes effect,
  `EN` reads 0, `COUNT` keeps the value that edge gave it, and no more counts
  end, until `EN` is written 1 again. [req:TMR-STOP]
* The stop edge is still an edge of the running count: unless it ends the
  count, `COUNT` goes down by one on it, so after the stop `COUNT` is one
  less than before the stop edge. `EN` written 0 while `EN` is already 0
  leaves `COUNT` as it is. [req:TMR-STOP-EDGE]
* A `CTRL` write that takes effect on the edge a count ends wins for `EN`
  and `COUNT`. With `EN` 1, `EN` stays 1 and `COUNT` takes the value of
  `LOAD`: the count restarts. With `EN` 0, `EN` is 0 after that edge and
  `COUNT` takes what the count end gives it under the `MODE` held before
  that edge, not the `MODE` the write sets: 0 when that `MODE` is 0
  (one-shot), the value of `LOAD` when it is 1 (periodic); `COUNT` then keeps
  that value. `EXPIRED` is still set by the count that ended.
  [req:TMR-CTRL-WINS]
* A count end beats a clear: when a `STATUS` clear takes effect on the edge
  a count ends, `EXPIRED` stays set. [req:TMR-END-BEATS-CLEAR]
* `irq` is `EXPIRED` and `IE`, as a level: it is high when both are 1 and
  low otherwise, it stays high until `EXPIRED` is cleared or `IE` is written
  0, and writing `IE` 1 while `EXPIRED` is set raises it. [req:TMR-IRQ]
* `irq` has no delay of its own: it changes after the very edge on which a
  write that sets or clears `IE`, or a `STATUS` clear, takes effect.
  [req:TMR-IRQ-EDGE]

## 4. Transfers

* Write address and write data may arrive in either order or together; a
  write completes on the edge that accepts the second of them, or both
  together. [req:TMR-ORDER]
* Readiness, one outstanding transaction per direction. `s_axil_awready` is
  high if and only if no write address is held and `s_axil_bvalid` is low;
  `s_axil_wready` is high if and only if no write data is held and
  `s_axil_bvalid` is low; `s_axil_arready` is high if and only if
  `s_axil_rvalid` is low. A write address is held after the edge that
  accepts it without its write data, until the edge that accepts that data;
  write data is held after the edge that accepts it without its address,
  until the edge that accepts that address; after the edge that completes a
  write nothing is held. So no new write address or data is accepted while a
  write response waits, and no new read address while a read response waits.
  [req:TMR-READY]
* `s_axil_bvalid` never rises before the write completes; once high it
  stays high, with `s_axil_bresp` stable, until an edge on which
  `s_axil_bready` is high, and is low after that edge. `s_axil_rvalid` never
  rises before the read address is accepted; once high it stays high, with
  `s_axil_rdata` and `s_axil_rresp` stable, until an edge on which
  `s_axil_rready` is high, and is low after that edge. [req:TMR-RESPONSE]
* `s_axil_bvalid` is high after the same edge that completes the write, not
  a later one; `s_axil_rvalid` is high after the same edge that accepts the
  read address, not a later one. [req:TMR-RESPONSE-EDGE]
* A read returns the value the register holds before the edge that accepts
  its address, not the value that edge gives it. [req:TMR-READ-VALUE]

## 5. Responses and unmapped addresses

* An address is mapped only when it is word aligned (`addr[1:0]` is 0) and
  below `0x10`. Every other address is unmapped and never aliases a register.
  [req:TMR-DECODE]
* An unmapped write, and any write to `COUNT`, changes nothing and gets
  SLVERR. An unmapped read returns zero with SLVERR. Every other transfer gets
  OKAY. [req:TMR-SLVERR]

## 6. Reset

* `aresetn` is active low. Reset puts every register at its reset value,
  stops the count and clears `EXPIRED`; `irq` is low after reset.
  [req:TMR-RESET]
* `aresetn` is synchronous: it is sampled on the rising edge of `aclk`, and
  every edge on which it is low resets the block. After such an edge
  `s_axil_bvalid` and `s_axil_rvalid` are low and no write address or write
  data is held, whatever was in progress. The manager does not start a
  transfer while `aresetn` is low. [req:TMR-RESET-EDGE]

## 7. Implementation and verification

* Verilator `--lint-only -Wall` clean with no waivers, and Yosys synthesis
  with no latches. [req:TMR-CLEAN]
* A self-checking testbench that passes under Icarus Verilog on a block that
  meets this document and instantiates the block at `ADDR_WIDTH` 4 and at a
  width above 4. [req:TMR-TB]
* The testbench checks every requirement in sections 2 to 6, each count
  timed to the clock edge. [req:TMR-TB-ALL]
* Tests accept the whole allowed range. A testbench checks only what this
  document states, and accepts every behaviour it allows; it never requires
  one choice where this document leaves a choice open. This document leaves
  no timing or response choice open: every rule in sections 3 to 6 is exact.
  [req:TMR-TEST-RANGE]

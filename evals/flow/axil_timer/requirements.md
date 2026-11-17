# Requirements: `axil_timer`

The customer's requirements for a timer peripheral, given with the request
"Create an AXI4-Lite timer peripheral with an interrupt." to the whole-flow
case `flow/axil-timer` (council record 2026-11-17, decision 2). It is written
before the flow and is no stage's output. Every requirement states behaviour
at the block's ports and ends with its tag. The requirements specification
carries every requirement forward, and every later document restates each one
where it belongs, with the same tag.

## 1. The block

* One Verilog module named `axil_timer`: a 32-bit down-counting timer with a
  one-shot and a periodic mode and a level interrupt, behind an AXI4-Lite
  subordinate port. [req:TMR-MODULE]
* One parameter, `ADDR_WIDTH`, the byte address width: default 4, and the
  block works at every value from 4 to 8. With a width above 4, every offset
  from `0x10` up is unmapped (section 5). [req:TMR-ADDR-WIDTH]
* The ports, all synchronous to the rising edge of `aclk`: `aclk`;
  `aresetn` (active low, synchronous); `s_axil_awaddr` (`ADDR_WIDTH` bits),
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

* `EN` written 1 starts a count: `COUNT` takes the value of `LOAD`. Written 1
  while a count runs, it restarts the count from `LOAD`. [req:TMR-START]
* A `LOAD` of 0 counts as 1. [req:TMR-LOAD-ZERO]
* While `EN` is 1, `COUNT` goes down by one on every clock edge, except on
  the edge that ends the count: an edge on which `EN` is 1 and `COUNT` is 1
  or 0. That edge sets `EXPIRED`. [req:TMR-COUNT]
* Count length, exactly: a write takes effect on the clock edge after which
  `s_axil_bvalid` is first high. A count started on edge `E` with `LOAD` of
  `N` (at least 1) ends on edge `E + N`, and in periodic mode again on
  `E + 2N`, `E + 3N`, and so on. `irq` (when `IE` is 1) is high after the edge
  that ends the count. [req:TMR-COUNT-LENGTH]
* One-shot (`MODE` 0): the edge that ends the count sets `COUNT` to 0 and
  clears `EN` itself, so `CTRL` reads `EN` 0 afterwards and nothing more
  happens, and no second interrupt comes, until `EN` is written 1 again.
  [req:TMR-ONESHOT]
* Periodic (`MODE` 1): the edge that ends the count loads `COUNT` from `LOAD`
  again and `EN` stays 1. Every period is exactly `LOAD` cycles (1 when
  `LOAD` is 0). [req:TMR-PERIODIC]
* `EN` written 0 stops the count: `COUNT` keeps its value and no more counts
  end until `EN` is written 1 again. [req:TMR-STOP]
* A `CTRL` write that lands on the edge a count ends wins for `EN` and
  `COUNT` (`EN` 1 restarts from `LOAD`, `EN` 0 stops); `EXPIRED` is still set
  by the count that ended. [req:TMR-CTRL-WINS]
* A count end beats a clear: when a `STATUS` clear lands on the edge a count
  ends, `EXPIRED` stays set. [req:TMR-END-BEATS-CLEAR]
* `irq` is `EXPIRED` and `IE`, as a level: it stays high until `EXPIRED` is
  cleared or `IE` is written 0, and it is high at once after `IE` is written
  1 while `EXPIRED` is set. [req:TMR-IRQ]

## 4. Transfers

* Write address and write data may arrive in either order or together; a
  write completes when both have been accepted. [req:TMR-ORDER]
* `s_axil_awready` is high whenever no write address is held and no write
  response is waiting; `s_axil_wready` is high whenever no write data is held
  and no write response is waiting. [req:TMR-READY]
* `s_axil_bvalid` rises on the edge after the write completes and stays high,
  with `s_axil_bresp` stable, until `s_axil_bready`. `s_axil_arready` is high
  whenever no read response is waiting; `s_axil_rvalid` rises on the edge
  after the read address is accepted and stays high, with `s_axil_rdata` and
  `s_axil_rresp` stable, until `s_axil_rready`. A read returns the register's
  value on the edge its address was accepted. [req:TMR-RESPONSE]

## 5. Responses and unmapped addresses

* An address is mapped only when it is word aligned (`addr[1:0]` is 0) and
  below `0x10`. Every other address is unmapped and never aliases a register.
  [req:TMR-DECODE]
* An unmapped write, and any write to `COUNT`, changes nothing and gets
  SLVERR. An unmapped read returns zero with SLVERR. Every other transfer gets
  OKAY. [req:TMR-SLVERR]

## 6. Reset

* `aresetn` is active low and sampled on the rising edge of `aclk`. Reset
  puts every register at its reset value, stops the count, clears `EXPIRED`
  and any held request, and drops `s_axil_bvalid` and `s_axil_rvalid`; `irq`
  is low after reset. [req:TMR-RESET]

## 7. Implementation and verification

* Verilator `--lint-only -Wall` clean with no waivers, and Yosys synthesis
  with no latches. [req:TMR-CLEAN]
* A self-checking testbench, passing under Icarus Verilog, that instantiates
  the block at `ADDR_WIDTH` 4 and at a width above 4 and checks every
  requirement in sections 2 to 6, each count timed to the clock edge.
  [req:TMR-TB]
* Tests accept the whole allowed range. A testbench checks only what this
  document states, and accepts every behaviour it allows; it never requires
  one choice where this document leaves a choice open. This document leaves
  no timing or response choice open: every rule in sections 3 to 6 is exact.
  [req:TMR-TEST-RANGE]

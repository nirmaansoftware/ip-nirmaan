# Interface specification: `axil_timer`

A 32-bit down-counting timer with one-shot and periodic modes and a level
interrupt, behind an AXI4-Lite subordinate port. This is the upstream
specification of the eval case `rtl/axil-timer` (P3-E2); the block itself is
the M29 firmware fixture `axil_timer.v`, extended with the periodic mode. Its
channel behavior is the same as the AXI4-Lite register block in
`../axi4_lite/`.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `ADDR_WIDTH` | 4 | Byte address width, 4 to 8. The registers fill offsets `0x0` to `0xC`; with a wider address every offset from `0x10` up is unmapped. |

The block must work at every `ADDR_WIDTH` from 4 to 8.

## 2. Ports

All signals are synchronous to the rising edge of `aclk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `aclk` | in | 1 | Clock. |
| `aresetn` | in | 1 | Reset, active low, synchronous. |
| `s_axil_awaddr` | in | `ADDR_WIDTH` | Write address. |
| `s_axil_awvalid` | in | 1 | Write address valid. |
| `s_axil_awready` | out | 1 | Write address ready. |
| `s_axil_wdata` | in | 32 | Write data. |
| `s_axil_wstrb` | in | 4 | Write byte enables; bit `n` enables bits `8n+7:8n`. |
| `s_axil_wvalid` | in | 1 | Write data valid. |
| `s_axil_wready` | out | 1 | Write data ready. |
| `s_axil_bresp` | out | 2 | Write response: `00` OKAY, `10` SLVERR. |
| `s_axil_bvalid` | out | 1 | Write response valid. |
| `s_axil_bready` | in | 1 | Write response ready. |
| `s_axil_araddr` | in | `ADDR_WIDTH` | Read address. |
| `s_axil_arvalid` | in | 1 | Read address valid. |
| `s_axil_arready` | out | 1 | Read address ready. |
| `s_axil_rdata` | out | 32 | Read data. |
| `s_axil_rresp` | out | 2 | Read response: `00` OKAY, `10` SLVERR. |
| `s_axil_rvalid` | out | 1 | Read data valid. |
| `s_axil_rready` | in | 1 | Read data ready. |
| `irq` | out | 1 | Interrupt, active high, level sensitive. |

## 3. Register map

| Offset | Name | Access | Reset value | Fields |
|---|---|---|---|---|
| `0x0` | `CTRL` | read/write | `0x0` | bit 0 `EN`, bit 1 `IE`, bit 2 `MODE`; bits 31:3 read as zero |
| `0x4` | `LOAD` | read/write | `0x0` | the count length, in clock cycles |
| `0x8` | `COUNT` | read only | `0x0` | the cycles left in the current count |
| `0xC` | `STATUS` | write 1 to clear | `0x0` | bit 0 `EXPIRED`; bits 31:1 read as zero |

* **`CTRL`** is written only when `wstrb[0]` is set (all its fields are in
  byte 0); a write without it changes nothing and still answers OKAY.
  * `EN` written 1 starts a count: `COUNT` takes the value of `LOAD`. Written
    1 while a count runs, it restarts the count from `LOAD`.
  * `EN` written 0 stops the count. `COUNT` keeps its value; no more counts
    end until `EN` is written 1 again.
  * `IE` is the interrupt enable. `MODE` is 0 for one-shot, 1 for periodic.
* **`LOAD`** is a plain storage register, written byte by byte as `wstrb`
  enables. A `LOAD` of 0 counts as 1.
* **`COUNT`** cannot be written: a write gets SLVERR and changes nothing.
* **`STATUS`**: writing a 1 to bit 0 with `wstrb[0]` set clears `EXPIRED`.
  Writing 0, or writing without `wstrb[0]`, leaves it as it is.

## 4. The timer

While `EN` is 1, `COUNT` goes down by one on every clock edge, except on the
end of the count: an edge on which `EN` is 1 and `COUNT` is 1 or 0. On it:

* `EXPIRED` is set.
* **One-shot** (`MODE` 0): `COUNT` becomes 0 and `EN` clears itself, so
  `CTRL` reads `EN` 0 after the count ends. Nothing else happens until `EN`
  is written 1 again.
* **Periodic** (`MODE` 1): `COUNT` takes the value of `LOAD` again and `EN`
  stays 1, so the next count ends `LOAD` edges later. Every period is
  exactly `LOAD` cycles (1 when `LOAD` is 0).

Timing: a write takes effect on the clock edge after which `BVALID` is first
high. A count started on edge `E` with `LOAD` of `N` (at least 1) ends on edge
`E + N`, and in periodic mode again on `E + 2N`, `E + 3N`, and so on.

When a `CTRL` write lands on the edge a count ends, the write wins for `EN`
and `COUNT`: `EN` 1 restarts from `LOAD`; `EN` 0 stops, with `COUNT` at the
value that edge gives it. `EXPIRED` is still set by the count that ended.

**A count end beats a clear.** When a `STATUS` clear lands on the edge a count
ends, `EXPIRED` stays set: the new expiry is not lost.

`irq` is `EXPIRED` and `IE`: it stays high until the expiry is cleared or
`IE` is written 0, and it rises at once when `IE` is written 1 with `EXPIRED`
already set.

## 5. Transfers

* **Independent channels.** `AWREADY` is high whenever no write is held and
  no write response is waiting; `WREADY` likewise. The address and the data
  may arrive in either order, or together. A write completes when both have
  been accepted.
* **One outstanding transaction per direction.** `BVALID` rises on the edge
  after the write completes and stays high, with `BRESP` stable, until
  `BREADY`. `ARREADY` is high whenever no read response is waiting; `RVALID`
  rises on the edge after the address is accepted and stays high, with
  `RDATA` and `RRESP` stable, until `RREADY`.
* A read returns the register's value on the edge the address was accepted.

## 6. Responses and unmapped addresses

* An address is mapped only when it is word aligned (`addr[1:0] == 0`) and
  below `0x10`. Every other address is unmapped: unaligned ones always, and,
  when `ADDR_WIDTH` is above 4, every offset from `0x10` up. An unmapped
  address must never alias a register.
* An unmapped write, and any write to `COUNT`, changes nothing and gets
  SLVERR. An unmapped read returns zero with SLVERR.
* Every other transfer gets OKAY.

## 7. Reset

`aresetn` is active low and sampled on the rising edge of `aclk`. Reset puts
every register at its reset value, stops the count, clears `EXPIRED` and any
held request, and drops `BVALID` and `RVALID`. The manager does not start a
transfer while `aresetn` is low.

## 8. Verification requirements

* Verilator `--lint-only -Wall` clean, with no waivers.
* A self-checking testbench, passing under Icarus Verilog and Verilator, that
  covers: reset values; `LOAD` read back with partial strobes; both channel
  orders and response backpressure; `COUNT` read only and the SLVERR policy,
  including offsets from `0x10` up at `ADDR_WIDTH` 8; a `CTRL` write without
  `wstrb[0]`; one-shot counts timed to the cycle, with `EN` clearing itself
  and no second interrupt; the interrupt enable on a pending expiry; periodic
  counts timed over several periods; a stop that freezes `COUNT`; a restart;
  and reset during a count.
* Synthesizes with Yosys, with no latches.
* A formal proof of the channel rules and of the timer against the rules
  above, with covers that show each timer path is reached.

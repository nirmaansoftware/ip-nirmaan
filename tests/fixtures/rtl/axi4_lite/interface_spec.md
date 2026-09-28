# Interface specification: `axi4_lite_regs`

A block of four 32-bit control and status registers behind an AXI4-Lite
subordinate port. This is the M23 reference fixture: the specification a spec
engineer hands to the microarchitecture and RTL seats.

## 1. Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `ADDR_WIDTH` | 4 | Byte address width. 4 bits cover the four registers. |
| `DATA_WIDTH` | 32 | Data bus width. `wstrb` is `DATA_WIDTH/8` bits wide. |

Only the defaults are required to work. Any other value is outside this
specification.

## 2. Ports

All signals are synchronous to the rising edge of `aclk`.

| Port | Dir | Width | Description |
|---|---|---|---|
| `aclk` | in | 1 | Clock. |
| `aresetn` | in | 1 | Reset, active low, synchronous. |
| `s_axil_awaddr` | in | `ADDR_WIDTH` | Write address. |
| `s_axil_awvalid` | in | 1 | Write address valid. |
| `s_axil_awready` | out | 1 | Write address ready. |
| `s_axil_wdata` | in | `DATA_WIDTH` | Write data. |
| `s_axil_wstrb` | in | `DATA_WIDTH/8` | Write byte enables; bit `n` enables byte `n` (bits `8n+7:8n`). |
| `s_axil_wvalid` | in | 1 | Write data valid. |
| `s_axil_wready` | out | 1 | Write data ready. |
| `s_axil_bresp` | out | 2 | Write response. |
| `s_axil_bvalid` | out | 1 | Write response valid. |
| `s_axil_bready` | in | 1 | Write response ready. |
| `s_axil_araddr` | in | `ADDR_WIDTH` | Read address. |
| `s_axil_arvalid` | in | 1 | Read address valid. |
| `s_axil_arready` | out | 1 | Read address ready. |
| `s_axil_rdata` | out | `DATA_WIDTH` | Read data. |
| `s_axil_rresp` | out | 2 | Read response. |
| `s_axil_rvalid` | out | 1 | Read data valid. |
| `s_axil_rready` | in | 1 | Read data ready. |

The protection signals (`awprot`, `arprot`) are not part of this interface:
the registers have no access protection.

## 3. Register map

| Offset | Name | Access | Reset value |
|---|---|---|---|
| `0x0` | `REG0` | read/write | `0x00000000` |
| `0x4` | `REG1` | read/write | `0x00000000` |
| `0x8` | `REG2` | read/write | `0x00000000` |
| `0xC` | `REG3` | read/write | `0x00000000` |

Each register is a plain 32-bit storage register: a read returns the last
value written, byte by byte, as enabled by `wstrb`.

## 4. Transactions

* **Handshakes.** Every channel uses the AXI VALID/READY handshake: a transfer
  happens on a rising edge where both are high. The subordinate may raise
  READY before VALID, and it never lowers BVALID or RVALID, or changes their
  payload, until the manager takes the response.
* **One outstanding transaction** per direction. The subordinate accepts no new
  write address or write data while a write response is pending, and no new
  read address while read data is pending. Reads and writes are independent
  and may be in flight at the same time.
* **Write address and write data are independent.** AW and W may arrive in
  either order, in the same cycle, or with any gap between them. The write is
  performed when both have been accepted.
* **Byte enables.** Only the bytes whose `wstrb` bit is set are written. A write
  with `wstrb` all zero changes nothing and is still answered with OKAY.

## 5. Responses and unmapped addresses

* A mapped access is answered with **OKAY** (`2'b00`).
* **Policy for unmapped addresses: SLVERR** (`2'b10`). An address is mapped only
  when it is word aligned (`addr[1:0] == 0`) and is one of `0x0`, `0x4`,
  `0x8`, `0xC`. With `ADDR_WIDTH` 4 the unmapped addresses are the misaligned
  ones (for example `0x5` or `0xE`).
  * An unmapped write changes no register and is answered with SLVERR.
  * An unmapped read returns `rdata` of zero with SLVERR.
* DECERR is not used: it is reserved for an interconnect that finds no
  subordinate at all, while this subordinate did receive the access.

## 6. Latency

Latency is counted from the rising edge that completes the request (for a
write, the edge that accepts the later of AW and W; for a read, the edge that
accepts AR) to the first rising edge at which BVALID or RVALID is high.

* The bound is **at most 2 cycles** for both writes and reads.
* This design meets it with 1 cycle: the response is valid in the cycle right
  after the request completes.
* After a response is taken, the channel can accept a new request in the next
  cycle.

## 7. Reset

* `aresetn` is active low and sampled on the rising edge of `aclk`.
* During and after reset, BVALID and RVALID are low, and every register holds
  its reset value (zero). Any half-accepted write (AW without W, or W without
  AW) is discarded.
* The manager keeps its VALID signals low while `aresetn` is low.

## 8. Verification requirements

* Verilator `--lint-only -Wall` clean, with no waivers.
* A self-checking testbench, passing under Icarus Verilog and Verilator, that
  covers: reset values; write then read of every register; `wstrb` partial
  writes; AW before W, W before AW, and both together; B and R backpressure;
  back-to-back transactions; the SLVERR policy; and the latency bound.
* Synthesizes with Yosys, with no latches.
* A formal proof of the handshake rules: responses hold until taken, follow
  only accepted requests, and at most one transaction is outstanding.

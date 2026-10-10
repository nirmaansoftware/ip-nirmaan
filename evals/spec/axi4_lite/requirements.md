# Requirements: `axi4_lite_regs`

The approved requirements for a small register block, written for the M45
evaluation of the interface specification seat. Each requirement ends with its
tag. The interface specification restates every requirement below in the
section where it belongs, in its own words and with the detail an RTL engineer
needs, and ends that statement with the same tag, exactly once.

## 1. The block

* A block of four 32-bit read/write registers, `REG0` to `REG3`, at byte
  offsets `0x0`, `0x4`, `0x8`, and `0xC`, each resetting to zero.
* An AXI4-Lite subordinate port. Every port is named with the `s_axil_` prefix
  and the AXI4-Lite channel signal name (for example `s_axil_awaddr`,
  `s_axil_bresp`), on clock `aclk` and active-low reset `aresetn`. There are no
  protection signals.
* Parameters `ADDR_WIDTH` (default 4) and `DATA_WIDTH` (default 32).

## 2. Behavior

* Write address and write data may arrive in either order, in the same cycle,
  or with any gap; the write happens when both have been accepted. [req:AXIL-ORDER]
* Only the bytes whose write strobe (`wstrb`) bit is set are written; a write
  with no strobe bit set changes nothing and still completes normally. [req:AXIL-WSTRB]
* An access to an address that is not one of the four registers, or not word
  aligned, is answered with SLVERR, changes no register, and a read of it
  returns zero. [req:AXIL-SLVERR]
* A response is valid at most 2 cycles after its request completes, for both
  reads and writes. [req:AXIL-LATENCY]
* After a response is taken, the channel accepts a new request in the next
  cycle. [req:AXIL-B2B]
* During and after reset no response is valid, every register holds zero, and
  a write with only one of address or data accepted is discarded. [req:AXIL-RESET]

## 3. Implementation and verification

* The design synthesizes with Yosys with no latches. [req:AXIL-SYNTH]
* The handshake rules are proven formally: responses hold until taken, follow
  only accepted requests, and at most one transaction is outstanding per
  direction. [req:AXIL-FORMAL]

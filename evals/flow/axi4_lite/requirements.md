# Requirements: `axi4_lite_regs`

The customer's requirements for a small register block and its driver, given
with the request "Create an AXI4-Lite register block and its driver." to the
whole-flow case `flow/axi4-lite-regs-driver` (council record 2026-11-17,
decision 2). It is the case's own copy of `evals/spec/axi4_lite/requirements.md`
(the single-seat specification case's document, which stays as it is), with
tags added to section 1, section 4 added, and rules split so that each
tag states only what the case judges: the protection signals
(`AXIL-NO-PROT`), the parameter defaults (`AXIL-PARAMS-DEFAULT`) and "no
other ports" (`AXIL-PORTS-ONLY`) have their own tags, and `AXIL-B2B` says
what accepting a new request in the next cycle means at the ports; the latency
bound with READY already high (`AXIL-LATENCY-READY-HIGH`) and what reset does from its
first edge (`AXIL-RESET-REGS`) have their own tags. It is written before the flow and is no stage's output. Each
requirement ends with its tag. The requirements specification carries every
requirement forward, and the interface specification restates every
requirement below in the section where it belongs, in its own words and with
the detail an RTL engineer needs, and ends that statement with the same tag,
exactly once.

## 1. The block

* A block of four 32-bit read/write registers, `REG0` to `REG3`, at byte
  offsets `0x0`, `0x4`, `0x8`, and `0xC`, each resetting to zero. [req:AXIL-MAP]
* An AXI4-Lite subordinate port. Each AXI4-Lite channel signal is a port
  named with the `s_axil_` prefix and the signal name (for example
  `s_axil_awaddr`, `s_axil_bresp`), on clock `aclk` and active-low reset
  `aresetn`. [req:AXIL-PORTS]
* The block has no ports other than those. [req:AXIL-PORTS-ONLY]
* There are no protection signals. [req:AXIL-NO-PROT]
* Parameters `ADDR_WIDTH` and `DATA_WIDTH`. [req:AXIL-PARAMS]
* `ADDR_WIDTH` defaults to 4 and `DATA_WIDTH` to 32. [req:AXIL-PARAMS-DEFAULT]

## 2. Behavior

* Write address and write data may arrive in either order, in the same cycle,
  or with any gap; the write happens when both have been accepted. [req:AXIL-ORDER]
* Only the bytes whose write strobe (`wstrb`) bit is set are written; a write
  with no strobe bit set changes nothing and still completes normally. [req:AXIL-WSTRB]
* An access to an address that is not one of the four registers, or not word
  aligned, is answered with SLVERR, changes no register, and a read of it
  returns zero. [req:AXIL-SLVERR]
* A response is valid at most 2 cycles after its request completes, for both
  reads and writes, while the manager's response READY is low until the
  response is valid. [req:AXIL-LATENCY]
* The same bound holds when the manager's response READY (`s_axil_bready`
  for a write, `s_axil_rready` for a read) is already high on the edge that
  completes the request: the response is valid, and is taken on the first
  edge it is valid, not lost because READY was early.
  [req:AXIL-LATENCY-READY-HIGH]
* After a response is taken, the channel accepts a new request in the next
  cycle: a write address and write data offered together in the cycle after
  the edge that takes a write response are both accepted on the edge that
  ends that cycle, and a read address offered in the cycle after the edge
  that takes a read response is accepted on the edge that ends that cycle.
  [req:AXIL-B2B]
* During and after reset no response is valid, and after reset every
  register holds zero and a write with only one of address or data accepted
  is discarded. [req:AXIL-RESET]
* During reset, from the very first edge on which `aresetn` is low, every
  register holds zero and a write with only one of address or data accepted
  is discarded, not only from a later reset edge. [req:AXIL-RESET-REGS]

## 3. Implementation and verification

* The design synthesizes with Yosys with no latches. [req:AXIL-SYNTH]
* The handshake rules are proven formally: responses hold until taken, follow
  only accepted requests, and at most one transaction is outstanding per
  direction. [req:AXIL-FORMAL]

## 4. Tests

* Tests accept the whole allowed range. A testbench or a driver test checks
  only what this document states, and accepts every behaviour it allows; it
  never requires one choice where this document leaves a choice open. For
  example, counted from the clock edge that completes the request to the
  first edge with the response valid, the latency requirement above allows a
  response 1 or 2 cycles after its request (it cannot be valid before its
  request is accepted), so a test accepts both and requires neither.
  [req:AXIL-TEST-RANGE]

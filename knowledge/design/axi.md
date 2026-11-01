---
id: design/axi
skill: axi
as_of: 2026-10-31
review_by: 2027-04-30
sources:
  - open | Gisselquist, AXI Handshaking Rules, ZipCPU blog, 2021 [Rules] | https://zipcpu.com/blog/2021/08/28/axi-rules.html
  - open | Gisselquist, Building an AXI-Lite slave the easy way, ZipCPU blog, 2020 [Easy] | https://zipcpu.com/blog/2020/03/08/easyaxil.html
  - open | Gisselquist, Using a formal property file to verify an AXI-lite peripheral, ZipCPU blog, 2018 [Props] | https://zipcpu.com/formal/2018/12/28/axilite.html
  - open | Gisselquist, axil2apb.v, an AXI-Lite to APB bridge with its proof, WB2AXIP (Apache 2.0) [A2APB] | https://github.com/ZipCPU/wb2axip/blob/master/rtl/axil2apb.v
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source; the Arm AXI specification is not a source here (it comes under a licence accepted by use)
export_screen: clear
writer: IP-P3-K1 session (P3 pilot, item K1, 2026-10-31)
checker: pending, a different session reads the sources in P3-C1 and writes the check record
---
Knowledge only: no tool run backs this.

# AXI4-Lite subordinate

This pilot covers one thing: an AXI4-Lite subordinate (the cited sources say
slave), such as a register block. Full AXI, bursts, IDs and interconnects are
out of scope. Tags in brackets name the sources above. A line marked
"inference" is this document's own reasoning from the cited source, not a
statement the source makes. The specification itself is not cited (see
`licence_check`), so a block's own interface spec is the authority wherever
it is more precise than this page.

## Channels

AXI has five channels: write address (AW), write data (W), write response
(B), read address (AR) and read data (R) [Props]. Each has a VALID from the
side that sends and a READY from the side that receives [Easy] [Props].
AXI-Lite carries one data item per request and has no bursts, IDs, locking,
quality of service or cache signals [Props]; it also has no size signal, so
`WSTRB` is the only way to write part of a word [Easy].

## Handshake rules

- A transfer happens on a clock where VALID and READY are both high, and only
  then; when both are high something must happen, so add no other condition
  to that test [Rules].
- VALID is low after any reset [Rules] [Props].
- Once raised, VALID stays high until the handshake, and the payload holds
  still meanwhile [Props]; the subordinate asserts this of B and R and
  assumes it of AW, W and AR [Props].
- VALID must not depend on READY of the same channel; READY may be raised
  before VALID or in response to it [Props].
- No combinational path from an input to an output: register READY, and use
  a skid buffer where a registered READY would cost throughput [Rules]. A
  READY computed combinationally from the same channel's VALID breaks this
  (inference from [Rules]).
- Recommended, not required: hold READY high while idle and lower it only
  after a transfer [Rules].

## Writes

- AW and W arrive independently: either may come first, or both on one clock,
  and the subordinate must pair them itself [Props]. A simple design raises
  AWREADY and WREADY together only when both VALIDs are high [Easy]. Bounds on
  how far apart they arrive came from a vendor guide, not the specification,
  in the author's reading [Props], so do not rely on them (inference).
- Send B only after both the address and the data of that write were
  accepted, and send exactly one B per write [Props]; a response can never
  come on the same cycle as its request [Props].
- Back-pressure: while BVALID is high and BREADY low, accept no new write,
  or its response is lost and the bus hangs [Easy] [Props]. Because a
  registered READY is decided a clock early, the simple design accepts at
  most one write every other clock [Easy].
- `WSTRB` bit k enables byte k (bits 8k+7 down to 8k); with no strobe set,
  nothing changes. A manager may send a write with every strobe low, so
  support strobes rather than ignore them [Easy].

## Reads

- Accept a read only when the R channel can take its answer: while RVALID is
  high and RREADY low, hold ARREADY low [Easy] [Props]. The simple design
  sets ARREADY to the inverse of RVALID [Easy].
- The answer comes at the earliest on the clock after the request, and one R
  follows each accepted AR [Props]. Change RDATA only when the channel is not
  stalled (RVALID low or RREADY high) [Easy] [Rules]; while stalled, RDATA and
  RRESP hold [Props].

## Reads and writes together

If AW and AR are both accepted on one clock, both transactions must be
processed, or one held for later; handling only one loses or corrupts the
other [Rules]. Simple fixes: give one side priority with a combinational
grant [Rules], or alternate between reads and writes as the APB bridge does
[A2APB].

## Responses

- `BRESP` and `RRESP` are 2'b00, OKAY, when nothing went wrong [Easy].
- AXI defines three outcomes: OK, an error from the subordinate, and an error
  from the interconnect [Props]. The code 2'b01 is never valid here
  [Props]. A manager treats a response with bit 1 set as an error [Easy], and
  the APB bridge answers an APB error with 2'b10 [A2APB].
- There is no abort: after an error every outstanding request still gets its
  response [Props].
- Which accesses err (unmapped or misaligned addresses, read-only registers)
  and whether an erroring write changes state is the block's spec
  (inference).

## Addresses and protection

Decode the word address: drop the bits below log2 of the bus width in bytes,
which is 2 for a 32-bit bus [Easy]. The simple design leaves the protection
bits (`AWPROT`, `ARPROT`) unused [Easy]; the APB bridge forwards them to APB
[A2APB].

## Throughput

Without skid buffers the simple design moves one transfer every other clock;
with a skid buffer on AW, W and AR it can move one per clock [Easy].

## Common failure modes

- A write or read accepted while its response channel is stalled, so a
  response is lost [Easy] [Props].
- B sent before both halves of the write arrived [Props].
- An extra condition in the handshake test, so a transfer is missed [Rules].
- AW and AR accepted together with only one handled [Rules].
- The payload or RDATA changing while stalled [Props] [Easy].
- Strobes ignored [Easy].
- VALID not cleared by reset [Rules].

## How a result is checked

- **Properties.** Bind a property set to the subordinate: assume the manager
  rules on AW, W and AR, assert the subordinate's on B and R (reset, stable
  payload, no response without an outstanding request, bounded waits and
  delays) [Props]. It counts outstanding requests per channel; a response
  needs a count above zero [Props].
- **Induction.** With the property set alone a bounded check can pass;
  an unbounded proof also needs assertions tying those counts to the design's
  own state, for example one outstanding write exactly when BVALID is high
  [Easy] [Props].
- **Covers.** Cover a completed write and a completed read [Props], and
  several in a row to measure throughput [Props]; cover writes and reads of
  every register (inference).
- **Contract.** Assert that a read returns the register it addressed [Easy].
- **Simulation.** Hold BREADY and RREADY low for a while: back-pressure is
  the case simulation tends to miss [Easy]. Also send AW before W, W before
  AW, both together, a read and a write on the same clock, and partial and
  empty strobes (inference from the rules above).

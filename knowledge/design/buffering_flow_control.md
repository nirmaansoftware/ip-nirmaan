---
id: design/buffering_flow_control
skill: buffering_flow_control
as_of: 2026-11-03
review_by: 2027-05-03
sources:
  - open | Gisselquist, Lesson 10: Adding a FIFO, ZipCPU tutorial [Tut] | https://zipcpu.com/tutorial/lsn-10-fifo.pdf
  - open | Gisselquist, Getting the basic FIFO right, ZipCPU blog, 2017 [Blog] | https://zipcpu.com/blog/2017/07/29/fifo.html
  - open | lowRISC, OpenTitan prim_fifo_sync.sv and prim_fifo_sync_cnt.sv (Apache 2.0) [OT] | https://github.com/lowRISC/opentitan/tree/master/hw/ip/prim/rtl
  - open | LaForest, Pipeline FIFO Buffer, FPGA Design Elements (MIT) [LaF] | https://fpgacpu.ca/fpga/Pipeline_FIFO_Buffer.html
  - open | Gisselquist, AXI Handshaking Rules, ZipCPU blog, 2021 [Rules] | https://zipcpu.com/blog/2021/08/28/axi-rules.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-P3-K2 session (P3 pilot, item K2, 2026-11-03)
checker: pending, a different session reads the sources in P3-C2 and writes the check record
---
Knowledge only: no tool run backs this.

# Buffering and flow control

Single-clock FIFOs: pointers, full, empty and count at any depth, with a
valid/ready handshake on each side. Tags in brackets name the sources above;
a line marked "inference" is this document's own reasoning.

## Handshake on each side

- A transfer happens on an edge where valid and ready are both high, and
  every such edge must act, with no extra condition [Rules].
- Valid is low after reset. While valid is high and ready low, valid and
  the payload hold [Rules].
- Write side: ready is not full; a push is valid and ready. Read side:
  valid is not empty; a pop is valid and ready [OT]. A push when full or a
  pop when empty is then refused, and the caller handles it [Tut].
- One FIFO holds write ready low for the cycle after reset [OT].
- A pass-through option forwards a push on an empty FIFO to the read side
  in the same cycle [OT], which makes a combinational path from input to
  output (inference).

## Pointers, full and empty

- Depth 2^N with N-bit pointers: equal pointers mean empty and also full,
  so only 2^N - 1 entries are usable. Give each pointer one extra bit: the
  count is their difference, empty is a count of 0, full a count of 2^N
  [Tut].
- Any depth D: each pointer counts 0 to D-1 and is reset to 0 by logic
  after D-1, not by binary overflow; a wrap bit toggles on each wrap.
  Empty is equal pointers with equal wrap bits; full is equal pointers with
  different wrap bits [OT] [LaF].
- Count at any depth: D when full; write minus read pointer when the wrap
  bits match; D minus read plus write when they differ. The count needs
  enough bits to hold D itself [OT].
- A non power-of-two depth that wraps by overflow addresses entries past
  D-1 and breaks the flags (inference from [OT] [LaF]).
- Push and pop together: when empty the pop is refused unless pass-through
  is on [OT]; when full the common form refuses the push [OT] [Tut],
  though one older design accepts it [Blog]. The spec must pick
  (inference).

## Timing of flags and data

- Flags from a pointer subtract and compare sit in front of every update.
  Register them, computing next values one clock early [Blog] [Tut].
- A count kept as a register must move with accepted pushes and pops; a
  registered pointer difference is a cycle late [Blog].
- Reading memory at the read pointer combinationally gives first-word
  fall-through; a RAM with a registered read needs a bypass register or an
  empty flag delayed a cycle [Tut]. One FIFO registers its output, with
  two cycles from input to output [LaF]. The spec states the latency
  (inference).
- Output data while empty is a don't care unless the spec says otherwise;
  one design drives zero [OT].
- Reset and any synchronous clear empty the FIFO by zeroing pointers and
  wrap bits; the storage needs no reset [OT] [Blog].

## Sizing

- A FIFO absorbs rate differences and, in loops, holds enough to avoid
  deadlock [LaF]. A producer stopped by a nearly full flag needs space for
  the data already on its way [Tut].

## Common failure modes

- Full and empty that cannot be told apart [Tut].
- A wrap at a power of two when D is not one (inference).
- A count off by one, or a cycle late [Blog].
- A push accepted when full, or a pop when empty (inference).
- Payload or valid changed while stalled [Rules].

## How a result is checked

- Proof: write two solver-chosen values back to back at a solver-chosen
  address, then assert they sit in memory and leave in order. Find whether
  an address is in use by subtracting the read pointer and comparing with
  the count. Also assert the count never exceeds the depth and the flags
  agree with it [Tut].
- Cover full followed by empty, so the FIFO is seen to return to idle
  [Tut].
- Simulation: random push and pop with random stalls on both sides, against
  a queue model; reach full and empty; push and pop together at both; run
  two depths, one not a power of two (inference; random delays from
  [Tut]).

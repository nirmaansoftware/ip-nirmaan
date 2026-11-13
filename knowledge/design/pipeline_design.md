---
id: design/pipeline_design
skill: pipeline_design
as_of: 2026-11-03
review_by: 2027-05-03
sources:
  - open | Gisselquist, Building a Skid Buffer for AXI processing, ZipCPU blog, 2019 [Skid] | https://zipcpu.com/blog/2019/05/22/skidbuffer.html
  - open | Gisselquist, Strategies for pipelining logic, ZipCPU blog, 2017 [Pipe] | https://zipcpu.com/blog/2017/08/14/strategies-for-pipelining.html
  - open | LaForest, Pipeline Skid Buffer, FPGA Design Elements (MIT) [LaF] | https://fpgacpu.ca/fpga/Pipeline_Skid_Buffer.html
  - open | Gisselquist, AXI Handshaking Rules, ZipCPU blog, 2021 [Rules] | https://zipcpu.com/blog/2021/08/28/axi-rules.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-P3-K2 session (P3 pilot, item K2, 2026-11-03)
checker: pending, a different session reads the sources in P3-C2 and writes the check record
---
Knowledge only: no tool run backs this.

# Pipeline design

Pipeline stages joined by valid/ready, the register slice (skid buffer), and
stalls that lose no data. Tags in brackets name the sources above; a line
marked "inference" is this document's own reasoning.

## Handshake styles

- A global clock enable suits fixed-rate data; a valid that travels with the
  data says which outputs are real; neither can stall [Pipe].
- With valid and ready (the source calls ready "not busy"), a transfer
  happens when both are high. The source raises valid without waiting for
  ready, which avoids deadlock; ready idles high; the payload holds until
  the clock after the transfer; data is a don't care while valid is low;
  valid resets to 0 [Pipe] [Rules].
- A ready made combinationally from the next stage's ready grows longer at
  every stage. Registering it plainly costs an idle cycle per transfer
  [Pipe].
- An interface needs no combinational path from its inputs to its outputs:
  register ready, and use a skid buffer to keep full throughput [Rules].

## The skid buffer (register slice)

- Why two registers: with ready registered, the upstream stage learns of a
  stall one cycle late, so the beat it sends in that cycle needs a place to
  go [Skid] [LaF].
- States: empty, busy (one beat in the output register) and full (a second
  beat in the buffer register). Moves: load (empty to busy), flow (busy, in
  and out together), fill (busy to full), flush (full to busy, the buffer
  moves to the output), unload (busy to empty) [LaF].
- Upstream ready is "not full" and output valid is "not empty", both
  registered from the next state, so neither side's outputs depend
  combinationally on the other side [LaF].
- Equivalent form: a buffer valid bit and buffer data. Upstream ready is
  the inverse of the buffer valid bit. The buffer fills when a beat is
  accepted while the output is stalled, and empties when the output is
  ready [Skid].
- Registered outputs: change output valid and data only when output valid is
  low or downstream ready is high, taking the buffered beat first, else the
  input [Skid]. Adding any other condition to that update is how such logic
  breaks [Skid] [Rules].
- A variant drives output valid and data combinationally (input or buffer)
  and registers only upstream ready [Skid]. It breaks the ready path but
  not the data path (inference).
- Feeding one output register through a multiplexer, rather than choosing
  between two registers at the output, keeps the multiplexer before the
  register [LaF].
- The buffered beat always leaves before any newer one, so order holds
  [LaF].
- Reset or a clear empties both registers by clearing their valid bits
  [Skid] [LaF]; data needs no reset [Pipe]. An option can hold data at
  zero while not valid, to cut toggling [Skid].

## A buffered pipeline

- With registered ready at every stage, a stall travels back one stage per
  clock, and each stage holds one extra beat in its buffer; data bunches up
  and then drains in order [Pipe].
- By the source's estimate this at least doubles the logic, so use it
  where timing or throughput needs it [Pipe].

## Common failure modes

- No second register, so the beat sent on the stall cycle is lost [Skid]
  [LaF].
- Upstream ready computed from downstream ready in the same cycle: correct,
  but no slice, and the path grows (inference from [Pipe] [Rules]).
- Output payload or valid changed while stalled [Skid] [Rules].
- The buffered beat sent after a newer one (inference from [LaF]).
- Valid that never returns low after the last beat [Skid].
- A transfer condition with extra terms, which misses handshakes [Rules].

## How a result is checked

- Properties [Skid]:
  - assume of the input, and assert of the output: valid is low after
    reset, and a stalled beat holds still;
  - every accepted beat goes straight out or into the buffer;
  - after the last beat the output returns to idle;
  - a full buffer with downstream ready empties on the next clock.
- Prove every parameter combination as its own task. Cover a trace that
  drops downstream ready more than once, sends counting data and ends idle;
  short depths suffice [Skid].
- Simulation: compare sent and received beats in a scoreboard, with random
  valid and ready on both sides; send back to back; hold ready low for one
  cycle and for several; reset during traffic. Upstream ready must change
  only at clock edges, never in response to downstream ready within a
  cycle (inference).

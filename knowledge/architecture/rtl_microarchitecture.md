---
id: architecture/rtl_microarchitecture
skill: rtl_microarchitecture
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | Gisselquist, Strategies for pipelining logic, ZipCPU blog, 2017 [Pipe] | https://zipcpu.com/blog/2017/08/14/strategies-for-pipelining.html
  - open | Gisselquist, Building a Skid Buffer for AXI processing, ZipCPU blog, 2019 [Skid] | https://zipcpu.com/blog/2019/05/22/skidbuffer.html
  - open | lowRISC, Ibex documentation: Pipeline Details (Apache 2.0) [Ibex] | https://ibex-core.readthedocs.io/en/latest/03_reference/pipeline_details.html
  - open | Gisselquist, Rules for FPGA development, for new students, ZipCPU blog, 2017 [Rules] | https://zipcpu.com/blog/2017/08/21/rules-for-newbies.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: RETRO-A5 session (retrospective action A5, item P3-K3, 2026-11-15)
checker: pending, a different session reads the sources in P3-C3 and writes the check record
---
Knowledge only: no tool run backs this.

# RTL microarchitecture

Deciding, before RTL, how a block moves data cycle by cycle: its stages, its
buffers, who may stall whom, and what each state register holds. Tags in
brackets name the sources above; a line marked "inference" is this document's
own reasoning; a line marked "gate" names the repository code that backs it.

## What the microarchitecture states

- Per interface: the handshake, which side drives which signal, and when data
  must hold [Pipe] [Skid]; and whether a transfer can happen on the cycle after
  reset (inference).
- Per stage: what it computes in one clock, its latency and its throughput
  (items per cycle), and whether it can stall [Pipe] [Ibex].
- Per buffer: its width, its depth, why that depth, and what happens when it is
  full (inference from the card, "every buffer has a depth justification").
- Per state register: its reset value and which events change it (inference).
- The clocking: one clock where the job allows; other timing done with enables
  inside clocked logic rather than extra clocks, and no falling-edge
  logic [Rules].
- In this repository the step that holds it produces a microarchitecture
  specification and needs an independent review record; no tool run is
  required for it (gate: src/nirmaan/company/workflows.py:195-197, with
  `REVIEWED` at workflows.py:63). The skill holds no tool.

## Choosing the signalling between stages

ZipCPU's article lists strategies from simplest to most general, and says no
one fits all; the choice depends on the source and the sink [Pipe].

- A global valid (clock enable): logic changes only when it is high. Fits
  fixed-rate sample streams such as filters; it cannot say whether an output
  is valid and cannot stall [Pipe].
- A valid that travels with the data: each stage forwards it, the valid is
  cleared on reset and data is a don't-care on reset. It cannot stall, so
  every stage must accept a new item every cycle [Pipe].
- A valid and busy (or ready) handshake: a transfer happens when valid is
  high and busy is low. The source raises valid without waiting for busy, to
  avoid deadlock; data holds until the transfer; the busy line idles low so
  no cycle is lost [Pipe].
- A buffered handshake: the busy signal is registered, so one extra item
  may arrive after a stall, and the stage stores it in a buffer and releases
  it when the stall ends [Pipe]. The skid buffer is this buffer [Skid].

## Backpressure, end to end

- A stall computed combinationally and passed back through many stages gains
  delay at each stage, and can set the clock period [Pipe] [Skid]. A
  registered stall breaks that chain but costs either an idle cycle between
  transfers or a buffer to hold the item that arrives meanwhile [Pipe] [Skid].
- A skid buffer has two requirements: while valid is high and ready low,
  the data stays constant into the next cycle, and no item is lost [Skid].
- Write down, for every link, which of the two it uses, and where the
  stall ends (the sink that can refuse). A chain that stalls in one place and
  assumes it never stalls in another loses data (inference).
- A stage that must stall for a long operation, such as a memory access or
  a divide, stalls the stage before it, and that one the stage before it, so
  the stall signal accumulates along the pipeline [Skid]. Ibex stalls its single decode and execute stage until a
  multi-cycle instruction completes, and a load stalls at least one cycle to
  await its response [Ibex].
- A wait on a memory or bus makes the stall length variable; the spec gives a
  bound or a timeout, or says there is none (inference from [Ibex]).

## Sizing buffers and queues

- A queue with no bound is not a design: say what bounds the number of items
  in flight, such as credits, a fixed number of outstanding requests, or the
  consumer rate (inference from the card).
- Depth follows from the delay between a stall being decided and its effect
  reaching the source, times the rate, plus the burst that can arrive in that
  time. With a registered ready that is one extra item per stage [Pipe] [Skid]
  (inference for the rule of thumb).
- When a buffer is full and the source cannot be stopped, the spec says what is
  dropped, or that nothing is (inference).

## Example from a CPU

- Ibex has two stages: instruction fetch through a prefetch buffer, and a
  combined decode and execute stage. The best case is one instruction per cycle;
  a multi-cycle instruction, a load, a jump or a taken branch stalls the second stage,
  and each costs a stated number of cycles [Ibex].
- A table of stall cycles per instruction class, as Ibex gives, is a good
  form for any block: it makes the cost of each case a number that a testbench
  can count [Ibex] (inference for the testbench use).

## Common failure modes

- Backpressure not defined for every interface (card).
- A queue without a bound (card).
- A buffer with no stated reason for its depth (card).
- A registered ready with no buffer, so one item is lost on a stall [Pipe].
- Data allowed to change while valid is high and ready is low [Skid].
- A valid raised only after ready, which can deadlock when the sink waits for
  valid before ready [Pipe].
- Two clocks or an edge of something other than the system clock, where one
  clock and enables would do [Rules].

## How a result is checked

- A reviewer walks one item through every stage, cycle by cycle, including a
  stall in the middle and a reset in the middle (inference).
- Each rule above becomes a property or a testbench check in the RTL step: data
  stable under valid and not ready, no item lost, outputs idle after reset
  [Skid] (see the pipeline and buffering documents for the properties).
- The stall-cycle table is checked against a simulation that counts cycles
  (inference from [Ibex]).

---
id: design/fsm_design
skill: fsm_design
as_of: 2026-11-03
review_by: 2027-05-03
sources:
  - open | Gisselquist, ZipTimer: A simple countdown timer, ZipCPU blog, 2018 [Tmr] | https://zipcpu.com/zipcpu/2018/04/17/ziptimer.html
  - open | Gisselquist, Lesson 3: Finite State Machines, ZipCPU tutorial [FSM] | https://zipcpu.com/tutorial/lsn-03-fsm.pdf
  - open | YosysHQ, Yosys command reference: FSM handling [Yosys] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_passes_fsm.html
  - open | lowRISC, OpenTitan rv_timer, Theory of Operation (Apache 2.0) [RVT] | https://opentitan.org/book/hw/ip/rv_timer/doc/theory_of_operation.html
  - open | lowRISC, OpenTitan Comportability Specification, Interrupt Handling (Apache 2.0) [CIP] | https://opentitan.org/book/doc/contributing/hw/comportability/index.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-P3-K2 session (P3 pilot, item K2, 2026-11-03)
checker: pending, a different session reads the sources in P3-C2 and writes the check record
---
Knowledge only: no tool run backs this.

# FSM design

State machines for small blocks, worked through a timer: idle, count,
expire, one-shot or periodic. Tags in brackets name the sources above; a
line marked "inference" is this document's own reasoning.

## Structure

- An FSM is inputs, a state variable with a finite set of values, and
  outputs. Moore outputs depend on the state only, Mealy outputs on the
  state and the inputs. One clocked process, or a clocked state register
  plus a combinational next-state block, are both fine [FSM].
- When a state variable may take only some values, assert that it stays in
  range [FSM].
- Yosys's `fsm` pass finds state registers, extracts and optimises them and
  may re-encode them as one-hot or binary unless told not to; `fsm_info`
  writes what it found to the log [Yosys]. The netlist encoding can thus
  differ from the RTL's (inference).

## A timer as a state machine

- Idle: count zero, not running. Count: a non-zero count steps down by one
  on each tick. Expire: the tick that takes the count from one to zero.
  Then a one-shot returns to idle, and a periodic timer reloads its
  interval [Tmr].
- Keep a running flag: set by a write of a non-zero count, held while the
  count is non-zero or a reload is due, cleared when a one-shot reaches
  zero [Tmr]. That hardware clear is a self-clearing enable: when the flag
  is a software-visible bit, it reads 0 after expiry, and the spec must say
  which wins when software writes it on the expiry cycle (inference).
- Periodic mode needs a non-zero interval; accept periodic mode only with a
  non-zero value [Tmr].
- A one-shot restarted by software in its handler drifts later each period;
  a hardware reload keeps the period [Tmr].
- Where a write changes only the reload value, the first period after it
  can still run at the old length; the timer here loads the count on every
  write instead [Tmr]. The spec must say which (inference).
- Count on a tick (a clock enable), not every clock, when the spec has a
  prescaler; a prescaler counts to its programmed value and then ticks
  [Tmr] [RVT].
- Another form counts up and raises its interrupt when the count is at or
  past a compare value [RVT].
- A registered "count is zero" flag, set on the edge where the count
  reaches zero, keeps a wide compare out of every decision; assert that it
  always equals the compare [Tmr].

## Expiry and interrupt

- Raise expiry for one cycle on the tick that takes the count to zero; never
  on reset, on a bus write, or without a tick [Tmr].
- Testing only "count is one" fires wrongly when a restart lands on the same
  cycle [Tmr].
- Latch expiry into a sticky status bit that software clears by writing 1;
  status shows the raw event, and an enable bit masks only the interrupt
  output [CIP].
- Reset and initial values must agree, and every state register returns to
  idle on reset [Tmr].

## Common failure modes

- A period of N+1 ticks where the spec says N: counting from N through zero
  takes N+1 ticks (inference from [Tmr]).
- Expiry missing, doubled or on the wrong cycle when a write meets expiry
  [Tmr].
- A state that cannot be reached or cannot be left (card).
- A status bit cleared by a read or by writing 0 (inference from [CIP]).

## How a result is checked

- Properties [Tmr]:
  - reset puts every register in its idle value;
  - invariants: the zero flag matches the count; a non-zero count means
    running; periodic means running with a non-zero interval;
  - steps: a tick lowers a non-zero count by one, no tick holds it, a write
    loads it, a tick at zero in periodic mode reloads it;
  - expiry is high exactly after the tick that reached zero.
- Cover each state and a return to idle (inference from [FSM]).
- Simulation: one-shot and periodic at small and large values; a write
  while counting; a write of zero to stop; a write on the expiry cycle;
  ticks gated off; read the running bit after expiry; measure the time
  between interrupts (inference).

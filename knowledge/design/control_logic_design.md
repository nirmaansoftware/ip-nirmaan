---
id: design/control_logic_design
skill: control_logic_design
as_of: 2026-11-03
review_by: 2027-05-03
sources:
  - open | lowRISC, OpenTitan GPIO, Theory of Operation (Apache 2.0) [GPIO] | https://opentitan.org/book/hw/ip/gpio/doc/theory_of_operation.html
  - open | lowRISC, OpenTitan Comportability Specification, Interrupt Handling (Apache 2.0) [CIP] | https://opentitan.org/book/doc/contributing/hw/comportability/index.html
  - open | Gisselquist, The ZipCPU's Interrupt Controller, ZipCPU blog, 2019 [PIC] | https://zipcpu.com/zipcpu/2019/04/02/icontrol.html
  - open | Gisselquist, Some Simple Clock-Domain Crossing Solutions, ZipCPU blog, 2017 [CDC] | https://zipcpu.com/blog/2017/10/20/cdc.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-P3-K2 session (P3 pilot, item K2, 2026-11-03)
checker: pending, a different session reads the sources in P3-C2 and writes the check record
---
Knowledge only: no tool run backs this.

# Control logic design

Register-controlled peripheral logic, worked through a GPIO block: direction,
output enable, input sampling, edge and level interrupt detect, mask and
write-1-to-clear status. Tags in brackets name the sources above; a line
marked "inference" is this document's own reasoning.

## Outputs and direction

- Keep one output data register and one output-enable register, one bit per
  pin; a pin drives its data bit only while its enable bit is set [GPIO].
  The enable is the pin's direction (inference).
- A masked write carries a bit mask and data, so software changes chosen
  bits without a read-modify-write [GPIO]. Without one, bus byte strobes
  give byte granularity only (inference).
- The input register shows the pin whatever the enable; with the output
  enabled it shows the driven value [GPIO].

## Inputs

- A pin is an asynchronous input: pass it through two flip-flops (some use
  three) on the block's clock, and never use the first flip-flop's output
  [CDC].
- An optional filter that waits for a stable value (16 cycles in one
  design) feeds both the input register and interrupt detect [GPIO].
- Edge detect: keep the synchronised value and its copy from the previous
  cycle; a rise is new high and old low [CDC], a fall the reverse
  (inference). Reset the copy to the pin's reset value, so leaving reset
  makes no false edge (inference).

## Detect, status and mask

- Per bit, enables for rising edge, falling edge, level high and level low;
  both edges may be enabled, with no record of which one fired [GPIO].
- An event sets a sticky status bit. Software clears it by writing 1;
  writing 0 changes nothing; hardware never clears it; a clear while the
  event is still active leaves the bit set [CIP]. One controller writes the
  next status as new events OR (old status AND NOT the written bits), so a
  new event wins over a clear in the same cycle [PIC].
- Status shows raw events and is not masked; each interrupt output is its
  status bit AND its enable bit, active high and level [CIP] [GPIO]. A
  block with one interrupt line ORs these [PIC]. Unmasking a pending bit
  raises the output (inference from [CIP]).
- A "status" style interrupt follows its condition, and software clears it
  by removing the cause or by masking it, not through the status register
  [CIP]. A level detect latched as an event sets again at once after a
  clear while the level holds (inference from [CIP]).
- A test register can set status bits from software [CIP].
- Register the interrupt output; the processor has much logic behind it
  [PIC].
- Give enables set and clear operations, or a mask, so changing one bit
  never disturbs another (inference from [PIC], whose first design could
  not clear one enable without clearing the master enable).

## Common failure modes

- Status cleared by a read, by writing 0, or by any write (inference from
  [CIP]).
- An event lost when it lands on the cycle of a clear [CIP] [PIC].
- The mask applied to status instead of the output, hiding pending events
  (inference from [CIP]).
- Edge logic on the raw pin, or a false edge at reset (inference from
  [CDC]).
- One enable bit that cannot change without touching others [PIC].

## How a result is checked

- Properties [PIC]:
  - reset clears status, enables and the output;
  - an event sets its status bit on the next clock;
  - the output rises after a bit that is both set and enabled (and the
    master enable, where there is one), and stays low otherwise;
  - a write of 1 clears only the written bits, unless an event lands
    together with it;
  - enables hold without a write.
- Cover the interrupt rising and a write clearing it [PIC].
- Simulation: each detect mode on several bits; one-cycle pulses; both
  edges; masked and unmasked with an event pending; a clear while the event
  is active; per-bit data and enable; the input read with the output
  enabled (inference).

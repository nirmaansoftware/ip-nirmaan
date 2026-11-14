---
id: design/reset_design
skill: reset_design
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | Gisselquist, Formally Verifying an Asynchronous Reset, ZipCPU blog, 2018 [AReset] | https://zipcpu.com/formal/2018/04/12/areset.html
  - open | Gisselquist, Resetting an AXI component, ZipCPU blog, 2020 [AxiReset] | https://zipcpu.com/blog/2020/03/14/axi-reset.html
  - open | Gisselquist, Rules for FPGA development, for new students, ZipCPU blog, 2017 [Rules] | https://zipcpu.com/blog/2017/08/21/rules-for-newbies.html
  - open | Gisselquist, Chasing resets, ZipCPU blog, 2024 [Chase] | https://zipcpu.com/blog/2024/04/01/chasing-resets.html
  - open | lowRISC, Verilog Coding Style Guide (CC BY 4.0) [lowRISC] | https://github.com/lowRISC/style-guides/blob/master/VerilogCodingStyle.md
  - open | lowRISC, OpenTitan Comportability Specification (Apache 2.0) [CIP] | https://opentitan.org/book/doc/contributing/hw/comportability/index.html
  - open | Verilator manual: Warnings (SYNCASYNCNET) [VLW] | https://verilator.org/guide/latest/warnings.html
  - open | YosysHQ, Yosys command reference: Converting process blocks (proc_arst, proc_dff) [Proc] | https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_passes_proc.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: RETRO-A5 session (retrospective action A5, item P3-K3, 2026-11-15)
checker: pending, a different session reads the sources in P3-C3 and writes the check record
---
Knowledge only: no tool run backs this.

# Reset design

Choosing a reset style, sequencing it across domains, and checking that a block
starts, and restarts, in a known state. Tags in brackets name the sources
above; a line marked "inference" is this document's own reasoning; a line
marked "gate" names the repository code that backs it. The card holds no tool.

## Choosing a style

The sources disagree, so the document records both and the reason each gives.

- Asynchronous active low: OpenTitan and the lowRISC style guide make every
  reset asynchronous and active low, named `rst_n` or a clock-qualified
  variant, written `always_ff @(posedge clk or negedge rst_n)` [CIP] [lowRISC].
  OpenTitan's reason: assertion is asynchronous to any clock but deassertion is
  synchronised to the clock of the storage element; the choice came from a
  survey, team experience and security analysis; it costs slightly more area
  and needs more care, and the synchronous form needs a clock edge to take
  effect [CIP].
- Synchronous: ZipCPU's rules for new designers say not to use an asynchronous
  reset inside a design, and to test the reset inside a block clocked by the
  system clock [Rules].
- Whichever is chosen, use one style across a block: Verilator warns when one
  net is an asynchronous reset in one flop and a synchronous reset in another
  and calls the mix usually a mistake [VLW].

## Making the release safe

- An asynchronous reset input has no relation to the clock. Flops may enter a
  metastable state if it is released near a clock edge, so the design must
  release all at once on a clock edge [AReset].
- The fix is a reset synchroniser: assertion sets the synchroniser flops
  immediately, release shifts a zero through a short chain of flops on the
  clock; ZipCPU's example uses three stages [AReset].
- The output of that synchroniser is high whenever the input reset is active
  (so it is also an asynchronous reset in effect), is high for at least one
  clock before release, and falls only on a rising clock edge [AReset].
- The reset must be active long enough to propagate through the design.
  Most digital designs can reset in one clock and some need two; analogue
  circuits that must lock first, and memory devices, can need much longer,
  and an arbitrary 1,000 clock reset in a testbench cost time for no reason
  [Chase].

## Sequencing and domains

- Each clock domain has its own reset, released synchronously to that clock.
  A reset from another domain is brought across by a synchroniser in the
  destination domain, never used directly [AReset] [CIP].
- OpenTitan names a clock and reset pair for each domain of a block, and the
  primary clock must have a reset [CIP].
- A document names the reset domains, the order in which they release and
  what must be true before each does (card: "Define reset domains and
  sequencing"). Anything that starts a handshake waits for its own reset to
  release (inference).
- Security state needs care whichever style is used; OpenTitan's example is a
  synchronous reset to a random value after the chip-wide reset [CIP].

## What a reset sets

- Control state, valid and busy flags: cleared on reset. Data that is a
  don't-care while valid is low needs no reset value (inference).
- State registers return to idle, and every flag and counter agrees with
  the idle state (inference).
- A local reset, which resets part of a block while the bus keeps running, is
  a different thing. For an AXI-lite slave, reset the registers, not the
  bus signals, or the bus hangs: an in-flight transaction would be dropped.
  A local reset can come from an input or from a bus-writable register that
  clears itself [AxiReset].
- Retrofit a local reset by wrapping the existing core with a firewall, not by
  pulling its bus reset low alone, which would hang the bus [AxiReset].
- A local reset must reach every block that depends on it: in ZipCPU's
  example the master used one and its slave ignored it, which can read results
  into the wrong address or hang the design [AxiReset].
- A register given an initial value in its declaration, rather than an
  explicit reset: Yosys turns it into an `init` attribute, and its
  asynchronous-reset pass has an option that uses a named net as the reset for
  such registers [Proc]. Write the reset in the block instead of relying on this
  (inference).

## What the repository's gates say about reset

- Lint runs Verilator with `-Wall` and accepts no warning (gate:
  src/nirmaan/integrations/eda.py:427-428; src/nirmaan/integrations/eda_parsers.py:92-103).
  SYNCASYNCNET, the mixed-reset warning, belongs to the style group that
  `-Wall` enables [VLW], so a block that uses one net both ways fails
  `lint.run` (inference from the gate lines and [VLW]). That the lint gate
  accepts a style is not a statement that the style is right.
- No gate in the repository checks reset sequencing or release timing; the
  card's "documented and checked" is a review matter (inference; no reset
  tool is registered for this skill in src/nirmaan/company/skills.py).
- A formal setup with `[tasks]` is refused by the formal gate (gate:
  src/nirmaan/integrations/eda.py:644-649), so reset properties are written
  for a single-task setup.

## Common failure modes

- Reset deassertion races: the release is not aligned to a clock edge, so
  parts of the design leave reset on different cycles (card) [AReset].
- A reset synchroniser missing on a reset that crosses domains [AReset].
- A flop reset in one block style and not reset in another.
- A local reset that also resets the bus handshake [AxiReset].
- A testbench that holds reset for an arbitrary long time, so a block that
  needs more than a clock or two to reset is never found (inference from
  [Chase]).

## How a result is checked

- Properties for a block [AReset]: after reset every register has its idle
  value; the reset output is high whenever the input reset is active; the reset
  falls only on a clock edge; a cover shows the release happens.
- Simulation: reset at power-up, reset in the middle of a transaction,
  reset held for one clock and for several, release near a clock edge in a
  gate-level or randomised test where the tools allow (inference).
- Read the lint log for SYNCASYNCNET and the register styles (see the
  `rtl_lint` document).

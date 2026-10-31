---
id: design/apb
skill: apb
as_of: 2026-10-31
review_by: 2027-04-30
sources:
  - open | Ghena, EECS 373 Lecture 5: Memory and Peripheral Buses, University of Michigan, 2015 [UMich] | https://web.eecs.umich.edu/~prabal/teaching/eecs373-w15/slides/lec5.pdf
  - open | Johnson, ELE 4142 Parallel Communications: APB, Milwaukee School of Engineering, 2024 [MSOE] | https://faculty-web.msoe.edu/johnsontimoj/ELE4142/files4142/parallel_communications_apb.pdf
  - open | AVL-APB documentation: Protocol Support [AVL] | https://avl-apb.readthedocs.io/en/latest/protocol/protocol.html
  - open | Gisselquist, fapb_slave.v, formal properties of an APB slave, WB2AXIP (Apache 2.0) [FAPB] | https://github.com/ZipCPU/wb2axip/blob/master/bench/formal/fapb_slave.v
  - open | Gisselquist, apbslave.v, a demonstration APB slave with its proof, WB2AXIP (Apache 2.0) [APBS] | https://github.com/ZipCPU/wb2axip/blob/master/rtl/apbslave.v
  - open | Gisselquist, axil2apb.v, an AXI-Lite to APB bridge with its proof, WB2AXIP (Apache 2.0) [A2APB] | https://github.com/ZipCPU/wb2axip/blob/master/rtl/axil2apb.v
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source; the Arm APB specification is not a source here (it comes under a licence accepted by use)
export_screen: clear
writer: IP-P3-K1 session (P3 pilot, item K1, 2026-10-31)
checker: pending, a different session reads the sources in P3-C1 and writes the check record
---
Knowledge only: no tool run backs this.

# APB completer

How an APB completer (a peripheral; the older sources say slave) behaves on
the bus, how to build one as RTL, where it goes wrong, and how it is checked.
Tags in brackets name the sources above. A line marked "inference" is this
document's own reasoning from the cited source, not a statement the source
makes. The specification itself is not cited (see `licence_check`), so a
block's own interface spec is the authority wherever it is more precise than
this page.

## Signals

- From the requester: `PSEL` (one per completer), `PENABLE`, `PWRITE`,
  `PADDR`, `PWDATA`; to it: `PRDATA` [UMich]. Each completer has its own
  `PRDATA` and `PREADY` [UMich].
- Later versions add optional signals: `PREADY` and `PSLVERR` (APB3), then
  `PPROT` and `PSTRB` (APB4); APB5 adds more sidebands [AVL]. `PSTRB` holds one
  strobe per byte lane for writes and `PPROT` carries protection information
  [AVL] [MSOE].

## A transfer

1. **Idle.** `PSEL` low. After reset the requester keeps `PSEL` and `PENABLE`
   low [FAPB].
2. **Setup, one cycle.** `PSEL` rises with `PENABLE` low, and the requester
   presents address, direction and write data [UMich] [MSOE].
3. **Access.** `PENABLE` goes high on the next cycle [FAPB]. While `PREADY` is
   low the transfer waits, `PENABLE` stays high and address, direction,
   `PPROT`, and for a write the data and strobes, hold still [UMich] [FAPB].
4. **Completion.** The transfer completes on the clock edge where `PSEL`,
   `PENABLE` and `PREADY` are all high [FAPB] [A2APB]. The requester then
   returns to idle or starts the next setup [UMich], so a transfer takes at least
   two cycles [MSOE]. A bridge from AXI-Lite therefore reaches at most half
   a transfer per clock [A2APB].

Once `PSEL` is high it stays high until completion [FAPB]: a transfer cannot
be abandoned, so a completer may decode in setup and act at completion
(inference from [FAPB]).

## Building the completer

- **Completion strobe.** Derive one signal, `PSEL && PENABLE && PREADY`, and
  use it for every write, every read side effect and every response
  (inference from the completion rule above).
- **PREADY.** A completer that never waits can tie `PREADY` high [UMich]. One
  that waits drives it low during access [UMich]. The open demonstration
  completer registers `PREADY` so it is high exactly in the access cycle and
  low out of reset [APBS]; the property set also expects `PREADY` low during
  reset [FAPB]. Outside access `PREADY` may take any value [FAPB], so a
  test must not judge it there (inference). Bound the wait: the property set
  fails a completer that stalls past a chosen limit [FAPB]; the lecture notes
  find no limit stated [UMich].
- **Writes.** Commit the write on the completing cycle; that is where the
  transfer completes and every rule above has held (inference from [FAPB]).
  The demonstration completer commits at the setup edge [APBS]; do that only
  when the block's spec allows it (inference).
- **PSTRB.** Strobe bit i enables byte lane i, bits 8i+7 down to 8i of
  `PWDATA`; a lane whose strobe is low keeps its old value [APBS]. A design
  that ignores strobes writes whole words, which is wrong for any partial
  write (inference).
- **Reads.** Present `PRDATA` by the completing cycle; the requester samples
  it there [A2APB]. The demonstration completer loads `PRDATA` at the setup
  edge, ready for the access cycle [APBS].
- **PSLVERR.** Optional: a completer without errors ties it low [UMich]
  [FAPB] [APBS]. When used, drive it high only in the completing cycle and low
  whenever `PSEL`, `PENABLE` or `PREADY` is low [FAPB]. Which accesses are
  errors (unmapped or misaligned addresses, read-only registers) is the
  block's spec, and the spec must also say whether an erroring write changes
  state (inference). A bridge to AXI-Lite turns `PSLVERR` into an error
  response, code 2'b10 [A2APB].
- **Address decode.** Decode the word address bits above the byte offset, and
  decide in the spec what the low bits and the unused range do (inference;
  [APBS] drops the byte-offset bits).
- **PPROT.** Carry it, or record in the spec that the block ignores it: the
  demonstration completer leaves it unused [APBS], and the bridge forwards
  the AXI-Lite protection bits to it [A2APB].

## Common failure modes

- A write or side effect on a cycle that is not the completing one, or on a
  waited cycle (inference from the transfer rules).
- `PSLVERR` high outside the completing cycle [FAPB], or never driven when the
  spec says an access errors (inference).
- Strobes ignored or mapped to the wrong lanes (inference from [APBS]).
- `PREADY` held low with no bound, so the bus hangs [FAPB].
- A decode that aliases: an address outside the map answering as if it were a
  register (inference).

## How a result is checked

- **Properties.** Bind a property set to the completer: assume the requester
  rules (the setup and access order, stable inputs while waiting, reset) and
  assert the completer's (`PSLVERR` only on completion, a bounded wait,
  `PREADY` low in reset) [FAPB]. The demonstration completer adds a contract:
  a solver-chosen address, a model of its expected value with strobes
  applied, and an assertion that a read there returns the model [APBS].
- **Covers.** Cover completed writes and reads, and a sequence of reads
  returning chosen values, so the proof is not empty [APBS].
- **Simulation.** Drive wait states if the completer has them, back-to-back
  transfers (setup straight after a completion), every strobe pattern
  including none, each register read after a write, and every address class
  the spec names, checking `PSLVERR` on the completing cycle only
  (inference from the rules above).

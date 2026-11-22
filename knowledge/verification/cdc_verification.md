---
id: verification/cdc_verification
skill: cdc_verification
as_of: 2026-11-22
review_by: 2027-05-22
sources:
  - open | Ginosar, Fourteen Ways to Fool Your Synchronizer, ASYNC 2003 (author copy, IEEE copyright, no open licence stated) [GIN] | https://webee.technion.ac.il/~ran/papers/Sync_Errors_Feb03.pdf
  - open | Litterick, Full Flow Clock Domain Crossing: From Source to Si, DVCon proceedings (no licence stated) [LIT] | https://dvcon-proceedings.org/wp-content/uploads/full-flow-clock-domain-crossing-from-source-to-si.pdf
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: RX-K2 session (wave 2 close, 2026-11-22)
checker: pending, a different session reads the sources and writes the check record
---
Knowledge only: no tool run backs this; the card's one tool, cdc.run, is contract only.

# CDC and RDC verification

Finding and judging signals that cross between clocks that have no fixed
timing relation, and the reset crossings that go with them. Tags in brackets
name the sources above; a line marked "inference" is this document's own
reasoning; a line marked "gate" names repository code that backs it. Several
sources are vendor or single-author papers; their claims are the authors'.

## What the repository gives this skill

- The card lists one tool, cdc.run, and it is CONTRACT_ONLY: the catalog says
  the broker refuses it, so no agent can claim a crossing analysis ran (gate:
  src/nirmaan/company/tools.py:5-8, 177; test:
  tests/test_nirmaan_eda.py::test_the_open_source_tools_are_available_and_the_rest_stay_contracts).
- The card names the packs cdc and reset-clocking and asks that waivers be
  reviewed and that no violation go unexplained (gate:
  src/nirmaan/company/skills.py:545-550).
- So any statement from this skill about crossings is reasoning over source
  files and papers. It cannot say "the crossing check passed" (inference).

## Why a crossing is a problem

- A flop that samples a signal changing near its clock edge can go
  metastable and settle to either value after an unpredictable delay [GIN]
  [LIT].
- Metastability is not visible in RTL simulation, gate simulation or formal
  analysis; it belongs to the real flop [LIT].
- Reliability is stated as a mean time between failures. Both papers give the
  same shape: it grows exponentially with the settling window and falls with
  the clock rate and the data rate of the crossing [GIN] [LIT]. A small loss
  of settling time therefore costs a great deal (inference from the two
  formulas).
- The usual fix is a synchroniser: a chain of flops on the receiving clock,
  with a request and acknowledge exchange when data of more than one bit
  moves [GIN] [LIT].

## Failure modes to look for in the RTL

Each is a case [GIN] reports, with its fix; the author met them while teaching, working with design teams and reviewing papers.

- No synchroniser at all. The designer judged the failure rate too low, or
  the receiver clock much faster. Simulation can hide it by assuming clock
  relations that always meet timing, and static timing warnings on crossings
  get ignored because there are so many [GIN].
- One flop only, or logic after the first flop. A slow first flop leaves too
  little time for the logic behind it. A one-flop design is legal only if the
  logic delay leaves enough settling time for the target failure rate [GIN].
- A "greedy" arrival detector that combines the first and second flop
  outputs, which has the same fault [GIN].
- A sneaky path: a signal moved to another domain in a redesign and still
  used in its old one, or the raw signal used instead of its synchronised
  copy [GIN].
- A wrong protocol: dropping the acknowledge and waiting a fixed number of
  cycles. It overwrote data the receiver had not used, and it broke when one
  clock was later sped up [GIN].
- Global reset: the end of reset reaching clock domains without being
  synchronised. The start of reset is harmless; its release must be
  synchronised to each clock [GIN].
- An asynchronous clear or preset driven from another domain has the same
  release problem; synchronise it, or use an asymmetric form that does not
  delay the start of the clear [GIN].
- Test leakage: test modes that tie clocks together hide crossings under
  false-path lists, and a later change can open a real path behind the list.
  Recheck the whole list after the last design change [GIN].
- A pulse synchroniser that fails when the pulse lasts two cycles or two
  pulses come one cycle apart [GIN].
- A slow-to-fast shortcut: when the sender is slower than the receiver, a
  one-cycle request is sampled by at least two receiver edges, so the
  handshake is simplified. It fails when clock frequencies change and the
  assumption of who is faster no longer holds [GIN].
- A "metastability blocker" circuit that only moves the risk to a latch [GIN].
- One two-flop synchroniser on each bit of a bus. Bits can resolve
  differently, and the paper's example puts a 32 bit bus at a failure every
  16 microseconds [GIN]. A bus survives only when one bit changes at a time,
  as in Gray coded values; a binary bus can produce values that were never
  sent [LIT].
- A handshake where one signal is shared by both sides and not synchronised
  by the receiver [GIN].
- More stages than two is not an error; it buys more settling time [GIN].
- Missed reconvergence, which the card lists: signals that cross separately
  and meet again behind their synchronisers can arrive in different cycles.
  [LIT] says the rest of the device must work in the presence of the
  synchronisers, including convergent paths, but gives no checklist for
  them. The checking method here is unsourced.

## Method

- Structural pass: identify clock domains, find every crossing, and flag
  illegal logic on the crossing path [LIT]. Using clock pairs, list every path
  from a flop on one clock to a flop on the other and approve each one [GIN].
- Classify each crossing as a single bit, a handshake or a FIFO, give each the
  properties of its protocol, and prove or simulate them [LIT]. For a
  two-flop synchroniser these are: no logic on the crossing, no pulse
  narrower than the sampling can see, and stability for more than two active
  clock edges. For a handshake: every request gets an acknowledge, a full
  request and acknowledge sequence, and data stable until the acknowledge is
  seen [LIT].
- Waive only with a reason; who approves a waiver is unsourced.
- Repeat after every design change and before closing [GIN].

## Beyond RTL

- RTL verification of crossings is necessary and not enough: synthesis, test
  insertion, clock gating, placement and clock-tree work can weaken or break
  a synchroniser even when the RTL passed [LIT].
- The remedy [LIT] gives is structural and timing analysis of the final
  netlist, not gate simulation. Marking a crossing as a false path lets the
  tools use weak drivers and loose routing, so the metastable net needs a
  sub-cycle limit, and the second flop of a two-flop synchroniser should not
  get scan insertion [LIT].
- [LIT] also names assertion-based timing checks on RTL and gate level, CDC
  analysis on the netlist, at-speed test, and a CDC review before signoff.

## Failure modes in the work

- Blanket waivers (the card's own failure): a waiver with no reason is a
  crossing nobody has looked at (inference).
- Reading a clean report of one tool as proof for the whole flow: a report
  speaks of the stage it ran on (inference). [LIT] says RTL verification is
  necessary and not enough and recommends netlist CDC analysis.
- Treating a quiet simulation as evidence: it cannot show metastability [LIT].

## Not sourced here

- Reset domain crossing beyond the synchronised release of reset [GIN].
- FIFO verification detail, and formal property sets for crossings.
- The reconvergence method, and waiver approval.
- Cummings' SNUG 2008 CDC paper sits behind a registration form, so it was
  not read.

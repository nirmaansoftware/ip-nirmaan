---
id: verification/reference_modelling
skill: reference_modelling
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | lowRISC, OpenTitan Design Verification Methodology (Apache 2.0) [OTDV] | https://opentitan.org/book/doc/contributing/dv/methodology/index.html
  - open | lowRISC, OpenTitan UART DV document (Apache 2.0) [OTUart] | https://opentitan.org/book/hw/ip/uart/dv/index.html
  - open | cocotb documentation: First Steps (BSD-3-Clause) [CocoFirst] | https://docs.cocotb.org/en/stable/first_steps.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K3 session (wave 2 knowledge batch, plan row W2-K3, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Practising: the simulator this skill holds is available; this document is knowledge, not evidence.

# Reference modelling

Writing a behavioural model of a block from its specification, comparing it
against the RTL in a scoreboard, and how this repository's simulation gate
reads the result. Tags in brackets name the sources above; a line marked
"inference" is this document's own reasoning; a line marked "gate" names the
repository code that backs it.

## What a reference model is for

- OpenTitan's IP-level environments model the behaviour of the design more
  closely than the stimulus does, and do the checking in the scoreboard or in
  assertions, independently of the stimulus [OTDV].
- Where a trusted external implementation exists, OpenTitan calls it as the
  model: its cryptographic blocks are checked against open source C libraries
  [OTDV]. A model that is not independent of the RTL checks nothing: if both
  came from one reading of the code, one mistake is in both (inference).
- The model comes from the specification, never from the RTL. Anything the
  specification leaves open is a question to put back to the specification's
  owner, not a choice to copy from what the RTL happens to do (inference).

## Where the comparison happens

- OpenTitan's UART scoreboard does end-to-end checking: it receives the
  items that the interface monitors saw, through analysis FIFOs, rather than
  reading the design's internals [OTUart]. The pattern is monitors that
  observe, a model that predicts, and a scoreboard that compares (inference).
- For a small clocked block, compare every output after every edge, not once at
  the end of a phase. The first wrong cycle is then the one reported, with the
  inputs that led to it (inference).
- In the cocotb tutorial the expected value is kept in the test and updated on
  each clock edge, and the assertion compares it with the register after the
  design has settled. The same example shows what a model must get right: the
  counter wraps at its maximum and the naive model does not, so the check
  fails [CocoFirst].
- A scoreboard that cannot cope with fully unconstrained traffic is common;
  OpenTitan builds stress tests with knobs on the constraints, so the
  scoreboard is made more complete step by step and the constraints are eased
  later [OTDV]. Error and illegal stimulus is usually handled by directed tests
  because a scoreboard for it is costly [OTDV].

## What the model must cover

For arithmetic and state blocks these are the places a model usually differs
from a copied one (inference):

- saturation and wrap, and any sticky flag that records them, checked on the
  cycle after and several cycles later;
- signed against unsigned reading of operands, and sign extension;
- rounding and truncation at each stage;
- priority between simultaneous inputs, such as clear with accumulate, or
  reset with a valid input;
- holding behaviour when an enable is low.

A comparison passes trivially if the stimulus never reaches these. The test
should therefore fail itself when its run did not reach the corner, for example
a saturation that never occurred (inference). Code coverage shows the code ran,
not that its result was checked; functional coverage answers whether the
specified behaviour was seen [OTDV].

## What the simulation gate demands

- The testbench is the file that declares the run's top module; that is the one
  file that may end the simulation, read arguments, or open a file. A design
  file with those is refused before anything runs (gate:
  src/nirmaan/integrations/eda.py:451-464, 476-497).
- The testbench must print one verdict line, `NIRMAAN-SIM <nonce> <n> passed,
  <m> failed`, with the nonce the run passed in. The run fails when the verdict
  is missing or repeated, reports a failed check, or reports no passed check
  (gate: src/nirmaan/integrations/eda_parsers.py:128-129, 188-224). A
  scoreboard that checks nothing therefore fails the gate; count each passing
  comparison as a check, not only the failures (inference).
- A passing run says the testbench reported success. It does not say the model
  is right; the gate has no view of the model (inference). What shows the
  scoreboard can tell right from wrong is the must-fail scorer: the clean RTL
  must pass, and each planted mutant must fail the same testbench (gate:
  src/nirmaan/evals/scorers.py:135-224).
- A scoreboard written in Python for cocotb has the same limit: cocotb counts
  tests, so a test with no assertion passes (gate:
  src/nirmaan/integrations/eda_parsers.py:620-627).

## Common failure modes

- A model copied from the RTL, so the RTL's bug is also in the model.
- A scoreboard that compares the final total but not each cycle, or the value
  but not the flag.
- A comparison on a cycle where the design has not settled, so the check
  samples the previous value [CocoFirst].
- Stimulus below the corners: operands that stay small, a total that never
  reaches its limit, a clear that is never offered with an accumulate.
- A model with the same state encoding and update order as the RTL, which
  hides a reset or ordering bug (inference).
- A scoreboard made complete for random traffic only; error cases left
  unchecked [OTDV].

## How a result is checked

- Read the first mismatch: it names the cycle, the inputs and the two
  values (inference).
- Compare the model's text with the specification clause by clause, not with the
  RTL (inference).
- Run the testbench on a copy of the RTL with one behaviour changed
  (saturation removed, a flag cleared one cycle early). A scoreboard that
  still passes is missing a comparison or a corner (inference).
- Count the corner events the run reached; a count of zero for a corner means the
  clean pass says nothing about it (inference).

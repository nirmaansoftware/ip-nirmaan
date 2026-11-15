---
id: verification/accelerator_verification
skill: accelerator_verification
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | John R. Hauser, Berkeley TestFloat web page (Release 3e, BSD-style licence) [TFPage] | http://www.jhauser.us/arithmetic/TestFloat.html
  - open | John R. Hauser, Berkeley TestFloat Release 3e: General Documentation [TFGen] | http://www.jhauser.us/arithmetic/TestFloat-3/doc/TestFloat-general.html
  - open | John R. Hauser, Berkeley TestFloat Release 3e: testfloat_gen [TFCmd] | http://www.jhauser.us/arithmetic/TestFloat-3/doc/testfloat_gen.html
  - open | Gisselquist Technology, ZipCPU blog: Bit growth in FPGA arithmetic (2017) [ZGrow] | https://zipcpu.com/dsp/2017/07/21/bit-growth.html
  - open | Gisselquist Technology, ZipCPU blog: Rounding Numbers without Adding a Bias (2017) [ZRound] | https://zipcpu.com/dsp/2017/07/22/rounding.html
  - open | Gisselquist Technology, ZipCPU blog: How to Debug a DSP algorithm (2017) [ZDebug] | https://zipcpu.com/dsp/2017/07/24/dsp-debugging.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K6 session (wave 2 knowledge batch, plan row W2-K6, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# Accelerator verification

Checking an arithmetic datapath (a filter, a multiply-accumulate array, a
floating-point unit) against a golden model, with the numeric rules written
down first. Tags in brackets name the sources above; a line marked
"inference" is this document's own reasoning. This skill's card holds no tool
(src/nirmaan/company/skills.py:453-459), and nothing here has been run.

## State the numeric promise first

The card's first step is to state the format, rounding and saturation the
datapath promises. The golden model and the corner tests both come from that
statement (inference).

- Width. The ZipCPU post finds the width needed by looking at the extremes of
  the operation [ZGrow]. Adding two N-bit numbers needs one more bit. Adding K
  values of N bits needs about N plus the base-2 logarithm of K, rounded up,
  which is less than N plus K. Multiplying N-bit by M-bit numbers needs N plus
  M bits, and the page names the product of the two most negative signed
  values as the defining case [ZGrow]. A subtraction of unsigned values may
  go below zero and so changes the representation [ZGrow].
- Rounding. Dropping low bits (truncation) biases the result about half a bit
  downward. Round half up still leaves a bias. Rounding half toward zero or
  away from zero avoids that bias but subtly changes amplitude. Convergent
  rounding (half to even) is the approach the author chose, and he notes it is
  the default rounding mode of IEEE 754 [ZRound]. The author found the bias
  as a stray DC component in an FFT output when the input was a sine wave
  [ZRound].
- Saturation and overflow. No open source read for this document describes how
  to specify or test saturation for a fixed-point datapath; this is recorded
  in the wanted-sources list. The ZipCPU bit-growth page works by avoiding
  overflow with enough width [ZGrow]. For a saturating datapath, the promise to
  write down is which inputs clamp and to what value (inference).
- Floating point. For IEEE binary formats the promise includes the five
  rounding modes and the five exception flags, and TestFloat checks both the
  result and the flags [TFGen].

## Golden model and comparison

- The ZipCPU debug post's method: build a duplicate calculation that does the
  same work, then compare the results; the chance that the fixture and the
  design are wrong in the same way is smaller than either alone [ZDebug].
  Its example recomputes an interpolator in double-precision math, using
  logged inputs, intermediate values and outputs lined up together
  [ZDebug].
- A model that reuses the design's own widths and rounding repeats the same
  mistake (inference). The card's failure mode is to check only random values
  and miss the format corners; the model should be written from the numeric
  promise, not read off the RTL (inference).
- TestFloat shows the shape for floating point. It compares the unit under test
  with its own software implementation, and any difference is reported as a
  probable error that the user must confirm [TFPage] [TFGen].

## Corner values and random values

- TestFloat's cases mix simple pattern tests with weighted random inputs. Its
  documentation says they are adequate for carry chain propagation and for the
  rounding of add, subtract, multiply and simple operations, and that it
  checks boundary cases such as underflow, overflow, invalid operations,
  subnormal inputs, signed zeros, infinities and NaNs [TFGen].
- It is not good at difficult rounding cases for division and square root, and
  it does not look for bugs specific to SRT division [TFGen] [TFPage]. A
  datapath with such an operation needs separate corner work (inference).
- `testfloat_gen` takes a seed, and the same seed and arguments give the same
  cases. It has two levels, with level 2 generating many more cases, and it can
  also print the expected results for a named function [TFCmd]. Recording the
  seed and level makes a run repeatable (inference).
- For a fixed-point datapath, the corners follow the extremes the width rules
  use: the most negative and most positive inputs, zero, and the pairs that
  make a sum or product largest (inference, from [ZGrow]).
- ZipCPU's debug post found its first bug as dropped high bits, and a second
  as a mix-up between signed and unsigned multiplication [ZDebug].
  Widening the datapath temporarily and backing away from full range were its
  ways to confirm a bit-select error [ZDebug].

## Interpreting a mismatch

- TestFloat lists reasons a difference may not be a design fault: the standard
  allows variation, the trusted model may be faulty, the test program may be
  wrong, or the unit may be faulty. It leaves the decision to the user
  [TFGen].
- The allowed variations include whether tininess is detected before or after
  rounding, which NaN bit pattern is returned, and what integer comes back
  when a conversion is invalid. TestFloat has options to set the first and to
  check the others [TFGen] [TFCmd]. A model and a unit must make the same
  choice or the comparison reports false errors [TFGen].
- A passing run proves little on its own. The TestFloat documentation says
  that finding no fault in no way guarantees the implementation is bug-free
  [TFGen].

## Common failure modes

- Random values only, so the format corners are never hit.
- A golden model written from the RTL, so both share the bug.
- Truncation where the promise says rounding, which shows as a steady bias
  [ZRound].
- Too few bits for a sum or product at the extremes [ZGrow].
- Comparing floating-point results without fixing the rounding mode, tininess
  rule and NaN handling [TFGen].
- Giving a numeric rule in prose only, with no corner test that targets it
  (inference).

## How a result is checked

- Each stated numeric rule (width, rounding, saturation, flags) has a named
  corner test and a golden-model comparison (the card's own check).
- The model's source is the written promise, and the mismatch log names the
  input, the observed output and the expected output, as the TestFloat error
  line does [TFGen].
- The seed, the test level, the rounding mode and the tool or model version are
  recorded with the result (inference).
- Whether the datapath survives a planted single-change fault is a separate
  question; the verification-department documents on testbench qualification
  and reference modelling cover it (inference).

## Sources

- [TFPage], [TFGen], [TFCmd] What TestFloat checks, how it compares, its limits,
  its seed and level options and the allowed variations.
- [ZGrow] Width needed for sums and products.
- [ZRound] Truncation, half-up, toward-zero and convergent rounding and the
  bias each causes.
- [ZDebug] Building a second calculation and comparing it with the design.

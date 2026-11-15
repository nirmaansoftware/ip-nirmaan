---
id: verification/isa_compliance
skill: isa_compliance
as_of: 2026-11-15
review_by: 2027-05-15
sources:
  - open | RISC-V International, riscv-arch-test README (code BSD-3-Clause or Apache-2.0, documentation CC-BY-4.0) [ACT] | https://github.com/riscv-non-isa/riscv-arch-test
  - open | RISC-V Certification Test Plan, chapters 1 to 5, 7 and 8 and the openings of appendices A, C and E (CC-BY-4.0, draft dated 2026-11-14) [CTP] | https://riscv.github.io/riscv-arch-test/ctp.html
  - open | RISC-V Sail model README (BSD 2-clause) [Sail] | https://github.com/riscv/sail-riscv
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-W2-K6 session (wave 2 knowledge batch, plan row W2-K6, 2026-11-15)
checker: pending, a different session reads the sources in W2-C and writes the check record
---
Knowledge only: no tool run backs this.

# ISA compliance

Showing that a RISC-V core implements the instruction set it claims, and
saying exactly where that evidence stops. Tags in brackets name the sources
above; a line marked "inference" is this document's own reasoning. This
skill's card holds no tool (src/nirmaan/company/skills.py:446-452), and
nothing here has been run.

## What a compliance suite is, and is not

- The RISC-V architectural certification tests are assembly tests meant to
  certify that a design faithfully implements the specification. Their own
  README says they are not verification tests and that additional
  verification should be run on all processors [ACT].
- The test plan draws the same line. Certification checks that an
  implementation meets the normative rules of the ratified specifications for
  a certificate. It does not test what needs knowledge of the microarchitecture:
  timing, pipeline hazards, power management features [CTP].
- Certification also does not try to prove every bit of a carry chain for
  every input or that all stuck-at faults would be found. The plan asks the
  test author to pick a reasonable set of values, such as combinations of
  zero, one, minus one, the extremes and one intermediate value [CTP].
- So a pass on the suite supports "this configuration meets the tested rules".
  It does not support "this core is verified" (inference).

## How the suite is built and run

- A profile is a named set of required and optional extensions. The plan calls
  it a partial configuration. A configuration adds the optional extensions and
  the parameters, and is written in a machine-readable YAML form [CTP].
- The framework needs three DUT files: a configuration file listing the
  supported extensions and parameters, an `rvmodel_macros.h` that boots the
  DUT, prints, ends a test with pass or fail and raises interrupts, and a
  linker script for the memory map [ACT] [CTP].
- The framework picks the tests that apply to that configuration and builds
  them into self-checking ELF files. Expected values come from the Sail
  reference model, configured to match the DUT [ACT].
- The user then runs every ELF on the DUT with their own testbench. Each test
  prints a pass or a fail summary line [ACT].
- The README names the older riscof tool as deprecated and replaced by this
  framework [ACT]. Older write-ups that name riscof describe the earlier flow
  (inference).

## What the plan tests and skips

- Every normative rule is tied to one or more coverpoints, and each coverpoint
  has tests that hit it. Coverpoints are machine-readable, and the tests are
  self-checking [CTP].
- A rule that says a behaviour is UNSPECIFIED is not tested, since there is no
  wrong answer. Reserved instructions are skipped unless the Ssstrict
  extension is on. Custom encodings are never tested [CTP].
- CSR fields are treated by kind. A WARL field is tested with legal values, and
  with illegal ones only when legality is easy to know, such as a 1-bit field.
  WLRL fields get legal values only, and reserved values are never tested
  [CTP].
- Three kinds of behaviour need different checks [CTP]. A deterministic one has
  one expected value for the configuration, and a test compares against the
  reference model. A constrained non-deterministic one (the plan's example is a
  tail-agnostic vector element, which may keep its old value or become all
  ones) must accept every legal outcome. An unconstrained one, such as an
  integer register's value after reset, must not be assumed or compared
  with the reference model.
- The plan says tests often have bugs and do not exercise the feature the
  author meant, which is why a different engineer writes the coverpoints that
  measure whether the tests did [CTP].
- Test developers also produce a coverage report, based on a trace from the
  Sail model, to confirm the tests hit all the coverpoints [CTP].

## Mapping a claim to evidence

For the card's step "map each clause to a test, a formal check or a random
stream", a plain route is below. The formal route and the random route are
this document's reasoning (inference); the sources here do not teach formal
ISA proofs.

1. Write down the claimed profile and the optional extensions and parameter
   values. The README says the expected results of the tests differ with the
   DUT's configuration, so a run is tied to one configuration [ACT].
2. For each claimed extension, list the suite directory or test files that
   cover it, and the result of running them on the core (inference).
3. For a claimed feature with no compliance test, name the other evidence or
   state the gap (inference). The plan itself lists rules it marks as not
   tested, and says every limitation is documented [CTP].
4. For behaviour the plan leaves out, such as interrupt timing during a
   multicycle instruction, the plan says design verification must cover it
   [CTP].
5. A reference model can also be an oracle for random instruction streams: the
   Sail model supports the TestRIG protocol and produces traces in the RVFI
   format, and it has been cross-tested against Spike and another
   specification model [Sail].

## Common failure modes

- Reporting compliance from a suite that was never run on this core, or run on
  a different configuration (this is the card's own failure mode).
- A configuration that does not match the core. The README calls configuration
  mismatches a common source of errors, and its checklist covers the
  configuration file, the Sail configuration, the macros and the linker script
  [ACT]. The plan says a full configuration is what lets a reference model
  match a DUT, apart from non-deterministic behaviour [CTP].
- Reading a failure as a core bug without checking the other side. The README
  says that if the expected value looks wrong, a configuration mismatch is the
  likely cause, and it may even be a defect in the suite, for instance a test
  of behaviour that should be UNSPECIFIED [ACT].
- Claiming an extension the reference model does not yet support. The Sail
  README lists the extensions it covers and points to a roadmap of those it
  does not [Sail]. The plan says no simulator is yet fully configurable to
  match every feature, and that Spike has a minimal set of configuration
  options [CTP]. A compliance claim should stay inside what the model can
  predict (inference).
- Treating a draft plan as final. The plan describes itself as a work in
  progress and carries TODO notes [CTP]. Record the plan and framework
  versions with a result (inference).

## How a result is checked

- The result names the profile, the extensions, the parameters, the framework
  and plan versions, and the Sail version used (inference). The README names
  the Sail and compiler versions it was tested with, so a record of them is
  part of repeating a run [ACT].
- Each failure shows the failing PC, the instruction, the mismatching
  register, and the expected and actual values [ACT]. A debug flag adds the
  Sail trace and a trap report, and the README advises using it for one
  extension at a time since it slows generation [ACT].
- Each gap is stated: a feature claimed but not covered by a run, a rule the
  plan marks as not tested, or a behaviour left to design verification
  (inference).

## Sources

- [ACT] What the suite is, the files a DUT supplies, how self-checking ELFs
  are made, the pass and fail output and the failure checklist.
- [CTP] Certification against verification, normative rules and coverpoints,
  what is not tested, deterministic and non-deterministic behaviours, the
  reference model chapter.
- [Sail] The reference model, its configuration, supported extensions and
  its use as a test oracle.

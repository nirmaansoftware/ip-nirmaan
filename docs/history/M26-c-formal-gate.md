# Milestone 26 (formal gate) - Synthesis and formal before review, formal in CI (after Stage 6)

The `block-design` rtl stage gains two `checked(...)` requirements, as data:
`synth.run` over the produced `rtl_source` files (top from the RTL file's
entry) with `max_latches=0`, always; and `formal.run` with `sby` from a
produced `formal_spec` file (a `.sby`) and `sources` from the `rtl_source`
files, only when a `formal_spec` was produced. The `rtl_design` skill is
granted both tools. Design doc: `docs/FORMAL_GATE.md`.

Key design points worth not re-deriving:
- **Two generic fields on `EvidenceRequirement`.** `params` (fixed tool
  parameters, merged over task inputs in pre-flight and post-flight; `satisfies`
  counts a run only if it was made with every one) and `when_produced` (the
  requirement applies only when an artifact of those kinds was produced;
  `EvidenceRequirement.applies(kinds)` is read by the post-flight step, the
  `evidence-before-review` check over the submitted drafts, and
  `unsatisfied_requirements` over the task's artifacts). Nothing names formal.
- **Limits are generic in `eda.execute`.** Any `max_<metric>` parameter fails
  a passing result whose parsed metric exceeds it, or that never reported it.
  Yosys's latch count (M21's `stat -json` parse) is what `max_latches` reads.
- **Formal is conditional for `block-design`**, not required: a required `.sby`
  invites vacuous proofs, and it would couple other blocks on the workflow to
  writing properties. When present, it must pass. Properties live in the RTL
  under `` `ifdef FORMAL ``; the `.sby` lists the RTL by relative path, which
  resolves because a seat's files share one attempt directory.
- **The proof must read the submitted RTL.** `Backend.check` (new, optional)
  runs before any step; the SymbiYosys backend uses it to fail a run whose
  `.sby` `[files]` does not list every `sources` file. Whether `[script]`
  reads it is left to the reviewer, who reads the `.sby`.
- **CI:** OSS CAD Suite 2026-09-28 streamed into `$RUNNER_TEMP`, not cached.
  Only `sby` and `yices-smt2` wrappers go on PATH; the suite's `sby` launcher
  prepends the suite's `bin` for its own process, so proofs use the suite's
  matched Yosys and yosys-smtbmc while every other test keeps apt's tools.
  `NIRMAAN_REQUIRE_EDA` gains `sby yices-smt2`, and the test step runs with
  `-rs` so the log lists every skip.

Tests: `tests/test_nirmaan_formal_gate.py` (13): a latch hidden from lint by a
waiver pragma, and a Yosys error, both refused with recorded failed runs; an
AXI4-Lite mutant (`arready` tied high) that passes lint, simulation, and
synthesis but fails the proof; a `.sby` proving an embedded copy of the module;
passing synthesis and formal reach review and approval; no `.sby` means no
formal; no `sby` blocks with nothing recorded; a claimed formal pass is refused
(P5); a hand-made synthesis without `max_latches` does not count; metric
limits; crown jewel `test_a_new_before_review_check_needs_no_core_changes`;
and, with the repair loop merged alongside, a counterexample refused on attempt
1 (kept as an `Attempt`) and repaired on attempt 2. The AXI4-Lite demo's RTL seat now also writes `axi4_lite_regs.sby`. The
engineering-graph fake-EDA fixture gained a fake `synth.run`; the firmware and
design-agent and repair tests that reach the rtl stage now also need
`yosys`. The FIFO, arbiter, and APB end-to-end tests (M26 blocks) now have the
RTL seat write the block's `.sby` too, so all four blocks are synthesized and
proven before review. The standard run is 1113 tests with 2 skipped (OpenSTA,
OpenROAD), with `sby` required.

Deferred: a separate properties seat and vacuity (cover) checks; formal and
synthesis on the `new-ip`, `feature-addition`, and `rtl-change` RTL stages;
checking the `.sby` `[script]`; moving all of CI to the suite's tools.

v1.20.0 is the one version bump for the three M26 parts (repair loop #33,
blocks #35, formal gate #34), built in parallel. The same release teaches the
vocabulary two APB spellings: the `apb` feature matches APB3 and APB4, and
`block_design` also matches a request for an APB or AXI4-Lite subordinate
(`test_apb_revisions_are_recognized`). The standard run is 1115 tests with 2
skipped (OpenSTA and OpenROAD, not installed).

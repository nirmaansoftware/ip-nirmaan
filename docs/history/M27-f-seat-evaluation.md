# Milestone 27 (seat evaluation) - Structural review, and seat evaluation

The first milestone of the structural review of 2026-09-29
(`docs/architecture/`: `current-state.md`, `target-state.md`,
`proposed-change.md`, and the resumable `REVIEW_PLAN.md`). The review found
that the brief's engine (task, plan, artifact, evidence, tool broker, roles vs
skills, gates, audit, events, traceability) already exists as `work/` plus
`runtime/`, so it adds no parallel `nirmaan/engine/` package and no duplicate
per-topic docs; it orders the real gaps as M27 to M33 in `target-state.md`
section 5 (seat evaluation is a part of the M27 batch, engineering records of the
M29 batch; M28 and M30 to M33 are this review's own). Released in v1.22.0.

M27 answers "does a seat's work actually work?" with cases as data and judges
that are real tool runs. `evals/rtl/*.json` (four cases: the AXI4-Lite and APB
register blocks, the FIFO, the arbiter) each fix the `rtl-implementation`
seat's upstream to the block's interface spec and microarchitecture, hold a
reference answer for replay, and hold out the block's reference testbench.
`nirmaan.evals.run_case` plans the request in a sandbox, fixes the upstream,
puts any runtime in the seat through the unchanged `run_task`, then runs each
held-out check through the broker and returns an `EvalResult`.
`nirmaan eval list` and `nirmaan eval run [CASE...] (--runtime ID | --replay)`.

Key design points worth not re-deriving:
- **A pass is a recorded run.** The runner records a scorer's "passed" as
  failed unless it cites sandbox runs that all succeeded; a refused tool is
  `not_run`, never a pass; replay results carry `replay: true`.
- **The harness fixes work stages only**, as a `SYSTEM` actor named
  `eval-fixture` whose review text names the reference documents; no human
  attestation. A gate or decision upstream of the seat raises `EvalError`.
  The `new-ip` interface-spec stage fans out into variants, so a seat must be
  exactly one task (validated).
- **Scorers are a registry** (`register_scorer`); one ships, `held-out-run`,
  which fills tool parameters from the seat's submitted files by kind, then
  the case's files. Runner and scorers name no stage, tool, kind, or role.
- Case digest: SHA-256 over the case and every file it names.
- Rich markup swallowed `[rtl-implementation]` in CLI lines; whole lines are
  escaped now and a test asserts the brackets appear.

`tests/test_nirmaan_evals.py` (15 tests; on v1.21.0 the standard local run is 1218 passed, 3 skipped), including replay passing on all four
blocks with real tools, and `test_what_the_gates_miss_the_held_out_testbench_catches`
(RTL with `reg3` reset to all ones and a testbench that checks nothing passes
lint, simulation, and synthesis and reaches review; the reference testbench
fails it). Crown jewel `test_a_new_case_or_scorer_needs_zero_core_changes`.
Design doc: `docs/SEAT_EVALUATION.md`; case format: `evals/README.md`.

Deferred: the first live-model run (`--runtime anthropic`), token and cost
accounting (M31), mutation scoring of a seat's testbench, held-out proofs,
specification-seat cases.

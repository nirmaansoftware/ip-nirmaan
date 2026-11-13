# Repro gates: triage and root cause reproduce the failure (M71)

Wave 2 of the capability build-out (council record
`council/records/2026-10-18-capability-buildout.md`, section 10: Verification,
the Debug and Regression department). A debug skill is judged at a seat of a
regression investigation, the way a verification skill is judged at a seat of
block verification (`docs/BLOCK_VERIFICATION.md`). For that, a seat's claimed
root cause must come with a failure a tool ran: a repro testbench that fails on
the RTL under investigation, and, in an evaluation, passes on the held-out fix.

## The gap

- `regression-investigation`'s `triage` stage needs a VeriTriage session and
  `root-cause` needs a review. Nothing either seat claims is run: a root cause
  that names the wrong signal reaches review as easily as the right one.
- The workflow has no RTL under investigation as an artifact, so no gate has
  anything to run a repro on.
- The debug seats were not granted any simulator.
- The eval harness took only a work task as its seat (root cause is a
  decision), could not give a stage the failing logs it investigates, and the
  must-fail scorer judged a seat's files together, one top module for all.

## Reproduction as a tool of its own

`simulator.reproduce` runs the same simulators as `simulator.run` (the `icarus`
and `verilator-sim` steps, the same check that only the testbench may end the
run or read its arguments, the same per-run nonce) and asks the opposite
question. A run passes only when the failure reproduced:

- the design and the testbench built;
- the simulation ran to `$finish`;
- the testbench printed its one verdict line with this run's nonce
  (`NIRMAAN-SIM <nonce> <passed> passed, <failed> failed`), with at least one
  failed check.

A build error, a run that never finishes, a verdict that is missing, repeated
or forged, and a testbench whose checks all pass fail the run, so only the
testbench's own failed check stands for the failure
(`integrations/eda_parsers.py`, `parse_reproduction`).

Why a tool and not a parameter of `simulator.run`: a passing `simulator.run`
means the tests pass, and every reader relies on that (the RTL gates, the
verification-plan status in `engineering.py`, VeriTriage's simulation runs, the
eval records). A reproduction is a passing run of a different tool, so no
requirement that names `simulator.run` can ever be met by one, and no policy
rule had to change. It is not a new external tool: the executables are the
ones `simulator.run` already uses.

## The workflow

A new feature, `reproduction` ("reproduce", "reproducing", "repro",
"reproduction"), with no skills of its own. When a regression investigation
asks for it:

| Stage | Change | Checked before review |
|---|---|---|
| `design-under-investigation` (new, planned only with `reproduction`) | the RTL under investigation, handed over and reviewed (`rtl.implement`, as block verification's `design-under-test`) | none (reviewed) |
| `triage` | builds on that stage; also writes `testbench` files, one repro per failure bucket; adds the skill `failure_triage` | `simulator.reproduce` over the approved RTL and each repro testbench, one run per testbench, top from that testbench |
| `root-cause` | builds on that stage; also writes `testbench` (the repro for its root cause) | the same gate |

The gate's files: `sources` takes the approved upstream `rtl_source` plus one
of the seat's `testbench` files (`FileInput.each`), and `top` that file's own
entry. Every repro the seat submits must reproduce on its own; a repro that
does not reproduce stops the work even beside one that does (tested). The
handed-over RTL writes no RTL, so it is the second named exception, after
`design-under-test`, in `test_every_stage_that_produces_rtl_is_gated`. The gate
shows that the failure is real and reproducible; which of the four outcomes
the root cause is (an RTL bug, a testbench bug, infrastructure, a
specification question) stays the reviewer's call, and in an evaluation the
held-out fix decides whether the repro tests the right thing.

An investigation that does not ask for a reproduction plans exactly as
before. Making the gate unconditional would need the RTL handed over in every
investigation and every existing seat to write a repro; that is a later
decision.

## Three model additions

All are data; nothing names a stage, a tool or a kind in the engine.

1. **`Refinement.outputs` and `Refinement.depends_on`.** A refinement (M65)
   adds skills to a stage's one task when a plan-time condition holds; it may
   now also add outputs and dependencies on earlier stages. A stage's
   `depends_on` would have changed every investigation's plan: a task's
   `inputs` list every dependency's outputs whether or not that stage is
   planned. Validation refuses a refinement dependency that is not an earlier
   stage of the workflow.
2. **`FileInput.each`.** The runtime runs such a requirement once per task
   file of those kinds, each run with that file alone in its parameter (and,
   for an entry binding of the same kinds, that file's own entry). The
   before-review policy counts a file covered only by a passing run that had
   no other file of those kinds from the task, so one run over two
   testbenches, which executes only one top, covers neither.
3. **The grant.** The `failure_triage` and `root_cause_analysis` cards gain
   `simulator.reproduce` and `simulator.run` (tools are granted through
   skills, at the working band and above). The gate needs the first; the
   must-fail judges of an evaluation run the second as the seat.

## Who gets each task

| Request | Stage | Task skills | Owner | Reviewer |
|---|---|---|---|---|
| Investigate the failing counter test in regression and reproduce the failure. | design-under-investigation | | RTL architecture engineer | RTL architecture senior |
| same | triage | failure_triage | debug triage engineer (was the debug intelligence engineer, with no skill) | none (as before) |
| same | root-cause | root_cause_analysis | debug root-cause senior (unchanged) | debug tech lead (unchanged) |

Role changes: every role holding `failure_triage` or `root_cause_analysis` at
the working band or above is now granted `simulator.reproduce` and
`simulator.run`. No owner changes outside a reproduction request.

## The eval harness

- **A decision seat.** `validate_case` and the runner take a decision task as
  the seat. Its case names the reference answer's `outcome` (one of the
  seat's outcomes; refused on any other seat), which replay records.
- **Case inputs.** `EvalCase.inputs`: stage to task input to case files,
  given to that stage, seat or upstream, as a comma-joined list. A triage is
  fixed through its gates and needs a VeriTriage session over the failing
  logs; `{"triage": {"paths": [<log>]}}` gives them. The files are part of
  the case digest. Adding the two fields changes every case's digest; no run
  record is committed, so no recorded trial becomes incomparable.
- **`must-fail-each`.** A registered scorer for several seat files of one
  kind: each runs alone with the case's files (its entry from the seat's own
  passing run over that file alone), each must pass on the clean inputs, and
  each mutant must fail a different file (a matching of mutants to files).
  One repro that fails every seeded bug cannot stand for two buckets.

The root-cause seat needs no new scorer: `must-fail` with `simulator.run`, the
held-out fix as the case file and the RTL under investigation (and a second
planted variant) as mutants, judges its one repro.

## What does not change

Every request that does not ask a regression investigation for a
reproduction plans exactly as before, task for task: the test builds the
organization without M71's planning data (no feature, no new stage, no
refinements or repro gates) and compares every task of every representative
request in the golden suite, plus investigations without a reproduction and a
block-design request that says "reproduces". On a reproduction request, only
the new stage and its workstream are added, triage and root cause change, and
the later tasks' priorities and the debug workstream's status follow the
longer path. No existing gate, evidence requirement or review changes. The regression seats' golden prompts
(`tests/fixtures/prompts/`) change in one line each: their permitted tools now list `simulator.reproduce`
and `simulator.run`.

## Tests

`tests/test_repro_gates.py`: planning and the gate's files; each seat's
skill, owner, grant and packet; `FileInput.each` and refinement validation;
the reproduction verdict on captured logs; the before-and-after comparison;
and, with real simulators through `run_case`, a root-cause seat whose repro
reproduces on the RTL under investigation and passes the must-fail check
against the fix, one whose repro passes on that RTL and never reaches review,
a triage seat with one repro per bucket that `must-fail-each` passes, one
whose single repro fails both bugs and is failed, and one with a repro that
does not reproduce beside one that does, stopped.

## Not in this milestone

- The debug eval cases (W2-E4: `debug/root-cause-uart-tx`,
  `debug/triage-three-bugs`) and their fixtures.
- Repro gates on an investigation that does not ask for one.
- `log_analysis` on the triage seat: it is credited only with a repro
  must-fail (wave 2 plan), which W2-E4's cases give.

`runtime/model.py` and `evals/runner.py` are harness code (M73, `docs/HARNESS.md`), so the harness
fingerprint changes; no trial is recorded, so no level goes stale.

Counts: tools `AVAILABLE` 36 to 37 (`scripts/status.py --write`); no new
skill, workflow, unit or principle.

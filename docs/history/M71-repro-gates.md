# Milestone 71 - Repro gates: a regression investigation asked to reproduce its failure gates triage and root cause on repro testbenches that fail on the handed-over RTL

Wave 2 (Verification, W2-R2) of the capability build-out (council record
`council/records/2026-10-18-capability-buildout.md`, section 10). Design:
`docs/REPRO_GATES.md`. Tests: `tests/test_repro_gates.py`.

**The gap.** Nothing a triage or root-cause seat claimed was run, the
investigation had no RTL artifact to run a repro on, the debug seats held no
simulator, and the eval harness could not seat a decision or give a stage its
failing logs.

**Reproduction.** `simulator.run` gains `expect` (`pass` or `fail`). With
`fail` a run passes only when the testbench ran to `$finish` and its one
nonce-carrying verdict reports a failed check. `expect` is a verdict parameter
(`ToolRun.answers`): such a run counts only where a requirement fixes it, so a
reproduction never meets a requirement for a passing simulation, and the
verification-plan status never reads one. No tool is added.

**Workflow.** The `reproduction` feature plans `design-under-investigation`
(the RTL handed over and reviewed) and refines `triage` (adds
`failure_triage`) and `root-cause`: both build on the handed-over RTL, also
write repro testbenches, and must pass `simulator.run` with `expect=fail` on each one, one
run per testbench, before the work goes on.

**Model.** `Refinement.outputs` and `Refinement.depends_on` (earlier stages
only); `FileInput.each` (one run per task file; the policy counts a file
covered only by a run that had no other such file of the task's).

**Grant.** `failure_triage` and `root_cause_analysis` gain `simulator.run`.

**Harness.** A decision seat with the case's `outcome`; `EvalCase.inputs`
(task inputs as case files, such as the failing logs triage investigates);
the `must-fail-each` scorer (each seat file judged alone; each mutant must fail
a file of its own).

Every request that does not ask an investigation for a reproduction plans
exactly as before, which a test proves against the organization without M71's
planning data.

**Counts.** None change (`scripts/status.py --write`).

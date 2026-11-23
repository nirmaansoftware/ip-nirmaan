# The runner option, part 4b: the flow module

`src/nirmaan/evals/flow.py` (`harness.FLOW_CODE`, digested only in a
whole-flow run's fingerprint) seats every work stage in dependency order with
one seat runtime and one recorder, through the unchanged `run_task`, so each
stage's own before-review checks run for real.

- **Inputs.** A stage gets the case's fixed inputs as task inputs and as
  customer documents (`document.<name>`), so the requirements seat reads them
  as text and its trials are seated at every stage.
- **Pass-through.** Review and approval of every stage but the last are done
  by the harness as `eval-flow-passthrough`, never the fixture, with the note
  "Whole-flow evaluation: not reviewed. No reviewer judged this stage: the
  evaluation harness recorded this review and approval itself, by the
  evaluation's rule, so that later stages receive it as input; 'approved'
  here records that rule, not a judgement. Before-review checks passed:
  <runs>." or, for a stage with no check, the same first two sentences and
  then "This stage has no before-review check: submitted, not checked." These
  are the words of the council record 2026-11-17, sixth addendum, decision P2,
  item 3. A later stage's prompt shows each stage it builds on as approved,
  with a review record that reads "Independent review by" the stage's reviewer
  role and then this note, so the note says who made the record and by what
  rule. The words "reviewed in the repository" are never used.
- **A stage that does not reach review** stops the flow. Later stages are
  recorded "not run", every held-out check is not run, and the trial is a
  failed trial of its group. There is no fallback to a reference document.
- **The judge.** Only the final block is judged. Each check runs under the
  stage that produced the first kind it takes from the seat (so its tool runs
  under a role that may run it) and sees every seated stage's files. A check
  that takes its `top` from `seat_entries` reads it from the producing stage's
  own runs, so check 5 runs on the flow's RTL with the RTL stage's top. The
  held-out-run scorer now honours `seat_entries` (only the whole-flow case
  uses them there).
- **The record.** The record's name ends in `-whole-flow`, and the manifest
  and every trial carry `flow: whole`, all from the case: no option sets or
  clears it. A run never mixes whole-flow and single-seat cases. Each trial
  keeps one `EvalStage` per stage (task, role, the actors that reviewed and
  approved it, status, attempts, gate runs, the skills given with their
  digests, model, calls and tokens, the note), the sums over all stages, the
  attestations of any stage, and the flow digest. The flow digest is sha256
  over the sorted (stage, skill, skill digest) of every skill each seated
  stage was given, in the trial's arm.
- **A test stricter than the contract.** When the clean run of a must-fail
  check fails (the flow's own test on the reference block), or a check with no
  mutants fails on a case file while the same tool on the flow's own file
  passes (check 6 against check 5), the trial's detail names the candidate
  cause "a flow test stricter than the contract", as an inference, not a fact.
  A must-fail check whose mutants survive is a weak test and is never called
  stricter.
- **The stop rule (WF8).** A live whole-flow run stops right after a trial
  whose last recorded answer has no text and an error (`flow_stopped`). The
  single-seat rule (`no_model_answer`) is unchanged.
- **Replay.** A replay answers each stage with the case's reference files of
  the kinds it outputs (`FlowReplayLLM`). `eval run` runs a whole-flow case
  only when it is named, and `eval rejudge` finds it.

Tests (`tests/test_whole_flow_runner.py`):
- the reference flow of both cases passes every check and re-judges clean;
- a flow ending in a mutant RTL fails, and a flow with the wrong map fails
  checks 5 and 6;
- a flow on the conforming RTL passes, with check 5 on the RTL stage's top;
- a flow whose second stage never answers is a failed trial with the later
  stages and every check not run;
- the requirements seat's prompt carries the fixed document;
- a testbench written to the conforming RTL's one choice is named "stricter
  than the contract" as an inference, and a plain fault never is;
- the stop rule fires on (text, text, no text and an error) and not on three
  answers;
- the whole-flow fingerprint digests this module.

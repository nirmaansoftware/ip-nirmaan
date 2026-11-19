# The label and the list (M87)

**The case.** `EvalCase.flow` is `"seat"` (every case so far) or `"whole"`. It
is a property of the case, inside its digest; it is neither a harness variant
nor a command-line flag (decision 3). A whole-flow case names no skill in
`skills` and fixes no upstream stage (`upstream` is empty: every work stage is
seated). It lists the skills each seated stage exercises in `exercised`
(stage to skills), which nothing credits. `validate_case` refuses a whole-flow
case that names a skill, fixes a stage, lists nothing exercised, or lists a
skill outside the catalog or a stage outside the planned workflow, and a
single-seat case that lists anything exercised.

**Two locks.** The label takes the trial out of the levels; the empty `skills`
means the existing rule credits nothing even if a label is lost.

**The trial and the manifest.** `EvalTrial.flow` and `EvalRunManifest.flow`
carry the label. `EvalTrial.stages` (one `EvalStage` per seated stage: task,
role, the actors that submitted, reviewed and approved it, status, attempts,
gate runs, the skills given with their digests, model calls, tokens and the
pass-through note) and `EvalTrial.flow_digest` are defined here and filled by
the whole-flow runner (a later pull request).

**Nothing changes for a single-seat run.** A case, manifest or trial whose
`flow` is `"seat"` dumps exactly as before these fields existed (they are left
out at their defaults), so no case digest changes and no record file gains a
key. No file in `harness.CODE` is touched, so no harness fingerprint changes.

**The reader.** `levels.practised()` checks the label first, before the
calibration, ablation and variant labels and before the skill loop: either the
manifest's label or the trial's alone puts the trial under `whole_flow` in
`capability/levels.json`, and nowhere else. The record's name is never read. A
record that mixes whole-flow and single-seat trials is refused
(`records.is_whole_flow`). A replay or an attested whole-flow record is
refused as any other.

**The listed count.** Trials are grouped by case, case digest, model, harness,
CLI version and flow digest, and by purpose, so a calibration trial is never
pooled with evidence. Arms are apart already: a run without knowledge is a
different harness. Every trial is listed one by one with whether a judge ran.
A group's "whole-flow pass count" (`count`: `n`, `passed`, `unjudged` and the
95 percent Wilson interval) is written only from `WHOLE_FLOW_MIN` (10) trials;
whether the planned count of the group is complete is the committed batch
plan's (decision 4), which this file does not hold. A trial no judge ran on is
a failed trial of its group. The count is never a level, a score or a bare
percentage, has no bar, is never in the totals and is never pooled across
groups (WF11).

**Default case sets.** `load_cases(root)` returns single-seat cases only;
`flow="whole"` or `flow=None` asks for the others. So `eval run`, the levels
and the shipped-case checks never see a whole-flow case, and the weekly or any
default run cannot pick one up. Until the whole-flow runner is merged,
`record_run` refuses a whole-flow case before it writes anything: a whole-flow
case never runs as a single-seat case.

Tests: `tests/test_whole_flow.py` and the whole-flow section of
`tests/test_capability_levels.py`.

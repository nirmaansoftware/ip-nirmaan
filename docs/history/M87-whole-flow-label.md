# Milestone 87 - Whole-flow cases: the label and the list

Item G3 of the capability build-out, first pull request of the council record
`council/records/2026-11-17-g3-whole-flow-cases.md` (decision 1, decision 3
"The label and the list", gate WF2). Design: `docs/WHOLE_FLOW.md`. Tests:
`tests/test_whole_flow.py` and the whole-flow section of
`tests/test_capability_levels.py`.

**The gap.** The levels credited every skill a case names. Only three labels
took a trial out (knowledge off, a calibration purpose, a harness variant), so
a whole-flow record that named skills would have been credited.

**The label.** `flow: whole` on the case, the run manifest and the trial.
Either the manifest's label or the trial's alone takes a trial out of the
levels, checked before every other label. The record's name is never read.

**The list.** `whole_flow` in `capability/levels.json`, by group (case digest,
model, harness, CLI, flow digest, purpose), every trial listed; the
whole-flow pass count is written only from 10 trials. A mixed record is
refused. A whole-flow case names no skill and lists what it exercises
apart, the second lock.

**No change for a run without the label.** Single-seat cases, manifests and
trials dump as before, so no case digest changes; no file in `harness.CODE`
is touched, so the default, attempts-3 and tools-in-loop fingerprints are
unchanged. A whole-flow case is in no default case set, and `record_run`
refuses one until the whole-flow runner exists.

**Not here.** The cases, fixed documents and judge controls, and the runner
option (its `runner.py` dispatch waits for the H3 batch, gate WF1).

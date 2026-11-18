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

**The cases (second pull request).** `flow/axil-timer` and
`flow/axi4-lite-regs-driver` under `evals/flow/`, a new tagged timer
requirements document, the register block's own copies of its requirements,
driver interface and held-out test, a citation file per case, and the
fixtures for the controls. A test settles fact 10: a document given through a
case's `inputs` never reaches the requirements seat as text.

**The judge controls (third pull request).** `evals/flow/controls.json`, 20
replays through the real gates and scorers with no model call, run in CI
(`tests/test_whole_flow_controls.py`), and their recorded CI run in
`evals/flow/controls_record.json`. They confirm by a run that `b_before_w` is
not visible through the HAL and that no driver test can see latency.

**The timer document fixed, and the check record rule (follow-up).** An
independent check found that `evals/flow/axil_timer/requirements.md` claimed
tags its checks do not reach and left rules open (readiness one way only, the
response edge, the read value, `COUNT` after a stop and on a `CTRL` write at a
count end). The document now states each rule exactly as the reference RTL
does, splits every partly reached rule, and lists the unreached parts as not
judged. Each flow requirements document gets a check record by another
session (`requirements_check.json`), held by a test; both documents wait for
theirs.

**Not here.** The runner option (its `runner.py` dispatch waits for the H3
batch, gate WF1).

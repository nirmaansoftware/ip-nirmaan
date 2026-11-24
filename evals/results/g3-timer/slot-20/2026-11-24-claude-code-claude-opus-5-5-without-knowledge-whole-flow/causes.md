# Failed trial and its cause (flow/axil-timer, slot 20)

Record `2026-11-24-claude-code-claude-opus-5-5-without-knowledge-whole-flow`, one trial, G3 timer case, slot 20 of 20, group B, without documents, purpose evidence, run 45467216245, manifest head_sha `e058183a`, harness `sha256:7e8ba68dd60b395186441ba4c27392659189a603b59705fa2cc3d4dbf5c4a83c`, case digest `sha256:ff8a4afc77caee105070d996f3e29142f2fe013c411752becdc46090b7553da3`, flow digest `sha256:9d94c40502aa75d262248c4e74b51aecbe1f9a0ec8d661a1db9e1723f78f0506`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`). Written after the read, from the committed record only (the stage records and the trial's detail); the record was committed without a `causes.md`.

Cause words are those of the read of the timer case's twenty trials: the eighth addendum of `council/records/2026-11-17-g3-whole-flow-cases.md` (ip#545, read on `main` at `904bb511`), unchanged. A cause is stated as fact only where a gate's own record shows it; anything else is marked inference.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, flow stopped | stopped at `microarchitecture`: the seat escalated; cause not established | Stage `microarchitecture` has no check; its recorded status is `escalated`, with one attempt and one model call, and no answer of the trial records an error. No later stage ran and no judge ran (both held-out scores read "the work never reached review, so there is nothing to judge"), so the trial is a failed trial of its group. The seat's own words, in the trial's `detail`: "Escalation goes to design.rtl.architecture.staff first. No tools were run and no run IDs exist in the citation list. Requirement tags (TMR-*) appear in the file as plain text taken from the interface spec, not as citation tokens." |

Not labelled "model": the failure-to-curriculum rule does not apply, and the trial is not said to show a gap in any skill (decision P4). No count is stated from which it is left out and no figure for a stage.

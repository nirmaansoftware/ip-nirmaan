# Failed trial and its cause (flow/axil-timer, slot 9)

Record `2026-11-24-claude-code-claude-opus-5-5-whole-flow`, one trial, G3 timer case, slot 9 of 20, group A, with documents, purpose evidence, run 45367262139, manifest head_sha `90fabb76`, harness `sha256:56c5fac7d788bb34f84b263db1a50b896aba5779387bfed63a0a07975e4dcd72`, case digest `sha256:ff8a4afc77caee105070d996f3e29142f2fe013c411752becdc46090b7553da3`, flow digest `sha256:4ff378d26fdeb8f6daab2aaebfbe8395e44ec663e0ad7f7d7eaf1a155b971315`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`). Written after the read, from the committed record only (the stage records and the trial's detail); the record was committed without a `causes.md`.

Cause words are those of the read of the timer case's twenty trials: the eighth addendum of `council/records/2026-11-17-g3-whole-flow-cases.md` (ip#545, read on `main` at `904bb511`), unchanged. A cause is stated as fact only where a gate's own record shows it; anything else is marked inference.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, flow stopped | stopped at `microarchitecture`: the seat escalated; cause not established | Stage `microarchitecture` has no check; its recorded status is `escalated`, with one attempt and one model call, and no answer of the trial records an error. No later stage ran and no judge ran (both held-out scores read "the work never reached review, so there is nothing to judge"), so the trial is a failed trial of its group. The seat's own words, in the trial's `detail`: "The bracketed requirements-spec tokens that the upstream interface spec uses are not on my citation list, so I refer to that document in words only. Requirement tags such as TMR-READY are plain text labels copied from the interface spec. Per P6, this spec needs an independent review record; I do not review or approve it." |

Not labelled "model": the failure-to-curriculum rule does not apply, and the trial is not said to show a gap in any skill (decision P4). No count is stated from which it is left out and no figure for a stage.

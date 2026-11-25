# Failed trial and its cause (debug/root-cause-uart-tx, slot 90)

Record `2026-11-25-claude-code-claude-opus-5-5`, one trial, wave 2 re-measure batch slot 90 of 117 (round 7, arm E, with documents), purpose evidence, run 45551469299, manifest head_sha `ac4cf264`, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`, case digest `sha256:9be6d4f3a142bf825f6b7a8938d836e9acec0f3ad6b69bf4cc519d4f81a9f06c`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`, `same: true`). Written before this record merged, from the record only (the seat's answer, its gate runs, the judge runs and the scores); plan `evals/plans/2026-11-23-w2-remeasure.md`, section 8 ("Labels"). A cause is stated as fact only where the record shows it; anything else is marked inference.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, judged | model (the repro does not fail the shift-register variant uart_tx_alt_reload) | Both held-out checks failed on the same mutant: "mutant tests/fixtures/dv/uart_tx/mutants/uart_tx_alt_reload.v survived: simulator.run run-0006 passed" (failed runs: run-0005) and "... survived: simulator.run run-0009 passed" (failed runs: run-0008). |

Fact: the seat's repro failed the RTL under investigation and passed the fixed implementations, but passed the defective variant uart_tx_alt_reload as well.

Inference, not fact: the repro checks the symptom of the bug in one implementation's form and not the defect the variant shares; which bit or cycle it samples is not read for this label.

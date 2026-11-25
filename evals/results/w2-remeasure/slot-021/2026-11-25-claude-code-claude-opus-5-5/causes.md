# Failed trial and its cause (dv/coverage-tick-timer, slot 21)

Record `2026-11-25-claude-code-claude-opus-5-5`, one trial, wave 2 re-measure batch slot 21 of 117 (round 2, arm E, with documents), purpose evidence, run 45525932379, manifest head_sha `9646f5b3`, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`, case digest `sha256:b4be7351302e30fcb73109e39941b7d05871cf99957c46a9495fda80e3cae17a`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`, `same: true`). Written before this record merged, from the record only (the seat's answer, its gate run, the judge runs and the score); plan `evals/plans/2026-11-23-w2-remeasure.md`, section 8 ("Labels"). A cause is stated as fact only where the record shows it; anything else is marked inference.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, judged | model (the testbench never writes LOAD while the count runs) | The seat's gate passed: `coverage.read` run-0002, "line 100.00% (10/10), toggle 84.54% (93/110), branch 100.00% (8/8); simulation passed: 88 checks passed". The held-out must-fail check failed: "mutant tests/fixtures/dv/tick_timer/mutants/tick_timer_load_late_applies.v survived: coverage.read run-0006 passed" (failed runs: run-0005). That mutant's header: "A write to LOAD also replaces the count while the timer runs, in place of that edge's count step." In the testbench in the seat's answer, each `write(A_LOAD, ...)` comes in a section before the `write(A_CTRL, ...)` that starts the count (sections B, D, E, F and G), after a reset or a stop. |

Fact: no LOAD write in the testbench is made while the count runs; the surviving mutant differs from the approved RTL only on such a write.

Inference, not fact: the mutant survived because that write is never made. The judge does not report which check a testbench making it would have failed.

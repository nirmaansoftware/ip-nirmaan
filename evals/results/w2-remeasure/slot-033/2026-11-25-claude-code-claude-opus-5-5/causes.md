# Failed trial and its cause (dv/coverage-tick-timer, slot 33)

Record `2026-11-25-claude-code-claude-opus-5-5`, one trial, wave 2 re-measure batch slot 33 of 117 (round 3, arm E, with documents), purpose evidence, run 45530785114, manifest head_sha `d83d6aaa`, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`, case digest `sha256:b4be7351302e30fcb73109e39941b7d05871cf99957c46a9495fda80e3cae17a`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`, `same: true`). Written before this record merged, from the record only (the seat's answer, its gate run, the judge runs and the score); plan `evals/plans/2026-11-23-w2-remeasure.md`, section 8 ("Labels"). A cause is stated as fact only where the record shows it; anything else is marked inference.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, judged | model (the testbench never writes LOAD while the count runs) | The seat's gate passed (`coverage.read` run-0002). The held-out must-fail check failed: "mutant tests/fixtures/dv/tick_timer/mutants/tick_timer_load_late_applies.v survived: coverage.read run-0006 passed" (failed runs: run-0005). That mutant's header: "A write to LOAD also replaces the count while the timer runs, in place of that edge's count step." The testbench in the seat's answer writes LOAD at its lines 68, 70, 74, 94, 139, 146 and 157: after reset (68, 70, 74), after `wr(CTRL, 32'h0000_0000)` stops the count (139, 146), and each time before the `wr(CTRL, ...)` that starts it (74, 94, 139, 157). |

Fact: the LOAD writes at lines 68, 70, 74, 139 and 146 are made with the count stopped; the surviving mutant differs from the approved RTL only on a LOAD write while the count runs.

Inference, not fact: the writes at lines 94 and 157 also come with the count stopped (after a one-shot expiry and an earlier stop), so no LOAD write is made while the count runs, and the mutant survived for that reason. The judge does not report which check a testbench making such a write would have failed.

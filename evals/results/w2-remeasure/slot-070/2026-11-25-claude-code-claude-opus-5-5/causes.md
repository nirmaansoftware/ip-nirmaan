# Failed trial and its cause (dv/coverage-tick-timer, slot 70)

Record `2026-11-25-claude-code-claude-opus-5-5`, one trial, wave 2 re-measure batch slot 70 of 117 (round 5, arm E, with documents), purpose evidence, run 45544560506, manifest head_sha `643d1120`, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`, case digest `sha256:b4be7351302e30fcb73109e39941b7d05871cf99957c46a9495fda80e3cae17a`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`, `same: true`). Written before this record merged, from the record only (the seat's answer, its gate runs, the judge runs and the scores); plan `evals/plans/2026-11-23-w2-remeasure.md`, section 8 ("Labels"). A cause is stated as fact only where the record shows it; anything else is marked inference.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, judged | model (the testbench does not catch a LOAD write that changes the running count, req:TMR-LOAD-LATE) | The held-out must-fail check failed: "mutant tests/fixtures/dv/tick_timer/mutants/tick_timer_load_late_applies.v survived: coverage.read run-0006 passed" (failed runs: run-0005). That mutant's header: "A write to LOAD also replaces the count while the timer runs, in place of that edge's count step." The case's specification (`tests/fixtures/dv/tick_timer/interface_spec.md`, line 62) states the rule the mutant breaks: "A write to `LOAD` does not change the count: the new value is used at the next start or periodic reload. [req:TMR-LOAD-LATE]" |

Fact: the surviving mutant breaks a requirement the case's specification states by tag; the seat's testbench passed the approved RTL and did not fail that mutant; the replay of this case's reference answer in this batch (gate W2C5) failed every mutant, so the mutant can be caught.

Inference, not fact: the testbench never writes LOAD while the count runs, or does not check the count after such a write (not read line by line for this label). Every coverage-tick-timer trial of this batch so far failed, most on this mutant; that is for the read.

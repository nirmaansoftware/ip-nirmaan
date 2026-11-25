# Failed trial and its cause (rtl/apb-gpio, slot 76)

Record `2026-11-25-claude-code-claude-opus-5-5`, one trial, wave 2 re-measure batch slot 76 of 117 (round 6, arm E, with documents), purpose evidence, run 45546830513, manifest head_sha `3b435921`, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`, case digest `sha256:99f32bda9197066b2e7ab67ef4cbdb2793259ae556a38257b5035f2e82d04cd5`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`, `same: true`). Written before this record merged, from the record only (the seat's answer, its gate runs, the judge runs and the scores); plan `evals/plans/2026-11-23-w2-remeasure.md`, section 8 ("Labels"). A cause is stated as fact only where the record shows it; anything else is marked inference.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, judged | model (the seat's RTL leaves PSLVERR unknown on a read) | The first held-out check failed: "simulator.run run-0004: icarus: simulation failed: 4 errors, the testbench reports 4 of 1521 checks failed; first: ...apb_gpio_tb.v:69: lane N=8: read pslverr low: got 0x0000000X, expected 0x00000000". The other three held-out checks passed. |

Fact: the reference testbench read X on PSLVERR during a read from the seat's RTL at N=8, where 0 is expected.

Inference, not fact: the seat's RTL leaves PSLVERR undriven or unreset in some state; which line does so is not read for this label.

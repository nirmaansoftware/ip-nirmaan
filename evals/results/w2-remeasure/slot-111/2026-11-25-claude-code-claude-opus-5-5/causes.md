# Failed trial and its cause (rtl/apb-gpio, slot 111)

Record `2026-11-25-claude-code-claude-opus-5-5`, one trial, wave 2 re-measure batch slot 111 of 117 (round 8, arm E, with documents), purpose evidence, run 45558177839, manifest head_sha `eb6197ff`, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`, case digest `sha256:99f32bda9197066b2e7ab67ef4cbdb2793259ae556a38257b5035f2e82d04cd5`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`, `same: true`). Written before this record merged, from the record only (the seat's answer, its gate runs, the judge runs and the scores); plan `evals/plans/2026-11-23-w2-remeasure.md`, section 8 ("Labels"). A cause is stated as fact only where the record shows it; anything else is marked inference.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, judged | model (the seat's RTL leaves DATA_IN unknown after reset) | The first held-out check failed: "simulator.run run-0004: icarus: simulation failed: 2 errors, the testbench reports 2 of 1521 checks failed; first: ...apb_gpio_tb.v:69: lane N=8: DATA_IN after reset: got 0xxxxxxxxx, expected 0x00000000". The other three held-out checks passed (the seat's testbench failed 4 of 4 mutants; both proofs reached every cover and failed each mutant). |

Fact: the reference testbench read X on DATA_IN after reset from the seat's RTL at N=8, where 0 is expected.

Inference, not fact: the seat's RTL does not reset or drive DATA_IN's register at reset; which line of its RTL does so is not read for this label. The same first failure is in slot 64's record.

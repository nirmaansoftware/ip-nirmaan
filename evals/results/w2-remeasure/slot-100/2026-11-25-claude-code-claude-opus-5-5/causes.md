# Failed trial and its cause (rtl/apb-gpio, slot 100)

Record `2026-11-25-claude-code-claude-opus-5-5`, one trial, wave 2 re-measure batch slot 100 of 117 (round 7, arm E, with documents), purpose evidence, run 45554792178, manifest head_sha `6e21f719`, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`, case digest `sha256:99f32bda9197066b2e7ab67ef4cbdb2793259ae556a38257b5035f2e82d04cd5`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`, `same: true`). Written before this record merged, from the record only (the seat's answer, its gate runs, the judge runs and the scores); plan `evals/plans/2026-11-23-w2-remeasure.md`, section 8 ("Labels"). A cause is stated as fact only where the record shows it; anything else is marked inference.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, judged | model (the seat's testbench names a signal its RTL does not have) | The second held-out check failed before any mutant ran: "the clean inputs do not pass: simulator.run run-0005: icarus: simulation failed: 1 error, exit status 1, $finish never reached ...; first: ...apb_gpio_tb.v:450: Unable to bind wire/reg/memory `dut8.status' in `apb_gpio_tb`". The reference testbench passed on the seat's RTL (run-0004, 1521 checks), and both proofs passed. |

Fact: the seat's own testbench refers to `dut8.status`, which the elaborated design does not have, so it does not compile against the RTL it was judged with.

Inference, not fact: the testbench reaches into an internal signal by hierarchical name that the seat's RTL names otherwise or does not have.

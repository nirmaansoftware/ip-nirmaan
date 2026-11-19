# Failed trial and its cause (rtl/apb-gpio, arm E: the default harness)

Record `2026-11-19-claude-code-claude-opus-5-5-68`, one trial, W2-L1 batch (slot 132 of 153), purpose evidence, knowledge on, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` (the default harness, attempts-3, on main 01adfe9), Claude Code 2.1.325, seat model claude-opus-5-5. Rejudged: the verdict reproduces (`rejudge.json`).

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed | model | Reached review; 3 of 4 held-out checks passed. The reference testbench failed on the seat's RTL: 2 of 1521 checks, first `apb_gpio_tb.v:69: lane N=8: DATA_IN after reset: got 0xxxxxxxxx, expected 0x00000000`. The input path is left unreset, so DATA_IN reads x after reset. The seat's own testbench and both proofs passed. |

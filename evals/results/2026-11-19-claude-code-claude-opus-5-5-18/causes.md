# Failed trial and its cause (dv/coverage-irq-ctrl, arm E: the default harness)

Record `2026-11-19-claude-code-claude-opus-5-5-18`, one trial, W2-L1 batch (slot 78 of 153), purpose evidence, knowledge on, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` (the default harness, attempts-3, on main 01adfe9), Claude Code 2.1.325, seat model claude-opus-5-5. Rejudged: the verdict reproduces (`rejudge.json`).

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed | model | Reached review. The held-out check failed: "mutant tests/fixtures/dv/irq_ctrl/mutants/irq_ctrl_level_mask_ignored.v survived: coverage.read run-0007 passed". The seat's testbench passed the approved RTL but did not fail the mutant that ignores the mask in level mode. |

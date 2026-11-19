# Failed trial and its cause (dv/equiv-gray, arm E: the default harness)

Record `2026-11-18-claude-code-claude-opus-5-5-35`, one trial, W2-L1 batch (slot 40 of 153), purpose evidence, knowledge on, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` (the default harness, attempts-3, on main 01adfe9), Claude Code 2.1.325, seat model claude-opus-5-5. Rejudged: the verdict reproduces (`rejudge.json`).

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed | model | Reached review. The held-out must-fail check failed: "mutant tests/fixtures/dv/gray_counter/mutants/gray_counter_refactor_flip_wrong_bit.v survived: equivalence.run run-0003 passed". The seat's eqy setup proved the approved refactor equivalent (2 of 2 partitions) but also proved a non-equivalent refactor. The setup used the `sat` strategy at depth 10; the record does not establish which setup line lets the mutant through. |

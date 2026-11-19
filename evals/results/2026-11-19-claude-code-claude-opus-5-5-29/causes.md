# Failed trial and its cause (dv/equiv-gray, arm E: the default harness)

Record `2026-11-19-claude-code-claude-opus-5-5-29`, one trial, W2-L1 batch (slot 89 of 153), purpose evidence, knowledge on, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` (the default harness, attempts-3, on main 01adfe9), Claude Code 2.1.325, seat model claude-opus-5-5. Rejudged: the verdict reproduces (`rejudge.json`).

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed | model | Reached review. The held-out must-fail check failed: "mutant tests/fixtures/dv/gray_counter/mutants/gray_counter_refactor_flip_wrong_bit.v survived: equivalence.run run-0003 passed". The seat's eqy setup (strategies `sat` then `sby`, depth 10) proved the approved refactor and also the non-equivalent one; the record does not establish which setup line lets the mutant through. |

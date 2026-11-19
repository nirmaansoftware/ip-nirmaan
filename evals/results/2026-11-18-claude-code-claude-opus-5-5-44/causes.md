# Failed trial and its cause (dv/plan-irq-ctrl, arm E: the default harness)

Record `2026-11-18-claude-code-claude-opus-5-5-44`, one trial, W2-L1 batch (slot 49 of 153), purpose evidence, knowledge on, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` (the default harness, attempts-3, on main 01adfe9), Claude Code 2.1.325, seat model claude-opus-5-5. Rejudged: the verdict reproduces (`rejudge.json`).

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed | model | vplan.check failed on each of the 3 attempts: the YAML did not parse, then 42 problems (no `format` or `version`, items with `description` and no `name`), then 20 problems (items with no `id`). The last attempt was refused (P9: the plan does not cover every requirement of the approved interface spec). Never reached review. |

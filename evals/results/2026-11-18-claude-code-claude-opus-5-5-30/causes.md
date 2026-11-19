# Failed trial and its cause (dv/plan-irq-ctrl, arm E: the default harness)

Record `2026-11-18-claude-code-claude-opus-5-5-30`, one trial, W2-L1 batch (slot 33 of 153), purpose evidence, knowledge on, harness `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` (the default harness, attempts-3, on main 01adfe9), Claude Code 2.1.325, seat model claude-opus-5-5. Rejudged: the verdict reproduces (`rejudge.json`).

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed | model | vplan.check failed on each of the 3 attempts: the YAML file did not parse ("line 1: Expecting value"), then the JSON plan had no `format` or `version`, unknown fields and items without `name`, then `format` was `vplan` instead of `nirmaan.vplan` and items had no `id`. The last attempt was refused (P5, a tool run never recorded). Never reached review. |

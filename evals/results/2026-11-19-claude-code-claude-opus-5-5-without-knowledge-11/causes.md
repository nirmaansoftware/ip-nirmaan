# Failed trial and its cause (dv/plan-irq-ctrl, arm N: without knowledge documents)

Record `2026-11-19-claude-code-claude-opus-5-5-without-knowledge-11`, one trial, W2-L1 batch (slot 152 of 153), purpose evidence, knowledge off, harness `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39` (the default harness, attempts-3, on main 01adfe9), Claude Code 2.1.325, seat model claude-opus-5-5. Rejudged: the verdict reproduces (`rejudge.json`).

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed | model | Run without knowledge documents (arm N). vplan.check failed: a Markdown file that did not parse, then a JSON plan with 129 problems (no `format` or `version`, unknown fields). It asked for escalation on attempt 3. Never reached review. The same case passed 6 of 8 with documents. |

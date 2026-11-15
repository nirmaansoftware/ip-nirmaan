# Ablation records (P3-L2, knowledge documents off): trials and causes

Records: `-without-knowledge-10` (skid-buffer, 2 trials) and `-11` (apb-gpio, 2 trials). Run without the knowledge documents (`--without-knowledge`; manifest and trials carry `"knowledge": "off"`), harness
`sha256:e4dea03a8b802265a19b0215bae56c4e79b0af6203e2125ed5a930d3ec6458b1` as recorded in every trial (the knowledge-on records carry a different harness hash, so the two sets do not share a harness), Claude Code 2.1.325, model claude-opus-5-5. These records never count toward a level.
Authority: the founder decision on main 3c9fe7d (live eval batches).

Failed trials:

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| `-without-knowledge-11` | 1 | not passed, judged | model (not further established) | trial-01.json: the reference testbench failed on the seat's RTL, "2 of 1521 checks failed; first: apb_gpio_tb.v:69: lane N=8: DATA_IN after reset: got 0xxxxxxxxx"; the seat's testbench and both proofs passed their checks. |

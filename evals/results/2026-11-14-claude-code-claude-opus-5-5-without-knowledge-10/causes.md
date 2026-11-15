# Ablation records (P3-L2, knowledge documents off): trials and causes

Records: `-without-knowledge-10` (skid-buffer, 2 trials) and `-11` (apb-gpio, 2 trials). Run without the knowledge documents (`--without-knowledge`; manifest and trials carry `"knowledge": "off"`), same commit, same harness
`sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711`, Claude Code 2.1.325, model claude-opus-5-5. These records never count toward a level.
Authority: the founder decision on main 3c9fe7d (live eval batches).

Failed trials:

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| `-without-knowledge-11` | 1 | not passed, judged | model (not further established) | trial-01.json: the reference testbench failed on the seat's RTL, "2 of 1521 checks failed; first: apb_gpio_tb.v:69: lane N=8: DATA_IN after reset: got 0xxxxxxxxx"; the seat's testbench and both proofs passed their checks. |

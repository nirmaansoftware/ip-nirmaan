# Ablation records (P3-L2, knowledge documents off): trials and causes

Records: `-without-knowledge` (rr-arbiter, 3 trials) and `-without-knowledge-2` (2 trials). Run without the knowledge documents (`--without-knowledge`; manifest and trials carry `"knowledge": "off"`). The manifests carry different head_sha values: `-without-knowledge` 9789616 and `-without-knowledge-2` 930238e (the commit relationship is not established here). Same harness
`sha256:e4dea03a8b802265a19b0215bae56c4e79b0af6203e2125ed5a930d3ec6458b1`, Claude Code 2.1.325, model claude-opus-5-5. These records never count toward a level.
Authority: the founder decision on main 3c9fe7d (live eval batches).

Failed trials:

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| `-without-knowledge-2` | 2 | not passed, never judged | model (not further established) | trial-02.json: the seat's own simulation gate failed with "rr_arbiter_tb.v:39: syntax error"; submission refused (P9 "Self-checking simulation passes" not met). |

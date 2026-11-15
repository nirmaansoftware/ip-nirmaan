# Ablation records (P3-L2, knowledge documents off): trials and causes

Records: `-without-knowledge-9` (skid-buffer, 3 trials) and `-14` (axil-timer, 1 trial). Run without the knowledge documents (`--without-knowledge`; manifest and trials carry `"knowledge": "off"`), same commit, same harness
`sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711`, Claude Code 2.1.325, model claude-opus-5-5. These records never count toward a level.
Authority: the founder decision on main 3c9fe7d (live eval batches).

Failed trials:

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| `-without-knowledge-14` | 1 | not passed, never judged | model (not further established) | trial-01.json: the seat's own simulation gate failed with "axil_timer_tb.v:117: syntax error"; submission refused (P9 "Self-checking simulation passes" not met). |

# Ablation records (P3-L2, knowledge documents off): trials and causes

Records: `-without-knowledge-7` (axi4-lite-regs, 3 trials). Run without the knowledge documents (`--without-knowledge`; manifest and trials carry `"knowledge": "off"`), same commit, same harness
`sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711`, Claude Code 2.1.325, model claude-opus-5-5. These records never count toward a level.
Authority: the founder decision on main 3c9fe7d (live eval batches).

Failed trials:

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| `-without-knowledge-7` | 2 | not passed, refused before review | the seat declared `[tasks]` and the gates refuse it (H2: harness input rule; the document is not loaded here) | trial-02.json: "axi4_lite_regs.sby declares [tasks]; the cover check runs single-task setups only"; P9 "Formal properties are proven" and "The proof is not vacuous" not met. |

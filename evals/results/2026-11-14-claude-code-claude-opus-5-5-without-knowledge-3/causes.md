# Ablation records (P3-L2, knowledge documents off): trials and causes

Records: `-without-knowledge-3` (sync-fifo, 3 trials) and `-4` (2 trials). Run without the knowledge documents (`--without-knowledge`; manifest and trials carry `"knowledge": "off"`), on different commits (manifest head_sha `f8f80baba04efe31a592669ba676e36fd1da4a4d` for `-3`, `e1d0154a7713bf5c313631fd0236d1495ba06783` for `-4`), same harness in both records
`sha256:e4dea03a8b802265a19b0215bae56c4e79b0af6203e2125ed5a930d3ec6458b1`. This knowledge-off harness differs from the with-knowledge harness (`sha256:35643990...`). Claude Code 2.1.325, model claude-opus-5-5. These records never count toward a level.
Authority: the founder decision on main 3c9fe7d (live eval batches).

No failed trial in these records.

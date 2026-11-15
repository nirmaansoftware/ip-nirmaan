# Trials that hit the plan limit (P3 top-up, rtl/apb-gpio and rtl/axil-timer)

Records: this directory (`-limit-12`, apb-gpio, 2 trials), `-limit-13` (axil-timer, 3 trials) and `-limit-14` (axil-timer, 2 trials). The manifests keep their original ids (`...-5-5-12`, `-13`, `-14`); the directories carry `-limit-` in the name because the re-run records, made after the limit reset, were written under those same names. Harness `sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711`, Claude Code 2.1.325, model claude-opus-5-5.

| Record | Trials | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this, `-limit-13`, `-limit-14` | 7 in all (2 + 3 + 2), started 08:36Z | not passed, no submission, work stayed in progress | plan limit, not the model | Each trial's result detail and answer error: "Claude Code reported success: You've hit your 5-hour limit". Each call returned in about 2 seconds with no model answer. |

These 7 trials were committed late: they were first kept out of the repository, then recorded here (decision D11: an interrupted trial stays recorded as failed). Trials 2 and 3 of `2026-11-15-claude-code-claude-opus-5-5-11` (apb-gpio) hit the same limit and were already merged with their own causes.md.

The same 7 slots were run again after the limit reset (10:20Z): apb-gpio in `2026-11-15-claude-code-claude-opus-5-5-12` (2 trials), axil-timer in `...-13` (3 trials) and `...-14` (2 trials). Those are the merged records of the same numbers. The 35 planned trials are therefore recorded as 35 trials plus 7 limit-failed attempts re-run, 42 attempts in all. The levels rule (`not_tool_judged`) leaves trials that never reached review out of a group, so these records do not move any level.

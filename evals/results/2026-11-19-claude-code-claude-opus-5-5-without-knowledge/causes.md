# Failed trial and its cause (dv/random-crc, arm N: without knowledge documents)

Record `2026-11-19-claude-code-claude-opus-5-5-without-knowledge`, one trial, W2-L1 batch (slot 57 of 153), purpose evidence, knowledge off, harness `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39` (the default harness, attempts-3, on main 01adfe9), Claude Code 2.1.325, seat model claude-opus-5-5. Rejudged: the verdict reproduces (`rejudge.json`).

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed | plan limit, not the model | Run without knowledge documents (arm N). The second attempt's model call returned "Claude Code reported success: You've hit your 5-hour limit" with no answer, and the seat was declined; the first attempt's testbench had printed no verdict. The batch driver stopped on this record (2026-11-19 00:04Z) and continued from the next slot after the reset. Under decision D11 this trial stays recorded as failed and was not run again. Arm N trials count toward no level. |

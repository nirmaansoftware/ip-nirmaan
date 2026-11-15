# Failed trials and their causes (rtl/skid-buffer and rtl/axil-timer)

Records: `-9` (skid-buffer, 3 trials, all passed) and `-12` (axil-timer, 2 trials). Harness `sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711`, Claude Code 2.1.325, seat model claude-opus-5-5.
Authority for the live run: the founder decision on main 3c9fe7d (live eval batches). The runner started each record only after a script check
that no review was running; that check is not recorded in the repository.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| `-12` | 2 | not passed, never judged | infrastructure: interrupted by the plan limit (H2), not the model | trial-02.json: "the model call failed: Claude Code reported success: You've hit your 5-hour limit"; 1.8 s, 0 input and 0 output tokens, no text. Kept as a failed trial: a trial with no judge run is a failed trial (CAPABILITY_LEVELS) and is never left out. It was not rerun in place; record `-14` (PR to follow) adds one more axil-timer trial. |

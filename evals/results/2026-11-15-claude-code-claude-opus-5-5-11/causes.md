# Failed trials and their causes (P3 top-up, rtl/apb-gpio)

Record: this directory (3 trials, harness `sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711`, Claude Code 2.1.325, model claude-opus-5-5).
Authority: the founder decision of 2026-11-14 (live eval batches) and D1d of the pilot retrospective.

| Trial | Outcome | Cause | What the record shows |
|---|---|---|---|
| 2 | not passed, work stayed in progress, no submission | plan limit, not the model | `trial-02.json` result detail and answer error: "the model call failed: Claude Code reported success: You've hit your 5-hour limit". The call returned after about 2 seconds with no answer. |
| 3 | not passed, same | plan limit, not the model | Same message, same 2 second call, started right after trial 2. |

Trial 1 passed. Under D11 an interrupted trial is recorded as failed. These two trials ran no model work, so they say nothing about the skill. Neither reached a judge, but rtl/apb-gpio is tool-judged, so they stay in each group as unjudged failures (record section 9 item 6) and are not in `not_tool_judged`. The trials that replace them (the 2-trial apb-gpio record that follows) are recorded in the next PR.

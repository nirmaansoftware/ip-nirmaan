# Failed trials and their causes (P3-L1, rtl/rr-arbiter)

Records: this directory (3 trials, manifest head_sha 160d2a8) and `2026-11-14-claude-code-claude-opus-5-5-2` (2 trials,
manifest head_sha 558e3e3: the same run branch, one commit later, the first record's own commit). Both trials sets carry the harness
`sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711` and Claude Code 2.1.325. Authority for the live run: the founder
decision on main 3c9fe7d (live eval batches). The runner started each record only after a script check that no review was running; that
check is not recorded in the repository.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 3 | not passed, work stayed in progress | model (not further established) | `trial-03.json` result `gate_runs` run-0002: the seat's own simulation gate failed, message "N=4: coverage: no-request case not reached", 8 errors, no verdict line. Lint and synth passed. The record does not show why the stimulus missed that case; nothing points to the harness or the case. |

Record `-2`: both trials passed. The five trials (4 passed) give a Wilson lower bound of 0.376, under 0.5, so the group is not Practised.

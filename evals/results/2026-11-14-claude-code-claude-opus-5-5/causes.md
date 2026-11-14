# Failed trials, causes (P3-L1, rtl/rr-arbiter)

Records: this directory (3 trials) and `2026-11-14-claude-code-claude-opus-5-5-2` (2 trials). Harness
`sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711` (Claude Code 2.1.325), run on main 160d2a8.
Live run authorised by the founder decision on main 3c9fe7d (live eval batches, gate G17), run while both review loops were idle.

| Record | Trial | Outcome | Cause | Evidence |
|---|---|---|---|---|
| this | 3 | failed, work did not pass its own simulation gate | model | The seat's own testbench (`rr_arbiter_tb.v`) reported "N=4: coverage: no-request case not reached": it asserted a coverage goal its own stimulus never drove. Lint and synth passed. |

Record `-2`: both trials passed. The group (5 trials, 4 passed) has a Wilson lower bound under 0.5, so it is not Practised.

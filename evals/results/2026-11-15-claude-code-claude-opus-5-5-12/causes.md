# Failed trials and their causes (P3 top-up, rtl/apb-gpio)

Record: this directory (2 trials, harness `sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711`, Claude Code 2.1.325, model claude-opus-5-5).
Authority: the founder decision of 2026-11-14 (live eval batches) and D1d of the pilot retrospective.

| Trial | Outcome | Cause | What the record shows |
|---|---|---|---|
| 2 | not passed, reached review, 3 of 4 held-out checks passed | model | `trial-02.json` score 1: the reference testbench failed on the seat's RTL, "lane N=8: DATA_IN after reset: got 0xxxxxxxxx, expected 0x00000000" (2 of 1521 checks failed). The seat's own lint, simulation and synthesis runs passed. The two mutant checks and both proofs passed. |

Trial 1 passed.

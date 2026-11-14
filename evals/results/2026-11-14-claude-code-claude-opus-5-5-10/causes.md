# Failed trials and their causes (rtl/skid-buffer and rtl/apb-gpio)

Records: `-10` (skid-buffer, 2 trials, both passed) and `-11` (apb-gpio, 2 trials). Harness `sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711`, Claude Code 2.1.325, seat model claude-opus-5-5.
Authority for the live run: the founder decision on main 3c9fe7d (live eval batches). The runner started each record only after a script check
that no review was running; that check is not recorded in the repository.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| `-11` | 2 | not passed, never reached review | model (not further established) | trial-02.json: the seat's own simulation gate failed, "77 errors, the testbench reports 77 of 3128 checks failed; first: apb_gpio_tb.v:167: step 2 check 26: got ffffffff expected 00000000"; submission refused (P9 "Self-checking simulation passes" not met). The record does not show whether the testbench or the RTL was wrong. |

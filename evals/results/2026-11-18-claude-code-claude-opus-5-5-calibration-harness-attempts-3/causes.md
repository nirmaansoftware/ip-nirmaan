# Failed trial and its cause (rtl/apb-gpio, arm R: attempts-3)

Record `2026-11-18-claude-code-claude-opus-5-5-calibration-harness-attempts-3`, one trial, harness variant attempts-3, Claude Code 2.1.325, seat model claude-opus-5-5, purpose calibration.

| Trial | Outcome | Cause | What the record shows |
|---|---|---|---|
| 1 | reached review, 3 of 4 held-out checks passed | model | The reference testbench failed on the seat's RTL: 2 of 1521 checks failed, first `apb_gpio_tb.v:69: lane N=8: DATA_IN after reset: got 0xxxxxxxxx, expected 0x00000000`. The seat's RTL left the input path unreset, so DATA_IN reads x after reset. The seat's own testbench and both proofs passed. The same fault failed the other default-family arm on this case (the harness comparison H3, one trial per arm per case). |

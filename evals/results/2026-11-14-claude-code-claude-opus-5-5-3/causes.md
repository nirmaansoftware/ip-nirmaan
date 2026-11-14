# Failed trials and their causes (rtl/sync-fifo)

Records: `-3` (3 trials, all passed) and `-4` (2 trials). Harness `sha256:35643990d58bf28264abe98752bd6c2750a391483ac43176b4748a38fbc32711`, Claude Code 2.1.325, seat model claude-opus-5-5.
Authority for the live run: the founder decision on main 3c9fe7d (live eval batches). The runner started each record only after a script check
that no review was running; that check is not recorded in the repository.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| `-4` | 1 | not passed, never reached review | knowledge document contradicts the gate (H2: knowledge/harness defect) | trial-01.json: the seat submitted a `.sby` that declares `[tasks]`; `formal.run` and `formal.cover` refused it ("declares [tasks]; formal runs single-task setups only (refused, nothing ran)"), and the submission was refused before review (P9 "Formal properties are proven" and "The proof is not vacuous" not met). `knowledge/design/rtl_design.md` ("Proof setup") says an optional `[tasks]` section runs a proof and a cover from one file, which the gates do not accept. The L2 record `-without-knowledge-7` shows the seat can also choose `[tasks]` without the document, so the document is a contributing cause, not the only one. |
| `-4` | 2 | not passed, never reached review | knowledge document contradicts the gate (H2: knowledge/harness defect) | trial-02.json: same refusal as trial 1. |

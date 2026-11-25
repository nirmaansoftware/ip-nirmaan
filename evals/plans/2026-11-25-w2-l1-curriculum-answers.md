# W2-L1: the failure-to-curriculum answers

The answers for the model-labelled failed trials of the W2-L1 batch, as
`council/records/2026-11-23-wave-2-close-meeting-1.md` (addendum of
2026-11-25, decision M8) rules them and as the text of ip#568 gave them,
one line per failure in the form `scripts/failure_curriculum.py` reads.
They are the eleven of W2-L1 and the two calibration records of the
harness comparison that the script lists with the same record keys.

`tests/test_failure_curriculum.py` runs the script on this file in the
test job, with the record keys dated 2026-11-18 and 2026-11-19, and fails
if any of the thirteen is unanswered or names a path that is not a file.

This file changes no record, label, level or case. No trial reads it.

- 2026-11-18-claude-code-claude-opus-5-5-30:trial-01: note: knowledge/verification/verification_planning.md (ip#439): the plan file's format as the plan check reads it
- 2026-11-18-claude-code-claude-opus-5-5-44:trial-01: note: knowledge/verification/verification_planning.md (ip#439): the plan file's format as the plan check reads it
- 2026-11-18-claude-code-claude-opus-5-5-35:trial-01: note: knowledge/verification/equivalence_checking.md (ip#431, ip#443, ip#453): the sat strategy and the mutant it proved falsely
- 2026-11-19-claude-code-claude-opus-5-5-29:trial-01: note: knowledge/verification/equivalence_checking.md (ip#431, ip#443, ip#453): the sat strategy and the mutant it proved falsely
- 2026-11-19-claude-code-claude-opus-5-5-71:trial-01: note: knowledge/verification/equivalence_checking.md (ip#431, ip#443, ip#453): the sat strategy and the mutant it proved falsely
- 2026-11-19-claude-code-claude-opus-5-5-18:trial-01: must-fail: evals/dv/coverage_tick_timer.json (ip#436): its mutant tick_timer_irq_ie_ignored_periodic.v is wrong in one mode only; that it is of the same class as the survivor irq_ctrl_level_mask_ignored is an inference
- 2026-11-19-claude-code-claude-opus-5-5-37:trial-01: note: knowledge/design/control_logic_design.md (ip#439), given as decision M8 rules; the note describes a register left out of the reset branch, and design-architect's read of this record found both sample registers in the reset branch and the input widened in an always @* block, so a corrected answer is carried (design-architect)
- 2026-11-19-claude-code-claude-opus-5-5-68:trial-01: note: knowledge/design/control_logic_design.md (ip#439), given as decision M8 rules; the note describes a register left out of the reset branch, and design-architect's read of this record found both sample registers in the reset branch and the input widened in an always @* block, so a corrected answer is carried (design-architect)
- 2026-11-18-claude-code-claude-opus-5-5-calibration:trial-01: note: knowledge/design/control_logic_design.md (ip#439), given as decision M8 rules; the note describes a register left out of the reset branch, and design-architect's read of this record found both sample registers in the reset branch and the input widened in an always @* block, so a corrected answer is carried (design-architect)
- 2026-11-18-claude-code-claude-opus-5-5-calibration-harness-attempts-3:trial-01: note: knowledge/design/control_logic_design.md (ip#439), given as decision M8 rules; the note describes a register left out of the reset branch, and design-architect's read of this record found both sample registers in the reset branch and the input widened in an always @* block, so a corrected answer is carried (design-architect)
- 2026-11-18-claude-code-claude-opus-5-5-8:trial-01: no: the repro was refused for its verdict line and file I/O; the card now states the repro gate's plusarg and verdict line (ip#442), and a card change is not a knowledge note, so the answer is this written reason (meeting 1, decision 8, item 4); the label stays "model"
- 2026-11-19-claude-code-claude-opus-5-5-without-knowledge-3:trial-01: no: the arm without documents on debug/root-cause-uart-tx; the same written reason as the trial with documents on this case, citing ip#442 (meeting 1, decision 8, item 4); the label stays "model"
- 2026-11-19-claude-code-claude-opus-5-5-without-knowledge-11:trial-01: no: the arm without documents on dv/plan-irq-ctrl, where the documents are withheld by design; the plan format it missed is answered by the note in knowledge/verification/verification_planning.md (ip#439) for the trials with documents

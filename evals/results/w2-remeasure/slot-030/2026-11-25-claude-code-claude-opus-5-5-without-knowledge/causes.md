# Failed trial and its cause (dv/plan-irq-ctrl, slot 30)

Record `2026-11-25-claude-code-claude-opus-5-5-without-knowledge`, one trial, wave 2 re-measure batch slot 30 of 117 (round 2, arm N, without documents), purpose evidence, run 45529525294, manifest head_sha `d83d6aaa`, harness `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39`, case digest `sha256:1a553dafca71aece791fbac7921963f026cf0750fa3efd43e7f495dfd5ebb799`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`, `same: true`). Written before this record merged, from the record only (the seat's three answers, the gate runs and the score); plan `evals/plans/2026-11-23-w2-remeasure.md`, section 8 ("Labels"). A cause is stated as fact only where the record shows it; anything else is marked inference. Arm N counts toward no level.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, never reached review | model (without documents: the plan did not follow the plan check's format, and the seat escalated) | The plan gate refused the first two attempts: `vplan.check` run-0001, "verification_plan.md: 1 problem(s): line 1: Expecting value"; run-0002, "verification_plan.json: 114 problem(s): line 1: the plan has no 'format'; line 1: the plan has no 'version'; line 2: unknown field 'title' in the plan; ...". On attempt 3 the seat submitted no plan and escalated ("needs_escalation on attempt 3"; "No plan file is submitted, because a file built on a guessed schema would likely fail vplan.check again"). The held-out check is "not_run" ("the work never reached review"). |

Fact: both plans the seat submitted were refused by `vplan.check` for their format, and the third attempt escalated with no plan.

Inference, not fact: without the knowledge document the seat did not know the plan file's format (its own note says it guessed the schema). Whether the card, the case or the gate's refusal gives enough to write the format is not established here.

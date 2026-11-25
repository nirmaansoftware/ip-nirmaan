# Failed trial and its cause (dv/plan-tick-timer, slot 103)

Record `2026-11-25-claude-code-claude-opus-5-5-without-knowledge`, one trial, wave 2 re-measure batch slot 103 of 117 (round 7, arm N, without documents), purpose evidence, run 45555950335, manifest head_sha `6e21f719`, harness `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39`, case digest `sha256:7737a5dbba68a1313cbd3ac54e330c5c6f56ae0d7b7a3cd3e59f7d8d1ccf21d4`, Claude Code 2.1.325, seat model claude-opus-5-5. Re-judged: the verdict reproduces (`rejudge.json`, `same: true`). Written before this record merged, from the record only (the seat's answer, its gate runs, the judge runs and the scores); plan `evals/plans/2026-11-23-w2-remeasure.md`, section 8 ("Labels"). A cause is stated as fact only where the record shows it; anything else is marked inference. Arm N counts toward no level.

| Record | Trial | Outcome | Cause | What the record shows |
|---|---|---|---|---|
| this | 1 | not passed, never reached review | model (without documents: the plan did not follow the plan check's format, and the seat escalated) | The plan gate refused the first two attempts: `vplan.check` run-0001, "tick_timer_vplan.md: 1 problem(s): line 1: Expecting value"; run-0002, "tick_timer_vplan.json: 114 problem(s): line 1: the plan has no 'format'; line 1: the plan has no 'version'; line 2: unknown field 'block' in the plan; ...". Attempt 2 was also refused under P5 for naming run-0001 in tool_runs. On attempt 3 the seat escalated ("needs_escalation on attempt 3"). The held-out check is "not_run". |

Fact: both plans the seat submitted were refused by `vplan.check` for their format, and the third attempt escalated with no plan.

Inference, not fact: without the knowledge document the seat did not know the plan file's format; whether the card, the case or the gate's refusal gives enough to write it is not established here.

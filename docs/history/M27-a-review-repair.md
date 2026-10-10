# Milestone 27 - Repair after review, and retry limits per stage (after Stage 6)

When an independent reviewer (a human, or a review seat through `review_task`)
requests changes, the owner seat can be run again with the review's findings
and the sent-back files in its prompt; its new files go through every
before-review check and to review again. `max_attempts` and a new
`max_review_rounds` can be set per workflow stage, and both budgets persist
across `nirmaan run` invocations. Design doc: `docs/REVIEW_REPAIR.md`.

Key design points worth not re-deriving:
- **Supersession happens at the change request, in `TaskEngine.review`.** When
  the verdict moves the task to `changes_requested`, `_supersede` moves the
  task's artifacts out of `state.artifacts` into an M26 `Attempt` with the new
  field `reviews` (every review of that submission). The audit entry is the
  `task.review` itself, with `details.superseded` and `details.artifacts`.
  Superseded artifacts keep their IDs; `submit` numbers new ones after them, so
  an ID never changes meaning. Export, links, trace, and approval never see
  them, structurally, as with M26's refused files.
- **`latest_verdicts` skips reviews listed in an `Attempt`**, so a second
  round's verdict never conflicts with the first round's.
- **A change request is citable, not evidence.** The prompt declares each
  review as `[review:<task>.r<n>]`; recording it as `REVIEW_RECORD` evidence
  would satisfy "Independent review recorded" with a rejection.
- **Limits:** `runtime.limits(engine, task, attempts, review_rounds)` returns
  the CLI override, else `StageTemplate.max_attempts` or `max_review_rounds`
  (new, `None` inherits), else the capability (`max_review_rounds` new,
  default 1), else 1. `nirmaan run --review-rounds N` joins `--attempts N`.
- **Budget from state:** rounds used = superseded `Attempt`s; attempts used =
  refused `Attempt`s numbered after the latest superseded one (this round).
  `run_task` escalates (technical, the owner's route, no model call) when
  rounds used reach the limit, or this round's recorded refusals do. Resolving
  the escalation restores the task, not the budget; a higher limit allows more.
  With the default of one round, running the owner on a sent-back task now
  escalates instead of starting fresh; humans can still start and submit.
- **Prompt:** work mode renders "Repair after review", every change request
  with its token, and the latest sent-back files (digest-checked), then M26's
  block for this round's refused attempts only. Review mode lists earlier
  change requests as context, never a superseded file.

`tests/test_nirmaan_review_repair.py` (11 tests): crown jewel
`test_a_new_stage_gets_review_repair_with_no_core_changes` (a units-sheet stage
with `max_review_rounds=2` over a capability's 3, checker bound in the test);
precedence; a CLI limit below the stage escalates; exhausted rounds escalate
and resolution does not reset them; the attempt budget across three CLI runs
with the SDK import poisoned; real RTL sent back by a reviewer seat, repaired
through lint and simulation, approved, with only the second submission in the
export and the links; supersession audited and IDs never reused; a superseded
round's reviews do not conflict; P6; the runtime names nothing and keeps the
import laws; nothing shipped sets a limit. `test_changes_requested_sends_work_back`
now expects v1 in an `Attempt`, not among the task's artifacts.

Deferred: an unattended owner and reviewer loop in one command; resetting a
budget on resolution; file-level signoff (a passing run over a superseded file
stays on the task as evidence); `DOCUMENT` evidence and spec requirements that
name a superseded artifact keep their records.

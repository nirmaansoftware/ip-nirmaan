# Milestone 29 - An unattended owner and reviewer loop in one command (after Stage 6)

`nirmaan drive PROJECT [TASK] --runtime ID --reviewer-runtime ID` strings M27's
steps together: the owner seat (`run_task`, with M26 attempts and M27 limits),
the planned reviewer seat (`review_task`), the owner again after a change
request, and so on, until a person must act. With no TASK it drives every
ready task in dependency order. Design doc: `docs/AUTO_LOOP.md`.

Key design points worth not re-deriving:
- **The loop holds two seats only.** `nirmaan/runtime/loop.py` calls
  `run_task` and `review_task` and nothing else that changes state, apart from
  its audit entry. It never approves a task, signs a gate (human-required or
  not), completes, resolves, unblocks, or cancels; a test checks the module's
  calls. A passed review stops at `awaiting_approval`; a ready gate stops at
  `awaiting_gate`, so dependents stay planned until a person acts. Tasks with
  no review complete on submission (the engine's rule), so their dependents
  are driven in the same invocation.
- **Next step from state alone** (`next_step`): `ready`, `changes_requested`,
  `in_progress` mean the owner; `in_review` with review `pending` means the
  reviewer; everything else is a `Stop` (`awaiting_approval`, `conflicted`,
  `escalated`, `blocked`, `waiting`, `done`, `awaiting_gate`). Results add
  `declined`, `refused`, and `budget`. After a `refused` owner step the loop
  continues only when the next owner run would escalate (no call); with one
  attempt M26 records nothing, so it stops rather than ask forever.
- **Budget:** `--max-calls` (default 20) per invocation. A call is one owner
  attempt (`len(report.attempts)`) or one reviewer step (always charged 1). A
  step starts only if its worst case fits: `owner_calls` is the stage's
  attempts minus this round's refused attempts, or 0 when `exhausted` (M27's
  check, extracted from `_exhausted` in `runtime/base.py` and now public). The
  task limits in state still cap every task across invocations.
- **Audit and resume:** `TaskEngine.record_step` (the one engine addition)
  writes `loop.step` on the task as the acting seat (an AI agent named for its
  runtime), with step, seat, runtime, status, calls, review, escalation,
  attempts, and tool runs. The CLI saves after every step (`on_step`), so an
  interruption loses at most the step in flight; rerunning resumes.
- **Independence:** the reviewer is always the task's planned reviewer (P6 is
  checked inside `review_task`). `--reviewer-runtime` defaults to `--runtime`;
  the doc justifies that (different seat and packet, a fresh stateless review
  prompt that never carries the owner's prompt, grounded verdicts, and a
  person still approves). The CLI notes a shared runtime on stderr.
- `plan_loop` gives the worst case sequence as data for `--dry-run`; nothing
  is called or saved. `--input` needs a TASK.

`tests/test_nirmaan_auto_loop.py` (19 tests): the full loop on the AXI4-Lite
interface spec in one CLI command (owner, change request, repair, approving
review, stop at the human approval, then a person approves); the same on real
AXI4-Lite RTL with a formal counterexample repaired inside an attempt
(`NIRMAAN_REQUIRE_EDA`); never self-approves; project mode stops at a gate
(human-required or not) and never crosses it; the budget before a step and an
owner charged its attempts; resume after a crash from saved state; spent
rounds and spent attempts escalate with no call; a refusal with one attempt
stops; a decline stops; the plan and `--dry-run`; a shared runtime is named;
crown jewel `test_a_new_workflow_is_driven_with_no_core_changes` (a gated
two-stage workflow and a runtime, both written in the test); the loop names
nothing and keeps the import laws; every step audited as its seat.

Deferred: concurrent tasks; a call budget across invocations; approval by a
delegated non-human approver; task inputs in project mode.

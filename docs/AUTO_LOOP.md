# An unattended owner and reviewer loop (Milestone 29)

Status: design for the owner's review, implemented on branch `m29/auto-loop`.
This is post-roadmap work (see `docs/ROADMAP.md`, "After Stage 6"). Prose here
is free of em and en dashes per the standing style law.

M27 made every piece of the owner and reviewer cycle exist, one invocation at a
time: `nirmaan run` works a task (with M26's repair attempts), `nirmaan run
--review` seats the independent reviewer, and a task the reviewer sends back is
worked again with the findings. M27 deferred the loop that strings them
together. M29 builds it:

```
nirmaan drive <project> rtl-implementation --runtime anthropic --reviewer-runtime anthropic
nirmaan drive <project> --runtime anthropic --max-calls 40          # every ready task, in dependency order
nirmaan drive <project> rtl-implementation --runtime anthropic --dry-run
```

`drive` runs the owner seat (and its repair attempts), then the independent
reviewer seat, then the owner again on a change request, and so on, until the
task reaches something the loop may not do itself: an approval or a gate that
a person gives, an escalation, a block, or a decline. It never approves
anything.

---

## 1. The laws

Every earlier law holds: the engine decides whether work goes to review (P9),
the reviewer is a different seat from the owner (P6), a human signs the gates
marked human-required (P12), nothing unbacked counts, and every limit is data
(M27). M29 adds:

1. **The loop holds two seats, and only two.** It acts as a task's owner
   (`run_task`) and as its planned reviewer (`review_task`). It never approves
   a task, signs a gate, completes a task, resolves an escalation, unblocks, or
   cancels. Approval is the approver's decision and stays with a person, so the
   loop cannot approve its own work even indirectly. A task with no review
   completes on submission, as it always has; that is the engine's rule, not a
   decision the loop makes.
2. **It never crosses a gate.** In project mode a gate task that is ready is a
   stop, whether or not the gate is human-required. Work behind a gate stays
   planned until a person signs it.
3. **The next step is a function of state alone.** What the loop does next is
   read from the task's status and review state, and the limits from
   `state.attempts` (M27). Nothing is kept in memory between steps, so an
   interrupted loop resumes by being run again.
4. **Every step is audited and saved.** Each step adds a `loop.step` audit
   entry (seat, runtime, status, calls, and the records it produced), and the
   CLI saves the project after every step. An interruption loses at most the
   step in flight.
5. **It is bounded twice.** The M27 limits bound each task (attempts per round,
   review rounds), across every run. A call budget (`--max-calls`, default 20)
   bounds one invocation: a step starts only if its worst case fits.
6. **Exhaustion escalates, as in M27.** When a task's rounds or attempts are
   spent, the owner step escalates through the owner's route with no model
   call, and the loop stops there.
7. **The loop names nothing.** No seat, stage, tool, skill, or artifact kind.
   Which task is next comes from the plan's dependencies; who acts comes from
   the task's `owner` and `reviewer`.

---

## 2. One task

```
                +--------------------------------------------+
                v                                            |
 ready / changes_requested / in_progress                     |
        | owner step: run_task (M26 attempts, M27 limits)    |
        v                                                    |
 in_review, review pending                                   |
        | reviewer step: review_task (P6 checked first)      |
        +-- request_changes -> changes_requested ------------+
        +-- approve -> in_review, review passed  ==> STOP: awaiting approval
```

The next step, from the task alone:

| Task | Next |
|---|---|
| `ready`, `changes_requested`, `in_progress` | owner step |
| `in_review`, review `pending` | reviewer step |
| `in_review`, review `passed` | stop: `awaiting_approval` (a person approves) |
| `in_review`, review `conflicted` | stop: `conflicted` (a manager settles it, P7) |
| `escalated` | stop: `escalated` |
| `blocked` | stop: `blocked` |
| a ready gate | stop: `awaiting_gate` |
| `planned` | stop: `waiting` (upstream not done) |
| `approved`, `completed`, `cancelled`, `failed` | stop: `done` |

And from a step's result:

| Step result | Loop |
|---|---|
| owner `submitted` | continue (the task is now in review, or completed if it needs none) |
| owner `needs_escalation` | stop: `escalated` (the model asked, or a limit is spent) |
| owner `blocked` | stop: `blocked` (a check that must pass cannot run here) |
| owner `declined` | stop: `declined` |
| owner `refused` | continue only if the next owner step would escalate (the attempt limit is spent, so it costs no call); else stop: `refused`. With an attempt limit of 1, M26 records no attempt, so asking again would never end: the loop stops |
| reviewer `submitted` | continue (the verdict moved the task) |
| reviewer `declined` | stop: `declined` (no verdict, or a verdict with nothing cited) |

A step the engine refuses outright (a policy violation, for example P8 on an
unapproved input) raises, as `nirmaan run` does: the CLI reports it, and the
steps before it are already saved.

---

## 3. The whole project

With no task named, `drive` works the plan in dependency order: a stable
topological order of the project's work and decision tasks. Each pass takes the
first task, in that order, whose next step is a seat step and that has not
stopped in this invocation, and drives it until it stops. It ends when no task
has a step to take.

A task is driven only when it is `ready` (every dependency completed or
cancelled) or already in the owner and reviewer cycle. Because the loop never
approves, a reviewed task stops at `awaiting_approval`, and its dependents stay
planned until a person approves it. The same holds at a gate. In practice one
invocation works every task that is ready now and returns the list of what is
waiting on people; after they approve, the next invocation carries on. Tasks
whose stage needs no review complete on submission, so their dependents become
ready and are worked in the same invocation.

---

## 4. Budgets

| Bound | Where | Covers |
|---|---|---|
| `max_attempts` | stage, then capability, or `--attempts` (M26, M27) | owner model calls in one review round |
| `max_review_rounds` | stage, then capability, or `--review-rounds` (M27) | submissions of a task that may go to review |
| `--max-calls N` (default 20) | the command | runtime calls in this invocation |

A call is one answer asked of a runtime: one `execute` of the owner seat (each
M26 attempt is one) or one `review`. Before a step, the loop computes its worst
case: an owner step may make `max_attempts` minus this round's refused
attempts, or zero when the step would escalate; a reviewer step makes one. If
the worst case does not fit in what is left, the loop stops with `budget`
before the step, so the budget is never exceeded. Calls are counted from each
step's report (one per attempt), so a step that ends early costs only what it
used.

The per task bound is in state and covers every invocation. The call budget is
per invocation, by design: rerunning the command is the operator choosing to
spend more, and the task limits still cap the total at
`max_attempts x max_review_rounds` owner calls and `max_review_rounds` review
calls for each task.

### Dry run

`--dry-run` prints the plan of calls and changes nothing: no model is called,
no tool is run, nothing is saved. For each task the loop would drive now, it
lists the worst case sequence from the current state, with the seat, the
runtime, the round, and the most calls each step may make, and ends with the
total against the budget:

```
plan for prj-...:rtl-implementation (reviewer seat on mock-llm, owner seat on mock-llm)
  1. owner design.rtl.interface.senior on mock-llm: round 1 of 2, up to 3 calls
  2. reviewer design.rtl.interface.tech_lead on mock-llm: 1 call
  3. owner design.rtl.interface.senior on mock-llm: round 2 of 2, up to 3 calls
  4. reviewer design.rtl.interface.tech_lead on mock-llm: 1 call
  5. owner design.rtl.interface.senior: escalates if changes are requested again (no call)
  then: stop, awaiting a person's approval
worst case: 8 calls, budget 20
```

In project mode only tasks that are actionable now are planned; tasks that
become ready during a run (behind a stage that needs no review) are planned
when they do.

---

## 5. Independence of the reviewer

P6 is enforced by the engine on every review: `review_task` checks
`independent-review` before the runtime is asked anything, so the owner's seat
can never be handed its own work. The loop seats the task's planned reviewer,
a different role from its owner, every time.

`--reviewer-runtime` defaults to `--runtime`, so both seats may run on the same
model. Independence still holds, for these reasons, each of which is a
property of the code rather than of the model:

1. **A different seat.** The reviewer acts as a different role, with that
   role's packet (`assemble(engine, task, role=reviewer)`): its own skills,
   authority, and memory scope. The engine records the verdict as that role's,
   and P6 refuses it from the owner.
2. **A different prompt, with no shared conversation.** Each call is a fresh,
   stateless request. The review prompt is rendered in review mode from state:
   the submitted files (digest checked), the recorded tool runs, and earlier
   change requests. It never contains the owner's prompt, reasoning, or a
   superseded or refused file (M27). The loop also builds the two seats as
   separate runtime objects, so nothing in process is shared between them.
3. **The verdict must be grounded.** A review with no citation of a declared
   record is not recorded (M20), so a reviewer cannot approve on the owner's
   say so.
4. **A person still approves.** The review opens approval; it does not grant
   it. The approver, outside the loop, decides.

An organization that wants a different model in the reviewer seat passes
`--reviewer-runtime` (for example a second registered provider). The step
records and the report name the runtime of every step, and the report says
when both seats shared one.

---

## 6. Resuming

The CLI saves the project after every step. If the command is interrupted
(Ctrl-C, a crash, a lost connection), the saved state is the state after the
last finished step, and the step in flight is redone on the next run: a task
that was started but not submitted is `in_progress`, which `run_task` already
continues. Budget counts come from `state.attempts`, so nothing double counts.
To resume, run the same command again.

---

## 7. Audit

* `loop.step` per step, on the task, by the seat that acted (an AI agent named
  for its runtime): `details.step` (its number in this invocation), `seat`
  (`owner` or `reviewer`), `runtime`, `status`, `calls`, and the records it
  produced (`review`, `escalation`, `attempts`, `tool_runs`).
* Underneath, every engine action the step took has its own entry, as before:
  `task.start`, `task.attempt`, `task.submit`, `task.review`,
  `escalation.raise`.

`TaskEngine.record_step` is the one engine addition: it appends that entry,
through the policy checks like any other action, and changes nothing else.

---

## 8. Extension points

| To add | Do this | Core changes |
|---|---|---|
| A new workflow driven end to end | data: stages, reviews, gates | none |
| A runtime for either seat | `@register_runtime` (M20) | none |
| A tighter or looser per task bound | `max_attempts`, `max_review_rounds` on the stage | none |

The crown jewel `test_a_new_workflow_is_driven_with_no_core_changes` adds a
two-stage workflow with a human-required gate between the stages, from data in
the test. The loop works the first stage through a change request, a repair,
and an approval by review, stops for a person's approval, then stops at the
gate; after a person signs it, the next invocation drives the second stage.

---

## 9. Laws, each pinned by a test (`tests/test_nirmaan_auto_loop.py`)

1. The full loop on the AXI4-Lite flow: owner, a change request, the repair,
   an approving review, and a stop at the human approval, in one command.
2. It never self-approves: no approval, gate, completion, or resolution is in
   the loop's audit entries; the module calls none of them.
3. In project mode it stops at human gates and never crosses one.
4. The call budget is enforced before a step, and counted after.
5. An interrupted loop resumes from the saved state alone.
6. An exhausted limit escalates with no model call, and the loop stops.
7. `--dry-run` prints the plan, calls nothing, and saves nothing.
8. Crown jewel: a new workflow is driven with no core changes.
9. The loop names no seat, stage, or tool, and keeps the import laws. Real
   tool tests use `NIRMAAN_REQUIRE_EDA`; no test reaches a model API.

---

## 10. Deferred

* Running independent tasks concurrently. The loop is sequential; a project's
  ready tasks are worked one after another.
* A call budget that persists across invocations. The task limits already
  bound the total; a project wide spend limit would be new state.
* Approval by a delegated non-human approver. The loop leaves every approval
  to a person.
* Setting task inputs per task in project mode beyond the same `--input` for
  every driven task.

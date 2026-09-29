# Repair after review, and retry limits per stage (Milestone 27)

Status: design for the owner's review, implemented on branch
`m27/review-repair`. This is post-roadmap work (see `docs/ROADMAP.md`, "After
Stage 6"). Prose here is free of em and en dashes per the standing style law.

M26 closed one loop: when the constitution refuses a submission because a
before-review check failed, the seat is asked again with the failed runs as
evidence. M26 deferred three things, and M27 builds them:

1. **Repair after review.** An independent reviewer (a human, or a review seat
   through `review_task`) requests changes. Until now the next `nirmaan run`
   started fresh from `changes_requested`, never saw what the reviewer said,
   and the rejected files stayed among the task's artifacts: they were
   approved, exported, and linked with the files that replaced them.
2. **Limits per stage.** `max_attempts`, and a new `max_review_rounds`, can be
   set on a workflow stage, overriding the capability.
3. **A budget across runs.** The counts live in project state, so a limit
   applies to the total over every `nirmaan run`, not to each run.

```
nirmaan run <project> rtl-implementation --runtime anthropic --review-rounds 3
nirmaan run <project> rtl-implementation --runtime anthropic --review
```

---

## 1. The laws

Every earlier law holds. In particular P6: the reviewer is independent, and
never reviews its own output; the engine decides whether work may go to review;
and nothing that did not pass counts. M27 adds:

1. **A submission sent back by review is superseded, at once, structurally.**
   When a review moves a task to `changes_requested`, the engine moves the
   task's artifacts out of `state.artifacts` into an `Attempt` record that
   names the reviews of that submission. Nothing that reviews, verifies,
   approves, exports, or links artifacts can see them again, exactly as M26
   keeps refused files out.
2. **The findings are citable, and they are not evidence.** The work prompt
   declares each review record as a `[review:...]` citation. A change request
   is never recorded as `Evidence`: a `REVIEW_RECORD` evidence satisfies
   "Independent review recorded", and a review that rejected the work must not
   satisfy anything.
3. **A repair goes through everything again.** The owner's new files are
   checked by every before-review requirement (P9) over the files submitted,
   and go to review again. Reviews of a superseded submission no longer count
   toward the verdict.
4. **Every limit is data, and bounded.** Precedence for both limits: the CLI
   flag, then the workflow stage, then the capability, then 1.
5. **Exhausted budgets escalate.** When the rounds (or this round's recorded
   attempts) are used up, `run_task` escalates through the owner's existing
   escalation route instead of calling the model. It never loops.
6. **The runtime names nothing.** No seat, tool, stage, or artifact kind.

---

## 2. What is superseded, and when

```
IN_REVIEW --review: request_changes--> CHANGES_REQUESTED
              task.artifacts           -> Attempt <task>#t<n> (reviews: every review of that submission)
              state.artifacts          -  those IDs removed
              audit task.review        details: superseded, artifacts
```

The `Attempt` is M26's record, with one new field:

```python
class Attempt(BaseModel):
    ...
    reviews: tuple[str, ...] = ()   # M27: the reviews that sent this submission back
```

An `Attempt` with `reviews` is a superseded submission; one without is a
refused attempt (M26). Both count in the same sequence (`<task>#t1`,
`<task>#t2`, ...), so the order of events on the task is the order of its
numbers. A superseded artifact keeps its ID, its assurance, and its digest.

**Why at the change request, not at the resubmit?** From the moment a
reviewer rejects the work it is not a deliverable, so the export and the links
should not show it while the owner repairs it either. It also keeps every
record in time order, which the budget counts depend on (section 4).

**Artifact IDs are never reused.** `submit` numbers a new artifact after every
artifact the task has ever had, superseded ones included, so a verification
item or an audit entry that names `<task>#a1` can never come to mean a
different file.

**What else changes.** `latest_verdicts` (policy) ignores reviews listed in an
`Attempt`, so a second round's verdict is not in conflict with the first
round's. A verification item declared in a superseded file reports
`unverifiable: its artifact ... is not recorded`, which is true: the file it
lives in is no longer a deliverable. Evidence on the task (the tool runs of
every round) stays, as M26 keeps a refused attempt's runs: a failed run is a
fact worth keeping.

A task whose reviews conflict stays `in_review`, as before; nothing is
superseded until the verdict is a change request.

---

## 3. What the owner sees on a repair after review

The packet's `task["reviews"]` lists every review of the task, and each entry
of `task["attempts"]` carries its `reviews`. The work prompt declares a
citation per review, `[review:<task>.r<n>]`, and renders, in the Task section:

```
- Repair after review: submission 1 was sent back by an independent review and nothing
  from it counts. Address every finding and answer again in full; your new files go
  through every check and to review again.
- Review [review:....rtl-implementation.r1] by <reviewer> on submission 1 requested
  changes: the counter wraps at 15 but the spec [artifact:...] says 9 ...
- Content of sent-back file counter.v (sha256:...):
=== FILE: counter.v ===
...
=== END FILE ===
```

* Every change request of every superseded submission is listed; the files are
  the latest superseded submission's, digest-checked with `read_verified`.
* M26's refused-attempt block follows when the current round has refused
  attempts; refusals from earlier rounds are stale and are not repeated.
* The review prompt lists earlier change requests too (as context, citable),
  so the reviewer can judge whether they were addressed. It still never shows
  a superseded or refused file.

---

## 4. The limits

```python
Capability(id="rtl.implement", ..., max_attempts=3, max_review_rounds=2)
StageTemplate(id="rtl-implementation", ..., max_attempts=2, max_review_rounds=3)
```

| Field | Where | Default | Means |
|---|---|---|---|
| `max_attempts` | `Capability` (M26), `StageTemplate` (M27, `None` = inherit) | 1 | Tries to pass the before-review checks in one review round |
| `max_review_rounds` | `Capability`, `StageTemplate` (both M27) | 1 | Submissions of the task that may go to review |

Precedence, for each: `run_task(attempts=, review_rounds=)` (the CLI's
`--attempts` and `--review-rounds`), then the task's workflow stage, then its
capability, then 1. `nirmaan.runtime.limits(engine, task, attempts=None,
review_rounds=None)` returns the pair; the stage is found through the task's
`workflow` and `stage`, so the runtime names neither. No shipped capability or
stage sets either, so behaviour
changes only where an organization or an operator asks for repair.

### Counting, across runs

Both counts are read from `state.attempts`, which `nirmaan run` saves:

* **Rounds used** = the task's superseded submissions (attempts with
  `reviews`). Running the owner starts round `used + 1`; that is allowed only
  while `used < max_review_rounds`.
* **Attempts used** = refused attempts numbered after the latest superseded
  submission (this round's). A run may make `max_attempts - used` more.

So `--attempts 3` over two runs is three attempts in all, and the total over a
task is at most `max_attempts x max_review_rounds` model answers that reach
the engine. With `max_attempts` 1 no refused attempt is recorded (M26 law 3),
so each run is one try, exactly as in M23 and M26.

### Exhaustion

| Situation | `run_task` does | Task |
|---|---|---|
| `used rounds >= max_review_rounds` | escalates (technical) through the owner's route; no model call | `escalated` |
| this round has recorded refused attempts, `>= max_attempts` | the same | `escalated` |
| attempts run out within a run | `refused`, as M26 | `in_progress` |

The escalation names every superseded submission and refused attempt, asks
"How should this task proceed?", and offers raising the limit, reassigning,
changing the approach, or cancelling. Resolving it restores the task's status
but not the budget: the limit applies to the total, and the way to allow more
is a higher limit (a flag for one run, or the stage's data).

With the default of one round, running the owner on a task a reviewer sent
back now escalates instead of starting fresh: the review is heard by a manager
rather than silently retried. A human can still start and submit by hand
(`nirmaan task start`, `nirmaan task submit`); the limits bound the runtime,
not the people.

---

## 5. The flow

```
nirmaan run T                       round 1: attempts (M26), submit -> in_review
nirmaan run T --review              reviewer seat: request_changes -> changes_requested,
                                    files superseded into T#t<n>
nirmaan run T                       round 2 (if max_review_rounds >= 2): the prompt carries
                                    the findings and the sent-back files; the new files pass
                                    P9 and go to in_review
nirmaan run T --review              approve -> passed
nirmaan task approve T              approved: only round 2's files are the deliverables
```

Each step is one invocation and one saved state; nothing runs the owner and
the reviewer in an unattended loop.

---

## 6. Audit

* `task.review` with a change request that supersedes: `details.superseded`
  (the `Attempt` ID) and `details.artifacts` (the superseded IDs).
* `task.attempt` (M26) for each refused attempt.
* `escalation.raise` for an exhausted budget, with the reason and the records
  that used it.

---

## 7. Extension points

| To add | Do this | Core changes |
|---|---|---|
| Repair after review for any seat | `max_review_rounds` on its capability or stage, or `--review-rounds` | none |
| A different limit for one workflow's stage | `max_attempts` or `max_review_rounds` on the `StageTemplate` | none |

The crown jewel `test_a_new_stage_gets_review_repair_with_no_core_changes`
adds a units-table capability and a stage with `max_review_rounds=2`, binds its
checker in the test, and has a reviewer send the first table back: the owner is
re-run with the finding, and the second table is approved alone.

---

## 8. Laws, each pinned by a test (`tests/test_nirmaan_review_repair.py`)

1. A reviewer seat requests changes on real, checked RTL; the owner is re-run
   with the review token and comments and the sent-back file in its prompt; the
   new files pass lint and simulation, go to review, and are approved.
2. The superseded artifacts are in the `Attempt`, not in `state.artifacts`;
   the export and the engineering links carry only the second submission.
3. A stage limit overrides the capability's; the CLI overrides the stage.
4. Exhausted review rounds escalate with no model call; so does an exhausted
   attempt budget.
5. The budget persists across separate `nirmaan run` invocations.
6. P6 holds: the owner can never review; the reviewer cannot be the owner.
7. Crown jewel: a new stage gets review repair with no core changes.
8. The runtime names no seat or tool and keeps the import laws; no test reaches
   a model API; real-tool tests use `NIRMAAN_REQUIRE_EDA`.

---

## 9. Deferred

* An unattended owner and reviewer loop (`run`, `review`, `run`, ...) in one
  command. Each step is its own invocation today.
* Resetting a budget when an escalation is resolved. A higher limit is the
  explicit way to allow more.
* File-level signoff (M26's deferral stands): a passing run over a superseded
  file stays on the task as evidence. Review opens only with passing runs over
  the submitted files, so this lets nothing through today.
* `DOCUMENT` evidence and spec requirements that cite a superseded artifact
  keep their records; the requirement coverage report shows the verification
  items in it as unverifiable.

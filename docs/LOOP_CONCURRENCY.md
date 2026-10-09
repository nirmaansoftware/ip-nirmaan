# Concurrent tasks and a project wide call budget (Milestone 36)

Status: design for the owner's review, implemented on branch
`m36/loop-concurrency`. This is post-roadmap work (see `docs/ROADMAP.md`,
"After Stage 6"). Prose here is free of em and en dashes per the standing style
law.

M29 built `nirmaan drive`, the unattended owner and reviewer loop, and deferred
two things (`docs/AUTO_LOOP.md` section 11): running independent tasks
concurrently, and a call budget that persists across invocations. M36 builds
both:

```
nirmaan drive <project> --runtime anthropic --jobs 4             # independent ready tasks at once
nirmaan budget <project> --calls 200 --as <role> --reason "..."  # a person sets the project's budget
nirmaan budget <project>                                         # what is set, and what is spent
nirmaan drive <project> --runtime anthropic --jobs 4 --dry-run   # the waves and the budget impact
```

---

## 1. The laws

Every M29 law holds: the loop holds two seats and only two, never approves,
never crosses a gate, decides each step from state alone, audits and saves
every step, and is bounded per task (M27) and per invocation (`--max-calls`).
M36 adds:

1. **One writer.** Model calls run in parallel; engine work does not. Every
   read and every mutation of project state happens in exactly one thread at a
   time, the thread whose turn it is, and turns go round the batch in plan
   order. The hash chain (P11) and the committed state (P10) are extended by
   one writer, exactly as before.
2. **The result does not depend on `--jobs`.** The same answers to the same
   prompts give the same final state and the same audit chain for any
   `--jobs`. `--jobs` bounds how many model calls are in flight; it never
   changes whose turn it is.
3. **Only independent tasks overlap.** A batch is the set of tasks that are
   actionable now. A task is actionable only when every dependency is
   completed or cancelled, both terminal, so no task in a batch can depend on
   another in it. A task that becomes ready during a batch waits for the next.
4. **The project budget is a person's decision, and it persists.** It is
   recorded on the audit trail by a person (`budget.set`), read back from
   state by every invocation, and spent as M31 records model calls. An agent
   cannot set or raise it.
5. **A budget is never exceeded by a step that starts.** Before a step, its
   worst case is reserved against both budgets, counting what the steps
   already in flight may still spend. A stop for the project budget is
   audited.

---

## 2. The concurrency model

### Batches

In project mode the loop works in batches. A batch is every target, in the
plan's stable dependency order (M29's `order`), that has a seat step to take
and has not stopped in this invocation. Each task in the batch is driven, as
in M29, until it stops. When every task in the batch has stopped, the loop
computes the next batch from state; tasks that became ready (behind a stage
that needs no review) are in it. The loop ends when a batch is empty, or after
a batch in which a task stopped for a budget.

A batch of one (always the case when a TASK is named) runs inline, in the
calling thread, exactly as M29 did.

### Turns

A batch of more than one runs one thread per task, coordinated by a writer
(`nirmaan.runtime.writer`). The writer holds a turn, which starts at the first
task of the batch. A task's thread does engine work only while it holds the
turn. It gives the turn up in two places only:

* **Around a model call.** `ModelRuntime` wraps `llm.complete` in
  `outside_writer()`. Inside the writer, that takes one of `--jobs` call
  slots (while still holding the turn, so calls are issued in turn order),
  passes the turn to the next unfinished task in the batch, makes the call,
  frees the slot, and waits for the turn to come back round.
* **When its task stops.** The thread leaves the batch and passes the turn on.

The turn always passes to the next unfinished task in batch order, cyclically,
and the writer waits for that task even if another is ready sooner. So the
sequence of engine segments is fixed:

```
T1 seg1 | T2 seg1 | T3 seg1 | T1 seg2 | T2 seg2 | T3 seg2 | ...
        ^ T1's model call runs here, while T2 and T3 do engine work and start their own calls
```

A segment is everything a task does between two model calls: assembling the
packet, starting the task, the tools its evidence names (the broker records
each run), rendering the prompt, then, after the answer, writing files,
postflight tools, the submission or review, the M31 call records, the
`loop.step` entry, and the save.

### Why the result does not depend on `--jobs`

* The batch is a function of state, computed between batches.
* The turn order is a function of the batch alone.
* A segment reads state only while it holds the turn, so it sees the state left
  by the segments before it in that fixed order.
* A segment's operations are a function of that state and of the answer to
  the model call that ended the previous segment; the answer is a function of
  the prompt, which the previous segment rendered.

By induction every segment, and so every audit entry and every ID drawn from
a counter (`run-NNNN`, `esc-NNN`, evidence, attempts, model calls), is the
same for any `--jobs`. With `--jobs 1` the call slot is held across the whole
call, so calls happen one at a time, in turn order; with `--jobs 4`, up to four
are in flight. The engine never sees the difference.

One caveat, stated rather than hidden: an LLM whose answer depends on the
order calls arrive in, rather than on the prompt (a single ordered script
shared by several tasks), is only reproducible at `--jobs 1`. Real models,
`MockLLM` without a script, and a script per task are reproducible at any
`--jobs`.

### What runs in parallel, and what does not

| Work | Where | Why |
|---|---|---|
| Model calls (`llm.complete`) | outside the turn, up to `--jobs` at once | they touch no project state |
| Packet assembly, prompt rendering | inside the turn | they read state |
| Tool runs (EDA included) | inside the turn | a binding is handed the engine and may read state (`status.read` does); its run ID comes from a counter |
| File writes (`_attempt_dir`) | inside the turn | the directory is chosen by an exists check; two writers could race for it |
| `on_step` (the CLI's save) | inside the turn | one writer saves a consistent state |

Keeping tools inside the turn removes the shared workdir hazard: an EDA run
uses its own `mkdtemp` directory unless the task names a `workdir`, and two
tasks naming the same one would collide only if their runs overlapped, which
they cannot. Running tools in parallel is deferred (section 7).

### Runtimes

A seat's runtime is shallow copied per task in a concurrent batch, so per call
state a runtime rebinds on itself (`ModelRuntime` sets `_calls` and
`_purpose` at the start of every call) is private to its task, while anything
it shares by reference (the LLM, a test's call log) stays shared. A runtime
that never calls `outside_writer()` (`ScriptedRuntime`, a test's runtime)
simply never gives the turn up between its own segments: its tasks run one
after another, correctly, with no overlap.

### Errors and interruption

A step the engine refuses outright raises, as in M29. In a batch, the error is
raised in its own task's turn. Every other task finishes the step it is in, so
a model call already made is recorded (M31: every call counted), then stops
at its next step boundary. The loop then raises the first error in batch
order. Ctrl-C does the same: the threads finish their steps, then the
interrupt is raised.

Saving after every step means the saved state is always one the writer
produced between segments. A task interrupted mid-step is `in_progress` or in
review, which the next run continues (M29 section 6). Up to one step per task
in the batch may be redone, never double counted: the per task limits and the
project budget are read from state.

---

## 3. The project budget

### Setting it

```
nirmaan budget PROJECT --calls N [--cost-usd X] --as ROLE --reason TEXT
nirmaan budget PROJECT --clear --as ROLE --reason TEXT
nirmaan budget PROJECT                      # show the budget and the spend
```

`TaskEngine.set_budget(actor, calls, cost_usd, reason)` records a `budget.set`
audit entry on the project: the actor (who must be a person), the reason, the
new limits, and the previous ones. Nothing else changes. Setting, raising,
lowering, and clearing are the same decision, each recorded. A limit the
command does not name keeps its previous value. An agent calling it is
refused (`AuthorityError`), and nothing is recorded.

The budget lives on the audit trail rather than in a new field, for three
reasons: it is already persisted in project state; it is hash chained, so
raising the budget by editing the file breaks P11 and is detected; and it says
who decided and why. `nirmaan.work.budget.budget(state)` reads the latest
`budget.set` entry.

### Spending it

Spend is M31's accounting, read from state: the number of recorded
`ModelCall`s, and the sum of their known costs. Every model call a seat makes
is recorded, from any command (`nirmaan run`, `drive`, `eval`), so the budget is
project wide, not loop wide. A runtime that calls no model (a scripted one)
spends nothing.

| Limit | Before a step |
|---|---|
| `calls` | the step's worst case (M29) must fit in `calls` minus the recorded calls minus what in flight steps may still make |
| `cost_usd` | the recorded known cost must be below the limit, and no recorded call may be of unknown cost |

A step's worst case is counted in runtime answers, and a `ModelRuntime`
answer is at most one model call (the `auto` runtime, M31, included), so the
calls limit is never exceeded. Cost cannot be known before a call, so the cost
limit stops new steps once it is reached; steps already in flight may finish,
and the overshoot is at most their calls. A call of unknown cost is never
treated as free (M31): with a cost limit set, it stops the loop until a person
sets a calls limit or clears the cost one.

### Stopping

When a step's worst case does not fit the project budget, the task stops with
`project_budget`, and the loop records a `loop.stop` entry on the task, as the
seat that would have acted, with the limit, the spend, and the worst case.
The loop then starts no new batch. `--max-calls` still bounds one invocation
and stops with `budget`, as in M29, unaudited.

### Resuming

The budget and the spend are both read from state, so a later invocation, or
one after a crash, continues from what is left. A person raises the budget
with `nirmaan budget`, which is audited, and the next `drive` continues.

---

## 4. Dry run

`--dry-run` prints, as before, the worst case sequence of calls for each task
actionable now, then the concurrency and the budget impact, and changes
nothing:

```
$ nirmaan drive prj-1 --runtime mock-llm --jobs 4 --dry-run
plan for prj-1:a
  1. owner ... on mock-llm: round 1 of 1, up to 1 call
  ...
concurrently: prj-1:a, prj-1:b, prj-1:c (up to 4 calls in flight)
worst case: 6 calls, budget 20
project budget: 2 of 5 calls spent, 3 left; the worst case does not fit, so the loop stops when it is spent
```

`plan_loop(..., jobs=N)` returns the same as data: `plan.concurrent` (the
tasks of the first batch), `plan.project_budget`, and `plan.spent`.

---

## 5. The API

```python
from nirmaan.runtime import Stop, loop, plan_loop
from nirmaan.work.budget import budget, spend

engine.set_budget(person, calls=200, cost_usd=None, reason="phase 1 allowance")
report = loop(engine, owner, reviewer, max_calls=40, jobs=4, on_step=save)
report.stops      # {task: Stop}; Stop.PROJECT_BUDGET when the project budget stopped it
```

`nirmaan.runtime.writer` holds the writer: `together(bodies, jobs)` runs
callables under one writer and returns their results in order, and
`outside_writer()` is the context a runtime puts around a call that touches no
project state. Neither names a seat, stage, or tool.

---

## 6. Laws, each pinned by a test (`tests/test_nirmaan_loop_concurrency.py`)

1. With `--jobs 1` and `--jobs 4`, the final state and the audit chain are
   identical, tool runs and model call records included.
2. Independent tasks overlap: an instrumented model sees more than one call in
   flight at `--jobs 4`, and never more than one at `--jobs 1`.
3. Dependent tasks never overlap: a task behind another starts its first call
   after the other's last call ended.
4. The project budget persists across invocations and stops the loop, with a
   `loop.stop` entry; it is never exceeded.
5. Setting and raising the budget is audited as a person's decision; an agent
   is refused.
6. An interruption mid-batch loses no recorded call, and the next run finishes
   from the saved state with nothing double counted.
7. Human gates are never crossed, and no decision a person makes appears in
   the loop's entries, at any `--jobs`.
8. `--dry-run` shows the concurrent batch and the budget impact, calls
   nothing, and saves nothing.
9. Crown jewel: a new workflow of independent stages, added as data in the
   test, is driven concurrently and deterministically with no core changes.
10. The writer names nothing and keeps the import laws.

---

## 7. Deferred

* **Tool runs in parallel.** Tools run inside the turn. Running a binding
  outside it is safe only for a binding that does not read the engine, and
  would need the binding to declare that, and each run to have its own
  workdir. The run would still be recorded inside the turn.
* **Prefetching across steps.** A task's next model call is made only when
  its turn has produced the prompt; the loop does not speculate.
* **Authority over spend.** Any role, acting as a person, may set the budget.
  Tying it to the authority matrix (who may approve how much) is a data change
  for later.
* **A cost limit checked before the call.** Cost is known only after a call;
  the cost limit stops new steps once reached.

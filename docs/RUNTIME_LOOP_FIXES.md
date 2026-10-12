# Runtime and loop fixes (Milestone 52)

Status: implemented on branch `m52/runtime-loop-fixes`. Prose here is free of
em and en dashes per the standing style law.

Two audits of v1.24.0 found that the unattended loop (`nirmaan drive`, M29)
and the runtime under it (`run_task`, M20, M26, M27) could spin, abort, or let
one submission's evidence back another. This milestone fixes them in the
engine and the runtime, so the CLI, the MCP server, and the loop all get the
same behavior. Tests: `tests/test_nirmaan_runtime_loop_fixes.py`, one per
finding, written first and failing on main.

---

## 1. A runtime's submission is final (audit A C1)

**What was wrong.** `submit` on a task with no review completes the task only
if every evidence requirement is met; otherwise it left the task
`in_progress`, with the new artifacts on it. The loop read `submitted` as
progress, `next_step` saw `in_progress`, and the owner was asked again. Nothing
counted it, so no limit fired: the probe made 20 model calls, 20 failed runs,
and 20 artifacts, then stopped only on the call budget. Real stages hit it:
`rtl-lint`, `synthesis`, `power-analysis`, `infra-fix`.

**Decision.** `TaskEngine.submit(..., final=True)` says nothing will be
recorded after this submission. For a task with no review a final submission
is its completion, so the P9 check `evidence-before-review` requires every
applicable requirement to be met by it, and refuses it otherwise
(`... cannot complete on this submission: 'Lint run' is not met`). The model
runtime always submits with `final=True`: it records every run (preflight and
postflight) before it submits.

A refused final submission takes the M26 path, unchanged: the refusal is an
`Attempt` under the M48 `Limits.attempts`, the seat is asked again while the
limit allows, and the next run escalates when it is spent. Nothing is appended
to the task, so a submission can no longer grow silently.

**Why not refuse every unmet submission.** A person (or an MCP agent acting
step by step) may submit first and record the evidence after; the engine
completes the task when the last requirement is met (`record_evidence`). That
two-step flow is legitimate and the test helpers use it. `final` keeps it and
removes the ambiguity only where nothing can follow.

The loop also stops (`refused`) if an owner step reports `submitted` and the
task is still in progress. With the engine rule this cannot happen for the
model runtime; it bounds any other runtime the same way.

## 2. Every refusal is an attempt, with any limit

M26 recorded no `Attempt` when the limit was 1, so `exhausted` never fired at
that limit, the loop stopped with `refused`, and each later `drive` asked the
model once more, forever. Now every refused submission is recorded, whatever
the limit. With the default limit of 1 the run is still one model call; the
difference is that the next owner step escalates (`1 of 1 attempts were
refused`) with no model call. This is the M27 rule (the counts live in state
and cover every run) without its one exception. M26 law 3 changes accordingly:
with a limit of 1 there is one call and one `Attempt`.

## 3. A bad answer is a refused attempt, never an abort (audit A H2)

`_apply` used to enforce the `runtime.result` checks (P3 uncertainty, P4 an
artifact for a claimed completion) and record evidence for declared runs (P5)
by raising. One answer with no uncertainty, with every artifact dropped by
grounding, or naming a run that never happened, stopped the whole `drive`
batch.

Now the runs that did happen are recorded first, then every violation (the
`runtime.result` checks and P5 for each declared run) is collected and the
result is refused, with the constitution's own messages as the refusal. It is
an attempt like any refused submission: the limits decide whether the seat is
asked again or the task escalates. A declared run that never happened is left
out of the attempt's runs.

**The CLI saves before it reports an error.** `nirmaan drive` saves the
project when a step raises (an engine refusal that is still an error, such as
P8 on an unapproved input), if the step changed anything; `nirmaan run` saves
before it reports one. The model calls and the `task.start` of the failed step
are kept, so the spend that M31 and M36 count is never lost.

**The first stage can ground its answer.** The first stage of a workflow had
nothing to cite, so any real model's artifact was dropped as uncited. Every
work and review prompt now declares the project requirement as a citation,
`[requirement:<requirement ID>]`, labeled with its text: it is the record
every task traces to (P1). Citing it grounds an artifact in the request; it is
not evidence and satisfies no requirement.

## 4. The mock runtime drives a fresh project (audit C H3)

`MockLLM` cites the prompt's runs and records first; when nothing else is
citable it cites the requirement. On a fresh project the requirements task's
owner now submits an artifact grounded in the requirement, and the reviewer,
which approves only when it has a declared record to cite, approves citing it.
`drive --runtime mock-llm` therefore does what `--dry-run` shows: owner,
reviewer, then a stop for a person's approval. A stage whose checks need real
files (RTL) still ends honestly: the mock writes no RTL, P9 refuses it, and the
task escalates.

## 5. Evidence is bound to the submission it was recorded for (M50 deferral)

M50 moved a sent-back submission's evidence onto its `Attempt`. A refused M26
attempt's evidence still stayed on the task, so a passing run from a refused
attempt could satisfy a later attempt with no file binding.

**Design.** An evidence record belongs to exactly one submission: the task's
current one (`Task.evidence`) or an earlier one (`Attempt.evidence`). Binding
is by where the ID lives, the same structure M27 and M50 use for artifacts and
sent-back evidence, so no reader needs a filter:

1. `record_attempt` moves the attempt's own evidence (the IDs it is given) off
   the task, onto the attempt. Evidence recorded outside the attempt, by a
   person, stays.
2. A tool run bound to an earlier submission (listed in any `Attempt` of the
   task) backs nothing again: evidence recorded for it later is
   unsubstantiated. A model cannot revive an old passing run by naming it.
3. Requirements (`unsatisfied_requirements`, P9, signoff, verification) read
   only `Task.evidence`, so they count only the current submission's evidence.

**The repair prompt still cites the failed run.** The prompt declares each
refused attempt's failed runs and their evidence as citations, read from the
attempt (`AttemptView.failed_runs`). The repair section renders them with
their tokens and log excerpts as before. They are citable; they satisfy
nothing.

## 6. A person's resolution grants a fresh budget (audit A M5)

After a person resolved a "repair budget exhausted" escalation, the very next
run escalated again: `exhausted` read only the `Attempt` records, which the
resolution does not change.

**Decision: the resolution grants a fresh budget.** The escalation's own first
option is "Allow more attempts or review rounds", and resolving it is the
recorded human decision to go on. Requiring a raised limit flag on every later
command made that decision inert. So the limits count only the submissions
made after the latest such resolution: `_spent` skips every attempt that
existed when a person resolved an escalation whose reason begins
`repair budget exhausted`. The grant is read from the audit trail (the
resolve entry, its actor kind, and the attempt and supersede entries before
it), so it needs no new state and is itself the record.

Only a person grants. An AI agent in the target seat may still resolve the
escalation, but its resolution grants nothing, so no agent can buy itself
unlimited attempts. Each resolution grants one budget; when that is spent the
task escalates again.

## 7. Old bounds only in old data (audit A M6)

The pre-M48 conversion (a fixed `max_<metric>` or `min_<metric>` parameter
becomes a `Bound`) ran in the `EvidenceRequirement` validator, so it rewrote
data built today: `dft.scan_insert`'s real `max_chain_length` input became a
bound. The conversion now runs only in the store, for a file with
`schema_version` "1" (written before M51 sealing), and only for a requirement
with no `bounds` key (every requirement saved after M48 has one).
`nirmaan.models.workflow.legacy_requirement` is the one function.

## 8. Smaller fixes

- **M4, `inputs` clauses.** `run_facts` (policy) and the runtime's `_facts`
  now supply `inputs`: the kinds of the approved, located upstream artifacts.
  A requirement conditioned on an approved input applies only when one is
  available, as UNIFIED_APPLICABILITY.md 2.2 says and the prompt tells the
  seat.
- **L1, registry reads.** `Registry.items()` and `values()` read a snapshot of
  each layer under its lock, so a reader never meets a key removed between
  reading the keys and the values.
- **L4, preflight.** One run per distinct tool, fixed parameters, and bounds,
  the key postflight uses.
- **L5, upstream evidence.** The packet's upstream evidence is the evidence of
  the tasks whose artifacts `upstream_artifacts()` returns, so a task behind a
  gate sees the gated stage's evidence.
- **Gate overrides.** `nirmaan plan --auto-gate` and MCP `plan_project`'s
  `auto_gates` are removed. Since M50 every gate is a person's, so they could
  not do what they said. `--human-gate` and `human_gates` remain: they mark a
  gate human-required in the plan, which is shown and recorded. The Python
  API's `gate_overrides` still accepts False, which makes nothing stricter.

## 9. Flows that changed

| Flow | Before | Now |
|---|---|---|
| A limit of 1, a refused submission | `refused`, no `Attempt`; each `drive` asks again | `refused`, one `Attempt`; the next owner step escalates with no call |
| A review-less task whose evidence the answer does not meet | `submitted`, task left in progress, asked again until the budget is gone | `refused` attempt; escalates when the limit is spent |
| A model answer with no uncertainty, nothing grounded, or an invented run | raises, the batch stops, the CLI saves nothing | `refused` attempt with the constitution's reason |
| A spent budget resolved by a person | the next run escalates again | one fresh budget |
| `drive --runtime mock-llm` on a fresh project | escalates at step 1 | owner, reviewer, stop for approval |

## 10. Deferred

- The audit A findings outside this milestone (L3, L6, the documentation
  contradictions not named above) are unchanged.
- A per-file signoff (M26's deferral) is unchanged: binding evidence to the
  submission closes the cross-attempt hole, not a check that every passing run
  covered every submitted file for requirements with no file binding.
- The Python API's `gate_overrides=False` is kept for callers that pass it.

# Engineering records: decisions and failures (M29)

The third milestone of the structural review
(`docs/architecture/target-state.md` section 5). Two questions a long-running engineering
organization must answer from its records, not from memory:

- **Why did we choose this?** (a decision record: question, context,
  alternatives, choice, rationale, evidence, who, when, consequences)
- **What went wrong, how often, and was it fixed?** (a failure record: where,
  what kind, what it touched, what backs it, whether it was resolved)

## What the inspection found

The review planned to add fields to `Decision` and a category to failures.
Reading the code after M27 changed that:

- **Nothing records a `Decision`.** `TaskEngine.record_decision` exists and is
  tested, but no CLI command, MCP tool, or runtime calls it. The decisions the
  organization actually makes are **decision tasks** (`TaskKind.DECISION`, such
  as `root-cause` in the regression workflow): their `outcomes` are the
  alternatives, the recorded `outcome` is the choice, their artifacts carry the
  written rationale, their evidence backs it, the audit trail says who
  submitted and approved it and when, and `_take_branch` cancels every branch
  not taken with an audit entry naming the decision. Every field of an
  architecture decision record is already recorded; nothing presents it.
- **Failures are already recorded as structure.** A failed check is a
  `ToolRun` with `succeeded=False`; a refused or sent-back submission is an
  `Attempt` (M26, and M27's review repair); blocks and failures are audit
  entries with reasons; escalations are records. What is missing is one place
  that reads them as failures, classifies them, and says whether each was
  resolved.
- **Artifact supersession** is already done by M27's review repair: a
  sent-back submission's artifacts move into an `Attempt`, out of
  `state.artifacts`. M29 adds nothing there.

So M29 adds **views over recorded state**, like `nirmaan gaps` and the export:
no new stored fields, no schema change, no state change, no audit entry.

## Decision records

`nirmaan.records.decision_records(state)` returns one `DecisionRecord` per
decision task and per recorded `Decision`, sorted by ID:

| Field | From a decision task | From a recorded `Decision` |
|---|---|---|
| question, context | task title and description | the statement |
| alternatives | the task's declared `outcomes` | none recorded |
| chosen | the recorded `outcome` (None while open) | the statement |
| rationale | the summaries of the task's artifacts | `rationale` |
| evidence | the task's evidence: ID, kind, substantiated | the cited evidence |
| decided by, at | the `task.submit` audit entry that recorded the outcome | the `decision.record` entry |
| approved by | the `task.approve` audit entry, if any | none |
| consequences | every `task.cancel` audit entry for a branch not taken | none recorded |
| status | the task's status | `recorded` |

Nothing is inferred: a field with no record behind it is empty, never filled
by guessing.

## Failure records

`nirmaan.records.failure_records(state)` returns one `FailureRecord` per
recorded failure, in audit order. Categories (`FailureCategory`):

| Category | Source | Subject | Resolved when |
|---|---|---|---|
| `check_failed` | a `ToolRun` with `succeeded=False` | the tool | a later run of the same tool on the same task succeeded |
| `review_sent_back` | an `Attempt` with reviews | the reviewers | the task later passed review |
| `submission_refused` | an `Attempt` refused with no failed run of its own | none | the task later reached review |
| `blocked` | a `task.block` audit entry | none | the task is no longer blocked |
| `failed` | a `task.fail` audit entry | none | the task later completed |
| `escalated` | an `Escalation` | its kind | it is resolved |

Each record carries the task, its stage, the attempt, the run and evidence
IDs, a summary taken from the record (the run's summary, the refusal, the
reason), and, when resolved, what resolved it. A root cause is not guessed:
it appears only where a person or a decision recorded one (an escalation's
resolution, a decision task's outcome).

`failure_summary(states)` counts failures across projects by category and
subject (for example `check_failed lint.run: 7 in 3 projects, 6 resolved`),
the raw material for the learning proposals of a later milestone.

## Surfaces

- `nirmaan decisions PROJECT [--json]` and `nirmaan failures PROJECT... [--json]`
  (several projects add the cross-project summary).
- Export: two new sections, `decisions` in `10_signoff` and `failures` in
  `09_evidence`, through the existing section-writer registry and folder table
  (data). Output stays sorted, so a state and its reloaded copy export
  byte-identically.
- MCP: read tools `decisions` and `failures` in the Nirmaan table, so an agent
  can ask why a choice was made before revisiting it.

## Tests (`tests/test_nirmaan_records.py`)

- The regression workflow's `root-cause` decision, driven to `rtl_bug`, is a
  record with its four alternatives, the choice, the rationale, the evidence,
  who and when, and the three cancelled branches as consequences; an open
  decision lists no choice; a recorded `Decision` appears too.
- A failed platform tool run on a task is `check_failed`, then resolved by a
  later successful run of the same tool; a sent-back review, a block, a
  failure, and an escalation each appear with the right category and
  resolution.
- The cross-project summary counts by category and subject.
- The views are reads: state and audit are unchanged.
- Export carries both sections, and a reloaded state exports byte-identically.
- CLI and MCP return the same records as the functions.
- `records.py` names no stage, tool, artifact kind, or role.
- Crown jewel `test_a_new_decision_stage_is_recorded_with_no_core_changes`: an
  extension workflow's decision stage with branches appears with its
  alternatives and consequences.

## Not in M29

Recording richer explicit decisions (no caller exists yet), declined model
answers (the engine records nothing for them, so a view cannot report them),
principle IDs on refusals, and learning from the summary.

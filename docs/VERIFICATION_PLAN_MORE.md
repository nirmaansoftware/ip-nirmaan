# Verification plans on `new-ip` and `feature-addition`, and amending a recorded plan (M38)

Status: implemented on branch `m38/vplan-more`. This document was written
before the code and records the decisions the code follows. Prose here is free
of em and en dashes per the standing style law.

M29 (`docs/VERIFICATION_PLAN.md`) gave a project one way to get a checked plan
from a seat (the `block-design` `dv-plan` stage, on request) and one way to
load one from a file (`nirmaan vplan import`). It deferred three things this
milestone closes:

1. **The plan seat on `new-ip` and `feature-addition`.** Their `dv-plan`
   stages wrote plans as plain documents, which recorded nothing.
2. **Amending a recorded plan.** A second plan that repeated an ID was
   refused, and nothing could be withdrawn.
3. **Planned items in an import.** An imported item had to name a file that
   was already recorded.

None of this ever makes a requirement backed. A plan, an amendment, and a
retirement are declarations; only a passing, cited, substantiated run over the
file that holds an item backs anything (M24).

---

## 1. The plan seat on `new-ip` and `feature-addition`

### Decision: the existing stage becomes a checked plan

Two choices were open: make the existing `dv-plan` stage a checked plan, or
add a second, checked stage beside it. A second stage would leave two plans in
one project, one checked and one not, and every downstream stage (`dv-environment`,
`vip`, `assertions`, `tests`) would still be waiting on the unchecked one. So
the existing stage becomes the checked one, on every request, not only when
the request asks for a plan as on `block-design`: on these two workflows the
plan is a deliverable of the lifecycle, and an unchecked deliverable is the
weaker thing.

| Workflow | Stage | Before | After (M38) |
|---|---|---|---|
| `new-ip` | `dv-plan` | review only; the plan is a document | review, and before review `vplan.check` over the plan (`plan`) and the approved upstream `requirements_spec` (`spec`, `upstream=True`) |
| `feature-addition` | `dv-plan` | review only; depends on `microarchitecture` | the same check; it also depends on `requirements-delta` directly, so the approved requirements spec is an upstream input. That stage is already complete before `microarchitecture` starts, so no task waits longer |

The check is one shared data value, `PLAN_CHECKED` in
`company/workflows.py`. The spec it checks against is the approved
requirements specification: on these workflows that is where the requirements
are stated, as the interface spec is on `block-design`. Because the stage now
checks its plan with `vplan.check`, the M29 approval consumer records it on
approval with no change (it acts on exactly the plans whose stage checks
them). The stage's requirements, capability, output, and downstream edges are
otherwise unchanged.

### What a seat must now write

The requirements seat must tag each requirement (`[req:ID]`, M29 section 3),
and the plan seat must write a `nirmaan.vplan` file that covers exactly those
tags, quoting each. A plan seat that writes prose, or a plan that misses a
tagged requirement, is refused before review, with the check's reasons, as on
`block-design`.

### Migrations

Making the stage checked changes what every existing flow through it must
produce. Each existing plan and test is migrated, never weakened; the list is
section 6.

## 2. Amending a recorded plan

### The model: one current plan per project, revisions per record, history on the audit trail

A project has one recorded plan: its active requirements and items. A **plan
version** is a whole plan file. A later version is an **amendment**: compared
with what is recorded, each requirement and item in it is

| In the new version | Recorded and active | Result |
|---|---|---|
| present | no | **added** (revision 1) |
| present, every field the same | yes | **kept** (nothing recorded) |
| present, any field different | yes | **modified** (revision + 1) |
| listed under `retired`, with a reason | yes | **retired** (revision + 1, kept, with the reason) |
| absent, not listed under `retired` | yes | **refused**: a version must account for every active record |

The fields compared are, for a requirement, its text, its source artifact,
and its section; for an item, its kind, name, file (or bound artifact),
proves, and rationale.

**History is kept, never deleted.** `SpecRequirement` and `VerificationItem`
gain two fields: `revision` (1 when first recorded) and `retired` (empty, or
the reason it was retired). A modified or retired record replaces the current
one in state; the version it replaces is written, whole, into the audit entry
that replaced it (`details["previous"]`), and the hash-chained audit is never
rewritten. A retired record stays in state, marked. `vplan.history(state, id)`
returns every version of a record, oldest first, read from the audit entries.

**Rules an amendment cannot break:**

- An ID is never reused: a retired requirement or item cannot be added again
  (choose a new ID).
- An active item proves only active requirements. Retiring a requirement that
  an active item still proves is refused, unless the same version modifies or
  retires that item.
- A retirement needs a reason: a `retired` entry without a non-empty
  `reason` is refused at its line, and the engine refuses an empty reason too.
- Retiring a requirement that has passing evidence is allowed, with its
  reason; its audit entry also records the passing runs that backed it at that
  moment (`details["backed_by"]`), so the retirement of backed work is visible,
  not quiet.

**`nirmaan gaps` uses the current version.** Coverage, gaps, the engineering
graph, and the export read only active records. A retired requirement is not a
gap and is not counted; a retired item proves nothing.

### The format: an optional `retired` list

Version 1 gains one optional top-level field:

```json
"retired": [
  {"requirement": "AXIL-B2B", "reason": "Back-to-back acceptance moved to the next revision of the spec."},
  {"item": "cov-b2b", "reason": "Its requirement is retired."}
]
```

Each entry names exactly one `requirement` or `item`, and a non-empty
`reason`; IDs are unique within the list, and an entry cannot name a record
the same file keeps. The version number stays 1: no file valid before means
anything different now, and a reader older than M38 refuses a file that uses
`retired` (it refuses every unknown field), so nothing is silently misread.
Export writes the current version (active records only); a project's
retirements are in its state and audit, not in the next plan.

### Every amendment goes through the same check and the same approval as a plan

**From a seat.** A plan seat's file is checked by `vplan.check` before review.
The check now also takes the project's recorded plan into account (the tool
binding is handed the engine): a version that drops an active record without
retiring it, retires something not active, or reuses a retired ID fails
before review, with its reasons. On approval the M29 consumer re-runs every
check against the digest-checked bytes and then records the difference
(additions, modifications, retirements) as the system actor, with the plan
named in each audit entry. A plan with nothing recorded yet is simply all
additions, so every M29 flow is unchanged. A plan that repeats an ID with the
same content no longer refuses; it keeps the record.

**From a file.** `nirmaan vplan import PROJECT FILE --as ROLE --amend`
(Python: `vplan.amend_plan(engine, actor, text)`): the same reader, the same
reference resolution, and every record made through the engine as the
importing actor, first on a scratch engine, so a refused amendment records
nothing. An import has no approval step (M29: the actor rule on each record
is its authority), and an amendment keeps that rule: an actor may amend or
retire a record only if they may record it.

**The spec check on import.** For each requirement source that is a recorded,
digest-checked file that tags at least one requirement, the import (plain or
`--amend`) runs the seat's check for that spec: the file must cover every
requirement the spec tags and quote each. So "an amendment that misses a spec
requirement is refused" holds on both paths. A source with no file, or a file
that tags nothing, is not checked, exactly as before.

A plain import is unchanged: it adds, and refuses any ID already recorded. It
refuses a `retired` list ("use --amend").

## 3. Planned items in an import

M29 refused an imported item whose file was not yet recorded, because an
item planned before its file exists must be attributed to an artifact. M38
attributes it to the specification its requirements are quoted from:

- An item's `file` that resolves to a recorded artifact binds to it now, as
  before.
- A plain file name that no recorded artifact has becomes a **planned item**
  (`TaskEngine.record_planned_item`), exactly as the seat records one: it
  names the file and is bound, on every query, to the latest recorded
  artifact of that name. Its `plan` is the source artifact of the first
  requirement it proves, and the M24 actor rule applies to that artifact's
  task, so the importer must own, review, or manage the work that produced the
  spec.
- That source must be a recorded file (as the seat's plan must be); a file
  name with a directory, a name that matches several artifacts, or a planned
  item whose spec has no file is refused at its line.

## 4. Extension points

| To add | Do this | Core changes |
|---|---|---|
| A checked plan stage on another workflow | a stage with capability `dv.plan` and a `vplan.check` requirement (or `PLAN_CHECKED`) | none |
| A re-plan stage that amends the recorded plan | a later stage with the same check; its approved plan is an amendment | none |
| A new item kind an amendment may use | `register_item_kind` (M24) | none |

The crown-jewel test adds, by org extension, a workflow with a plan stage and
a later re-plan stage against an amended spec, with a newly registered item
kind: the second plan adds and retires records through the check and the
approval with zero core changes.

## 5. Laws, each pinned by a test (`tests/test_nirmaan_verification_plan_more.py`)

1. A `new-ip` plan is checked before review, recorded on approval, and feeds
   `nirmaan gaps` (requirements from the requirements spec, items bound to
   the RTL seat's testbench and backed by the real simulation).
2. Old flows are migrated without weakening them: a prose plan on `new-ip` or
   `feature-addition` is now refused before review, and the migrated flows
   reach the same states as before, with the plan recorded.
3. An amendment adds, modifies, and retires items and requirements; the
   superseded versions stay on the audit trail; `gaps` reads the current one.
4. An amendment that misses a spec requirement is refused, on the seat and on
   import, and records nothing.
5. Retiring needs a reason; retiring a backed requirement is allowed and
   records what backed it.
6. An import with planned items records them as the seat would, and they bind
   once the file is recorded.
7. Crown jewel: a re-plan stage on a new workflow needs no core change.
8. Import laws: `nirmaan.vplan` never imports VeriTriage; the runtime, the
   engine, the policy, and the orchestrator name no plan kind, stage, or tool.
9. Contract scan: `vplan.check` keeps its declared contract and status.
10. No model API is called.

## 6. Migrations

Every flow through the changed stages, and every behavior an existing caller
could see change, with what replaced it. None is weakened: each now passes a
real check it did not have, or refuses something it used to accept.

| # | What | Before | After |
|---|---|---|---|
| 1 | `new-ip` `dv-plan` (`company/workflows.py`) | review only | review, and `PLAN_CHECKED` before review |
| 2 | `feature-addition` `dv-plan` | review only; depends on `microarchitecture` | `PLAN_CHECKED`; also depends on `requirements-delta` (no task waits longer) |
| 3 | `drive` (`tests/nirmaan_helpers.py`), every requirements stage | an artifact with no file | a real file, `tests/fixtures/vplan/requirements_spec.md` (three tagged requirements of the counter), with its digest |
| 4 | `drive`, a gated `verification_plan` | not producible: `drive` raised | the real plan file `tests/fixtures/vplan/verification_plan.json` (its item lives in `counter_tb.v`, the testbench `drive` writes), with its digest, checked for real |
| 5 | `drive`, before-review checks | only the task's own files were bound; `workdir` passed to every tool | `upstream=True` bindings are filled from the approved upstream files, as the runtime fills them; `workdir` only to a tool whose contract takes it (an in-process check takes none). `GATED_FILES` paths are now relative to `tests/fixtures/` |
| 6 | `tests/test_nirmaan_export.py` `midway` | a hand-written Markdown plan, submitted with no check | the plan file, through `gated_submit`, after a real passing `vplan.check`; the sidecar test reads the copied plan file's first line |
| 7 | `tests/test_nirmaan_work.py` whole-project drive of `new-ip` | completed with a document plan | unchanged test; it now completes with the plan checked for real and recorded on approval (3 requirements, 1 planned item) |
| 8 | The M29 approval consumer | refused a plan repeating a recorded ID | a later plan is the next version: a repeated ID with the same content is kept, a different one is modified, a dropped one must be retired |
| 9 | `vplan.check` | file and spec rules only | also the amendment rules against the project's recorded plan |
| 10 | `nirmaan vplan import` | an item in an unrecorded file was refused | it is planned, when its spec is a recorded file; otherwise refused at its line, as before. A recorded, tagged source spec must be covered exactly. A `retired` list is refused ("use --amend") |
| 11 | `requirement_coverage`, `engineering_graph`, `export_plan`, `nirmaan gaps` | every record | active records only; retired ones are history |
| 12 | `TaskEngine` new-item checks | an item could prove any recorded requirement | not a retired one |

M29's demo and tests run unchanged: the `block-design` plan stage has nothing
recorded before it, so its plan is all additions.

## 7. Deferred

- A YAML or spreadsheet reader for the same format (from M29).
- Requirement tags in other spec formats than Markdown (from M29).
- Re-planning inside one stage after approval: an approved task is complete,
  so a new plan version comes from a later stage or from `--amend`. A
  reopen-and-replan action on a completed plan task is not built.
- Several independent plans in one project (one per spec): a project has one
  recorded plan, and a version must account for every active record.
- Reinstating a retired ID; a new ID is required.
- A CLI view of a record's history (`vplan.history` is Python only).

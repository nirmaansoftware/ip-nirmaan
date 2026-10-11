# Verification plans: loaded from a file, and written by a seat (M29)

Status: implemented on branch `m29/vplan`. This document was written before
the code and records the decisions the code follows. Prose here is free of em
and en dashes per the standing style law.

M24 made one question answerable: which requirements are not yet backed by
passing verification evidence? But every requirement and every verification
item had to be recorded one Python call at a time, and its demo did exactly
that, by hand, in a test. M29 adds the two ways a real team gets them in:

1. **A file.** A small, versioned JSON format for a verification plan:
   requirements with IDs, text, and source, and the items that prove them.
   `nirmaan vplan import` records one through the task engine; `nirmaan vplan
   export` writes the project's plan back out in the same format.
2. **A seat.** A verification-plan stage on `block-design`, after the
   interface spec. Its seat reads the approved spec and writes a plan file; a
   real check validates the file against the format and the approved spec
   before review; on approval, the plan is recorded into the engineering
   graph, and `nirmaan gaps` answers from it.

Neither ever makes anything backed. A plan is a declaration of intent: only a
passing, cited, substantiated run over the file that holds an item does that,
exactly as in M24.

---

## 1. The format, version 1

```json
{
  "format": "nirmaan.vplan",
  "version": 1,
  "requirements": [
    {"id": "AXIL-SLVERR", "text": "...", "source": "interface_spec.md", "section": "5"}
  ],
  "items": [
    {"id": "tb-slverr", "kind": "test", "file": "axi4_lite_regs_tb.v",
     "name": "unmapped write SLVERR", "proves": ["AXIL-SLVERR"], "rationale": "..."}
  ]
}
```

| Field | Rule |
|---|---|
| `format` | Exactly `nirmaan.vplan`. |
| `version` | Exactly `1`. A later version is a new reader, never a silent guess. |
| `requirements` | A list, required. Each has `id` (a letter, then letters, digits, `_`, `.`, `-`), `text` (non-empty), `source` (non-empty), and optional `section`. |
| `items` | A list, optional. Each has `id`, `kind`, `file`, `name` (all non-empty), `proves` (a non-empty list of requirement IDs in this file), and optional `rationale`. |
| `kind` | A registered verification-item kind (`test`, `assertion`, `coverage_point`, or one added with `register_item_kind`). |
| Anything else | Refused. In particular a plan cannot say `status`, `backed`, `passed`, or `run`: an import declares, it never records a result. |

Requirement and item IDs are unique within the file. JSON was chosen over
YAML because the repository has no YAML dependency and adding one for a file
this small is not worth it.

**Line-level reasons.** The reader records the line on which every object
starts, so each problem is reported as `line N: ...`: a JSON syntax error at
its line, a missing or unknown field at its object's line.

**References.** `source` and `file` name a recorded artifact: its ID, its
recorded path, or the file name of exactly one recorded artifact's path. A
name that matches nothing, or more than one artifact, is refused with the
candidates.

**Export** writes the same format, requirements and items sorted by ID, with
`indent=2`. A reference is written as the file name when that name is unique
among recorded artifacts, else as the artifact ID, so importing an export
into the same project state gives the same records, and exporting a file that
was imported gives the file back (in canonical form).

## 2. Import: through the engine, all or nothing

`nirmaan vplan import PROJECT FILE --as ROLE [--agent]` (Python:
`nirmaan.vplan.import_plan(engine, actor, text)`).

1. The file is read and validated against the format. Any problem refuses the
   whole file.
2. Every reference is resolved against the project. Any unresolved one refuses
   the whole file.
3. The records are made, in order, on a **scratch engine** built from the
   current state: every requirement through `TaskEngine.record_spec_requirement`
   and every item through `TaskEngine.record_verification_item`, so the M24
   actor rule (own, review, or manage the task that produced the artifact),
   the duplicate checks, and the constitution all apply. Every refusal is
   collected with the line of the record it came from.
4. Only when the scratch run raised nothing are the same calls made on the
   real engine. A refused file therefore records nothing and adds no audit
   entry; an accepted one adds one `trace.requirement` or `trace.item` audit
   entry per record, attributed to the actor.

An import records declarations only. It records no tool run and no evidence,
changes no artifact's assurance, and every requirement it records stays
unbacked until a real run backs it.

An import binds each item to a recorded artifact now: a file that is not yet
recorded is refused. Items planned before their file exists come only from an
approved plan (section 4), because only there is there an approved artifact
whose author the declaration can be attributed to.

## 3. Requirements in a specification

A seat's plan is checked against the approved specification, so the
specification must say which of its statements are requirements. A
requirement is tagged in the Markdown list item or paragraph that states it:

```
* The bound is **at most 2 cycles** for both writes and reads. [req:AXIL-LATENCY]
```

The tag pattern is data (`REQUIREMENT_TAG` in `company/traceability.py`). The
requirement's text is that list item or paragraph with the list marker and the
tag removed and whitespace collapsed; its section is the number of the nearest
heading above it. The AXI4-Lite fixture spec now tags the eight requirements
the M24 demo quoted by hand, with the same IDs.

## 4. The verification-plan seat

### As data

| Where | What |
|---|---|
| `company/vocabulary.py` | A feature, `verification_plan`, for "verification plan", "vplan", or "test plan" in a request. |
| `company/workflows.py` | A `dv-plan` stage on `block-design`, capability `dv.plan` (it existed), output `verification_plan` (it existed), after `interface-spec`, planned when the request has the feature. Nothing depends on it: its items bind to the testbench whenever that file is recorded (below), so the RTL stage, and every workflow built from its stages, is unchanged. |
| The stage's evidence | Independent review, and a before-review check: `vplan.check` over the produced plan (`plan`) and the approved upstream `interface_spec` (`spec`, `upstream=True`). |
| `company/tools.py` | `vplan.check`, AVAILABLE, bound in `integrations/vplan.py`; the `verification_planning` skill grants it. |

The stage is conditional so that the many existing tests and demos that plan a
block without asking for a plan keep their exact task graph.

### The check before review

`vplan.check` is a real, in-process tool run, recorded like any other. It
passes only when every plan file:

1. is valid in the format (section 1), every item naming a registered kind;
2. names, as each requirement's `source`, one of the approved spec files it was
   given (by file name);
3. covers every tagged requirement of each such spec, and has no requirement
   the spec does not tag;
4. quotes each requirement's text as the spec states it (whitespace
   normalized);
5. names each item's `file` as a plain file name (no directory), since the
   file may not exist yet.

A requirement with no item is allowed and reported in the summary: it is an
honest gap that `nirmaan gaps` will name. The spec file must tag at least one
requirement; a plan cannot be checked against a spec that marks none.

Because the `spec` binding is `upstream`, the M25 rule in the
`evidence-before-review` policy check already insists that the passing run
used an approved upstream spec file, byte for byte as recorded.

### On approval

The task engine gains a small registry, `register_approval_consumer(kind,
fn)`. When `approve` approves a task, each of its artifacts whose kind has a
consumer is handed to it **before** the approval commits; the consumer
validates and either refuses (the approval is refused, nothing changes) or
returns what to record, which runs right after the approval commits. The
engine names no kind; `nirmaan.vplan` registers the one for
`verification_plan`.

The verification-plan consumer acts only on a plan whose stage checks it with
`vplan.check` (a requirement whose `files` bind the `verification_plan` kind).
A `verification_plan` from any other stage, such as the `dv-plan` stages of
`new-ip` and `feature-addition`, is a document and records nothing, so those
workflows are unchanged. For a checked plan, it:

1. reads the plan file, checked against its recorded digest;
2. parses it, resolves each `source` to an approved upstream artifact of the
   plan's task by file name, and re-runs the spec checks against those
   digest-checked bytes;
3. refuses requirement or item IDs that are already recorded;
4. then records every requirement (`source` is the approved spec artifact) and
   every item, attributed to the engine's system actor (as every consequence
   of an approval is), with the plan named in each audit entry.

### Items planned before their file exists

The plan is normally approved before the RTL seat writes the testbench, so its
items name a file that is not yet an artifact. `VerificationItem` gains two optional
fields, `file` and `plan`; `artifact` becomes optional. The engine gains
`record_planned_item(actor, item_id, kind, name, file, plan, proves,
rationale)`: the same checks as `record_verification_item`, with the actor
rule applied to the plan artifact.

**Binding is derived, never asserted** (M24's Decision 1). Each time the gap
query asks, a planned item is bound to the latest recorded artifact whose file
has that name. Every M24 rule then applies unchanged to the bound artifact:
its digest must match, the item's name must occur in its bytes, and a passing,
cited, substantiated run of one of the kind's tools must name it. With no such
artifact yet, the item is `unverifiable`: "no recorded artifact holds
`axi4_lite_regs_tb.v` yet (planned in ...)". The engineering graph adds a
`planned_in` edge from the item to its plan, and `held_in` points at the bound
artifact.

## 5. The demo: AXI4-Lite, driven by the seat's plan

"Create an AXI4-Lite register block with a verification plan." plans
`dv-plan` after `interface-spec`. On scripted MockLLM answers and the real
tools:

1. The interface-spec seat writes the fixture spec, which is reviewed and
   approved.
2. The plan seat writes `tests/fixtures/rtl/axi4_lite/verification_plan.json`;
   `vplan.check` passes before review; it is reviewed and approved, and its
   eight requirements and six items are recorded.
3. The microarchitecture and RTL seats run as in M23, with real lint,
   simulation, and synthesis before review.
4. `nirmaan gaps` reports what the M24 demo did: AXIL-RESET, AXIL-WSTRB,
   AXIL-ORDER, AXIL-SLVERR, and AXIL-LATENCY backed by the real simulation;
   AXIL-B2B a gap (its cover point needs `coverage.read`, which is
   `CONTRACT_ONLY`); AXIL-SYNTH and AXIL-FORMAL gaps with no item.

The difference is where the plan came from: M24's demo test recorded it by
hand, after the RTL existed. Here a seat wrote it from the approved spec
before the RTL existed, a tool checked it, a reviewer and an approver passed
it, and the engine recorded it.

## 6. Extension points

| To add | Do this | Core changes |
|---|---|---|
| A verification-plan stage on another workflow, against another spec kind | A stage with capability `dv.plan` and a `vplan.check` requirement whose `spec` binding names that kind | none |
| A new item kind a plan may use | `register_item_kind` (M24) | none |
| Another artifact kind recorded on approval | `register_approval_consumer` | none |

The crown-jewel test adds a workflow through an org extension whose plan seat
checks against an approved `requirements_spec` instead of an interface spec,
with a newly registered item kind, and shows the plan checked, approved, and
recorded with zero core changes.

## 7. Laws, each pinned by a test (`tests/test_nirmaan_verification_plan.py`)

1. An imported plan exports back to the same file, and an export imports back
   to the same records.
2. A bad file is refused with line-level reasons, and nothing is recorded (no
   record, no audit entry).
3. An import never counts as passing: every imported requirement is unbacked,
   and no tool run or evidence is recorded.
4. An import is audited and authorized per record; an actor who neither owns,
   reviews, nor manages the producing task is refused, for the whole file.
5. The plan seat's check refuses a plan that misses a spec requirement,
   misquotes one, or names an unregistered item kind; the task stays out of
   review.
6. Approval records the plan; items bind to the file once the RTL seat writes
   it.
7. The AXI4-Lite demo, end to end, with the real tools.
8. Crown jewel: a plan seat on a new workflow, against a new spec kind, with a
   new item kind, needs no core change.
9. Import laws: `nirmaan.vplan` never imports VeriTriage, and the runtime, the
   engine, and the policy name no plan kind, capability, or tool.
10. No model API is called.

## 8. Deferred

M38 (`docs/VERIFICATION_PLAN_MORE.md`) closes three of these: the plan seat on
`new-ip` and `feature-addition` (their `dv-plan` stages are now checked plans,
so the "document" behavior described in section 4 no longer applies to them),
amending and retiring recorded requirements and items, and planned items in an
import.

- A YAML or spreadsheet reader for the same format.
- Planned items in an import (needs an artifact to attribute them to).
- Re-planning: amending or withdrawing recorded requirements and items. Today a
  second approved plan that repeats an ID is refused.
- Requirement tags in other spec formats than Markdown.
- Running the plan stage on `new-ip` and `feature-addition` (their `dv-plan`
  stages are unchanged).

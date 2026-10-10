# Milestone 38 - Checked plans on `new-ip` and `feature-addition`, and amending a recorded plan (after Stage 6)

Closes three M29 deferrals. Design doc: `docs/VERIFICATION_PLAN_MORE.md`. No
version bump.

Key design points worth not re-deriving:
- **The existing `dv-plan` stage became the checked one**, on every request
  (not only on a request for a plan, as on `block-design`): `PLAN_CHECKED` in
  `company/workflows.py` runs `vplan.check` over the plan and the approved
  upstream `requirements_spec`. `feature-addition` `dv-plan` also depends on
  `requirements-delta` directly. The M29 consumer records it on approval
  unchanged, since it acts on plans whose stage checks them.
- **Migrations, all listed in the doc (section 6):** `drive` writes a real,
  tagged requirements spec (`tests/fixtures/vplan/requirements_spec.md`, with
  digest) for every requirements stage and a real plan file
  (`tests/fixtures/vplan/verification_plan.json`, item in `counter_tb.v`) for a
  gated plan stage; it fills `upstream=True` bindings from approved upstream
  files and passes `workdir` only to tools whose contract takes it. The export
  `midway` fixture submits the plan file through `gated_submit`.
- **Amendments: one current plan per project.** A plan version is a whole
  file; against active records each entry is added, kept, or modified; an
  optional top-level `retired: [{requirement|item, reason}]` retires (format
  stays version 1). Every active record must be kept or retired; IDs are never
  reused. `SpecRequirement` and `VerificationItem` gain `revision` and
  `retired` (the reason). Engine: `amend_spec_requirement`,
  `retire_spec_requirement` (refused while an active item proves it; takes
  `backed_by`, the passing runs it had), `amend_verification_item`,
  `retire_verification_item`; audit actions `trace.{requirement,item}.{amend,retire}`
  carry the superseded record whole in `details["previous"]`.
  `vplan.history(state, id, what)` reads the versions back.
- **Same check, same approval.** `vplan.check` also applies
  `amendment_problems` (the binding passes `engine.state`); the consumer
  computes the changes and records them as the system actor with `plan`.
  `nirmaan vplan import --amend` (`vplan.amend_plan`) goes through the engine
  on a scratch engine first. Imports (plain or amend) run the seat's spec
  check when a source is a recorded, digest-checked file that tags
  requirements.
- **Planned items in an import**: an unrecorded plain file name is planned,
  attributed (actor rule and `plan`) to the source spec of the item's first
  requirement, which must be a recorded file.
- Coverage, `gaps`, the engineering graph, and export read active records only.

`tests/test_nirmaan_verification_plan_more.py` (14), crown jewel
`test_a_replan_stage_amending_the_plan_needs_no_core_changes`.

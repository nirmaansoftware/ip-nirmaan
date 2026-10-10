# Milestone 29 (verification plan) - Plans loaded from a file, and a plan seat (after Stage 6)

Closes M24's first deferral. A verification plan (requirements, and the items
that prove them) is a small JSON format, `nirmaan.vplan` version 1, read and
written by `nirmaan/vplan.py`; a seat writes one on `block-design`, a real tool
checks it before review, and the engine records it on approval.

Key design points worth not re-deriving:
- **Format.** `{"format", "version", "requirements": [{id, text, source,
  section}], "items": [{id, kind, file, name, proves, rationale}]}`. Unknown
  fields are refused (a plan cannot say `status` or `passed`), kinds must be
  registered, `proves` must name requirements in the file. JSON, not YAML:
  there is no YAML dependency. A pure-Python `JSONDecoder` whose
  `parse_object` records each object's line and each value's line gives
  `line N:` reasons.
- **Import is all or nothing, through the engine.** References (`source`,
  `file`) resolve by artifact ID, recorded path, or unique file name. The
  records are first made on a scratch `TaskEngine` over the same state; any
  refusal (M24 actor rule, duplicates, policy) is collected with its line and
  nothing is recorded. CLI: `nirmaan vplan import PROJECT FILE --as ROLE` and
  `nirmaan vplan export PROJECT [--out FILE]`; export is canonical (sorted,
  `indent=2`, file names when unique), so an imported file exports back
  byte for byte.
- **Spec requirements are tagged** `[req:ID]` in the Markdown list item or
  paragraph (`REQUIREMENT_TAG` in `company/traceability.py`); text is that
  item without marker or tag, section is the nearest heading's number. The
  AXI4-Lite fixture spec now tags the eight M24 demo requirements.
- **The seat is data.** Feature `verification_plan` ("verification plan",
  "vplan", "test plan"); a `dv-plan` stage on `block-design` (capability
  `dv.plan`, output `verification_plan`, after `interface-spec`, conditional on
  the feature, nothing depends on it, so every existing plan and every
  workflow built from block-design stages is unchanged). Before review:
  `vplan.check` (new, AVAILABLE, in-process, `integrations/vplan.py`, granted
  by `verification_planning`) over `plan` and the approved upstream
  `interface_spec` (`spec`, `upstream=True`): valid, covers exactly the tagged
  requirements, quotes each, plain item file names.
- **On approval.** `TaskEngine` gains `register_approval_consumer(kind, fn)`:
  `fn(engine, artifact)` runs before the approval commits (raise to refuse;
  nothing changes) and returns what to record after it commits. The engine
  names no kind. `nirmaan.vplan` registers for `verification_plan`, acting only
  when the artifact's stage checks it with `vplan.check` (so `new-ip`'s
  document plans are untouched); it re-checks the digest-verified plan against
  the digest-verified approved spec and records as the system actor, with
  `plan` in each audit entry. `nirmaan/work/__init__.py` imports `nirmaan.vplan`
  last, so the consumer is registered wherever the engine is.
- **Planned items.** `VerificationItem` gains `file` and `plan`; `artifact`
  defaults to empty. `TaskEngine.record_planned_item` applies the M24 checks
  with the actor rule on the plan artifact. `engineering.holding_artifact`
  binds a planned item, on every query, to the latest recorded artifact of
  that file name; with none it is `unverifiable` ("no recorded artifact holds
  ... yet"). The graph adds `planned_in` edges.

Demo (real tools): "Create an AXI4-Lite register block with a verification
plan." The plan seat writes `tests/fixtures/rtl/axi4_lite/verification_plan.json`
(8 requirements, 6 items), it is checked, reviewed, approved, and recorded
before any RTL; after the real simulation `nirmaan gaps` reports 5 of 8
backed, with AXIL-B2B, AXIL-SYNTH, and AXIL-FORMAL gaps, as in M24.

Tests: `tests/test_nirmaan_verification_plan.py`; crown jewel
`test_a_plan_seat_against_a_new_spec_kind_with_a_new_item_kind_needs_no_core_changes`.
Design doc: `docs/VERIFICATION_PLAN.md`. Deferred: YAML, planned items in an
import, amending recorded plans, non-Markdown spec tags, the plan seat on
`new-ip` and `feature-addition`.

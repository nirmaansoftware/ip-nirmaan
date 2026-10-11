# Milestone 23 (part) - The project deliverable export (roadmap Stage 4)

`nirmaan export PROJECT --out DIR` writes the numbered deliverable tree
(`01_requirement/` to `10_signoff/`, plus `INDEX.md`) as a **view over project
state**. It lands as part of M23, beside the design-agent seats; version bump is
left to the coordinator at merge.

Key design points worth not re-deriving:
- **The layout is data.** `src/nirmaan/company/deliverables.py` declares
  `DELIVERABLE_FOLDERS` (`DeliverableFolder`: ID, artifact kinds, fallback
  capabilities, `ExportSection`s). `nirmaan/export.py` names no folder (a test
  reads its string constants). An artifact goes to the folder naming its kind,
  else its task's capability, else it is listed as unfiled. The registry is
  `register_folder` (same ID replaces, which is how a remap works) and
  `unregister_folder`; `validate_folders` refuses a kind, capability, or section
  claimed twice. Implementation views sit in `04_rtl` until Stage 6.
- **Honesty.** Assurance is written as recorded and is in every artifact's file
  name (`rtl-lint_a1.EXECUTED.md`), its `.provenance.json` sidecar, and
  `INDEX.md`. A deliverable a live task still owes is listed as missing (with
  the task's status), a cancelled task's as not required; nothing stands in for
  either. Signoff lists a gate as signed off only with a completed, granted gate
  task and its `gate.approve` audit entry.
- **A broken chain exports loudly.** `ProjectStore.load(..., verify=False)` is
  new and used only by the export, which runs `verify_chain` itself: the
  `INDEX.md` banner, `09_evidence/audit_chain.json`, the signoff report, and the
  CLI all say the chain failed.
- **A read, and deterministic.** No state change and no audit entry; the output
  directory must be new or empty. Everything is sorted by ID and JSON keys are
  sorted, so a state and its saved-and-reloaded copy export byte-identically.
- Tool-run references that are files (EDA `<backend>.log`,
  `<backend>.result.json`) are copied into `09_evidence/tool_runs/<run>/` with a
  hash; references that are not files (VeriTriage session IDs) are recorded as
  given. An artifact's `location` is copied the same way, and the sidecar
  checks the copy against the artifact's recorded `digest` (match, mismatch,
  or none recorded).

20 new tests in `tests/test_nirmaan_export.py` (984 total), built by planning
and driving a project through the engine. Crown jewel
`test_a_new_folder_or_a_remap_needs_zero_core_changes`. Design doc:
`docs/DELIVERABLE_EXPORT.md`.

Deferred: an archive format with a signed manifest, and artifact bodies beyond
the recorded summary (the Stage 4 design agents will record located files,
which the export already copies).

v1.18.0 is the one version bump for the three M23 parts (fixtures, design
agents, export), built in parallel and merged as #23, #24, #26, and #25. The
standard run is 984 tests.

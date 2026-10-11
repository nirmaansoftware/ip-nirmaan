# Milestone 51 - Persistence integrity: planning never overwrites a project, sealed and atomic saves

Findings C3, H3, M3 and L6 of audit A and B1 of audit C, against v1.24.0.
Design: `docs/PERSISTENCE_INTEGRITY.md`. Tests:
`tests/test_nirmaan_persistence_integrity.py`, written first from the audit
probes and failing on `main`.

**Planning again is refused.** The project ID is derived from the requirement,
so planning the same text replaced the saved project, its work and its audit
trail. `ProjectStore.create` now refuses when the project exists; `nirmaan plan`
and `nirmaan demo --save` say so and point at `nirmaan show` and `--replace`.
`--replace` moves the old file to `<root>/archive/projects/<id>.<n>.json`,
which is itself a project store whose chain and seal still verify. MCP
`plan_project` honors `save` (it ignored it) and takes `replace`.

**Saved records are sealed.** Each save adds a `seal`: a SHA-256 over every
record except the audit entries, bound to the chain's length and head hash.
Load refuses a file whose records were edited (the probes: model calls erased
to reset the budget, a critical task marked completed) or whose seal is gone
or moved. `status`, `show` and `audit` take `--unverified` and mark the output
in bold red; the export and `nirmaan projects` state each project's records
status. Sealing on save, not per audit entry, keeps M32's per-operation cost:
about 5 ms of a 59 ms save on a 2.7 MiB project, and no engine change.

**Old projects** load as pre-sealing and are sealed on their next save;
`sealed_from` records the entry where sealing began, so records saved before
M51 are never reported as bound.

**Atomic save.** A temporary file, fsync, rename. `list` returns the readable
projects plus what it could not read; `nirmaan projects` reports unreadable
files and exits 1.

**Schema version "2"** marks the sealed format. "1" files load and are written
back as "2".

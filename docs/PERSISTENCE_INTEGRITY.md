# Persistence integrity (M51)

Two audits of v1.24.0 found that the saved project file did not live up to
P10 (no hidden state changes) and P11 (work remains auditable). This milestone
fixes four findings; every fix began as a test that failed on `main`
(`tests/test_nirmaan_persistence_integrity.py`).

| Finding | What was wrong | Fix |
|---|---|---|
| C3 (audit A), B1 (audit C) | The project ID is a hash of the requirement text, so `nirmaan plan`, `nirmaan demo N --save`, and MCP `plan_project` on the same text replaced the saved project: every task, review, tool run, model call, and the whole audit trail, with only "saved prj-..." printed. MCP `plan_project` ignored `save: false`. | Planning refuses to save over a saved project; `--replace` archives it first. `plan_project` honors `save` and takes `replace`. |
| H3 (audit A) | The hash chain covered only audit entries. Erasing `model_calls` reset the budget's spend; setting a task to `completed` marked work done. The file loaded cleanly. | Every save is sealed: a digest of every record, bound to the chain's length and head hash. A hand edit fails to load. |
| M3 (audit A) | The file was rewritten in place, so an interrupted save could leave it truncated, and `list` skipped unreadable files silently. | Atomic save (temporary file, fsync, rename). `list` reports what it cannot read. |
| L6 (audit A) | `schema_version` stayed "1" through the M39 and M48 data migrations. | Bumped to "2", the sealed format; see section 4. |

## 1. Planning never destroys a saved project

`ProjectStore.create(state, replace=False)` is the one way a new plan is saved.
If the project's file exists it raises `ProjectExistsError` and changes
nothing:

```
$ nirmaan plan "Create an AXI4-Lite register block."
Project prj-... already exists (.nirmaan/projects/prj-....json); planning it again would discard its work
and audit trail. Nothing was changed. See it with `nirmaan show prj-...`, or pass --replace to archive it
and plan afresh.
```

The first `nirmaan plan "..."` works exactly as before, and `--no-save` never
checks (it writes nothing). `demo --save` checks every chosen demo before
saving any, so `demo all --save` never saves half.

**Why `--replace` with an archive, not `--new` with a fresh ID.** The project
ID being a function of the requirement, the organization and the gate
overrides is relied on (docs, demos, the audit report's own walk-through use
`prj-1fdd8e0738`), and a nonce would make every plan of the same text a
different project, which is the duplicate-project problem in another form. A
replace is a deliberate act, so it is spelled out, and it destroys nothing:
the old file is moved, byte for byte, to
`<root>/archive/projects/<id>.<n>.json` (`n` counts up from 1). That folder is
itself a project store, so the archived project still verifies and can be
read: `nirmaan audit <id>.1 --root .nirmaan/archive`. The CLI prints both
paths. Recording the replace in the new project's audit trail would need a new
engine action; the archive is the durable record instead, and it carries the
old project's complete, sealed chain.

MCP `plan_project` takes `save` (default true; false only shows the plan) and
`replace` (default false), returns `saved` and `archived`, and a refusal is a
tool error with the same message.

## 2. The seal

### What it is

`ProjectStore.save` writes one more top-level key, `seal`:

```json
"seal": {"format": 1, "entries": 12, "head": "<hash of audit entry 11>",
         "sealed_from": 0, "digest": "<sha256>"}
```

`digest` is SHA-256 over a canonical JSON (sorted keys, no whitespace) of
`entries`, `head`, `sealed_from`, and every top-level record of the file except
`audit` and `seal`: tasks, artifacts, evidence, tool runs, reviews,
escalations, decisions, memory, model calls, attempts, the project itself, and
`schema_version`. The audit entries are already covered by the chain; the seal
binds everything else to the chain's length and head hash.

On load (`ProjectStore.read`), the store checks, from the file's own JSON:

1. The chain verifies (as before).
2. `entries` and `head` match the file's audit trail. Entries appended or
   dropped outside the engine fail here ("the seal covers N audit entries ...").
3. The recomputed digest matches. Any edited record fails here ("the project
   records were edited outside the engine: they do not match the seal at audit
   entry N").

The digest is computed from the file's JSON, never from a re-validated model,
so a later milestone that adds a field with a default does not invalidate
files sealed before it.

### Which design, and why

The brief offered two: a sealing field that names the chain head, or a state
digest chained into every audit entry. M51 seals **on save**.

- **A digest in every audit entry** would hash the whole state on every engine
  operation. That is exactly the cost M32 removed (`docs/SCALABLE_STATE.md`:
  `state_fingerprint` was 68% of an operation's time, and the total cost grew
  with the square of the project's length). It would also put the digest
  inside the engine, which another milestone is changing in parallel.
- **A seal on save** costs one SHA-256 over JSON the save has already built.
  Measured on the 55-task NoC bridge project with 3,000 audit entries (a
  2.7 MiB file): a save takes 59 ms, of which the digest is 5 ms (about 8%);
  loading adds the same 5 ms to 46 ms. No engine operation changes: a test
  holds that only `work/store.py` computes the digest and that the engine,
  the policy and the audit modules never import the store.
- What a hand edit is checked against is the same either way: the records as
  of the last audit entry. The engine never saves between operations, so a
  per-entry digest would add nothing a per-save one does not.

### What it does and does not guarantee

The seal makes the records as tamper-evident as the audit entries already
were, no more. Neither has a secret key: a person who edits the file **and**
recomputes the hashes with code that knows the format defeats both. What both
catch is every edit that does not, which is every edit by hand, by a text
editor, or by a script that does not know about the seal: the two probes of
audit A (spend erased, critical work marked completed) now fail to load.
Strong tamper-proofing needs an anchor outside the file, such as publishing
the head hash (the export's `INDEX.md` prints it) or signing it; that is not
done here.

### Loading a project that fails

`load` (and so every command that changes state, and every MCP tool) refuses
it, with the reason. A read-only view can show it on request:
`nirmaan status|show|audit <id> --unverified` loads it and prints
**UNVERIFIED PROJECT RECORDS: ...** in bold red above the output;
`status --json --unverified` carries `"records": {"status": "broken", ...}`.
`nirmaan export` always exports (it is a read, and it already reported a
broken chain the same way) and states the result in `INDEX.md` and on the
terminal: **PROJECT RECORDS FAILED VERIFICATION** beside the existing
**AUDIT CHAIN FAILED VERIFICATION**. `nirmaan projects` and MCP
`list_projects` show each project's records status (`sealed`, `pre-sealing`,
or `BROKEN`).

The store docstring said load also verified the organization fingerprint; it
never did (the CLI prints a note). The docstring now says so, and the
`budget.py` docstring and LOOP_CONCURRENCY.md section 3 now point at the seal
for the claim that editing the file is detected.

## 3. Projects saved before M51

A file with no seal and `schema_version` "1" is **pre-sealing**. It loads
(its chain still verifies), and every view says so: the CLI prints a yellow
note, `projects` shows `pre-sealing`, and the export's index states it. The
next save seals it.

Sealing does not pretend the old records were ever bound. The seal's
`sealed_from` is the number of audit entries the project had when it was first
sealed (0 for a project sealed since planning), carried from save to save; for
an upgraded project the views say "sealed from audit entry N: the records as
saved before M51 were never bound, everything since is". The fixture
`tests/fixtures/projects/m28-tool-runs.json` is the test case: it loads as
pre-sealing, and after one save reads as sealed from entry 9.

A file whose seal was stripped and whose version was set back to "1" therefore
loads only as pre-sealing, never as sealed, and once saved again its
`sealed_from` records the point at which it was unbound. A file that says "2"
but has no seal is refused.

## 4. Atomic save and an honest listing

`save` writes to `.<id>.json.<pid>.<random>.tmp` in the same directory, flushes
and fsyncs it, `os.replace`s it over the project file, then fsyncs the
directory where the platform allows. A crash, a Ctrl-C, or a full disk leaves
the previous file or the new one, never a truncated one, and the temporary
file is removed on failure. Its name ends in `.tmp`, so a listing never takes
it for a project. This keeps LOOP_CONCURRENCY.md's promise that the saved
state is always one the writer produced between segments.

`list()` returns a `Listing`: still a list of the readable projects (so
existing callers keep working), plus `unreadable` (each path and why) and
`integrity` (each project's status). `nirmaan projects` prints every
unreadable file in red and exits 1; MCP `list_projects` adds an
`{"unreadable": path, "reason": ...}` item for each.

## 5. Schema version "2"

`ProjectState.schema_version` now defaults to "2", and the store writes
`SCHEMA_VERSION` ("2") on every save, since what it writes is in the current
format whatever version it was read in. The migration path is: a "1" file is
read as before (the M39 and M48 conversions run in the model validators), is
reported as pre-sealing, and is written back as "2" with a seal. A "2" file
always carries a seal. A state read from a "1" file keeps "1" in memory until
it is saved and read again.

This also gives audit A's M6 finding (the pre-M48 parameter-to-bound
conversion also rewrites new data) the marker it asked for: data written as
"2" has already been through the conversion. Gating that conversion on the
version is left to the milestone that fixes M6.

## 6. Not done here

- No key, signature or external anchor for the chain head (section 2).
- A replace is recorded by the archive file, not by an audit entry in the new
  project.
- Two commands saving the same project at once still race (last save wins);
  M36's writer serializes saves within one `drive`, not across processes.
- MCP still accepts unknown arguments (audit C's B1 asked to reject them);
  only `plan_project`'s `save` and `replace` changed.

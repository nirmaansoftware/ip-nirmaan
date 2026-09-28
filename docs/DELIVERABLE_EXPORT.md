# The project deliverable export (Stage 4, M23)

A finished IP leaves the factory as a numbered tree of deliverables:

```
01_requirement/  02_architecture/  03_microarchitecture/  04_rtl/
05_verification/ 06_formal/        07_lint/               08_documentation/
09_evidence/     10_signoff/       INDEX.md
```

Everything that tree needs is already project state: artifacts with provenance
and assurance, evidence, tool runs, reviews, gate approvals, and the
hash-chained audit trail. The export is a **view** over that state. It creates
nothing, upgrades nothing, and writes nothing back.

```
nirmaan export PROJECT --out DIR [--root .nirmaan]
```

---

## 1. The rules

1. **The export never raises an assurance level.** Each artifact is written at
   the level the engine recorded, and the level is part of its file name
   (`rtl-implementation.axi_a1.EXECUTED.md`), its sidecar, and `INDEX.md`. An
   artifact that is only executed says so in all three places.
2. **Missing is missing.** A deliverable the plan expects but nobody has
   produced is listed as missing, with the task that owes it and that task's
   status, in the folder's `README.md` and in `INDEX.md`. No file stands in for
   it. A deliverable whose task was cancelled (a branch not taken) is listed as
   not required, not as missing.
3. **Signoff appears only when the engine recorded it.** A gate counts as
   signed off only when its task is completed with approval granted and the
   audit trail holds the `gate.approve` entry for it. Everything else is listed
   as not signed off, with its status.
4. **A broken audit chain is exported, loudly.** The export still runs (it is
   the evidence a reviewer needs to see the break), but `INDEX.md` opens with a
   failure banner, `09_evidence/audit_chain.json` carries every problem
   `verify_chain` found, the signoff report warns that its records come from an
   unverified trail, and the CLI prints the failure in red. `nirmaan export` is
   the one command that loads a project whose chain fails verification; it
   passes `verify=False` to `ProjectStore.load` and verifies the chain itself.
5. **It is a read.** Project state and the audit trail are byte-for-byte
   unchanged after an export. No audit entry records it, because nothing
   changed.
6. **It is deterministic.** Exporting the same state twice gives byte-identical
   trees: every collection is sorted by ID, JSON is written with sorted keys,
   and the only timestamps are those already in the recorded state (audit
   entries and the project's creation time). The output directory must be new
   or empty, so a stale file can never pass for part of the export.

---

## 2. The folder table is data

`src/nirmaan/company/deliverables.py` declares the layout. Each
`DeliverableFolder` names its directory, the artifact kinds it collects, the
capabilities it collects as a fallback for artifacts whose kind no folder
names, and the evidence sections it holds:

| Folder | Artifact kinds | Sections |
|---|---|---|
| `01_requirement` | `requirements_spec`, `product_brief`, `competitive_analysis` | |
| `02_architecture` | `architecture_spec`, `ip_architecture_spec`, `interface_spec`, `interconnect_architecture`, `qos_architecture`, `memory_architecture`, `security_architecture`, `power_architecture`, `performance_model`, `software_architecture`, `threat_model`, `impact_analysis` | |
| `03_microarchitecture` | `microarchitecture_spec` | |
| `04_rtl` | `rtl_source`, `power_intent`, `quality_report`, `constraints`, `netlist`, `synthesis_report`, `timing_report`, `power_report`, `dft_netlist`, `layout`, `ip_package`, `merge_record` | |
| `05_verification` | `verification_architecture`, `verification_plan`, `testbench`, `vip_configuration`, `tests`, `assertions`, `coverage_report`, `regression_report`, `triage_report`, `root_cause_analysis`, `cdc_report`, `security_verification_report`, `verification_closure_report`, `regression_infrastructure` | |
| `06_formal` | `formal_report`, `equivalence_report` | |
| `07_lint` | `lint_report` | |
| `08_documentation` | `document`, `register_doc`, `programming_guide`, `driver` | |
| `09_evidence` | `traceability_matrix`, `audit_report` | trace, tool runs, reviews, audit chain |
| `10_signoff` | `release_record` | signoff |

Implementation views (netlist, timing, power, layout) travel with the RTL they
were built from until Stage 6 gives physical design its own folder; that is one
table edit.

An artifact goes to the folder that names its kind; failing that, to the folder
that names its task's capability; failing both, it is listed in `INDEX.md` as
unfiled (never dropped silently). A test checks that every output kind any
workflow declares is routed.

`nirmaan/export.py` reads the table and never names a folder. The extension
point is a registry over the table:

```python
register_folder(DeliverableFolder(id="11_software", title="Software", artifact_kinds=("driver",)))
register_folder(documentation_without_driver)   # same ID: replaces, i.e. remaps
unregister_folder("11_software")                # overlays come off; built-ins return
```

`validate_folders` refuses a table where two folders claim the same kind,
capability, or section. The crown-jewel test adds a folder and remaps a kind
with zero core changes.

---

## 3. What each part of the tree holds

**Artifact folders.** Per artifact, named from its ID without the project prefix
and labelled with its assurance:

* `<name>.<ASSURANCE>.md`: title, kind, assurance and what that level means,
  the task, and the recorded content (the artifact's summary), or a plain
  statement that no content was recorded.
* `<name>.<ASSURANCE>.provenance.json`: who produced it, the task (owner,
  reviewer, approver, status), the requirement, its inputs (the artifact kinds
  the task consumes and the upstream artifact IDs it was derived from), its
  evidence (kind, substantiated or not, tool run, reference), the reviews of its
  task, the audit entries that name it (sequence and hash), and hashes: of the
  artifact record, of the exported content file, and of any copied location.
* `<name>.<ASSURANCE>.<basename>`: when the artifact's recorded location is a
  readable file, a copy as found at export time. The sidecar compares it with
  the `sha256:` digest recorded with the artifact (M23 design seats record
  one): it matches, it does NOT match (the file changed since), or no digest
  was recorded, so it cannot be checked.
* `README.md`: what the folder collects, what is present, what is missing, and
  what is not required.

**`09_evidence/`**

* `requirement_trace.json` and `requirement_trace.md`: requirement to tasks to
  artifacts to evidence, plus the completed work tasks that lack substantiated
  evidence (`untraced_requirements`).
* `tool_runs/<run-id>/run.json` and a copy of every reference that is a
  readable file (for EDA runs, `<backend>.log` and `<backend>.result.json`),
  with its hash. A reference that is not a file, such as a VeriTriage session
  ID, is recorded as such, not invented.
* `reviews.json`: every review record.
* `audit_chain.json`: every entry, the head hash, and a fresh `verify_chain`
  result.

**`10_signoff/`**: `signoff.md` and `signoff.json`, one row per gate in the
plan: signed off (by whom, human or not, when, and the audit entry), or not
signed off (and its status).

**`INDEX.md`**: the project, the chain verdict, the assurance legend, every
folder with its files and assurance labels, missing and not-required
deliverables, unfiled artifacts, and the signoff summary.

---

## 4. Tests

`tests/test_nirmaan_export.py` builds its projects through the engine (plan,
then drive tasks as the other Nirmaan tests do) and checks: the table drives the
layout; assurance levels are preserved and labelled; missing deliverables are
reported; a tampered chain is flagged; output is deterministic; state and the
stored file are unchanged; signoff appears only for recorded gate approvals; a
real lint run's log and result are copied (skipped without `verilator`); every
workflow output kind is routed; and the crown jewel,
`test_a_new_folder_or_a_remap_needs_zero_core_changes`.

## 5. Deferred

* An archive format (zip or tar) with a manifest signature. The tree plus
  `INDEX.md` is the content; packaging it is a later, separate step.
* Artifact bodies beyond the recorded summary. Stage 4's design agents will
  record RTL and specs as located files; the export already copies those.

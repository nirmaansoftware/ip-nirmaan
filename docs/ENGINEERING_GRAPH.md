# The cross-domain engineering graph (M24, roadmap Stage 5)

Status: implemented on branch `m24/engineering-graph`. This document was
written before the code and records the decisions the code follows.

## The question

Stage 5 is done when one call answers:

> Which requirements are not yet backed by passing verification evidence?

Two graphs already exist and nothing joins them:

- The **trace graph** (`nirmaan/work/trace.py`, M19): requirement, tasks,
  artifacts, evidence, tool runs. It knows what the organization did.
- The **Design Graph** (`veritriage/design/`, M15): modules, interfaces,
  instantiation, connection. It knows what the system is.

M24 adds the two missing joins:

1. **Artifact to design node.** An RTL file is linked to the modules it
   defines; a testbench to the module and interface it exercises.
2. **Requirement to verification item.** A requirement quoted from a
   specification is linked to the tests, assertions, or coverage points
   declared to prove it.

With both joins, "is this requirement backed?" becomes a walk: requirement,
verification item, the file holding it, the tool runs over that file, and the
evidence citing those runs.

## Decision 1: links are parsed, never asserted

A link from an artifact to a Design Graph node is **derived from the file's
bytes**, on demand, every time it is asked for. Nothing records a link, so
nothing (a model, a person, a stale cache) can assert one.

The derivation, for each artifact whose kind a link kind names:

1. The artifact must have a recorded `location` and `digest`. Without them the
   link is refused: there is nothing to parse, or nothing to check the parse
   against.
2. The file at `location` is read once. Its sha256 must equal the recorded
   `digest`; otherwise the link is **refused** with both digests in the reason.
   A file edited after it was recorded is never linked.
3. Those exact bytes (not the path, which could change between check and
   parse) cross the bridge to VeriTriage, which builds a Project Model and a
   Design Graph from them.
4. The link kind's walk runs over the returned graph and yields node IDs, each
   with the chain of Design Graph edge rationales that reached it.

Node IDs are VeriTriage's content-hashed IDs (`make_node_id(kind, name)`), so
two artifacts parsed separately converge on the same node: the RTL's
`axi4_lite_regs` and the testbench's instance of it are one node.

### Where the parsing lives: a VeriTriage RTL provider

The M15 law says the Design Graph is derived, never extracted, and that a
missing structural fact is fixed by a `ProjectProvider`, never by a parser in
`design/`. M11 deferred the RTL provider. M24 adds it:
`veritriage/project/providers/rtl.py` (`RtlSourceProvider`, name `rtl`).

It reads `.v` and `.sv` files (a file root, or the files directly in a
directory root) and emits only normalized structure:

- **Modules** each file defines (`source_file` set) and modules instantiated
  inside them (`parent` set to the instantiating module). A module that is only
  instantiated has no `source_file`: its definition is not in these sources.
- **Interfaces**: SystemVerilog `interface` declarations, and **port groups**:
  three or more ports of one module sharing a name prefix up to their last
  underscore (`s_axil_awaddr`, `s_axil_wdata`, ... form `s_axil`). The group
  is named `<module>.<prefix>` so the same bundle converges whether it is read
  from the module's port list or from a testbench's named connections
  (`.s_axil_awaddr(awaddr)`) to that module.

It is a lexical reader (comments and strings stripped, balanced parentheses),
not an elaborator: no preprocessor, no generate expansion, no parameter
evaluation. What it cannot see, it leaves out; a partial model gives a smaller
graph, never a wrong one.

`Interface` gains one optional field, `module` (the module whose ports form
it), and the interface extractor turns it into a declared (not inferred)
`connects` edge. That is the only change to the Design Graph layer.

### Link kinds are data

`nirmaan/company/traceability.py` declares `LINK_KINDS`:

| Link kind | Artifact kinds | Walk from the modules the file defines | Node kinds |
|---|---|---|---|
| `defines` | `rtl_source` | (none: the defined modules themselves) | module |
| `exercises` | `testbench` | `instantiates`, then `connects` backwards | module, interface |

A walk step is a Design Graph relation; a leading `<` follows it backwards.
With steps, only nodes reached by a step are linked (the testbench's own top
module is not something it exercises). `register_link_kind` in
`nirmaan/engineering.py` adds or replaces one; the crown-jewel test adds a
kind with zero core changes.

## Decision 2: requirement-to-item traceability is recorded, with provenance

Which requirement a test proves is a declaration, not a derivation: the
testbench cannot say it. It is recorded through the task engine, like every
other state change, so it passes authority and the constitution and gets an
audit entry.

Two new records in `ProjectState` (both default empty, so older states load):

- `SpecRequirement`: `id`, `text`, `source` (the artifact it is quoted from,
  such as the interface spec), `section`, `recorded_by`.
- `VerificationItem`: `id`, `kind` (a registered item kind), `name` (the test,
  check label, property, or cover point), `artifact` (the located file that
  holds it), `proves` (requirement IDs), `rationale`, `recorded_by`.

`TaskEngine.record_spec_requirement` and `TaskEngine.record_verification_item`
refuse unknown artifacts and requirements, duplicate IDs, an item in an
artifact with no file, and an actor who neither owns, reviews, nor manages the
task that produced the artifact.

A recorded mapping is a claim about intent. It can never make a requirement
backed on its own: that takes a passing run, below.

### Item kinds are data

| Item kind | Tools whose runs can prove it |
|---|---|
| `test` | `simulator.run`, `test.run` |
| `assertion` | `formal.run`, `simulator.run` |
| `coverage_point` | `coverage.read` |

`coverage.read` is `CONTRACT_ONLY`, so a coverage point is always a gap today,
and the gap says so. `register_item_kind` adds or replaces one.

## Decision 3: the gap query

`nirmaan.engineering.unbacked_requirements(state)` is the single call. It
returns every recorded spec requirement that is not backed, each with its
reasons. `requirement_coverage(state)` returns all of them, backed or not.

A requirement is **backed** when at least one verification item proves it and
**every** such item passed. An item passed when all of these hold:

1. Its kind is registered.
2. Its artifact's file still matches the recorded digest (the same check as a
   link).
3. Its name occurs in those bytes (an item cannot live in a file that does not
   mention it).
4. There is a recorded tool run, of one of the kind's tools, whose parameters
   name the file.
5. The **latest** such run succeeded. A later failure overrides an earlier
   pass.
6. That run is cited by `tool_run` evidence that is substantiated.

Everything else is a gap with a reason: no item at all, an unknown kind, a
changed or missing file, a name not found, no run (with the tools that would
count), a failed latest run (with its summary), or a passing run nobody cited.
Claims and human attestations on the producing task never count; when they
exist, the reason names them so a reader sees why they were not enough.

"Every item" rather than "any item" is deliberate: a failing test declared to
prove a requirement is evidence against it, and must not be outvoted.

## Surfaces

- **Python**: `nirmaan.engineering` (`artifact_links`, `requirement_coverage`,
  `unbacked_requirements`, `engineering_graph`).
- **CLI**: `nirmaan gaps PROJECT` (exit 1 when any requirement is unbacked,
  `--json` for data) and `nirmaan links PROJECT`.
- **Export**: a new `engineering_graph` section in `09_evidence/`
  (`engineering_graph.json` and `requirement_gaps.md`). The export gains a
  small section-writer registry (`register_section_writer`); the section is
  listed for `09_evidence` in the folder table, and its writer,
  `nirmaan.engineering.export_section`, is registered into that registry.

All three are reads: no state change, no audit entry, no model call.

## Import laws

Unchanged and still enforced: VeriTriage never imports Nirmaan, and only
`nirmaan/integrations/veritriage.py` imports VeriTriage. The bridge gains
`parse_design(name, data)`, which returns the Design Graph as plain data; the
link walk runs over that data on the Nirmaan side.

## Deferred

- Loading requirements and items from a file (a CLI `trace` command), and a
  verification-plan seat that proposes them for review: done in M29, see
  `docs/VERIFICATION_PLAN.md`.
- Per-check pass/fail inside one self-checking testbench: today a test item
  passes when its testbench's simulation passes.
- Parsing SystemVerilog interface ports on modules, packages, and includes.
- Merging every linked file into one project-wide Design Graph view.

# Milestone 24 - The cross-domain engineering graph (roadmap Stage 5)

"Which requirements are not yet backed by passing verification evidence?" is
one call: `nirmaan.engineering.unbacked_requirements(state)`, also `nirmaan
gaps PROJECT` (exit 1 when any; `--json`) and `09_evidence/engineering_graph.json`
plus `requirement_gaps.md` in the export. Version bump left to the coordinator.

Two joins the M19 trace graph lacked:
- **Artifact to Design Graph node, parsed, never recorded.** For each artifact
  whose kind a link kind names, the file at `location` is read once and must
  match the recorded `digest` (else the link is refused with both digests; no
  file or no digest is refused too). Those exact bytes go through the bridge
  (`parse_design(name, data)`, written to a private temp file) to VeriTriage,
  and the Design Graph comes back as plain data. `nirmaan links PROJECT` lists
  links and refusals. An RTL file `defines` its modules; a testbench
  `exercises` what it instantiates and those modules' interfaces.
- **Requirement to verification item, recorded with provenance.**
  `ProjectState.spec_requirements` (`SpecRequirement`: text, source artifact,
  section, recorded_by) and `verification_items` (`VerificationItem`: kind,
  name, artifact holding it, proves, rationale, recorded_by), written only by
  `TaskEngine.record_spec_requirement` / `record_verification_item` (audit
  actions `trace.requirement`, `trace.item`; the actor must own, review, or
  manage the artifact's task; unknown references, duplicates, and an item in
  an artifact with no file are refused). A mapping is intent and backs nothing.

Key design points worth not re-deriving:
- **The parser is a VeriTriage provider**, per the M15 law (the Design Graph
  is derived, never extracted): `veritriage/project/providers/rtl.py`
  (`RtlSourceProvider`, the M11.x RTL provider). Lexical, not an elaborator:
  modules defined, instances (with `parent`), SV `interface` declarations, and
  port bundles (three or more ports sharing a prefix up to the last `_`, named
  `<module>.<prefix>`, read from ports or from named connections, so the RTL's
  and the testbench's `axi4_lite_regs.s_axil` converge on one node). The only
  other VeriTriage changes: `Interface.module` (optional) and the declared
  `connects` edge it yields in the interface extractor; the manifest reads
  `module`; `_input_fingerprint` also hashes `*.v`/`*.sv`.
- **Backed** means at least one item proves the requirement and every one
  passed: kind registered, file digest still matches, the item's name occurs
  in the bytes, the latest run of one of the kind's tools naming the file
  succeeded, and substantiated `tool_run` evidence cites that run. A later
  failure overrides an earlier pass; claims and attestations never count and
  the reason says so. `coverage_point` needs `coverage.read`, a contract, so
  it is always a gap today.
- **Kinds are data**: `company/traceability.py` (`LINK_KINDS` with a walk of
  Design Graph relations, `<rel` backwards; `ITEM_KINDS` with the tools whose
  runs count), overlaid by `register_link_kind` / `register_item_kind`.
- The export gained a small section-writer registry
  (`register_section_writer`) and one section, `ExportSection.ENGINEERING_GRAPH`,
  listed for `09_evidence` in the folder table. Output is sorted, so reloaded
  states still export byte-identically.

17 new tests in `tests/test_nirmaan_engineering_graph.py` (984 -> 1001 on v1.18.0). Most
drive the AXI4-Lite RTL seat with fake lint and simulation executables the
test writes (real brokered processes). `test_stage5_demo_on_the_axi4_lite_flow`
runs the Stage 4 flow with real Verilator and Icarus: the RTL and testbench
link to `axi4_lite_regs` and `axi4_lite_regs.s_axil`, five interface-spec
requirements are backed by the passing simulation, and back-to-back (a
coverage point never measured), synthesis, and the formal proof (no item) are
listed as gaps. Crown jewel `test_a_new_link_kind_or_item_kind_needs_zero_core_changes`.
Design doc: `docs/ENGINEERING_GRAPH.md`.

Deferred: loading requirements and items from a file, a verification-plan
seat, per-check results inside one self-checking testbench, SV interface ports
and packages in the provider, and a project-wide merged Design Graph view.

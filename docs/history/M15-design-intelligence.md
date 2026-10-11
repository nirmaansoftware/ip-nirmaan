# Milestone 15 (v1.11.0) - Design Intelligence

The milestone that moves VeriTriage from understanding failures to
understanding systems. New top-level package `design/`, above `project/`,
below the pipeline.

**The critical evaluation that changed the milestone's shape.** The spec asked
for a `design/` package owning `Module`, `Interface`, `ClockDomain`, `Port`,
`AddressMap`, `UVMAgent`, `Scoreboard` and its own RTL/UVM extractors. But M11's
`ProjectModel` **already carries roughly eighteen of the twenty-eight proposed
artifacts**: modules with parents, IP blocks with members, interfaces with
protocols and signals, clock/reset domains with roots, an address map with
target IPs, UVM components with parents and interfaces, VIPs, RAL, coverage,
assertions, sequences, config objects. Building a second model would have
created two sources of truth for the same facts, and putting extractors in
`design/` would have broken M11's most important law (only a `ProjectProvider`
reads source).

**What is actually missing is not nouns but verbs.** Every relationship in the
Project Model exists as an unresolved string nothing walks: `DesignModule.parent`,
`ClockDomain.roots`, `UvmComponent.interface`, `AddressRegion.target_ip`,
`Vip.protocol_id`. The visible symptom was `resolve_scope()` in
`project/inference.py` bridging them by splitting strings on dots and
intersecting sets.

**Adopted design:** `design/` owns the *graph layer over* the Project Model, not
a rival model. This is the M1 to M2 transition repeated (parsers produced flat
ParseResults; M2 added the Evidence Graph over them without re-parsing).
Consequence: **zero changes to `project/`** were needed, which is the strongest
evidence the shape was right.

**The load-bearing law:** the Design Graph is *derived, never extracted*.
`design/` performs no source reading and imports no provider. If a structural
fact is missing, the fix is a `ProjectProvider`, not a new parser. RTL parsing
stays deferred to M11.x where it already belongs.

Structure: `model.py` (DesignNode/DesignEdge/DesignGraph; content-hashed IDs
like the Evidence Graph; node *merging* so extractors stay independent while
describing the same module), `registry.py` (`@register_extractor`, order-ranked),
`extractors/` (hierarchy, clock-reset, interfaces, address-map, verification,
verification-assets), `builder.py`, `query.py` (`DesignQuery`: affected_region,
owner_of, observers_of, clock_domains_of, crossings, hierarchy, dependencies,
protocol_map, unverified_modules), `inference.py` (report view).

14 relations: instantiates, owns, connects, drives, monitors, predicts,
implements, depends_on, clocked_by, reset_by, communicates_with, covers,
asserts, configured_by. Every edge carries a `rationale` naming the field it
came from, and edges that follow hierarchy rather than a declaration are marked
`inferred` (inference is allowed; hiding it is not).

Additive edits only: `AnalysisReport.design` (schema `11` -> `12`),
`AgentContext.design` (plain data; `agents/` never imports `design/`), five
WorkspaceServices methods, 8 MCP tools (43 -> 51), CLI `design` command, and a
report Design Intelligence section. No new ArtifactType, no Evidence Graph
change, no project/ change.

41 new tests (575 total). Design doc: `docs/DESIGN_INTELLIGENCE.md` (approved
before implementation). Crown jewel `test_new_extractor_needs_only_registration`:
a throwaway power-domain extractor defined in the test reaches the graph, the
queries, and the report with zero core changes. Caught during implementation:
`dependents_of` missed the address region because the fixture names an IP and
its top module identically, fixed by resolving across all same-named nodes.

Deferred to M15.x: the M11.x `rtl`/`uvm` providers that would populate ports,
FSM references and package imports; cross-probing and IDE clients over
`DesignQuery`; graph embeddings behind the M4 `EmbeddingProvider` seam.

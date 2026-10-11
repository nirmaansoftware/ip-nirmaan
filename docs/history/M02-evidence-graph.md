# Milestone 2 (v0.2.0) - `1985e5f`
Introduced the **Evidence Graph** as the central architecture and single
source of truth. `EvidenceNode`/`EvidenceEdge` with deterministic
content-hash IDs (`make_node_id`), typed `ArtifactType` (simulation_log,
assertion, coverage, test_metadata, compile_log, waveform_metadata
reserved), typed `RelationType` (PRECEDES, CAUSES, CORRELATES_WITH,
PART_OF, SUPPORTS). Parsers became `emit_evidence()` producers of graph
fragments; `GraphBuilder` merges + runs deterministic correlation passes.
Established the rule: **the AI layer must never read raw files, only the
graph's `to_reasoning_view()` projection.** Rules rewritten to be
graph-native.

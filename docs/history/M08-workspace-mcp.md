# Milestone 8 (v0.8.0) - Verification Workspace & MCP Platform
The Verification Intelligence Core is declared architecturally complete in
*shape* (packs/adapters/providers still grow through registries); M8 builds
around it, never into it. New `workspace/` package: `session.py`
(`InvestigationSession`, frozen: report + graph + deterministic content-hash
`session_id`; identity never depends on wall-clock), `persistence.py`
(`SessionStore`, one JSON bundle per session under `.veritriage/sessions/`,
byte-identical re-save), `services.py` (`WorkspaceServices`: THE public API:
investigate with optional record_history so history augmentation happens
before the session freezes, save/load/list, summary, evidence queries +
bounded graph view, matched patterns, waveform observations, engineering
context, timeline with graph-built fallback, read-only similar_regressions
probe, deterministic compare), `navigation.py` (every report section
individually addressable: one hypothesis/pattern/observation/commit/timeline
event/evidence node, None on miss), `search.py` (deterministic evidence +
knowledge-base search). New `mcp/` package: `tools.py` (transport-agnostic
tool table, 12 v1 tools, all routing through services; `register_tool` is the
new-endpoint extension point) and `server.py` (dependency-free MCP stdio
transport: newline-delimited JSON-RPC 2.0 subset: initialize, ping,
tools/list, tools/call; protocol version 2024-11-05; tool failures return
isError results, never crash the loop). **The CLI became client number one:**
analyze/investigate route through WorkspaceServices, cli/main.py no longer
imports veritriage.pipeline (AST-verified guard), investigate saves and
prints its session id, and new commands `mcp` (serve stdio) and `sessions`
(list bundles) landed. No report schema change (v7 stays; sessions wrap it).
No core file changed except cli/main.py. Architecture guards:
cli-and-mcp-share-services, sessions-immutable, public-API-never-exposes-raw
-parser-objects (AST import analysis: the third prose-vs-code guard lesson,
now done properly), no-engine-knows-workspace, workspace-never-depends-on-AI,
mcp-tools-route-through-services, and the crown jewel
`test_new_endpoint_needs_only_a_tool` (a throwaway tool registered inside the
test is served through the real transport with zero core changes). 25 new
tests (238 total). Review decisions (user-confirmed): hand-rolled stdio over
the official SDK (zero deps, offline-testable; SDK adapter is a future thin
file), two cohesive packages instead of the spec's seven examples, full
CLI-as-client refactor. Design doc: `docs/WORKSPACE_PLATFORM.md` (approved
before implementation).

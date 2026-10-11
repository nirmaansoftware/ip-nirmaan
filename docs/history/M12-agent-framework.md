# Milestone 12 (v1.8.0) - Agent Framework and Coordinator

The milestone that makes AI an *orchestration layer* rather than a text
generator at the end of a pipeline. New top-level package `agents/`, a peer of
`knowledge/`/`waveform/`/`engineering/`/`project/` but one layer higher: above
reasoning and above every lens, below the pipeline.

**The finding that shaped it:** the platform already had agent *parts* scattered
across three layers under three names (`ReasoningRule` observes with confidence
and citations; `HypothesisGenerator` produces positions and abstains without
evidence; `KnowledgePatternRule` gives 92 domain specialists at pattern
granularity; `rank_hypotheses` is already a merge function with a full trace;
`ExecutionEngine` is already a coordinator with attribution) and no agent
*unit*. M12 supplies exactly the four missing things: a per-domain aggregation
unit, a standard multi-part output contract, explicit agreement/conflict
detection, and a per-domain seam for generative intelligence.

**The load-bearing decision:** agents form a **second opinion, never a
replacement verdict**. The Coordinator consumes the finished deterministic
`ReasoningResult`, cross-examines it, and records `agrees_with_reasoning`;
nothing is reordered on disagreement. Test-pinned: the graph, the
classification, and the deterministic hypotheses are byte-identical with agents
on or off.

Structure: `context.py` (frozen `AgentContext`, the only input an agent ever
gets: normalized evidence and lenses, no path, so it *cannot* read a raw
artifact), `base.py` (`Agent` ABC + a builder that filters citations against the
real graph, drops uncitable hypotheses, and forces abstention), `registry.py`
(`@register_agent`), `providers.py` (the Deterministic/Generative boundary:
`ReasoningProvider` Protocol + `NullProvider` default + `DeterministicProvider`;
`build_request` deep-copies so a provider holds no live reference), and
`coordinator.py` (invoke in sorted order, isolate failures, merge, detect
conflict). Eight built-in agents in `builtin/`: protocol, rtl, testbench,
coverage, regression, formal, project, knowledge. Agents read the *deterministic
signals* the reasoning engine already computed rather than re-deriving patterns
from text, so extraction still happens exactly once.

Merge semantics (additive and traceable, mirroring `rank_hypotheses`):
`final = clamp(base + corroboration + contest, 0, 0.95)` where base is the
strongest single agent confidence for a category, corroboration is +0.05 per
additional independent supporter (capped +0.15), and contest is -0.10 once when
another agent leads elsewhere. The 0.95 ceiling is deliberate: unanimous
specialists can still all be reading incomplete evidence.

**Zero API-calling providers ship.** M12 delivers the seam and two deterministic
implementations; no vendor SDK, model name, or network call appears anywhere in
`agents/`. Existing `reasoning/ai.py` is untouched; a later milestone may
re-express it as an `AnthropicProvider` behind this seam.

Additive edits only: `AnalysisReport.agents` (schema `8` -> `9`),
`analyze(agents=True)`, `WorkspaceServices.investigate(agents=...)` plus two
read-only accessors (`agent_assessment`, `agent_result`), 3 MCP tools
(get_agent_assessment, get_agent_result, list_agents; 28 -> 31), CLI
`--agents/--no-agents` and an `agents` command, and a report "Agent Findings"
section. No `ArtifactType`, no `RelationType`, no core engine changed.

45 new tests (443 total). Design doc: `docs/AGENT_FRAMEWORK.md` (approved before
implementation). Crown jewel `test_new_agent_needs_only_registration`: a
throwaway thermal agent defined in the test reaches the Coordinator, the merged
findings, the conflict list, and the report with zero core changes. Notable: the
rogue-provider test found a real hole during implementation (the request handed
providers live model references, so a provider *could* mutate conclusions in
place); fixed by deep-copying in `build_request`. Also fixed on the way: the
long-stale README/KNOWLEDGE_ENGINE/ARCHITECTURE counts (still claiming 13 packs
/ 29 patterns / 12 MCP tools from v1.0.0-era text).

Deferred to M12.x: real AI providers behind `ReasoningProvider`; an
`agent-review` orchestration step; agent-aware bundle comparison; per-agent
confidence calibration from `feedback/`.

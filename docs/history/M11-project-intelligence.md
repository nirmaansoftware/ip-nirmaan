# Milestone 11 (v1.7.0) - Verification Project Intelligence (manifest-first)

A new layer of intelligence, not another parser/rule/pack: VeriTriage now
understands a verification project *before* any failure is analyzed. New
`project/` package building a durable, frozen, content-addressed **Project
Model** (the verification equivalent of an IDE index): DUT hierarchy,
interfaces with identified protocols, clock/reset domains, address map; UVM
topology (agents/monitors/scoreboards/predictors); testbench; sim
infrastructure; the expected **SimulationLifecycle**; and a **LogProfile**.
Structured exactly like M6/M7: **providers** are the only source-aware code
(`providers/base.py` `ProjectProvider` + `ProjectCapability`, `registry.py`
`@register_project_provider` + `collect_project`, `providers/manifest.py`
`*.vproj.json` canonical manifest that ships first), and everything downstream
is source-agnostic: `model.py` (frozen models + merge + `make_project_id` +
`seal_project` fingerprint), `insights.py` (`@register_insight`;
protocol identification reuses Knowledge Pack markers, so no protocol logic
lives in the core), `lifecycle.py` (pure projection of the Evidence Graph onto
the expected flow, reusing the M5 state-projection idea), `logmap.py` (log
intelligence: classify each line by origin rtl/testbench/vip/simulator/infra;
reads artifacts only through the parser registry), `inference.py`
(`project_reasoning_rules` + `build_project_view`), `persistence.py`
(`ProjectStore` caches one model per root under `.veritriage/project/`).

**The load-bearing decision:** the Project Model is a *separate*, persistent,
content-addressed model (parallel to the Knowledge Graph and Regression DB)
that **never enters the Evidence Graph**; it is a lens over it. It reaches
reasoning through the standard `ReasoningRule` interface (three rules:
`project:log-origin` shifts blame off the DUT when failing evidence originates
in VIP/infra; `project:lifecycle` favors build/testbench when the run stopped
before traffic; `project:scope-ownership` sharpens RTL when a scope resolves to
a DUT IP), each citing *existing* evidence node IDs, and reaches the report as
a new `AnalysisReport.project` field (schema `7` -> `8`). Additive edits:
`analyze(project=...)` optional keyword (CLI builds/caches the model, pipeline
stays pure), one `_SIGNAL_SUBSYSTEM` prefix in the orchestrator, WorkspaceServices
gains `build_project_model`/`load_project_model`/`project_summary`/`project_context`/
`explain_log` and `investigate(project=...)`, a report Project Intelligence
section, CLI `project` and `explain` commands + `--project/--no-project` on
`analyze`, 4 MCP tools (analyze_project, get_project_model, get_project_context,
explain_log). No `ArtifactType`, no `RelationType`, no core engine changed.
Permanent law (test-pinned): no component beyond a `ProjectProvider` reads
source; the model never retains source text. Crown-jewel
`test_new_project_source_needs_only_a_provider` (a throwaway provider defined in
the test reaches the model, a reasoning signal, and the report with zero core
changes). 21 new tests (398 total). Design doc: `docs/PROJECT_INTELLIGENCE.md`
(approved before implementation). Deferred to M11.x: `rtl`/`uvm`/`build`/
`regression` source providers, richer insights (bus/CDC topology), the optional
AI project brief. Also fixed on the way: the stale `__version__` (1.0.0 ->
1.7.0) and this file's section-3 header drift.

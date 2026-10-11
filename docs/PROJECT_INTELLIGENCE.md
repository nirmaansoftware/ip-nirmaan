# Verification Project Intelligence (M11)

Status: design approved, manifest-first increment planned. This document is the
architectural baseline for the Verification Project Intelligence subsystem. It
obeys every law in the platform baseline (Evidence Graph ownership, the AI
boundary, deterministic reasoning, registry-shaped extension, evidence-backed
conclusions). Prose here is intentionally free of em and en dashes per the
standing style law.

---

## 1. Vision

Give VeriTriage the capability a senior DV engineer has and the tool currently
lacks: a durable, structured understanding of the verification project itself,
built before any failure is opened. Today the platform reasons from the
artifacts of one run. A senior engineer reasons from a mental model of the whole
project, then reads the run against it. M11 builds that mental model as a
first-class, deterministic, reusable artifact: the Project Model, the
verification equivalent of an IDE's code index.

The Project Model is not evidence about a failure. It is the lens through which
every failure is subsequently read. Built once per project (cached,
fingerprint-invalidated), it makes every downstream investigation sharper
without changing a single existing conclusion path.

---

## 2. Problem statement

The Evidence Graph, rules, reasoning, knowledge, waveform, and engineering
layers all begin at the moment a run produces artifacts. None of them knows:

- what the DUT is (IP blocks, hierarchy, protocols, clock and reset domains,
  address map, register model);
- how the verification environment is organized (UVM topology, agents, monitors,
  scoreboards, predictors, RAL, coverage, assertions, sequencer);
- how a simulation is supposed to run (compile, elaborate, build, connect, reset,
  configure, traffic, check, shutdown, report);
- what a log line means (RTL vs testbench vs VIP vs simulator vs infrastructure
  vs boilerplate vs phase progress).

Consequences visible in the current code: correlation passes in
`graph/builder.py` fall back to substring matching on module strings; hypothesis
generators bucket failures by coarse heuristics (`"env" in module`); reasoning
cannot tell "died in connect_phase before any traffic" from "real design bug at
t=5000"; knowledge `suggested_signals` and waveform scopes resolve to nothing
concrete because the platform does not know this project's interfaces. Every
investigation re-derives project context from scratch, badly, and per run.

The gap is a missing layer of persistent, structural intelligence, not a missing
parser, rule, or pack.

---

## 3. High-level architecture

M11 introduces one new peer intelligence layer, `project/`, structured with the
platform's signature split (the M6 adapters-vs-engine pattern):

```
 PROJECT SOURCES (source tree, filelists, scripts, topology dumps, *.vproj.json)
        |  (only ProjectProviders touch source syntax: SV / Make / Tcl / dumps)
        v
   ProjectProvider.collect() --> ProjectModelFragment  (normalized, lossy, provenanced)
        |  merge (content-addressed, order-independent)
        v
   +--------------  PROJECT MODEL  (frozen, fingerprinted, cached)  --------------+
   |  Dut . VerificationEnv . Testbench . SimInfra . EngineeringMeta              |
   |  SimulationLifecycle . LogProfile          (all source/tool-agnostic)        |
   +------------------------------------------------------------------------------+
        |                    |                         |
        v                    v                         v
   ProjectInsight       project_reasoning_rules   build_project_view / lifecycle
   detectors            (injected like knowledge   projection (pure projections
   (protocol ID via     /waveform/engineering      of the Evidence Graph, never
   knowledge markers,    rules; cite EXISTING       mutating it)
   bus/CDC topology,     evidence node IDs)              |
   lifecycle inference)      |                           v
                             v                     AnalysisReport.project (schema 8)
                        Reasoning ranking                +  optional AI project brief
                                                            (downstream, model view only)
```

The one load-bearing decision, stated once: the Project Model is a separate,
persistent, content-addressed model, parallel to the Knowledge Graph and the
Regression Database, and it never enters the Evidence Graph. It reaches reasoning
the same way knowledge does (injected `ReasoningRule`s that cite existing
evidence nodes), and it reaches the report as context. This is what keeps
Evidence Graph ownership intact: the graph stays "what happened in this run"; the
project model is "what this project is."

Format and tool-specific parsing (SystemVerilog, Makefiles, Tcl, topology dumps)
is quarantined in `ProjectProvider`s, exactly as waveform formats live only in
adapters and engineering tools live only in providers. The model, the insight
detectors, the reasoning rules, and the report views are source-agnostic and
read only normalized data.

---

## 4. Where it belongs in the package hierarchy

New top-level package `src/veritriage/project/`, a peer of `knowledge/`,
`waveform/`, `engineering/`, at the same layer (above reasoning, below
workspace):

```
models  <  graph  <  parsers/rules  <  reasoning  <  knowledge
                                                        ^
                                              project  -+   (reuses knowledge markers for protocol ID)
                                                        ^
                                                     pipeline  <  workspace  <  mcp/orchestrator/collab  <  cli
```

```
src/veritriage/project/
  model.py            frozen ProjectModel + submodels + fingerprint + merge
  providers/
    base.py           ProjectProvider ABC + ProjectCapability  (ONLY source-aware code)
    registry.py       @register_project_provider, collect_project(), find/available
    manifest.py       *.vproj.json canonical provider (the escape hatch; ships first)
    rtl.py            heuristic RTL structure provider (SV/Verilog, capability-declared) [later]
    uvm.py            UVM topology provider (print_topology dump or factory/type scan) [later]
    build.py          filelist/Makefile/run-script provider -> SimInfra [later]
    regression.py     regression-launcher config provider [later]
  insights.py         source-agnostic detectors: protocol ID (via knowledge markers),
                      bus/interconnect topology, clock/reset domain grouping,
                      SimulationLifecycle inference
  persistence.py      ProjectStore (one JSON model under .veritriage/project/<id>.json)
  inference.py        project_reasoning_rules(model) + build_project_view(model, graph, report)
  lifecycle.py        project_lifecycle_projection(model, graph)  (pure projection)
  logmap.py           LogProfile application: classify evidence-node origin/phase
  ai.py               optional ProjectAISummarizer (project brief; downstream; model view only)

src/veritriage/models/project.py   layer-neutral report/API views (like models/orchestration.py)
```

`project/` may import `graph`, `models`, `reasoning.signals` (the `ReasoningRule`
ABC), and `knowledge` (to reuse concept markers for protocol identification).
Nothing below `project/` imports it. `knowledge/` does not import `project/`, so
there is no cycle.

---

## 5. Data models

All frozen, all carrying provenance (`source_provider`, `source_file`, `line`)
and a `confidence` (1.0 for declared facts, lower for inferred), mirroring
`EvidenceNode`. IDs are content-derived (`make_project_id`,
`pm-xxxxxxxxxxxx`), so the same source produces the same model byte for byte.

Root: `ProjectModel` with `project_id`, `source_root`, `built_at`,
`input_fingerprint` (of the source it was built from, for staleness),
`provider_versions`, the five sub-models, plus `lifecycle` and `log_profile`.
`fingerprint()` for immutability proofs (like `KnowledgeGraph`). `merge()` for
combining fragments (content-addressed, so double delivery is a no-op).

DUT (`Dut`): `DesignModule` hierarchy, `IpBlock`, `Interface`
(name, `protocol_id | None`, signals, direction), `ClockDomain`, `ResetDomain`,
`AddressMap` with `AddressRegion`, `RegisterModelRef`, module `dependencies`.

Verification Environment (`VerificationEnv`): `UvmComponent` topology tree
(typed: agent, monitor, scoreboard, predictor, subscriber, sequencer, driver,
env, test, coverage), `RalModel`, `CoverageCollector`, `AssertionGroup`, `Vip`.

Testbench (`Testbench`): `TestDef`, `SequenceDef`, `ConfigObject`, `Plusarg`,
`FactoryOverride`, `PhaseUsage`.

Simulation Infrastructure (`SimInfra`): `Simulator`, `CompileFlow`, `RunFlow`,
`RegressionSetup`, `GeneratedArtifactKind` (glob + ignorable flag), `LogSource`
(path pattern -> origin), `WaveformFormat`, `FormalFlow | None`.

Engineering Metadata (`EngineeringMeta`): `Owner`, `Repository`, `Manifest`,
`Doc`, `BuildScript`, `ImportantPath`, `IgnoreGlob`.

Cross-cutting: `SimulationLifecycle` (ordered `LifecyclePhase`s with markers,
reusing the `StateMachine`/`ProtocolState` shape so the existing projection
algorithm applies unchanged); `LogProfile` (ordered `LogOriginRule`s mapping
message/scope patterns to an origin: rtl, testbench, vip, simulator,
infrastructure, boilerplate, progress, phase).

Report and API views in `models/project.py`: `ProjectContext` (report section),
`DutTopologyView`, `UvmTopologyView`, `LifecycleProjection` (reused
`StateProjection` shape), `LogAnnotationView`.

No new `ArtifactType`, no new `RelationType`. The Evidence Graph vocabulary is
untouched.

---

## 6. Extension points (registries)

Three registries, all in the established `@register` / `available_*` / `get_*` /
`unregister_*` shape, each test-pinned by a crown-jewel:

1. `ProjectProvider` (`@register_project_provider`): one source kind in, one
   `ProjectModelFragment` out. Built-ins: `manifest` (`*.vproj.json`), then
   `rtl`, `uvm`, `build`, `regression`. The only source-aware code in the
   platform. Declares `ProjectCapability` (HIERARCHY, INTERFACES, CLOCKS,
   UVM_TOPOLOGY, ADDRESS_MAP, REGISTER_MODEL, SIM_FLOW) so missing capabilities
   degrade honestly, exactly like `WaveformCapability`.
2. `ProjectInsight` detectors (`@register_insight`): source-agnostic derivations
   over merged fragments (protocol identification via knowledge markers, bus
   topology, CDC domain grouping, lifecycle inference). Same split as waveform
   `ObservationDetector`s: providers parse, detectors conclude, and detectors
   never read files.
3. `LogOriginRule` registry (`@register_log_origin`): extensible message-origin
   classification for log intelligence.

Escape hatch (ships first, mirrors `*.engctx.json` / `*.wave.json` /
`*.formal.json`): the canonical `*.vproj.json` manifest lets any project or CI
export its structure with zero RTL parsing. This makes the whole subsystem usable
and testable on day one and keeps source providers as pure, additive enrichment.

---

## 7. Interaction with the Evidence Graph

None, by design, and that is the point. Project facts never become `EvidenceNode`s
and add no `ArtifactType`. Instead the model provides two read-only services over
the graph:

- Scope resolution: `resolve_scope(module_str) -> ResolvedScope` upgrades a bare
  module string into `{ip, interface, protocol, clock_domain, owner}`. Reasoning
  rules and report views use this; `graph/builder.py` is not modified (keeping the
  core free of project coupling).
- Lifecycle projection: `project_lifecycle_projection(model, graph)` projects the
  run's evidence onto the expected `SimulationLifecycle` to find where the run
  stopped, a pure projection (no mutation), reusing the Knowledge Engine's
  `project_states` algorithm. Pinned by a no-mutation test, like the engineering
  timeline.

Project-derived signals still cite real evidence node IDs, so conclusions stay
evidence-backed and reasoning stays deterministic.

---

## 8. Interaction with the Knowledge Engine

Reuse, not duplication:

- Protocol identification consumes knowledge markers. `insights.py` asks the
  `KnowledgeGraph` for each pack's concept markers and matches them against the
  project's interface signal names and module names to set
  `Interface.protocol_id`. No protocol logic is hardcoded in the project core; it
  is entirely data-driven by the packs, so adding a protocol pack automatically
  improves project protocol ID.
- Knowledge matching becomes project-aware downstream. Matched patterns can be
  prioritized by whether their protocol is present in the DUT, and
  `suggested_signals` resolve against real interfaces. This is a report-view
  refinement, not a matcher change; `knowledge/matcher.py` stays untouched.

Dependency direction: `project -> knowledge` (consumer). `knowledge` never
imports `project`.

---

## 9. Interaction with the Reasoning Engine

Identical mechanism to knowledge, waveform, and engineering:
`project_reasoning_rules(model)` returns standard `ReasoningRule`s injected by the
pipeline into the same rule slot. They cite existing evidence node IDs, only shift
ranking, and never conclude. High-value rules:

- Log-origin rule: using `LogProfile`, if the failing evidence originates from VIP
  or infrastructure rather than the DUT, raise INFRASTRUCTURE_ISSUE and
  TESTBENCH_ISSUE and lower RTL_BUG, with cited nodes and justification.
- Lifecycle-divergence rule: if the lifecycle projection shows the run stopped
  before traffic, raise BUILD_ISSUE and TESTBENCH_ISSUE and lower RTL_BUG.
- Scope-ownership rule: when a failing scope resolves to a specific IP or
  interface, sharpen the RTL_BUG statement and route the recommendation
  (ownership informs recommendations only, never ranking, per the M7 law).

`reasoning/` and `rules/` never import `project`. Signal naming convention
`project:*` slots into the orchestrator's `attribute_subsystems` prefix map with a
one-line addition.

---

## 10. Interaction with the Workspace

`WorkspaceServices` gains project methods (additive, deterministic, AI-free), and
`investigate` accepts an optional model, mirroring how it already accepts
engineering context:

```python
def build_project_model(self, root: Path) -> ProjectModel
def load_project_model(self, root_or_id) -> ProjectModel | None
def project_summary(self, model) -> ProjectSummary
def dut_topology(self, model) -> DutTopologyView
def uvm_topology(self, model) -> UvmTopologyView
def simulation_lifecycle(self, session, model) -> LifecycleProjection
def explain_log(self, path, model=None) -> list[LogAnnotationView]
def investigate(self, paths, engineering=None, project=None, ...) -> InvestigationSession
```

The session optionally references `project_id` via `model_copy` (never part of
identity, like `plan`/`trace`). The workspace stays the single public boundary;
clients never import `project` directly.

---

## 11. Public APIs

- Library: `veritriage.project.build_project_model(root)`, `ProjectModel`,
  `project_reasoning_rules`, `build_project_view`, and
  `analyze(paths, ..., project=model)`.
- Service: the `WorkspaceServices` methods above.
- MCP tools (each one `register_tool`, zero core change): `analyze_project`,
  `get_project_model`, `get_dut_topology`, `get_uvm_topology`,
  `get_simulation_lifecycle`, `explain_log`, `list_project_sources`.
- The stable-surface list grows by one registry family (`ProjectProvider` /
  `@register_insight` / `@register_log_origin`).

---

## 12. CLI changes

```
veritriage project [ROOT]            build/refresh + print project brief
veritriage project --json            machine-readable model
veritriage dut [ROOT]                DUT topology view
veritriage env [ROOT]                verification-environment topology view
veritriage flow [ROOT]               simulation lifecycle + sim infra
veritriage explain sim.log           log intelligence: annotate each line by origin/phase
veritriage analyze sim.log --project     use cached model (default: use if present)
veritriage analyze sim.log --no-project  opt out (byte-identical to today)
```

`--project` defaults to "use the cached model if one exists for this root, else
degrade silently", exactly like `--context/--no-context`. The pipeline stays pure:
the CLI builds/loads the model and passes it in; `analyze()` performs no source I/O.

---

## 13. Testing strategy

Fixtures: a small synthetic project tree under `tests/fixtures/project/` and a
canonical `sample.vproj.json`.

- Unit and determinism: each provider parses deterministically; merge is
  order-independent; `fingerprint()` stable; `project_id` content-derived;
  protocol ID via knowledge markers; lifecycle projection finds the stop point;
  `explain_log` classifies origins.
- Architecture guards (AST-based like the existing ones):
  - `test_project_core_is_source_agnostic`: only `providers/` reference SV/Make/Tcl
    or file reads; `model.py`, `insights.py`, `inference.py`, `lifecycle.py` never
    call `open`/`read_text`/`Path(`.
  - `test_project_never_becomes_evidence`: no new `ArtifactType`; the Evidence
    Graph is byte-identical with and without a project model supplied.
  - `test_reasoning_has_no_project_dependency`: `reasoning/` and `rules/` never
    import `veritriage.project`.
  - `test_core_unchanged_by_project`: nothing at or below `pipeline` imports
    `project` except through the optional keyword; `knowledge` does not import it.
  - `test_project_never_depends_on_ai`: no `anthropic`/`reasoning.ai` in `project/`
    except `ai.py`.
  - `test_projections_do_not_mutate_the_graph`: lifecycle/topology views are
    read-only.
  - Crown jewel `test_new_project_source_needs_only_a_provider`: a throwaway
    `ProjectProvider` defined inside the test reaches the model, a `project:*`
    reasoning signal, and the report with zero core changes.
- Report: the Project section renders; no em or en dashes (U+2014, U+2013) in output.

---

## 14. Migration strategy

Purely additive, in the established milestone style:

1. New `project/` package and `models/project.py`. No `ArtifactType`, no
   `RelationType`.
2. `AnalysisReport` gains an optional `project` field, so report schema `"7"`
   becomes `"8"` (consistent with the M6/M7 bumps for waveform/engineering, since
   project context is report-rendered). Update the `test_cli` schema assertion.
3. `analyze(project=None)` optional keyword; pipeline stays pure.
4. `WorkspaceServices` additive methods; session references `project_id` via
   `model_copy`.
5. `_SIGNAL_SUBSYSTEM` in the orchestrator gains one `("project:", "project")`
   entry.
6. Ship the `manifest` provider first; `rtl`/`uvm`/`build`/`regression` providers
   land additively behind their capabilities.
7. Backward compatibility is total: with no model, every output is byte-identical
   to today. The existing tests pass unchanged before any new test is added.
8. Refresh the portfolio sample report/dashboard per the standing habit once
   user-visible behavior changes.

A permanent law for this layer, pinned by tests (the M6/M7 quarantine applied to
source): no component beyond a `ProjectProvider` references a source language,
build tool, or file format; the model never retains source text.

---

## 15. Risks and trade-offs

- SystemVerilog parsing is a tar pit. Full elaboration is out of scope forever.
  Mitigation: manifest-first, plus a heuristic structural provider that declares
  limited capabilities and attaches honest confidence (the VCD-adapter precedent).
  We index structure; we do not build a compiler.
- Scope creep toward an EDA frontend or linter. Guarded by the lossy-by-design law
  above: providers normalize and discard; the model is a structural summary, never
  a source mirror.
- Staleness. A cached model can drift from source. Mitigation: `input_fingerprint`
  invalidation; `veritriage project` reports staleness and rebuilds.
- Determinism of inference. Protocol ID, CDC grouping, and lifecycle inference are
  heuristic. Keep them deterministic, confidence-tagged, provenance-backed, and let
  them only inform ranking, never conclude.
- Correlation-precision temptation. Keep the model a reasoning-and-report lens, not
  a graph mutator, to preserve Evidence Graph ownership.
- AI shortcut temptation. Deterministic structural analysis first; the AI
  summarizes the model and cites project-node IDs, and never originates a
  structural fact. Same boundary as `AIReasoner`.
- Adoption cost. Manifest-first keeps entry near zero; source providers are opt-in.
  Multi-DUT confusion is bounded by `project_id` + `source_root` scoping.

---

## How failure investigations become fundamentally better

1. Contextualized diagnosis. A failing scope stops being `uvm_test_top.env.axi_mon`
   and becomes "the AXI read-data monitor watching the cpu_l2 interface (AXI4),
   clock domain clk_core, IP l2_cache, owned by team-cache." Hypotheses,
   recommendations, and routing become specific.
2. The reasoner stops blaming the DUT for other people's noise. Log intelligence
   tags each failing message with an origin, so VIP or infrastructure noise shifts
   weight away from RTL_BUG with justification.
3. Lifecycle-aware failures. "The run stopped between connect_phase and reset,
   before any traffic" is a diagnosis today's generic timeout rule cannot make.
4. Knowledge and waveform become concrete. `suggested_signals` and observation
   scopes resolve to actual interfaces and signals in this project.
5. Cross-run leverage and onboarding. The model is built once and reused; "what is
   this project?" becomes a single command.
6. Sharper AI and fewer false positives, because both the AI review and the
   knowledge matcher operate against a known topology.

Net effect: VeriTriage crosses from a Failure Investigation Platform to a
Verification Intelligence Platform, without weakening a single existing
architectural law.

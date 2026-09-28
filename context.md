# IP Nirmaan - Project Context

This file is a continuity document: what VeriTriage is, how it got built,
where every piece lives, and what is deliberately left for later. It exists
so work can resume in a new session (or by a new contributor) without
re-deriving decisions already made. It is not user-facing documentation -
see `README.md` and `docs/` for that - this is the "how we got here and
what's next" record.

Repo: https://github.com/nirmaansoftware/ip-nirmaan (public, Apache-2.0; renamed from
`veritriage` (then `nirmaan-ip`) after M19, then transferred from `patel-om`
to the `nirmaansoftware` account on 2026-09-28; GitHub redirects the old URLs,
and `patel-om` keeps push access as a collaborator)
Local path: `/Users/ompatel/Documents/veritriage`
Current version: **1.16.1** (distribution `ip-nirmaan`; packages `nirmaan` and `veritriage`)
Portfolio: removed from `/Users/ompatel/Documents/Om Portfolio` at the user's
request after M19 (card and sample pages deleted).

---

## 1. What VeriTriage is

VeriTriage is an AI-assisted **Verification Intelligence Platform** for
semiconductor DV (design verification) engineers. It turns raw verification
artifacts - simulation logs, compile logs, coverage summaries, test
metadata - into:

1. A normalized **Evidence Graph** (typed nodes + typed edges, deterministic
   content-hashed IDs) that is the single source of truth for everything
   downstream.
2. A deterministic **failure classification** with confidence and evidence.
3. A multi-stage **Reasoning Engine** that produces multiple ranked,
   evidence-backed competing hypotheses (RTL bug vs. testbench vs.
   infrastructure vs. build) with fully traceable confidence propagation.
4. A **Verification Knowledge Engine**: 42 pluggable Knowledge Packs across
   six domains (interconnect, CPU/ISA, memory, serial IO, coherency,
   methodology) encoding real protocol/methodology expertise that match
   deterministic failure patterns against evidence, project it onto protocol
   state machines, and attach fixed debug playbooks with real specification
   references - all before any AI runs.
5. An **Agent Framework** (M12): eight domain specialists that form
   independent, evidence-backed positions over the finished deterministic
   result, and a Coordinator that merges them into ranked findings with
   agreement, conflict, and per-agent contribution made explicit. A second
   opinion, never a replacement verdict.
6. A **Learning Engine** (M13): every completed investigation improves the
   next one. Seven families of versioned, explainable artifacts derived
   deterministically from recorded history (recurring patterns, evidence
   combinations, agent reliability, project profiles, protocol statistics,
   recommendation outcomes, hypothesis history), recalled as hints and a
   bounded agent calibration map. It remembers; it does not decide.
7. A **Planning Engine** (M14): the layer that answers "what should happen
   next?" rather than "what is true?". Derives a branching `DebugPlan` from
   the conclusions: steps ordered by value against effort, decision points,
   the evidence still missing and why it matters, completion conditions, and
   risks. It contributes structure, never content.
8. A **Design Intelligence Engine** (M15): the third graph. A **Design Graph**
   of modules, IP blocks, interfaces, clock/reset domains, address regions,
   register blocks, UVM components and VIPs, joined by 14 typed relationships,
   derived deterministically from the Project Model and never from source.
   Structural questions ("which agent owns this interface?", "what crosses this
   clock boundary?") become graph traversals.
9. A **Conversation Engine** (M16): the intelligence becomes navigable.
   Structured questions, answers assembled from artifacts that already exist,
   navigation state that carries between turns, and suggested follow-ups. It
   owns no intelligence: conversation navigates, it never concludes.
10. **Generative AI** (M17): providers render, never reason. An `LLMProvider`
   receives a frozen `Prompt` built from cited platform objects and returns
   prose; grounding is enforced by stripping citations the prompt did not
   authorize. Generation is off by default and no built-in provider calls an
   external API.
11. An **Automation Engine** (M18): the platform reacts. Immutable, ordered,
   content-addressed events on a replayable bus; declarative triggers; rules
   that are structured data; and a closed action vocabulary the workspace
   dispatches. Automation observes and decides; it never executes.
12. A persistent **Regression Database** (SQLite) giving the platform
   historical memory: deterministic failure signatures, similarity search,
   "have we seen this before?", failure clustering, and team-level
   analytics via an engineering dashboard.
13. A **legacy AI review** (`reasoning/ai.py`, M3) that reasons only over the
   bounded, normalized output of the deterministic stages (never raw files) and only explains/annotates -
   it cannot alter the graph, classification, ranking, or knowledge
   conclusions.

**Non-negotiable design law, stated once and enforced by architecture tests
at every milestone since M2:** the AI layer never reads raw artifact text
and never originates a technical conclusion. Everything it explains was
already established deterministically. This is the platform's core thesis
and the reason it's structured as five composable layers rather than one
big prompt.

**Standing constraint from the user, applies to all text everywhere:** no
em dashes or en dashes anywhere in code, docs, comments, or generated
report content ("it looks AI generated"). Every commit sweeps for this.

**Commit convention:** every commit message ends with
`Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Never `--amend`;
always new commits. Never force-push.

---

## 2. Milestone history

The project was built "brick by brick" - each milestone is a complete,
tested, documented, shippable increment. Do not skip ahead of the current
milestone without the user asking.

### Milestone 1 (v0.1.0) - `f8f5698` - originally named TraceIQ
Deterministic log parsing (UVM/Questa/VCS/Xcelium + generic fallback),
structured Pydantic models, a rule-based classifier (compile/assertion/
timeout/testbench/fatal/unknown/no-failure with fixed confidences), an
EDA-dashboard-style self-contained HTML report, optional AI summary, Typer
CLI (`analyze` command), pluggable parser registry. Explicitly excluded:
waveform/RTL parsing, multi-agent, RAG, vector DBs, cloud.

### Milestone 2 (v0.2.0) - `1985e5f`
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

### Milestone 3 (v0.3.0) - `47b1f57`
The **Verification Reasoning Engine**: a 7-stage pipeline (Evidence Graph
→ Evidence Selection → Rule Evaluation → Hypothesis Generation →
Hypothesis Ranking → Recommendation Generation → Final Report), every
stage independently testable and injectable. `EvidenceSelector` produces a
bounded `WorkingSet`; `ReasoningRule` subclasses emit evidence-cited
`ReasoningSignal`s that only shift ranking, never conclude; a
`HypothesisGenerator` registry produces competing `Hypothesis` objects that
must abstain without evidence; `rank_hypotheses` computes
`final = clamp01(base + Σ signal_contributions) * evidence_factor` with a
full `ConfidenceTrace` recorded per hypothesis; `RecommendationEngine`
produces categorized next steps. Optional `AIReasoner` runs strictly after,
receiving only `build_ai_payload()` (selected evidence + signals +
hypotheses + recommendations), never raw files - pinned by
`tests/test_ai_boundary.py`. `docs/REASONING_ENGINE.md` written.

### Milestone 4 (v0.4.0) - `675c8d0`
**Regression Intelligence**: turns every analysis into historical memory.
New packages, all downstream of reasoning and never imported by it
(architecture test enforces this): `signatures/` (deterministic
`FailureSignature`, stable fingerprint excluding anything volatile),
`storage/` (`RegressionStore`, one SQLite file, full records as JSON blobs
with indexed query columns), `similarity/` (deterministic sparse feature
embeddings + cosine ranking behind an `EmbeddingProvider` seam; signature
matches always score 1.0), `history/` (`HistoryEngine` records runs,
answers "seen before?", and *additively* augments the report - one extra
precedent recommendation, confidence discounted 0.85x from similarity -
never rewriting what reasoning produced), `analytics/` (hotspots, failure
mix, signal frequency, confidence histogram, daily trend, deterministic
signature+embedding clustering via union-find), `feedback/` (interfaces
and storage only - `FeedbackRecord`, no learning implemented, designed so
confirmed root causes immediately improve similarity results and so future
work can reweight recommendations from labeled data), `dashboard/`
(self-contained `dashboard.html`, no JS). CLI gained `--history/--db` on
`analyze` (recording on by default) plus `history`, `dashboard`, `feedback`
commands. Report schema bumped to v4 (`history` field). `docs/
REGRESSION_INTELLIGENCE.md` written.

### Milestone 5 (v0.5.0) - `8df1652` - architecture, initially thin content
The **Verification Knowledge Engine**: structured, versioned, LLM-independent
domain knowledge as a first-class component. `knowledge/model.py` defines
the normalized schema (`Concept`, `ProtocolSignal`, `StateMachine`,
`EvidenceClause`, `FailurePattern`, `DebugPlaybook`, `Reference`,
`KnowledgePack`, all versioned/serializable/metadata-carrying).
`knowledge/registry.py` is the `@register_pack` plugin mechanism.
`knowledge/graph.py` normalizes packs into a **frozen, queryable**
Verification Knowledge Graph (`contains`/`suggests_playbook`/`follows`
edges; `fingerprint()` for immutability proofs). `knowledge/matcher.py` is
pure deterministic clause matching (required/optional/forbidden clauses
against evidence node descriptions) plus state-machine projection ("where
did progress stop?"). `knowledge/inference.py` bridges knowledge into
reasoning: every `FailurePattern` becomes a `KnowledgePatternRule` - a
standard `ReasoningRule` - so matched knowledge contributes evidence-cited
ranking weight through **the exact same interface every built-in rule
uses**; the reasoning engine has zero knowledge dependency (architecture
test enforced). Report schema bumped to v5 (`knowledge` field); report.html
gained a Verification Knowledge section (pattern cards, protocol-sequence
stepper, playbooks, references). Shipped with only 4 packs (axi, uvm,
reset-clocking, coverage; 9 patterns total) - **the user flagged this as
too shallow given the milestone spec explicitly said "every protocol,
every architecture."**

### Milestone 5 follow-up (v0.5.1) - `6d59aad` - knowledge base breadth
Direct response to the user's "very less effort" feedback. Expanded from 4
packs / 9 patterns to **13 packs / 29 patterns / 29 playbooks / 31
concepts / 9 state machines**, with zero changes to the matcher, the
reasoning engine, or the report layer (proof that the M5 architecture
genuinely supports this - the whole diff was pack content plus tests).
New packs: `apb`, `ahb` (AMBA low/high-speed bus), `chi`, `tilelink`
(coherent interconnects), `pcie` (LTSSM/credits/completions), `sva`
(assertion-failure-shape semantics, protocol-agnostic), `cdc` (clock
domain crossing, distinct from reset sequencing), `coherency` (MESI/MOESI
legality, protocol-agnostic), `riscv-privilege` (trap delegation, CSR
access faults). AXI deepened with a write-channel lifecycle FSM plus
write-response and exclusive-access patterns. Two Milestone-5-era patterns
were found to be missing spec references during validation-test
development and were fixed. Added `test_pack_schema_is_well_formed`
(parametrized over every registered pack: regexes compile, confidence
modifiers name real `HypothesisCategory` values, every pattern cites a
reference, every playbook step has a real action, IDs unique within/across
packs) and one fixture + match test per new pattern (11 new fixture logs
under `tests/fixtures/`), proving each pattern fires on realistic evidence
and reaches the reasoning engine as a cited signal, not just loads without
error. 166 tests passing (up from 134).

### Milestone 6 (v0.6.0) - Waveform Intelligence Engine
The reserved `ArtifactType.WAVEFORM_METADATA` (idle since M2) finally has a
producer. New `waveform/` package with the load-bearing split the milestone
demanded: **adapters** are the only format-aware code (`adapters/base.py`
`WaveformAdapter` ABC + capabilities, `adapters/registry.py` `@register_adapter`,
`adapters/manifest.py` for a simulator-independent JSON manifest, `adapters/vcd.py`
for VCD via header parse plus a bounded counter-only activity scan that never
retains transitions), and the **observation engine** (`model.py` normalized
`WaveformMetadata`, `observations.py` deterministic `ObservationDetector`s,
`engine.py` `WaveformEngine`) is format-agnostic: it consumes only normalized
metadata and turns it into engineering observations (dead clock, stalled FSM,
incomplete handshake, unretired transaction, unexpected reset, repeated retries,
sequence-never-started). Observations carry full provenance (detector,
source_adapter, input_signals, deterministic observation_id) and a confidence
that propagates into evidence and hypotheses; each has an `ObservationCategory`.
`waveform/parser.py` `WaveformParser` is an ordinary registered `Parser` (so
`pipeline.analyze()` handles a `.vcd`/`.wave.json` with no pipeline change),
dispatching to the adapter and projecting observations into evidence nodes.
`waveform/inference.py` mirrors the M5 knowledge bridge exactly:
`waveform_reasoning_rules()` wraps each ranking-relevant observation kind as a
standard `ReasoningRule`, and `build_waveform_context()` assembles the
report-facing `WaveformContext`. Additive edits only: one correlation pass
(`_link_waveform_observations_to_failures`) in `graph/builder.py` (links an
observation to a failure sharing a scope segment, making M5 `suggested_signals`
actionable), an optional `waveform` field on `AnalysisReport` (schema `5` -> `6`),
`pipeline.py` composition, a report section, a `waveform` CLI command,
`models/waveform.py` report views. **Adapter capabilities** give honest
degradation: VCD declares no TRANSACTIONS/PROTOCOL_ANNOTATIONS, so those
detectors are reported unavailable rather than silently passing. Two permanent
architecture laws written into `docs/ARCHITECTURE.md` and pinned by tests:
core-format isolation and lossy-by-design ingestion. The crown-jewel test
`test_new_simulator_needs_only_an_adapter` registers a throwaway fake-format
adapter inside the test and proves it reaches evidence, reasoning, and the
report with zero core changes. 28 new tests (189 total, up from 161 actual at
the M5.1 head; note the M5.1 entry's "166" was optimistic, the real count was
161). Design doc: `docs/WAVEFORM_ENGINE.md`. User-approved refinements folded
in: observation provenance, categories, adapter capability declaration,
confidence propagation, and the two laws.

### Milestone 7 (v0.7.0) - Engineering Context Engine
Answers "what changed?" before "what broke?": engineering change becomes one
more normalized evidence source, and VeriTriage grows from a verification
intelligence platform into an engineering investigation platform. New
`engineering/` package with the M6 split applied to tools: **providers** are
the only tool-aware code (`providers/base.py` `ContextProvider` ABC +
`ContextCapability`, `providers/registry.py` `@register_provider` +
`collect_context`, `providers/git.py` local git via subprocess, the platform's
ONLY git call site, `providers/manifest.py` canonical `*.engctx.json` any CI
can export), and everything downstream is tool-agnostic: `model.py` (frozen
`EngineeringContext`: bounded commits with categorized `ChangedFile`s, `CIRun`
with declared `environment_changes`, `Ownership`, `IssueRef`; lossy by design,
no diffs or patch text survive), `context.py` (evidence emission + report view
+ ownership augment), `inference.py` (4 modest-weight `ReasoningRule`s:
RTL/testbench change in failing scope, build-flow change, environment drift
toward INFRASTRUCTURE), `impact.py` (deterministic two-tier test impact:
in-run pure, historical via CLI-mapped `HistoricalRegression` slices; no
storage import), `ownership.py` (routing recommendation only, appended via the
M4 additive-augment seam; never ranking, test-enforced), `timeline.py` +
`investigation.py` (pure projections of the Evidence Graph, never new graphs,
mutation-tested). One new enum member (`ArtifactType.ENGINEERING_CHANGE`),
zero new relation types. Additive edits: correlation pass
`_link_engineering_changes_to_failures`, `analyze(engineering=...)` optional
keyword (CLI gathers via providers with `--context/--no-context`, default on,
degrades silently outside a repo; pipeline stays pure), report schema `6` ->
`7` (`engineering` field), report section, CLI commands `context`,
`investigate`, `impact`. **M4 migration:** `capture_execution_metadata` now
delegates (lazily) to `providers/git.py::execution_snapshot`, so the "no git
outside providers" law holds repo-wide with no grandfather clause. Ownership
and issues deliberately never become graph nodes. Two permanent laws in
`docs/ARCHITECTURE.md` (core-tool isolation; evidence never conclusions),
each test-pinned. Crown-jewel test `test_new_system_needs_only_a_provider`:
a fake Perforce provider defined inside the test reaches evidence,
correlation, reasoning, and the report with zero core changes. 24 new tests
(213 total). CLI tests pin `--no-context` for determinism (they run inside
the real repo). Design doc: `docs/ENGINEERING_CONTEXT_ENGINE.md` (approved
before implementation; scope, git-law migration, and default-on context all
user-confirmed).

### Milestone 8 (v0.8.0) - Verification Workspace & MCP Platform
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

### Milestone 9 (v0.9.0) - Investigation Orchestrator
An orchestration layer that composes existing Workspace Services into complete
investigations; it schedules and observes, never concludes (every technical
conclusion still comes from the deterministic stack, unchanged). New
`orchestrator/` package: `steps.py` (`InvestigationStep` ABC +
`@register_step` + 10 built-in steps, each a thin `WorkspaceServices` call:
gather-context, analyze-artifacts, summarize, historical-lookup,
knowledge-review, waveform-review, engineering-review, build-timeline,
render-report, persist-session), `profiles.py` (`@register_profile` + 7
built-ins: fast-triage, full-investigation, regression-analysis,
protocol-debug, waveform-focused, infrastructure-review, engineering-review;
`build_plan` with deterministic plan IDs), `engine.py` (deterministic Kahn
execution: sorted-id ready frontier = the future-async seam; per-step retry
budget; failure isolation with transitive-dependent SKIP and surviving
independent branches; partial completion; `run_profile`; `resume_profile`
re-runs only non-COMPLETED steps; `attribute_subsystems` maps signals by name
prefix and recommendations by rationale marker to knowledge/waveform/
engineering/history/ownership/rules/reasoning). **Key design decision
(user-approved):** the deterministic pipeline is ONE atomic `analyze-artifacts`
step; per-subsystem visibility comes from trace attribution, NOT from
fragmenting reasoning (which would duplicate it or dismantle the core's
test-pinned composition). Vocabulary in `models/orchestration.py` (frozen
`InvestigationPlan`/`PlanStep`/`StepStatus`/`StepTrace`/`SubsystemAttribution`/
`InvestigationTrace`; `structural_view()` strips timings for determinism
comparison) so the session can reference it while the workspace stays below
the orchestrator. Additive edits only: two workspace service methods
(`gather_engineering_context`, `render_report`; both benefit MCP too), two
optional `InvestigationSession` fields (`plan`, `trace`, attached via
`model_copy` so identity is unchanged: workflow bookkeeping is never
identity), a presentation-only report "Investigation performance" section
(`HtmlReportGenerator.render(metrics=...)`, byte-identical without metrics),
CLI `run`/`profiles` commands, 5 MCP tools (run_investigation, list_profiles,
get_investigation_plan, get_investigation_trace, resume_investigation). No
core engine changed; no report schema change (sessions wrap v7). Architecture
guards: orchestrator-never-bypasses-services (AST: imports only workspace +
models + itself), core-unchanged-by-orchestration (nothing below imports it,
workspace included), plans/traces-immutable, profiles-only-compose-registered
-steps, no-AI, and the crown jewel `test_new_step_needs_only_registration` (a
throwaway step + profile run through the real engine with zero core changes).
18 new tests (256 total). Two implementation deltas from the design, both doc
-noted: models live in models/orchestration.py (layer-neutral), and
regression-analysis ships without a compare-to-precedent step (historical
matches carry regression IDs not session IDs; services.compare stays available
directly). Design doc: `docs/INVESTIGATION_ORCHESTRATOR.md` (approved before
implementation).

### Milestone 10 (v1.0.0) - Collaborative Investigation Platform
The capstone, and the version freeze. Makes investigations portable,
reviewable, reproducible engineering artifacts, and declares the public API
stable. New `collab/` package: `model.py` (frozen `InvestigationBundle` =
session + reviews + annotations + `BundleMetadata`; content-derived `bundle_id`;
sha256 integrity `fingerprint`; `seal_bundle` recomputes both on any amend;
`extra="allow"` for forward compatibility), `exchange.py` (deterministic
canonical JSON + gzip mtime=0 -> `.vtb`; lossless round-trip; auto-detects
compression on import; no raw waveform/log files embedded, only the normalized
session incl. per-node raw_line provenance), `validation.py` (deterministic
`ValidationResult`: schema-major compat, fingerprint recompute, bundle_id/
session_id consistency, dangling-annotation + dangling-edge + dangling-
hypothesis detection, unknown-extension warnings), `review.py` (5 verdicts:
approved/needs_investigation/incorrect_diagnosis/incomplete_evidence/
false_positive; `add_review` returns a new sealed bundle), `annotation.py`
(`@register_annotation_target` registry + 6 built-in kinds: evidence,
knowledge-pattern, waveform-observation, engineering-commit, recommendation,
execution-step; `add_annotation` rejects unknown kinds and dangling targets),
`comparison.py` (explanatory diff across classification/evidence/knowledge/
waveform/engineering/recommendations/trace/metadata with a human summary
sentence). **Reviews and annotations layer on top; the session is never
mutated and reasoning is never affected** (deep-compare tests). Additive
integration only: WorkspaceServices gains bundle methods (export/import/
validate/review/annotate/compare/collaboration_view) that reach collab via
LAZY imports so services stays the boundary with no import-time coupling; an
optional report Collaboration section (`render(collaboration=...)`, plain data,
byte-identical without it); CLI `bundle` sub-app (export/import/validate/
compare) + `review`/`annotate` commands; 7 MCP tools (export/import/validate/
compare_bundles/get_bundle_metadata/list_reviews/list_annotations). No core
engine changed; NO report schema change (collab lives in the bundle, not the
report). collab imports only workspace + models (AST-verified); nothing below
imports collab. Crown jewel `test_new_annotation_target_needs_only_registration`
(a throwaway target kind validates and round-trips with zero core changes). 22
new tests (278 total). Version freeze: pyproject Development Status -> 5 -
Production/Stable; the public API (WorkspaceServices, MCP tool table,
orchestrator step/profile registries, .vtb format) is declared stable. Review
decisions (user-confirmed): ship AS v1.0.0, include raw_line in bundles, one
collab/ package. Design doc: `docs/COLLABORATION_PLATFORM.md` (approved before
implementation).

**As of v1.0.0 the core is complete and stable.** Future milestones are
integrations and ecosystem adoption over existing seams (section 5.8), never
core expansion.

### Knowledge Base Expansion program (post-1.0, content-only)

A user-approved drive to make the Verification Knowledge Engine *elite in
breadth*: grow from 13 packs toward a broad, deep library across four domain
tiers. Every tier is additive content exactly like the M5.1 expansion - new
`knowledge/packs/` modules plus one realistic fixture per pattern - with zero
change to `EvidenceClause`, the matcher, the Knowledge Graph, reasoning, or
the report. Backward compatible; minor-version releases.

- **Tier 1 (v1.1.0) - RISC-V & CPU/ISA depth.** Six new packs beside the
  existing `riscv-privilege`: `riscv-atomics` (LR/SC forward progress, AMO
  aq/rl ordering), `riscv-vector` (illegal vtype, tail/mask undisturbed
  policy, vl element-count), `riscv-memory-model` (RVWMO ordering, FENCE
  enforcement), `riscv-interrupts` (PLIC priority inversion, claim/complete
  gateway, mie/mip masking), `riscv-pmp` (access-fault miss, NAPOT/TOR
  boundary decode), `riscv-debug` (abstract-command cmderr, halt-request
  timeout). 14 new patterns/playbooks, 3 new state machines, 14 fixtures.
  Breadth floors in `test_knowledge.py` raised (>=18 packs, >=40 patterns/
  playbooks/concepts). 19 packs / 44 patterns total; 298 tests (up from 278).
- **Tier 2 (v1.2.0) - Interconnect & NoC.** Five new packs: `axi-stream`
  (TLAST packet framing, backpressure deadlock), `ace` (snoop CR response,
  barrier ordering), `noc` (routing deadlock, credit underflow, HOL blocking
  + packet-lifecycle state machine), `cxl` (Flex Bus negotiation, CXL.mem
  completion), `ucie` (die-to-die training, lane repair/degrade). 11 new
  patterns/playbooks, 1 state machine, 11 fixtures. Floors raised (>=24
  packs, >=55 patterns). 24 packs / 55 patterns / 53 playbooks / 54 concepts;
  314 tests.
- **Tier 3 (v1.3.0) - Memory & Serial IO.** Nine new packs: `ddr` (command
  timing, refresh discipline), `hbm` (channel decode, per-channel refresh),
  `usb` (transaction handshake, USB3 LTSSM), `ethernet` (MAC FCS, PCS block
  lock), `mipi` (D-PHY HS sync, CSI-2 ECC/CRC), `i2c-i3c` (I2C ACK, I3C IBI),
  `spi` (CPOL/CPHA, CS framing), `uart` (framing, RX overrun), `jtag` (TAP FSM
  + IR/DR scan, with a TAP state machine). 18 new patterns/playbooks, 1 state
  machine, 18 fixtures. As planned, only presence-expressible failure modes
  ship; memory-timing SLA and performance patterns still wait on the future
  numeric-clause upgrade (5.1) - each such pack notes this in its docstring.
  Floors raised (>=33 packs, >=72 patterns). 33 packs / 73 patterns / 71
  playbooks / 72 concepts; 341 tests.
- **Tier 4 (v1.4.0) - Methodology & fundamentals depth.** Seven new packs:
  `uvm-ral` (mirror/prediction, field access policy), `uvm-phasing`
  (objection leak, phase order), `uvm-tlm` (port connectivity, analysis
  drop), `formal` (counterexample, vacuous pass, inconclusive bound),
  `low-power` (isolation, retention + the On/Isolate/Retain/Off power-domain
  state machine), `dft` (scan-chain integrity, MBIST signature),
  `x-propagation` (uninitialized-X read, X through control). 15 new
  patterns/playbooks, 1 state machine, 15 fixtures. As flagged: `low-power`
  ships the new power-domain state machine; `formal` reads formal-tool *log
  results* only (native proof-artifact ingestion still wants a dedicated
  ArtifactType, 5.1). Floors raised (>=40 packs, >=86 patterns). Final:
  **40 packs / 88 patterns / 86 playbooks / 86 concepts / 15 state machines**;
  363 tests.

**Knowledge Base Expansion (Tiers 1-4, v1.1.0-v1.4.0).** The engine grew from
13 packs to 40 across six domains (interconnect, CPU/ISA, memory, serial IO,
coherency, methodology/fundamentals) with no change to `EvidenceClause`, the
matcher, the Knowledge Graph, reasoning, or the report - proving the M5
registry architecture scales to elite breadth on content alone.

### Clause expressiveness upgrade (v1.5.0) - the one sanctioned matcher change

The first change to `knowledge/matcher.py` and `EvidenceClause` since M5, and
the single legitimate one flagged in section 5.1. Strictly additive and
backward compatible (the 363 pre-existing tests passed unchanged before any
new pack was added):
- **Numeric clauses.** New `NumericConstraint` (op in gt/ge/lt/le/eq/ne +
  value) on `EvidenceClause.numeric`. The clause's regex locates a number
  (first capture group, else first number in the match) and the node matches
  only when the value satisfies the threshold. Turns "the word latency
  appears" into "latency over 1000 ns".
- **Omission clauses.** New `EvidenceClause.absent`: as a *required* clause it
  is satisfied when NO node matches, a first-class "this expected marker never
  appeared" replacing the old must_fail/pattern="." trick.
- **Unlocked packs.** `performance` (latency/bandwidth SLA misses via numeric
  clauses) and `security` (access-control bypass, unverified secure boot via
  omission clauses) - the two domains named in the M5 spec that presence-only
  matching could not express. Dedicated unit tests pin the numeric boundary
  (fires at 3200 ns, silent at 200 ns) and omission semantics (blocked the
  moment the expected check appears).

Final: **42 packs / 92 patterns / 90 playbooks / 90 concepts / 15 state
machines**; 373 tests. Section 5.1's numeric-comparison and
forbidden-by-omission items are now resolved.

### Native formal-result ingestion (v1.6.0) - the last 5.1 knowledge item

The M5 spec's "formal verification" line item, and the sequencing 5.1 called
for (a new ArtifactType and parser first, the pack on top). Formal tools emit
per-property verdicts, not a simulation log, so this is Evidence-Graph-shaped
(M2) work, kept strictly additive:
- New `ArtifactType.FORMAL_RESULT` (one new enum member, mirroring the M6/M7
  additions). No other core type changed.
- New `parsers/formal_result.py` `FormalResultParser`: a registered `Parser`
  claiming `*.formal.json` (a simulator-independent manifest any formal flow
  can export), normalizing a broad status-alias table (proven / falsified /
  cex / vacuous / inconclusive / covered / unreachable) into one evidence node
  per property. Falsified/vacuous/inconclusive/unreachable are failing; proven/
  covered are informational. Node descriptions are phrased so the existing
  `formal` Knowledge Pack patterns match, so a native run reaches evidence,
  matching, and reasoning with zero pack or reasoning change.
- Registered in `parsers/__init__.py`; `pipeline.analyze()` handles a
  `*.formal.json` like any other artifact (no pipeline change). No report
  schema bump (formal verdicts are evidence nodes + knowledge matches, not a
  new report field). 4 new parser tests (proof the verdicts become evidence,
  aliases normalize, and the native path reaches the pack). 377 tests total.

**5.1 knowledge items are now fully resolved** (numeric clauses, omission
clauses, and native formal ingestion). The knowledge engine is elite in
breadth (42 packs / six domains) and expressiveness (presence, numeric, and
omission clauses, plus native formal artifacts).

### Milestone 11 (v1.7.0) - Verification Project Intelligence (manifest-first)

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

### Milestone 12 (v1.8.0) - Agent Framework and Coordinator

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

### Milestone 13 (v1.9.0) - Learning Engine

The milestone that makes VeriTriage adaptive rather than stateless. New
top-level package `learning/`, a peer of `knowledge/`/`agents/`/`project/`,
positioned above all of them.

**The finding that shaped it:** the regression database was write-rich and
read-poor. It stored complete reports and complete Evidence Graphs and ran
exactly two queries against them (`count_signature`, `find_similar`), whose
total influence on the next run was capped at one appended recommendation.
Stored-but-never-read included: every agent outcome (v1.8.0 records what eight
specialists concluded and nothing asked whether any was right), the
`useful_recommendations`/`false_recommendations` votes M4 designed and left
unbuilt, `diagnosis == "incorrect"`, per-pack utility across 42 packs, project
continuity, and evidence co-occurrence.

**The load-bearing decision:** *learning is a pure function of recorded
history*. Same records plus same feedback yields byte-identical artifacts,
independent of arrival order and of the wall clock. Two mechanical details make
that hold rather than merely be claimed: `Corpus.as_of` supplies artifact
timestamps from the newest recorded run instead of `now()`, and artifact IDs use
content digests rather than builtin `hash()` (which is salted per process and
was caught doing exactly that during implementation).

Structure: `corpus.py` (indexed read-only view; the only thing a learner sees),
`registry.py` (`@register_learner`, batch not incremental, so rebuilds are
idempotent), `learners/` (seven families), `persistence.py` (`LearningStore`, a
**separate** SQLite file so deleting it restores exact pre-M13 behavior),
`calibration.py`, `engine.py` (`observe` / `recall` / `augment`, mirroring
`HistoryEngine.record`/`augment`).

Three guards on calibration: a floor on evidence (`MIN_OBSERVATIONS = 3` judged
runs), a clamp to [0.80, 1.20], and a default of nothing. Applied by the
**Coordinator at merge time, never by an agent**, so an agent still computes the
same position from the same evidence and only its influence moves. Agents gain
memory without gaining a dependency: hints arrive as plain data on
`AgentContext.learning`, and `agents/` never imports `learning/`.

Additive edits only: `AnalysisReport.learning` (schema `9` -> `10`),
`analyze(learning=...)`, `AgentCoordinator(calibration=...)`,
`WorkspaceServices(learning_db=...)` plus six methods,
`investigate(learn=True)`, 6 MCP tools (31 -> 37), CLI `learn` command and
`--learn/--no-learn`, and a report "What Prior Investigations Suggest" section.
No LLM, no embeddings, no vector DB, no ArtifactType, no reasoning change, no
agent rewritten, Regression Intelligence untouched and still authoritative.

44 new tests (487 total). Design doc: `docs/LEARNING_ENGINE.md` (approved before
implementation). Crown jewel `test_new_learner_needs_only_registration`: a
throwaway flakiness learner defined in the test reaches the store, the
statistics, and the recall path with zero core changes. Notable: an agent-memory
test caught that recurring patterns only arrived in `augment()` (after agents
ran), defeating the intended "agents receive historical context before
execution" flow; fixed by recalling all investigation patterns up front, with
`augment` promoting the signature-specific match.

Deferred to M13.x: learned embeddings behind the existing `EmbeddingProvider`
seam; a learning-aware dashboard section; recommendation reranking from
`RecommendationOutcome` (the artifacts exist, the reranker does not).

### Milestone 14 (v1.10.0) - Planning Engine

The milestone that moves VeriTriage from explaining failures to planning
investigations. New top-level package `planning/`, above learning, below the
pipeline. It is the only layer that answers "what should happen next?".

**The critical evaluation that changed the milestone's shape.** The requested
artifact names collided with frozen M9 public API: `InvestigationPlan`
(models/orchestration.py, exported from `veritriage.models`, embedded in
`InvestigationSession.plan` and therefore inside every `.vtb` bundle),
`InvestigationStep` (the orchestrator step ABC), and `PlanStep`. The conceptual
clash mattered more than the collision: **M9's plan is what the platform will
run; M14's plan is what the engineer should do.** Machine workflow versus human
debug strategy. Adopted `DebugPlan` / `DebugStep` / `StepSource` instead, and
pinned the separation with `test_planning_does_not_collide_with_m9_orchestration`.

Two further design changes adopted before coding:
- **Agents needed no change at all.** The spec asked for agents to "recommend
  planning steps", which would have meant editing the frozen `Agent` ABC. But
  agents already emit `AgentRecommendation` and the Coordinator already merges
  them, so planning just reads `report.agents.recommendations`. Zero agent
  edits.
- **The Planner must not invent advice.** Every `DebugStep` is *derived* from an
  existing artifact and names it in `derived_from`. Otherwise the platform grows
  an unaudited advice generator on top of five audited layers. Same move as M12
  (agents aggregate, never extract) and M13 (learning aggregates, never decides).

**The load-bearing decision:** the Planner contributes structure, ordering,
branching, and valuation; never content. `StepCandidate` deliberately has no
priority field, so a source physically cannot rank itself.

Structure: `context.py` (`PlanningContext` + `StepCandidate`; `competing()`
decides which explanations are still live, by absolute margin OR ratio to the
leader), `registry.py` (`@register_source`, ordered by `rank` so curated
knowledge outranks generic templates), `sources/` (knowledge playbooks, agent
recommendations, reasoning recommendations, evidence gaps), `valuation.py`
(`value / effort` with every term recorded), `tree.py` (decision points, AUTO
conditions settled from the graph, ASK conditions left open; risks; completion
conditions), `progress.py` (pure function of plan plus graph, no store),
`engine.py` (`Planner`: gather, deduplicate, value, order, branch).

Learning contributes priority only, bounded to +/-0.5 and recorded in the
valuation. Project Intelligence shapes strategy and removes the "no project
model" risk. Planning never executes: no I/O, no subprocess, no tool call.

Additive edits only: `AnalysisReport.plan` (schema `10` -> `11`),
`analyze(plan=True)`, `investigate(plan=True)`, five WorkspaceServices methods,
6 MCP tools (37 -> 43), CLI `plan` command and `--plan/--no-plan`, and a report
"Recommended Investigation" section. `reasoning.recommendations` untouched.

47 new tests (534 total). Design doc: `docs/PLANNING_ENGINE.md` (approved before
implementation). Crown jewel `test_new_step_source_needs_only_registration`: a
throwaway emulation source defined in the test is deduplicated, valued, ordered,
leads the plan on merit, and reaches the report with zero core changes. Two
things caught during implementation: the `competing()` ratio was initially 0.6
and never branched on a realistic 0.65/0.38 spread (fixed to 0.5); a guard
test banned the substring `requests.` which false-positived on a local list
variable (fixed to check imports via AST); and the first decision trees offered
*identical* steps on both branches, which makes a branch pointless (fixed by
assigning branch steps greedily, most category-specific first, never reusing a
step across outcomes; pinned by `test_branches_give_different_advice`).

Deferred to M14.x: interactive planning (observations fed back into ASK
conditions); a `plan` orchestration step; plan diffing across runs; VS Code
plan rendering.

### Milestone 15 (v1.11.0) - Design Intelligence

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

### Milestone 16 (v1.12.0) - Conversation Engine

The milestone that turns a static report into something an engineer can
interrogate. New top-level package `conversation/`, above every intelligence
layer, below `workspace/`. It is the only layer that owns no intelligence at
all.

**The critical evaluation that reframed the milestone.** The spec read as "add
a way to ask questions", but VeriTriage *already had* a question-answering
layer: 51 MCP tools, ~40 WorkspaceServices methods, `workspace/navigation.py`
(address one object by ID) and `workspace/search.py` (substring match). Each
answers exactly one question completely, then forgets everything. Four things
were actually missing: **composition** (follow-ups require restating
everything), **navigation state** (no current hypothesis/module/filter),
**cross-layer joins** (evidence -> hypothesis -> agent -> plan step is four
calls and a manual correlation the report performs, renders, and discards), and
**a uniform answer contract**. M16 supplies those four and reimplements no
existing query.

Two further corrections adopted before coding:
- **Honest parsing.** The non-goal says "do not create natural language" while
  the examples are English sentences. Resolved by making the canonical question
  a structured object and the parser a *declared, finite vocabulary* matcher
  (keyword/regex, in the spirit of the M5 clause matcher). Out-of-vocabulary
  input returns an honest miss listing what *can* be asked, never a nearest
  guess. This is exactly what makes a future LLM a **translator** producing
  `Question` objects, never an owner of answers.
- **No new store.** `ConversationSession` is serializable and handed back to
  the caller. Navigation state is not intelligence; a sixth SQLite file for
  "which hypothesis am I looking at" would be storage for nothing.

**The load-bearing decision:** conversation navigates, it never concludes.
Enforced rather than trusted: `ConversationEngine._verify` strips any citation
that does not resolve to a real artifact and records the omission, so a handler
that invents a node ID cannot reach a client.

Structure: `context.py` (`ConversationContext` + the *only* sanctioned reference
builders, each returning None when the artifact is absent), `registry.py`
(`@register_handler`, one per intent), `parse.py` (declared vocabulary),
`handlers/` (explain/why/why_not, show_evidence/filter,
navigate/summarize/help, trace/compare), `engine.py`.

Ten intents. `Answer.followups` is what makes navigation possible without
prose: each answer names the questions it has made available.

Additive edits only: two WorkspaceServices methods, 8 MCP tools (51 -> 59), a
CLI `ask` command. **No report schema bump**: conversation is live interaction
over a finished report, not a new report field, which is itself the clearest
statement of what this layer is.

34 new tests (609 total). Design doc: `docs/CONVERSATION_ENGINE.md` (approved
before implementation). Crown jewel `test_new_intent_needs_only_registration`.
Caught during implementation: `summarize design` lost its target because no
pattern captured the noun after an intent verb, fixed by adding a verb-plus-noun
extractor.

Deferred to M16.x: an LLM translator producing `Question` objects; a VS Code
conversation panel; Slack threading over serialized `ConversationSession`s.

### Milestone 17 (v1.13.0) - Generative AI providers

The milestone that introduces LLMs without letting them near a conclusion. New
top-level package `ai/`, above `conversation/`, below `workspace/`. It owns
provider integration and no verification intelligence.

**The critical evaluation that simplified the milestone.** The spec asked for
`ai/LLMProvider` as a fresh abstraction, but M12 had already shipped
`agents.ReasoningProvider` with NullProvider, DeterministicProvider, a registry,
and a documented promise that a vendor is "one class plus one registration". A
parallel registry would have meant two registries, two NullProvider semantics,
two config paths, and two places to register Anthropic.

But the M12 seam genuinely could not carry M17: it is **agent-shaped**
(`elaborate(ProviderRequest with agent_id/domain/observations/hypotheses)`),
with no way to ask for a project digest or a design walkthrough.

**Adopted design:** `ai/` owns ONE `LLMProvider` shaped like a *vendor* (frozen
prompt in, text out) rather than like a use case. The M12 contract stays frozen
and untouched, and `ai/adapters.LlmReasoningProvider` satisfies it by delegating
to an `LLMProvider`. Registering a vendor once therefore serves both agent
narration and every renderer. Pinned by
`test_the_m12_contract_is_untouched` (agents/providers.py must not mention
veritriage.ai).

**The load-bearing decision:** providers render, never reason. A provider's
entire input is a frozen `Prompt`: no path, no store, no service, no graph, no
report. "Read-only" therefore holds by construction, because a provider has
nothing to mutate anything with.

**Grounding is enforced, not requested.** The `Prompt` declares its citation
set; `grounding.enforce()` scans the response and strips any token outside it,
recording the omission. Deterministic, and no model is needed to check a model.
Same pattern as the M12 Coordinator `_verify` and the M16 Conversation `_verify`.
Tested against a `MockProvider` that deliberately invents citations.

Structure: `provider.py` (LLMProvider Protocol + BaseProvider whose `generate`
returns failures rather than raising), `registry.py`
(`@register_llm_provider`; named apart from M12's `register_provider`),
`providers/` (null, deterministic-echo, mock, reference), `prompt.py`
(PromptTemplate/PromptContext/PromptBuilder + 7 versioned templates; building is
pure and the prompt is inspectable), `grounding.py`, `renderers.py` (7 named
views, an enumerable closed list), `adapters.py` (the M12 bridge), `service.py`
(AIService: selection, capability discovery, health, degradation).

Additive edits only: five WorkspaceServices methods, 6 MCP tools (59 -> 65), CLI
`render` and `providers` commands. **No report schema bump**: generated prose is
a view, never a report field.

**Honest note carried in the docs:** `reasoning/ai.py` (M3 `AIReasoner`) is the
only file in the repo importing a vendor SDK and hardcoding a model name. The
non-goal forbade changing reasoning, so it stays and keeps working via
`analyze --ai`. It is now explicitly the *legacy* path, superseded by `ai/`;
saying so in AI_PROVIDERS.md rather than leaving it as a trap.

38 new tests (647 total). Design doc: `docs/AI_PROVIDERS.md` (approved before
implementation). Crown jewel `test_new_provider_needs_only_registration`: a
throwaway ACME vendor defined in the test renders, has its hallucinated citation
stripped by the same enforcement as every built-in, appears in discovery
honestly declaring it is not local, and serves the M12 agent seam through the
same registry. Caught during implementation: the vendor-SDK guard matched vendor
names in a docstring listing *future* integrations, fixed by checking imports
via AST rather than substrings (the same false-positive class as M14's
`requests.`).

Deferred to M17.x: actual vendor integrations (OpenAI, Anthropic, Google, local
models, MCP-hosted); per-provider grounding reliability aggregated by the
Learning Engine via `grounding.grounded_ratio`; retiring `reasoning/ai.py` in
favour of an `ai/` provider.

### Milestone 18 (v1.14.0) - Automation Engine

The milestone that makes VeriTriage event-driven. New top-level package
`automation/`, a peer of `planning/`, importing **only `models`**.

**The critical evaluation that forced the shape.** Two facts:
1. **M9 already owns execution.** The proposed action list (run analysis,
   generate report, summarize changes, ...) maps almost one-to-one onto the
   orchestrator's ten registered steps, and M9 already ships DAG scheduling,
   retries, failure isolation, and a trace. A second action registry would sit
   beside a proven one.
2. **The layering forbids it anyway.** `orchestrator/` imports `workspace/`, so
   an `automation/` that executed would sit above the orchestrator and the
   workspace could not then consume it without a cycle.

**Adopted design:** automation **decides, never executes**. It publishes
events, evaluates triggers, fires rules, and emits `ActionRequest` objects
naming capabilities the workspace already has; the workspace dispatches them to
its own methods. Consequences: no third registry, the non-goals (no
simulations/CI/webhooks/OS jobs) hold *by construction* because there is no I/O
in the package at all, and nothing is inverted.

**Why events are immutable:** replay, ordering, and audit are only meaningful if
the log cannot have changed since it was written. Frozen models, content-derived
`event_id`, monotonic sequence assigned by the bus.

**The bus** is synchronous (no threads, queues, async, or hidden callbacks),
ordered, replayable, filterable, and bounded with drops reported. A broken
subscriber is isolated.

**Scheduling**, which the requirements asked for and the non-goals forbade, is
resolved honestly: a `schedule_tick` event a *caller* publishes (CI job, cron
someone else owns, future daemon). The platform never sleeps, spawns, or polls.

Structure: `bus.py` (EventBus), `triggers.py` (@register_trigger + 10 built-in
conditions), `rules.py` (RuleEngine; rules are a trigger ID plus a tuple of enum
members, with registration *failing* if the trigger is unknown rather than
silently never firing), `builtin.py` (6 shipped rules).

Additive edits: `AnalysisReport.automation` (schema `12` -> `13`, appended by
the workspace after analyze exactly as history is), `investigate(automate=True)`,
seven WorkspaceServices methods, 7 MCP tools (65 -> 72), CLI `automation`
command, and a report Automation section.

37 new tests (684 total). Design doc: `docs/AUTOMATION_ENGINE.md` (approved
before implementation). Crown jewel `test_new_trigger_needs_only_registration`:
a throwaway coverage-drop trigger plus one rule fires on a caller-published
event, its requests reach the workspace dispatcher and execute, and it declines
cleanly when the condition does not hold.

**Real bug found and fixed on the way:** M13's `AgentReliabilityLearner` cited
supporting regressions only for runs where an agent *led*, so an agent that was
applicable but never led produced an artifact with `observations > 0` and no
provenance, violating M13's own "everything links back" law. Latent until
automation's `REFRESH_LEARNING` action changed which agents became applicable.
Fixed to cite on applicability.

Deferred to M18.x: a CI adapter publishing events from GitHub Actions/Jenkins;
Slack and VS Code subscribers; a `due()` evaluation for schedule ticks.

### Milestone 19 (v1.15.0) - IP Nirmaan: the Organizational Operating System

The user named the larger vision **IP Nirmaan**: an AI-native semiconductor IP
company in which a requirement goes in and an organization plans, owns,
reviews, gates, and evidences the work. VeriTriage becomes its verification-
intelligence subsystem. This milestone delivers the spec's Phases 1-3 in full,
the Phase 4 runtime interface, and a thin but real Phase 5 bridge.

**Placement decision.** A sibling top-level package `src/nirmaan/` in the same
distribution (`nirmaan` CLI entry point), not growth inside `veritriage/`.
Two AST-enforced laws: VeriTriage never imports Nirmaan; only
`nirmaan/integrations/veritriage.py` imports VeriTriage (through
`WorkspaceServices` and the Knowledge Pack registry). The M9 Kahn engine, M18
event bus, and M10 reviews were evaluated and deliberately not reused (each is
verification-specific; bending them would couple VeriTriage to Nirmaan). The
42 Knowledge Packs ARE reused: skills cite them by ID, never duplicating
protocol knowledge (`missing_packs()` proves every citation resolves).

Structure:
- `models/` (frozen vocabulary; imports only pydantic)
- `company/` (the IP Nirmaan definition as data: org chart, 140 skills, 97
  capabilities, 38 tools with AVAILABLE/CONTRACT_ONLY status, authority
  matrix, escalation routes, 6 gates, 12-article constitution, 7 workflows,
  requirement vocabulary)
- `org/` (builder that DERIVES 685 roles from unit kinds, immutable
  `Organization` with memoized queries, validation, authority service,
  escalation routing)
- `orchestrator/` (analyze, router, planner)
- `work/` (TaskEngine, policy checks, hash-chained audit, blockers,
  management, trace graph, store)
- `runtime/` (AgentRuntime protocol, NullRuntime, ScriptedRuntime, work
  packets with four separate knowledge scopes, ToolBroker)
- `integrations/veritriage.py`, `views.py`, `dashboard.py`, `demos.py` (7
  demos), `cli.py`

Key design points worth not re-deriving:
- Staffing is derived: division->VP, department->Director,
  team->Manager+Tech Lead, leaf->IC ladder (override inherits down).
- Escalation rises one rung at a time (spec chain verified by test).
- Proficiency is derived from level; signoff capabilities also need a
  `min_level`; tools flow from skills (execute/write need WORKING).
- Routing is a scored join, and a test forbids domain literals in
  `orchestrator/`. The score weighs stage skills, then unit specialty
  (distance-decayed), then capped requirement-context skills, then level fit.
- Un-reviewable work is planned BLOCKED, never a silent deadlock.
- Evidence requirements name the tools whose runs count, so a lint
  requirement cannot be met by an unrelated tool run.
- Every mutation passes the state machine, authority, and constitution, then
  one audit entry; P10 detects state changed outside the engine by
  fingerprint.

Real bugs found by the validator and tests on the way:
- staff escalating down to a tech lead
- `rtl.impact` held by nobody
- ladder overrides not inheriting
- the only `debug.review` holder being the owner
- a trace-graph keyword collision
- `division_of` returning the company for top-level departments

170 new tests across 6 files (`tests/test_nirmaan_*.py` +
`nirmaan_helpers.py`). Crown jewel
`test_a_new_engineering_domain_needs_only_an_extension` adds silicon photonics
(unit, skill, capabilities, tool, feature, intent, workflow) through one
`@register_extension` and plans owned, reviewed, gated work into it. The
end-to-end test drives the 55-task AXI-to-NoC bridge project to COMPLETED
under the real rules. Design doc: `docs/NIRMAAN_ORG_OS.md` (includes the
architecture assessment and the extension guide).

---

## 3. Current architecture map

```
src/veritriage/
  models/           Pydantic vocabulary shared by every layer (events, evidence,
                     failure, reasoning, history, knowledge, report). Must never
                     import veritriage.graph at runtime (graph imports models).
  graph/             EvidenceGraph, EvidenceNode/Edge, GraphBuilder + correlation
                     passes, to_reasoning_view() (the AI boundary).
  parsers/           Parser ABC + registry (@register), one module per artifact
                     type: simulation_log, compile_log, coverage, test_metadata,
                     formal_result (*.formal.json -> FORMAL_RESULT evidence, v1.6.0).
  rules/             Graph-native deterministic classification rules.
  reasoning/         The M3 pipeline: selection, signals, hypotheses, recommend,
                     ai.py (AIReasoner), engine.py (orchestrator). Zero knowledge
                     or history dependency - architecture tests enforce this.
  knowledge/         M5: model.py (schema), registry.py (plugin table), packs/
                     (13 built-in modules), graph.py (frozen KG), matcher.py
                     (deterministic matching + projection), inference.py
                     (KnowledgeEngine + KnowledgePatternRule reasoning adapter).
  waveform/          M6: model.py (normalized WaveformMetadata + observations),
                     adapters/ (base+registry+manifest+vcd; the ONLY format-aware
                     code), observations.py + engine.py (format-agnostic detectors),
                     parser.py (WaveformParser: Evidence Graph seam), inference.py
                     (waveform_reasoning_rules + build_waveform_context). Never
                     imported by reasoning; architecture tests enforce isolation.
  engineering/       M7: model.py (frozen EngineeringContext + capabilities),
                     providers/ (base+registry+git+manifest; the ONLY tool-aware
                     code, and the only git call site in the platform),
                     parser.py (*.engctx.json artifact seam), context.py
                     (evidence emission + view + ownership augment), inference.py
                     (engineering_reasoning_rules), impact.py (two-tier test
                     impact), ownership.py (routing only), timeline.py +
                     investigation.py (pure graph projections). Never imported
                     by reasoning; architecture tests enforce isolation.
  workspace/         M8: session.py (immutable InvestigationSession), services.py
                     (WorkspaceServices, THE public API every client consumes),
                     persistence.py (session bundles), navigation.py (addressable
                     report sections), search.py (deterministic search). Imports
                     the core; NOTHING in the core imports it (guard-enforced).
  mcp/               M8: tools.py (transport-agnostic tool table over services,
                     72 tools incl. 5 M9 orchestration, 7 M10 collaboration,
                     4 M11 project, 3 M12 agent, 6 M13 learning, 6 M14 planning,
                     8 M15 design, 8 M16 conversation, 6 M17 AI, and 7 M18
                     automation tools; register_tool extension point), server.py
                     (dependency-free MCP stdio JSON-RPC transport). Serve with
                     `veritriage mcp`.
  orchestrator/      M9: steps.py (InvestigationStep + register_step + 10 built-in
                     steps), profiles.py (register_profile + 7 profiles +
                     build_plan), engine.py (deterministic execution, trace,
                     attribution, run_profile + resume_profile). Imports ONLY the
                     workspace + models vocabulary; nothing below imports it.
  collab/            M10: model.py (frozen InvestigationBundle + fingerprint),
                     exchange.py (.vtb export/import), validation.py, review.py,
                     annotation.py (register_annotation_target + 6 kinds),
                     comparison.py (explanatory diff). Imports ONLY workspace +
                     models; nothing below imports it. Reached via WorkspaceServices
                     (lazy import); clients never import collab directly.
  history/           M4: record.py (RegressionRecord + git metadata capture),
                     engine.py (HistoryEngine: record + additive augment).
  signatures/        M4: deterministic FailureSignature + digest.
  similarity/        M4: FeatureEmbedding, cosine, SimilarFailureEngine.
  storage/           M4: RegressionStore (SQLite; also implements FeedbackSink).
  analytics/         M4: RegressionAnalytics (aggregations) + cluster_regressions.
  feedback/          M4: FeedbackRecord + FeedbackSink protocol (design only).
  dashboard/         M4: DashboardGenerator (self-contained dashboard.html).
  project/           M11: model.py (frozen ProjectModel + merge + fingerprint),
                     providers/ (base+registry+manifest; the ONLY source-aware code,
                     *.vproj.json ships first), insights.py (protocol ID via knowledge
                     markers), lifecycle.py (lifecycle projection), logmap.py (log
                     intelligence via the parser registry), inference.py
                     (project_reasoning_rules + build_project_view), persistence.py
                     (ProjectStore). A separate, cached model that NEVER enters the
                     Evidence Graph; a lens over it. Reaches reasoning as injected
                     rules; nothing in the core imports it (guard-enforced).
  agents/            M12: context.py (frozen AgentContext: the ONLY agent input,
                     carries normalized evidence + lenses and no path), base.py
                     (Agent ABC + contract-enforcing builder), registry.py
                     (@register_agent), providers.py (ReasoningProvider Protocol +
                     NullProvider + DeterministicProvider: the Deterministic/
                     Generative boundary; zero API-calling providers ship),
                     coordinator.py (invoke/merge/conflict/cross-check), builtin/
                     (8 specialists). Sits ABOVE reasoning and every lens; imports
                     only models, graph, knowledge. Nothing below imports it
                     (guard-enforced). Never mutates the graph or ReasoningResult.
  learning/          M13: corpus.py (indexed read-only view over recorded history;
                     `as_of` supplies the corpus clock so purity holds), registry.py
                     (@register_learner; batch, so rebuilds are idempotent),
                     learners/ (7 families), persistence.py (LearningStore, a SEPARATE
                     SQLite file; deleting it restores exact pre-M13 behavior),
                     calibration.py (bounded, floored, explainable), engine.py
                     (observe/recall/augment). Sits ABOVE agents; imports only models
                     plus the history/feedback record vocabulary. Nothing below imports
                     it, and agents/ in particular does not: hints reach agents as plain
                     data on AgentContext (guard-enforced).
  planning/          M14: context.py (PlanningContext + StepCandidate, which has NO
                     priority field so a source cannot rank itself), registry.py
                     (@register_source, rank-ordered), sources/ (knowledge playbooks,
                     agent recs, reasoning recs, evidence gaps), valuation.py
                     (value/effort, every term recorded), tree.py (decision points:
                     AUTO settled from the graph, ASK left open; risks; completion),
                     progress.py (pure function, no store), engine.py (Planner).
                     Sits ABOVE learning; imports only models and graph. Never
                     executes and never invents advice: every step names the artifact
                     it restates. Vocabulary deliberately distinct from M9
                     orchestration (DebugPlan vs InvestigationPlan).
  design/            M15: model.py (DesignNode/DesignEdge/DesignGraph, content-hashed
                     IDs, node merging so extractors stay independent), registry.py
                     (@register_extractor, order-ranked), extractors/ (6 built-in),
                     builder.py, query.py (DesignQuery: the structural questions),
                     inference.py (report view). THE THIRD GRAPH: evidence is what
                     happened, knowledge is what is generally true, design is what the
                     system IS. Derived from the Project Model, NEVER from source
                     (guard-enforced); imports no provider; nothing below imports it.
  conversation/      M16: context.py (ConversationContext + the ONLY sanctioned
                     reference builders), registry.py (@register_handler, one per
                     intent), parse.py (declared vocabulary; honest miss, never a
                     guess), handlers/ (10 intents), engine.py (ask/verify/record).
                     Owns NO intelligence: it navigates, never concludes. Never
                     imports workspace/ (the workspace exposes conversation, not the
                     reverse); persists nothing. Guard-enforced.
  ai/                M17: provider.py (LLMProvider Protocol + BaseProvider), registry.py
                     (@register_llm_provider; ONE vendor registry for the platform),
                     providers/ (null=default, deterministic-echo, mock, reference;
                     none calls an API), prompt.py (versioned templates; building is
                     pure, prompts are inspectable before generation), grounding.py
                     (strips citations the prompt did not authorize), renderers.py
                     (7 named views), adapters.py (LlmReasoningProvider: the frozen
                     M12 seam delegating here), service.py (selection/health/
                     degradation). Owns NO verification intelligence. Providers get a
                     frozen Prompt and nothing else, so read-only holds by
                     construction. conversation/ stays AI-free (guard-enforced).
  automation/        M18: bus.py (EventBus: ordered, synchronous, replayable, bounded;
                     a broken subscriber is isolated), triggers.py (@register_trigger
                     + 10 built-ins; pure functions of an event), rules.py (RuleEngine;
                     rules are structured data, and registration FAILS on an unknown
                     trigger rather than silently never firing), builtin.py (6 rules).
                     Imports ONLY models. Performs no I/O and imports no scheduler,
                     subprocess, socket, or thread: it decides, the workspace executes.
                     Nothing below imports it (guard-enforced).
  reports/           HTML report generator (Jinja2, self-contained, light/dark).

src/nirmaan/         M19: IP Nirmaan, the organizational OS ABOVE VeriTriage (sibling
                     package; `nirmaan` CLI). models/ (plain data), company/ (the
                     company as data), org/ (derived staffing, validation, authority),
                     orchestrator/ (analyze, route, plan), work/ (TaskEngine, policy,
                     audit, blockers, management, trace, store), runtime/ (agent
                     interface + tool broker), integrations/veritriage.py (the ONLY
                     VeriTriage import site). VeriTriage never imports it.
  cli/main.py        Typer app: analyze, parsers, knowledge, waveform, context,
                     project, dut, env, flow, explain, investigate, impact, mcp, sessions, run,
                     profiles, bundle (export/import/validate/compare), review,
                     annotate, dashboard, history, feedback, version. Since M8 a
                     WorkspaceServices client (never imports veritriage.pipeline); M9
                     run/profiles drive the orchestrator; M10 bundle/review/annotate
                     drive collaboration; M11 project/explain drive project intelligence.
  pipeline.py        analyze(): parse -> graph -> classify -> knowledge -> reason.
                     Waveform artifacts and context manifests parse like any other
                     (registered Parsers); waveform + engineering + project reasoning
                     rules join the rule set beside knowledge rules; the Agent
                     Coordinator runs last over the finished report;
                     build_waveform_context, build_engineering_view, and (when a model
                     is supplied) build_project_view fill the report; ownership augment
                     appends last. analyze(engineering=..., project=...) accepts
                     CLI-collected context/model so the library stays pure, no provider
                     or storage I/O (context/model gathering and history recording are
                     CLI decisions).
```

**Pipeline call order** (`pipeline.py::analyze`): parsers emit graph
fragments → `GraphBuilder` merges + correlates → `RuleEngine.classify()` →
`KnowledgeEngine.analyze()` computes the `KnowledgeContext` →
`ReasoningEngine(rules=[*default_reasoning_rules(), *knowledge_reasoning_rules(), *waveform_reasoning_rules(), *engineering_reasoning_rules(), *project_reasoning_rules(project) if project else []])`
runs selection/signals/hypotheses/ranking/recommendations, with knowledge
patterns, waveform observations, engineering changes, and (when a model is
supplied) project intelligence all injected as ordinary rules → `AnalysisReport`
assembled (`schema_version = "8"`, `waveform` field via `build_waveform_context`,
`engineering` field via `build_engineering_view`, `project` field via
`build_project_view`). History recording (`HistoryEngine.record` +
`.augment`) happens in the CLI, strictly after `analyze()` returns, so the
library function itself never touches the filesystem beyond reading the
input artifacts.

**Report schema version history:** v1 (M1) → v2 adds Evidence Graph (M2) →
v3 adds `reasoning` (M3) → v4 adds `history` (M4) → v5 adds `knowledge`
(M5) → v6 adds `waveform` (M6) → v7 adds `engineering` (M7) → v8 adds
`project` (M11) → v9 adds `agents` (M12) → v10 adds `learning` (M13) →
v11 adds `plan` (M14) → v12 adds `design` (M15) →
v13 adds `automation` (M18). Bump on any breaking field change; tests assert the current
value (`test_cli.py`).

**Current test count: 854** (684 VeriTriage + 170 IP Nirmaan), across `tests/test_*.py`: parsers, rules,
graph, artifact parsers, models, report, CLI, AI boundary, reasoning,
history, analytics, knowledge, waveform, engineering, workspace/MCP,
orchestrator, collaboration, project, agents, learning, planning, design,
conversation, ai, automation. Run with `.venv/bin/python -m pytest -q`
from the repo root.

---

## 4. Operational notes for resuming work

- Python 3.11 venv at `veritriage/.venv/`; rebuild after any repo move or
  rename (`python -m venv .venv && .venv/bin/pip install -e ".[ai,dev]"`).
- CLI entry point: `.venv/bin/veritriage`. Default regression DB path:
  `.veritriage/regressions.db` (gitignored, override with `--db`).
- Fixtures live in `tests/fixtures/`; add a new one whenever a new
  Knowledge Pack pattern needs proof it fires on realistic evidence rather
  than only passing schema validation.
- The Anthropic integration (`reasoning/ai.py`) uses `claude-opus-4-8` with
  `thinking={"type": "adaptive"}` and structured JSON output; it's an
  optional extra (`pip install ip-nirmaan[ai]`) and degrades gracefully
  (warns, continues deterministic-only) if the SDK or API key is missing.
- Portfolio: no longer integrated. The project card and sample pages were
  removed from `patel-om/portfolio` after M19; do not refresh them per
  milestone unless the user asks to bring the project back.
- Package naming history: TraceIQ (M1, collided with existing PyPI/products)
  → briefly considered "verifAI" (collided with Berkeley's VerifAI) →
  renamed to **VeriTriage** at M2/M3 boundary (GitHub redirect preserved
  from the rename). After M19 the user renamed the PROJECT, first to "Nirmaan IP"
  (repo `nirmaan-ip`, v1.16.0) and then, to match the `ipnirmaan.com` domain, to
  **IP Nirmaan** (repo `patel-om/ip-nirmaan`, distribution `ip-nirmaan`, v1.16.1).
  On 2026-09-28 the repo was transferred to `nirmaansoftware/ip-nirmaan`.
  The `nirmaan` package and CLI keep their short name by the user's choice. VeriTriage
  was deliberately NOT renamed: it is the verification engine inside Nirmaan
  IP, and the user wants its technology kept and built on, with the platform
  now "bigger than just a verification tool". The `veritriage` package, CLI,
  MCP server, and `.veritriage/` data directory keep their names. Never
  suggest renaming again without the user raising it.
- Domain (final, for now): **`ip.nirmaan.online`**, a subdomain of the user's
  existing software-services domain. No new domain is being purchased. The
  brand stays **IP Nirmaan** (it was renamed to match `ipnirmaan.com`, which the
  user may still buy later). Do not add the URL to project metadata until the
  subdomain actually serves a page.
- Portfolio: the user removed this project from `/Users/ompatel/Documents/Om Portfolio`
  (card and sample pages deleted after M19). Do not refresh portfolio artifacts
  per milestone any more unless the user asks. Do not put
  a domain into project metadata until the user confirms they own it.
- **iCloud eviction (discovered at M19).** The repo lives in iCloud-synced
  `~/Documents` with storage optimization on, and macOS evicts files to
  "dataless" placeholders, including freshly written `.py` and `.pyc` files.
  Reads then block until iCloud re-downloads them (about 1s per file), which
  shows up as tests hanging inside `importlib` `get_data` (the old 13-minute
  `test_ai_boundary.py` stall was this). Workarounds: run tests with
  `PYTHONPYCACHEPREFIX` pointing outside iCloud, pre-read the tree
  (`find src tests -flags +dataless -type f -print0 | xargs -0 cat >/dev/null`),
  or move the repo out of `~/Documents` / mark it "Keep Downloaded".
- Standing unexecuted offer: publish an initial release to PyPI to reserve
  the `veritriage` package name. Not done; requires explicit confirmation
  before acting (irreversible-ish - name squatting disputes are a hassle).

---

## 5. Future work

This section is intentionally detailed - it's the answer to "what's left"
for whoever (human or agent) picks this up next. Nothing here should be
started without the user asking for it; this is a map, not a queue.

### 5.1 Knowledge Engine - more packs (natural continuation of the M5 fix)
The M5 follow-up covered the milestone's explicit list. Real breadth still
missing, in likely priority order for a DV audience:
- **AXI-Stream and ACE/ACE-Lite** (cache-coherent AXI extensions) - natural
  sibling to the existing AXI pack; ACE shares failure-pattern shape with
  the `coherency` pack (illegal snoop responses, barrier ordering).
- **OCP, Wishbone** - older but still-used open interconnects; low effort,
  same pattern-library shape as APB/AHB.
- **UCIe / die-to-die interconnect** - increasingly relevant for chiplet
  designs; would need new concepts (link training analogous to PCIe LTSSM,
  but for die-to-die).
- **Power management / UPF-aware sequencing** - power domain
  sequencing violations (isolation before power-down, retention timing)
  are a distinct enough failure class to warrant concepts + a state
  machine (power domain lifecycle: On → Isolate → Retain → Off).
  This is genuinely new territory (not just "another protocol"); think
  through the state machine before writing patterns.
- **Security verification** (side-channel timing hints, access-control
  bypass patterns) - mentioned explicitly in the M5 spec, not yet started.
  Needs care: security failure signatures in a sim log are often *absence*
  of an expected check firing, which the current matcher (presence-based
  clauses) handles awkwardly; may need a new clause type ("expected marker
  never appears" as a first-class forbidden-by-omission clause rather than
  today's `must_fail` workaround).
- **Performance verification** (bandwidth/latency SLA misses) - also
  named in the spec. Needs a new evidence shape (numeric threshold
  comparison, not just regex presence) - likely needs `EvidenceClause` to
  grow a numeric-comparison variant, which *is* a matcher change (the one
  legitimate reason to touch `knowledge/matcher.py` rather than just add a
  pack). Worth flagging to the user before starting since it's the first
  extension that isn't purely additive.
- **Formal verification result ingestion** - the M5 spec's "formal
  verification" line item. This is bigger than a pack: formal tools
  produce proof/counterexample artifacts, not simulation logs, so it likely
  wants a new `ArtifactType` (`formal_result`) and parser first (that's
  Evidence Graph / M2-shaped work), with a `knowledge` pack layered on top
  once the artifact type exists. Sequence matters here.

### 5.2 External documentation / reference resolution
`Reference.uri` exists as a hook but nothing resolves it yet. Two directions:
- Company-internal spec/wiki adapters (the M5 doc already names this as an
  extensibility point) - would live outside `knowledge/packs/` entirely,
  as a separate installable pack a company writes against the same schema.
- Live link validation / fetching for public specs (AMBA, PCIe SIG) - low
  priority, mostly a nice-to-have for the HTML report's reference links.

### 5.3 Learning feedback (M4's deliberately-unbuilt half)
`feedback/` ships interfaces and storage only, by explicit M4 design ("do
not implement machine learning yet, only design the interfaces"). Concrete
next steps when the user asks for this:
- Use `FeedbackRecord.diagnosis == "incorrect"` aggregated by
  `FailureSignature` digest to flag signatures where the deterministic
  rules/patterns are systematically wrong - surface this in the dashboard
  as a "needs a new rule" list, not as any model training.
- Use `useful_recommendations` / `false_recommendations` votes to reweight
  the `RecommendationEngine`'s per-category step templates - still
  deterministic (a weighted-count reorder), not ML.
- The explicit non-goal remains: no model retraining, no embedding
  fine-tuning. If a future request asks for that, it's a scope change from
  everything built so far and should be confirmed with the user first.

### 5.4 Learned similarity embeddings
`similarity.EmbeddingProvider` is a `Protocol` specifically so a learned
text-embedding model can be swapped in without touching `history/`,
`analytics/`, or the report layer. Not started. Would need: an opt-in
dependency (sentence-transformers or an API-based embedding call), a
concrete `EmbeddingProvider` implementation, and a decision about whether
it replaces or augments `FeatureEmbedding` (augment is safer - keep the
deterministic default, add the learned one behind a flag).

### 5.5 Waveform metadata - DONE in M6 (v0.6.0)
Delivered by the Waveform Intelligence Engine. `ArtifactType.WAVEFORM_METADATA`
now has a producer via `WaveformParser` + adapters (VCD and a JSON manifest;
FSDB/FST/WLF are documented next adapters). The correlation pass
`_link_waveform_observations_to_failures` links observations to failing
evidence sharing a scope segment, and knowledge packs' `suggested_signals` are
now actionable in practice. Remaining follow-ups worth a future milestone:
richer transaction/handshake inference from raw VCD (today VCD honestly
declares no TRANSACTIONS/PROTOCOL_ANNOTATIONS capability and reports those
analyses unavailable); a numeric-threshold observation kind for timing/perf
(would want the same numeric `EvidenceClause` variant flagged in 5.1, so
coordinate the two); resolving observation scopes to actual dump-file offsets
so a report link can jump straight into the viewer. See
`docs/WAVEFORM_ENGINE.md`.

### 5.6 Git history / commit correlation - LARGELY DONE in M7 (v0.7.0)
Delivered by the Engineering Context Engine, which superseded the M4-era
plan of "a new history/ adapter" with a first-class `engineering/` package
(providers are a general seam, not a git-only one; the M7 spec was explicit
about this). Shipped: recent-commit collection (git provider), change ->
failure correlation pass, change-category reasoning signals, ownership
routing, two-tier test impact, timeline, investigation view.
`capture_execution_metadata` now delegates to the git provider. Remaining
follow-up worth a future increment: cross-regression diffing ("what changed
between THIS run's commit and the last green run's commit?"), which needs
the regression DB's per-run commits joined with a provider diff query;
would live as a new history-aware analysis in `engineering/impact.py` or a
`history/` consumer, still behind the provider seam.

### 5.7 CI / issue-tracker adapters - seam now exists (M7)
The `ContextProvider` interface (M7) is exactly the seam these plug into:
a Jenkins/GitHub-Actions/Jira/DOORS integration is one registered provider
class, proven by `test_new_system_needs_only_a_provider`. The canonical
`*.engctx.json` manifest already lets any CI feed context without a
dedicated provider. Live API providers remain unbuilt (organization
specific; the user hasn't asked).

### 5.8 Front-ends and clients - MCP DONE in M8 (v0.8.0); rest are thin clients
The MCP server shipped in M8 (`veritriage mcp`, 12 tools over stdio), and
the client seam moved up a level: front-ends are no longer "thin clients
over `pipeline.analyze()`" but thin clients over `WorkspaceServices` (in
process) or the MCP tools (out of process); `pipeline.analyze()` is now an
internal detail only the service layer calls. Remaining, in rough order of
value: **VS Code extension** (everything it needs exists: sessions,
navigation getters for lazy trees, search; it is a rendering shell),
Claude Code / Cursor onboarding docs (an `mcpServers` config snippet is all
a user needs), Slack integration, GitHub Action (run `veritriage analyze`
in CI, upload the session bundle + report as artifacts). None require core
or workspace changes; `test_new_endpoint_needs_only_a_tool` is the proof.

### 5.9 Packaging
Standing offer, not executed: publish an initial `veritriage` release to
PyPI to reserve the name. Requires explicit user go-ahead.

### 5.10a IP Nirmaan next steps (M19 follow-ups)

Superseded by `docs/ROADMAP.md`, which is now the authoritative plan (Stages
0 to 6, with scope and done-when criteria). The notes below are kept for history.
- A model-backed `AgentRuntime` (Claude via the M17 provider registry, so one
  vendor registry still serves everything), first on verification seats where
  `veritriage.investigate` already produces real evidence.
- Deeper Phase 5: map the M12 specialists onto verification roles' work
  packets; publish organizational events to the M18 bus through the bridge.
- Real bindings for CONTRACT_ONLY tools (lint, simulator, formal) behind the
  broker, each proven by a crown-jewel-style test.
- MCP tools for Nirmaan (a separate tool table; the VeriTriage table must not
  learn about Nirmaan).
- Cross-domain graph (Phase 8): link trace-graph artifacts to Design Graph
  nodes, not only to VeriTriage session IDs.

### 5.10 Housekeeping / debt
- `docs/EVIDENCE_GRAPH.md` and `docs/ARCHITECTURE.md` should get a light
  pass any time a new milestone lands, to keep the "why v3+ needs no
  restructuring" style tables current (this file's section 3 is a faster
  place to check current state than re-reading every doc).
- No known failing tests or open bugs as of M10 / v1.0.0 (278/278 passing).
- `analyzers/` package (superseded by `reasoning/ai.py` at M3) was already
  removed; if it ever reappears from a bad merge, delete it again.

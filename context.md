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
Current version: **1.22.0** (distribution `ip-nirmaan`; packages `nirmaan` and `veritriage`)
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

### Landing page (side work, 2026-09-28) - `site/` for ip.nirmaan.online

A static page built from `docs/LANDING_PAGE_BRIEF.md`: `index.html`,
`styles.css`, `motion.js`, no build step and no dependencies. It reuses the
nirmaan.online design system (tokens copied, not linked, since the two sites
deploy separately) and follows that site's motion standard
(`docs/engineering/motion.md` in `nirmaansoftware/Nirmaan`). Motion is opt-in
(`html.motion`, set only without a reduced-motion preference) and only animates
toward content already in the HTML. `tests/test_landing_site.py` ties the stat
tiles to `build_organization().stats()` and the pack registry, and the
constitution cards to `CONSTITUTION`; the test count (879, up from the brief's 853
with this change) is maintained by hand.
Not deployed yet: hosting and the `ip` CNAME are the owner's call. See
`site/README.md`.

### Continuous integration (side work, Stage 0) - `.github/workflows/ci.yml`

GitHub Actions runs the full suite on Python 3.11 and 3.12 for every PR and
every push to `main`, installing with `pip install -e ".[ai,dev]"`. CI runs
`test_missing_sdk_raises_clean_error` too; it is deselected only locally, where
iCloud eviction stalls the `anthropic` import. A second job runs
`scripts/check_dashes.py`, which fails on U+2014 or U+2013 in any tracked text
file except the vendored nirmaan.online files (`site/nirmaan.css`,
`site/site.js`, `site/hero.js`). The README carries the CI badge.
Since v1.17.0 the test job runs on ubuntu-24.04 with `verilator iverilog yosys`
from apt and `NIRMAAN_REQUIRE_EDA` set, so the M21 real-tool tests run in CI
rather than skip (formal still skips: apt has no `sby`). v1.17.0 is the one
version bump covering Stage 0 and M20 to M22, which were built in parallel.

### Milestone 20 - AI workers in verification seats (roadmap Stage 1)

The first language-model workers, seated where their output can be checked:
verification debug. Three seats from the regression-investigation workflow
(Demo 4): failure triage (runs `veritriage.investigate`), root cause (a
decision over the declared outcomes), and debug review (a different seat and a
separate model call). Everything they return goes through `run_task` /
`review_task` and the engine, exactly like a human's work. Off by default:
`unbound` stays the default runtime. Version number left to the coordinator
at merge.

**The open decision (settled in `docs/AI_WORKERS.md`).** The runtime reaches a
model through the bridge, not through its own adapter. The bridge gained
`render_prompt`, `generate`, and `ground`, which wrap the M17 registry, its
frozen `Prompt`, and `grounding.enforce`. So one vendor registry still serves
the whole platform, and citation stripping has one implementation. The
Anthropic provider (`claude-opus-5-5`, adaptive thinking, effort high,
`fallbacks: "default"` under `server-side-fallback-2026-07-01`, SDK imported
lazily) is registered into the M17 registry by the bridge, because
`test_no_vendor_sdk_in_ai` forbids vendor SDKs in `veritriage/ai/` and
VeriTriage was not to change. A refusal or truncation is a failed generation.

Structure:
- `runtime/prompt.py`: `WorkPrompt`, `render_work_prompt(packet, mode)`. Only
  the four scopes (Company, Domain, Project, Task) are rendered; memory never
  is. Evidence and tool runs become citation tokens; Nirmaan IDs have `:` and
  `#` replaced by `.` to fit M17's token grammar, with the mapping kept.
- `runtime/model.py`: `ModelRuntime` (one class for every seat), the `LLM`
  protocol, `RegistryLLM` (any M17 provider), `MockLLM` (deterministic,
  scriptable). Registered runtimes: `mock-llm`, `anthropic`.
- `runtime/base.py`: `review_task` (P6 checked before any model call),
  `ReviewResult`, `unregister_runtime`, `RunReport.review`.
- `runtime/context.py`: `assemble(..., role=)` builds a packet for another
  seat; the task scope now carries evidence (own and upstream) and the task's
  own artifacts. `Artifact.summary` (new optional field) stores an agent's
  cited write-up.
- `cli.py`: `nirmaan run PROJECT TASK --runtime ID [--review] [--dry-run]
  [--input key=value]`. Inputs are recorded as task memory `input.<key>`.

Key design points worth not re-deriving:
- Seat behaviour is derived from the packet, never from a role or stage name:
  tools named by tool-backed evidence requirements run before the model is
  asked (with `input.*` params); outcomes come from the task.
- Prose citations are stripped when undeclared; an artifact left uncited is
  dropped (then P4 refuses an empty completion). Declared `tool_runs` go to
  the engine unfiltered, so a fabricated run is refused by P5 rather than
  silently cleaned.
- A failed or non-JSON model answer is DECLINED with uncertainty 1.0: any
  tool runs that really happened are still recorded, nothing else is.
- An uncited review is not recorded.

20 new tests in `tests/test_nirmaan_ai_workers.py` (879 -> 899). Demo 4 runs
triage, root cause, and review on agents with `tests/fixtures/axi_timeout.log`
and ends at a human approval that picks the fix branch. The Anthropic
provider is tested against a fake `anthropic` module; no test calls an API.
Crown jewel `test_a_new_runtime_registers_with_zero_core_changes` registers a
new model runtime and runs it through `nirmaan run`; a second test proves any
M17 provider (VeriTriage's `mock`) serves a seat through the one registry.
Deferred: seating from `AgentProfile.runtime`, model-chosen tool calls, seats
outside verification, token and cost accounting.

### Milestone 21 - Real design tools through open-source EDA (roadmap Stage 2)

`lint.run` (Verilator `--lint-only -Wall`), `simulator.run` and `test.run`
(Icarus Verilog, else Verilator `--binary`), `synth.run` (Yosys), and
`formal.run` (SymbiYosys) moved from `CONTRACT_ONLY` to `AVAILABLE`, backed by
`nirmaan/integrations/eda.py` (runner, backends) and `eda_parsers.py` (pure
parsers). `sta.run` stays a contract.

Key design points worth not re-deriving:
- Two facts, kept apart: the catalog status says a real implementation exists
  in the repo; a binding **probe** says this machine can run it now. The broker
  gained one generic hook, `register_binding(tool, probe=...)`; a probe
  returning a reason makes the broker refuse (`ToolAccessDenied`), so a missing
  executable is never a run, simulated or otherwise.
- `register_backend(Backend(...))` is the extension point (executables, steps
  as argv lists, parser, required params, optional cwd); the first backend for
  a tool also binds it. Crown jewel
  `test_a_new_backend_needs_no_core_changes` adds a lint backend whose
  executable is a script the test writes, and its run substantiates the lint
  requirement.
- Tool failures (lint warnings, `$error`, counterexamples, missing sources,
  timeouts) are recorded runs with `succeeded=False`. Each run writes
  `<backend>.log` and `<backend>.result.json`; those paths are its references.
- Lint warnings fail lint (lint-clean means clean; waivers live in the RTL).
  Icarus exits 0 on `$error`, so simulation passes only with exit 0, no error
  message, and `$finish` reached.
- `triage_simulation()` hands a simulation log to `veritriage.investigate`
  through the broker, as its own recorded run. `eda.py` never imports
  VeriTriage.
- Existing tests that used `simulator.run` as the example contract-only tool
  now use `git.write`.

Fixtures: `tests/fixtures/rtl/` (4-bit counter, passing and failing
testbenches, a `.sby` proof) and `tests/fixtures/eda/` (captured outputs).
`tests/test_nirmaan_eda.py` (24 tests): parsers against captured output, real
tools (skipped when absent, or failing when named in `NIRMAAN_REQUIRE_EDA`),
refusal with a reason, and a real lint run substantiating the RTL lint
requirement with no human attestation. Design doc: `docs/EDA_TOOLS.md`.

### Milestone 22 - IP Nirmaan over MCP, and organizational events (roadmap Stage 3)

Claude Code or Cursor can now plan a project, ask "why is this blocked?", and
move tasks through their lifecycle over MCP, and organizational moments reach
the M18 bus so VeriTriage automation rules can react. Version bump is left to
the coordinator at merge.

**A second tool table, not an extension of the first.** `src/nirmaan/mcp/`
(`tools.py` table with `@register_tool`, `server.py` stdio transport,
`__main__.py`) mirrors M8's shape. VeriTriage's table cannot hold Nirmaan tools
(it would have to import Nirmaan), and its `McpStdioServer` is bound to its
table and `WorkspaceServices`, so Nirmaan carries its own ~80-line JSON-RPC
subset rather than generalizing VeriTriage for Nirmaan's sake. Serve with
`nirmaan mcp --root .nirmaan` or `python -m nirmaan.mcp`. 16 tools: plan,
list, show, status, why, audit, organization events, and nine task actions.
No tool name collides with VeriTriage's (`recent_events` was renamed
`organization_events` when a test caught the overlap).

**Actions go through the engine.** Each action tool is load, one `TaskEngine`
call, save: state machine, authority, constitution, one audit entry. Refusals
come back as MCP tool errors and save nothing. **The MCP caller is always
`ActorKind.AI_AGENT`**; there is no flag to act as a human, so human-required
gates are refused by P12 and attestations over MCP are unsubstantiated. People
use the CLI for those.

**The event-bus coupling question, resolved.** `EventKind` stays a closed
verification vocabulary plus ONE generic member, `EventKind.EXTERNAL`: events
published by a system beside VeriTriage, with `Event.source` naming the
publisher and `payload["topic"]` naming what happened. VeriTriage names no
Nirmaan concept; no built-in trigger applies to EXTERNAL, so it is inert until
someone registers a trigger. That one enum member is the only change inside
`src/veritriage/`. Rejected: Nirmaan members in `EventKind` (couples the
engine), a Nirmaan-only bus (rules could not react), wrapping `EventBus`
(`Event.kind` is typed).

**Events are projections of the audit trail**, not engine hooks.
`nirmaan/events.py` maps `task.complete`, `gate.approve`, `escalation.raise`
audit entries to `task.completed`, `gate.approved`, `escalation.raised`
`OrgEvent`s carrying the entry's sequence and hash. The engine is untouched,
indirect completions (approval implies completion) are caught for free, and an
event cannot exist for a change the engine did not commit. The bridge registers
three triggers (`nirmaan.task_completed`, `nirmaan.gate_approved`,
`nirmaan.escalation_raised`), ships one rule (`nirmaan-escalation-raised` ->
NOTIFY), and adds `AutomationBridge`, which publishes onto a
`WorkspaceServices` bus with `source="nirmaan"`, evaluates rules, and dispatches
through `dispatch_actions`. Each MCP action returns the events it caused and
what automation decided.

13 new tests in `tests/test_nirmaan_mcp.py` (892 total). Crown jewel
`test_a_new_mcp_tool_needs_only_registration`. The existing M19 import-law and
no-dash tests cover the new modules and `docs/NIRMAAN_MCP.md` automatically.
Design doc: `docs/NIRMAAN_MCP.md`.

Deferred: a durable event log (the audit trail is the durable record), more
topics (one row in `TOPICS` plus a trigger), and tool-run evidence over MCP
(after Stage 2's real bindings).

### Milestone 23 fixtures - AXI4-Lite reference design (roadmap Stage 4)

`tests/fixtures/rtl/axi4_lite/` is the reference output of the design seats,
and the contract their end-to-end test scripts a model to produce:
`interface_spec.md`, `microarchitecture.md`, `axi4_lite_regs.v` (module
`axi4_lite_regs`, `ADDR_WIDTH` 4, `DATA_WIDTH` 32, `s_axil_*` ports, four
registers at 0x0 to 0xC), `axi4_lite_regs_tb.v` (self-checking, top
`axi4_lite_regs_tb`), `axi4_lite_regs_tb_fail.v` (one deliberately wrong
`wstrb` expectation, top `axi4_lite_regs_tb_fail`), and `axi4_lite_regs.sby`.
Choices: unmapped (misaligned) addresses get SLVERR, write latency and read
latency are 1 cycle (bound 2), reset values are zero, no skid buffer (READY
depends only on state). `tests/test_axi4_lite_fixture.py` proves it through
the broker with real tools: Verilator lint clean under `-Wall` with no
waivers, simulation passing under Icarus and Verilator, the wrong testbench a
recorded failed run, Yosys synthesis with no latches, and a SymbiYosys proof
of the handshake rules (formal skips in CI, which has no `sby`).

### Milestone 23 - Architecture and RTL agents (roadmap Stage 4)

Model seats for interface specification, microarchitecture, and RTL
implementation, all filled by the one M20 `ModelRuntime` with no branch per
seat. The first IP is an AXI4-Lite register block (not the roadmap's original
arbiter). The mechanism is proven on the M21 counter, and end to end on the
AXI4-Lite fixture set above (`tests/fixtures/rtl/axi4_lite/`). Version bump
left to the coordinator.

**A small-block workflow, as data.** `block-design` (requirements ->
interface-spec -> microarchitecture -> rtl-implementation) with a new intent
`block_design` (register block/file/bank, FIFO, arbiter, counter; priority 55,
ahead of `new_ip`). Demo 8 is "Create an AXI4-Lite register block." The RTL
stage outputs `rtl_source` and `testbench`; the RTL seat writes both.

**Approved inputs only.** `Capability.approved_inputs` (True for
`arch.interface`, `arch.microarchitecture`, `rtl.implement`). A new check
`approved-inputs`, joined to P8, refuses `task.start` while any artifact of a
dependency is below APPROVED, so `run_task` fails before a prompt exists. The
prompt withholds such artifacts (for `--dry-run`). Approved upstream artifacts
are citable by every seat as `[artifact:<id>]`, and a recorded file's content
is rendered only while its digest matches.

**Files in model answers.** The JSON object gains `files` (path, kind, title,
summary, entry); contents follow as `=== FILE: <path> ===` ... `=== END FILE
===` blocks, split off before JSON parsing (Verilog braces) and kept verbatim
(`runtime/files.py`). Summaries are grounded like artifacts (uncited files are
dropped, not written); unsafe paths, orphans, duplicates, unterminated blocks
are rejected and reported. Kept files are written to
`<input.workspace or a temp dir>/<task>/<attempt>/` and become artifacts with
`location`, `digest` (`sha256:...`, new optional `Artifact` field),
`derived_from` (the approved artifacts cited).

**Checked before review.** `EvidenceRequirement` gains `files`
(`FileInput(param, kinds, entry)`: which produced files fill which tool
parameter) and `before_review`. Requirements with `files` run after the model
answers (post-flight); without, before (M20 pre-flight). A new check
`evidence-before-review`, joined to P9, refuses `task.submit` until each such
requirement is met by substantiated evidence whose runs cover every submitted
file of those kinds (so a pass on an earlier attempt's files does not count).
`run_task` now reports a constitution refusal at submission as
`ResultStatus.REFUSED` (task stays in progress, failed runs saved as evidence)
instead of raising; a runtime result `BLOCKED` (a before-review tool the broker
refused: executable missing) blocks the task with the reason. Earlier refusals
(P3, P4, P5, P8 at start) still raise.

Key design points worth not re-deriving:
- The review gate is the engine's (a policy check at submit), not the
  runtime's; a person submitting through the CLI meets it too.
- Upstream artifacts are "unapproved while the dependency is finished" only when
  the dependency was cancelled after submission; the test builds exactly that.
- `new-ip`, `feature-addition`, and `rtl-change` RTL stages are unchanged: their
  flows (and tests) submit before attaching evidence. Adopting `files` and
  `before_review` there is a data edit, deferred.

19 new tests in `tests/test_nirmaan_design_agents.py`, plus Demo 8 in the
demo test. `test_the_axi4_lite_register_block_is_designed_by_agents` runs the
spec, microarchitecture, and RTL seats on MockLLM answers scripted with the
fixture files, real Verilator lint and Icarus simulation, agent reviews and
human approvals, and checks every tool-run evidence record is a passing run. Crown jewel
`test_a_new_design_seat_needs_no_core_changes`: a register-map seat with its
own capability, skill, unit, intent, workflow, and `regmap.check` tool, refused
on an overlapping map and approved on a clean one. Design doc:
`docs/DESIGN_AGENTS.md`. Deferred: a repair loop feeding the lint/simulation
log back to the model, a separate testbench (DV) seat, synth and formal as
before-review checks, FIFO/arbiter/APB blocks.

### Milestone 23 (part) - The project deliverable export (roadmap Stage 4)

`nirmaan export PROJECT --out DIR` writes the numbered deliverable tree
(`01_requirement/` to `10_signoff/`, plus `INDEX.md`) as a **view over project
state**. It lands as part of M23, beside the design-agent seats; version bump is
left to the coordinator at merge.

Key design points worth not re-deriving:
- **The layout is data.** `src/nirmaan/company/deliverables.py` declares
  `DELIVERABLE_FOLDERS` (`DeliverableFolder`: ID, artifact kinds, fallback
  capabilities, `ExportSection`s). `nirmaan/export.py` names no folder (a test
  reads its string constants). An artifact goes to the folder naming its kind,
  else its task's capability, else it is listed as unfiled. The registry is
  `register_folder` (same ID replaces, which is how a remap works) and
  `unregister_folder`; `validate_folders` refuses a kind, capability, or section
  claimed twice. Implementation views sit in `04_rtl` until Stage 6.
- **Honesty.** Assurance is written as recorded and is in every artifact's file
  name (`rtl-lint_a1.EXECUTED.md`), its `.provenance.json` sidecar, and
  `INDEX.md`. A deliverable a live task still owes is listed as missing (with
  the task's status), a cancelled task's as not required; nothing stands in for
  either. Signoff lists a gate as signed off only with a completed, granted gate
  task and its `gate.approve` audit entry.
- **A broken chain exports loudly.** `ProjectStore.load(..., verify=False)` is
  new and used only by the export, which runs `verify_chain` itself: the
  `INDEX.md` banner, `09_evidence/audit_chain.json`, the signoff report, and the
  CLI all say the chain failed.
- **A read, and deterministic.** No state change and no audit entry; the output
  directory must be new or empty. Everything is sorted by ID and JSON keys are
  sorted, so a state and its saved-and-reloaded copy export byte-identically.
- Tool-run references that are files (EDA `<backend>.log`,
  `<backend>.result.json`) are copied into `09_evidence/tool_runs/<run>/` with a
  hash; references that are not files (VeriTriage session IDs) are recorded as
  given. An artifact's `location` is copied the same way, and the sidecar
  checks the copy against the artifact's recorded `digest` (match, mismatch,
  or none recorded).

20 new tests in `tests/test_nirmaan_export.py` (984 total), built by planning
and driving a project through the engine. Crown jewel
`test_a_new_folder_or_a_remap_needs_zero_core_changes`. Design doc:
`docs/DELIVERABLE_EXPORT.md`.

Deferred: an archive format with a signed manifest, and artifact bodies beyond
the recorded summary (the Stage 4 design agents will record located files,
which the export already copies).

v1.18.0 is the one version bump for the three M23 parts (fixtures, design
agents, export), built in parallel and merged as #23, #24, #26, and #25. The
standard run is 984 tests.

### Milestone 25 (part) - Physical design through OpenSTA and OpenROAD (roadmap Stage 6)

`sta.run` (backend `opensta`, executable `sta`) and `pnr.run` (backend
`openroad`) moved from `CONTRACT_ONLY` to `AVAILABLE`, in
`nirmaan/integrations/physical.py` (bindings) and `pd_parsers.py` (pure
parsers), on the M21 `register_backend` registry. `synth.run` gained a second
backend, `yosys-liberty` (chosen with `backend=yosys-liberty`), that maps to a
Liberty library and writes `netlist.v`, the input STA and PnR need. **Neither
OpenSTA nor OpenROAD has run in this repository**: they are not installed
locally or in CI, and Homebrew has no formula. Version bump left to the
coordinator.

Key design points worth not re-deriving:
- **One staged `pnr.run`**, not four tools: OpenROAD is one process and one
  database, so one run does floorplan, place, route (ending at `stop_after`),
  then timing, and prints `nirmaan-stage:` / `nirmaan-stage-done:` markers the
  parser reads. The existing skills already named `pnr.run`.
- **The PDK is an input, never bundled.** `liberty`, `tech_lef`, `lef`, `site`,
  `hor_layers`, `ver_layers` are task parameters; relative files resolve under
  `pdk_root` or `NIRMAAN_PDK_ROOT`. A missing PDK input is a *refusal* (the
  probe; no run recorded), like a missing executable; a missing netlist or SDC
  is a recorded failed run, like a missing source.
- `Backend` gained two optional generic fields in `eda.py`: `environment`
  (asked by the probe after the executables; its reason joins the refusal) and
  `files` (parameters whose paths must exist). `select_backend`'s refusal text
  now reads `<backend> needs <exe> on PATH, not found; <backend>: <reason>`.
- `nirmaan.runtime.unavailable_reason(tool, params)` exposes the broker's probe;
  `nirmaan org tools` shows it in a new **Here** column.
- STA passes only with a worst setup slack reported and non-negative, hold
  non-negative, and no violating endpoint; `worst slack INF` (unconstrained)
  fails. PnR passes only when every requested stage and timing finished, DRC
  count is 0 after routing, and timing is met.
- New workflow `physical-implementation` (intent `physical_implementation`,
  priority 50: "place and route", "PnR", "physical design/implementation"):
  timing-constraints -> synthesis -> floorplan -> place-route -> sta-signoff
  (gate.implementation). Existing capabilities and skills only. `floorplan`
  artifacts and `pd.floorplan` file into `04_rtl` in the export. The landing
  page's workflow tile is now 9.

Fixtures `tests/fixtures/pd/`: `axi4_lite_regs.sdc` (100 MHz), `tiny_cells.lib`
(a toy Liberty library, no timing, so `yosys-liberty` runs for real in CI), and
four **synthetic** logs (`synthetic_*.log`, first line `# SYNTHETIC:`) written to
the documented report formats. `tests/test_nirmaan_physical.py` (22 tests, 2
skip without `sta`/`openroad` and sky130 under `NIRMAAN_PDK_ROOT`; CI does not
require them). Test stand-in executables exercise the runner (script written,
argv, parse, timeout, failures). Crown jewel
`test_a_new_pd_backend_needs_no_core_changes`. The `test_nirmaan_eda` catalog
test no longer lists `sta.run` and `pnr.run` as contracts. Design doc:
`docs/PHYSICAL_DESIGN.md`. Deferred: CTS, power grid, tap/filler cells, repair,
parasitic extraction, MCMM, captured logs, a physical deliverable folder.

### Milestone 25 (firmware part) - A driver run on the approved RTL (roadmap Stage 6)

The firmware part of Stage 6, built in parallel with the physical-design and
DFT parts and the Stage 5 graph. A firmware seat writes a C driver and its
tests; they reach review only after a strict build and a co-simulation against
a Verilator model of the approved RTL passed. Version bump left to the
coordinator.

**Two tools, through the M21 registry.** `src/nirmaan/integrations/firmware.py`
registers `fw.build` (backends `host-cc`, and `riscv-gcc`, which is refused
unless `riscv64-unknown-elf-gcc` is on PATH) and `fw.test` (backend
`verilator-cosim`, needs `cc`, `verilator`, `make`). Both are `AVAILABLE` in
`company/tools.py`; `compiler.run` stays `CONTRACT_ONLY`. `fw.build` compiles
every `.c` under `-std=c11 -Wall -Wextra -Werror -pedantic` and checks each
`.h` alone (through a generated one-line file, since a macro-only header is an
empty translation unit under `-pedantic`). `fw.test` compiles the driver and
tests the same way, builds the RTL with Verilator (`--prefix Vdut`) around
`integrations/firmware_harness/axil_manager.cpp`, and runs it. Parsers
`parse_c_build` (GCC and Clang, `-Werror=` and `-Werror,-W` mapped to the
warning code) and `parse_fw_test` (the harness's `FWTEST` lines) are pure.

**The HAL.** `firmware_harness/nirmaan_hal.h`: a struct of `read32`/`write32`
function pointers plus a context, each returning the AXI response code; tests
define `nirmaan_fw_test(const nirmaan_hal *)` and report through
`nirmaan_test_result`. The harness is a generic AXI4-Lite manager over the
`s_axil_*` port convention (32-bit data): real VALID/READY handshakes, one
`FWTEST BUS` line per transfer, a 1000-cycle handshake timeout that fails the
run, and exit 0 only when at least one check passed and none failed.

**The seat, as data.** Capability `fw.driver` (`approved_inputs=True`,
produces `driver`, `driver_test`), provided by the existing `device_drivers`
skill (now with tools `fw.build` and `fw.test` and the HAL contract in its
procedures; extended rather than a new skill so the landing page's skill count
stays true), held by the existing Driver Engineer practice; review is
`sw.review` (HAL, BSP, and boot engineers). Stage `firmware` in `block-design`,
when the requirement mentions firmware or a driver, depending on
`interface-spec` and `rtl-implementation`. `driver_test` joins `driver` in the
`08_documentation` export folder.

**One generic addition: `FileInput.upstream`.** A tool parameter can be filled
from the task's approved upstream artifacts of given kinds, not only its own
files. The runtime passes only files that are APPROVED and still match their
digest; the `evidence-before-review` policy additionally requires a passing run
to have named an approved upstream file in that parameter (so a co-simulation
against some other copy of the RTL does not open review); the prompt says
"with the approved rtl_source". None of the three names a seat, kind, or tool.
`runtime/tools.py` now imports every `nirmaan.integrations` module to register
bindings, instead of naming `eda` and `veritriage`, so the runtime names no
integration (a test checks it names no firmware).

Key design points worth not re-deriving:
- Verilator's `--build` runs make, which breaks on a space in a path, and this
  repo lives under `~/Documents/IP Nirmaan`. `fw.test` copies the harness and
  the RTL into the working directory first; the run records the given paths.
  A working directory with a space in it fails as a recorded run.
- The wrong-driver fixture (`axi4_lite_regs_map_wrong.h`, REG2 at REG1's
  offset) builds clean; only the co-simulation catches it, because the tests
  write all four registers before reading any back.
- An approved RTL that changed on disk is not co-simulated: the check does not
  run and the submission is refused (as M23 treats a missing file), not
  blocked.

18 new tests in `tests/test_nirmaan_firmware.py`, including the end-to-end
`test_the_firmware_seat_runs_its_driver_on_the_approved_rtl` (the M23 flow,
then the firmware seat on the `tests/fixtures/fw/axi4_lite/` answer, real
build and co-simulation, agent review, human approval) and the crown jewel
`test_a_new_firmware_backend_needs_no_core_changes` (an `arm-cc` backend whose
compiler is a script the test writes). CI adds `cc make` to
`NIRMAAN_REQUIRE_EDA`. Design doc: `docs/FIRMWARE.md`. Deferred: a RISC-V
cross compile in CI and an instruction-set simulator in the loop, a repair
loop, APB and AXI4 harnesses, static analysis, generated register headers.

### Milestone 24 - The cross-domain engineering graph (roadmap Stage 5)

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

### Milestone 25 (DFT part) - Design for test through Yosys and Icarus (roadmap Stage 6)

Three new tools, all `AVAILABLE` and backed by M21 backends in
`nirmaan/integrations/dft.py` (the broker imports every integrations module): `dft.scan_insert`
(backend `yosys-scan`), `dft.check` (`yosys-dft`), and `dft.scan_sim`
(`icarus-scan`). `dft.run` (ATPG, MBIST) stays `CONTRACT_ONLY`. Physical design
and firmware are the M25 entries above; M24, the engineering graph, sits between.

Key design points worth not re-deriving:
- **Architecture: mux-D, one chain.** Yosys `synth -flatten` then `dffunmap`
  leaves only `$_DFF_[PN]_` and `$_DFF_[PN][PN][01]_` flops.
  `dft_scan.py stitch` renames each to a `$__NIRMAAN_SCAN_DFF_*` cell with `SE`
  and `SI` pins in the Yosys JSON, chaining flops in natural net-name order;
  Yosys then `techmap`s each into a `$_MUX_` plus the original flop and writes
  `scan.v` with ports `scan_en`, `scan_in`, `scan_out`, plus `chain.json`.
  Latches, a second clock or edge, a non-input clock, or taken port names are
  refused as a failed run.
- **`dft_scan.py` is standard library only.** The backends run it as a step
  (`sys.executable dft_scan.py ...`) between Yosys and Icarus, so it never
  depends on how Nirmaan is installed; `dft.py` imports the same functions.
- **Rules are a registry** (`register_rule(DftRule(...))`), evaluated over the
  Yosys netlist in the parser: `no-latches`, `no-combinational-loops`,
  `scannable-flops`, `clock-from-input`, `reset-from-input`,
  `one-clock-domain`, `recognized-cells`, and `scan-chain-complete` (only when
  the top has the scan ports). Each violation's diagnostic code is its rule ID.
- **The chain is traced functionally**, not by finding muxes (synthesis may
  restructure them): random 64-bit words on inputs and flop outputs, `scan_en`
  high, each flop's D evaluated by a small gate evaluator over the netlist.
- **`dft.scan_sim`** generates a testbench: shift 2L known bits (scan_out must
  replay them after L cycles), then load a state, capture once with `scan_en`
  low, and unload. The expected capture is the gate evaluator's next state over
  Yosys's netlist, so Icarus and Yosys cross-check each other. A broken chain
  fails before simulating, with the chain problems.
- **The seat is data.** `scan_design` and `dft_verification` skills gain the
  tools; `block-design` gains a `dft` stage ("Scan insertion", `dft.insert`,
  output `dft_netlist`, review `dft.review`) only when the request asks for
  test (the existing `dft` feature). Its two `checked(...)` requirements make
  `dft.check` and `dft.scan_sim` before-review checks over the netlist file.
- Verified on Yosys 0.33 (CI's apt version, via `yowasp-yosys`) and current
  Yosys: both fixtures insert, check, and simulate cleanly (4 and 206 flops).

Fixtures: `tests/fixtures/rtl/dft/` (`untestable.v`: latch, gated and divided
clocks, a combinational loop; `broken_chain.v`: a flop with no scan mux).
`tests/test_nirmaan_dft.py` (16 tests): pure stitcher, tracer, and rule tests; real
insertion, rules, and chain simulation on `counter.v` and `axi4_lite_regs.v`;
a broken chain and a mis-shifting chain as recorded failed runs; refusal
without Yosys; the DFT stage gated before review end to end; crown jewel
`test_a_new_dft_rule_needs_no_core_changes`. Design doc: `docs/DFT.md`.

Deferred: ATPG and fault grading, multiple chains and clock domains, MBIST,
a Verilator backend for `dft.scan_sim`, a seat that records a tool-written file
(the runtime records only model-written files today), and the before-review
checks on `new-ip`'s `dft` stage.

v1.19.0 is the one version bump for Stage 5 (M24, #29) and the three Stage 6
parts (physical design #28, firmware #30, DFT #31), built in parallel. The
standard run is 1055 tests with 2 skipped: the real OpenSTA and OpenROAD tests,
whose tools are not installed anywhere yet.

### Milestone 26 - The repair loop (post-roadmap)

When a seat's submission is refused (a before-review check failed on its
files), `run_task` may ask the same seat again, bounded, handing it the failed
runs as citable evidence with a log excerpt. Off unless configured: a
capability's `max_attempts` defaults to 1 and no shipped capability sets it;
`run_task(..., attempts=N)` and `nirmaan run --attempts N` override per run.

Key design points worth not re-deriving:
- **The loop lives in `run_task`** (`runtime/base.py`) and names nothing. Only
  a constitution refusal at `engine.submit` starts another attempt; `blocked`
  (the broker refused a tool), `declined`, an escalation, and a P5 raise end it
  as before. With a limit of 1 no `Attempt` is recorded: state and audit are
  exactly M23's.
- **A refused attempt is an `Attempt`** (`models/work.py`, stored in the new
  `ProjectState.attempts`, ID `<task>#t<n>`), written only by
  `TaskEngine.record_attempt` and audited as `task.attempt`. Its files are full
  `Artifact` records held inside it, never in `state.artifacts`, so review,
  verification, approval, export, and the engineering links cannot see them.
  M23's per-attempt directories (`<workspace>/<task>/<n>/`) keep the bytes.
- **The repair prompt** (`prompt._repair`, work mode only): every refused
  attempt's reason; the latest one's failed runs with run and evidence tokens
  (already citable, since `run_task` recorded them as evidence), a log excerpt
  (`files.excerpt`: the run's first reference, notable lines first, at most 20
  lines of 240 characters), and its files, digest-checked.
- `evidence-before-review` is unchanged; a test hand-submits a refused
  attempt's files after an earlier attempt's lint passed and is refused with
  "no passing run ... covers".

`tests/test_nirmaan_repair.py` (10 tests): lint repaired to review; the repair
prompt's tokens and excerpt; limit 1 unchanged; exhaustion lists and audits
every attempt; broker refusal is blocked with one model call; CLI `--attempts`
with the SDK import poisoned; a firmware seat repaired from the wrong register
map to the fixture driver; crown jewel `test_a_new_check_gets_repair_with_no_core_changes`
(a capability with `max_attempts=2` and a `units.check` tool bound in the
test); the runtime names no seat or tool. Design doc: `docs/REPAIR_LOOP.md`.

Deferred: repair after a reviewer's `request_changes`, a per-stage limit, a
budget shared across separate runs, and file-level signoff evidence.

### Milestone 26 (blocks) - FIFO, arbiter, and APB register block on the design flow (post-roadmap)

Three more fixture sets, in the AXI4-Lite set's shape, each proven through the
broker by real tools and each run end to end through `block-design`. No
runtime, policy, workflow, or vocabulary change: the requests already match
`block_design`. Design doc: `docs/IP_BLOCKS.md`.

- `tests/fixtures/rtl/sync_fifo/`: module `sync_fifo`, `DEPTH` 8, `WIDTH` 8,
  ports `clk rst_n wr_en wr_data full rd_en rd_data empty count`. Explicit
  `count` register (any `DEPTH` of 2 or more), first-word fall-through, a
  write while full and a read while empty dropped, full with a write and a read
  accepts only the read. Proofs `sync_fifo.sby` and `sync_fifo_depth5.sby`.
  Wrong testbench: a full FIFO of depth 8 "holds 9" (`count when full`).
- `tests/fixtures/rtl/rr_arbiter/`: module `rr_arbiter`, `N` 4, ports
  `clk rst_n req grant`. Index pointer, combinational same-cycle grant,
  pointer to one past the winner, wait at most `N-1`. Proofs `rr_arbiter.sby`
  and `rr_arbiter_n5.sby`. Wrong testbench: the winner "keeps" top priority
  (`rotation with everyone requesting`).
- `tests/fixtures/rtl/apb_regs/`: module `apb_regs`, APB4, `ADDR_WIDTH` 8,
  `DATA_WIDTH` 32, ports `pclk presetn paddr psel penable pwrite pwdata pstrb
  prdata pready pslverr`, four registers at 0x0 to 0xC, zero wait states.
  **Unmapped policy: PSLVERR**, the AXI4-Lite block's SLVERR (misaligned, or
  0x10 and above: a write changes nothing, a read returns zero). Proof
  `apb_regs.sby`. Wrong testbench: `pstrb 0101`, as the AXI4-Lite one.
- The FIFO and arbiter testbenches run a default and a non-power-of-two
  instance side by side against reference models, with coverage counters that
  fail the run if a corner case was never reached. Two `.sby` files each
  because the broker's `sby -d` takes one task per file.
- Mutation check (not committed): 19 mutants; simulation caught 18, formal 19.
  The one simulation misses is an APB write in the setup phase too, invisible
  at the ports. It also showed that APB properties reusing the design's
  `is_mapped` and `merge` hid bugs in them, so the properties now have their
  own decode and byte merge.

Tests: `tests/test_sync_fifo_fixture.py`, `tests/test_rr_arbiter_fixture.py`,
`tests/test_apb_regs_fixture.py` (lint, both simulators, the wrong testbench
as a recorded failed run, synthesis with no latches, formal skipping without
`sby`) and `tests/test_nirmaan_more_blocks.py` (six natural requests plan
`block-design`; `test_the_block_is_designed_by_agents` per block). 35 tests.

Deferred: lint at non-default parameters through the broker (checked by hand),
and richer variants (registered FIFO read, weighted arbiter, APB wait states).

### Milestone 26 (formal gate) - Synthesis and formal before review, formal in CI (after Stage 6)

The `block-design` rtl stage gains two `checked(...)` requirements, as data:
`synth.run` over the produced `rtl_source` files (top from the RTL file's
entry) with `max_latches=0`, always; and `formal.run` with `sby` from a
produced `formal_spec` file (a `.sby`) and `sources` from the `rtl_source`
files, only when a `formal_spec` was produced. The `rtl_design` skill is
granted both tools. Design doc: `docs/FORMAL_GATE.md`.

Key design points worth not re-deriving:
- **Two generic fields on `EvidenceRequirement`.** `params` (fixed tool
  parameters, merged over task inputs in pre-flight and post-flight; `satisfies`
  counts a run only if it was made with every one) and `when_produced` (the
  requirement applies only when an artifact of those kinds was produced;
  `EvidenceRequirement.applies(kinds)` is read by the post-flight step, the
  `evidence-before-review` check over the submitted drafts, and
  `unsatisfied_requirements` over the task's artifacts). Nothing names formal.
- **Limits are generic in `eda.execute`.** Any `max_<metric>` parameter fails
  a passing result whose parsed metric exceeds it, or that never reported it.
  Yosys's latch count (M21's `stat -json` parse) is what `max_latches` reads.
- **Formal is conditional for `block-design`**, not required: a required `.sby`
  invites vacuous proofs, and it would couple other blocks on the workflow to
  writing properties. When present, it must pass. Properties live in the RTL
  under `` `ifdef FORMAL ``; the `.sby` lists the RTL by relative path, which
  resolves because a seat's files share one attempt directory.
- **The proof must read the submitted RTL.** `Backend.check` (new, optional)
  runs before any step; the SymbiYosys backend uses it to fail a run whose
  `.sby` `[files]` does not list every `sources` file. Whether `[script]`
  reads it is left to the reviewer, who reads the `.sby`.
- **CI:** OSS CAD Suite 2026-09-28 streamed into `$RUNNER_TEMP`, not cached.
  Only `sby` and `yices-smt2` wrappers go on PATH; the suite's `sby` launcher
  prepends the suite's `bin` for its own process, so proofs use the suite's
  matched Yosys and yosys-smtbmc while every other test keeps apt's tools.
  `NIRMAAN_REQUIRE_EDA` gains `sby yices-smt2`, and the test step runs with
  `-rs` so the log lists every skip.

Tests: `tests/test_nirmaan_formal_gate.py` (13): a latch hidden from lint by a
waiver pragma, and a Yosys error, both refused with recorded failed runs; an
AXI4-Lite mutant (`arready` tied high) that passes lint, simulation, and
synthesis but fails the proof; a `.sby` proving an embedded copy of the module;
passing synthesis and formal reach review and approval; no `.sby` means no
formal; no `sby` blocks with nothing recorded; a claimed formal pass is refused
(P5); a hand-made synthesis without `max_latches` does not count; metric
limits; crown jewel `test_a_new_before_review_check_needs_no_core_changes`;
and, with the repair loop merged alongside, a counterexample refused on attempt
1 (kept as an `Attempt`) and repaired on attempt 2. The AXI4-Lite demo's RTL seat now also writes `axi4_lite_regs.sby`. The
engineering-graph fake-EDA fixture gained a fake `synth.run`; the firmware and
design-agent and repair tests that reach the rtl stage now also need
`yosys`. The FIFO, arbiter, and APB end-to-end tests (M26 blocks) now have the
RTL seat write the block's `.sby` too, so all four blocks are synthesized and
proven before review. The standard run is 1113 tests with 2 skipped (OpenSTA,
OpenROAD), with `sby` required.

Deferred: a separate properties seat and vacuity (cover) checks; formal and
synthesis on the `new-ip`, `feature-addition`, and `rtl-change` RTL stages;
checking the `.sby` `[script]`; moving all of CI to the suite's tools.

v1.20.0 is the one version bump for the three M26 parts (repair loop #33,
blocks #35, formal gate #34), built in parallel. The same release teaches the
vocabulary two APB spellings: the `apb` feature matches APB3 and APB4, and
`block_design` also matches a request for an APB or AXI4-Lite subordinate
(`test_apb_revisions_are_recognized`). The standard run is 1115 tests with 2
skipped (OpenSTA and OpenROAD, not installed).

### Milestone 27 - Repair after review, and retry limits per stage (after Stage 6)

When an independent reviewer (a human, or a review seat through `review_task`)
requests changes, the owner seat can be run again with the review's findings
and the sent-back files in its prompt; its new files go through every
before-review check and to review again. `max_attempts` and a new
`max_review_rounds` can be set per workflow stage, and both budgets persist
across `nirmaan run` invocations. Design doc: `docs/REVIEW_REPAIR.md`.

Key design points worth not re-deriving:
- **Supersession happens at the change request, in `TaskEngine.review`.** When
  the verdict moves the task to `changes_requested`, `_supersede` moves the
  task's artifacts out of `state.artifacts` into an M26 `Attempt` with the new
  field `reviews` (every review of that submission). The audit entry is the
  `task.review` itself, with `details.superseded` and `details.artifacts`.
  Superseded artifacts keep their IDs; `submit` numbers new ones after them, so
  an ID never changes meaning. Export, links, trace, and approval never see
  them, structurally, as with M26's refused files.
- **`latest_verdicts` skips reviews listed in an `Attempt`**, so a second
  round's verdict never conflicts with the first round's.
- **A change request is citable, not evidence.** The prompt declares each
  review as `[review:<task>.r<n>]`; recording it as `REVIEW_RECORD` evidence
  would satisfy "Independent review recorded" with a rejection.
- **Limits:** `runtime.limits(engine, task, attempts, review_rounds)` returns
  the CLI override, else `StageTemplate.max_attempts` or `max_review_rounds`
  (new, `None` inherits), else the capability (`max_review_rounds` new,
  default 1), else 1. `nirmaan run --review-rounds N` joins `--attempts N`.
- **Budget from state:** rounds used = superseded `Attempt`s; attempts used =
  refused `Attempt`s numbered after the latest superseded one (this round).
  `run_task` escalates (technical, the owner's route, no model call) when
  rounds used reach the limit, or this round's recorded refusals do. Resolving
  the escalation restores the task, not the budget; a higher limit allows more.
  With the default of one round, running the owner on a sent-back task now
  escalates instead of starting fresh; humans can still start and submit.
- **Prompt:** work mode renders "Repair after review", every change request
  with its token, and the latest sent-back files (digest-checked), then M26's
  block for this round's refused attempts only. Review mode lists earlier
  change requests as context, never a superseded file.

`tests/test_nirmaan_review_repair.py` (11 tests): crown jewel
`test_a_new_stage_gets_review_repair_with_no_core_changes` (a units-sheet stage
with `max_review_rounds=2` over a capability's 3, checker bound in the test);
precedence; a CLI limit below the stage escalates; exhausted rounds escalate
and resolution does not reset them; the attempt budget across three CLI runs
with the SDK import poisoned; real RTL sent back by a reviewer seat, repaired
through lint and simulation, approved, with only the second submission in the
export and the links; supersession audited and IDs never reused; a superseded
round's reviews do not conflict; P6; the runtime names nothing and keeps the
import laws; nothing shipped sets a limit. `test_changes_requested_sends_work_back`
now expects v1 in an `Attempt`, not among the task's artifacts.

Deferred: an unattended owner and reviewer loop in one command; resetting a
budget on resolution; file-level signoff (a passing run over a superseded file
stays on the task as evidence); `DOCUMENT` evidence and spec requirements that
name a superseded artifact keep their records.

### Milestone 27 (physical design) - OpenROAD and OpenSTA run for real in CI (after Stage 6)

M25's `sta.run` and `pnr.run` bindings had never run. A new CI job,
`physical-design`, runs them for real, and the first runs' breakages are
fixed. Design doc: `docs/PHYSICAL_DESIGN.md` (sections 8 and 10). No version
bump.

Key points worth not re-deriving:
- **Where it runs.** Only in CI: the job runs inside
  `openroad/orfs:26Q3-687-gc63a606f9` (pinned by digest; ORFS `c63a606f9`,
  OpenROAD `c487fc70`, Yosys 0.68+post, Nangate45 under `flow/platforms`),
  Python 3.12 from `setup-uv`, `NIRMAAN_PDK_ROOT` at the platforms directory,
  `NIRMAAN_REQUIRE_EDA="yosys openroad"`, and only
  `tests/test_nirmaan_physical.py`. Every run's working directory is uploaded as
  the `pd-logs` artifact. The main test jobs are unchanged. macOS: no Homebrew
  formula and no Docker, so the real tests skip locally.
- **No standalone `sta` exists in packaged OpenROAD**, and `openroad` has no
  OpenSTA-only mode. `sta.run` gained a second backend, `openroad-sta`: the same
  script under `openroad`, plus `read_lef` (OpenROAD links into its database;
  `ORD-2010` without LEFs), so it also needs `tech_lef` and `lef`. `opensta`
  stays first when `sta` is on PATH.
- **Fixes from the real output:** `yosys-liberty` takes optional
  `tie_high`/`tie_low` (`CELL/PORT`, via `hilomap`), since the detailed router
  rejects a constant net (`DRT-0305`); the area line is `um^2`, not `u^2`;
  `report_worst_slack` prints `worst slack max <n>` and `report_tns` `tns max
  <n>` (parsed by label, unlabelled still read in order); `-group_count` and
  `-endpoint_count` became `-group_path_count` and `-endpoint_path_count`; a
  violator count at the report cap (`VIOLATOR_REPORT_LIMIT`, 100) is "at least".
- **Real numbers** (AXI4-Lite block, Nangate45, ideal clock, no CTS or power
  grid): STA at 100 MHz met, setup slack 7.264, hold 0.101; at 5 GHz
  (`axi4_lite_regs_fast.sdc`) violated, setup -0.905, TNS -157.481; place and
  route to route, 41% utilization, 0 DRC (the signal routing only; power pins
  are unconnected), wirelength 10783 um, setup slack 7.120; at 300% utilization
  it fails in placement (`GPL-0301`).

Fixtures: the four `synthetic_*.log` are deleted; `opensta_met.log`,
`opensta_violated.log`, `openroad_route.log`, and `openroad_error.log` are
captured from CI run 36600440325, each with a `# CAPTURED:` first line and the
log unedited below it. The real-tool tests moved from sky130 to Nangate45 and
gained the violated-timing and failed place-and-route cases; new unit tests
cover the `openroad-sta` fallback and tie cells. The standard local run is 1128
tests with 3 skipped (the three real OpenROAD tests); in CI the
`physical-design` job runs them. Deferred: standalone OpenSTA in CI, sky130,
a local OpenROAD, and CTS, power grid, and parasitic extraction as before.

### Milestone 27 (gates everywhere) - The design gates on every RTL workflow, and non-vacuous proofs (after Stage 6)

The `new-ip` `rtl-implementation`, `feature-addition` `rtl-change`, and
`rtl-change` `change` stages now carry `RTL_GATES` (in `company/workflows.py`):
the `block-design` checks (lint, simulation, synthesis with `max_latches=0`,
formal when a `formal_spec` is produced) plus `NOT_VACUOUS`, a `formal.cover`
run over the same `.sby`, also tied to `formal_spec`. Each of the three stages
now produces a `testbench` too, and a human attestation no longer meets them.
`block-design` gains `NOT_VACUOUS` as one added line. Design doc:
`docs/GATES_EVERYWHERE.md`.

Key design points worth not re-deriving:
- **Non-vacuity is a cover run of the seat's own setup.** The
  `symbiyosys-cover` backend (`integrations/eda.py`) writes a copy of the
  `.sby` into the run's directory with `mode cover` and absolute `[files]`
  paths; script, engines, depth, and assumptions are the proof's.
  `parse_sby_cover` passes only on `DONE (PASS)`, exit 0, at least one reached
  cover, and none unreached (SymbiYosys itself calls a setup with no covers a
  pass). `[tasks]` setups are a recorded failure. A separate tool, not a
  `formal.run` mode, so a cover run can never meet "Formal properties are
  proven".
- **What it catches:** over-constrained inputs, assumptions contradictory on
  the path to a covered state, antecedents the seat covers. A plain
  `assume (1'b0)` already fails `formal.run` (smtbmc `--presat`). Covers the
  seat did not write, or trivial ones, are the reviewer's to catch.
- **Approved inputs through gates.** On `new-ip` and `feature-addition` the RTL
  task depends on `microarchitecture.gate`, which has no artifacts, so the seat
  saw no upstream and the M23 approved-inputs check held vacuously.
  `upstream_artifacts(state, task)` in `work/policy.py` looks through gate
  tasks; the context packet, the `approved-inputs` check, and the upstream
  bindings of `evidence-before-review` all use it.
- **`drive` follows the gated order.** `tests/nirmaan_helpers.py`
  `gated_submit` writes `counter.v` and `counter_tb.v`, runs each applicable
  before-review check through the broker from the requirement's own data,
  records the runs, then submits. Tests that drive through these stages need
  `GATE_TOOLS` (`verilator iverilog vvp yosys`) and are marked so.
- **Fixture covers** in `counter`, AXI4-Lite (8), FIFO (6), arbiter (2 per
  requester, including the tight fairness bound), and APB (4), under
  `` `ifdef FORMAL ``. The APB proof depth rose from 4 to 8 so a write and read
  back is reachable.

Tests: `tests/test_nirmaan_gates_everywhere.py` (34): the stages as data; the
planned tasks gated and on approved inputs (through a gate, and a cancelled
impact analysis refusing an `rtl-change`); on each of the three workflows a
latch and a failing self-check refused and clean RTL with a proof approved;
two vacuous proofs refused while `formal.run` passes; `assume (1'b0)` failing
both runs; no covers refused; all
seven fixture setups reach every cover; the cover run's isolation and
prechecks; the parser on captured logs; crown jewel
`test_a_fourth_workflow_is_gated_with_no_core_changes`; `drive`'s order; the
core never names `formal.cover`; CI requires the formal tools. Migrated (each
listed in the design doc, section 5): two `test_nirmaan_work.py` tests and one
each in `test_nirmaan_eda.py` and `test_nirmaan_export.py` gained
`GATE_TOOLS`; three exact tool-set assertions gained `formal.cover`. The
standard run, merged with the review-repair milestone, is 1160 tests with 2
skipped (OpenSTA, OpenROAD).

Deferred: the same gates on `parameter-change` and the fix stages
(`regression-investigation`, `timing-closure`) and on `cdc-design`; automatic
antecedent covers; multi-task setups in the cover check.

### Milestone 27 (RISC-V firmware) - the driver on a core against the RTL (after Stage 6)

Closes M25's first deferred firmware item. The firmware seat's driver and
tests, unchanged, are cross-compiled for bare-metal RV32I and run on PicoRV32
in one Verilator model with the approved RTL. Built in parallel with other
post-Stage-6 work; no version bump. Design doc: `docs/RISCV_FIRMWARE.md`.

**Two tools, through the M21 registry.** `src/nirmaan/integrations/firmware_riscv.py`
registers `fw.cross_build` (backend `rv32-gcc`) and `fw.soc_test` (backend
`picorv32-verilator`, also needs `verilator`, `make`), both `AVAILABLE`. The
compiler is `riscv64-unknown-elf-gcc` (Ubuntu) or `riscv64-elf-gcc`
(Homebrew): the backends' `environment` hook takes the first prefix with
`gcc`, `objcopy`, and `size` on PATH, else refuses naming both.
`fw.cross_build` compiles the driver, the tests, and the runtime under M25's
strict flags plus `-march=rv32i -mabi=ilp32 -ffreestanding -Os`, assembles
`crt0.S`, links with `link.ld` and `-lgcc`, and runs `size`: metrics `text`,
`data`, `bss`, `image_bytes`. `fw.soc_test` builds that image, converts it
with `objcopy -O verilog`, builds `nirmaan_soc.v`, `picorv32.v`, and the RTL
with Verilator (`--prefix Vsoc`, the design as `+define+NIRMAAN_DUT=<top>`;
`top` defaults to the one module nothing instantiates), and runs it. Output is
M25's `FWTEST` format, so `parse_soc_test` is `parse_fw_test(...,
what="SoC run")` plus code size. `firmware.py` changed only by that `what`
argument, link errors in `parse_fw_test`, and a shared `copy_rtl`.

**The SoC** (`integrations/firmware_soc/`): PicoRV32 (vendored unmodified,
ISC, SHA-256 pinned by a test; upstream YosysHQ/picorv32 at `ef203c2`), 64 KiB
RAM at 0, the design at `0x1000_0000` behind a native-to-AXI4-Lite bridge, and
control registers at `0x2000_0000` (`STATUS`, `CONSOLE`, `EXIT`, `CYCLES`).
The target HAL is `soc_runtime.c`; `libc/` is a small strict-C libc
(`snprintf`, `mem*`, `strlen`), since Homebrew's GCC ships none.

Key design points worth not re-deriving:
- **Register shift 2.** A CPU never issues an unaligned bus address, but the
  M25 tests check SLVERR for offsets `0x5` and `0xE`. AXI offset N is the CPU
  word at `0x1000_0000 + 4*N` (like `reg-shift = <2>` for 8250 UARTs), so
  every offset is one aligned access and the RTL's own decode answers.
- **Bus errors reach the driver through `STATUS`**, latched from `BRESP` or
  `RRESP` per transfer and read by the HAL after each access; PicoRV32 has no
  bus-error input to trap on. A zero strobe is refused by the HAL with SLVERR.
- **Byte stores replicate the byte** (`write 0x4 = 0xabababab strobe 0x4`); the
  byte-lane check proves the RTL takes only the strobed lane.
- **`-fno-tree-loop-distribute-patterns`**, or GCC may turn the libc's
  `memset` loop into a call to `memset`.
- **The gate is conditional on the request, as data.** New feature `riscv`
  (`RISC-V`, `riscv`, `rv32...`); the firmware stage gains two `checked(...)`
  requirements with `when=when("riscv")`. One generic field,
  `EvidenceRequirement.when: Condition` (default unconditional), read only by
  the planner, which drops a requirement whose condition the request does not
  meet. Required everywhere would make every firmware task need a RISC-V GCC;
  opt-in by the seat (`when_produced`) would let the seat choose its own test.
  `device_drivers` gains both tools.

Tests: `tests/test_nirmaan_riscv_firmware.py` (14): the catalog; a RISC-V
request gates the seat on four checks and a plain one on two; parsers on
captured text; refusal with nothing on PATH; a real cross build (a 32-bit
RISC-V ELF) and a strict warning failing it; a real SoC run passing all six
M25 checks with the RTL's SLVERRs in the log; the wrong driver failing as a
recorded run; the end-to-end seat
(`test_the_firmware_seat_runs_its_driver_on_a_riscv_core`: four real runs
against the approved RTL, review, approval); the crown jewel
`test_a_new_soc_backend_needs_no_core_changes`; the pinned core; import laws.
CI installs `gcc-riscv64-unknown-elf` and adds `riscv64-unknown-elf-gcc` to
`NIRMAAN_REQUIRE_EDA`. The standard run, with M27 review repair merged, is
1140 tests with 2 skipped.

Deferred: interrupts from the design, precise bus-error traps, other cores and
ISAs, a code-size budget in the gate, APB and AXI4 bridges.

### Milestone 27 (DFT) - ATPG, multiple scan chains, and MBIST (after Stage 6)

Two new tools, both `AVAILABLE` and backed by M21 backends in
`nirmaan/integrations/dft.py`: `dft.atpg` (backend `icarus-atpg`) and
`dft.mbist` (`icarus-mbist`); `dft.scan_insert` gains multiple chains. The
step helpers are standard library only: `dft_scan.py` (as in M25),
`dft_atpg.py`, and `dft_mbist.py`. `dft.run` stays `CONTRACT_ONLY`.

Key design points worth not re-deriving:
- **Chains.** `chains` and `max_chain_length` params; flops are grouped by
  (clock, edge), each domain gets at least one chain, spare chains go to the
  domain with the longest chain, and within a domain natural-order runs differ
  in length by at most one. One chain keeps scalar `scan_in`/`scan_out`; N
  chains make them N-bit vectors. The tracer starts a chain at each `scan_in`
  bit and checks `scan_out[k]` and one domain per chain. The M25 rule
  `one-clock-domain` is retired. `dft.scan_sim` pulses all clocks together;
  each clock idles low if any flop uses its rising edge, and the expected
  capture is evaluated in edge order (first-toggle flops, then the rest).
- **ATPG is our own, not an external tool.** Nothing is packaged in Homebrew
  or apt; Atalanta would need a `.bench` converter and a CI build. `dft_atpg.py
  generate`: random 64-pattern batches with bit-parallel cone fault
  simulation, then PODEM (three-valued good and faulty machines, D-frontier,
  X-path, full backtracking, limit 200) on the capture model (scan_en low,
  resets inactive). Fault universe: stuck-at 0/1 on every controllable input
  and gate output of the Yosys gate netlist (stems, uncollapsed).
- **Coverage is measured, not claimed.** `dft_atpg.py inject` enumerates the
  universe again from the netlist, adds a `$_MUX_` per fault site (select
  `nirmaan_fault_en[s]`, value `nirmaan_fault_val[s]`), and Yosys writes it.
  The testbench runs the design as given (good machine) beside the fault
  netlist, through the real scan protocol. It first checks the pattern file's
  expected responses and that the fault netlist equals the design with no
  fault; then, per fault, detection at the first differing output or
  unloaded bit. A claim the simulation does not bear out, a wrong expected
  response, or an injection mismatch fails the run. `min_<metric>` params
  (for example `min_test_coverage`) are checked in `parse_atpg` from
  `atpg_config.json`; `max_` limits work as in M21. `patterns` grades a given
  file; `fault_sample` samples, and says so.
- **A capture-untestable fault can still be detected** by shifting (for
  example a NAND with `scan_en` stuck at 1): the class is from the
  simulation, so `undetectable` means proven by PODEM and not detected.
- **MBIST.** `dft_mbist.py` writes a March C- controller (10N operations,
  solid backgrounds, a read is issue then compare) for a single-port sync RAM
  (`clk`, `we`, `addr`, `wdata`, registered `rdata`) whose widths Yosys reads.
  The testbench counts reads, writes, and cycles independently (5N, 5N, 15N)
  and flags X reads. The controller is `verilator -Wall` lint clean (a test).
- **Seat data.** Skills `atpg`, `fault_modeling`, `scan_design` gain
  `dft.atpg`; `mbist` gains `dft.mbist`. The `block-design` `dft` stage's third
  `checked(...)` requirement is `dft.atpg` with `min_test_coverage` 90.

Measured (8 chains for the register blocks): counter 70/70 faults (100%),
`atpg_demo` 130/132 (2 proven undetectable, 100% test coverage), rr_arbiter
116/116, sync_fifo 754/754, apb_regs 1800/1800, axi4_lite_regs 2476/2476.
The last two take about 2 and 3 minutes of Icarus, so the tests grade only
the smaller blocks. MBIST passes the clean `sync_ram` in 240 cycles and fails
each of six faulty RAMs (stuck-at 0 and 1, transition, inversion and
idempotent coupling, address decoder).

Fixtures: `tests/fixtures/rtl/dft/two_clocks.v`, `dft/atpg_demo.v`,
`mbist/sync_ram.v`, `mbist/faulty_rams.v`. Tests:
`tests/test_nirmaan_dft_advanced.py`; crown jewel
`test_a_new_atpg_backend_needs_no_core_changes`. Design doc:
`docs/DFT_ADVANCED.md`. Deferred: transition faults, pin faults, ATPG across
capture edges, lockup latches, compression, other memory types, a memory stage.

### Milestone 27 (seat evaluation) - Structural review, and seat evaluation

The first milestone of the structural review of 2026-09-29
(`docs/architecture/`: `current-state.md`, `target-state.md`,
`proposed-change.md`, and the resumable `REVIEW_PLAN.md`). The review found
that the brief's engine (task, plan, artifact, evidence, tool broker, roles vs
skills, gates, audit, events, traceability) already exists as `work/` plus
`runtime/`, so it adds no parallel `nirmaan/engine/` package and no duplicate
per-topic docs; it orders the real gaps as M27 to M33 in `target-state.md`
section 5 (seat evaluation is a part of the M27 batch, engineering records of the
M29 batch; M28 and M30 to M33 are this review's own). Released in v1.22.0.

M27 answers "does a seat's work actually work?" with cases as data and judges
that are real tool runs. `evals/rtl/*.json` (four cases: the AXI4-Lite and APB
register blocks, the FIFO, the arbiter) each fix the `rtl-implementation`
seat's upstream to the block's interface spec and microarchitecture, hold a
reference answer for replay, and hold out the block's reference testbench.
`nirmaan.evals.run_case` plans the request in a sandbox, fixes the upstream,
puts any runtime in the seat through the unchanged `run_task`, then runs each
held-out check through the broker and returns an `EvalResult`.
`nirmaan eval list` and `nirmaan eval run [CASE...] (--runtime ID | --replay)`.

Key design points worth not re-deriving:
- **A pass is a recorded run.** The runner records a scorer's "passed" as
  failed unless it cites sandbox runs that all succeeded; a refused tool is
  `not_run`, never a pass; replay results carry `replay: true`.
- **The harness fixes work stages only**, as a `SYSTEM` actor named
  `eval-fixture` whose review text names the reference documents; no human
  attestation. A gate or decision upstream of the seat raises `EvalError`.
  The `new-ip` interface-spec stage fans out into variants, so a seat must be
  exactly one task (validated).
- **Scorers are a registry** (`register_scorer`); one ships, `held-out-run`,
  which fills tool parameters from the seat's submitted files by kind, then
  the case's files. Runner and scorers name no stage, tool, kind, or role.
- Case digest: SHA-256 over the case and every file it names.
- Rich markup swallowed `[rtl-implementation]` in CLI lines; whole lines are
  escaped now and a test asserts the brackets appear.

`tests/test_nirmaan_evals.py` (15 tests; on v1.21.0 the standard local run is 1218 passed, 3 skipped), including replay passing on all four
blocks with real tools, and `test_what_the_gates_miss_the_held_out_testbench_catches`
(RTL with `reg3` reset to all ones and a testbench that checks nothing passes
lint, simulation, and synthesis and reaches review; the reference testbench
fails it). Crown jewel `test_a_new_case_or_scorer_needs_zero_core_changes`.
Design doc: `docs/SEAT_EVALUATION.md`; case format: `evals/README.md`.

Deferred: the first live-model run (`--runtime anthropic`), token and cost
accounting (M31), mutation scoring of a seat's testbench, held-out proofs,
specification-seat cases.

### Milestone 28 - Tool contracts (structural review, milestone 2)

Every tool with a binding declares what it takes, and the broker holds
callers to it before anything runs. Design doc: `docs/TOOL_CONTRACTS.md`.
Version bump left to the coordinator.

- **Vocabulary** (`models/org.py`): `ParamKind` (text, path, paths, integer,
  number), `ParamSpec` (name, kind, required, description, `prefix` for
  families such as `max_<metric>`), `ToolSpec.params` (None: no contract,
  taken as given, which keeps extension tools working), `list_values`, and
  `ToolRun.values(param)`.
- **Catalog** (`company/tools.py`): all 24 bound tools declare parameters (19 when written; the M27 parts added
  `formal.cover`, `dft.atpg`, `dft.mbist`, `fw.cross_build`, `fw.soc_test`, given contracts at the merge),
  inventoried from what every binding and backend actually reads (both quote
  styles; OpenROAD's settings included though nothing here can run it).
  Shared tuples: `RUNNER` (backend, workdir, timeout, max_), `PDK`,
  `PDK_REQUIRED` (sta and pnr probes refuse without Liberty), `NETLIST`.
- **Broker** (`runtime/tools.py`): `check_params` after the authority check:
  an undeclared name or an ill-typed integer or number raises
  `ToolContractError` (a `ToolAccessDenied`, so every caller already reports
  it) and records no run. A `paths` value may be a list; an element with a
  comma is refused; lists are stored comma-joined as before, so stored
  projects and bindings are unchanged. A `path` takes a one-element list.
- **Runtime**: each tool gets only the task inputs its contract declares
  (`ToolHandle.declared`), so `input.workspace` no longer reaches lint; file
  parameters go to the broker as lists.
- **Required is declared, not enforced by the broker.** A missing required
  input stays a recorded failed run (the M21/M25 rule, asserted by a physical
  test); M28 does not re-decide it.
- `nirmaan org tool ID` prints a tool's contract and whether it runs here.

Found on the way: two refusal tests passed one parameter dict to every tool
(`top` to formal, the LEFs to OpenSTA); they now pass each tool its own
parameters. The runtime passed `sby` as a one-element list, which is why a
`path` accepts one.

`tests/test_nirmaan_contracts.py` (13), including a static scan that every
parameter an integration reads is declared, and the crown jewel
`test_a_new_tool_contract_needs_no_core_changes`. On v1.21.0 the standard local run is
1231 passed, 3 skipped. Deferred to the next M28 part: typed values end to end (a
`ToolRun` storing real lists) and the typed work packet.

### Milestone 29 (verification plan) - Plans loaded from a file, and a plan seat (after Stage 6)

Closes M24's first deferral. A verification plan (requirements, and the items
that prove them) is a small JSON format, `nirmaan.vplan` version 1, read and
written by `nirmaan/vplan.py`; a seat writes one on `block-design`, a real tool
checks it before review, and the engine records it on approval.

Key design points worth not re-deriving:
- **Format.** `{"format", "version", "requirements": [{id, text, source,
  section}], "items": [{id, kind, file, name, proves, rationale}]}`. Unknown
  fields are refused (a plan cannot say `status` or `passed`), kinds must be
  registered, `proves` must name requirements in the file. JSON, not YAML:
  there is no YAML dependency. A pure-Python `JSONDecoder` whose
  `parse_object` records each object's line and each value's line gives
  `line N:` reasons.
- **Import is all or nothing, through the engine.** References (`source`,
  `file`) resolve by artifact ID, recorded path, or unique file name. The
  records are first made on a scratch `TaskEngine` over the same state; any
  refusal (M24 actor rule, duplicates, policy) is collected with its line and
  nothing is recorded. CLI: `nirmaan vplan import PROJECT FILE --as ROLE` and
  `nirmaan vplan export PROJECT [--out FILE]`; export is canonical (sorted,
  `indent=2`, file names when unique), so an imported file exports back
  byte for byte.
- **Spec requirements are tagged** `[req:ID]` in the Markdown list item or
  paragraph (`REQUIREMENT_TAG` in `company/traceability.py`); text is that
  item without marker or tag, section is the nearest heading's number. The
  AXI4-Lite fixture spec now tags the eight M24 demo requirements.
- **The seat is data.** Feature `verification_plan` ("verification plan",
  "vplan", "test plan"); a `dv-plan` stage on `block-design` (capability
  `dv.plan`, output `verification_plan`, after `interface-spec`, conditional on
  the feature, nothing depends on it, so every existing plan and every
  workflow built from block-design stages is unchanged). Before review:
  `vplan.check` (new, AVAILABLE, in-process, `integrations/vplan.py`, granted
  by `verification_planning`) over `plan` and the approved upstream
  `interface_spec` (`spec`, `upstream=True`): valid, covers exactly the tagged
  requirements, quotes each, plain item file names.
- **On approval.** `TaskEngine` gains `register_approval_consumer(kind, fn)`:
  `fn(engine, artifact)` runs before the approval commits (raise to refuse;
  nothing changes) and returns what to record after it commits. The engine
  names no kind. `nirmaan.vplan` registers for `verification_plan`, acting only
  when the artifact's stage checks it with `vplan.check` (so `new-ip`'s
  document plans are untouched); it re-checks the digest-verified plan against
  the digest-verified approved spec and records as the system actor, with
  `plan` in each audit entry. `nirmaan/work/__init__.py` imports `nirmaan.vplan`
  last, so the consumer is registered wherever the engine is.
- **Planned items.** `VerificationItem` gains `file` and `plan`; `artifact`
  defaults to empty. `TaskEngine.record_planned_item` applies the M24 checks
  with the actor rule on the plan artifact. `engineering.holding_artifact`
  binds a planned item, on every query, to the latest recorded artifact of
  that file name; with none it is `unverifiable` ("no recorded artifact holds
  ... yet"). The graph adds `planned_in` edges.

Demo (real tools): "Create an AXI4-Lite register block with a verification
plan." The plan seat writes `tests/fixtures/rtl/axi4_lite/verification_plan.json`
(8 requirements, 6 items), it is checked, reviewed, approved, and recorded
before any RTL; after the real simulation `nirmaan gaps` reports 5 of 8
backed, with AXIL-B2B, AXIL-SYNTH, and AXIL-FORMAL gaps, as in M24.

Tests: `tests/test_nirmaan_verification_plan.py`; crown jewel
`test_a_plan_seat_against_a_new_spec_kind_with_a_new_item_kind_needs_no_core_changes`.
Design doc: `docs/VERIFICATION_PLAN.md`. Deferred: YAML, planned items in an
import, amending recorded plans, non-Markdown spec tags, the plan seat on
`new-ip` and `feature-addition`.

---

### Milestone 29 - An unattended owner and reviewer loop in one command (after Stage 6)

`nirmaan drive PROJECT [TASK] --runtime ID --reviewer-runtime ID` strings M27's
steps together: the owner seat (`run_task`, with M26 attempts and M27 limits),
the planned reviewer seat (`review_task`), the owner again after a change
request, and so on, until a person must act. With no TASK it drives every
ready task in dependency order. Design doc: `docs/AUTO_LOOP.md`.

Key design points worth not re-deriving:
- **The loop holds two seats only.** `nirmaan/runtime/loop.py` calls
  `run_task` and `review_task` and nothing else that changes state, apart from
  its audit entry. It never approves a task, signs a gate (human-required or
  not), completes, resolves, unblocks, or cancels; a test checks the module's
  calls. A passed review stops at `awaiting_approval`; a ready gate stops at
  `awaiting_gate`, so dependents stay planned until a person acts. Tasks with
  no review complete on submission (the engine's rule), so their dependents
  are driven in the same invocation.
- **Next step from state alone** (`next_step`): `ready`, `changes_requested`,
  `in_progress` mean the owner; `in_review` with review `pending` means the
  reviewer; everything else is a `Stop` (`awaiting_approval`, `conflicted`,
  `escalated`, `blocked`, `waiting`, `done`, `awaiting_gate`). Results add
  `declined`, `refused`, and `budget`. After a `refused` owner step the loop
  continues only when the next owner run would escalate (no call); with one
  attempt M26 records nothing, so it stops rather than ask forever.
- **Budget:** `--max-calls` (default 20) per invocation. A call is one owner
  attempt (`len(report.attempts)`) or one reviewer step (always charged 1). A
  step starts only if its worst case fits: `owner_calls` is the stage's
  attempts minus this round's refused attempts, or 0 when `exhausted` (M27's
  check, extracted from `_exhausted` in `runtime/base.py` and now public). The
  task limits in state still cap every task across invocations.
- **Audit and resume:** `TaskEngine.record_step` (the one engine addition)
  writes `loop.step` on the task as the acting seat (an AI agent named for its
  runtime), with step, seat, runtime, status, calls, review, escalation,
  attempts, and tool runs. The CLI saves after every step (`on_step`), so an
  interruption loses at most the step in flight; rerunning resumes.
- **Independence:** the reviewer is always the task's planned reviewer (P6 is
  checked inside `review_task`). `--reviewer-runtime` defaults to `--runtime`;
  the doc justifies that (different seat and packet, a fresh stateless review
  prompt that never carries the owner's prompt, grounded verdicts, and a
  person still approves). The CLI notes a shared runtime on stderr.
- `plan_loop` gives the worst case sequence as data for `--dry-run`; nothing
  is called or saved. `--input` needs a TASK.

`tests/test_nirmaan_auto_loop.py` (19 tests): the full loop on the AXI4-Lite
interface spec in one CLI command (owner, change request, repair, approving
review, stop at the human approval, then a person approves); the same on real
AXI4-Lite RTL with a formal counterexample repaired inside an attempt
(`NIRMAAN_REQUIRE_EDA`); never self-approves; project mode stops at a gate
(human-required or not) and never crosses it; the budget before a step and an
owner charged its attempts; resume after a crash from saved state; spent
rounds and spent attempts escalate with no call; a refusal with one attempt
stops; a decline stops; the plan and `--dry-run`; a shared runtime is named;
crown jewel `test_a_new_workflow_is_driven_with_no_core_changes` (a gated
two-stage workflow and a runtime, both written in the test); the loop names
nothing and keeps the import laws; every step audited as its seat.

Deferred: concurrent tasks; a call budget across invocations; approval by a
delegated non-human approver; task inputs in project mode.

### Milestone 29 (engineering records) - Decisions and failures, as views (structural review, milestone 3)

The third structural-review milestone, a part of the M29 batch.
"Why did we choose this?" and "what went wrong, and was it fixed?" answered
from the record. Design doc: `docs/ENGINEERING_RECORDS.md`. No version bump.

Key design points worth not re-deriving:
- **Views, not new fields.** Inspection found that nothing in the product calls
  `record_decision`: the decisions made are DECISION tasks, which already hold
  every decision-record field (outcomes as alternatives, outcome, artifacts as
  rationale, evidence, `task.submit`/`task.approve` audit entries, and the
  branches `_take_branch` cancelled as consequences). M27's review repair
  already moves superseded artifacts into an `Attempt`. So
  `nirmaan/records.py` reads state and stores, infers, and audits nothing.
- **Failure categories come from structure, never prose**: `check_failed` (a
  failed `ToolRun`; resolved by a later successful run of the same tool on the
  same task), `review_sent_back` (an `Attempt` with reviews), `submission_refused`
  (an `Attempt` with no failed run of its own), `blocked` (`task.block`,
  resolved by `task.unblock`), `failed` (`task.fail`), `escalated` (an
  `Escalation`, resolved with its resolution). Ordered by audit sequence.
  `failure_summary(states)` counts by category and subject across projects.
- Surfaces: `nirmaan decisions PROJECT`, `nirmaan failures PROJECT...` (both
  `--json`), export sections `decisions` (in `10_signoff`) and `failures` (in
  `09_evidence`) through the section-writer registry and the folder table, and
  MCP read tools `decisions` and `failures`.
- The records-names-nothing test leaves platform tools out of its vocabulary:
  `task.cancel` and `escalation.raise` are both platform tool IDs and the
  engine's audit actions.
- Two projects planned from the same request under a fixed clock share an ID;
  the cross-project test uses two requests.

`tests/test_nirmaan_records.py` (10), including Demo 4's `root-cause` decision
(four alternatives, `rtl_bug`, three cancelled branches) and the crown jewel
`test_a_new_decision_stage_is_recorded_with_no_core_changes`. With the M29 loop merged,
the standard local run is 1260 passed, 3 skipped. Deferred: recording explicit decisions
from the CLI or MCP, declined model answers (the engine records nothing for
them), principle IDs on refusals, learning from the summary.

### Milestone 29 (gates) - The RTL gates on the remaining workflows, and automatic antecedent covers (after Stage 6)

Every stage that produces `rtl_source` now carries `RTL_GATES`: M29 adds
`parameter-change` `rtl-change`, `regression-investigation` `rtl-fix`,
`timing-closure` `rtl-fix`, and `new-ip` `cdc-design` (each also produces a
`testbench`; a test enumerates `WORKFLOWS` so no RTL stage is ungated). And
the `formal.cover` run behind `NOT_VACUOUS` now derives a cover for every
assertion's antecedent, so a proof whose assertions sit under guards that
never hold is refused. Design doc: `docs/GATES_REST.md`.

Key design points worth not re-deriving:
- **`cdc-design` needed two data edits.** `rtl.cdc_design` gains
  `approved_inputs=True`, and the `cdc_design` skill gains the five gate tools:
  the runtime runs before-review checks as the seat, and the broker refuses a
  tool the role may not use. The skill does not include `rtl_design`, so
  routing is unchanged.
- **No STA before review on the timing fix.** `reanalysis` already re-runs
  `sta.run` after the fix and is the implementation gate; STA needs a Liberty
  netlist, SDC, and PDK the RTL seat does not produce; and it runs only in CI's
  `physical-design` job, so a before-review STA would either silently not
  apply or block every timing fix on most machines. Tightening `reanalysis` to
  a real run is deferred to the PD signoff work.
- **Antecedent covers are derived by elaboration, not by parsing guards.**
  `integrations/eda_antecedents.py` (imports nothing of Nirmaan) wraps each
  procedural assertion as `begin cover (1'b1); <assertion> end`, so Yosys
  gives the cover exactly the assertion's path condition: every `if`, `else`,
  `case` arm, loop iteration, generate instance, and task call. A top-level
  `A |-> B` covers `A` (module scope: `cover property (A);` after it); a
  module-scope assertion with no implication is `unguarded`. Inserted text
  never adds a newline; the manifest `<run>/antecedents.json` records each
  derived cover's file, line, and column, and `parse_sby_cover` counts those
  apart from the seat's covers (`antecedents_reached`, `_unreached`,
  `_unelaborated`; `covers_*` stay the seat's).
- **Never silently skipped.** Sequence operators, nested or chained
  implications, named properties, action blocks, deferred assertions, and
  macros whose body asserts are refused by the backend's precheck, as a
  recorded failed run listing each file, line, and reason. A derived cover
  missing from the elaborated design (generate branch not taken, task never
  called) is a warning, not a failure.
- **The seat's files are never edited.** The cover `.sby`'s `[files]` names
  the instrumented copies in `<run>/antecedents/`. All seven fixture setups
  pass unchanged: counter 1, AXI4-Lite 14, FIFO 18, arbiter 33 (N=5: 45), APB
  38 derived covers reached.

Tests: `tests/test_nirmaan_gates_rest.py` (47): the stages as data and
the registry-wide law; the CDC seat's data; on each of the four stages a latch
and a failing self-check refused, clean RTL with a proof approved, and a
never-checked assertion refused while `formal.run` passes; derivation on every
fixture (same lines, nothing else changed) and every fixture antecedent
reached; an unreachable antecedent and an underivable assertion as recorded
failed runs; the deriver and parser on text; crown jewel
`test_a_new_workflow_with_the_gates_refuses_a_never_checked_assertion_with_no_core_changes`;
`drive` on a newly gated stage; the core never names antecedents; CI requires
the formal tools. Migrated (design doc, section 4): one M27 test, which now checks that the
cover run reads an instrumented copy differing only by the derived cover; the
bridge plans that reach `cdc-design` already drove the gated
`rtl-implementation` first and pass unchanged. `formal.cover` gains no
parameter, so its M28 contract is unchanged. The standard run, merged with
main (M28 contracts, M29 auto loop), is 1297 passed and 3 skipped (OpenROAD).

Deferred: a real `sta.run` on `timing-closure` `reanalysis`; antecedents of
boolean implications inside an immediate assertion; expanding named
properties and macros; multi-task setups in the cover check.

### Milestone 29 (DFT) - Transition ATPG, lockup latches, and an MBIST stage (after Stage 6)

One new tool, `AVAILABLE`: `dft.atpg_transition` (backend
`icarus-atpg-transition`, in `nirmaan/integrations/dft.py`); `dft.scan_insert`
gains `cross_domains=lockup` and `dft.mbist` makes `top` optional. Design doc:
`docs/DFT_NEXT.md`.

Key design points worth not re-deriving:
- **Transition faults are two-frame stuck-at faults.** `build_model` in
  `dft_atpg.py` copies the capture model into a second frame
  (`CaptureModel.copy_frame`); `net/STR` is the frame-2 copy stuck at 0 with a
  need (`Fault.need`) that the net is 0 in frame 1. PODEM treats needs as goals
  and contradictions as dead ends, so "untestable" is still a proof. Primary
  inputs are held through launch and capture (launch on capture only; LOS is
  deferred), so their transitions are proven undetectable.
- **The grader's delay model.** In the fault netlist each site gets a flop on
  `nirmaan_fault_clk` holding the previous value and becomes `net & prev`
  (STR) or `net | prev` (STF), only while `nirmaan_fault_en[s]` and
  `nirmaan_fault_atspeed` are high; the testbench raises at-speed 1 ns after
  the launch edge and drops it 1 ns after the capture edge. Pattern files carry
  `fault_model` (absent means stuck-at) and a mismatch is refused.
- **Stuck-at across capture edges is now modelled, not refused**: second-edge
  flops capture from a copy of the logic whose first-edge flops hold their new
  state; a fault sits on both copies (`Fault.extra`). Transition ATPG over two
  edges is still refused with the reason.
- **Lockups.** With `cross_domains=lockup`, flops are ordered second-edge
  domains first, then by clock port and edge, cut into balanced chains, and a
  `$_DLATCH_N_` (after a rising-edge flop) or `$_DLATCH_P_` goes on each clock
  crossing. `Design.lockups` are latches whose D is a flop Q and enable a
  module input; `no-latches` skips them unless they reach capture logic
  (`lockup_leaks`). The tracer reports `hazards` (an unlatched crossing, a
  wrong latch, a second-edge flop loading a first-edge one), which make a chain
  incomplete. `dft.scan_sim` with several clocks runs the shift three times:
  together, skewed 1 ns per clock, and skewed in reverse.
- **MBIST.** With no memory as top, every module with the single-port
  interface in the hierarchy is a memory, each with its own controller in one
  testbench. `(* read_latency = N *)` sets the latency (default 1); the
  testbench measures it first (word 0 zeros, word 1 ones, switch the address)
  and a mismatch fails the run. Cycles are (10 + 5L)N.
- **Data.** Features `memory` (RAM, SRAM, memory array, MBIST) and `at_speed`
  (implies `dft`); `block-design` gains an `mbist` stage (`dft.mbist` over the
  approved upstream `rtl_source`, no top) and the `dft` stage a fourth check,
  `dft.atpg_transition` with `min_test_coverage` 80, `when=when("at_speed")`.
  Skills `atpg`, `fault_modeling`, `scan_design` gain the new tool. Under the
  M28 contracts, `dft.atpg_transition` declares `dft.atpg`'s parameters,
  `dft.scan_insert` declares `cross_domains`, and `dft.mbist`'s `top` is no
  longer required.

Measured transition coverage (launch on capture): counter 53/70 (17 proven
undetectable), `atpg_demo` 87/132 (45), rr_arbiter 92/116 (24): 100% test
coverage each. The lockup `two_clocks` chain shifts clean in all three passes;
with the latch made a wire, `dft.check` reports the crossing and the skewed
shift loses 8 bits. MBIST passes `sync_ram_2cycle` (32x16, latency 2) in 640
cycles.

Fixtures: `mbist/sync_ram_2cycle.v`, `mbist/ram_block.v`, `mbist/block_ram.v`,
`mbist/ram_block_tb.v`. Tests: `tests/test_nirmaan_dft_next.py`; crown jewel
`test_a_new_transition_backend_needs_no_core_changes`. Deferred: launch on
shift, transition ATPG over two capture edges, pin and path delay faults,
parameterized memory instances, multi-port memories, a memory collar.

---

---

### Milestone 29 (RISC-V) - interrupts, a second core, a code-size gate, and APB (after Stage 6)

Closes four of M27's deferred RISC-V items. Built in parallel with other
post-Stage-6 work; no version bump. Design doc: `docs/RISCV_NEXT.md`.

**Cores and buses are data** in `src/nirmaan/integrations/firmware_riscv.py`:
`CORES` (`Core(name, module, verilog, runtime, march)`, `register_core`) holds
`picorv32` (default) and `serv`; `BUSES` (`Bus(name, module, verilog, ports)`,
`register_bus`) holds `axi4-lite` and `apb`. `fw.cross_build` and
`fw.soc_test` take `core=`; the bus is read from the top module's ports
(`design_ports`, `bus_of`). The SoC instantiates `` `NIRMAAN_CORE `` (a
wrapper, `core_<name>.v`, with PicoRV32's memory interface, `trap`, and `irq`)
and `` `NIRMAAN_BRIDGE `` (`bridge_axil.v` or `bridge_apb.v`, each of which
instantiates `` `NIRMAAN_DUT ``), so `nirmaan_soc.v` names no core, bus, or
design. The `fw.soc_test` backend keeps its M27 name `picorv32-verilator`.
The one new parameter, `core`, is declared (M28 contracts) on both tools in
`company/tools.py`; the IRQ and the bus need none, being read from the RTL.

Key design points worth not re-deriving:
- **SERV 1.4.0** (olofk/serv, commit `7d9cde4`), seventeen `rtl/` files
  unmodified in `firmware_soc/serv/` with its ISC `LICENSE`, every SHA-256
  pinned. `serv_compdec.v` keeps Ibex's Apache-2.0 header (unused with
  `COMPRESSED=0`, but Verilator resolves the generate branch). Chosen over
  VexRiscv because VexRiscv's Verilog is generated from SpinalHDL. SERV is
  bit-serial: about ten times PicoRV32's cycles (682,218 against 63,642 for
  the register block).
- **The wrapper aligns SERV's address** (it puts a byte store's byte address
  on the bus) and shares one port between its I and D buses, which are never
  active together.
- **Interrupts.** A design output named `irq` adds `+define+NIRMAAN_DUT_IRQ`;
  the bridge wires it to the core. PicoRV32: `ENABLE_IRQ`, QREGS, `irq[3]`,
  level sensitive (`LATCHED_IRQ` bit 3 clear), `PROGADDR_IRQ` 0x10, `maskirq`
  and `retirq` emitted with `.insn`. SERV: `WITH_CSR=1`, the line on
  `i_timer_irq` (its only one), `mtvec` = 0x10, `mstatus.MIE`, `mret`; its
  exceptions also arrive at 0x10 and end the run as `FWTEST ERROR the CPU
  trapped`. `crt0.S` puts the vector at 0x10; `irq_<core>.S` defines
  `nirmaan_core_init`, `nirmaan_core_irq_set`, `nirmaan_core_trap`.
- **`nirmaan_irq.h`** (in `firmware_harness/`, the platform's): `attach`,
  `count`, `wait`. Each HAL access plus its `STATUS` read is a critical
  section, or a handler touching the device could overwrite `STATUS`.
- **No precise bus-error traps.** Neither core has a bus-error input, and
  SLVERR on an external IRQ line would be an imprecise interrupt; `STATUS`
  stays. A core with `data_err_i` (Ibex) would be the path.
- **`max_text_bytes`.** `_size` adds `text_bytes`; the `block-design`
  firmware stage's `fw.cross_build` requirement carries
  `params=(("max_text_bytes", "16384"),)` (images are about 10 KiB).

Fixtures: `tests/fixtures/rtl/axil_timer/axil_timer.v` (AXI4-Lite one-shot
timer: `CTRL` EN and IE, `LOAD`, read-only `COUNT`, W1C `STATUS`,
`irq = EXPIRED && IE`), its driver and interrupt tests in
`tests/fixtures/fw/axil_timer/`, and an APB driver in
`tests/fixtures/fw/apb_regs/` for the M26 `apb_regs.v`.

Tests: `tests/test_nirmaan_riscv_next.py` (20): the gate's limit; `text_bytes`;
cores and buses as data; the SoC naming nothing; an unknown core and an
unknown bus as recorded failed runs; an oversized image refused; on both
cores, the register driver, the timer's five interrupt checks, the two broken
IRQs (stuck low, ignoring IE) each failing the expected checks, and the APB
driver; a wrong APB map failing; crown jewel
`test_a_new_core_needs_no_core_changes` (a third core from a temporary
directory); SERV pinned; import laws. One M27 assertion changed: a cross build
now compiles six files (the core's interrupt runtime). CI is unchanged.

Deferred: precise bus-error traps, interrupts and APB in the host
co-simulation (`fw.test`), more than one interrupt line, and running the gate
on both cores.

### Milestone 29 (PD signoff) - Power grid, CTS, extraction, and signoff STA on the SPEF (after Stage 6)

`pnr.run` stopped at a routed layout with no power grid, an ideal clock, and
estimated parasitics (M27). It now runs the signoff steps in the same staged
OpenROAD session, for real on Nangate45 and sky130hd in the `physical-design`
CI job, and the workflow asks for their evidence as data. Design doc:
`docs/PD_SIGNOFF.md`. No version bump.

Key points worth not re-deriving:
- **Stages** are `floorplan`, `place`, `cts`, `route`, `extract` (then
  `timing`). Each optional step runs only when its PDK input is given:
  `tap_cell`/`endcap_cell`/`tap_distance`, `pdn_tcl` (sourced, then `pdngen`),
  `rc_tcl` (layer RC), `filler_cells`, `supply_voltage` (IR analysis),
  `rcx_rules` (enables `extract`, and is then the default `stop_after`),
  `dont_use`, `routing_layers` (`LOWEST,HIGHEST`; a `max_` name is read as a
  limit), `cts_buffers`, `place_density`. All declared in `company/tools.py`
  (M28). `synth.run` takes `buffer_cell` (`CELL/IN/OUT`, `insbuf`) so no
  output port drives another through an `assign`.
- **CTS needs `rc_tcl`** (`RSZ-0089` without it), so a run that reaches `cts`
  without it is refused like a missing PDK file.
- **Parsed**: `slack_by_stage` (place: ideal clock; cts: propagated; route:
  global-routing estimate; extract: SPEF), CTS buffers and sinks, skew,
  insertion delay, taps, endcaps, fillers, `power_grids`,
  `unconnected_supply_pins` (Nirmaan's own count after a second
  `global_connect`), antenna violations, worst IR drop per supply net, and
  `unannotated_nets`. Pass adds: every supply pin connected when a grid was
  built and the block routed, and no antenna violation.
- **`unannotated_nets`, not unannotated drivers**: the unused `QN`s (Yosys
  names their nets), CTS dummy loads, and the `inout` `VDD`/`VSS` ports drive
  nothing and have no wire; the scripts list them and the parser counts, by
  name, the unannotated drivers that do drive something.
- **Signoff STA on the SPEF is data**: `sta-signoff` asks for an `sta.run`
  made with `max_unannotated_nets=0`; a run without a SPEF never reports the
  metric and fails the limit. A new `power-grid` stage (`pd.power_plan`) asks
  for `max_unconnected_supply_pins=0`; `place-route` adds that and
  `max_drc_violations=0`. `ran()` takes keyword arguments; `power_grid` joins
  `04_rtl`. `sta.run` with a `spef` propagates clocks.
- **Standalone OpenSTA** is built in the job from the commit the image's
  OpenROAD embeds (`The-OpenROAD-Project/OpenSTA` `e983e15b`), cached by
  commit; `NIRMAAN_REQUIRE_EDA` there is `yosys openroad sta`.
- **Real numbers** (CI run 37632069804, 100 MHz, typical corner): Nangate45
  signoff routes with 0 DRC, 12562 um, 43%, every supply pin connected, IR
  drop 1.56 mV on VDD, 17 clock buffers for 206 sinks, skew 0.003 ns, insertion
  delay 0.111 ns, setup slack 7.471 (place), 7.449 (cts), 7.435 (estimated),
  7.449 ns (extracted), hold 0.155 ns; separate signoff STA on the SPEF gives
  7.449 / 0.155 through both STA backends. sky130hd: 0 DRC, 30569 um, 518 taps,
  skew -0.009 ns, insertion delay 0.456 ns, setup 4.197 estimated and 4.419 ns
  extracted. 5 GHz to `cts`: -0.249 ns after repair, a recorded failed run.
- **Not available**: multi-corner timing (both platforms ship one Liberty
  corner); a KLayout or Magic DRC/LVS deck; metal fill; an IR limit.

Fixtures (captured from that run): `openroad_route.log` (re-captured with
CTS), `openroad_signoff.log`, `opensta_spef.log` (standalone OpenSTA). CI time:
the `physical-design` job went from 2.5 to 7 minutes with an uncached OpenSTA
build (3.6 minutes cached), in parallel with the 5 to 7 minute main
jobs. Tests: `tests/test_nirmaan_physical.py`; crown jewel
`test_signoff_on_extracted_parasitics_needs_no_core_changes`, and the M25
crown jewel now meets the M29 limits.


---

### Milestone 30 - The register map as data

The fourth structural-review milestone: a
register map that was only a table in an interface spec becomes an
intermediate representation that is validated, lowered, and judges RTL.
Design doc: `docs/REGISTER_MAP.md`. No version bump.

Key design points worth not re-deriving:
- `RegisterMap` (`models/regmap.py`): block, bus, `addr_width`, 32-bit
  registers with `rw`/`ro`/`wo` access and reset values, and the `unmapped`
  response (`slverr`, `decerr`, `okay`). No bit fields yet.
- `nirmaan/regmap.py`: `validate` (width, alignment, address space, overlaps,
  C identifiers, duplicates, reset width), a lowering registry
  (`register_lowering`; `c-header` compiles under strict flags and agrees with
  the hand-written firmware header; `markdown` reproduces the AXI4-Lite spec's
  section 3 table line for line), and `c_test`, a `nirmaan_fw_test` whose
  checks run in order (reset values, write-then-read with every register
  written first, read-only, strobes, unmapped) because the co-sim parser names
  only the first failing check.
- Tools with contracts: `regmap.check` (validation as a recorded run) and
  `regmap.verify`, a backend that writes the generated test and reuses
  `fw.test`'s co-simulation steps and parser unchanged. A bus with no harness
  (APB: the host harness drives AXI4-Lite only; M29's `fw.soc_test` reaches APB
  through a RISC-V core) is a recorded failed run, never a simulation. Granted to `rtl_design`
  (both) and `interface_specification` (check).
- The `rtl/axi4-lite-regs` evaluation case holds the map out as a second judge;
  the gates-miss eval test now expects both judges to fail the `reg3` mutant.
- Not adopted in a workflow yet: an added expected output would show as a
  missing deliverable in the export; a conditional-on-upstream rule is needed.
- The M23 crown jewel's hypothetical `regmap.check` collided with the core
  tool and was renamed `regmap.overlaps`.

`tests/test_nirmaan_regmap.py` (19): real co-simulation passes on the fixture
RTL and fails on a `reg3` reset mutant, a REG2-into-REG1 alias, and a map that
misstates the unmapped response; crown jewel
`test_a_new_lowering_needs_no_core_changes`. With the M29 parts merged, the
standard local run is 1387 passed, 3 skipped.

### Milestone 31 - Model selection by capability, and every model call counted

The fifth structural-review milestone. Design
doc: `docs/MODEL_SELECTION.md`. No version bump.

Key design points worth not re-deriving:
- **Accounting is the engine's.** `ModelRuntime` lists every call it made in its
  `WorkResult`/`ReviewResult` (`model_calls`); `run_task` and `review_task`
  record each through `TaskEngine.record_model_call` (audited `model.call`)
  before anything else, so a declined, refused, or failed call is still
  counted. `ProjectState.model_calls` is a new, defaulted field (old projects
  load). Usage travels VeriTriage `GenerationResponse` (new optional token
  fields, the only VeriTriage change) -> bridge `Generation` -> `Completion`.
  The Anthropic provider reads `response.usage` (`input_tokens`,
  `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`);
  a missing `usage` is `None`, never zero. Cost comes from the model's profile
  (`cost_of`); unknown price or usage is `None`.
- **Prices** (claude-api skill, cached 2026-09-25): Opus 5.5 $4 input, $20
  output, $0.20 cache read per million tokens; cache write 1.25 times input.
  `context_chars` is 400,000, matching the provider's declared prompt budget.
- **Needs are derived, not hand-written**: `structured_output` always, `files`
  when an evidence requirement runs over files the task produces, plus the new
  `Capability.model_needs`. `select_model` keeps profiles offering every need
  whose budget holds the rendered prompt, excludes `for_testing` profiles unless
  asked, picks the cheapest known price (ties by ID), and lists every rejection.
- **The `auto` runtime** is `ModelRuntime(SelectingLLM())`; with nothing fitting,
  it declines with the reasons and makes no call (the `NO_CALL` prefix keeps it
  out of the accounting). `MockLLM(model=...)` reports a profile's model.
- `nirmaan costs PROJECT [--json]`; evaluation results gain `model_calls`,
  `input_tokens`, `output_tokens`, `cost_usd`.

`tests/test_nirmaan_model_selection.py` (14), crown jewel
`test_a_new_model_profile_needs_no_core_changes`. The standard local run is
1401 passed, 3 skipped.

### Milestone 32 - Scalable state: hidden edits impossible, chains verified once

The sixth structural-review milestone. Design
doc: `docs/SCALABLE_STATE.md`. No version bump.

Measured first: one recorded tool run cost 3.6 ms on the 55-task NoC project,
95 ms at 5,000 runs; 68% was P10's whole-state fingerprint (twice per
operation), 32% P11's full chain re-verification. After: 0.25 ms at 5,000 runs.

Key design points worth not re-deriving:
- **P10 by construction, then identity.** `FrozenDict`/`FrozenList`
  (`models/frozen.py`, standard library only) are `dict`/`list` subclasses whose
  mutators raise `TypeError`; they serialize identically, and every copy
  (`dict()`, `copy.deepcopy`, pickle) is plain and writable. The engine freezes a
  state on takeover (`work/frozen.freeze_state`) and every container it
  commits; record dict fields (`ToolRun.params`, `AuditEntry.details`, the
  analysis's `feature_evidence`/`parameters`, `Project.gate_overrides`) are
  deep-frozen by field validators. With nothing editable in place, P10's check
  compares the engine's state with the one it committed by identity.
- **P11 incremental.** `verify_chain(trail, start, previous)`; the engine
  verifies a trail in full when it takes it over and remembers the verified
  length and head. A chain that arrives broken is never marked verified, so
  every operation re-checks it in full and is refused.
- A source law test: no Nirmaan module writes through `object.__setattr__` or
  `__dict__[...]`. `state_fingerprint` stays for stores and tools.
- Tests count hashing instead of timing it, so CI is stable.

`tests/test_nirmaan_scalable_state.py` (14). The standard local run is 1415 passed,
3 skipped. Found on the way: the vocabulary may import only `__future__`, `enum`,
`datetime`, `typing`, and pydantic, so the frozen containers copy through
`__reduce__` alone (no `copy` import).

### Milestone 33 - Learning proposals: recurring failures propose, a person decides

The seventh and last structural-review milestone . Design doc: `docs/LEARNING_PROPOSALS.md`. No version bump.

Key design points worth not re-deriving:
- **A view over failure records (M29)**, never a writer: `learning_proposals(org,
  states)` runs a registry of rules (`register_proposal_rule`) over every
  project's `failure_records`. Two ship: `recurring-check-failure` (one tool
  failing work of one capability in at least `MIN_TASKS` = 2 different tasks ->
  a failure mode and a procedure) and `recurring-review-send-back` (reviews
  sending one capability's work back in two tasks -> a validation criterion
  quoting the reviewers). Targets are the skills that provide the capability
  (`org.providers_of`). The ID hashes rule, capability, and subject, so it is
  the same proposal as evidence grows; every proposal cites every record.
- **Deciding is a recorded human decision**: `decide_proposal` refuses any actor
  that is not human, refuses a project the proposal does not rest on, and calls
  `TaskEngine.record_decision` (cross-team, medium: the authority matrix
  requires a manager or above). It shows in `nirmaan decisions`; a proposal's
  status is the latest such decision across the projects read.
- **Adopting edits no skill.** Skills are company data in
  `company/skills.py`; an adopted proposal is the reviewed reason for a person's
  pull request. No new workflow was added: the landing-site tests tie the
  public page's workflow count to the organization, so a workflow would have
  changed the live site.
- `nirmaan learn PROJECT... [--json]`; `--decide ID --in PROJECT --as ROLE
  (--adopt | --reject) --reason TEXT`.

`tests/test_nirmaan_learning_proposals.py` (9), crown jewel
`test_a_new_proposal_rule_needs_no_core_changes`. The standard local run is
1424 passed, 3 skipped.

### Milestone 36 - Concurrent tasks and a project wide call budget in the unattended loop (after Stage 6)

Post-roadmap work that builds two items M29 deferred. Design doc: `docs/LOOP_CONCURRENCY.md`. No version bump.

Key design points worth not re-deriving:
- **One writer, turns in plan order.** In project mode the tasks with a seat
  step form a batch (all actionable, so their dependencies are terminal and
  none depends on another). A batch of more than one runs a thread per task
  under `nirmaan.runtime.writer`: a thread reads or writes state only while it
  holds the turn, and gives it up only around `outside_writer()` (which
  `ModelRuntime._ask` puts around `llm.complete`) and when its task stops. The
  turn passes to the next unfinished task cyclically and waits for it, so the
  segment order, and with it every counter ID and audit hash, is a function of
  the batch alone. `--jobs` is the number of call slots; a slot is taken while
  the turn is still held, so `--jobs 1` is strictly sequential in turn order.
  A shared ordered script (one MockLLM script for several tasks) is
  reproducible only at `--jobs 1`; prompt-driven answers at any `--jobs`.
- **Tools, file writes, and saves stay inside the turn.** Bindings get the
  engine and may read it (`status.read` does), and `_attempt_dir` picks a
  directory by an exists check, so neither may race. Parallel tool runs are
  deferred.
- **Runtimes are shallow copied per task** in a concurrent batch (`private`),
  so `ModelRuntime`'s per-call `_calls` and `_purpose` stay with one task.
  A runtime that never calls `outside_writer()` just runs its tasks in turn.
- **Errors:** a failing step raises in its own turn; the other tasks finish
  the step in hand (so a call already made is recorded), see `stopping()`,
  and the first error in batch order is raised. Ctrl-C does the same.
- **The budget lives on the audit trail.** `TaskEngine.set_budget` (person
  only, reason required) appends `budget.set` with the new and previous
  limits; `nirmaan.work.budget.budget(state)` reads the latest. Spend is the
  recorded `ModelCall`s (M31), from any command. Before a step its worst case
  must fit `calls` minus the spend minus what in-flight steps may still make;
  a cost limit stops new steps once reached, and a call of unknown cost stops
  it (never free). The stop is `Stop.PROJECT_BUDGET` with a `loop.stop` entry
  (`record_step` gained an `action` limited to `loop.*`).
- `nirmaan drive ... --jobs N`; `--dry-run` adds the concurrent batch and the
  budget impact (`plan.concurrent`, `plan.project_budget`, `plan.spent`);
  `nirmaan budget PROJECT [--calls N] [--cost-usd X] [--clear] --as ROLE
  --reason TEXT`, or no limits to show the budget and spend.

`tests/test_nirmaan_loop_concurrency.py` (14), crown jewel
`test_a_new_runtime_on_a_new_workflow_runs_concurrently_with_no_core_changes`.

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

v1.21.0 is the one version bump for the five M27 parts, built in parallel and
merged as #39 (repair after review), #38 (physical design for real), #42 (gates
everywhere), #43 (DFT), and #40 (RISC-V firmware). The standard local run is
1203 tests with 3 skipped: the real OpenROAD tests, which run in CI's
`physical-design` job. The owner's structural review (PR #37) also uses the
M27 label; it is not part of this release.

v1.22.0 is the one version bump for everything merged after v1.21.0: the
structural review and its seven milestones (#37 seat evaluation, an M27 part;
#41 M28 tool contracts; #48 engineering records, an M29 part; #52 M30 register
map; #53 M31 model selection and accounting; #54 M32 scalable state; #55 M33
learning proposals) and the parallel M29 parts (#46 the unattended loop, #47
verification plans, #49 RISC-V, #50 DFT, #51 the remaining RTL gates). The
standard local run is 1424 tests with 3 skipped: the real OpenROAD tests, which
run in CI's `physical-design` job. No live-model evaluation has run yet: this
machine has no Anthropic credentials (`nirmaan eval run --runtime anthropic`
once one is set).

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
  **IP Nirmaan** (repo `patel-om/ip-nirmaan`, distribution `ip-nirmaan`, v1.22.0).
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

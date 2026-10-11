# context.md before M43 (sections 1, 3, 4, and 5)

Kept verbatim from `context.md` at v1.23.0, when its milestone entries moved
to one file each in this folder (M43, `docs/STATUS_DOCS.md`). The v1.21.0 and
v1.22.0 paragraphs of section 3 became `release-v1.21.0.md` and
`release-v1.22.0.md`. Facts here may be stale: `context.md` holds the current ones.

---

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
Current version: **1.23.0** (distribution `ip-nirmaan`; packages `nirmaan` and `veritriage`)
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
  **IP Nirmaan** (repo `patel-om/ip-nirmaan`, distribution `ip-nirmaan`, v1.23.0).
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

# Nirmaan IP

**An AI-native semiconductor IP company, as software.** Nirmaan IP is an
organizational operating system for semiconductor engineering. Give it a
requirement ("Create a 4-port AXI-to-NoC bridge") and a machine-readable
company plans the work: divisions, teams, and roles from Intern to CEO, with
skills, authority, gates, and a 12-article constitution. Every task gets an
owner, an independent reviewer, an authorized approver, evidence requirements,
and an escalation path, and each routing decision records why it was made.

```
nirmaan plan "Create a 4-port AXI-to-NoC bridge." --detail
nirmaan demo all
nirmaan why <project> microarchitecture
```

The task engine keeps planned, executed, verified, and approved distinct, and
it makes a fake tool run or a self-approval impossible. Language models will
power workers who fill seats in the organization. They get no special access
and cannot mark their own work verified. Design:
[docs/NIRMAAN_ORG_OS.md](docs/NIRMAAN_ORG_OS.md).

## The platform

| Component | What it is | Entry point |
|---|---|---|
| **Nirmaan IP organizational OS** (`src/nirmaan/`) | The company as data, the task engine, the orchestrator, and the agent runtime interface | `nirmaan` |
| **VeriTriage** (`src/veritriage/`) | The verification-intelligence engine: evidence graphs, knowledge packs, reasoning, regression memory | `veritriage` |

Nirmaan IP is bigger than verification, and it builds on VeriTriage's
verification technology rather than replacing it:

* VeriTriage investigations are real, evidence-producing tools inside Nirmaan's task engine.
* VeriTriage's 42 Knowledge Packs are the domain knowledge that Nirmaan's skills cite.
* VeriTriage never depends on Nirmaan, so it stays usable as a standalone verification tool.

## VeriTriage: the verification engine

**Verification intelligence for semiconductor regression debug.** VeriTriage turns
raw verification artifacts (simulation logs, compile logs, coverage summaries,
test metadata) into a normalized **Evidence Graph**, a deterministic failure
classification with confidence and evidence, an engineering-grade HTML report,
and suggested next debugging steps - in one command. A **Verification
Knowledge Engine** ships 42 pluggable Knowledge Packs across six domains
(interconnect, CPU/ISA, memory, serial IO, coherency, and methodology):
AMBA AXI/APB/AHB/ACE/AXI-Stream, CHI, TileLink, NoC, PCIe, CXL, UCIe, DDR,
HBM, USB, Ethernet, MIPI, I2C/I3C, SPI, UART, JTAG, UVM methodology with
RAL/phasing/TLM, SVA, formal, low power, DFT, X-propagation, CDC, reset,
coherency, security, performance, and RISC-V depth (92 deterministic failure
patterns, 90 debug playbooks, 15 protocol state machines total) that match the
evidence against known failure patterns, project it onto protocol state
machines to show where progress stopped, and attach deterministic debug
playbooks with real specification references. An **Agent Framework** then puts
eight domain specialists over the deterministic result, merging their
evidence-backed positions into ranked findings with agreement and conflict made
explicit. Every analysis is also recorded into a persistent **Regression
Database**, so the platform tells you whether this failure has been seen
before, what resembled it, and what the historical root cause was. A
**Learning Engine** then turns that accumulated history into reusable
knowledge: recurring patterns, evidence combinations, per-specialist
reliability, and project memory, all derived deterministically and all linked
back to the investigations they were learned from. Finally a **Planning
Engine** turns all of it into a structured, branching investigation plan:
what to inspect next, what evidence would confirm or reject each hypothesis,
what it costs, and how you will know when you are done. A **Design
Intelligence Engine** underpins all of it with a structural understanding of
the system: a Design Graph of modules, interfaces, clock and reset domains,
address regions, and verification components, joined by typed relationships
and derived deterministically from the project model. A **Conversation
Engine** finally makes all of it navigable: grounded, structured questions
whose every statement cites an artifact that already exists. **Generative AI**
sits above all of it as a rendering layer only: providers turn structured
findings into prose, grounded by enforcement rather than by request, and never
touch a conclusion. An **Automation Engine** finally makes the platform react:
it publishes the events it already detects, evaluates declarative rules against
them, and requests follow-up work. It observes and decides; it never executes.

```
veritriage analyze simulation.log coverage.txt test_metadata.json
```

### Why VeriTriage

Today's debug flow after a regression failure is manual: open the log, grep for
errors, open the waveform, inspect signals, form a hypothesis. VeriTriage
automates the front half of that loop:

```
Regression failure
  -> Collect artifacts        (sim log, compile log, coverage, test metadata)
  -> Parse deterministically  (UVM / Questa / VCS / Xcelium / generic)
  -> Normalize                (Evidence Graph: typed nodes + typed edges)
  -> Correlate evidence       (temporal, causal, cross-artifact links)
  -> Classify                 (rule engine over the graph, confidence-ranked)
  -> Apply knowledge          (packs -> knowledge graph -> pattern match ->
                               state projection -> playbooks -> references)
  -> Reason                   (evidence selection -> signals incl. knowledge ->
                               competing hypotheses -> traceable confidence)
  -> Remember                 (regression database: signature, similarity,
                               "have we seen this before?")
  -> Coordinate agents        (eight domain specialists over the finished result
                               -> merged findings, agreement, conflict)
  -> Learn                    (recurring patterns, agent reliability, project
                               memory -> hints for the next investigation)
  -> Locate structurally      (Design Graph: which modules, domains, agents and
                               protocols the failure actually touches)
  -> React                    (publish events, evaluate rules, request follow-up
                               work: recurrence, disagreement, unexplained failure)
  -> Plan                     (derive a branching debug plan: ordered steps,
                               decision points, evidence still needed)
  -> Report                   (analysis.json + evidence_graph.json + report.html)
  -> Optional AI review       (reasons ONLY over selected evidence, cites node IDs)
```

**Design principles**

- AI assists engineers; it never replaces engineering judgment.
- The Evidence Graph is the single source of truth: every conclusion carries
  node IDs that trace to an artifact file and line.
- Deterministic parsing, graph building, and classification always run
  **before** any LLM; the AI layer never reads raw files.
- Modular plugin architecture: new parsers, rules, and correlation passes drop
  in without touching the rule engine or the AI layer.

See [docs/EVIDENCE_GRAPH.md](docs/EVIDENCE_GRAPH.md) for why this architecture
improves scalability, explainability, and deterministic reasoning,
[docs/REASONING_ENGINE.md](docs/REASONING_ENGINE.md) for the multi-stage
reasoning pipeline: how it generates multiple ranked, evidence-backed
hypotheses with traceable confidence, and how deterministic rules and AI
collaborate without the AI ever reading a raw file, and
[docs/REGRESSION_INTELLIGENCE.md](docs/REGRESSION_INTELLIGENCE.md) for the
regression database: deterministic failure signatures, similar-failure
search, clustering, analytics, and the engineering dashboard, and
[docs/KNOWLEDGE_ENGINE.md](docs/KNOWLEDGE_ENGINE.md) for the Verification
Knowledge Engine: why structured, versioned verification knowledge beats
prompt engineering, and how to add a protocol pack, and
[docs/AGENT_FRAMEWORK.md](docs/AGENT_FRAMEWORK.md) for the Agent Framework:
how specialized reasoning components form a second opinion over the
deterministic result, how the Coordinator merges and cross-examines them, and
how Deterministic and Generative Intelligence are kept cleanly separated so any
future AI provider is one class behind one protocol, and
[docs/LEARNING_ENGINE.md](docs/LEARNING_ENGINE.md) for the Learning Engine: why
learning is a pure function of recorded history, how it stays explainable
without embeddings or models, and how it calibrates without ever overriding
deterministic evidence, and
[docs/PLANNING_ENGINE.md](docs/PLANNING_ENGINE.md) for the Planning Engine: why
a plan is structurally different from a recommendation, how the Planner
contributes structure without ever writing debug advice, and how branching
stays deterministic without executing anything, and
[docs/DESIGN_INTELLIGENCE.md](docs/DESIGN_INTELLIGENCE.md) for Design
Intelligence: why the Design Graph is derived from the Project Model rather
than extracted from source, why it is a third graph beside Evidence and
Knowledge, and how structural questions become deterministic traversals, and
[docs/CONVERSATION_ENGINE.md](docs/CONVERSATION_ENGINE.md) for the Conversation
Engine: why conversation is navigation rather than reasoning, how a declared
vocabulary keeps it honest without a language model, and how an LLM later
becomes a renderer of conversation objects rather than an owner of them, and
[docs/AI_PROVIDERS.md](docs/AI_PROVIDERS.md) for generative AI: why providers
render rather than reason, how grounding is enforced instead of requested, and
why one vendor registry serves both agent narration and every renderer, and
[docs/AUTOMATION_ENGINE.md](docs/AUTOMATION_ENGINE.md) for the Automation
Engine: why automation decides rather than executes, why events are immutable,
and how CI, schedulers, and chat clients plug in as event producers.

## Installation

Requires Python 3.11+.

```bash
pip install -e .            # core (deterministic pipeline)
pip install -e ".[ai]"      # + optional AI summary (Anthropic SDK)
pip install -e ".[dev]"     # + test tooling
```

## Usage

```bash
# Analyze one artifact
veritriage analyze simulation.log

# Analyze a whole run: log + coverage + test metadata, correlated in one graph
veritriage analyze simulation.log compile.log coverage.txt test_metadata.json -o out/

# Add waveform metadata: a VCD, or a simulator-independent JSON manifest.
# VeriTriage reads metadata (signal activity, dump window), never transitions,
# and turns it into engineering observations linked to the failure.
veritriage analyze simulation.log dump.vcd -o out/
veritriage analyze simulation.log run.wave.json -o out/

# Engineering context: "what changed?" before "what broke?". Gathered by
# default from the working tree (recent commits via git, or a *.engctx.json
# manifest any CI can export); correlated changes become evidence.
veritriage analyze simulation.log -o out/                  # context on by default
veritriage analyze simulation.log --no-context -o out/     # opt out
veritriage investigate simulation.log                      # context + timeline + investigation view (saves a session)
veritriage impact                                          # tests likely hit by current changes (from history)
veritriage context                                         # what the providers see here

# Verification Project Intelligence: understand the project BEFORE the failure.
# A cached, content-addressed Project Model (DUT hierarchy, interfaces and
# identified protocols, UVM topology, expected simulation lifecycle, log profile)
# built from a *.vproj.json manifest. It never enters the Evidence Graph; it is a
# lens over it, reaching reasoning as ordinary evidence-cited signals.
veritriage project .                                       # build + print the project model
veritriage explain simulation.log                          # classify each line by origin + lifecycle phase
veritriage analyze simulation.log --project -o out/        # project-aware analysis (default on)
veritriage analyze simulation.log --no-project -o out/     # opt out

# Agent Framework: eight domain specialists (protocol, RTL, testbench, coverage,
# regression, formal, project, knowledge) form independent, evidence-backed
# positions over the deterministic result; the Coordinator merges them, detects
# agreement and conflict, and cross-checks against the reasoning engine. A second
# opinion, never a replacement verdict.
veritriage agents                                          # registered specialists + providers
veritriage analyze simulation.log -o out/                  # agents on by default
veritriage analyze simulation.log --no-agents -o out/      # opt out

# Learning Engine: every completed investigation improves the next one. Derived
# deterministically from the regression database (no LLM, no embeddings, no
# vector DB, no hidden state), stored separately, and rebuildable at any time.
# Learning produces hints and bounded agent calibration; it never decides.
veritriage learn                                           # recompute from recorded history
veritriage analyze simulation.log -o out/                  # recall on by default
veritriage analyze simulation.log --no-learn -o out/       # opt out
veritriage feedback reg-... --diagnosis correct            # feedback is what calibration learns from

# Planning Engine: what should I inspect next? Derives a branching investigation
# plan from the conclusions: steps ordered by value against effort, decision
# points, the evidence still missing and why it matters, and how you know you
# are finished. Every step names the artifact it restates; planning never
# invents advice and never executes anything.
veritriage plan simulation.log                             # print the investigation plan
veritriage analyze simulation.log -o out/                  # planning on by default
veritriage analyze simulation.log --no-plan -o out/        # opt out

# Design Intelligence: understand the system, not just the run. A Design Graph
# derived from the project model (never from source: only a ProjectProvider
# reads source) that answers structural questions deterministically. Which
# agent owns this interface? What crosses this clock boundary? What depends on
# this configuration?
veritriage design .                                        # the structural graph
veritriage design . --module l2_cache                      # one element and its relationships

# Conversation: ask grounded questions about an investigation. Not a chatbot and
# not an LLM wrapper: questions are matched against a declared vocabulary (never
# guessed at), answers are assembled from artifacts that already exist, and every
# statement cites evidence, knowledge, design, agent, learning, or plan IDs.
veritriage ask simulation.log -q "why is this a testbench issue?"
veritriage ask simulation.log -q "why not rtl_bug" -q "show only error" -q "trace"

# Generative AI: providers render, never reason. An LLM receives a frozen prompt
# built from cited platform objects, never a raw log, waveform, or RTL file.
# Citations outside the prompt's declared set are stripped from the output.
# Generation is off by default; no built-in provider calls an external API.
veritriage providers                                       # registered providers + capabilities
veritriage render simulation.log -r executive-summary      # grounded prose
veritriage render simulation.log --show-prompt             # audit the prompt without generating

# Automation: the platform reacts. Events it already detects (a signature
# recurring, specialists disagreeing, a failure the rules cannot explain) are
# published onto an ordered, replayable bus; declarative rules evaluate them and
# request follow-up work from a closed action vocabulary. Automation decides;
# the workspace executes. No simulations, no CI, no webhooks, no OS jobs.
veritriage automation                                      # rules, triggers, action vocabulary
veritriage automation simulation.log                       # what the platform reacted to

# Workspace and MCP: VeriTriage as an external investigation service.
# `veritriage mcp` serves 72 investigation tools over stdio, so Claude Code,
# Cursor, or any MCP host can analyze regressions, walk evidence, search the
# knowledge base, and query history: the CLI and MCP share the same services.
veritriage mcp                                             # MCP tool server (stdio)
veritriage sessions                                        # list persisted investigation sessions

# Orchestrated investigation workflows (M9): named profiles that compose the
# existing services into a complete investigation, producing an immutable
# plan, a deterministic execution trace with per-subsystem attribution and
# per-step timings, and a persisted session carrying both.
veritriage profiles                                        # list investigation profiles
veritriage run fast-triage simulation.log                  # thirty-second triage
veritriage run full-investigation simulation.log dump.vcd -o out/   # everything on

# Collaboration (M10): investigations as portable, reviewable artifacts.
# Export a session to a self-contained bundle (only normalized objects, no raw
# waveform or log files), hand it to another engineer, and review/annotate/
# validate/compare/continue it on any machine.
veritriage bundle export <session-id> -o inv.vtb
veritriage bundle import inv.vtb                           # loads the session, continue anywhere
veritriage bundle validate inv.vtb                         # integrity + referential checks
veritriage bundle compare a.vtb b.vtb                      # explains what changed
veritriage review inv.vtb --verdict approved --reviewer asha --comment "ship it"
veritriage annotate inv.vtb --target evidence:ev-abc123 --author diego --text "check this"

# Add an AI summary grounded in the evidence graph
veritriage analyze simulation.log -o out/ --ai

# Regression intelligence (database defaults to .veritriage/regressions.db)
veritriage history                     # recent regressions in the database
veritriage dashboard -o out/           # engineering analytics dashboard
veritriage feedback reg-... --diagnosis correct --root-cause "..."
veritriage analyze simulation.log --no-history   # opt out of recording

# Introspection
veritriage parsers
veritriage knowledge      # loaded Knowledge Packs
veritriage waveform       # registered waveform adapters and their capabilities
veritriage version
```

Each run writes three artifacts to the output directory:

| File | Contents |
|---|---|
| `analysis.json` | Classification, confidence, evidence (with graph node IDs), reasoning, agent findings, learned hints, the affected design region, the investigation plan, historical context, run summary, graph stats |
| `evidence_graph.json` | The full serialized Evidence Graph: every node and relationship |
| `report.html` | Self-contained EDA-style dashboard (light/dark), hypotheses, agent findings, what prior investigations suggest, the recommended investigation with its decision tree, historical context, evidence timeline, next steps |

Each analysis is also stored in the regression database (opt out with
`--no-history`), which powers `veritriage history`, `veritriage dashboard`,
and the "seen before" context in every report.

Exit codes: `0` clean run, `1` failure classified (useful for CI gating),
`2` usage error.

The AI summary uses the Anthropic API (`ANTHROPIC_API_KEY` or an `ant auth login`
profile) and receives only the graph's normalized reasoning view - never raw
artifact text.

### Library use

```python
from pathlib import Path
from veritriage.pipeline import analyze

outcome = analyze([Path("simulation.log"), Path("coverage.txt")])
print(outcome.report.classification.category, outcome.report.classification.confidence)
print(outcome.graph.stats().node_count, "evidence nodes")
```

## What the rule engine classifies

| Category | Typical signature | Confidence |
|---|---|---|
| Compile failure | dedicated compile-log evidence, syntax errors, undeclared identifiers | 90 |
| Assertion failure | SVA/checker assertion fired (first-class `assertion` nodes) | 90 |
| Timeout | phase/watchdog timeout, hung test | 85 |
| Testbench failure | scoreboard mismatch, compare errors | 80 |
| Fatal error | fatal message without a more specific diagnosis | 70 |
| Unknown failure | errors present, no signature matched | 30 |
| No failure | clean artifacts | 95 |

All rule verdicts (not just the winner) appear in the report as alternatives,
and every evidence item cites its graph node.

## Artifact types in the graph

Simulation logs, assertions, coverage, test metadata, compile logs, and
`waveform_metadata` are all live today. Waveform artifacts arrive through the
Waveform Intelligence Engine: a `WaveformAdapter` per format (VCD and a
simulator-independent JSON manifest ship today) normalizes signal-activity
metadata, and a format-agnostic observation engine turns it into engineering
observations (dead clock, stalled FSM, incomplete handshake, unretired
transaction) that enter the graph as evidence and correlate to failures. See
[WAVEFORM_ENGINE.md](docs/WAVEFORM_ENGINE.md). Adding an artifact type is a
parser plus an optional correlation pass; the rule engine and AI layer are
untouched by design
([checklist](docs/EVIDENCE_GRAPH.md#adding-a-new-artifact-type-checklist)).

## Roadmap (documented, not built)

As of v1.0.0 the core is stable and its public API (WorkspaceServices, the MCP
tool table, the orchestrator step/profile registries, the `.vtb` bundle format,
since v1.8.0 the `Agent` / `ReasoningProvider` contracts, since v1.9.0 the
`Learner` / `LearningArtifact` contracts, since v1.10.0 the `StepSource` /
`DebugPlan` contracts, since v1.11.0 the `StructureExtractor` / `DesignGraph`
contracts, since v1.12.0 the `Question` / `Answer` / `QuestionHandler`
contracts, since v1.13.0 the `LLMProvider` / `Prompt` contracts, and since v1.14.0 the
`Event` / `Trigger` / `AutomationRule` contracts) is frozen; future
work is integrations over existing seams: AI providers (Claude, GPT, Gemini,
local models, MCP-hosted reasoners) as `ReasoningProvider` implementations
behind the M12 seam -> a VS Code
extension and other IDE clients as thin consumers of `WorkspaceServices`, the
MCP server, orchestration profiles, and portable bundles -> more waveform
adapters (FSDB, FST, WLF, transaction DBs) behind the existing
`WaveformAdapter` interface -> more context providers (GitHub, GitLab,
Perforce, Gerrit, Jenkins, Jira, DOORS) behind the existing `ContextProvider`
interface -> more investigation profiles and steps behind the existing
`register_step` / `register_profile` seams -> learned similarity embeddings
behind the existing `EmbeddingProvider` interface -> Slack integration,
GitHub Action.

## License

Apache-2.0

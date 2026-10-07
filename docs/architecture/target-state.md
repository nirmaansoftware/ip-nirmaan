# Target state

Where IP Nirmaan's architecture goes next, measured against the structural
brief of 2026-09-29 ("build the engineering engine, not an AI wrapper").
Read `current-state.md` first; this file is the gap analysis and the
destination, and `proposed-change.md` is the first step toward it.

## 1. The finding in one paragraph

The brief describes, almost concept for concept, what M19 to M26 already
built: a task model with a real lifecycle, plans that are inspectable data,
artifacts with provenance and digests, immutable evidence that only a real
tool run can substantiate, a tool broker with permissions and honest refusal,
roles separate from skills, human gates, an audit trail, persistent project
state, events, and requirement-to-evidence traceability. The engine the brief
asks for is `nirmaan/work/` plus `nirmaan/runtime/`, and it is already the
product: the model sits in a seat and proposes, the engine decides. So the
target is **not** a new `nirmaan/engine/` package or a rewrite. It is a
short list of missing primitives, each added the way every milestone has
been: as data and registries, with a crown-jewel test. The largest gap is the
one the brief calls the ultimate evaluator: nothing yet measures whether a
real model's work in a seat actually works.

## 2. Principles (unchanged, and why they already fit)

The brief's principles restate the constitution and the rules in `CLAUDE.md`.
The mapping, so no one writes a second set:

| Brief | Where it already holds |
|---|---|
| The model is not the system | `run_task` applies a runtime's proposal through `TaskEngine`; P3, P4, P5 refuse unbacked results. |
| Separate intelligence from execution | Seats reason; `ToolBroker` executes; pre-flight and post-flight tools run around the model, not at its discretion. |
| Never fake work | P5 (no fabricated tool runs), `CONTRACT_ONLY`, probes that refuse; CLAIM evidence satisfies nothing. |
| Raw data vs normalized evidence | VeriTriage's parser -> Evidence Graph -> reasoning view; seats get log *excerpts* (M26) and evidence tokens, not raw logs. |
| Human in the loop | Gates with `human_required`, P12, authority matrix, escalation routes. |
| Do not overengineer | Every extension point is a registry with a zero-core-change test. |

## 3. Concept-by-concept gap analysis

Status: **Exists** (meets the brief), **Partial** (the core is there; named
fields or behaviour are missing), **Missing**.

| # | Brief concept | Status | Where it lives | Gap |
|---|---|---|---|---|
| 4 | Engine owning task, plan, execution, state, evidence, policy | Exists | `work/engine.py`, `work/policy.py`, `runtime/base.py` | Evaluation and learning are not engine concerns yet (see 16, 19). |
| 5 | Task model and lifecycle | Exists | `models/work.py` `Task`, `TaskStatus` (11 states), `_TRANSITIONS` | None. The brief's CREATED/WAITING map to PLANNED/BLOCKED; review, approval, and escalation states are richer than the brief's. |
| 6 | Plan before execution, inspectable | Exists | `orchestrator/planner.py`; `nirmaan plan`, `why`, dashboard | None structural. |
| 7 | Structured knowledge; FACT / INFERENCE / HYPOTHESIS / ASSUMPTION / UNKNOWN | Partial | VeriTriage Knowledge Packs (42), skills' procedures and failure modes, `Assumption` records, CLAIM vs substantiated evidence, VeriTriage hypotheses with confidence traces | The five epistemic states exist as separate mechanisms (substantiated evidence = fact; hypothesis with confidence trace = inference or hypothesis; `Assumption` = assumption; escalation question or "unrecognized" = unknown), not one tag. Design knowledge (as opposed to debug knowledge) is prose inside skills. |
| 8 | Evidence model, immutable | Exists | `Evidence`, `ToolRun` (frozen, append-only) | No `structured_data` on a run (parsed metrics live only in `<backend>.result.json`); no severity. Small. |
| 9 | Raw data vs normalized evidence | Exists | VeriTriage pipeline; `files.excerpt` | None. |
| 10 | Artifact graph | Partial | `Artifact` (kind, task, producer, assurance, location, digest, `derived_from`) | No explicit version or supersession; assurance updated in place (history only in the audit trail). |
| 11 | Requirement traceability | Exists | `engineering.unbacked_requirements`, `nirmaan gaps`, export `09_evidence` | Requirements and verification items are recorded by hand or API; no verification-plan seat (roadmap "Not yet"). |
| 12 | Agents as roles, not prompts | Exists | `Role` (unit, level, authority), derived agent cards, `AgentProfile` | None. |
| 13 | Skills as reusable capabilities | Exists | `Skill` (procedures, tools, constraints, failure modes, validation criteria), `Capability` | None. |
| 14 | Tools with contracts | Partial | `ToolSpec` (risk, status), bindings, probes, `Backend` (required params, timeout) | No parameter or output schema on the tool; list parameters comma-joined strings; side effects and timeout not declared on the tool. |
| 15 | Model abstraction, capability-based choice | Partial | M17 provider registry, `ProviderCapabilities`, `LLM` protocol, runtime registry | Seats are bound by runtime name; nothing selects a provider by declared capability; no cost or latency profile. |
| 16 | Reasoning is evaluated | **Missing** | Only mechanism tests on `MockLLM` | No measurement of a live seat's output by deterministic checks. |
| 17 | Evaluation harness (`evals/`) | **Missing** | Fixtures that would serve it: 4 blocks, wrong testbenches, proofs, mutants | Everything. |
| 18 | Failure is data | Partial | `Attempt` (refusal, failed runs, files), task `blocked_reason`, escalations | No failure category, no cross-project counts. |
| 19 | Learning loop with provenance | Partial (VeriTriage only) | VeriTriage `learning/` (regression history, calibration) | Nothing for Nirmaan seats; must never auto-edit knowledge. Depends on 16 and 18. |
| 20 | Memory with semantics | Exists | `MemoryScope` (company, project, team, task, agent) with provenance; knowledge is separate (packs, skills) | No embedding store, by design. |
| 21 | Decision records | Partial | `Decision` (kind, criticality, statement, rationale, evidence, author), P2 | No context, alternatives, consequences, or subject (requirement or artifact). |
| 22 | Autonomy boundaries | Exists | review requirements, gates, `human_required`, P12, authority by criticality, escalation | The four levels are implicit in those mechanisms rather than one declared per-action policy; adequate for now. |
| 23 | Permissions | Exists | tool grants flow from skills; `ToolRisk`; authority matrix | None structural. |
| 24 | Explicit, persistent project state | Exists | `ProjectState`, `ProjectStore`, hash-chained audit | Whole-state fingerprint per operation will not scale (current-state 5.4). |
| 25 | Domain events | Exists | `events.py` projects audit entries to `OrgEvent`s on the M18 bus | More topics are one row each. |
| 31 | Compiler-style IRs | Partial | Requirement IR = `RequirementAnalysis`; post-RTL Design Graph (M15/M24) | No pre-RTL structured design IR (e.g. a register map as data). |

## 4. Target architecture

The layering stays. Additions are marked **new**.

```
Requirement
   |  orchestrator/analyze          (Requirement IR: intent, features, params, assumptions)
   v
Plan  orchestrator/planner          (task graph from workflow data; inspectable)
   |
   v
TaskEngine  work/                   (lifecycle, authority, constitution, audit)
   |    ^
   |    | proposals only
   v    |
Seats  runtime/                     (packet -> prompt -> model -> grounded proposal)
   |        model selection by declared capability            (new, M31)
   |        typed WorkPacket                                   (new, M28)
   v
ToolBroker  runtime/tools + integrations/
   |        typed tool contracts: params, outputs, side effects, timeout (new, M28)
   v
ToolRun -> Evidence -> Assurance    (append-only; artifacts superseded, not edited: new, M29)
   |
   +--> engineering graph, gaps, export (views)
   |
   +--> Evaluation  evals/ + nirmaan/evals/                    (new, M27)
   |        a seat on a real or replayed model, scored by the same tools,
   |        plus held-out checks the seat never saw; results as records
   |
   +--> Failure records (classified) -> learning proposals     (new, M29, M33)
            proposals reach knowledge only through a reviewed task
```

### What deliberately does not change

- No `nirmaan/engine/` package: `work/` and `runtime/` are the engine.
- No second set of per-concept architecture documents. The brief lists
  `principles.md`, `engine.md`, `agents.md`, `skills.md`, `tools.md`,
  `evidence.md`, `artifacts.md`, `memory.md`, `evaluation.md`,
  `security.md`, and `autonomy.md`. Those subjects are already documented;
  a duplicate would drift. The index below points to each.
- VeriTriage stays standalone; the import laws stay.
- No vector store, message queue, service split, or new runtime dependency.

### Document index for the brief's topics

| Topic | Document |
|---|---|
| Principles | `CLAUDE.md`, the constitution in `company/governance.py`, section 2 above |
| Engine | `docs/NIRMAAN_ORG_OS.md` (task engine, policy, audit) |
| Agents, skills | `docs/NIRMAAN_ORG_OS.md`, `docs/AI_WORKERS.md`, `docs/DESIGN_AGENTS.md` |
| Tools | `docs/EDA_TOOLS.md`, `docs/PHYSICAL_DESIGN.md`, `docs/FIRMWARE.md`, `docs/DFT.md` |
| Evidence | `docs/EVIDENCE_GRAPH.md` (VeriTriage), `docs/NIRMAAN_ORG_OS.md` (records) |
| Artifacts, traceability | `docs/DELIVERABLE_EXPORT.md`, `docs/ENGINEERING_GRAPH.md` |
| Memory, knowledge | `docs/KNOWLEDGE_ENGINE.md`, `docs/NIRMAAN_ORG_OS.md` (work packet scopes) |
| Evaluation | `docs/SEAT_EVALUATION.md` (new with M27) |
| Security, autonomy | `docs/NIRMAAN_ORG_OS.md` (authority, gates, P12), `docs/NIRMAAN_MCP.md` (MCP caller is always an AI actor) |
| Repair and failure | `docs/REPAIR_LOOP.md`, `docs/FORMAL_GATE.md` |

## 5. Milestones toward the target

Each ships complete (design doc, code, crown-jewel test, `context.md`
entry, PR) and leaves the suite green. Numbering continues from M26.

| Milestone | What | Why in this order |
|---|---|---|
| **M27 Seat evaluation** | `evals/` cases as data; a runner that puts any registered runtime in a seat on a fixed upstream, scores the result with deterministic checks (the seat's own gates, plus held-out checks such as the reference testbench and mutants), and records results with model, attempts, and timing. Replay mode for CI; live mode opt-in. | Every later change to seats (typed packets, model choice, prompts, repair limits, new seats) needs a yardstick. It is additive and cannot break a working flow. |
| M28 Typed contracts | `ToolSpec` gains a parameter schema (typed, list values as lists), output metrics, side effects, and timeout; the broker validates before invoking. `WorkPacket` becomes typed models instead of dicts. | Prerequisite for model-chosen tool calls and for MCP clients discovering tool inputs; removes the comma-joined parsing in four places. Measured against M27 before and after. |
| M29 Engineering records | `Decision` gains context, alternatives, consequences, and subject; artifacts gain `supersedes`; failures (refused attempts, failed tasks) gain a registered category. | Makes long-running work explainable and failures countable. Small, data-only changes behind the engine. |
| M30 First design IR | A register map as structured data, produced by a seat, checked deterministically against the RTL (addresses, widths, access, reset values) and lowered to a C header and a register table. | The brief's compiler principle where it pays first: the four shipped blocks are register-mapped or register-like, and firmware already needs the header. |
| M31 Model selection | Seats declare required capabilities; providers declare capabilities, cost, and context; selection is a scored join (like routing). Token and cost accounting per call. | Needs M27's results to choose on evidence rather than preference. |
| M32 Scalable state | P10 checked against the audit head plus an incremental fingerprint instead of re-hashing the whole state per operation; store split so runs and evidence append. | Before projects grow past the fixtures. |
| M33 Learning proposals | Classified failures and eval results produce *proposed* skill or knowledge changes as tasks for a human-reviewed seat; nothing edits knowledge directly. | Depends on M27 and M29. |

Existing roadmap items (real OpenSTA/OpenROAD runs, a verification-plan seat,
repair after review, gating on the `new-ip` flows) continue alongside; they
are feature work on the same engine and are unaffected by this sequence.

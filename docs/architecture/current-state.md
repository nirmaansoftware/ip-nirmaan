# Current state (v1.20.0, 2026-09-29)

An inventory of what IP Nirmaan is today, written for the structural review
(`REVIEW_PLAN.md`). It describes the code as it stands on `main` at v1.20.0,
read module by module. History and rationale are in `docs/history/` (since M43); this file
is the map.

## 1. One-paragraph summary

IP Nirmaan is two packages in one distribution. **VeriTriage**
(`src/veritriage/`, M1 to M18) is a deterministic verification-intelligence
engine: parsers turn logs, waveforms, and manifests into an Evidence Graph,
and rules, knowledge packs, and reasoning explain failures over it.
**Nirmaan** (`src/nirmaan/`, M19 to M26) is an organizational operating
system on top of it. A requirement is analyzed against declared vocabulary,
planned into an owned, reviewed, gated task graph, and worked through a task
engine that enforces a lifecycle, an authority matrix, and a 12-article
constitution, with every change hash-chained into an audit trail. Workers
(human, scripted, or language-model seats) act only through that engine, and
tools act only through a broker that records real runs. Open-source EDA
(Verilator, Icarus, Yosys, SymbiYosys, OpenSTA and OpenROAD bindings, a C
toolchain) makes lint, simulation, synthesis, formal, DFT, and firmware checks
real. Four IP blocks (AXI4-Lite and APB register blocks, a FIFO, a
round-robin arbiter) are designed end to end by model seats in tests, gated
by those tools before review.

## 2. Components

### 2.1 Nirmaan (`src/nirmaan/`, about 13,300 lines)

| Layer | Modules | What it owns |
|---|---|---|
| Vocabulary | `models/` (`org`, `governance`, `workflow`, `work`, `deliverable`) | Frozen pydantic types only; imports nothing but pydantic (test-enforced). `Task`, `Artifact`, `Evidence`, `ToolRun`, `Attempt`, `Decision`, `Escalation`, `MemoryEntry`, `AuditEntry`, `SpecRequirement`, `VerificationItem`, `ProjectState`. |
| The company as data | `company/` | 207 units, 140 skills, 98 capabilities, 43 tools with `AVAILABLE`/`CONTRACT_ONLY` status, authority matrix, escalation routes, 6 gates, the constitution, 9 workflows, requirement vocabulary (intents, features, parameters, assumptions), deliverable folders, traceability kinds. |
| Organization | `org/` | Derives 685 roles from unit kinds; validation; `AuthorityService` (decision x criticality x level x scope); escalation routing. |
| Orchestrator | `orchestrator/` (`analyze`, `router`, `planner`) | Requirement to `RequirementAnalysis` (intent, features, parameters, explicit assumptions, or an honest "unrecognized"); workflow instantiation; scored routing of owners and reviewers. Names no domain (test-enforced). |
| Work engine | `work/` (`engine`, `policy`, `audit`, `store`, `blockers`, `management`, `trace`) | `TaskEngine`: the only way state changes. State machine, authority, constitution checks (`@register_check`), one audit entry per commit, assurance ladder PLANNED < EXECUTED < VERIFIED < APPROVED. JSON persistence per project. |
| Runtime | `runtime/` (`base`, `model`, `context`, `prompt`, `files`, `tools`) | `AgentRuntime` protocol and registry; `run_task` / `review_task`; bounded repair loop; `ModelRuntime` (one class for every seat); `WorkPacket` (four knowledge scopes); prompt rendering with citation tokens; file blocks in answers; `ToolBroker` with bindings and probes. |
| Integrations | `integrations/` (`veritriage`, `eda`, `eda_parsers`, `physical`, `pd_parsers`, `firmware`, `dft`, `dft_scan`) | The only VeriTriage import site (`veritriage.py`), plus EDA backends registered through `register_backend`. Parsers are pure functions. |
| Views and I/O | `engineering.py`, `export.py`, `events.py`, `views.py`, `dashboard.py`, `cli.py`, `mcp/`, `demos.py` | Requirement-to-evidence graph (M24), deliverable export (M23), audit-projected events (M22), CLI, a separate MCP tool table, demos. |

### 2.2 VeriTriage (`src/veritriage/`)

A one-directional pipeline (parse, graph, classify, knowledge, reason) with
lenses beside it (waveform, engineering context, project model, design graph)
and platform layers above it (workspace services, MCP, investigation
orchestrator, collaboration, agents, learning, planning, conversation, AI
providers, automation bus). Every layer is a registry; AST tests enforce the
import direction. `docs/history/context-before-M43.md` section 3 is its full map. Nirmaan uses five of
its surfaces: `WorkspaceServices` (investigations), the Knowledge Pack
registry, the M17 LLM provider registry and grounding, the M18 automation
registries, and the M15 design-graph provider (for M24 links).

## 3. Execution paths

1. **Plan.** `nirmaan plan "<requirement>"` -> `analyze` -> workflows by
   intent -> stages by feature conditions -> `Router` picks owners and
   reviewers -> gates and approvers from the authority matrix -> a
   `ProjectState` whose tasks are PLANNED or READY, audited as
   `project.create`.
2. **Work a task.** `nirmaan run PROJECT TASK --runtime R` -> `run_task`
   -> `assemble` a `WorkPacket` -> `engine.start` (P8 refuses unapproved
   upstream inputs) -> runtime `execute`: pre-flight tools named by evidence
   requirements, prompt, model answer, grounding (undeclared citations
   stripped), files written with a digest, post-flight tools over those
   files -> `_apply`: tool runs become evidence, claims become CLAIM
   evidence, then `engine.submit`. A before-review check that failed refuses
   the submission (P9); with `max_attempts > 1` the refusal is recorded as an
   `Attempt` and the seat is asked again with the failed runs.
3. **Review and approve.** `review_task` (P6 independence before any model
   call), `engine.review`, `engine.approve` (P7 conflicts, P9 evidence),
   `engine.approve_gate` (P12 refuses a non-human on a human gate).
4. **Evidence to assurance.** `record_evidence` marks evidence substantiated
   only for a successful brokered run, a human attestation by a human, a
   recorded review, or a real artifact reference. When every requirement is
   met, artifacts are promoted to VERIFIED automatically.
5. **Read views.** `nirmaan status`, `why`, `gaps` (unbacked requirements),
   `links` (artifact to Design Graph node), `export` (numbered deliverable
   tree), dashboard, MCP tools. All are pure reads over `ProjectState`.

## 4. Strengths worth protecting

- **Honesty is enforced by the engine, not by prompts.** A tool run can only
  come from the broker; `CONTRACT_ONLY` tools and missing executables are
  refusals, never simulated runs; a claim is recorded but satisfies nothing;
  an agent cannot review its own work; a human gate refuses AI actors. These
  are constitution checks with tests.
- **The model is already not the system.** Seats get a packet and return a
  proposal; the engine decides. Tools that must run before review run
  deterministically around the model, not at its discretion.
- **Data over code, with crown-jewel tests.** Workflows, skills, tools,
  gates, folders, link kinds, runtimes, checks, and backends are registries or
  tables; each milestone proves an extension needs zero core changes.
- **Traceability exists end to end**: requirement -> task -> artifact
  (digest, `derived_from`) -> evidence -> tool run -> log, and requirement ->
  verification item -> passing run (M24).
- **Real tools, real fixtures.** Four blocks with self-checking testbenches,
  deliberately wrong testbenches, formal proofs, and a mutation check.

## 5. Weaknesses and technical debt

Ordered by how much they limit the next stages.

1. **No measurement of seat quality.** Every model-seat test runs on
   `MockLLM` answers scripted from the fixtures, so the suite proves the
   *mechanism* (gating, grounding, repair) but says nothing about how well
   any real model does the work. There is no harness that runs a seat on a
   live model and scores the result with the same deterministic tools, no
   record of cost or latency per call, and no held-out check the seat did not
   write itself (its RTL is judged by its own testbench). Model choice,
   prompt changes, and `max_attempts` are therefore unmeasured decisions.
2. **Tool contracts are informal.** `ToolSpec` has id, category, risk, and
   status, but no parameter schema, output schema, side effects, or timeout.
   Parameters are `dict[str, str]` with lists comma-joined (`sources=a.v,b.v`)
   and split again in the runtime, the policy check `evidence-before-review`,
   and the parsers; a path containing a comma breaks that silently.
   Required parameters live on each EDA `Backend`, not on the tool.
3. **The work packet is untyped.** `WorkPacket` fields are `dict[str, Any]`
   built from `model_dump`, and `ModelRuntime` reads keys such as
   `req["files"]` and `a["trusted"]`. A renamed model field breaks seats at
   run time, not at import.
4. **Whole-state fingerprinting on every operation.** `TaskEngine._check` and
   `_commit` each serialize and hash the entire `ProjectState` (for P10). Cost
   grows with the project, and every operation pays it at least twice. Fine
   at 55 tasks; a real project with thousands of runs and evidence records
   will feel it. `ProjectStore` also rewrites one JSON file per project.
5. **Artifact versions are implicit.** Resubmitting a task adds new artifact
   IDs (`task#a3`) but nothing says `a3` supersedes `a1`; readers infer the
   latest by order. Assurance is updated in place (`model_copy`), so an
   artifact's promotion history lives only in the audit trail.
6. **Decision records are thin.** `Decision` has statement, rationale, and
   evidence, but no context, alternatives considered, or consequences, and no
   link to the requirement or artifact it constrains.
7. **Failures are recorded but not classified.** A refused `Attempt` keeps
   the refusal text and failed runs; a FAILED task keeps a reason. There is no
   failure category (tool, spec ambiguity, model format, grounding, timeout),
   so failures cannot be counted or learned from across projects.
8. **Design intent is prose.** Interface specs and microarchitectures are
   Markdown artifacts. The only structured design representation is the
   Design Graph derived from RTL *after* it exists. A register map, for
   example, cannot be checked against the RTL or used to generate a C header;
   the M23 crown-jewel test shows such a seat is possible, but none ships.
9. **Model selection is by name.** `--runtime anthropic` picks one provider
   with a hard-coded model; there is no "this seat needs long context and
   structured output" request resolved against declared provider
   capabilities (VeriTriage's `ProviderCapabilities` exists but nothing
   selects on it).
10. **Process-global registries.** About a dozen module-level dicts
    (`_CHECKS`, `_BINDINGS`, `_RUNTIMES`, backends, folders, link kinds). They
    make extension easy and are well tested, but two organizations or two
    configurations cannot coexist in one process, and tests depend on
    `unregister_*` cleanup.

## 6. Duplicated functionality (mostly deliberate)

The M19 placement decision kept VeriTriage standalone, so several concepts
exist twice, each documented as intentional:

| Concept | VeriTriage | Nirmaan | Why both |
|---|---|---|---|
| Orchestration | `orchestrator/` (investigation steps, Kahn order) | `orchestrator/` + `work/` (org task graph) | VeriTriage's is verification-specific; reusing it would couple the engines. |
| Planning | `planning/` (debug plans) | `orchestrator/planner.py` (project plans) | Different objects; vocabulary kept distinct on purpose. |
| Agents | `agents/` (M12 specialists over evidence) | `runtime/` (seats doing org work) | M12 agents reason over a finished report; seats do owned work. |
| MCP server | `veritriage/mcp/` | `nirmaan/mcp/` (~80-line JSON-RPC copy) | VeriTriage's server is bound to its table and services. |
| Evidence | Evidence Graph nodes | `Evidence` records citing `ToolRun`s | Graph evidence explains a failure; Nirmaan evidence backs a claim. A VERITRIAGE_SESSION record links the two. |

The one duplication that is *not* deliberate is small: comma-joined list
parameters are split in at least four places (item 2 above).

## 7. Missing abstractions (against the structural brief)

Present under other names: task, plan, artifact, evidence, tool permissions,
roles vs skills, human gates, audit, project state, events, memory scopes,
explicit assumptions, requirement traceability. Missing or partial: an
evaluation harness, typed tool contracts, a typed work packet, artifact
supersession, full decision records, failure classification, structured
design intermediate representations, capability-based model selection, and a
Nirmaan-side learning loop. `target-state.md` maps each concept of the brief
to what exists and what is proposed.

## 8. Build, test, CI

- Python 3.11/3.12, pydantic, typer, rich, jinja2; `anthropic` optional.
- Standard run at v1.20.0: 1115 tests, 2 skipped (OpenSTA, OpenROAD). EDA
  tests skip when a tool is absent unless named in `NIRMAAN_REQUIRE_EDA`.
- CI (`.github/workflows/ci.yml`): the suite on 3.11 and 3.12 with apt EDA
  tools and OSS CAD Suite `sby`; a dash check (`scripts/check_dashes.py`).
- Local hazard: the repo lives in iCloud-synced `~/Documents`. Evicted files
  (including `.git` objects) time out on read, and the venv must be rebuilt
  after any folder rename (it was stale at the start of this review).

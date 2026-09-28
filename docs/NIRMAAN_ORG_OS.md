# IP Nirmaan: the Organizational Operating System (Milestone 19)

IP Nirmaan is a machine-readable model of a semiconductor IP company, together
with the engine that runs its work. You submit a requirement ("Create a 4-port
AXI-to-NoC bridge"). The organization analyzes it, selects a workflow, and
routes every piece of work to a specific role. Each task gets an independent
reviewer, an authorized approver, evidence requirements, a gate where one
applies, and an escalation path. As work happens, a task engine enforces the
company constitution and records every change in a hash-chained audit trail.

The organization exists independently of any language model. Roles are records
of responsibility and authority, not prompts. Language models will later power
workers who fill seats in this organization. They get no special access: their
output passes the same state machine, authority matrix, and constitution as a
human's, and it can never mark itself verified or approved.

VeriTriage is IP Nirmaan's verification-intelligence subsystem. It is unchanged
by this milestone and reached through one bridge module.

```
nirmaan plan "Create a 4-port AXI-to-NoC bridge." --detail
nirmaan demo all
nirmaan why <project> microarchitecture
```

---

## 1. Architecture assessment (what existed, what was reused)

This milestone began with an inspection of VeriTriage v1.14.0. The findings
decided the shape of everything below.

| VeriTriage asset | Decision | Why |
|---|---|---|
| Knowledge Packs (42 packs: AXI, NoC, UVM, SVA, CDC, formal, DFT, ...) | **Reused** as skill knowledge sources | Protocol knowledge must not be duplicated per agent. Skills cite packs by ID; a test proves every cited pack exists. |
| `WorkspaceServices` (the stable public API) | **Reused** through one bridge | `veritriage.investigate`, `veritriage.explain_log`, and `knowledge.search` become real, executable organizational tools. |
| M12 agents (8 verification specialists) | **Preserved**, not re-modeled | They are the internals of `veritriage.investigate`. Organizational roles sit above them. |
| M9 orchestrator (Kahn engine) | **Pattern reused, code not shared** | It executes investigation steps against `WorkspaceServices`. Organizational tasks have a review and approval lifecycle it was never meant to carry. |
| M18 event bus | **Not reused** | Its `EventKind` is a closed, verification-specific vocabulary. Adding organizational kinds would couple VeriTriage to Nirmaan. Nirmaan has its own hash-chained audit trail. |
| M10 reviews | **Not reused** | They review investigation bundles, not engineering work products. |
| Idioms: frozen Pydantic vocabulary, `@register_*` tables, AST import laws, crown-jewel extension tests, no dashes | **Adopted wholesale** | Nirmaan reads like the rest of the repository. |

**Architectural gaps this milestone fills:** the repository had no model of
organization, roles, authority, tasks with owners and reviewers, approval
gates, escalation, or a policy layer. All of that is new, and all of it lives
in `src/nirmaan/`, a sibling package in the same distribution.

**The two import laws** (test-enforced in `tests/test_nirmaan_architecture.py`):

1. VeriTriage never imports Nirmaan.
2. Inside Nirmaan, only `nirmaan/integrations/veritriage.py` imports VeriTriage.

---

## 2. The concepts

```
ORGANIZATION -> ROLES -> SKILLS -> CAPABILITIES -> WORKFLOWS -> TASKS
             -> AGENTS -> TOOLS -> EVIDENCE -> REVIEWS -> SIGNOFF
```

| Concept | What it is | Where |
|---|---|---|
| **Organization** | The validated, immutable company. Every question about it is a lookup. | `org/organization.py` |
| **Unit** (company, office, division, department, team, practice) | One node of the org chart. Declares baseline skills and tools for its whole subtree. | `models/org.py::OrgUnit` |
| **Level** | The ladder from Intern to Board. `rank` is the only thing authority compares. | `models/org.py::Level` |
| **Role** | Responsibility plus authority plus expertise at one level in one unit. Mostly **derived**: see section 3. | `models/org.py::Role` |
| **Skill** | Reusable know-how: procedures, failure modes, validation criteria, knowledge sources, tools. Composable through `includes`. | `company/skills.py` |
| **Capability** | A unit of work (`rtl.implement`, `dv.plan`, `signoff.verification`). Tasks require capabilities; skills provide them. | `company/capabilities.py` |
| **Proficiency** | How deeply a role holds a skill, derived from level. Capabilities state the proficiency (and, for signoff, the level) they need. | `org/organization.py` |
| **Authority** | A table: (decision, criticality) to a minimum level and a scope. | `company/governance.py::AUTHORITY` |
| **Escalation route** | Where each kind of problem lands, walked up the role's technical chain. | `company/governance.py::ESCALATION` |
| **Gate** | A point that work may not pass without an authorized (optionally human) approval. | `company/governance.py::GATES` |
| **Principle** | One article of the constitution, backed by registered checks. | `company/governance.py::CONSTITUTION`, `work/policy.py` |
| **Tool** | A capability-granted instrument. `AVAILABLE` tools really execute; `CONTRACT_ONLY` tools are refused, never simulated. | `company/tools.py`, `runtime/tools.py` |
| **Workflow** | A reusable process: stages with conditions, fan-out variants, decision branches, reviews, gates, and evidence requirements. It names capabilities, never teams. | `company/workflows.py` |
| **Requirement / Analysis** | The request, and what the declared vocabulary found in it: intent, features, parameters, and explicit assumptions. | `orchestrator/analyze.py` |
| **Project / Program** | One requirement's plan and state. Programs group projects. | `models/work.py` |
| **Task** | Owner, reviewer, approver, dependencies, skills, evidence requirements, status, review, approval and escalation state, risk, routing rationale. | `models/work.py::Task` |
| **Artifact** | A work product, with provenance and an **assurance** level. | `models/work.py::Artifact` |
| **Evidence** | What backs a claim: a brokered tool run, a VeriTriage session, a review, a named human's attestation, a document, or a bare claim (which satisfies nothing). | `models/work.py::Evidence` |
| **Review / Approval** | Separate acts by separate people. Reviewing is not approving. | `work/engine.py` |
| **Escalation** | Reason, context, attempted actions, evidence, blocking question, and recommended options, routed to a specific role. | `models/work.py::Escalation` |
| **Decision** | An authorized, evidenced engineering decision on the record. | `models/work.py::Decision` |
| **Audit entry** | One hash-chained record: who, what, when, why. | `work/audit.py` |
| **Memory** | Structured, scoped (company, project, team, task, agent) and with provenance. | `models/work.py::MemoryEntry` |
| **Agent** | A worker (human, AI, or system) sitting in a role's seat, powered by a registered runtime. | `models/org.py::AgentProfile`, `runtime/` |

### The distinction everything is built around

```
planned  <  executed  <  verified  <  approved
```

* Planning creates tasks and **no** artifacts, evidence, or tool runs.
* Submitting work makes its artifacts **executed**, and nothing more.
* An artifact becomes **verified** only when substantiated evidence meets every requirement on the task.
* It becomes **approved** only through an authorized, independent approval.
* Work that never needed a review can at most be verified.
* A `CLAIM` is recorded for honesty and satisfies nothing.

---

## 3. How the organization is built

Only structure is written by hand. **Staffing is derived** from unit kinds:

| Unit kind | Derived roles |
|---|---|
| Division | a VP (or an executive named as `head_role`) |
| Department | a Director |
| Team | a Manager and a Tech Lead |
| Leaf team or practice | the individual-contributor ladder: Senior, Engineer, Junior, Intern (overridable, inherited down the subtree) |

Reporting lines follow the chart. Escalation rises one rung at a time:

```
Intern -> Junior -> Engineer -> Senior -> Tech Lead -> Manager -> Director -> VP -> CTO
```

Skills and tools are inherited from every ancestor's baseline, plus the level
profile (tech leads review and decompose; managers plan, delegate, and track).
Tools declared by skills are granted too. Read tools come with any holding of
the skill. Write, execute, and approve tools need at least WORKING proficiency,
so an intern can read a repository but not run the simulator.

The IP Nirmaan definition today has 207 units, 685 derived roles, 140 skills,
97 capabilities, 38 tools, 7 workflows, 6 gates, and 12 principles. It covers
Product and Programs, Architecture, Design Engineering, Verification, Silicon
Implementation (physical design and DFT), Software, Security, Engineering
Infrastructure, Technical Documentation, and Quality and Process. It also
declares structural placeholders for Finance, Legal, HR, Procurement,
Operations, Sales, Marketing, Customer Success, and Partnerships.

**Validation runs on every build.** Every reference must resolve, every chain
must terminate and rise strictly in seniority, the authority matrix must be
complete, and every workflow stage must be ownable by an active role. Every
HIGH or CRITICAL stage must declare an independent review, no evidence
requirement may accept a bare claim, and every gate must have someone
authorized to approve it. An incoherent company is a build error, not a
surprise at planning time.

---

## 4. From requirement to plan

```
requirement
  -> analyze          declared intents, features, parameters; silence becomes an explicit assumption
  -> select workflow  by intent, from the registry
  -> instantiate      stages whose conditions hold; one task per applicable variant
  -> route            owner, reviewer, approver: a scored join over organizational data
  -> gate             downstream work depends on the gate, not just the task
  -> workstreams      one per phase, led by the head of the narrowest unit containing the work
  -> program          owned by the program-management capability
```

**Routing is data, never a branch on a domain name.** A test reads every
string constant in `orchestrator/` and fails if one names a unit, skill,
capability, role, feature, or intent. A candidate owner must:

* hold the capability,
* be active,
* sit on the individual-contributor track (managers delegate; they do not absorb work),
* and hold execution authority for the task's criticality.

The score then prefers, in order:

1. the skills the stage asks for,
2. the unit whose declared specialty provides the capability (nearer units score higher),
3. skills the requirement's features bring into play (capped, so context breaks ties rather than dominating),
4. the level the criticality calls for.

Reviewers must be independent, qualified, and authorized, and the owner's own
chain is preferred. Approvers are the first role up the chain with approval
authority over the task's unit. Every decision keeps its candidate list and
rationale (`why this owner:` in `nirmaan plan --detail`).

Work that needs an independent reviewer and cannot get one is planned
**BLOCKED**, visibly, rather than as a silent deadlock.

---

## 5. The task engine and the constitution

Every operation runs the same gauntlet before it commits:

1. **The lifecycle state machine**: PLANNED, READY, IN_PROGRESS, BLOCKED, IN_REVIEW,
   CHANGES_REQUESTED, APPROVED, COMPLETED, FAILED, ESCALATED, CANCELLED.
2. **The authority matrix**, scoped to the org chart.
3. **The constitution.**

Only then does the engine produce a new state and append one audit entry. An
operation that fails any check changes nothing.

| Article | Enforced by |
|---|---|
| P1 Requirements are traceable | every task traces to the project requirement |
| P2 Important decisions need evidence | HIGH and CRITICAL decisions need substantiated evidence |
| P3 Uncertainty is explicit | an agent result without declared uncertainty is refused |
| P4 No fabricated work | a submission with no artifacts is refused |
| P5 No fabricated tool runs | tool evidence must cite a run the broker recorded, of an AVAILABLE tool |
| P6 Independent review | nobody reviews or approves their own work |
| P7 Conflicts escalate | conflicting reviews block approval until a CONFLICT escalation is resolved |
| P8 Provenance | artifacts carry kind, title, producer, and resolvable upstream inputs |
| P9 Signoff needs evidence | approval and completion need every evidence requirement met |
| P10 No hidden state changes | state changed outside the engine is detected by fingerprint and refused |
| P11 Auditability | the audit trail must verify as an intact hash chain |
| P12 Human gates | gates marked human-required refuse non-human approvers (configurable per project) |

Decision stages branch. Root-cause analysis concludes `rtl_bug`,
`testbench_bug`, `infrastructure`, or `spec_ambiguity`. Recording the outcome
cancels the untaken branches, visibly and audited. A task that fails retries
within its budget, then fails and escalates.

**Managers** get pure projections of state:

* `status_report`: progress, blocked tasks with reasons, escalations, pending reviews, gates, risks, assumptions, and the assurance ladder.
* `why_blocked`: the recursive dependency and evidence chain.
* `verify_completion`: completion that is checked, not asserted.

`trace_graph` links requirement to task to artifact to evidence to tool run.
VeriTriage evidence carries a session ID, so an organizational claim ("the
failure was triaged") leads into VeriTriage's Evidence Graph.

---

## 6. Agents (Phase 4) and VeriTriage (Phase 5)

An `AgentRuntime` implements two methods:

* `accepts(packet)`
* `execute(packet, tools) -> WorkResult`

The packet keeps four knowledge scopes separate:

| Scope | What it holds |
|---|---|
| Company | the constitution |
| Domain | the role's skills and the Knowledge Packs they cite |
| Project | the requirement, analysis, and decisions, plus approved upstream artifacts |
| Task | inputs, evidence requirements, and outcomes |

The runtime never touches state. `run_task` applies its result through the engine:

* its artifacts become executed;
* only tool runs the broker actually made become evidence;
* its statements become claims;
* an escalation request goes up the real chain.

Two runtimes ship:

* `NullRuntime` is the default for every seat. It declines honestly.
* `ScriptedRuntime` exists for tests and simulations.

A model-backed runtime is one class plus `@register_runtime`.

The tool broker executes only AVAILABLE tools with a registered binding, for a
role that holds the grant. `veritriage.investigate` runs the full deterministic
VeriTriage pipeline and returns a session ID. Simulators, synthesis, STA,
formal, and CDC are CONTRACT_ONLY here. The organization plans around them, and
the broker refuses to pretend they ran. Until such a binding exists, their
evidence requirements can be met only by a named human's attestation.

---

## 7. Extending the company without touching the core

Every extension below is data. It goes either into `company/` (the Nirmaan
definition) or into a function registered with `@register_extension`, which is
applied to every build. A JSON overlay shaped like `CompanyDefinition` also
works (`OrganizationBuilder.load_json`). The crown-jewel test
(`test_a_new_engineering_domain_needs_only_an_extension`) adds silicon
photonics this way, with a unit, skill, capabilities, tool, feature, intent,
and workflow, and plans real work into it with zero core changes.

| To add | Do this |
|---|---|
| **A department** | Add an `OrgUnit` (a `dept(...)`/`team(...)`/`prac(...)` entry in `company/org_chart.py`) with its baseline `skills` and `tools`. Its head, tech lead, and ladder are derived. Validation tells you if anything is unreachable. |
| **A role** | Usually unnecessary: roles are derived. For a one-off seat (an executive), add a `Role` to `EXECUTIVES` with `generated=False`. To change what every role at a level does, edit its `LevelProfile`. |
| **A skill** | Add a `Skill` (use `sk(...)` in `company/skills.py`) with `provides`, `includes`, procedures, failure modes, validation criteria, and knowledge sources. Cite a VeriTriage pack by ID instead of re-writing protocol knowledge. Attach it to the units that should hold it. |
| **A capability** | Add a `Capability` with its kind, the proficiency it needs, and (for signoff) the minimum level. Then have a skill provide it. |
| **An agent** | Implement `AgentRuntime` and register it with `@register_runtime("my-model")`. Seat it with an `AgentProfile(role=..., runtime="my-model")` in the definition's `agents`. It inherits everything else from the role. |
| **A workflow** | Add a `WorkflowTemplate`: stages naming capabilities, `depends_on`, `when` conditions, `variants`, `review`, `gate`, `evidence` (with the tools whose runs count), `outcomes` and `branch` for decisions, `owner_from` for continuity. Register an `IntentRule` that selects it. |
| **A tool** | Add a `ToolSpec`. If it can really run here, set `status=AVAILABLE` and register a binding with `@register_binding("tool.id")`. Grant it through a skill's `tools` or a unit's baseline. |
| **A policy** | Add a `Principle` naming check IDs, and implement each check with `@register_check("check-id")` in any module. The engine refuses to start if a named check is unregistered. |
| **An engineering domain** | All of the above, in one extension function. See the crown-jewel test for a complete, runnable example. |

---

## 8. Phases: what this milestone delivers and what it does not

| Phase | Status |
|---|---|
| 1. Organizational foundation | Done: schema, hierarchy, roles, skills, capabilities, authority, escalation, constitution, registry, validation |
| 2. Task and workflow foundation | Done: project, task, dependency graph, workflows, review, approval, gates, escalation, audit, persistence |
| 3. Organizational orchestrator | Done: requirement analysis, workflow selection, routing, task graph, workstreams, seven demos |
| 4. Agent runtime | Interface done: `AgentRuntime`, work packets, tool broker, `run_task`. No model-backed runtime ships yet. |
| 5. Verification organization | Bridge done: VeriTriage investigations are real, evidence-producing tools. Deeper integration is future work. |
| 6. RTL / architecture agents | Not started |
| 7. PD / DFT / firmware agents | Organization and workflow contracts exist; no execution |
| 8. Cross-domain engineering graph | Trace graph exists; linking to design and evidence graphs beyond session IDs is future work |

Nothing here claims RTL was written, simulated, or verified. The engine makes
that claim impossible to fake.

---

## 9. Command reference

```
nirmaan org tree [--unit ID] [--depth N] [--roles]   the org chart
nirmaan org role ROLE [--json]                       a full agent card
nirmaan org skills | skill ID | tools | stats        catalogs
nirmaan org validate | export [-o FILE]              integrity; the machine-readable company
nirmaan workflows [ID] | policies                     registries
nirmaan analyze "REQUIREMENT"                         how the organization reads it
nirmaan plan "REQUIREMENT" [--detail] [--human-gate G] [--auto-gate G]
nirmaan demo [N|all] [--detail]                       the demonstration requirements
nirmaan projects | show P | status P | why P TASK | trace P | audit P | dashboard P
nirmaan task start|submit|review|approve|evidence|attest|tool|complete|escalate|resolve P TASK --as ROLE [--agent]
```

# Milestone 19 (v1.15.0) - IP Nirmaan: the Organizational Operating System

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

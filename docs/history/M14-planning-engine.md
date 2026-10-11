# Milestone 14 (v1.10.0) - Planning Engine

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

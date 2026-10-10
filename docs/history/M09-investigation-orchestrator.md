# Milestone 9 (v0.9.0) - Investigation Orchestrator
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

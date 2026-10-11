# Milestone 18 (v1.14.0) - Automation Engine

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

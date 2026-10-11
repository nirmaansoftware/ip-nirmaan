"""Milestone 18: the Automation Engine.

Covers the milestone's guarantees, not just its features: automation decides
and never executes; events are immutable, ordered, and content-addressed;
replay is faithful; rule evaluation is pure; the action vocabulary is closed; a
broken subscriber never breaks a publish; and, above all, a brand-new trigger
or rule needs only a registration (the crown-jewel architecture test at the
bottom of this file).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import imports

import veritriage.automation.bus as bus_module
from veritriage.automation import (
    BUILT_IN_RULES,
    EventBus,
    RuleEngine,
    Trigger,
    available_rules,
    available_triggers,
    enabled_rules,
    get_trigger,
    register_rule,
    register_trigger,
    unregister_rule,
    unregister_trigger,
)
from veritriage.mcp.tools import call_tool
from veritriage.models import (
    ActionKind,
    AutomationRule,
    Event,
    EventKind,
    make_event_id,
)
from veritriage.workspace import WorkspaceServices

# .../src/veritriage/automation/bus.py -> parents[2] is the src/ root.
SRC = Path(bus_module.__file__).parents[2]


@pytest.fixture()
def bus():
    return EventBus()


@pytest.fixture()
def workspace(tmp_path, fixture_log):
    services = WorkspaceServices(session_root=tmp_path, db=tmp_path / "r.db")
    session = services.investigate([fixture_log("uvm_scoreboard.log")], record_history=True)
    return services, session


# --- Events -----------------------------------------------------------------


def test_events_are_immutable(bus):
    event = bus.publish(EventKind.ANALYSIS_COMPLETED, {"classification": "timeout"})
    with pytest.raises(Exception):
        event.sequence = 99
    with pytest.raises(Exception):
        event.kind = EventKind.PROVIDER_FAILURE


def test_event_ids_are_content_derived():
    first = make_event_id(EventKind.ANALYSIS_COMPLETED, {"a": 1}, 0)
    second = make_event_id(EventKind.ANALYSIS_COMPLETED, {"a": 1}, 0)
    assert first == second and first.startswith("ev-auto-")
    assert first != make_event_id(EventKind.ANALYSIS_COMPLETED, {"a": 2}, 0)
    assert first != make_event_id(EventKind.ANALYSIS_COMPLETED, {"a": 1}, 1)


def test_sequence_is_monotonic(bus):
    events = [bus.publish(EventKind.SCHEDULE_TICK, {"n": str(i)}) for i in range(5)]
    assert [e.sequence for e in events] == [0, 1, 2, 3, 4]


def test_every_event_kind_is_publishable(bus):
    for kind in EventKind:
        assert bus.publish(kind, {}).kind is kind


def test_events_summarize_themselves(bus):
    event = bus.publish(EventKind.REGRESSION_DETECTED, {"times_seen": 3}, subject="reg-1")
    assert "Regression Detected" in event.summary()
    assert "reg-1" in event.summary()


# --- The bus ----------------------------------------------------------------


def test_subscribers_run_in_registration_order(bus):
    order: list[str] = []
    bus.subscribe(lambda e: order.append("first"), name="first")
    bus.subscribe(lambda e: order.append("second"), name="second")
    bus.publish(EventKind.WORKSPACE_OPENED, {})
    assert order == ["first", "second"]


def test_subscribers_can_filter_by_kind(bus):
    seen: list[Event] = []
    bus.subscribe(seen.append, kind=EventKind.PROVIDER_FAILURE, name="only-providers")
    bus.publish(EventKind.ANALYSIS_COMPLETED, {})
    assert seen == []
    bus.publish(EventKind.PROVIDER_FAILURE, {"provider": "acme"})
    assert len(seen) == 1


def test_a_broken_subscriber_never_breaks_publish(bus):
    delivered: list[Event] = []

    def _explode(event):
        raise RuntimeError("subscriber is down")

    bus.subscribe(_explode, name="broken")
    bus.subscribe(delivered.append, name="healthy")

    event = bus.publish(EventKind.ANALYSIS_COMPLETED, {})
    assert event is not None
    assert len(delivered) == 1, "a broken listener must not cost a delivery"
    assert bus.failures and "broken" in bus.failures[0]


def test_replay_reproduces_the_same_decisions(bus):
    for i in range(3):
        bus.publish(EventKind.REGRESSION_DETECTED, {"seen_before": True, "times_seen": i})

    engine = RuleEngine()
    original = [
        [(o.rule_id, o.matched, o.reason) for o in engine.evaluate(e)]
        for e in bus.events()
    ]

    replayed: list[Event] = []
    bus.subscribe(replayed.append, name="collector")
    count = bus.replay()

    assert count == 3
    after = [
        [(o.rule_id, o.matched, o.reason) for o in engine.evaluate(e)] for e in replayed
    ]
    assert after == original


def test_replay_does_not_rewrite_history(bus):
    bus.publish(EventKind.SCHEDULE_TICK, {})
    before = [(e.event_id, e.sequence) for e in bus.events()]
    bus.replay()
    assert [(e.event_id, e.sequence) for e in bus.events()] == before


def test_the_log_is_bounded_and_reports_what_it_dropped():
    small = EventBus(capacity=3)
    for i in range(6):
        small.publish(EventKind.SCHEDULE_TICK, {"n": str(i)})
    assert len(small.events()) == 3
    assert small.dropped == 3
    # The survivors are the newest, in order.
    assert [e.payload["n"] for e in small.events()] == ["3", "4", "5"]


def test_events_can_be_filtered_and_limited(bus):
    bus.publish(EventKind.ANALYSIS_COMPLETED, {})
    bus.publish(EventKind.PROVIDER_FAILURE, {"provider": "a"})
    bus.publish(EventKind.PROVIDER_FAILURE, {"provider": "b"})
    assert len(bus.events(kind=EventKind.PROVIDER_FAILURE)) == 2
    assert len(bus.events(since=2)) == 1
    assert len(bus.events(limit=1)) == 1
    assert bus.last(EventKind.PROVIDER_FAILURE).payload["provider"] == "b"


# --- Triggers and rules -----------------------------------------------------


def test_built_in_triggers_and_rules_register():
    assert len(available_triggers()) >= 10
    assert {r.rule_id for r in BUILT_IN_RULES} <= set(available_rules())


def test_rules_fire_in_priority_order():
    ordered = [(r.priority, r.rule_id) for r in enabled_rules()]
    assert ordered == sorted(ordered)


def test_a_rule_referencing_an_unknown_trigger_is_rejected():
    """Failing at registration beats silently never firing."""
    with pytest.raises(ValueError, match="unknown trigger"):
        register_rule(
            AutomationRule(
                rule_id="bad-rule",
                description="references nothing",
                when="no.such.trigger",
                then=(ActionKind.NOTIFY,),
            )
        )


def test_rule_evaluation_is_deterministic(bus):
    event = bus.publish(
        EventKind.REGRESSION_DETECTED, {"seen_before": True, "times_seen": 4}
    )
    first = RuleEngine().evaluate(event)
    second = RuleEngine().evaluate(event)
    assert [o.model_dump(mode="json") for o in first] == [
        o.model_dump(mode="json") for o in second
    ]


def test_outcomes_are_recorded_whether_or_not_a_rule_fired(bus):
    event = bus.publish(
        EventKind.REGRESSION_DETECTED, {"seen_before": False, "times_seen": 0}
    )
    outcomes = {o.rule_id: o for o in RuleEngine().evaluate(event)}
    assert outcomes["new-regression"].matched is True
    assert outcomes["recurring-regression"].matched is False
    # A declined rule still explains itself.
    assert outcomes["recurring-regression"].reason


def test_a_broken_trigger_never_ends_evaluation(bus):
    class _Exploding(Trigger):
        trigger_id = "exploding"
        kind = EventKind.SCHEDULE_TICK

        def matches(self, event):
            raise RuntimeError("trigger is down")

    register_trigger(_Exploding)
    rule = AutomationRule(
        rule_id="exploding-rule",
        description="broken",
        when="exploding",
        then=(ActionKind.NOTIFY,),
    )
    register_rule(rule)
    try:
        event = bus.publish(EventKind.SCHEDULE_TICK, {})
        outcomes = {o.rule_id: o for o in RuleEngine().evaluate(event)}
        assert outcomes["exploding-rule"].matched is False
        assert "unaffected" in outcomes["exploding-rule"].reason
    finally:
        unregister_rule("exploding-rule")
        unregister_trigger("exploding")


def test_duplicate_requests_are_deduplicated(bus):
    """Two rules asking for the same thing is corroboration, not a repeat."""
    event = bus.publish(
        EventKind.REGRESSION_DETECTED, {"seen_before": True, "times_seen": 2}
    )
    requests = RuleEngine().requests_for(event)
    keys = [(r.action, r.subject) for r in requests]
    assert len(keys) == len(set(keys))


def test_triggers_only_see_their_own_event_kind(bus):
    """A trigger for a different kind is not a verdict, it is not its business."""
    event = bus.publish(EventKind.PROVIDER_FAILURE, {"provider": "acme"})
    fired = {o.rule_id for o in RuleEngine().evaluate(event)}
    assert "provider-outage" in fired
    assert "recurring-regression" not in fired


# --- The central law: decide, never execute ---------------------------------


def test_automation_never_executes_anything():
    """No I/O, no subprocess, no network, no scheduling anywhere in the package."""
    banned_calls = (".read_text", ".write_text", "open(", "Path(", "sleep(")
    banned_modules = {
        "subprocess",
        "os",
        "pathlib",
        "socket",
        "requests",
        "httpx",
        "threading",
        "asyncio",
        "sched",
        "time",
    }
    for path in (SRC / "veritriage" / "automation").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned_calls:
            assert term not in text, f"{path.name} may execute or perform I/O ({term})"
        leaked = banned_modules & imports(path)
        assert not leaked, f"{path.name} imports {leaked}"


def test_automation_imports_only_models():
    """The package decides; it needs nothing but the vocabulary to decide with."""
    for path in (SRC / "veritriage" / "automation").rglob("*.py"):
        for module in imports(path):
            if not module.startswith("veritriage."):
                continue
            assert module.startswith("veritriage.models") or module.startswith(
                "veritriage.automation"
            ), f"{path.name} imports {module}"


def test_actions_are_a_closed_vocabulary():
    """There is no 'run this' member, and no way to add one without editing the enum."""
    assert {a.value for a in ActionKind} == {
        "run_analysis",
        "generate_report",
        "generate_plan",
        "refresh_learning",
        "summarize_changes",
        "rebuild_design_graph",
        "export_bundle",
        "notify",
    }
    for rule in available_rules().values():
        for action in rule.then:
            assert isinstance(action, ActionKind)


def test_rules_carry_no_executable_content():
    """Rules are structured data: a trigger ID and enum members. Nothing more."""
    for rule in available_rules().values():
        payload = rule.model_dump(mode="json")
        assert set(payload) == {
            "rule_id",
            "description",
            "when",
            "then",
            "enabled",
            "priority",
        }
        assert isinstance(payload["when"], str)


def test_automation_never_changes_the_report(tmp_path, fixture_log):
    plain = WorkspaceServices(session_root=tmp_path / "a", db=tmp_path / "a.db")
    reactive = WorkspaceServices(session_root=tmp_path / "b", db=tmp_path / "b.db")

    without = plain.investigate([fixture_log("uvm_scoreboard.log")], automate=False)
    with_automation = reactive.investigate([fixture_log("uvm_scoreboard.log")], automate=True)

    assert without.report.automation is None
    assert with_automation.report.automation is not None
    assert without.report.classification == with_automation.report.classification
    assert [
        (h.id, h.confidence) for h in without.report.reasoning.hypotheses
    ] == [(h.id, h.confidence) for h in with_automation.report.reasoning.hypotheses]
    assert without.report.plan.plan_id == with_automation.report.plan.plan_id


def test_core_unchanged_by_automation():
    for package in (
        "graph",
        "parsers",
        "rules",
        "reasoning",
        "knowledge",
        "waveform",
        "engineering",
        "project",
        "design",
        "agents",
        "learning",
        "planning",
        "conversation",
        "ai",
        "history",
        "orchestrator",
    ):
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            assert "veritriage.automation" not in imports(path), path


def test_automation_vocabulary_is_plain_data():
    imported = imports(SRC / "veritriage" / "models" / "automation.py")
    assert not any(
        m.startswith("veritriage.") and not m.startswith("veritriage.models")
        for m in imported
    )


def test_automation_does_not_duplicate_the_m9_orchestrator():
    """M9 owns execution. Automation decides and hands requests to the workspace."""
    from veritriage.orchestrator import InvestigationStep

    for path in (SRC / "veritriage" / "automation").rglob("*.py"):
        assert "veritriage.orchestrator" not in imports(path), path
    # And M9's step registry is untouched.
    assert InvestigationStep.__module__ == "veritriage.orchestrator.steps"


# --- Workspace integration --------------------------------------------------


def test_analysis_publishes_events(workspace):
    _, session = workspace
    context = session.report.automation
    kinds = {e.kind for e in context.events}
    assert EventKind.ANALYSIS_COMPLETED in kinds
    assert EventKind.REGRESSION_DETECTED in kinds
    assert EventKind.PLAN_GENERATED in kinds


def test_rules_fire_and_actions_are_dispatched(workspace):
    _, session = workspace
    context = session.report.automation
    assert context.rules_fired
    assert context.actions_requested
    assert context.actions_executed
    # Every executed action names the rule that asked for it.
    for result in context.actions_executed:
        assert result.requested_by


def test_unsafe_actions_are_declined_with_a_reason(workspace):
    """Anything not safe to do unattended is recorded as skipped, not silently dropped."""
    _, session = workspace
    declined = [
        r for r in session.report.automation.actions_executed if not r.executed
    ]
    for result in declined:
        assert result.skipped_reason or result.error


def test_the_workspace_exposes_events_and_status(workspace):
    services, _ = workspace
    assert services.recent_events()
    status = services.automation_status()
    assert status.enabled_rules and status.registered_triggers
    assert status.action_vocabulary == [a.value for a in ActionKind]
    assert services.automation_rules()


def test_a_caller_can_drive_automation_with_its_own_events(workspace):
    """A CI job or scheduler publishes; automation decides. No daemon involved."""
    services, _ = workspace
    event = services.publish_event(EventKind.SCHEDULE_TICK, {"label": "nightly"})
    outcomes = RuleEngine().evaluate(event)
    assert event.kind is EventKind.SCHEDULE_TICK
    assert isinstance(outcomes, list)


def test_report_renders_the_automation_section(workspace, tmp_path):
    from veritriage.reports import HtmlReportGenerator

    _, session = workspace
    path = HtmlReportGenerator().write(
        session.report, tmp_path / "report.html", graph=session.graph
    )
    html = path.read_text(encoding="utf-8")
    for section in ("Automation", "Timeline", "Triggered Rules", "Rule Outcomes"):
        assert section in html, section


def test_schema_bumped_for_automation(workspace):
    _, session = workspace
    assert session.report.schema_version == "13"


# --- MCP --------------------------------------------------------------------


def test_automation_over_mcp(workspace):
    services, session = workspace
    services.save(session)

    assert call_tool(services, "recent_events", {})
    status = call_tool(services, "automation_status", {})
    assert status["enabled_rules"] and status["action_vocabulary"]
    assert call_tool(services, "automation_rules", {})

    published = call_tool(
        services,
        "publish_event",
        {"kind": "schedule_tick", "payload": {"label": "nightly"}},
    )
    assert published["event"]["kind"] == "schedule_tick"
    assert "outcomes" in published

    replayed = call_tool(services, "replay_events", {})
    assert replayed["replayed"] >= 1

    activity = call_tool(services, "system_activity", {"session_id": session.session_id})
    assert activity["events"] and activity["outcomes"]

    metrics = call_tool(services, "automation_metrics", {})
    assert metrics["events_by_kind"]
    assert "events_recorded" in metrics


# --- The crown jewel: a new trigger and rule are registrations, nothing else


class _CoverageDropTrigger(Trigger):
    """A throwaway trigger for a fictional condition, defined in this test.

    It proves the milestone's success criterion: teaching the platform to react
    to something new requires writing ONLY a trigger and registering a rule. It
    touches no core module, executes nothing, and its verdict flows to the rule
    engine, the requests, and the workspace dispatcher.
    """

    trigger_id = "coverage.dropped"
    kind = EventKind.ANALYSIS_COMPLETED
    description = "Coverage fell below a threshold."

    threshold = 80.0

    def matches(self, event: Event) -> tuple[bool, str]:
        percent = float(event.payload.get("coverage_percent", 100) or 100)
        if percent < self.threshold:
            return True, f"Coverage is {percent:.0f}%, below the {self.threshold:.0f}% floor."
        return False, f"Coverage is {percent:.0f}%, at or above the floor."


def test_new_trigger_needs_only_registration(tmp_path, fixture_log):
    register_trigger(_CoverageDropTrigger)
    rule = AutomationRule(
        rule_id="coverage-drop",
        description="Coverage fell; surface it and refresh what we know.",
        when="coverage.dropped",
        then=(ActionKind.NOTIFY, ActionKind.REFRESH_LEARNING),
        priority=5,
    )
    register_rule(rule)
    try:
        assert "coverage.dropped" in available_triggers()
        assert "coverage-drop" in available_rules()

        services = WorkspaceServices(session_root=tmp_path, db=tmp_path / "r.db")
        services.investigate([fixture_log("uvm_scoreboard.log")], record_history=True)

        # It fires on an event a caller publishes, with zero core changes...
        event = services.publish_event(
            EventKind.ANALYSIS_COMPLETED, {"coverage_percent": "42"}
        )
        outcomes = {o.rule_id: o for o in RuleEngine().evaluate(event)}
        assert outcomes["coverage-drop"].matched is True
        assert "42%" in outcomes["coverage-drop"].reason

        # ...its requests reach the workspace dispatcher and are executed...
        results = services.dispatch_actions(outcomes["coverage-drop"].requests)
        assert {r.action for r in results} == {ActionKind.NOTIFY, ActionKind.REFRESH_LEARNING}
        assert any(r.executed for r in results)

        # ...and it declines cleanly when the condition does not hold.
        quiet = services.publish_event(
            EventKind.ANALYSIS_COMPLETED, {"coverage_percent": "95"}
        )
        assert {o.rule_id: o for o in RuleEngine().evaluate(quiet)}[
            "coverage-drop"
        ].matched is False
    finally:
        unregister_rule("coverage-drop")
        unregister_trigger("coverage.dropped")

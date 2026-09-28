"""``veritriage`` command-line interface (Typer + Rich)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

import veritriage
from veritriage.models import AnalysisReport, Severity
from veritriage.reasoning import AIReasoner, AIReasoningError
from veritriage.parsers import available_parsers
from veritriage.reports import HtmlReportGenerator
from veritriage.utils import write_json

# The CLI is a client of the workspace service layer (M8): investigation
# logic lives in WorkspaceServices, shared verbatim with the MCP server.
# Nothing here may import veritriage.pipeline directly; an architecture test
# in tests/test_workspace.py pins that.
from veritriage.workspace import WorkspaceServices

#: Default location of the regression database, relative to the working tree.
DEFAULT_DB = Path(".veritriage") / "regressions.db"

app = typer.Typer(
    name="veritriage",
    help="VeriTriage, the IP Nirmaan verification engine - turn verification artifacts into evidence-backed root-cause reports.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
_err = Console(stderr=True)


@app.command()
def analyze(
    artifacts: List[Path] = typer.Argument(
        ...,
        help="Artifacts to analyze together: simulation log, compile log, coverage summary, test metadata.",
    ),
    output_dir: Path = typer.Option(
        Path("."),
        "--output-dir",
        "-o",
        help="Directory for analysis.json, evidence_graph.json, and report.html.",
    ),
    parser: Optional[str] = typer.Option(
        None, "--parser", help="Force one registered parser for every artifact instead of auto-detecting."
    ),
    ai: bool = typer.Option(
        False, "--ai/--no-ai", help="Also run the AI review stage (requires 'pip install ip-nirmaan[ai]')."
    ),
    ai_model: str = typer.Option(
        "claude-opus-4-8", "--ai-model", help="Claude model to use for the AI review."
    ),
    history: bool = typer.Option(
        True,
        "--history/--no-history",
        help="Record this run in the regression database and attach historical context.",
    ),
    context: bool = typer.Option(
        True,
        "--context/--no-context",
        help="Gather engineering context (recent commits, manifests) from the context root.",
    ),
    context_root: Path = typer.Option(
        Path("."), "--context-root", help="Directory the context providers inspect."
    ),
    project: bool = typer.Option(
        True,
        "--project/--no-project",
        help="Read a project model (*.vproj.json under the context root) for "
        "project-aware reasoning and report context; degrades silently if absent.",
    ),
    agents: bool = typer.Option(
        True,
        "--agents/--no-agents",
        help="Run the domain specialists over the deterministic result and attach "
        "their merged second opinion to the report.",
    ),
    learn: bool = typer.Option(
        True,
        "--learn/--no-learn",
        help="Recall what prior investigations suggest, and calibrate agent influence "
        "from their track record.",
    ),
    plan: bool = typer.Option(
        True,
        "--plan/--no-plan",
        help="Derive a structured investigation plan from the conclusions and attach "
        "it to the report.",
    ),
    db: Path = typer.Option(
        DEFAULT_DB, "--db", help="Regression database file (created on first use)."
    ),
) -> None:
    """Analyze verification artifacts into an evidence graph and reports."""
    engineering = _gather_context(context_root) if context else None
    services = WorkspaceServices(db=db)
    project_model = None
    if project:
        model = services.load_project_model(context_root) or services.build_project_model(
            context_root
        )
        project_model = model if not model.is_empty else None
    try:
        session = services.investigate(
            artifacts,
            parser_name=parser,
            engineering=engineering,
            record_history=history,
            project=project_model,
            agents=agents,
            learn=learn,
            plan=plan,
        )
    except (FileNotFoundError, ValueError) as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)
    except KeyError as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc.args[0]))}")
        raise typer.Exit(code=2)
    report, graph = session.report, session.graph

    if ai and report.reasoning is not None:
        try:
            review = AIReasoner(model=ai_model).review(graph, report.reasoning)
            report.reasoning.ai_review = review
            report.ai_summary = review.narrative
            for hypothesis in report.reasoning.hypotheses:
                note = review.hypothesis_notes.get(hypothesis.id)
                if note:
                    hypothesis.ai_note = note
        except AIReasoningError as exc:
            # AI is optional by design: warn and continue with the deterministic result.
            _err.print(f"[yellow]warning:[/yellow] AI review skipped - {escape(str(exc))}")

    json_path = write_json(report, output_dir / "analysis.json")
    graph_path = write_json(graph, output_dir / "evidence_graph.json")
    html_path = HtmlReportGenerator().write(report, output_dir / "report.html", graph=graph)

    _print_summary(report)
    console.print(f"\n[dim]wrote[/dim] {json_path}")
    console.print(f"[dim]wrote[/dim] {graph_path}")
    console.print(f"[dim]wrote[/dim] {html_path}")

    # Non-zero exit when the run failed, so CI can gate on it.
    if report.classification.category.value != "no_failure":
        raise typer.Exit(code=1)


@app.command()
def parsers() -> None:
    """List registered parsers."""
    table = Table(title="Registered parsers")
    table.add_column("Name")
    table.add_column("Artifact type")
    table.add_column("File patterns")
    for name, cls in sorted(available_parsers().items()):
        table.add_row(name, cls.artifact_type.value, ", ".join(cls.file_patterns) or "-")
    console.print(table)


@app.command()
def knowledge() -> None:
    """List loaded Knowledge Packs and what each one teaches."""
    from veritriage.knowledge import load_packs

    table = Table(title="Knowledge Packs")
    for column in ("Pack", "Version", "Domain", "Concepts", "Patterns", "Playbooks", "FSMs"):
        table.add_column(column)
    for pack in load_packs():
        table.add_row(
            f"{pack.name} ({pack.id})",
            pack.version,
            pack.domain,
            str(len(pack.concepts)),
            str(len(pack.patterns)),
            str(len(pack.playbooks)),
            str(len(pack.state_machines)),
        )
    console.print(table)


@app.command()
def learn(
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database to learn from."),
) -> None:
    """Recompute learning artifacts from the regression database."""
    services = WorkspaceServices(db=db)
    stats = services.learn_from_history()
    if stats is None:
        _err.print(
            f"[yellow]warning:[/yellow] no regression database at {escape(str(db))}; "
            "nothing to learn from yet."
        )
        raise typer.Exit(code=0)

    console.print(
        f"Learned from [bold]{stats.corpus_size}[/bold] recorded regression"
        f"{'s' if stats.corpus_size != 1 else ''} and "
        f"[bold]{stats.feedback_count}[/bold] feedback record"
        f"{'s' if stats.feedback_count != 1 else ''}."
    )
    table = Table(title="Learning artifacts")
    table.add_column("Family")
    table.add_column("Artifacts", justify="right")
    for kind, count in sorted(stats.artifacts_by_kind.items()):
        table.add_row(kind.replace("_", " "), str(count))
    if not stats.artifacts_by_kind:
        table.add_row("[dim]none yet[/dim]", "0")
    console.print(table)

    reliability = services.agent_reliability()
    rated = [r for r in reliability if r.accuracy is not None]
    if rated:
        agents_table = Table(title="Agent reliability")
        for column in ("Agent", "Led", "Correct", "Accuracy", "Influence"):
            agents_table.add_column(column)
        for item in rated:
            agents_table.add_row(
                item.agent_id,
                str(item.times_led),
                str(item.times_correct),
                f"{item.accuracy:.0%}" if item.accuracy is not None else "-",
                f"{item.calibration_multiplier:.2f}x",
            )
        console.print(agents_table)
    else:
        console.print(
            "[dim]No engineer feedback yet, so no specialist is calibrated. "
            "Record judgments with 'veritriage feedback' to enable calibration.[/dim]"
        )


@app.command()
def plan(
    artifacts: List[Path] = typer.Argument(..., help="Artifacts to plan an investigation for."),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database (for history and learning)."),
) -> None:
    """Produce a structured investigation plan for a set of artifacts."""
    services = WorkspaceServices(db=db)
    try:
        session = services.investigate(artifacts)
    except (FileNotFoundError, ValueError) as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)
    derived = services.investigation_plan(session) or services.build_investigation_plan(session)

    console.print(Panel(
        f"[bold]{escape(derived.objective)}[/bold]\n\n[dim]{escape(derived.strategy)}[/dim]",
        title=f"Investigation plan · {derived.plan_id}",
        border_style="blue",
    ))

    table = Table(title=f"Recommended steps (total effort {derived.estimated_effort})")
    for column in ("#", "Kind", "Action", "Value/effort", "Derived from"):
        table.add_column(column)
    for index, step in enumerate(derived.steps, start=1):
        table.add_row(
            str(index),
            step.kind.value,
            step.action,
            f"{step.valuation.priority_score:.2f}",
            step.derived_from,
        )
    console.print(table)

    for step in derived.steps:
        if step.decision is None:
            continue
        console.print(f"\n[bold]Decision point:[/bold] {escape(step.decision.question)}")
        if step.decision.resolved_outcome:
            console.print(
                f"  [green]already answered by this run's evidence:[/green] "
                f"{escape(step.decision.resolved_outcome)}"
            )
            console.print(f"  [dim]{escape(step.decision.resolved_because or '')}[/dim]")
        for branch in step.decision.branches:
            console.print(f"  [bold]->[/bold] {escape(branch.outcome)}")
            for child in branch.steps:
                console.print(f"       - {escape(child.action)}")

    if derived.evidence_requests:
        requests = Table(title="Evidence still needed")
        requests.add_column("What")
        requests.add_column("Why it matters")
        for request in derived.evidence_requests:
            requests.add_row(request.what, request.why)
        console.print(requests)

    if derived.completion_conditions:
        console.print("\n[bold]You are done when[/bold]")
        for condition in derived.completion_conditions:
            mark = "[green]done[/green]" if condition.satisfied else "[dim]open[/dim]"
            console.print(f"  {mark} {escape(condition.statement)}")

    if derived.risks:
        console.print("\n[bold]Risks[/bold]")
        for risk in derived.risks:
            console.print(f"  [yellow]![/yellow] {escape(risk)}")


@app.command()
def render(
    artifacts: List[Path] = typer.Argument(..., help="Artifacts to investigate, then render."),
    renderer: str = typer.Option(
        "engineer-summary", "--renderer", "-r", help="Named view to render."
    ),
    provider: str = typer.Option(
        "deterministic-echo", "--provider", "-p", help="Generative provider."
    ),
    show_prompt: bool = typer.Option(
        False, "--show-prompt", help="Print the exact prompt instead of generating."
    ),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database."),
) -> None:
    """Render an investigation as grounded prose."""
    services = WorkspaceServices(db=db)
    try:
        session = services.investigate(artifacts)
    except (FileNotFoundError, ValueError) as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)

    try:
        if show_prompt:
            prompt = services.preview_prompt(session, renderer)
            console.print(
                Panel(
                    escape(prompt.render()),
                    title=f"Prompt · {prompt.template_id} v{prompt.template_version} "
                    f"({prompt.size} chars, {len(prompt.citations)} citations)",
                    border_style="blue",
                )
            )
            raise typer.Exit(code=0)
        view = services.render_investigation(session, renderer, provider)
    except KeyError as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc.args[0]))}")
        raise typer.Exit(code=2)

    if view.is_empty:
        _err.print(
            f"[yellow]warning:[/yellow] the {escape(view.provider)!r} provider generated "
            "nothing. The structured intelligence is unaffected."
        )
        for limit in view.limitations:
            _err.print(f"  [dim]{escape(limit)}[/dim]")
        raise typer.Exit(code=0)

    body = Table.grid(padding=(0, 1))
    body.add_column()
    body.add_row(escape(view.prose))
    if view.citations:
        body.add_row("")
        body.add_row("[bold]Grounded in[/bold]")
        for citation in view.citations[:8]:
            body.add_row(f"  [dim]{citation.token}  {escape(citation.label[:60])}[/dim]")
    if not view.grounded:
        body.add_row("")
        body.add_row("[yellow]! this provider invented citations; they were removed[/yellow]")
    for limit in view.limitations:
        body.add_row(f"  [yellow]![/yellow] {escape(limit)}")
    console.print(
        Panel(
            body,
            title=f"{escape(renderer)} · {escape(view.provider)}",
            border_style="blue" if view.grounded else "yellow",
        )
    )


@app.command()
def automation(
    artifacts: List[Path] = typer.Argument(
        None, help="Optional artifacts to analyze first, so events have something to react to."
    ),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database."),
) -> None:
    """Show automation rules, triggers, and what the platform reacted to."""
    services = WorkspaceServices(db=db)

    if artifacts:
        try:
            session = services.investigate(list(artifacts), record_history=True)
        except (FileNotFoundError, ValueError) as exc:
            _err.print(f"[red]error:[/red] {escape(str(exc))}")
            raise typer.Exit(code=2)
        context = session.report.automation
        if context is not None:
            events = Table(title="Events published")
            events.add_column("#")
            events.add_column("Event")
            events.add_column("Detail")
            for event in context.events:
                events.add_row(
                    str(event.sequence),
                    event.kind.display_name,
                    ", ".join(f"{k}={v}" for k, v in sorted(event.payload.items()) if v not in (None, "")),
                )
            console.print(events)

            outcomes = Table(title="Rule verdicts")
            for column in ("Rule", "Fired", "Why"):
                outcomes.add_column(column)
            for outcome in context.outcomes:
                outcomes.add_row(
                    outcome.rule_id,
                    "[green]yes[/green]" if outcome.matched else "[dim]no[/dim]",
                    outcome.reason,
                )
            console.print(outcomes)

            if context.actions_executed:
                actions = Table(title="Actions")
                for column in ("Action", "Requested by", "Result"):
                    actions.add_column(column)
                for result in context.actions_executed:
                    outcome_text = (
                        result.detail or "done"
                        if result.executed
                        else f"[dim]{result.skipped_reason or result.error}[/dim]"
                    )
                    actions.add_row(
                        result.action.display_name, result.requested_by, outcome_text
                    )
                console.print(actions)

    status = services.automation_status()
    rules = Table(title="Registered rules")
    for column in ("Rule", "When", "Then", "Priority"):
        rules.add_column(column)
    for rule in services.automation_rules():
        rules.add_row(
            rule.rule_id,
            rule.when,
            ", ".join(a.value for a in rule.then),
            str(rule.priority),
        )
    console.print(rules)
    console.print(
        f"[dim]{len(status.registered_triggers)} triggers, "
        f"{len(status.action_vocabulary)} actions in the closed vocabulary, "
        f"{status.events_recorded} events recorded.[/dim]"
    )
    console.print(
        "[dim]Automation observes and decides. It runs no simulation, calls no "
        "webhook, and schedules no OS job.[/dim]"
    )


@app.command()
def providers(
    provider: Optional[str] = typer.Option(None, "--provider", help="Mark one active."),
) -> None:
    """List generative providers, their capabilities, and the named views."""
    services = WorkspaceServices()
    table = Table(title="Generative providers")
    for column in ("Provider", "Generates", "Deterministic", "Local", "Notes"):
        table.add_column(column)
    for status in services.ai_provider_status(provider):
        caps = status.capabilities
        marker = " [green](active)[/green]" if status.active else ""
        table.add_row(
            f"{status.name}{marker}",
            "yes" if caps and caps.generates else "no",
            "yes" if caps and caps.deterministic else "no",
            "yes" if caps and caps.local else "no",
            (caps.notes if caps and caps.notes else status.error or "-"),
        )
    console.print(table)
    console.print(f"[dim]named views: {', '.join(services.ai_renderers())}[/dim]")
    console.print(
        "[dim]No built-in provider calls an external API. Generation is off by "
        "default; the platform is complete without prose.[/dim]"
    )


@app.command()
def ask(
    artifacts: List[Path] = typer.Argument(..., help="Artifacts to investigate, then ask about."),
    question: List[str] = typer.Option(
        [],
        "--question",
        "-q",
        help="A question, in the platform's vocabulary. Repeat to hold a conversation; "
        "context carries between them.",
    ),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database."),
) -> None:
    """Ask grounded questions about an investigation."""
    services = WorkspaceServices(db=db)
    try:
        session = services.investigate(artifacts)
    except (FileNotFoundError, ValueError) as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)

    questions = list(question) or ["help"]
    engine = services.start_conversation(session)
    for text in questions:
        answer = engine.ask(text)
        body = Table.grid(padding=(0, 1))
        body.add_column()
        body.add_row(f"[bold]{escape(answer.summary)}[/bold]")
        for part in answer.sections:
            body.add_row("")
            body.add_row(f"[bold]{escape(part.heading)}[/bold]")
            for statement in part.statements:
                body.add_row(f"  • {escape(statement)}")
            for reference in part.references[:6]:
                body.add_row(
                    f"    [dim]{reference.kind.value}:{reference.ref_id}"
                    f"  {escape(reference.label[:60])}[/dim]"
                )
        if answer.limitations:
            body.add_row("")
            body.add_row("[bold]Limits[/bold]")
            for limit in answer.limitations:
                body.add_row(f"  [yellow]![/yellow] {escape(limit)}")
        if answer.followups:
            body.add_row("")
            hints = ", ".join(
                f"{f.intent.value}" + (f" {f.target}" if f.target else "")
                for f in answer.followups
            )
            body.add_row(f"[dim]next: {escape(hints)}[/dim]")
        console.print(
            Panel(
                body,
                title=f"{escape(text)}  [{answer.intent.value}]",
                border_style="blue" if answer.resolved else "yellow",
            )
        )
    console.print(f"[dim]navigation: {escape(engine.session.context.describe())}[/dim]")


@app.command()
def design(
    root: Path = typer.Argument(Path("."), help="Project root or manifest path."),
    module: Optional[str] = typer.Option(
        None, "--module", help="Describe one element and everything one hop around it."
    ),
) -> None:
    """Show the structural understanding of a project (the Design Graph)."""
    services = WorkspaceServices()
    graph = services.design_graph(root)
    if graph is None:
        _err.print(
            f"[yellow]warning:[/yellow] no project model at {escape(str(root))}; "
            "add a *.vproj.json manifest to give VeriTriage structure."
        )
        raise typer.Exit(code=0)

    if module:
        described = services.describe_module(module, root)
        if described is None:
            _err.print(f"[red]error:[/red] no design element named {escape(module)}")
            raise typer.Exit(code=2)
        node = described["node"]
        console.print(
            Panel(
                f"[bold]{escape(node['name'])}[/bold]  [dim]{node['kind']}[/dim]\n"
                + (f"path: {escape(node['qualified_name'])}\n" if node.get("qualified_name") else "")
                + (f"owner: {escape(node['owner'])}\n" if node.get("owner") else "")
                + (f"source: {escape(node['source_file'])}" if node.get("source_file") else ""),
                title="Design element",
                border_style="blue",
            )
        )
        table = Table(title="Relationships")
        for column in ("Direction", "Relation", "Other", "Derived from"):
            table.add_column(column)
        for relation in described["relations"]:
            table.add_row(
                relation["direction"],
                relation["relation"] + (" [dim](inferred)[/dim]" if relation["inferred"] else ""),
                relation["other"],
                relation["rationale"],
            )
        console.print(table)
        raise typer.Exit(code=0)

    stats = graph.stats()
    console.print(
        Panel(
            f"[bold]{len(graph.nodes)}[/bold] structural nodes, "
            f"[bold]{len(graph.edges)}[/bold] typed relationships\n"
            f"[dim]{escape(graph.fingerprint())}[/dim]",
            title=f"Design Graph · {graph.project_id}",
            border_style="blue",
        )
    )

    hierarchy = services.design_hierarchy(root)
    if hierarchy:
        console.print("\n[bold]Hierarchy[/bold]")
        for row in hierarchy:
            console.print(f"  {'  ' * row['depth']}{escape(row['name'])}")

    query = services.design_query(root)
    protocols = query.protocol_map() if query else {}
    if protocols:
        table = Table(title="Protocol map")
        table.add_column("Protocol")
        table.add_column("Interfaces")
        for protocol, interfaces in protocols.items():
            table.add_row(protocol, ", ".join(interfaces))
        console.print(table)

    if query:
        crossings = query.crossings()
        if crossings:
            console.print("\n[bold]Clock domain crossings[/bold]")
            for left, right in crossings:
                console.print(f"  [yellow]![/yellow] {escape(left.name)} <-> {escape(right.name)}")
        unverified = query.unverified_modules()
        if unverified:
            console.print("\n[bold]Modules with no coverage or assertions declared[/bold]")
            for node in unverified[:8]:
                console.print(f"  [dim]-[/dim] {escape(node.name)}")

    counts = Table(title="Graph composition")
    counts.add_column("Kind")
    counts.add_column("Count", justify="right")
    for key, value in stats.items():
        counts.add_row(key.replace("edge:", "-> "), str(value))
    console.print(counts)


@app.command()
def agents() -> None:
    """List the registered domain specialists and reasoning providers."""
    from veritriage.agents import available_agents, available_providers

    table = Table(title="Registered agents")
    for column in ("Agent", "Domain", "Class"):
        table.add_column(column)
    for agent_id, agent_cls in sorted(available_agents().items()):
        table.add_row(agent_id, agent_cls.domain.value, agent_cls.__name__)
    console.print(table)

    providers = Table(title="Reasoning providers (the generative seam)")
    for column in ("Provider", "Kind"):
        providers.add_column(column)
    for name in sorted(available_providers()):
        kind = "deterministic" if name != "null" else "disabled (default)"
        providers.add_row(name, kind)
    console.print(providers)
    console.print(
        "[dim]Agents are deterministic and always run. Providers may only narrate a "
        "conclusion that already exists; none calls an external API.[/dim]"
    )


@app.command()
def waveform() -> None:
    """List registered waveform adapters and the formats they resolve."""
    from veritriage.waveform import available_adapters

    table = Table(title="Waveform adapters")
    for column in ("Adapter", "Format", "File patterns", "Capabilities"):
        table.add_column(column)
    for name, cls in sorted(available_adapters().items()):
        table.add_row(
            name,
            cls.format,
            ", ".join(cls.file_patterns) or "-",
            ", ".join(sorted(c.value for c in cls.capabilities)) or "-",
        )
    console.print(table)


@app.command()
def mcp(
    session_root: Path = typer.Option(
        None, "--session-root", help="Sessions directory (default .veritriage/sessions)."
    ),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database file."),
) -> None:
    """Serve VeriTriage as an MCP tool server over stdio.

    Point an MCP host (Claude Code, an IDE) at `veritriage mcp` and it can
    analyze regressions, walk evidence, search knowledge, and query history
    through the same services the CLI uses.
    """
    from veritriage.mcp import McpStdioServer

    services = WorkspaceServices(session_root=session_root, db=db)
    McpStdioServer(services).serve_forever()


@app.command()
def sessions(
    session_root: Path = typer.Option(
        None, "--session-root", help="Sessions directory (default .veritriage/sessions)."
    ),
) -> None:
    """List persisted investigation sessions."""
    services = WorkspaceServices(session_root=session_root)
    stored = services.list_sessions()
    if not stored:
        console.print("[dim]no sessions stored yet; run `veritriage investigate`[/dim]")
        return
    table = Table(title=f"Investigation sessions ({len(stored)})")
    for column in ("Session", "Created", "Classification", "Confidence", "Test", "Inputs"):
        table.add_column(column)
    for summary in stored:
        table.add_row(
            summary.session_id,
            summary.created_at[:16],
            summary.classification,
            f"{summary.confidence}%",
            summary.test_name or "-",
            str(len(summary.input_files)),
        )
    console.print(table)


@app.command()
def run(
    profile: str = typer.Argument(..., help="Investigation profile, e.g. fast-triage."),
    artifacts: List[Path] = typer.Argument(..., help="Artifacts to investigate."),
    context_root: Path = typer.Option(
        Path("."), "--context-root", help="Directory the context providers inspect."
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Report output directory (profiles with render-report)."
    ),
    session_root: Path = typer.Option(
        None, "--session-root", help="Sessions directory (default .veritriage/sessions)."
    ),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database file."),
) -> None:
    """Run one orchestrated investigation profile end to end."""
    from veritriage.orchestrator import run_profile

    services = WorkspaceServices(session_root=session_root, db=db)
    try:
        session = run_profile(
            services, profile, artifacts, context_root=context_root, output_dir=output_dir
        )
    except KeyError as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc.args[0]))}")
        raise typer.Exit(code=2)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)

    _print_summary(session.report)
    trace = session.trace
    table = Table(title=f"Investigation trace ({trace.profile}, plan {session.plan.plan_id})")
    for column in ("Step", "Status", "Attempts", "Duration", "Produced"):
        table.add_column(column)
    for step in trace.steps:
        table.add_row(
            step.step_id,
            step.status.value,
            str(step.attempts),
            f"{step.duration_ms:.0f} ms" if step.duration_ms is not None else "-",
            ", ".join(step.produced) or "-",
        )
    console.print(table)
    for entry in trace.attribution:
        console.print(
            f"[dim]{entry.subsystem}:[/dim] {len(entry.signals)} signal"
            f"{'s' if len(entry.signals) != 1 else ''}, {entry.recommendations} recommendation"
            f"{'s' if entry.recommendations != 1 else ''}"
        )
    console.print(
        f"[dim]session[/dim] [bold]{session.session_id}[/bold]"
        + (f"  [dim]total[/dim] {trace.total_duration_ms:.0f} ms" if trace.total_duration_ms else "")
    )
    if not trace.completed:
        _err.print("[yellow]warning:[/yellow] investigation completed partially; see the trace")
    if session.report.classification.category.value != "no_failure":
        raise typer.Exit(code=1)


@app.command()
def profiles() -> None:
    """List registered investigation profiles and their steps."""
    from veritriage.orchestrator import available_profiles

    table = Table(title="Investigation profiles")
    for column in ("Profile", "Steps", "Description"):
        table.add_column(column)
    for name, profile in sorted(available_profiles().items()):
        table.add_row(name, " -> ".join(s.id for s in profile.steps), profile.description)
    console.print(table)


bundle_app = typer.Typer(
    name="bundle",
    help="Export, import, validate, and compare portable investigation bundles.",
    no_args_is_help=True,
)
app.add_typer(bundle_app)


@bundle_app.command("export")
def bundle_export(
    session_id: str = typer.Argument(..., help="Session ID to export (see `veritriage sessions`)."),
    output: Path = typer.Option(..., "--output", "-o", help="Bundle file to write (e.g. inv.vtb)."),
    exported_by: Optional[str] = typer.Option(None, "--by", help="Who exported this investigation."),
    title: Optional[str] = typer.Option(None, "--title", help="A human title for the bundle."),
    compress: bool = typer.Option(True, "--compress/--no-compress", help="gzip the bundle."),
    session_root: Path = typer.Option(None, "--session-root", help="Sessions directory."),
) -> None:
    """Export a persisted session as a portable investigation bundle."""
    services = WorkspaceServices(session_root=session_root)
    session = services.load(session_id)
    if session is None:
        _err.print(f"[red]error:[/red] unknown session {escape(session_id)}")
        raise typer.Exit(code=2)
    path = services.export_bundle(
        session, output, exported_by=exported_by, title=title, compress=compress
    )
    console.print(f"[dim]exported[/dim] {path}")


@bundle_app.command("import")
def bundle_import(
    bundle: Path = typer.Argument(..., help="Bundle file to import."),
    session_root: Path = typer.Option(None, "--session-root", help="Sessions directory."),
) -> None:
    """Import a bundle, loading its session into the workspace to continue."""
    from veritriage.collab import BundleFormatError

    services = WorkspaceServices(session_root=session_root)
    try:
        loaded = services.import_bundle(bundle)
    except BundleFormatError as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)
    console.print(
        f"imported bundle [bold]{loaded.bundle_id}[/bold]; session "
        f"[bold]{loaded.session.session_id}[/bold] is now available"
    )


@bundle_app.command("validate")
def bundle_validate(
    bundle: Path = typer.Argument(..., help="Bundle file to validate."),
) -> None:
    """Verify a bundle's schema, integrity, and referential consistency."""
    from veritriage.collab import BundleFormatError

    services = WorkspaceServices()
    try:
        result = services.validate_bundle(bundle)
    except BundleFormatError as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)
    verdict = "[green]valid[/green]" if result.ok else "[red]INVALID[/red]"
    console.print(f"bundle {result.bundle_id} (schema {result.schema_version}): {verdict}")
    for finding in result.findings:
        color = "red" if finding.severity.value == "error" else "yellow"
        console.print(f"  [{color}]{finding.severity.value}[/{color}] {finding.code}: {escape(finding.message)}")
    if not result.ok:
        raise typer.Exit(code=1)


@bundle_app.command("compare")
def bundle_compare(
    bundle_a: Path = typer.Argument(..., help="First bundle."),
    bundle_b: Path = typer.Argument(..., help="Second bundle."),
) -> None:
    """Explain what changed between two investigation bundles."""
    from veritriage.collab import BundleFormatError

    services = WorkspaceServices()
    try:
        comparison = services.compare_bundles(bundle_a, bundle_b)
    except BundleFormatError as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)
    console.print(f"[bold]{escape(comparison.summary)}[/bold]\n")
    for delta in comparison.deltas:
        console.print(f"[bold]{delta.facet}[/bold]")
        for item in delta.changed:
            console.print(f"  [yellow]~[/yellow] {escape(item)}")
        for item in delta.added:
            console.print(f"  [green]+[/green] {escape(item)}")
        for item in delta.removed:
            console.print(f"  [red]-[/red] {escape(item)}")


@app.command()
def review(
    bundle: Path = typer.Argument(..., help="Bundle file to review."),
    verdict: str = typer.Option(
        ..., "--verdict", help="approved | needs_investigation | incorrect_diagnosis | "
        "incomplete_evidence | false_positive."
    ),
    reviewer: str = typer.Option(..., "--reviewer", help="Who is reviewing."),
    comment: str = typer.Option("", "--comment", help="Review comment."),
) -> None:
    """Record a structured review on a bundle (layers on top; never edits it)."""
    from veritriage.collab import BundleFormatError

    services = WorkspaceServices()
    try:
        path = services.review_bundle(bundle, verdict, reviewer, comment)
    except (BundleFormatError, ValueError) as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)
    console.print(f"recorded [bold]{escape(verdict)}[/bold] review by {escape(reviewer)} on {path}")


@app.command()
def annotate(
    bundle: Path = typer.Argument(..., help="Bundle file to annotate."),
    target: str = typer.Option(
        ..., "--target", help="target_type:target_id, e.g. evidence:ev-abc123."
    ),
    author: str = typer.Option(..., "--author", help="Who is annotating."),
    text: str = typer.Option(..., "--text", help="The annotation text."),
) -> None:
    """Pin an immutable annotation to an existing object in the investigation."""
    from veritriage.collab import BundleFormatError

    if ":" not in target:
        _err.print("[red]error:[/red] --target must be 'target_type:target_id'")
        raise typer.Exit(code=2)
    target_type, target_id = target.split(":", 1)
    services = WorkspaceServices()
    try:
        path = services.annotate_bundle(bundle, target_type, target_id, author, text)
    except (BundleFormatError, ValueError) as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)
    console.print(f"annotated [bold]{escape(target)}[/bold] by {escape(author)} on {path}")


def _gather_context(root: Path):
    """Collect engineering context from every available provider, best-effort.

    Returns None when nothing contributed so the pipeline's report keeps its
    ``engineering`` field absent instead of empty.
    """
    from veritriage.engineering import collect_context

    gathered = collect_context(root)
    return None if gathered.is_empty else gathered


@app.command()
def context(
    root: Path = typer.Option(Path("."), "--root", help="Directory the providers inspect."),
    commits: int = typer.Option(10, "--commits", "-n", help="How many recent commits to gather."),
) -> None:
    """Show the normalized engineering context the providers see for a root."""
    from veritriage.engineering import available_providers, collect_context

    table = Table(title="Context providers")
    for column in ("Provider", "Source", "Available here", "Capabilities"):
        table.add_column(column)
    for name, cls in sorted(available_providers().items()):
        table.add_row(
            name,
            cls.source,
            "yes" if cls.available(root) else "no",
            ", ".join(sorted(c.value for c in cls.capabilities)) or "-",
        )
    console.print(table)

    gathered = collect_context(root, max_commits=commits)
    if gathered.is_empty:
        console.print("[dim]no engineering context available at this root[/dim]")
        return
    changes = Table(title=f"Recent changes ({', '.join(gathered.sources)})")
    for column in ("Revision", "Author", "When", "Title", "Files"):
        changes.add_column(column)
    for commit in gathered.commits:
        changes.add_row(
            commit.revision[:10],
            commit.author or "-",
            commit.timestamp.strftime("%Y-%m-%d %H:%M") if commit.timestamp else "-",
            commit.title,
            str(len(commit.files)),
        )
    console.print(changes)
    if gathered.ci_run is not None:
        ci = gathered.ci_run
        drift = "; ".join(ci.environment_changes) or "none declared"
        console.print(
            f"CI: [bold]{ci.pipeline or 'unknown'}[/bold]"
            + (f" #{ci.build_number}" if ci.build_number else "")
            + f"  |  environment drift: {escape(drift)}"
        )
    for entry in gathered.ownership:
        console.print(f"[dim]owner:[/dim] {escape(entry.scope)} -> {escape(entry.owner)} ({entry.role})")


@app.command()
def project(
    root: Path = typer.Argument(
        Path("."), help="Project root (or a *.vproj.json file) to understand."
    ),
) -> None:
    """Build and print the project model: what this verification project is."""
    from veritriage.project import available_project_providers

    providers_table = Table(title="Project providers")
    for column in ("Provider", "Source", "Available here", "Capabilities"):
        providers_table.add_column(column)
    for name, cls in sorted(available_project_providers().items()):
        providers_table.add_row(
            name,
            cls.source,
            "yes" if cls.available(root) else "no",
            ", ".join(sorted(c.value for c in cls.capabilities)) or "-",
        )
    console.print(providers_table)

    services = WorkspaceServices()
    model = services.build_project_model(root)
    if model.is_empty:
        console.print("[dim]no project model available at this root[/dim]")
        return
    summary = services.project_summary(model)
    console.print(
        f"\n[bold]{escape(summary.dut_top or 'project')}[/bold]  "
        f"[dim]{summary.project_id}[/dim]"
        + (f"  |  simulator {summary.simulator}" if summary.simulator else "")
    )
    console.print(
        f"{summary.module_count} modules  |  {summary.interface_count} interfaces  |  "
        f"{summary.uvm_component_count} UVM components  |  "
        f"{summary.lifecycle_phase_count} lifecycle phases"
    )
    if summary.identified_protocols:
        console.print(f"protocols: {', '.join(summary.identified_protocols)}")

    interfaces = Table(title="Interfaces")
    for column in ("Interface", "Protocol", "Signals"):
        interfaces.add_column(column)
    for iface in model.dut.interfaces:
        interfaces.add_row(iface.name, iface.protocol_id or "-", str(len(iface.signals)))
    console.print(interfaces)

    topo = Table(title="UVM topology")
    for column in ("Component", "Type", "Parent", "Interface"):
        topo.add_column(column)
    for component in model.env.components:
        topo.add_row(component.name, component.type, component.parent or "-", component.interface or "-")
    console.print(topo)


@app.command()
def explain(
    log: Path = typer.Argument(..., help="A log to classify by origin and lifecycle phase."),
    root: Path = typer.Option(
        Path("."), "--root", help="Project root for the model used to classify."
    ),
) -> None:
    """Log intelligence: classify each log line by origin and lifecycle phase."""
    services = WorkspaceServices()
    model = services.load_project_model(root) or services.build_project_model(root)
    model = model if not model.is_empty else None
    try:
        annotations = services.explain_log(log, model)
    except (FileNotFoundError, ValueError) as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)
    table = Table(title=f"Log intelligence: {log.name}")
    for column in ("Line", "Origin", "Phase", "Message"):
        table.add_column(column)
    for ann in annotations:
        table.add_row(
            str(ann.line_number or "-"),
            ann.origin,
            ann.phase or "-",
            escape((ann.snippet or "")[:80]),
        )
    console.print(table)


def _load_project_model(root: Path):
    """Build (or load) a project model, or exit cleanly when none is available."""
    services = WorkspaceServices()
    model = services.load_project_model(root) or services.build_project_model(root)
    if model.is_empty:
        console.print("[dim]no project model available at this root[/dim]")
        raise typer.Exit(code=0)
    return model


@app.command()
def dut(
    root: Path = typer.Argument(Path("."), help="Project root (or *.vproj.json) to inspect."),
) -> None:
    """Focused view of the DUT: modules, interfaces, clocks, resets, address map."""
    model = _load_project_model(root)
    console.print(f"[bold]{escape(model.dut.top or 'DUT')}[/bold]")
    ifaces = Table(title="Interfaces")
    for column in ("Interface", "Protocol", "Signals"):
        ifaces.add_column(column)
    for iface in model.dut.interfaces:
        ifaces.add_row(iface.name, iface.protocol_id or "-", ", ".join(iface.signals) or "-")
    console.print(ifaces)
    domains = Table(title="Clock / reset domains")
    for column in ("Kind", "Name", "Roots"):
        domains.add_column(column)
    for clock in model.dut.clocks:
        domains.add_row("clock", clock.name, ", ".join(clock.roots) or "-")
    for reset in model.dut.resets:
        domains.add_row("reset", reset.name, ", ".join(reset.roots) or "-")
    console.print(domains)
    if model.dut.address_map:
        amap = Table(title="Address map")
        for column in ("Region", "Base", "Size", "Target IP"):
            amap.add_column(column)
        for region in model.dut.address_map:
            amap.add_row(region.name, region.base or "-", region.size or "-", region.target_ip or "-")
        console.print(amap)


@app.command()
def env(
    root: Path = typer.Argument(Path("."), help="Project root (or *.vproj.json) to inspect."),
) -> None:
    """Focused view of the verification environment: UVM topology, RAL, VIPs."""
    model = _load_project_model(root)
    topo = Table(title="UVM topology")
    for column in ("Component", "Type", "Parent", "Interface"):
        topo.add_column(column)
    for component in model.env.components:
        topo.add_row(component.name, component.type, component.parent or "-", component.interface or "-")
    console.print(topo)
    if model.env.ral:
        console.print(f"RAL: [bold]{escape(model.env.ral)}[/bold]")
    for vip in model.env.vips:
        console.print(
            f"[dim]VIP:[/dim] {escape(vip.name)}"
            + (f" ({vip.protocol_id})" if vip.protocol_id else "")
            + (f" on {vip.interface}" if vip.interface else "")
        )


@app.command()
def flow(
    root: Path = typer.Argument(Path("."), help="Project root (or *.vproj.json) to inspect."),
) -> None:
    """Focused view of the simulation flow: simulator, lifecycle, artifacts."""
    model = _load_project_model(root)
    sim = model.sim_infra
    console.print(
        "[bold]Simulator:[/bold] "
        + (f"{sim.simulator_vendor}" if sim.simulator_vendor else "unknown")
        + (f" {sim.simulator_version}" if sim.simulator_version else "")
        + (f"  |  waveforms: {', '.join(sim.waveform_formats)}" if sim.waveform_formats else "")
    )
    if model.lifecycle.phases:
        console.print(
            "[bold]Expected lifecycle:[/bold] "
            + " -> ".join(p.name for p in model.lifecycle.phases)
        )
    if sim.log_sources:
        sources = Table(title="Log sources")
        for column in ("Pattern", "Origin"):
            sources.add_column(column)
        for source in sim.log_sources:
            sources.add_row(source.pattern, source.origin)
        console.print(sources)


@app.command()
def investigate(
    artifacts: List[Path] = typer.Argument(..., help="Artifacts to analyze with full context."),
    context_root: Path = typer.Option(
        Path("."), "--context-root", help="Directory the context providers inspect."
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Also write analysis.json / report.html here."
    ),
) -> None:
    """Analyze with engineering context and print the investigation view."""
    engineering = _gather_context(context_root)
    services = WorkspaceServices()
    try:
        session = services.investigate(artifacts, engineering=engineering)
    except (FileNotFoundError, ValueError) as exc:
        _err.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2)
    report, graph = session.report, session.graph
    bundle = services.save(session)
    _print_summary(report)
    console.print(
        f"[dim]session[/dim] [bold]{session.session_id}[/bold] [dim]saved to[/dim] {bundle}"
    )

    view = report.engineering
    if view is None:
        console.print("[dim]no engineering context contributed to this run[/dim]")
    else:
        if view.timeline:
            timeline = Table(title="Engineering timeline")
            for column in ("Phase", "When", "Event", "Evidence"):
                timeline.add_column(column)
            for event in view.timeline:
                timeline.add_row(
                    event.phase, event.when or "-", event.label, event.node_id or "-"
                )
            console.print(timeline)
        if view.investigation is not None:
            layers = Table(title="Investigation view (Evidence Graph projection)")
            for column in ("Layer", "Nodes", "IDs"):
                layers.add_column(column)
            for layer in view.investigation.layers:
                layers.add_row(
                    layer.name, str(len(layer.node_ids)), ", ".join(layer.node_ids[:4])
                )
            console.print(layers)
            for edge in view.investigation.cross_edges[:8]:
                console.print(
                    f"[dim]{edge.source_id} -{edge.relation}-> {edge.target_id}:[/dim] "
                    f"{escape(edge.rationale)}"
                )

    if output_dir is not None:
        write_json(report, output_dir / "analysis.json")
        write_json(graph, output_dir / "evidence_graph.json")
        HtmlReportGenerator().write(report, output_dir / "report.html", graph=graph)
        console.print(f"\n[dim]wrote artifacts to[/dim] {output_dir}")

    if report.classification.category.value != "no_failure":
        raise typer.Exit(code=1)


@app.command()
def impact(
    context_root: Path = typer.Option(
        Path("."), "--context-root", help="Directory the context providers inspect."
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="How many impacted tests to show."),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database file."),
) -> None:
    """Rank tests likely affected by the current changes, from history."""
    from veritriage.engineering import HistoricalRegression, impacted_tests_from_history
    from veritriage.storage import RegressionStore

    engineering = _gather_context(context_root)
    if engineering is None or not engineering.changed_modules():
        console.print("[dim]no changed modules found at this root; nothing to rank[/dim]")
        return
    if not db.is_file():
        _err.print(f"[red]error:[/red] no regression database at {db}; run an analysis first")
        raise typer.Exit(code=2)

    with RegressionStore(db) as store:
        history_slices = [
            HistoricalRegression(
                regression_id=record.regression_id,
                test_name=record.test_name,
                failing_modules=tuple(
                    sorted(
                        {
                            token
                            for node in record.graph.failing()
                            for token in (
                                node.module or "",
                                str(node.attributes.get("source_file") or ""),
                            )
                            if token
                        }
                    )
                ),
                classification=record.classification,
                created_at=record.created_at,
            )
            for record in store.all_records()
            if record.is_failure
        ]

    ranked = impacted_tests_from_history(engineering, history_slices, limit=limit)
    if not ranked:
        console.print("[dim]no historical failures overlap the changed modules[/dim]")
        return
    table = Table(title=f"Likely impacted tests ({len(engineering.changed_modules())} changed modules)")
    for column in ("Test", "Score", "Why", "Regressions"):
        table.add_column(column)
    for entry in ranked:
        table.add_row(
            entry.test_name,
            f"{entry.score:.2f}",
            entry.reason,
            ", ".join(entry.regression_ids[:3]),
        )
    console.print(table)


@app.command()
def dashboard(
    output_dir: Path = typer.Option(
        Path("."), "--output-dir", "-o", help="Directory for dashboard.html."
    ),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database file."),
) -> None:
    """Render the regression-intelligence dashboard from the database."""
    from veritriage.dashboard import DashboardGenerator
    from veritriage.storage import RegressionStore

    if not db.is_file():
        _err.print(f"[red]error:[/red] no regression database at {db}; run an analysis first")
        raise typer.Exit(code=2)
    with RegressionStore(db) as store:
        path = DashboardGenerator(store).write(output_dir / "dashboard.html")
        console.print(f"[dim]wrote[/dim] {path}  ({store.count()} regressions)")


@app.command()
def history(
    limit: int = typer.Option(15, "--limit", "-n", help="How many regressions to show."),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database file."),
) -> None:
    """List the most recent regressions in the database."""
    from veritriage.storage import RegressionStore

    if not db.is_file():
        _err.print(f"[red]error:[/red] no regression database at {db}; run an analysis first")
        raise typer.Exit(code=2)
    with RegressionStore(db) as store:
        table = Table(title=f"Regression history ({store.count()} total)")
        for column in ("When", "Regression", "Test", "Classification", "Confidence", "Signature"):
            table.add_column(column)
        for record in store.recent(limit=limit):
            table.add_row(
                record.created_at.strftime("%Y-%m-%d %H:%M"),
                record.regression_id,
                record.test_name or "-",
                record.report.classification.category.display_name,
                f"{record.confidence}%",
                record.signature.digest,
            )
        console.print(table)


@app.command()
def feedback(
    regression_id: str = typer.Argument(..., help="Regression ID the feedback applies to."),
    diagnosis: Optional[str] = typer.Option(
        None, "--diagnosis", help="Was the diagnosis right? 'correct' or 'incorrect'."
    ),
    root_cause: Optional[str] = typer.Option(
        None, "--root-cause", help="The confirmed actual root cause."
    ),
    useful: List[str] = typer.Option(
        [], "--useful", help="A recommendation action that helped (repeatable)."
    ),
    false: List[str] = typer.Option(
        [], "--false", help="A recommendation action that wasted time (repeatable)."
    ),
    note: Optional[str] = typer.Option(None, "--note", help="Free-form notes."),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="Regression database file."),
) -> None:
    """Record engineer feedback on an analyzed regression."""
    from veritriage.feedback import FeedbackRecord
    from veritriage.storage import RegressionStore

    if diagnosis is not None and diagnosis not in ("correct", "incorrect"):
        _err.print("[red]error:[/red] --diagnosis must be 'correct' or 'incorrect'")
        raise typer.Exit(code=2)
    if not db.is_file():
        _err.print(f"[red]error:[/red] no regression database at {db}; run an analysis first")
        raise typer.Exit(code=2)
    with RegressionStore(db) as store:
        if store.get(regression_id) is None:
            _err.print(f"[red]error:[/red] unknown regression {escape(regression_id)}")
            raise typer.Exit(code=2)
        store.save_feedback(
            FeedbackRecord(
                regression_id=regression_id,
                diagnosis=diagnosis,  # type: ignore[arg-type]
                actual_root_cause=root_cause,
                useful_recommendations=list(useful),
                false_recommendations=list(false),
                notes=note,
            )
        )
        console.print(f"recorded feedback for [bold]{escape(regression_id)}[/bold]")


@app.command()
def version() -> None:
    """Print the VeriTriage version."""
    console.print(f"veritriage {veritriage.__version__}")


def _print_summary(report: AnalysisReport) -> None:
    """Render the terminal summary panel for an analysis."""
    c = report.classification
    counts = Table.grid(padding=(0, 2))
    counts.add_column(style="bold")
    counts.add_column()
    for label, severity in (
        ("Fatals", Severity.FATAL),
        ("Errors", Severity.ERROR),
        ("Warnings", Severity.WARNING),
    ):
        counts.add_row(label, str(report.summary.count(severity)))
    counts.add_row("Evidence nodes", str(report.graph_stats.node_count))
    counts.add_row("Evidence edges", str(report.graph_stats.edge_count))

    body = Table.grid(padding=(0, 1))
    body.add_column()
    body.add_row(f"[bold]{c.category.display_name}[/bold]  |  confidence {c.confidence}%")
    body.add_row(f"[dim]{escape(c.summary)}  (rule: {c.rule_name})[/dim]")
    body.add_row("")
    body.add_row(counts)
    if c.evidence:
        body.add_row("")
        body.add_row("[bold]Evidence[/bold]")
        for ev in c.evidence:
            where = f"line {ev.line_number}" if ev.line_number else ""
            when = f"t={ev.sim_time}" if ev.sim_time else ""
            node = ev.node_id or ""
            loc = " ".join(x for x in (when, where, node) if x)
            body.add_row(f"  • {escape(ev.description)}" + (f"  [dim]({loc})[/dim]" if loc else ""))
    if report.knowledge is not None and report.knowledge.patterns:
        body.add_row("")
        body.add_row("[bold]Known patterns[/bold]")
        for pattern in report.knowledge.patterns[:3]:
            body.add_row(
                f"  • {escape(pattern.name)}  [dim]{pattern.score:.0%} match "
                f"({pattern.pack} pack, owns: {escape(pattern.ownership)})[/dim]"
            )
        if report.knowledge.state_projection and report.knowledge.state_projection.stopped_at:
            sp = report.knowledge.state_projection
            reached = " -> ".join(s.state for s in sp.states if s.reached)
            body.add_row(
                f"  [dim]{escape(sp.name)}: {escape(reached)} -> "
                f"stopped before {escape(sp.stopped_at)}[/dim]"
            )
    if report.history is not None:
        body.add_row("")
        h = report.history
        if h.seen_before:
            best = next((s for s in h.similar if s.signature_match), None)
            seen = f"[bold]Seen before:[/bold] yes, {h.times_seen} prior run{'s' if h.times_seen != 1 else ''} with this exact signature"
            body.add_row(seen)
            if best is not None:
                body.add_row(
                    f"  [dim]last: {best.regression_id} · {escape(best.root_cause)}[/dim]"
                )
        elif h.similar:
            top = h.similar[0]
            body.add_row(
                f"[bold]Seen before:[/bold] not exactly; closest is {top.regression_id} "
                f"[dim]({top.score:.0%} similar, {escape(top.root_cause)})[/dim]"
            )
        elif report.classification.category.value != "no_failure":
            body.add_row("[bold]Seen before:[/bold] no, this failure is new to the database")
    if report.reasoning is not None and report.reasoning.hypotheses:
        body.add_row("")
        body.add_row("[bold]Hypotheses[/bold]")
        for hypothesis in report.reasoning.hypotheses:
            pct = f"{hypothesis.confidence * 100:.0f}%"
            body.add_row(
                f"  • {escape(hypothesis.title)}  [dim]{pct} "
                f"({len(hypothesis.evidence_ids)} evidence nodes)[/dim]"
            )
    if report.agents is not None and report.agents.findings:
        a = report.agents
        body.add_row("")
        body.add_row(
            f"[bold]Agent findings[/bold]  [dim]({len(a.agents_invoked)} specialists "
            f"consulted)[/dim]"
        )
        for finding in a.findings[:3]:
            body.add_row(
                f"  • {escape(finding.category.display_name)}  "
                f"[dim]{finding.confidence * 100:.0f}% · {finding.consensus.value} · "
                f"{', '.join(finding.supporting_agents)}[/dim]"
            )
        if a.conflicts:
            body.add_row(
                f"  [dim]{len(a.conflicts)} conflicting position"
                f"{'s' if len(a.conflicts) != 1 else ''} between specialists[/dim]"
            )
        if a.agrees_with_reasoning is False:
            body.add_row(
                "  [yellow]specialists disagree with the deterministic ranking[/yellow]"
            )
    if report.plan is not None and report.plan.steps:
        pl = report.plan
        body.add_row("")
        body.add_row(
            f"[bold]Investigation plan[/bold]  [dim](effort {pl.estimated_effort}, "
            f"{len(pl.all_steps())} steps)[/dim]"
        )
        body.add_row(f"  [dim]{escape(pl.objective)}[/dim]")
        for step in pl.steps[:3]:
            body.add_row(
                f"  • {escape(step.action)}  [dim]{step.kind.value} · "
                f"value/effort {step.valuation.priority_score:.2f}[/dim]"
            )
        top = pl.steps[0].decision if pl.steps else None
        if top is not None:
            body.add_row(f"  [dim]then branches on: {escape(top.question)}[/dim]")
        if pl.evidence_requests:
            body.add_row(
                f"  [dim]evidence still needed: "
                f"{len(pl.evidence_requests)} item(s)[/dim]"
            )
    steps = (
        report.reasoning.recommendations
        if report.reasoning is not None and report.reasoning.recommendations
        else None
    )
    if steps:
        body.add_row("")
        body.add_row("[bold]Next steps[/bold]")
        for rec in sorted(steps, key=lambda r: r.priority)[:4]:
            module = f" [{rec.module}]" if rec.module else ""
            body.add_row(
                f"  {rec.priority}. {escape(rec.action)}"
                f"  [dim](effort {rec.effort}{escape(module)})[/dim]"
            )
    elif c.recommendations:
        body.add_row("")
        body.add_row("[bold]Next steps[/bold]")
        for i, rec in enumerate(sorted(c.recommendations, key=lambda r: r.priority), start=1):
            body.add_row(f"  {i}. {escape(rec.action)}")

    title = report.summary.test_name or Path(report.input_files[0]).name
    console.print(Panel(body, title=f"VeriTriage · {title}", border_style="blue"))


if __name__ == "__main__":
    app()

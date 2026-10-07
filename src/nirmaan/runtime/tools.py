"""The tool broker: capability-checked, honestly executed, always recorded.

A tool runs only if the role is granted it, the tool is AVAILABLE, a binding
exists, and the binding's probe (if any) finds it can run on this machine (an
EDA executable on PATH). Otherwise the broker refuses, and says why: a CONTRACT_ONLY
tool (a simulator, synthesis, STA) is never "run" here, so no agent can ever
produce evidence that one was. Every executed invocation becomes a
:class:`ToolRun` in project state through the task engine, which is the only
thing a TOOL_RUN or VERITRIAGE_SESSION evidence record may cite.

A call is also held to the tool's parameter contract (M28): an undeclared or
ill-typed parameter is refused before anything runs. A list of paths may be
passed as a list; it is stored comma-joined, as it always has been, so a path
containing a comma is refused rather than silently read as two.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from nirmaan.models import Actor, ParamKind, ToolRun, ToolSpec, ToolStatus
from nirmaan.org import AuthorityService
from nirmaan.work.engine import TaskEngine


@dataclass(frozen=True)
class ToolOutcome:
    succeeded: bool
    summary: str
    references: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)


Binding = Callable[[dict[str, str], TaskEngine], ToolOutcome]
#: Asked before every invocation: None when the binding can run here, else why not.
Probe = Callable[[dict[str, str]], str | None]
_BINDINGS: dict[str, Binding] = {}
_PROBES: dict[str, Probe] = {}


def register_binding(tool_id: str, probe: Probe | None = None) -> Callable[[Binding], Binding]:
    """Decorator: the real implementation behind an AVAILABLE tool.

    ``probe`` decides availability at run time (an EDA binding whose executable
    is not on PATH): when it returns a reason, the broker refuses and says why.
    """

    def _register(fn: Binding) -> Binding:
        if tool_id in _BINDINGS and _BINDINGS[tool_id] is not fn:
            raise ValueError(f"Tool binding {tool_id!r} is already registered")
        _BINDINGS[tool_id] = fn
        if probe is not None:
            _PROBES[tool_id] = probe
        return fn

    return _register


def unregister_binding(tool_id: str) -> None:
    _BINDINGS.pop(tool_id, None)
    _PROBES.pop(tool_id, None)


def available_bindings() -> list[str]:
    _ensure_builtin_bindings()
    return sorted(_BINDINGS)


def unavailable_reason(tool_id: str, params: dict[str, str] | None = None) -> str | None:
    """Why this machine cannot run a bound tool now (the probe the broker asks), or None."""
    _ensure_builtin_bindings()
    probe = _PROBES.get(tool_id)
    return probe(params or {}) if probe else None


class ToolAccessDenied(PermissionError):
    pass


class ToolContractError(ToolAccessDenied):
    """A call outside the tool's parameter contract. Refused; nothing ran."""


ParamValue = str | Sequence[str]


def check_params(spec: ToolSpec, params: dict[str, ParamValue]) -> dict[str, str]:
    """The call's parameters as stored (lists comma-joined), or ToolContractError saying what is wrong.

    A tool with no declared contract (``params`` None) takes any parameter; lists are still joined.
    """
    checked: dict[str, str] = {}
    problems: list[str] = []
    for name, raw in params.items():
        items = [str(v) for v in raw] if isinstance(raw, (list, tuple)) else None
        param = spec.param(name)
        if spec.params is not None and param is None:
            declared = ", ".join(p.label for p in spec.params) or "no parameters"
            problems.append(f"{spec.id} does not take {name!r} (it takes {declared})")
            continue
        kind = param.kind if param else None
        if items is not None:
            if kind is not None and kind is not ParamKind.PATHS and len(items) > 1:
                problems.append(f"{name} takes one {'path' if kind is ParamKind.PATH else 'value'}, not a list")
                continue
            commas = [v for v in items if "," in v]
            if commas:
                problems.append(f"{name}: {', '.join(repr(v) for v in commas)} contains a comma, "
                                "so it cannot be told apart from two paths")
                continue
            value = ",".join(items)
        else:
            value = str(raw)
        if kind is ParamKind.INTEGER and value.strip() and not value.strip().lstrip("-").isdigit():
            problems.append(f"{name} must be a whole number, not {value!r}")
            continue
        if kind is ParamKind.NUMBER and value.strip():
            try:
                float(value)
            except ValueError:
                problems.append(f"{name} must be a number, not {value!r}")
                continue
        checked[name] = value
    if problems:
        raise ToolContractError(f"{spec.id} refused before running: {'; '.join(problems)}")
    return checked


def declared_inputs(spec: ToolSpec, inputs: dict[str, str]) -> dict[str, str]:
    """The task inputs this tool's contract declares (all of them for a tool with no contract)."""
    return dict(inputs) if spec.params is None else {k: v for k, v in inputs.items() if spec.param(k)}


class ToolBroker:
    def __init__(self, engine: TaskEngine) -> None:
        self._engine = engine
        self._authority = AuthorityService(engine.org)
        _ensure_builtin_bindings()

    def declared_inputs(self, tool_id: str, inputs: dict[str, str]) -> dict[str, str]:
        tool = self._engine.org.tools.get(tool_id)
        return dict(inputs) if tool is None else declared_inputs(tool, inputs)

    def invoke(self, actor: Actor, tool_id: str, params: dict[str, ParamValue] | None = None,
               task_id: str | None = None) -> tuple[ToolRun, ToolOutcome]:
        allowed, why = self._authority.may_use_tool(actor.role, tool_id)
        if not allowed:
            raise ToolAccessDenied(why)
        binding = _BINDINGS.get(tool_id)
        tool = self._engine.org.tools[tool_id]
        if binding is None or tool.status is not ToolStatus.AVAILABLE:
            raise ToolAccessDenied(f"{tool_id} has no implementation in this installation")
        params = check_params(tool, params or {})
        probe = _PROBES.get(tool_id)
        unavailable = probe(params) if probe else None
        if unavailable:
            raise ToolAccessDenied(unavailable)
        try:
            outcome = binding(params, self._engine)
        except Exception as exc:  # a failing tool is a recorded, failed run
            outcome = ToolOutcome(succeeded=False, summary=f"{type(exc).__name__}: {exc}")
        run = ToolRun(
            id=f"run-{len(self._engine.state.tool_runs) + 1:04d}",
            tool=tool_id,
            actor=actor.label,
            task=task_id,
            params=params,
            succeeded=outcome.succeeded,
            summary=outcome.summary,
            references=outcome.references,
        )
        self._engine.record_tool_run(run, actor)
        return run, outcome


# --- Platform bindings: Nirmaan's own read tools --------------------------------------


@register_binding("status.read")
def _status(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    from nirmaan.work.management import status_report

    report = status_report(engine.org, engine.state)
    return ToolOutcome(True, f"{report.tasks} tasks, {report.progress:.0%} complete",
                       data=report.to_dict())


@register_binding("project.read")
def _project(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    task_id = params.get("task")
    if task_id:
        task = engine.task(task_id)
        return ToolOutcome(True, f"{task.title} [{task.status.value}]", data=task.model_dump(mode="json"))
    return ToolOutcome(True, engine.state.project.name, data=engine.state.project.model_dump(mode="json"))


@register_binding("artifact.read")
def _artifact(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    art = engine.state.artifacts.get(params.get("artifact", ""))
    if art is None:
        return ToolOutcome(False, f"no artifact {params.get('artifact')!r}")
    return ToolOutcome(True, f"{art.title} ({art.assurance.value})", (art.id,), art.model_dump(mode="json"))


@register_binding("trace.read")
def _trace(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    from nirmaan.work.trace import trace_graph

    graph = trace_graph(engine.state)
    return ToolOutcome(True, f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges", data=graph)


def _ensure_builtin_bindings() -> None:
    """Import every integration module (the VeriTriage bridge, the tool backends) so they register (lazily)."""
    import importlib
    import pkgutil

    from nirmaan import integrations

    for module in pkgutil.iter_modules(integrations.__path__):
        importlib.import_module(f"{integrations.__name__}.{module.name}")

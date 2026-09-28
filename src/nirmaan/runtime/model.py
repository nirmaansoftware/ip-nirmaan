"""Model-backed runtimes (M20): a language model in a seat, checked rather than trusted.

:class:`ModelRuntime` is one class for every seat. Its behaviour comes from the
work packet, never from a role, skill, or stage name:

* before the model is asked, it runs the tools the task's evidence
  requirements name (when the seat is granted them), with parameters from the
  task's ``input.*`` memory entries, so the model can cite real runs;
* it renders the packet's four scopes into a :class:`WorkPrompt` and asks an
  :class:`LLM`;
* it strips every citation the prompt did not declare (M17 grounding, through
  the bridge), drops artifacts left with no citation, and passes the tool runs
  the model says it relied on to the engine unfiltered, where P5 judges them.

Two LLMs ship. :class:`RegistryLLM` reaches any provider in the one M17
registry through the bridge. :class:`MockLLM` is deterministic and scriptable,
so no test ever calls an API. The model-backed seats are off by default:
``unbound`` stays the default runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from nirmaan.models import EscalationKind, EvidenceKind, Verdict
from nirmaan.runtime.base import (
    EscalationRequest,
    ResultStatus,
    ReviewResult,
    ToolHandle,
    WorkResult,
    register_runtime,
)
from nirmaan.runtime.context import WorkPacket
from nirmaan.runtime.prompt import ToolNote, WorkPrompt, render_work_prompt
from nirmaan.runtime.tools import ToolAccessDenied

_TOOL_BACKED = {EvidenceKind.TOOL_RUN.value, EvidenceKind.VERITRIAGE_SESSION.value}
_VERDICTS = {"approve": Verdict.APPROVE, "request_changes": Verdict.REQUEST_CHANGES}


@dataclass(frozen=True)
class Completion:
    """What a model returned: text, or the reason it returned nothing usable."""

    text: str
    model: str | None = None
    error: str | None = None


class LLM(Protocol):
    name: str

    def complete(self, prompt: WorkPrompt) -> Completion: ...


class RegistryLLM:
    """Any provider registered with ``@register_llm_provider``, reached through the bridge."""

    def __init__(self, provider: str) -> None:
        self.name = provider

    def complete(self, prompt: WorkPrompt) -> Completion:
        from nirmaan.integrations.veritriage import generate

        result = generate(self.name, prompt)
        return Completion(result.text, result.model, result.error)


class MockLLM:
    """A deterministic stand-in for a model. Scriptable; never touches a network.

    With no script it answers from the prompt alone: it cites the prompt's own
    tokens, chooses the first declared outcome, and approves a review only when
    it has evidence to cite. Scripted replies (text or a :class:`Completion`)
    are returned in order, which is how tests play a hostile or broken model.
    """

    name = "mock-llm"

    def __init__(self, script: Sequence[str | Completion] = ()) -> None:
        self._script = list(script)
        self.calls: list[WorkPrompt] = []

    def complete(self, prompt: WorkPrompt) -> Completion:
        self.calls.append(prompt)
        if self._script:
            reply = self._script.pop(0)
            return reply if isinstance(reply, Completion) else Completion(reply, self.name)
        runs = [c for c in prompt.citations if c.kind == "run"]
        tokens = [c.token for c in (*runs, *(c for c in prompt.citations if c.kind != "run"))][:2]
        if prompt.mode == "review":
            if not tokens:
                return Completion(json.dumps({"verdict": "request_changes", "comments": "No evidence to judge.",
                                              "uncertainty": 0.9}), self.name)
            return Completion(json.dumps({"verdict": "approve", "uncertainty": 0.1,
                                          "comments": f"The conclusion follows from {' and '.join(tokens)}."}),
                              self.name)
        if not tokens:
            return Completion(json.dumps({"uncertainty": 0.9, "artifacts": [], "escalation": {
                "reason": "there is no evidence to cite", "question": "Which artifacts should this task examine?"}}),
                self.name)
        artifacts = [{"kind": out, "title": f"{out.replace('_', ' ').capitalize()} (mock)",
                      "summary": f"Deterministic {out.replace('_', ' ')} grounded in {' and '.join(tokens)}."}
                     for out in (prompt.outputs or ("note",))]
        return Completion(json.dumps({
            "uncertainty": 0.2, "artifacts": artifacts, "tool_runs": [c.target for c in runs],
            "outcome": prompt.outcomes[0] if prompt.outcomes else None, "claims": [], "escalation": None,
            "notes": "deterministic mock answer",
        }), self.name)


def _parse(text: str) -> dict[str, Any] | None:
    """The model's JSON object, tolerating prose or a code fence around it."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _uncertainty(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class ModelRuntime:
    """A language model filling a seat. Registered as ``mock-llm`` and ``anthropic``."""

    def __init__(self, llm: LLM, runtime_id: str | None = None) -> None:
        self.llm = llm
        self.runtime_id = runtime_id or llm.name

    def accepts(self, packet: WorkPacket) -> bool:
        return True

    # --- Work --------------------------------------------------------------------------

    def execute(self, packet: WorkPacket, tools: ToolHandle) -> WorkResult:
        notes = self._preflight(packet, tools)
        runs = tuple(n.run for n in notes if n.run)
        prompt = render_work_prompt(packet, "work", notes)
        data, problem = self._ask(prompt)
        if data is None:
            return WorkResult(ResultStatus.DECLINED, uncertainty=1.0, tool_runs=runs, notes=problem)
        return self._result(data, prompt, runs, notes)

    def _preflight(self, packet: WorkPacket, tools: ToolHandle) -> tuple[ToolNote, ...]:
        """Run the tools the task's evidence requirements name, as the seat, before asking."""
        params = {
            m["key"].removeprefix("input."): m["value"] for m in packet.memory
            if m["scope"] == "task" and m["owner"] == packet.task_id and m["key"].startswith("input.")
        }
        wanted = dict.fromkeys(
            tool for req in packet.task["evidence_requirements"]
            if _TOOL_BACKED & set(req["accepts"]) for tool in req["tools"]
        )
        notes = []
        for tool in wanted:
            try:
                run_id, outcome = tools.invoke(tool, **params)
            except ToolAccessDenied as exc:
                notes.append(ToolNote(tool, None, False, str(exc)))
            else:
                notes.append(ToolNote(tool, run_id, outcome.succeeded, outcome.summary))
        return tuple(notes)

    def _result(self, data: dict[str, Any], prompt: WorkPrompt, runs: tuple[str, ...],
                notes: tuple[ToolNote, ...]) -> WorkResult:
        from nirmaan.integrations.veritriage import ground

        kept, dropped, stripped = [], [], []
        for art in data.get("artifacts") or []:
            if not isinstance(art, dict):
                continue
            summary, used, removed = ground(str(art.get("summary", "")), prompt)
            stripped += [t for t in removed if t not in stripped]
            if not used:
                dropped.append(str(art.get("title") or art.get("kind") or "untitled"))
                continue
            kept.append({"kind": str(art.get("kind", "")), "title": str(art.get("title", "")), "summary": summary})
        # Declared runs go to the engine unfiltered: a run that never happened is P5's to refuse.
        tool_runs = tuple(dict.fromkeys([*runs, *(str(r) for r in data.get("tool_runs") or [])]))
        remarks = [str(data.get("notes") or "")]
        if stripped:
            remarks.append(f"stripped undeclared citations: {', '.join(stripped)}")
        if dropped:
            remarks.append(f"dropped uncited artifacts: {', '.join(dropped)}")
        remarks += [f"{n.tool} not run: {n.summary}" for n in notes if n.run is None]
        common = dict(uncertainty=_uncertainty(data.get("uncertainty")), tool_runs=tool_runs,
                      claims=tuple(str(c) for c in data.get("claims") or []),
                      notes="; ".join(r for r in remarks if r))
        escalation = data.get("escalation")
        if isinstance(escalation, dict) and escalation:
            return WorkResult(ResultStatus.NEEDS_ESCALATION, escalation=EscalationRequest(
                EscalationKind.UNCERTAINTY, str(escalation.get("reason", "the agent could not conclude")),
                str(escalation.get("question", "How should this task proceed?")),
                attempted_actions=tuple(f"ran {n.tool}" for n in notes if n.run),
                recommended_options=tuple(str(o) for o in escalation.get("options") or ()),
            ), **common)
        outcome = data.get("outcome") if prompt.outcomes else None
        return WorkResult(ResultStatus.SUBMITTED, artifacts=tuple(kept),
                          outcome=str(outcome) if outcome is not None else None, **common)

    # --- Review ------------------------------------------------------------------------

    def review(self, packet: WorkPacket) -> ReviewResult:
        from nirmaan.integrations.veritriage import ground

        prompt = render_work_prompt(packet, "review")
        data, problem = self._ask(prompt)
        if data is None:
            return ReviewResult(None, uncertainty=1.0, notes=problem)
        verdict = _VERDICTS.get(str(data.get("verdict")))
        comments, used, stripped = ground(str(data.get("comments", "")), prompt)
        uncertainty = _uncertainty(data.get("uncertainty"))
        if verdict is None:
            return ReviewResult(None, uncertainty=1.0, notes=f"no verdict in the review: {data.get('verdict')!r}")
        if not used:
            return ReviewResult(None, uncertainty=1.0, notes="the review cited no evidence, so it is not recorded")
        notes = f"stripped undeclared citations: {', '.join(stripped)}" if stripped else ""
        return ReviewResult(verdict, comments, uncertainty, notes)

    def _ask(self, prompt: WorkPrompt) -> tuple[dict[str, Any] | None, str]:
        completion = self.llm.complete(prompt)
        if completion.error:
            return None, f"the model call failed: {completion.error}"
        data = _parse(completion.text)
        if data is None:
            return None, "the model's answer was not a JSON object; nothing was recorded"
        return data, ""


register_runtime("mock-llm")(lambda: ModelRuntime(MockLLM(), runtime_id="mock-llm"))
register_runtime("anthropic")(lambda: ModelRuntime(RegistryLLM("anthropic"), runtime_id="anthropic"))

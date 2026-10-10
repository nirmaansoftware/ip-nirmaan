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
  the model says it relied on to the engine unfiltered, where P5 judges them;
* files in the answer (M23) are written with a digest, and the tools of any
  evidence requirement over the task's own files run on them afterwards (with
  any approved upstream file the requirement names, M25). When such a check
  must pass before review and cannot run here, the work is blocked.

Two LLMs ship. :class:`RegistryLLM` reaches any provider in the one M17
registry through the bridge. :class:`MockLLM` is deterministic and scriptable,
so no test ever calls an API. The model-backed seats are off by default:
``unbound`` stays the default runtime.
"""

from __future__ import annotations

import dataclasses
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

from nirmaan.models import EscalationKind, EvidenceKind, EvidenceRequirement, MemoryScope, Verdict
from nirmaan.runtime.base import (
    EscalationRequest,
    ResultStatus,
    ReviewResult,
    ToolHandle,
    WorkResult,
    register_runtime,
)
from nirmaan.runtime.context import WorkPacket
from nirmaan.runtime.files import read_verified, split_files, write_file
from nirmaan.runtime.prompt import ToolNote, WorkPrompt, render_work_prompt
from nirmaan.runtime.tools import ToolAccessDenied
from nirmaan.runtime.writer import outside_writer

_TOOL_BACKED = {EvidenceKind.TOOL_RUN, EvidenceKind.VERITRIAGE_SESSION}
_VERDICTS = {"approve": Verdict.APPROVE, "request_changes": Verdict.REQUEST_CHANGES}


#: A Completion error starting with this means no model was called (e.g. no model fits): nothing to count.
NO_CALL = "no model was called: "


def call_record(completion: "Completion", purpose: str, llm_name: str) -> dict[str, Any]:
    """One model call as the runtime saw it, for the engine to record (M31)."""
    return {"purpose": purpose, "provider": completion.provider or llm_name, "model": completion.model,
            "input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens,
            "cache_read_tokens": completion.cache_read_tokens, "cache_write_tokens": completion.cache_write_tokens,
            "succeeded": completion.error is None, "error": completion.error, "priced": completion.priced}


@dataclass(frozen=True)
class Completion:
    """What a model returned: text, or the reason it returned nothing usable."""

    text: str
    model: str | None = None
    error: str | None = None
    #: Who served the call and the usage it reported (M31); None means not reported.
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    #: False when the call has no per-call price (a subscription seat): its cost is recorded as unknown.
    priced: bool = True


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
        return Completion(result.text, result.model, result.error, result.provider, result.input_tokens,
                          result.output_tokens, result.cache_read_tokens, result.cache_write_tokens)


class MockLLM:
    """A deterministic stand-in for a model. Scriptable; never touches a network.

    With no script it answers from the prompt alone: it cites the prompt's own
    tokens, chooses the first declared outcome, and approves a review only when
    it has evidence to cite. Scripted replies (text or a :class:`Completion`)
    are returned in order, which is how tests play a hostile or broken model.
    """

    name = "mock-llm"

    def __init__(self, script: Sequence[str | Completion] = (), model: str | None = None) -> None:
        self._script = list(script)
        self._model = model or self.name  # the model it reports, e.g. a profile's when ``auto`` seats it (M31)
        self.calls: list[WorkPrompt] = []

    def complete(self, prompt: WorkPrompt) -> Completion:
        self.calls.append(prompt)
        if self._script:
            reply = self._script.pop(0)
            return reply if isinstance(reply, Completion) else Completion(reply, self._model)
        runs = [c for c in prompt.citations if c.kind == "run"]
        tokens = [c.token for c in (*runs, *(c for c in prompt.citations if c.kind != "run"))][:2]
        if prompt.mode == "review":
            if not tokens:
                return Completion(json.dumps({"verdict": "request_changes", "comments": "No evidence to judge.",
                                              "uncertainty": 0.9}), self._model)
            return Completion(json.dumps({"verdict": "approve", "uncertainty": 0.1,
                                          "comments": f"The conclusion follows from {' and '.join(tokens)}."}),
                              self._model)
        if not tokens:
            return Completion(json.dumps({"uncertainty": 0.9, "artifacts": [], "escalation": {
                "reason": "there is no evidence to cite", "question": "Which artifacts should this task examine?"}}),
                self._model)
        artifacts = [{"kind": out, "title": f"{out.replace('_', ' ').capitalize()} (mock)",
                      "summary": f"Deterministic {out.replace('_', ' ')} grounded in {' and '.join(tokens)}."}
                     for out in (prompt.outputs or ("note",))]
        return Completion(json.dumps({
            "uncertainty": 0.2, "artifacts": artifacts, "tool_runs": [c.target for c in runs],
            "outcome": prompt.outcomes[0] if prompt.outcomes else None, "claims": [], "escalation": None,
            "notes": "deterministic mock answer",
        }), self._model)


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


#: The file blocks of an answer, by path, and the blocks that were rejected.
_Files = tuple[dict[str, str], list[str]]
_ID_UNSAFE = re.compile(r"[^A-Za-z0-9._\-]")


def _inputs(packet: WorkPacket) -> dict[str, str]:
    """The task's inputs (task memory ``input.<key>``), which parameterize its tools."""
    return {
        m.key.removeprefix("input."): m.value for m in packet.memory
        if m.scope is MemoryScope.TASK and m.owner == packet.task_id and m.key.startswith("input.")
    }


def _builds_on(packet: WorkPacket, req: EvidenceRequirement) -> bool:
    """Whether the task builds on an upstream artifact of a kind the requirement is scoped to (M37)."""
    return not req.when_upstream or any(a.kind in req.when_upstream for a in packet.task.upstream_artifacts)


def _grounded(art: dict[str, Any], prompt: WorkPrompt, stripped: list[str]) -> dict[str, Any] | None:
    """An artifact draft with its summary grounded, derived from the approved artifacts it cites.

    None when nothing it cites survives: an uncited artifact is dropped.
    """
    from nirmaan.integrations.veritriage import ground

    summary, used, removed = ground(str(art.get("summary", "")), prompt)
    stripped += [t for t in removed if t not in stripped]
    if not used:
        return None
    derived = tuple(c.target for c in prompt.citations if c.kind == "artifact" and c.token in used)
    return {"kind": str(art.get("kind", "")), "title": str(art.get("title", "")), "summary": summary,
            **({"derived_from": derived} if derived else {})}


def _attempt_dir(task_id: str, workspace: str | None) -> Path:
    """A fresh directory per attempt, so no later attempt overwrites files an earlier run checked."""
    base = Path(workspace) if workspace else Path(tempfile.mkdtemp(prefix="nirmaan-work-"))
    root = base / _ID_UNSAFE.sub("_", task_id)
    attempt = 1
    while (root / str(attempt)).exists():
        attempt += 1
    (root / str(attempt)).mkdir(parents=True)
    return root / str(attempt)


def _join(remarks: list[str]) -> str:
    return "; ".join(r for r in remarks if r)


class ModelRuntime:
    """A language model filling a seat. Registered as ``mock-llm`` and ``anthropic``."""

    def __init__(self, llm: LLM, runtime_id: str | None = None) -> None:
        self.llm = llm
        self.runtime_id = runtime_id or llm.name

    def accepts(self, packet: WorkPacket) -> bool:
        return True

    # --- Work --------------------------------------------------------------------------

    def execute(self, packet: WorkPacket, tools: ToolHandle) -> WorkResult:
        """Do the work; every model call made on the way is listed in the result (M31)."""
        self._calls: list[dict[str, Any]] = []
        self._purpose = "work"
        result = self._execute(packet, tools)
        return dataclasses.replace(result, model_calls=tuple(self._calls))

    def _execute(self, packet: WorkPacket, tools: ToolHandle) -> WorkResult:
        inputs = _inputs(packet)
        notes = self._preflight(packet, tools, inputs)
        runs = tuple(n.run for n in notes if n.run)
        prompt = render_work_prompt(packet, "work", notes)
        data, files, problem = self._ask(prompt)
        if data is None:
            return WorkResult(ResultStatus.DECLINED, uncertainty=1.0, tool_runs=runs, notes=problem)
        return self._result(data, files, prompt, packet, tools, inputs, notes)

    def _preflight(self, packet: WorkPacket, tools: ToolHandle, params: dict[str, str]) -> tuple[ToolNote, ...]:
        """Run the tools the task's evidence requirements name, as the seat, before asking.

        A requirement over the task's own files waits for them: it runs after the answer.
        """
        wanted: dict[str, dict[str, str]] = {}
        for req in packet.task.evidence_requirements:
            if _TOOL_BACKED & set(req.accepts) and not req.files and _builds_on(packet, req):
                for tool in req.tools:
                    wanted.setdefault(tool, dict(req.params))
        notes = []
        for tool, fixed in wanted.items():
            try:
                run_id, outcome = tools.invoke(tool, **{**tools.declared(tool, params), **fixed})
            except ToolAccessDenied as exc:
                notes.append(ToolNote(tool, None, False, str(exc)))
            else:
                notes.append(ToolNote(tool, run_id, outcome.succeeded, outcome.summary))
        return tuple(notes)

    def _result(self, data: dict[str, Any], files: _Files, prompt: WorkPrompt, packet: WorkPacket,
                tools: ToolHandle, inputs: dict[str, str], notes: tuple[ToolNote, ...]) -> WorkResult:
        kept, dropped, stripped = [], [], []
        for art in data.get("artifacts") or []:
            if not isinstance(art, dict):
                continue
            draft = _grounded(art, prompt, stripped)
            if draft is None:
                dropped.append(str(art.get("title") or art.get("kind") or "untitled"))
                continue
            kept.append(draft)
        remarks = [str(data.get("notes") or "")]
        if stripped:
            remarks.append(f"stripped undeclared citations: {', '.join(stripped)}")
        if dropped:
            remarks.append(f"dropped uncited artifacts: {', '.join(dropped)}")
        remarks += [f"{n.tool} not run: {n.summary}" for n in notes if n.run is None]
        common = dict(uncertainty=_uncertainty(data.get("uncertainty")),
                      claims=tuple(str(c) for c in data.get("claims") or []))
        # Declared runs go to the engine unfiltered: a run that never happened is P5's to refuse.
        declared = [str(r) for r in data.get("tool_runs") or []]
        runs = [n.run for n in notes if n.run]
        escalation = data.get("escalation")
        if isinstance(escalation, dict) and escalation:
            return WorkResult(ResultStatus.NEEDS_ESCALATION, escalation=EscalationRequest(
                EscalationKind.UNCERTAINTY, str(escalation.get("reason", "the agent could not conclude")),
                str(escalation.get("question", "How should this task proceed?")),
                attempted_actions=tuple(f"ran {n.tool}" for n in notes if n.run),
                recommended_options=tuple(str(o) for o in escalation.get("options") or ()),
            ), tool_runs=tuple(dict.fromkeys([*runs, *declared])), notes=_join(remarks), **common)

        before = len(stripped)
        produced = self._write(data, files, prompt, packet, inputs, stripped, remarks)
        if len(stripped) > before:
            remarks.append(f"stripped undeclared citations from files: {', '.join(stripped[before:])}")
        after, blocked = self._postflight(packet, tools, inputs, produced)
        runs += [n.run for n in after if n.run]
        remarks += [f"{n.tool} not run: {n.summary}" for n in after if n.run is None]
        remarks += [f"{n.tool} {n.run} failed: {n.summary}" for n in after if n.run and not n.succeeded]
        tool_runs = tuple(dict.fromkeys([*runs, *declared]))
        if blocked:  # a check the work must pass cannot run here: nothing goes forward
            return WorkResult(ResultStatus.BLOCKED, tool_runs=tool_runs, notes=_join([*blocked, *remarks]), **common)
        outcome = data.get("outcome") if prompt.outcomes else None
        artifacts = (*kept, *({k: v for k, v in f.items() if k != "entry"} for f in produced))
        return WorkResult(ResultStatus.SUBMITTED, artifacts=artifacts, tool_runs=tool_runs, notes=_join(remarks),
                          outcome=str(outcome) if outcome is not None else None, **common)

    # --- Files (M23) --------------------------------------------------------------------

    def _write(self, data: dict[str, Any], files: _Files, prompt: WorkPrompt, packet: WorkPacket,
               inputs: dict[str, str], stripped: list[str], remarks: list[str]) -> list[dict[str, Any]]:
        """Ground each declared file's summary, then write the kept ones with a digest."""
        blocks, problems = files
        chosen, uncited, orphans = [], [], []
        declared = [f for f in data.get("files") or [] if isinstance(f, dict)]
        for meta in declared:
            path = str(meta.get("path", ""))
            if path not in blocks:
                orphans.append(path or "(no path)")
                continue
            draft = _grounded({"title": path, **meta}, prompt, stripped)
            if draft is None:
                uncited.append(path)
                continue
            entry = meta.get("entry")
            chosen.append((path, {**draft, "entry": str(entry) if entry else None}))
        named = {str(f.get("path", "")) for f in declared}
        problems = [*problems, *(f"file block {p} was declared by no files entry" for p in blocks if p not in named)]
        if uncited:
            remarks.append(f"dropped uncited files: {', '.join(uncited)}")
        if orphans:
            remarks.append(f"dropped files with no content block: {', '.join(orphans)}")
        remarks += problems
        if not chosen:
            return []
        root = _attempt_dir(packet.task_id, inputs.get("workspace"))
        produced = []
        for path, draft in chosen:
            location, digest = write_file(root, path, blocks[path])
            produced.append({**draft, "location": str(location), "digest": digest})
        return produced

    def _postflight(self, packet: WorkPacket, tools: ToolHandle, inputs: dict[str, str],
                    produced: list[dict[str, Any]]) -> tuple[tuple[ToolNote, ...], list[str]]:
        """Run each requirement over the task's own files, filling parameters as the requirement says.

        Returns the notes, and the refusals that block the work: a before-review
        requirement none of whose tools can run here.
        """
        notes: list[ToolNote] = []
        blocked: list[str] = []
        seen: dict[tuple[str, tuple[tuple[str, str], ...]], ToolNote] = {}
        for req in packet.task.evidence_requirements:
            if not req.files or not _TOOL_BACKED & set(req.accepts):
                continue
            if req.when_produced and not any(f["kind"] in req.when_produced for f in produced):
                continue  # a conditional check whose files were not produced: not run, not claimed
            if not _builds_on(packet, req):
                continue  # scoped to work built on other kinds (M37): not run, not claimed
            files: dict[str, str | list[str]] = {}
            missing = None
            for binding in req.files:
                kinds = " or ".join(binding.kinds)
                if binding.upstream:  # approved upstream files only, bytes as recorded
                    paths = [a.location for kind in binding.kinds
                             for a in packet.task.upstream_artifacts
                             if a.kind == kind and a.trusted and a.location
                             and read_verified(a.location, a.digest)[0] is not None]
                    missing = missing or (None if paths else f"no approved upstream {kinds} file")
                    files[binding.param] = paths
                    continue
                matched = [f for kind in binding.kinds for f in produced if f["kind"] == kind]
                if binding.entry:
                    entry = matched[0]["entry"] if matched else None
                    missing = missing or (None if entry else f"no {kinds} file declares an entry")
                    files[binding.param] = entry or ""
                else:
                    paths = [f["location"] for f in matched]
                    missing = missing or (None if paths else f"the answer carried no {kinds} file")
                    files[binding.param] = paths
            refusals = []
            for tool in req.tools:
                if missing:
                    notes.append(ToolNote(tool, None, False, missing))
                    continue
                params = {**tools.declared(tool, inputs), **dict(req.params), **files}
                key = (tool, tuple(sorted((k, str(v)) for k, v in params.items())))
                if key not in seen:
                    try:
                        run_id, outcome = tools.invoke(tool, **params)
                    except ToolAccessDenied as exc:
                        seen[key] = ToolNote(tool, None, False, str(exc))
                    else:
                        seen[key] = ToolNote(tool, run_id, outcome.succeeded, outcome.summary)
                    notes.append(seen[key])
                if seen[key].run is None:
                    refusals.append(seen[key].summary)
            if req.before_review and refusals and len(refusals) == len(req.tools):
                blocked += [r for r in refusals if r not in blocked]
        return tuple(notes), blocked

    # --- Review ------------------------------------------------------------------------

    def review(self, packet: WorkPacket) -> ReviewResult:
        """Review the work; every model call made on the way is listed in the result (M31)."""
        self._calls = []
        self._purpose = "review"
        result = self._review(packet)
        return dataclasses.replace(result, model_calls=tuple(self._calls))

    def _review(self, packet: WorkPacket) -> ReviewResult:
        from nirmaan.integrations.veritriage import ground

        prompt = render_work_prompt(packet, "review")
        data, _, problem = self._ask(prompt)
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

    def _ask(self, prompt: WorkPrompt) -> tuple[dict[str, Any] | None, _Files, str]:
        with outside_writer():  # the call touches no project state: other tasks of a batch take turns (M36)
            completion = self.llm.complete(prompt)
        if not (completion.error or "").startswith(NO_CALL):
            self._calls.append(call_record(completion, getattr(self, "_purpose", "work"), self.llm.name))
        if completion.error:
            return None, ({}, []), f"the model call failed: {completion.error}"
        # File blocks come off first: their content is full of braces the JSON parser would take.
        rest, blocks, problems = split_files(completion.text)
        data = _parse(rest)
        if data is None:
            return None, ({}, []), "the model's answer was not a JSON object; nothing was recorded"
        return data, (blocks, problems), ""


register_runtime("mock-llm")(lambda: ModelRuntime(MockLLM(), runtime_id="mock-llm"))
register_runtime("anthropic")(lambda: ModelRuntime(RegistryLLM("anthropic"), runtime_id="anthropic"))

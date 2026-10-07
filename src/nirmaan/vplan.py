"""Verification plans (M29): requirements and the items that prove them, as a file.

* **The format** (``nirmaan.vplan``, version 1): one JSON object with
  ``requirements`` (ID, text, source, section) and ``items`` (ID, kind, file,
  name, proves, rationale). :func:`parse` reports every problem with the line
  it is on; anything the format does not name is refused, so a plan can never
  claim a result.
* **Import** (:func:`import_plan`): every record goes through the task engine,
  first on a scratch engine; a file with any problem records nothing.
* **Export** (:func:`export_plan`): the project's requirements and items, back
  in the same format.
* **The seat's check** (:func:`check_against_specs`, run as ``vplan.check``):
  a plan covers exactly the requirements its approved spec tags, quoting each.
* **On approval** of a plan its stage checked, the engine records it (a
  registered approval consumer); its items bind to their file once it exists.

Nothing here backs a requirement: only a passing, cited run does (M24).
See docs/VERIFICATION_PLAN.md.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from json import decoder, scanner
from pathlib import Path
from typing import Any, Callable

from nirmaan import engineering
from nirmaan.company import traceability
from nirmaan.models import Actor, Artifact, Assurance, ProjectState
from nirmaan.work.engine import TaskEngine, WorkError, register_approval_consumer
from nirmaan.work.policy import upstream_artifacts

FORMAT = "nirmaan.vplan"
VERSION = 1
#: The artifact kind a plan seat writes, and the tool that checks it before review.
ARTIFACT_KIND = "verification_plan"
CHECK_TOOL = "vplan.check"

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
#: Fields a result would need. Named in the refusal, since a plan only ever declares.
_RESULTS = {"status", "backed", "passed", "passing", "result", "run", "runs", "evidence", "verified"}


class PlanError(ValueError):
    """A plan the reader or the engine refused. Each problem names its line."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass(frozen=True)
class PlanRequirement:
    id: str
    text: str
    source: str
    section: str
    line: int


@dataclass(frozen=True)
class PlanItem:
    id: str
    kind: str
    file: str
    name: str
    proves: tuple[str, ...]
    rationale: str
    line: int


@dataclass(frozen=True)
class Plan:
    requirements: tuple[PlanRequirement, ...]
    items: tuple[PlanItem, ...]


@dataclass(frozen=True)
class ImportReport:
    requirements: int
    items: int


# --- Reading, with lines ----------------------------------------------------------------------


class _Obj(dict):
    """A JSON object that remembers the line it starts on, and the line of each value."""

    line = 1
    keys_in_order: list[str] = []
    key_lines: dict[str, int] = {}

    def at(self, key: str) -> int:
        return self.key_lines.get(key, self.line)


def _pairs(pairs: list[tuple[str, Any]]) -> _Obj:
    obj = _Obj(pairs)
    obj.keys_in_order = [k for k, _ in pairs]
    return obj


def _decoder() -> json.JSONDecoder:
    dec = json.JSONDecoder(object_pairs_hook=_pairs)

    def parse_object(s_and_end, strict, scan_once, object_hook, object_pairs_hook, memo=None,
                     _w=decoder.WHITESPACE.match, _ws=decoder.WHITESPACE_STR):
        text, end = s_and_end
        starts: list[int] = []

        def scan(string: str, idx: int):
            starts.append(idx)
            return scan_once(string, idx)

        obj, new_end = decoder.JSONObject(s_and_end, strict, scan, object_hook, object_pairs_hook, memo, _w, _ws)
        obj.line = text.count("\n", 0, end) + 1
        obj.key_lines = {k: text.count("\n", 0, i) + 1 for k, i in zip(obj.keys_in_order, starts)}
        return obj, new_end

    dec.parse_object = parse_object
    dec.scan_once = scanner.py_make_scanner(dec)
    return dec


def _fields(obj: _Obj, required: set[str], optional: set[str], what: str) -> list[str]:
    problems = [f"line {obj.at(k)}: duplicate field {k!r} in {what}"
                for k, n in Counter(obj.keys_in_order).items() if n > 1]
    problems += [f"line {obj.line}: {what} has no {k!r}" for k in sorted(required - obj.keys())]
    for key in obj:
        if key not in required | optional:
            why = ": a plan declares; it never records a result" if key in _RESULTS else ""
            problems.append(f"line {obj.at(key)}: unknown field {key!r} in {what}{why}")
    return problems


def _text(obj: _Obj, key: str, problems: list[str], required: bool = True) -> str:
    value = obj.get(key, "")
    if not isinstance(value, str) or (required and key in obj and not value.strip()):
        problems.append(f"line {obj.at(key)}: {key} must be a {'non-empty ' if required else ''}string")
        return ""
    return value


def parse(text: str) -> Plan:
    """A plan, or :class:`PlanError` with every problem found, each with its line."""
    try:
        data = _decoder().decode(text)
    except json.JSONDecodeError as exc:
        raise PlanError([f"line {exc.lineno}: {exc.msg}"]) from None
    if not isinstance(data, _Obj):
        raise PlanError(["line 1: a plan is one JSON object"])
    problems = _fields(data, {"format", "version", "requirements"}, {"items"}, "the plan")
    if "format" in data and data["format"] != FORMAT:
        problems.append(f"line {data.at('format')}: format must be {FORMAT!r}, not {data['format']!r}")
    if "version" in data and (data["version"] != VERSION or isinstance(data["version"], bool)):
        problems.append(f"line {data.at('version')}: version must be {VERSION}, not {data['version']!r}: "
                        f"this reader knows version {VERSION} only")

    requirements: list[PlanRequirement] = []
    raw = data.get("requirements", [])
    if not isinstance(raw, list):
        problems.append(f"line {data.at('requirements')}: requirements must be a list")
        raw = []
    for req in raw:
        if not isinstance(req, _Obj):
            problems.append(f"line {data.at('requirements')}: each requirement must be an object")
            continue
        problems += _fields(req, {"id", "text", "source"}, {"section"}, "a requirement")
        rid, body, source = (_text(req, k, problems) for k in ("id", "text", "source"))
        section = _text(req, "section", problems, required=False)
        if rid and not _ID.match(rid):
            problems.append(f"line {req.at('id')}: requirement ID {rid!r} must start with a letter and use only "
                            "letters, digits, '_', '.', and '-'")
        if rid and rid in {r.id for r in requirements}:
            problems.append(f"line {req.at('id')}: duplicate requirement ID {rid!r}")
        requirements.append(PlanRequirement(rid, body, source, section, req.line))

    known = {r.id for r in requirements}
    kinds = engineering.item_kinds()
    items: list[PlanItem] = []
    raw = data.get("items", [])
    if not isinstance(raw, list):
        problems.append(f"line {data.at('items')}: items must be a list")
        raw = []
    for item in raw:
        if not isinstance(item, _Obj):
            problems.append(f"line {data.at('items')}: each item must be an object")
            continue
        problems += _fields(item, {"id", "kind", "file", "name", "proves"}, {"rationale"}, "an item")
        iid, kind, file, name = (_text(item, k, problems) for k in ("id", "kind", "file", "name"))
        rationale = _text(item, "rationale", problems, required=False)
        if iid and not _ID.match(iid):
            problems.append(f"line {item.at('id')}: item ID {iid!r} must start with a letter and use only "
                            "letters, digits, '_', '.', and '-'")
        if iid and iid in {i.id for i in items}:
            problems.append(f"line {item.at('id')}: duplicate item ID {iid!r}")
        if kind and kind not in kinds:
            problems.append(f"line {item.at('kind')}: unknown verification-item kind {kind!r} "
                            f"(registered: {', '.join(sorted(kinds))})")
        proves = item.get("proves", [])
        if not isinstance(proves, list) or not proves or not all(isinstance(p, str) and p for p in proves):
            problems.append(f"line {item.at('proves')}: proves must be a non-empty list of requirement IDs")
            proves = []
        problems += [f"line {item.at('proves')}: proves {p!r}, which is not a requirement in this plan"
                     for p in proves if p not in known]
        items.append(PlanItem(iid, kind, file, name, tuple(proves), rationale, item.line))
    if problems:
        raise PlanError(problems)
    return Plan(tuple(requirements), tuple(items))


# --- Requirements a specification tags ---------------------------------------------------------


@dataclass(frozen=True)
class TaggedRequirement:
    id: str
    text: str
    section: str
    line: int


_LIST = re.compile(r"^\s*(?:[*+-]|\d+[.)])\s+")
_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_NUMBER = re.compile(r"^(\d+(?:\.\d+)*)\.?\s")


def spec_requirements(text: str) -> list[TaggedRequirement]:
    """Every requirement a Markdown spec tags (``REQUIREMENT_TAG``), in order.

    The text is the list item or paragraph holding the tag, without the list
    marker or the tag, whitespace collapsed; the section is the number of the
    nearest heading above it (or the heading itself when it has no number).
    """
    tag = re.compile(traceability.REQUIREMENT_TAG)
    units: list[tuple[int, str, list[str]]] = []
    section, current, fenced = "", None, False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced, current = not fenced, None
            continue
        if fenced:
            continue
        heading = _HEADING.match(line)
        if heading or not line.strip():
            current = None
            if heading:
                title = heading.group(1).strip()
                found = _NUMBER.match(title + " ")
                section = found.group(1) if found else title
            continue
        if current is None or _LIST.match(line):
            current = (number, section, [line])
            units.append(current)
        else:
            current[2].append(line)
    found_reqs = []
    for number, sec, lines in units:
        joined = " ".join(l.strip() for l in lines)
        ids = tag.findall(joined)
        if ids:
            body = " ".join(tag.sub(" ", _LIST.sub("", joined, count=1)).split())
            found_reqs += [TaggedRequirement(rid, body, sec, number) for rid in ids]
    return found_reqs


def _same(a: str, b: str) -> bool:
    return " ".join(a.split()) == " ".join(b.split())


def check_against_specs(plan: Plan, specs: dict[str, str]) -> list[str]:
    """What keeps a plan from matching its specs (file name to text): empty when it covers them exactly."""
    problems: list[str] = []
    tagged: dict[str, tuple[str, TaggedRequirement]] = {}
    for name, text in sorted(specs.items()):
        found = spec_requirements(text)
        if not found:
            problems.append(f"{name} tags no requirement, so no plan can be checked against it")
        for req in found:
            if req.id in tagged:
                problems.append(f"{name} line {req.line}: {req.id} is tagged more than once")
            else:
                tagged[req.id] = (name, req)
    planned = {r.id for r in plan.requirements}
    for req in plan.requirements:
        if req.source not in specs:
            problems.append(f"line {req.line}: {req.id} names source {req.source!r}, which is not the approved "
                            f"spec ({', '.join(sorted(specs))})")
        elif req.id not in tagged or tagged[req.id][0] != req.source:
            problems.append(f"line {req.line}: {req.id} is not a requirement {req.source} tags")
        elif not _same(req.text, tagged[req.id][1].text):
            spec = tagged[req.id][1]
            problems.append(f"line {req.line}: {req.id} does not quote {req.source} line {spec.line}, "
                            f"which says {spec.text!r}")
    problems += [f"{name} line {req.line}: requirement {rid} is not in the plan"
                 for rid, (name, req) in tagged.items() if rid not in planned]
    problems += [f"line {item.line}: item {item.id} must name a plain file name, not {item.file!r}"
                 for item in plan.items if "/" in item.file or "\\" in item.file]
    return problems


def check_files(plan_paths: list[str], spec_paths: list[str]) -> tuple[bool, str]:
    """The ``vplan.check`` run: every plan file valid and covering the given spec files exactly."""
    specs = {Path(p).name: Path(p).read_text(encoding="utf-8") for p in spec_paths}
    passed, summaries = True, []
    for path in plan_paths:
        name = Path(path).name
        try:
            plan = parse(Path(path).read_text(encoding="utf-8"))
            problems = check_against_specs(plan, specs)
        except PlanError as exc:
            plan, problems = None, exc.problems
        if problems or plan is None:
            passed = False
            summaries.append(f"{name}: {len(problems)} problem(s): " + "; ".join(problems))
            continue
        itemless = sorted(r.id for r in plan.requirements if not any(r.id in i.proves for i in plan.items))
        total = len(plan.requirements)
        summary = (f"{name} covers {total} of {total} requirements of {', '.join(sorted(specs))} "
                   f"with {len(plan.items)} items")
        summaries.append(summary + (f"; no item yet for {', '.join(itemless)}" if itemless else ""))
    return passed, " | ".join(summaries)


# --- Import and export --------------------------------------------------------------------------


def _resolve(state: ProjectState, ref: str) -> tuple[str | None, str]:
    """A recorded artifact by ID, recorded path, or unique file name."""
    if ref in state.artifacts:
        return ref, ""
    located = [a for a in state.artifacts.values() if a.location]
    named = [a for a in located if a.location == ref] or [a for a in located if Path(a.location).name == ref]
    if len(named) == 1:
        return named[0].id, ""
    if not named:
        return None, "no recorded artifact has that ID, path, or file name"
    return None, f"names {len(named)} recorded artifacts ({', '.join(a.id for a in named)}); name one by ID"


def _record(engine: TaskEngine, actor: Actor, plan: Plan, sources: dict[str, str], files: dict[str, str],
            problems: list[str] | None = None) -> None:
    """Make every record through the engine. With ``problems``, collect each refusal with its line."""
    calls: list[tuple[int, Callable[[], Any]]] = [
        (r.line, lambda r=r: engine.record_spec_requirement(actor, r.id, r.text, sources[r.id], r.section))
        for r in plan.requirements]
    calls += [(i.line, lambda i=i: engine.record_verification_item(actor, i.id, i.kind, i.name, files[i.id],
                                                                   i.proves, i.rationale))
              for i in plan.items]
    for line, call in calls:
        try:
            call()
        except (WorkError, PermissionError) as exc:
            if problems is None:
                raise
            problems.append(f"line {line}: {exc}")


def import_plan(engine: TaskEngine, actor: Actor, text: str) -> ImportReport:
    """Record a plan through the engine, as ``actor``, or nothing at all (:class:`PlanError`)."""
    plan = parse(text)
    problems: list[str] = []
    sources: dict[str, str] = {}
    files: dict[str, str] = {}
    for refs, entries, field in ((sources, plan.requirements, "source"), (files, plan.items, "file")):
        for entry in entries:
            ref = getattr(entry, field)
            found, why = _resolve(engine.state, ref)
            if found is None:
                problems.append(f"line {entry.line}: {field} {ref!r}: {why}")
            refs[entry.id] = found or ""
    if problems:
        raise PlanError(problems)
    _record(TaskEngine(engine.org, engine.state), actor, plan, sources, files, problems)  # a dry run
    if problems:
        raise PlanError(problems)
    _record(engine, actor, plan, sources, files)
    return ImportReport(len(plan.requirements), len(plan.items))


def export_plan(state: ProjectState) -> str:
    """The project's requirements and items in the plan format: canonical, sorted by ID."""
    names = Counter(Path(a.location).name for a in state.artifacts.values() if a.location)

    def ref(art_id: str) -> str:
        art = state.artifacts.get(art_id)
        if art is not None and art.location and names[Path(art.location).name] == 1:
            return Path(art.location).name
        return art_id

    doc = {
        "format": FORMAT,
        "version": VERSION,
        "requirements": [{"id": r.id, "text": r.text, "source": ref(r.source), "section": r.section}
                         for r in sorted(state.spec_requirements.values(), key=lambda r: r.id)],
        "items": [{"id": i.id, "kind": i.kind, "file": i.file or ref(i.artifact), "name": i.name,
                   "proves": list(i.proves), "rationale": i.rationale}
                  for i in sorted(state.verification_items.values(), key=lambda i: i.id)],
    }
    return json.dumps(doc, indent=2) + "\n"


# --- On approval -----------------------------------------------------------------------------------


def _checked_by_its_stage(engine: TaskEngine, art: Artifact) -> bool:
    task = engine.task(art.task)
    return any(CHECK_TOOL in req.tools and any(art.kind in b.kinds for b in req.files)
               for req in task.evidence_requirements)


def _on_approval(engine: TaskEngine, art: Artifact) -> Callable[[], None]:
    """Validate an approved plan against its approved specs, and return what records it.

    Only a plan whose stage checks it with ``vplan.check`` is a plan file; a
    verification plan from any other stage is a document and records nothing.
    """
    if not _checked_by_its_stage(engine, art):
        return lambda: None
    refused = f"plan {art.id} cannot be recorded"
    data, why = engineering.verified_bytes(art)
    if data is None:
        raise WorkError(f"{refused}: {why}")
    try:
        plan = parse(data.decode("utf-8"))
    except PlanError as exc:
        raise WorkError(f"{refused}: {exc}") from None
    task = engine.task(art.task)
    approved = {Path(a.location).name: a for a in upstream_artifacts(engine.state, task)
                if a.assurance is Assurance.APPROVED and a.location}
    problems: list[str] = []
    specs: dict[str, tuple[Artifact, str]] = {}
    for name in sorted({r.source for r in plan.requirements}):
        source = approved.get(name)
        if source is None:
            problems.append(f"source {name!r} is not an approved upstream file of {task.id}")
            continue
        spec, why = engineering.verified_bytes(source)
        if spec is None:
            problems.append(why)
            continue
        specs[name] = (source, spec.decode("utf-8"))
    if not problems:
        problems = check_against_specs(plan, {name: text for name, (_, text) in specs.items()})
    state = engine.state
    problems += [f"requirement {r.id} is already recorded" for r in plan.requirements
                 if r.id in state.spec_requirements]
    problems += [f"verification item {i.id} is already recorded" for i in plan.items
                 if i.id in state.verification_items]
    if problems:
        raise WorkError(f"{refused}: " + "; ".join(problems))

    def record() -> None:
        actor = engine.system  # a consequence of the approval, as every one is
        for req in plan.requirements:
            engine.record_spec_requirement(actor, req.id, req.text, specs[req.source][0].id, req.section,
                                           plan=art.id)
        for item in plan.items:
            engine.record_planned_item(actor, item.id, item.kind, item.name, item.file, art.id, item.proves,
                                       item.rationale)

    return record


register_approval_consumer(ARTIFACT_KIND, _on_approval)

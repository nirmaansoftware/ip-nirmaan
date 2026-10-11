"""``spec.check`` behind the tool broker (M45): a specification checked against the requirements it must carry.

An in-process tool that reads files only, so it runs on every machine.
``spec`` is the specification file (or files), ``checks`` a checks file
(format ``nirmaan.spec-checks``): requirement IDs, each with terms its tagged
text must contain, and names the specification must use as whole words. It
passes only when every listed requirement is tagged exactly once (the M29
``[req:ID]`` grammar, parsed by ``nirmaan.vplan.spec_requirements``), each
tagged text contains its terms (ignoring case), and every name appears. A
failing check is a recorded run with ``succeeded=False``. See
docs/LIVE_EVAL_EVIDENCE.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from nirmaan.models import list_values
from nirmaan.runtime.tools import Params, ToolOutcome, register_binding
from nirmaan.vplan import spec_requirements
from nirmaan.work.engine import TaskEngine

CHECK_TOOL = "spec.check"
FORMAT = "nirmaan.spec-checks"


def load_checks(path: str) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """The requirements (ID, terms) and names a checks file lists. A file in another format is an error."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError(f"{Path(path).name} is not a {FORMAT} file")
    requirements = [(str(r["id"]), [str(t) for t in r.get("terms", ())]) for r in data.get("requirements", ())]
    return requirements, [str(n) for n in data.get("names", ())]


def check_spec(spec_paths: list[str], checks_path: str) -> tuple[bool, str]:
    """The ``spec.check`` run: (passed, summary)."""
    requirements, names = load_checks(checks_path)
    texts = {Path(p).name: Path(p).read_text(encoding="utf-8") for p in spec_paths}
    tagged: dict[str, list[str]] = {}
    for text in texts.values():
        for req in spec_requirements(text):
            tagged.setdefault(req.id, []).append(req.text)
    problems: list[str] = []
    carried = 0
    for rid, terms in requirements:
        found = tagged.get(rid, [])
        if not found:
            problems.append(f"{rid} is not tagged")
            continue
        if len(found) > 1:
            problems.append(f"{rid} is tagged {len(found)} times")
            continue
        missing = [t for t in terms if t.lower() not in found[0].lower()]
        problems += [f"{rid} does not say {t!r}" for t in missing]
        carried += not missing
    whole = "\n".join(texts.values())
    absent = [n for n in names if not re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", whole)]
    problems += [f"{n} is never named" for n in absent]
    where = ", ".join(sorted(texts))
    summary = (f"{where} carries {carried} of {len(requirements)} required requirements and names "
               f"{len(names) - len(absent)} of {len(names)} required names")
    return not problems, summary + (f": {'; '.join(problems)}" if problems else "")


@register_binding(CHECK_TOOL)
def _check(params: Params, engine: TaskEngine) -> ToolOutcome:
    specs, checks = list_values(params.get("spec")), list_values(params.get("checks"))
    if not specs:
        return ToolOutcome(False, "no specification file to check")
    if len(checks) != 1:
        return ToolOutcome(False, "exactly one checks file is needed")
    try:
        passed, summary = check_spec(specs, checks[0])
    except (OSError, ValueError, KeyError) as exc:
        return ToolOutcome(False, f"cannot check: {exc}")
    return ToolOutcome(passed, summary, tuple(specs))

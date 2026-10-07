"""``vplan.check`` behind the tool broker (M29): a verification plan checked against its approved spec.

An in-process tool, so it runs on every machine: ``plan`` is the plan file (or
files) the seat wrote, ``spec`` the approved upstream spec file (or files) the
stage names. It passes only when each plan is valid in the ``nirmaan.vplan``
format and covers exactly the requirements the specs tag, quoting each. A
failing check is a recorded run with ``succeeded=False``. The rules live in
``nirmaan.vplan``; see docs/VERIFICATION_PLAN.md.
"""

from __future__ import annotations

from nirmaan.runtime.tools import ToolOutcome, register_binding
from nirmaan.vplan import CHECK_TOOL, check_files
from nirmaan.work.engine import TaskEngine


def _paths(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


@register_binding(CHECK_TOOL)
def _check(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    plans, specs = _paths(params.get("plan", "")), _paths(params.get("spec", ""))
    if not plans:
        return ToolOutcome(False, "no plan file to check")
    if not specs:
        return ToolOutcome(False, "no approved spec file to check the plan against")
    passed, summary = check_files(plans, specs)
    return ToolOutcome(passed, summary, tuple(plans))

"""A project wide model-call budget (M36): a person's recorded decision, spent as M31 records calls.

The budget is not a field of its own. A person sets it with
``TaskEngine.set_budget``, which appends a ``budget.set`` entry to the audit
trail; the latest such entry is the budget. So it persists with the project,
says who decided and why, and cannot be raised by editing the file without
breaking the hash chain (P11). The spend is read from the recorded
``ModelCall``s, so every model call from any command counts against it.
"""

from __future__ import annotations

from dataclasses import dataclass

from nirmaan.models import ProjectState

#: The audit action that sets the budget.
BUDGET_SET = "budget.set"


@dataclass(frozen=True)
class Budget:
    """The limits a person set; None means no limit of that kind."""

    calls: int | None
    cost_usd: float | None
    set_by: str
    reason: str


@dataclass(frozen=True)
class Spend:
    """What the project's recorded model calls add up to (M31). A call of unknown cost is never free."""

    calls: int
    cost_usd: float
    unknown_cost: int


def budget(state: ProjectState) -> Budget | None:
    """The latest budget a person set, or None when none is set (or the last one cleared every limit)."""
    for entry in reversed(state.audit):
        if entry.action == BUDGET_SET:
            calls, cost = entry.details.get("calls"), entry.details.get("cost_usd")
            if calls is None and cost is None:
                return None
            return Budget(calls, cost, entry.actor, entry.reason)
    return None


def spend(state: ProjectState) -> Spend:
    calls = list(state.model_calls.values())
    known = [c.cost_usd for c in calls if c.cost_usd is not None]
    return Spend(len(calls), round(sum(known), 6), len(calls) - len(known))


def over(state: ProjectState, limits: Budget | None, worst: int, reserved: int = 0) -> str | None:
    """Why a step that may make ``worst`` more calls may not start, or None.

    ``reserved`` is what the steps already in flight may still make.
    """
    if limits is None:
        return None
    spent = spend(state)
    if limits.calls is not None and worst > 0 and spent.calls + reserved + worst > limits.calls:
        left = max(limits.calls - spent.calls - reserved, 0)
        return (f"the project call budget is spent: {spent.calls} of {limits.calls} calls made, "
                f"{left} left, and the step may make {worst}")
    if limits.cost_usd is not None and worst > 0:
        if spent.unknown_cost:
            return (f"the project cost budget cannot be checked: {spent.unknown_cost} recorded call(s) "
                    f"of unknown cost")
        if spent.cost_usd >= limits.cost_usd:
            return f"the project cost budget is spent: {spent.cost_usd} of {limits.cost_usd} USD"
    return None

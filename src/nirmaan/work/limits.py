"""The one limits resolver (M48): override, then stage, then capability, then the default.

The runner (attempts, review rounds) and the engine (retries, on failure) both
ask here, so every limit follows the same precedence
(docs/UNIFIED_APPLICABILITY.md, section 2.4).
"""

from __future__ import annotations

from nirmaan.models import Limits, Task, resolve_limits


def limits_for(org, task: Task, override: Limits | None = None) -> Limits:
    """Every limit for a task, each from the first layer that sets it."""
    workflow = org.workflows.get(task.workflow or "")
    stage = workflow.stage(task.stage) if workflow and task.stage else None
    capability = org.capabilities.get(task.capability or "")
    return resolve_limits(override, stage.limits if stage else None, capability.limits if capability else None)

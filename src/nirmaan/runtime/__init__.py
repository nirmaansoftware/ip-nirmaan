"""Agent runtime interface (Phase 4): attach workers to roles without trusting them."""

from nirmaan.runtime.base import (
    AgentRuntime,
    EscalationRequest,
    NullRuntime,
    ResultStatus,
    RunReport,
    ScriptedRuntime,
    ToolHandle,
    WorkResult,
    available_runtimes,
    get_runtime,
    register_runtime,
    run_task,
)
from nirmaan.runtime.context import WorkPacket, assemble
from nirmaan.runtime.tools import (
    ToolAccessDenied,
    ToolBroker,
    ToolOutcome,
    available_bindings,
    register_binding,
    unregister_binding,
)

__all__ = [name for name in dir() if not name.startswith("_")]

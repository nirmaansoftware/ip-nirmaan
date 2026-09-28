"""Agent runtime interface (Phase 4): attach workers to roles without trusting them."""

from nirmaan.runtime.base import (
    AgentRuntime,
    EscalationRequest,
    NullRuntime,
    ResultStatus,
    ReviewResult,
    RunReport,
    ScriptedRuntime,
    ToolHandle,
    WorkResult,
    available_runtimes,
    get_runtime,
    register_runtime,
    review_task,
    run_task,
    unregister_runtime,
)
from nirmaan.runtime.context import WorkPacket, assemble
from nirmaan.runtime.model import LLM, Completion, MockLLM, ModelRuntime, RegistryLLM
from nirmaan.runtime.prompt import Citable, ToolNote, WorkPrompt, render_work_prompt
from nirmaan.runtime.tools import (
    ToolAccessDenied,
    ToolBroker,
    ToolOutcome,
    available_bindings,
    register_binding,
    unregister_binding,
)

__all__ = [name for name in dir() if not name.startswith("_")]

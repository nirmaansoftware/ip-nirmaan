"""Agent runtime interface (Phase 4): attach workers to roles without trusting them."""

from nirmaan.runtime.base import (
    AgentRuntime,
    EscalationRequest,
    Limits,
    NullRuntime,
    ResultStatus,
    ReviewResult,
    RunReport,
    ScriptedRuntime,
    ToolHandle,
    WorkResult,
    available_runtimes,
    exhausted,
    get_runtime,
    limits,
    register_runtime,
    review_task,
    run_task,
    unregister_runtime,
)
from nirmaan.runtime.context import WorkPacket, assemble
from nirmaan.runtime.loop import LoopPlan, LoopReport, LoopStep, PlannedStep, Stop, loop, plan_loop
from nirmaan.runtime.model import LLM, Completion, MockLLM, ModelRuntime, RegistryLLM
from nirmaan.runtime.prompt import Citable, ToolNote, WorkPrompt, render_work_prompt
from nirmaan.runtime.tools import (
    ToolAccessDenied,
    ToolBroker,
    ToolContractError,
    ToolOutcome,
    available_bindings,
    register_binding,
    unavailable_reason,
    unregister_binding,
)

from nirmaan.runtime import selection as _selection  # noqa: E402,F401  (registers the auto runtime)

__all__ = [name for name in dir() if not name.startswith("_")]

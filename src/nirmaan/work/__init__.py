"""Work layer: the task engine, policy, audit, blockers, management, persistence."""

from nirmaan.work.audit import verify_chain
from nirmaan.work.blockers import Blocker, blocked_tasks, why_blocked
from nirmaan.work.engine import AuthorityError, TaskEngine, TransitionError, WorkError
from nirmaan.work.management import StatusReport, status_report, verify_completion
from nirmaan.work.policy import (
    PolicyEngine,
    PolicyViolation,
    PolicyViolationError,
    available_checks,
    register_check,
    unregister_check,
)
from nirmaan.work.store import ProjectStore
from nirmaan.work.trace import TraceRelation, trace_graph

__all__ = [name for name in dir() if not name.startswith("_")]

# M29: verification plans register what approving one records (``register_approval_consumer``), so the
# registration is in place wherever the engine is. Imported last: it builds on everything above.
import nirmaan.vplan  # noqa: E402,F401

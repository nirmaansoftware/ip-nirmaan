"""Deliverable vocabulary: how a project's state is laid out as a deliverable tree.

A folder names what it collects (artifact kinds, and capabilities as a fallback)
and which evidence sections it holds. The export reads a table of these and
never names a folder itself.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ExportSection(str, Enum):
    """A part of the export that is not an artifact: evidence and signoff views."""

    TRACE = "trace"  # requirement -> tasks -> artifacts -> evidence
    TOOL_RUNS = "tool_runs"  # tool-run records, with their referenced files copied
    REVIEWS = "reviews"
    AUDIT_CHAIN = "audit_chain"  # the trail, its head hash, and a fresh verification
    SIGNOFF = "signoff"  # what is and is not signed off, from recorded gate approvals


class DeliverableFolder(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(description="The directory name, e.g. a numbered folder.")
    title: str
    description: str = ""
    artifact_kinds: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = Field(
        default=(), description="Fallback: artifacts whose kind no folder names, by their task's capability."
    )
    sections: tuple[ExportSection, ...] = ()

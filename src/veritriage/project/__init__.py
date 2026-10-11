"""Verification Project Intelligence (M11).

A durable, structured understanding of a verification project, built before any
failure is analyzed: the verification equivalent of an IDE's code index. The
Project Model is a separate, persistent, content-addressed model (parallel to the
Knowledge Graph and the Regression Database) that never enters the Evidence Graph;
it reaches reasoning as injected rules that cite existing evidence, and the report
as context. See ``docs/PROJECT_INTELLIGENCE.md``.

``build_project_model`` is the composition root: gather partial models from every
available provider, run insights, then seal a deterministic identity and integrity
fingerprint. It performs no reasoning and touches source only through providers.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from veritriage.project.inference import (
    build_project_view,
    project_reasoning_rules,
    resolve_scope,
)
from veritriage.project.insights import apply_insights, available_insights, register_insight
from veritriage.project.lifecycle import project_lifecycle
from veritriage.project.logmap import classify_origin, explain_log
from veritriage.project.model import ProjectModel, seal_project
from veritriage.project.persistence import ProjectStore
from veritriage.project.providers import (
    ProjectCapability,
    ProjectProvider,
    ProjectProviderError,
    available_project_providers,
    collect_project,
    register_project_provider,
    unregister_project_provider,
)

__all__ = [
    "ProjectCapability",
    "ProjectModel",
    "ProjectProvider",
    "ProjectProviderError",
    "ProjectStore",
    "apply_insights",
    "available_insights",
    "available_project_providers",
    "build_project_model",
    "build_project_view",
    "classify_origin",
    "collect_project",
    "explain_log",
    "project_lifecycle",
    "project_reasoning_rules",
    "register_insight",
    "register_project_provider",
    "resolve_scope",
    "seal_project",
    "unregister_project_provider",
]


def _input_fingerprint(root: Path) -> str:
    """A digest of the source a model was built from, for staleness checks.

    In the manifest-first increment the source is the set of ``*.vproj.json``
    files under (or at) the root; hashing their bytes is enough to detect drift.
    """
    hasher = hashlib.sha256()
    candidates: list[Path] = []
    if root.is_file():
        candidates = [root]
    elif root.is_dir():
        candidates = sorted(root.glob("*.vproj.json")) + sorted(
            p for suffix in ("*.v", "*.sv") for p in root.glob(suffix)  # the RTL provider's sources (M24)
        )
    for path in candidates:
        hasher.update(path.name.encode("utf-8"))
        hasher.update(path.read_bytes())
    return "sha256:" + hasher.hexdigest()


def build_project_model(root: Path) -> ProjectModel:
    """Build a sealed Project Model for ``root`` from every available provider.

    Deterministic: the same sources always produce the same ``project_id`` and
    fingerprint. Returns an empty (but sealed) model when nothing is available,
    so callers can treat "no project understanding" uniformly.
    """
    merged = collect_project(root)
    enriched = apply_insights(merged)
    with_fingerprint = enriched.model_copy(
        update={"input_fingerprint": _input_fingerprint(root)}
    )
    return seal_project(with_fingerprint)

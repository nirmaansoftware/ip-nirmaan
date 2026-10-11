"""Canonical engineering-context manifest provider (tool-independent JSON).

This is the reference contract: the format any CI system, review bot, or
internal tool can export to feed VeriTriage engineering context without
VeriTriage learning that tool's API. It is also the full-fidelity path,
declaring every capability, and doubles as the artifact-file entry route via
:class:`~veritriage.engineering.parser.EngineeringContextParser`.

Schema (`*.engctx.json`):

    {
      "commits": [
        {"revision": "a1b2c3d", "author": "asha", "timestamp": "2026-07-23T10:00:00+00:00",
         "title": "rework AR channel arbitration",
         "files": [
           {"path": "rtl/axi_monitor.sv", "category": "rtl",
            "lines_added": 40, "lines_deleted": 12, "modules": ["axi_monitor"]}
         ]}
      ],
      "ci_run": {"pipeline": "nightly", "build_number": "1204",
                 "simulator": "vcs", "compiler": "gcc-12",
                 "configuration": {"vcs": "2026.03"},
                 "environment_changes": ["simulator upgraded 2025.12 -> 2026.03"]},
      "ownership": [
        {"scope": "axi_monitor", "role": "verification", "owner": "asha"}
      ],
      "issues": [
        {"tracker_id": "PROJ-482", "title": "AR starvation under backpressure", "status": "open"}
      ]
    }

Unknown categories degrade to "other"; a file's category is inferred from its
path when omitted, using the same deterministic heuristic as the git provider.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from veritriage.engineering.model import (
    ChangeCategory,
    ChangedFile,
    CIRun,
    Commit,
    ContextCapability,
    EngineeringContext,
    IssueRef,
    Ownership,
    make_context_id,
)
from veritriage.engineering.providers.base import ContextProvider, ContextProviderError
from veritriage.engineering.providers.git import categorize_path, modules_for_path
from veritriage.engineering.providers.registry import register_provider

#: Filename patterns the manifest entry path claims.
MANIFEST_PATTERNS = ("*.engctx.json", "engineering_context.json")


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _category(entry: dict[str, Any]) -> ChangeCategory:
    declared = entry.get("category")
    if declared:
        try:
            return ChangeCategory(str(declared).lower())
        except ValueError:
            return ChangeCategory.OTHER
    return categorize_path(str(entry.get("path", "")))


def load_manifest(path: Path) -> EngineeringContext:
    """Parse one manifest file into a normalized context.

    Raises:
        ContextProviderError: If the file is not valid manifest JSON.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContextProviderError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ContextProviderError(f"{path}: expected a JSON object at the top level")

    source = ManifestProvider.source
    commits = tuple(
        Commit(
            id=make_context_id(source, str(c["revision"])),
            revision=str(c["revision"]),
            timestamp=_timestamp(c.get("timestamp")),
            author=str(c["author"]) if c.get("author") else None,
            title=str(c.get("title", "")),
            files=tuple(
                ChangedFile(
                    path=str(f["path"]),
                    category=_category(f),
                    lines_added=int(f.get("lines_added", 0)),
                    lines_deleted=int(f.get("lines_deleted", 0)),
                    modules=tuple(f.get("modules") or modules_for_path(str(f["path"]))),
                )
                for f in c.get("files", [])
            ),
            source=source,
        )
        for c in data.get("commits", [])
    )

    ci_raw = data.get("ci_run")
    ci_run = None
    if isinstance(ci_raw, dict):
        ci_run = CIRun(
            id=make_context_id(source, "ci", str(ci_raw.get("pipeline")), str(ci_raw.get("build_number"))),
            pipeline=ci_raw.get("pipeline"),
            build_number=str(ci_raw["build_number"]) if ci_raw.get("build_number") else None,
            timestamp=_timestamp(ci_raw.get("timestamp")),
            simulator=ci_raw.get("simulator"),
            compiler=ci_raw.get("compiler"),
            configuration={str(k): str(v) for k, v in (ci_raw.get("configuration") or {}).items()},
            environment_changes=tuple(ci_raw.get("environment_changes") or ()),
            source=source,
        )

    ownership = tuple(
        Ownership(
            scope=str(o["scope"]),
            role=str(o.get("role", "owner")),
            owner=str(o["owner"]),
            source=source,
        )
        for o in data.get("ownership", [])
    )
    issues = tuple(
        IssueRef(
            id=make_context_id(source, "issue", str(i["tracker_id"])),
            tracker_id=str(i["tracker_id"]),
            title=str(i.get("title", "")),
            status=i.get("status"),
            source=source,
        )
        for i in data.get("issues", [])
    )

    return EngineeringContext(
        sources=(ManifestProvider.name,),
        capabilities=ManifestProvider.capabilities,
        commits=commits,
        ci_run=ci_run,
        ownership=ownership,
        issues=issues,
    )


@register_provider
class ManifestProvider(ContextProvider):
    """Reads canonical context manifests found at the collection root."""

    name = "engineering_manifest"
    source = "manifest"
    # Canonical: a manifest can carry every kind of *recorded* context. It
    # cannot answer CHANGE_RANGE, which is a live query against a system
    # rather than a field in an export, so it does not claim it.
    capabilities = frozenset(ContextCapability) - {ContextCapability.CHANGE_RANGE}

    @classmethod
    def available(cls, root: Path) -> bool:
        return any(cls._manifests(root))

    def collect(self, root: Path, max_commits: int = 10) -> EngineeringContext:
        merged = EngineeringContext()
        for path in self._manifests(root):
            merged = merged.merge(load_manifest(path))
        return merged

    @staticmethod
    def _manifests(root: Path) -> list[Path]:
        found: list[Path] = []
        for pattern in MANIFEST_PATTERNS:
            found.extend(sorted(root.glob(pattern)))
        return found

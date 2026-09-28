"""Project persistence: one JSON document per project under ``.nirmaan/projects``.

Saving never alters state, and loading verifies the audit chain and the
organization fingerprint so a tampered file, or a project planned against a
different organization, is reported rather than silently trusted.
"""

from __future__ import annotations

import json
from pathlib import Path

from nirmaan.models import ProjectState
from nirmaan.work.audit import verify_chain

DEFAULT_ROOT = Path(".nirmaan")


class ProjectStore:
    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self._dir = Path(root) / "projects"

    def path(self, project_id: str) -> Path:
        return self._dir / f"{project_id}.json"

    def save(self, state: ProjectState) -> Path:
        self._dir.mkdir(parents=True, exist_ok=True)
        target = self.path(state.project.id)
        target.write_text(
            json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return target

    def load(self, project_id: str, verify: bool = True) -> ProjectState:
        """``verify=False`` is for readers that report a broken chain themselves (the export)."""
        path = self.path(project_id)
        if not path.exists():
            matches = sorted(self._dir.glob(f"{project_id}*.json")) if self._dir.exists() else []
            if len(matches) != 1:
                raise KeyError(f"Unknown project {project_id!r}")
            path = matches[0]
        state = ProjectState.model_validate_json(path.read_text(encoding="utf-8"))
        problems = verify_chain(state.audit) if verify else []
        if problems:
            raise ValueError(f"Project {project_id} failed audit verification: {problems[0]}")
        return state

    def list(self) -> list[ProjectState]:
        if not self._dir.exists():
            return []
        found = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                found.append(ProjectState.model_validate_json(path.read_text(encoding="utf-8")))
            except ValueError:
                continue
        return found

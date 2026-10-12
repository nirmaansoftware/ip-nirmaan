"""Project model persistence: one cached model per project, plus a root index.

Models live under ``.veritriage/project/<project_id>.json`` (beside the sessions
directory and regression database, same convention), so the model is built once
and reused by every investigation. A small ``index.json`` maps a source root to
its last-built project id, so ``--project`` can load the cached model for the
current directory without rebuilding, and report staleness by fingerprint.
"""

from __future__ import annotations

import json
from pathlib import Path

from veritriage.project.model import ProjectModel

#: Default project directory, beside the default sessions and regression DB.
DEFAULT_PROJECT_ROOT = Path(".veritriage") / "project"


class ProjectStore:
    """Saves and loads project models under one directory."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else DEFAULT_PROJECT_ROOT

    def path_for(self, project_id: str) -> Path:
        return self.root / f"{project_id}.json"

    def _index_path(self) -> Path:
        return self.root / "index.json"

    def _index(self) -> dict[str, str]:
        path = self._index_path()
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}

    def save(self, model: ProjectModel) -> Path:
        """Persist one model and index it by its source root."""
        path = self.path_for(model.project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        index = self._index()
        index[str(Path(model.source_root))] = model.project_id
        self._index_path().write_text(
            json.dumps(index, indent=2, sort_keys=True), encoding="utf-8"
        )
        return path

    def load(self, project_id: str) -> ProjectModel | None:
        """Load a model by ID; None when no model file exists."""
        path = self.path_for(project_id)
        if not path.is_file():
            return None
        return ProjectModel.model_validate_json(path.read_text(encoding="utf-8"))

    def load_for_root(self, root: Path) -> ProjectModel | None:
        """The cached model last built for ``root``, or None when absent or stale.

        Stale means the sources under ``root`` no longer hash to the model's
        ``input_fingerprint`` (an edited ``.v`` file, say), so the caller rebuilds.
        """
        from veritriage.project import _input_fingerprint  # the package imports this module

        project_id = self._index().get(str(Path(root)))
        model = self.load(project_id) if project_id else None
        if model is None or model.input_fingerprint != _input_fingerprint(Path(root)):
            return None
        return model

"""Project persistence: one JSON document per project under ``.nirmaan/projects``.

Saving never alters state. Each save is atomic (a temporary file, fsync, then a
rename) and seals the file (M51): a digest of every record, bound to the audit
chain's length and head hash, so a record edited outside the engine (a task
marked completed, the model calls erased to reset the budget's spend) is
detected on load, not only an edited audit entry. Loading verifies the chain
and the seal and refuses a file that fails either; ``read`` reports the failure
instead, for the views that show a tampered project loudly. The organization
fingerprint is not checked here: the CLI notes a project planned against a
different organization. See ``docs/PERSISTENCE_INTEGRITY.md``.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nirmaan.models import ProjectState
from nirmaan.models.workflow import legacy_requirement
from nirmaan.work.audit import GENESIS, verify_chain

DEFAULT_ROOT = Path(".nirmaan")

#: The saved file's format. "1": written before M51, with no seal (the M39 and M48 conversions apply on load).
#: "2": sealed (M51). A file is read in either format and always written in the current one.
SCHEMA_VERSION = "2"
#: The seal's own format, so a later change to how records are digested can be told apart.
SEAL_FORMAT = 1

SEALED, PRE_SEALING, BROKEN = "sealed", "pre-sealing", "broken"


class ProjectExistsError(ValueError):
    """Planning would replace a saved project; refused unless the caller asks to replace it."""


@dataclass(frozen=True)
class Integrity:
    """What loading a saved project could verify.

    ``sealed``: the chain is intact and every record matches the seal.
    ``pre-sealing``: saved before M51; the chain is intact, but the records were never bound to it.
    ``broken``: the chain or the seal failed; ``problems`` says how.
    ``sealed_from`` is the number of audit entries the project had when it was first sealed (0 for a project
    sealed since planning); the records as they stood before that were never bound.
    """

    status: str
    problems: tuple[str, ...] = ()
    sealed_from: int | None = None

    @property
    def verified(self) -> bool:
        return self.status != BROKEN

    def describe(self) -> str:
        if self.status == BROKEN:
            return f"failed verification: {self.problems[0]}"
        if self.status == PRE_SEALING:
            return ("pre-sealing: saved before M51, so its records are not bound to the audit chain "
                    "(the chain itself verifies); the next save seals it")
        if self.sealed_from:
            return (f"sealed from audit entry {self.sealed_from}: the records as saved before M51 "
                    "were never bound, everything since is")
        return "sealed: every record matches the audit chain"


@dataclass(frozen=True)
class Unreadable:
    path: Path
    reason: str


class Listing(list):
    """The readable projects, as a list, plus what could not be read and each project's integrity."""

    def __init__(self, projects: list[ProjectState], unreadable: list[Unreadable],
                 integrity: dict[str, Integrity]) -> None:
        super().__init__(projects)
        self.unreadable = unreadable
        self.integrity = integrity


def records_digest(data: dict[str, Any], entries: int, head: str, sealed_from: int) -> str:
    """The digest a seal carries: every record except the audit entries, bound to the chain's length and head.

    It is computed from the file's JSON (on save, the JSON about to be written), never from a re-validated
    model, so a later field with a default does not change the digest of an older file.
    """
    records = {k: v for k, v in data.items() if k not in ("audit", "seal")}
    payload = json.dumps({"entries": entries, "head": head, "sealed_from": sealed_from, "records": records},
                         sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _head(data: dict[str, Any]) -> tuple[int, str]:
    audit = data.get("audit") or []
    return len(audit), (audit[-1].get("hash", "") if audit else GENESIS)


def _check_seal(data: dict[str, Any]) -> tuple[str, list[str], int | None]:
    seal = data.get("seal")
    if seal is None:
        if str(data.get("schema_version", "1")) == "1":
            return PRE_SEALING, [], None
        return BROKEN, [f"the file says schema version {data.get('schema_version')} but has no seal "
                        "(the seal was removed)"], None
    if not isinstance(seal, dict) or seal.get("format") != SEAL_FORMAT:
        return BROKEN, ["unknown seal format; the records cannot be checked"], None
    entries, head = _head(data)
    sealed_from = seal.get("sealed_from")
    if seal.get("entries") != entries or seal.get("head") != head:
        return BROKEN, [f"the seal covers {seal.get('entries')} audit entries ending in {seal.get('head')}, "
                        f"but the file has {entries} ending in {head} (entries added or removed outside "
                        "the engine)"], sealed_from
    if not isinstance(sealed_from, int) or records_digest(data, entries, head, sealed_from) != seal.get("digest"):
        return BROKEN, [f"the project records were edited outside the engine: they do not match the seal "
                        f"at audit entry {entries}"], sealed_from if isinstance(sealed_from, int) else None
    return SEALED, [], sealed_from


def _write_atomically(target: Path, text: str) -> None:
    """A temporary file in the same directory, flushed to disk, then renamed over the target.

    A crash or a full disk leaves either the previous file or the new one, never a truncated one. The
    temporary name ends in ``.tmp`` so a listing never mistakes it for a project.
    """
    tmp = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    try:  # make the rename itself durable; not every platform can open a directory
        dir_fd = os.open(target.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def _pre_m48(data: dict[str, Any]) -> dict[str, Any]:
    """A schema version "1" file may predate M48: its requirements with no ``bounds`` read ``max_``/``min_``
    parameters as bounds (M52: only here, never for data built today). A sealed file is returned as it is."""
    if str(data.get("schema_version", "1")) != "1" or not isinstance(data.get("tasks"), dict):
        return data
    tasks = {}
    for key, task in data["tasks"].items():
        reqs = task.get("evidence_requirements") if isinstance(task, dict) else None
        if isinstance(reqs, list):
            task = {**task, "evidence_requirements": [legacy_requirement(r) if isinstance(r, dict) else r
                                                      for r in reqs]}
        tasks[key] = task
    return {**data, "tasks": tasks}


class ProjectStore:
    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self._root = Path(root)
        self._dir = self._root / "projects"

    def path(self, project_id: str) -> Path:
        return self._dir / f"{project_id}.json"

    def exists(self, project_id: str) -> bool:
        return self.path(project_id).exists()

    def save(self, state: ProjectState) -> Path:
        """Write ``state`` atomically, sealed. Overwrites the project's file: for a project already loaded."""
        self._dir.mkdir(parents=True, exist_ok=True)
        target = self.path(state.project.id)
        data = state.model_dump(mode="json")
        data["schema_version"] = SCHEMA_VERSION
        entries, head = _head(data)
        sealed_from = self._sealed_from(target, entries)
        data["seal"] = {"format": SEAL_FORMAT, "entries": entries, "head": head, "sealed_from": sealed_from,
                        "digest": records_digest(data, entries, head, sealed_from)}
        _write_atomically(target, json.dumps(data, indent=2, sort_keys=True) + "\n")
        return target

    def create(self, state: ProjectState, replace: bool = False) -> tuple[Path, Path | None]:
        """Save a newly planned project. Refused when the project exists, unless ``replace``.

        Replacing moves the existing file, byte for byte, to ``<root>/archive/projects/<id>.<n>.json`` first
        (itself a project store, so the archived chain and seal still verify). Returns the new file and the
        archive, or None when nothing was replaced.
        """
        target = self.path(state.project.id)
        archived = None
        if target.exists():
            if not replace:
                raise ProjectExistsError(
                    f"Project {state.project.id} already exists ({target}); planning it again would discard its "
                    f"work and audit trail. Nothing was changed. See it with `nirmaan show {state.project.id}`, "
                    "or pass --replace to archive it and plan afresh.")
            archive = self._root / "archive" / "projects"
            archive.mkdir(parents=True, exist_ok=True)
            n = 1
            while (archive / f"{state.project.id}.{n}.json").exists():
                n += 1
            archived = archive / f"{state.project.id}.{n}.json"
            os.replace(target, archived)
        return self.save(state), archived

    @staticmethod
    def _sealed_from(target: Path, entries: int) -> int:
        """Where sealing began for this project: carried from the file being overwritten, 0 for a new one.

        A file with no seal (saved before M51) was never bound, so sealing begins at its last audit entry; for
        a file that cannot be read at all, at the state's own last entry (``entries``).
        """
        if not target.exists():
            return 0
        try:
            old = json.loads(target.read_text(encoding="utf-8"))
        except ValueError:
            return entries
        if not isinstance(old, dict):
            return entries
        seal = old.get("seal")
        if isinstance(seal, dict) and isinstance(seal.get("sealed_from"), int):
            return seal["sealed_from"]
        audit = old.get("audit")
        return len(audit) if isinstance(audit, list) else entries

    def _resolve(self, project_id: str) -> Path:
        path = self.path(project_id)
        if not path.exists():
            matches = sorted(self._dir.glob(f"{project_id}*.json")) if self._dir.exists() else []
            if len(matches) != 1:
                raise KeyError(f"Unknown project {project_id!r}")
            path = matches[0]
        return path

    @staticmethod
    def _read_path(path: Path) -> tuple[ProjectState, Integrity]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ValueError(f"{path} is not readable JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{path} is not a saved project")
        status, problems, sealed_from = _check_seal(data)
        state = ProjectState.model_validate(_pre_m48({k: v for k, v in data.items() if k != "seal"}))
        problems = verify_chain(state.audit) + problems
        return state, Integrity(BROKEN if problems else status, tuple(problems), sealed_from)

    def read(self, project_id: str) -> tuple[ProjectState, Integrity]:
        """The saved state and what could be verified about it. Never refuses a tampered file: reports it."""
        return self._read_path(self._resolve(project_id))

    def load(self, project_id: str, verify: bool = True) -> ProjectState:
        """The saved state, refused if its audit chain or seal fails.

        ``verify=False`` is for readers that report a broken chain themselves (the export).
        """
        state, integrity = self.read(project_id)
        if verify and not integrity.verified:
            raise ValueError(f"Project {project_id} failed audit verification: {integrity.problems[0]}")
        return state

    def list(self) -> Listing:
        """Every saved project; a file that cannot be read is listed in ``unreadable``, never skipped."""
        if not self._dir.exists():
            return Listing([], [], {})
        found, unreadable, integrity = [], [], {}
        for path in sorted(self._dir.glob("*.json")):
            try:
                state, checked = self._read_path(path)
            except ValueError as exc:
                unreadable.append(Unreadable(path, str(exc).splitlines()[0]))
                continue
            found.append(state)
            integrity[state.project.id] = checked
        return Listing(found, unreadable, integrity)

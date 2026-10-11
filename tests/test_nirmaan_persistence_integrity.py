"""M51: persistence integrity. Planning never destroys a saved project, the saved records are bound to the
audit chain, and a save is atomic.

Each test here began as an audit probe that passed against v1.24.0 (it showed the bug):

* C3 (audit A) and B1 (audit C): planning the same requirement again overwrote the saved project, its work and
  its whole audit trail, from the CLI, ``demo --save``, and MCP ``plan_project`` (which also ignored
  ``save: false``).
* H3 (audit A): editing the saved file's records (erasing ``model_calls`` to reset the budget, marking a task
  completed) loaded cleanly, because the hash chain covered only the audit entries.
* M3 (audit A): the file was written in place, so an interrupted save could truncate it, and ``list`` skipped an
  unreadable file without a word.
* L6 (audit A): ``schema_version`` stayed "1" through two data migrations.
"""

from __future__ import annotations

import io
import json
import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from laws import imports

from nirmaan.cli import app
from nirmaan.demos import demo
from nirmaan.mcp import McpContext, NirmaanMcpServer
from nirmaan.models import Actor, ActorKind
from nirmaan.orchestrator import Orchestrator
from nirmaan.work import ProjectStore, TaskEngine
from nirmaan.work.budget import budget, over, spend
from nirmaan.work import store as store_module

FIXTURES = Path(__file__).parent / "fixtures"
OLD_PROJECT = FIXTURES / "projects" / "m28-tool-runs.json"
REGISTER_BLOCK = demo("8").requirement


def _cli(*args: str):
    return CliRunner().invoke(app, list(args))


def _saved(root: Path) -> dict:
    [path] = (root / "projects").glob("*.json")
    return json.loads(path.read_text(encoding="utf-8"))


# --- C3 / B1: planning again never destroys a saved project ---------------------------------------


def _plan_and_start(root: Path) -> tuple[str, Path, bytes]:
    """Probe p6: plan, start the first task, and return the project, its file and the file's bytes."""
    result = _cli("plan", REGISTER_BLOCK, "--root", str(root))
    assert result.exit_code == 0, result.output
    data = _saved(root)
    project = data["project"]["id"]
    owner = data["tasks"][f"{project}:requirements"]["owner"]
    result = _cli("task", "start", project, "requirements", "--as", owner, "--root", str(root))
    assert result.exit_code == 0, result.output
    path = root / "projects" / f"{project}.json"
    return project, path, path.read_bytes()


def test_planning_the_same_requirement_again_is_refused_and_changes_nothing(tmp_path):
    project, path, before = _plan_and_start(tmp_path)
    result = _cli("plan", REGISTER_BLOCK, "--root", str(tmp_path))
    assert result.exit_code == 1
    assert f"{project} already exists" in result.output and "--replace" in result.output
    assert f"nirmaan show {project}" in result.output
    assert path.read_bytes() == before
    assert _saved(tmp_path)["tasks"][f"{project}:requirements"]["status"] == "in_progress"


def test_the_first_plan_still_saves_and_no_save_never_checks(tmp_path):
    result = _cli("plan", REGISTER_BLOCK, "--root", str(tmp_path))
    assert result.exit_code == 0 and "saved prj-" in result.output
    again = _cli("plan", REGISTER_BLOCK, "--no-save", "--root", str(tmp_path))
    assert again.exit_code == 0, again.output  # a read: nothing is written, so nothing is at risk


def test_replace_archives_the_old_project_whole_and_it_still_verifies(tmp_path):
    project, path, before = _plan_and_start(tmp_path)
    result = _cli("plan", REGISTER_BLOCK, "--replace", "--root", str(tmp_path))
    assert result.exit_code == 0, result.output
    archived = tmp_path / "archive" / "projects" / f"{project}.1.json"
    assert archived.read_bytes() == before
    assert f"archived the previous {project}" in result.output and str(archived) in result.output
    assert _saved(tmp_path)["tasks"][f"{project}:requirements"]["status"] == "ready"
    # The archived project is a project store of its own: its chain and seal verify.
    shown = _cli("audit", f"{project}.1", "--root", str(tmp_path / "archive"))
    assert shown.exit_code == 0 and "chain intact" in shown.output, shown.output
    _cli("plan", REGISTER_BLOCK, "--replace", "--root", str(tmp_path))
    assert (tmp_path / "archive" / "projects" / f"{project}.2.json").is_file()


def test_demo_save_is_refused_over_a_planned_project(tmp_path):
    _project, path, before = _plan_and_start(tmp_path)
    result = _cli("demo", "8", "--save", "--root", str(tmp_path))
    assert result.exit_code == 1 and "already exists" in result.output
    assert path.read_bytes() == before
    assert _cli("demo", "8", "--save", "--replace", "--root", str(tmp_path)).exit_code == 0


def test_the_store_refuses_to_create_over_a_project(tmp_path, nirmaan_org):
    store = ProjectStore(tmp_path)
    engine = Orchestrator(nirmaan_org).plan(REGISTER_BLOCK)
    path, archived = store.create(engine.state)
    assert archived is None and store.exists(engine.state.project.id)
    with pytest.raises(store_module.ProjectExistsError, match="already exists"):
        store.create(Orchestrator(nirmaan_org).plan(REGISTER_BLOCK).state)


@pytest.fixture()
def mcp(nirmaan_org, tmp_path):
    from veritriage.workspace import WorkspaceServices

    from nirmaan.integrations.veritriage import AutomationBridge

    bridge = AutomationBridge(WorkspaceServices(session_root=tmp_path / "sessions"))
    server = NirmaanMcpServer(McpContext(nirmaan_org, ProjectStore(tmp_path / "nirmaan"), bridge.publish,
                                         bridge.recent), io.StringIO(), io.StringIO())

    def call(name, **arguments):
        line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": arguments}})
        result = server.handle_line(line)["result"]
        text = result["content"][0]["text"]
        return (text if result["isError"] else json.loads(text)), result["isError"]

    return call, tmp_path / "nirmaan"


def test_mcp_plan_project_honors_save_false(mcp):
    call, root = mcp
    plan, is_error = call("plan_project", requirement=REGISTER_BLOCK, save=False)
    assert not is_error and plan["saved"] is False
    assert not (root / "projects").exists() or not list((root / "projects").glob("*.json"))


def test_mcp_plan_project_refuses_to_overwrite_and_replace_archives(mcp):
    call, root = mcp
    plan, _ = call("plan_project", requirement=REGISTER_BLOCK)
    project = plan["project"]
    owner = next(t["owner"] for t in plan["tasks"] if t["id"] == f"{project}:requirements")
    _, is_error = call("start_task", project=project, task="requirements", role=owner)
    assert not is_error
    path = root / "projects" / f"{project}.json"
    before = path.read_bytes()
    message, is_error = call("plan_project", requirement=REGISTER_BLOCK)
    assert is_error and "already exists" in message and "replace" in message
    assert path.read_bytes() == before
    again, _ = call("plan_project", requirement=REGISTER_BLOCK, save=False)  # a read never checks
    assert again["saved"] is False and path.read_bytes() == before
    replaced, is_error = call("plan_project", requirement=REGISTER_BLOCK, replace=True)
    assert not is_error and replaced["archived"].endswith(f"{project}.1.json")
    assert Path(replaced["archived"]).read_bytes() == before


# --- H3: the saved records are sealed to the audit chain --------------------------------------------


def _spent_project(org, root: Path) -> tuple[ProjectStore, str, Path]:
    """Probe p5's project: a two-call budget, both calls made, saved."""
    engine = Orchestrator(org).plan("Add a QoS feature to the NoC router.")
    pid = engine.state.project.id
    owner = engine.task(f"{pid}:requirements-delta").owner
    engine.set_budget(Actor(role=owner, kind=ActorKind.HUMAN), calls=2, cost_usd=None, reason="probe")
    for _ in range(2):
        engine.record_model_call(f"{pid}:requirements-delta", Actor(role=owner),
                                 {"purpose": "work", "provider": "x", "model": "m", "succeeded": True})
    assert over(engine.state, budget(engine.state), 1)
    store = ProjectStore(root)
    return store, pid, store.save(engine.state)


def _edit(path: Path, change) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_erasing_the_spend_in_the_file_is_detected(nirmaan_org, tmp_path):
    store, pid, path = _spent_project(nirmaan_org, tmp_path)
    _edit(path, lambda d: d.update(model_calls={}))
    with pytest.raises(ValueError, match="edited outside the engine"):
        store.load(pid)


def test_marking_a_task_completed_in_the_file_is_detected(nirmaan_org, tmp_path):
    store, pid, path = _spent_project(nirmaan_org, tmp_path)

    def done(d):
        task = d["tasks"][f"{pid}:microarchitecture"]
        task["status"], task["approval_state"] = "completed", "granted"

    _edit(path, done)
    with pytest.raises(ValueError, match="edited outside the engine"):
        store.load(pid)


def test_an_untouched_file_loads_sealed_and_keeps_working(nirmaan_org, tmp_path):
    store, pid, path = _spent_project(nirmaan_org, tmp_path)
    state, integrity = store.read(pid)
    assert integrity.status == "sealed" and integrity.problems == () and integrity.sealed_from == 0
    assert spend(state).calls == 2
    engine = TaskEngine(nirmaan_org, store.load(pid))
    engine.start(f"{pid}:requirements-delta", Actor(role=engine.task(f"{pid}:requirements-delta").owner))
    store.save(engine.state)
    assert store.read(pid)[1].status == "sealed"


@pytest.mark.parametrize("change,why", [
    (lambda d: d.pop("seal"), "has no seal"),
    (lambda d: d["seal"].update(entries=1), "the seal covers"),
    (lambda d: d["audit"].pop(), "the seal covers"),
    (lambda d: d["seal"].update(format=99), "unknown seal format"),
])
def test_a_removed_or_moved_seal_is_detected(nirmaan_org, tmp_path, change, why):
    store, pid, path = _spent_project(nirmaan_org, tmp_path)
    _edit(path, change)
    _state, integrity = store.read(pid)
    assert integrity.status == "broken" and any(why in p for p in integrity.problems), integrity.problems
    with pytest.raises(ValueError):
        store.load(pid)


def test_a_tampered_project_loads_only_when_asked_and_the_views_say_so_loudly(nirmaan_org, tmp_path):
    _store, pid, path = _spent_project(nirmaan_org, tmp_path)
    _edit(path, lambda d: d.update(model_calls={}))
    refused = _cli("status", pid, "--root", str(tmp_path))
    assert refused.exit_code == 1 and "edited outside the engine" in refused.output
    assert "--unverified" in refused.output
    for view in ("status", "show", "audit"):
        shown = _cli(view, pid, "--unverified", "--root", str(tmp_path))
        assert shown.exit_code == 0, shown.output
        assert "UNVERIFIED PROJECT RECORDS" in shown.output, view
    as_json = _cli("status", pid, "--unverified", "--json", "--root", str(tmp_path))
    assert json.loads(as_json.output)["records"]["status"] == "broken"
    # A command that changes state never takes a tampered project, flag or not.
    task = _cli("task", "start", pid, "requirements-delta", "--as", "x", "--root", str(tmp_path))
    assert task.exit_code == 1 and "edited outside the engine" in task.output


def test_the_export_marks_tampered_records_loudly(nirmaan_org, tmp_path):
    _store, pid, path = _spent_project(nirmaan_org, tmp_path)
    _edit(path, lambda d: d.update(model_calls={}))
    out = tmp_path / "out"
    result = _cli("export", pid, "--out", str(out), "--root", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert "PROJECT RECORDS FAILED VERIFICATION" in result.output
    index = (out / "INDEX.md").read_text(encoding="utf-8").splitlines()
    assert any("PROJECT RECORDS FAILED VERIFICATION" in line for line in index[:6])


def test_the_seal_is_computed_by_the_store_never_by_an_engine_operation():
    """M32's per-operation cost is untouched: only the store hashes the records, once per save or load."""
    src = Path(__file__).parent.parent / "src" / "nirmaan"
    users = {p.relative_to(src).as_posix() for p in src.rglob("*.py") if "records_digest" in p.read_text("utf-8")}
    assert users == {"work/store.py"}
    for module in ("engine.py", "policy.py", "audit.py"):
        assert not {m for m in imports(src / "work" / module) if m.startswith("nirmaan.work.store")}, module


# --- Old projects: pre-sealing ---------------------------------------------------------------------


def _old_store(root: Path) -> tuple[ProjectStore, str]:
    project = json.loads(OLD_PROJECT.read_text())["project"]["id"]
    (root / "projects").mkdir(parents=True)
    shutil.copy(OLD_PROJECT, root / "projects" / f"{project}.json")
    return ProjectStore(root), project


def test_a_project_saved_before_sealing_loads_marked_pre_sealing(tmp_path):
    store, project = _old_store(tmp_path)
    state, integrity = store.read(project)
    assert integrity.status == "pre-sealing" and integrity.problems == ()
    assert "saved before" in integrity.describe()
    assert store.load(project).project.id == project  # it still loads
    status = _cli("status", project, "--root", str(tmp_path))
    assert status.exit_code == 0 and "pre-sealing" in status.output


def test_saving_an_old_project_seals_it_and_remembers_where_sealing_began(tmp_path):
    store, project = _old_store(tmp_path)
    entries = len(json.loads(OLD_PROJECT.read_text())["audit"])
    path = store.save(store.load(project))
    saved = json.loads(path.read_text())
    assert saved["schema_version"] == store_module.SCHEMA_VERSION == "2"
    _state, integrity = store.read(project)
    assert integrity.status == "sealed" and integrity.sealed_from == entries
    assert f"from audit entry {entries}" in integrity.describe()
    # Sealing begins once: later saves carry it, so the old records stay marked as never bound.
    assert store.save(store.load(project)).read_text() == path.read_text()


def test_a_downgraded_file_is_never_reported_sealed(nirmaan_org, tmp_path):
    store, pid, path = _spent_project(nirmaan_org, tmp_path)

    def downgrade(d):
        d.pop("seal")
        d["schema_version"] = "1"
        d["model_calls"] = {}

    _edit(path, downgrade)
    assert store.read(pid)[1].status == "pre-sealing"  # loads, but never as sealed
    store.save(store.load(pid))
    integrity = store.read(pid)[1]
    assert integrity.sealed_from == len(store.load(pid).audit) and integrity.sealed_from > 0


# --- M3: an atomic save, and a listing that reports what it cannot read ------------------------------


def test_an_interrupted_save_leaves_the_previous_file_whole(nirmaan_org, tmp_path, monkeypatch):
    store, pid, path = _spent_project(nirmaan_org, tmp_path)
    before = path.read_bytes()
    engine = TaskEngine(nirmaan_org, store.load(pid))
    engine.start(f"{pid}:requirements-delta", Actor(role=engine.task(f"{pid}:requirements-delta").owner))

    def crash(_fd):
        raise OSError("disk full")

    monkeypatch.setattr(os, "fsync", crash)
    with pytest.raises(OSError, match="disk full"):
        store.save(engine.state)
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == [path.name]  # no temporary file left behind


def test_list_reports_an_unreadable_project(nirmaan_org, tmp_path):
    store, pid, path = _spent_project(nirmaan_org, tmp_path)
    (path.parent / "prj-truncated.json").write_text('{"project": {"id": "prj-trunc', encoding="utf-8")
    listing = store.list()
    assert [s.project.id for s in listing] == [pid]
    [bad] = listing.unreadable
    assert bad.path.name == "prj-truncated.json" and bad.reason
    result = _cli("projects", "--root", str(tmp_path))
    assert result.exit_code == 1 and "prj-truncated.json" in result.output and "unreadable" in result.output


def test_list_shows_each_project_s_records_status(nirmaan_org, tmp_path):
    store, pid, path = _spent_project(nirmaan_org, tmp_path)
    _edit(path, lambda d: d.update(model_calls={}))
    listing = store.list()
    assert listing.integrity[pid].status == "broken"
    assert "BROKEN" in _cli("projects", "--root", str(tmp_path)).output


def test_a_new_state_is_already_in_the_current_schema():
    from nirmaan.models import ProjectState

    assert ProjectState.model_fields["schema_version"].default == store_module.SCHEMA_VERSION

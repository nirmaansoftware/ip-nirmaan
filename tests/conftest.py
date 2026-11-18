"""Shared pytest fixtures."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

#: M79: the SKY130 pilot runs only in its own workflow (.github/workflows/pd-sky130.yml), which sets
#: NIRMAAN_PD_PILOT and installs Magic, Netgen, and the PDK files. Elsewhere it is not collected, so the
#: required jobs neither run nor skip it (scripts/check_test_union.py). docs/PD_SKY130_PILOT.md.
#: M81: the GF180MCU pilot likewise, in pd-gf180.yml (docs/PD_GF180_PILOT.md); M82: the IHP SG13G2 pilot, in
#: pd-ihp.yml (docs/PD_IHP_PILOT.md).
collect_ignore = [] if os.environ.get("NIRMAAN_PD_PILOT") else ["test_pd_sky130_pilot.py", "test_pd_gf180_pilot.py",
                                                                "test_pd_ihp_pilot.py"]


# --- CI shards (scripts/shards.py) -----------------------------------------------------


def pytest_addoption(parser):
    group = parser.getgroup("shards", "CI shards (scripts/shards.py)")
    group.addoption("--shard", metavar="K/N", default=None, help="run only the test files of shard K of N")
    group.addoption("--shard-profile", default="test", help="which weights in scripts/shard_weights.json balance the shards")
    group.addoption("--shard-manifest", metavar="PATH", default=None, help="write what was collected and kept, as JSON")


def _shards():
    import importlib.util

    spec = importlib.util.spec_from_file_location("shards", Path(__file__).resolve().parents[1] / "scripts" / "shards.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    """With --shard K/N, keep only shard K's files (after every other selection, so all shards split one list)."""
    spec = config.getoption("--shard")
    if not spec:
        return
    shards = _shards()
    try:
        k, n = shards.parse(spec)
    except ValueError as error:
        raise pytest.UsageError(str(error)) from None
    record = shards.manifest([item.nodeid for item in items], k, n, config.getoption("--shard-profile"))
    path = config.getoption("--shard-manifest")
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # O_NOFOLLOW: a symlink planted at the path fails the write instead of redirecting it.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(record, indent=1) + "\n")
    keep = set(record["selected"])
    dropped = [item for item in items if item.nodeid not in keep]
    if dropped:
        config.hook.pytest_deselected(items=dropped)
    items[:] = [item for item in items if item.nodeid in keep]


@pytest.fixture(autouse=True, scope="session")
def _wide_cli_consoles():
    """M46: one fixed, wide width for the CLIs' rich consoles.

    A console takes its width from COLUMNS or the terminal (else 80) and wraps
    output to fit, so an assertion on CLI output passed or failed with the
    terminal and the temp path length. Fixed here, it depends on neither.
    """
    from nirmaan import cli as nirmaan_cli
    from veritriage.cli import main as veritriage_cli

    for console in (nirmaan_cli.console, nirmaan_cli._err, veritriage_cli.console, veritriage_cli._err):
        console.width = 1000


@pytest.fixture(autouse=True, scope="session")
def _temporary_root(tmp_path_factory):
    """M88: every temporary folder the suite makes in this process (tool runs, eval sandboxes) goes in one
    folder inside pytest's own base folder, removed when the session ends; NIRMAAN_KEEP_RUN_DIRS keeps it.

    Pytest's base folder is made first, so it stays where pytest keeps it.
    """
    from nirmaan.integrations.eda import keep_run_dirs

    root = tmp_path_factory.getbasetemp() / "tmp"
    root.mkdir()
    before, tempfile.tempdir = tempfile.tempdir, str(root)
    try:
        yield root
    finally:
        tempfile.tempdir = before
        if not keep_run_dirs():
            shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(autouse=True)
def _temporary_runs():
    """M88: the temporary run directories a test makes are removed when it ends, as an eval trial's are."""
    from nirmaan.integrations.eda import temporary_runs

    with temporary_runs():
        yield


@pytest.fixture()
def fixture_log():
    """Return a resolver for a named fixture log."""

    def _get(name: str) -> Path:
        path = FIXTURES / name
        assert path.is_file(), f"missing fixture {name}"
        return path

    return _get


# --- IP Nirmaan (Milestone 19) ------------------------------------------------------


@pytest.fixture(scope="session")
def nirmaan_org():
    """The built, validated IP Nirmaan organization (immutable, so shared)."""
    from nirmaan.company import build_organization

    return build_organization()


@pytest.fixture()
def fixed_clock():
    """A frozen clock, so audit trails and project state are reproducible."""
    from datetime import datetime, timezone

    return lambda: datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def registries():
    """M49: a fresh registry scope for one test; what it registers is gone when the test ends."""
    from nirmaan.registry import Registries

    with Registries.scoped() as scope:
        yield scope

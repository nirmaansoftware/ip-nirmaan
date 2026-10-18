"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


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
        Path(path).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
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

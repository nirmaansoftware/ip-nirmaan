"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


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

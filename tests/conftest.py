"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def fixture_log():
    """Return a resolver for a named fixture log."""

    def _get(name: str) -> Path:
        path = FIXTURES / name
        assert path.is_file(), f"missing fixture {name}"
        return path

    return _get


# --- Nirmaan IP (Milestone 19) ------------------------------------------------------


@pytest.fixture(scope="session")
def nirmaan_org():
    """The built, validated Nirmaan IP organization (immutable, so shared)."""
    from nirmaan.company import build_organization

    return build_organization()


@pytest.fixture()
def fixed_clock():
    """A frozen clock, so audit trails and project state are reproducible."""
    from datetime import datetime, timezone

    return lambda: datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)

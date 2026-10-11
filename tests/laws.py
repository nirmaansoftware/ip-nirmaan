"""Helpers the suite's laws share (M46): one copy of each, so they cannot drift.

``imports`` reads what a source file imports, for the import laws (VeriTriage
never imports Nirmaan; only the bridge imports VeriTriage; vocabularies stay
plain data). ``needs`` gates a test on real executables: it skips when one is
missing, unless CI names it in ``NIRMAAN_REQUIRE_EDA``, and then the test runs
and fails, so a missing tool in CI is red, never a silent skip.
"""

from __future__ import annotations

import ast
import os
import shutil
from pathlib import Path

import pytest


def imports(path: Path) -> set[str]:
    """Every module a file imports, anywhere in it, plus ``module.name`` for each ``from module import name``.

    It reads the AST, so prose in comments and docstrings can name modules
    without tripping a law. Relative imports with no module are not listed.
    """
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def needs(*executables: str, any_of: tuple[str, ...] = ()):
    """Skip without the executables (and, with ``any_of``, without any one of those), unless CI requires them.

    A missing ``any_of`` group is reported, and matched against
    ``NIRMAAN_REQUIRE_EDA``, by its first name.
    """
    required = set(os.environ.get("NIRMAAN_REQUIRE_EDA", "").replace(",", " ").split())
    missing = [e for e in executables if shutil.which(e) is None]
    if any_of and not any(shutil.which(e) for e in any_of):
        missing.append(any_of[0])
    skip = bool(missing) and not required.intersection(missing)
    return pytest.mark.skipif(skip, reason=f"not on PATH: {', '.join(missing)}")

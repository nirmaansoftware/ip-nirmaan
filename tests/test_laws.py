"""M46: the suite's shared helpers have one copy, and ``needs`` keeps its contract.

``needs`` skips a real-tool test when an executable is missing and fails it
instead when CI requires that executable, so a missing tool in CI is red. The
no-tools CI job depends on that: every test passes or skips there, none errors.
"""

from __future__ import annotations

import ast
from pathlib import Path

from laws import imports, needs

TESTS = Path(__file__).parent
SHARED = {"_imports", "imports", "needs", "_needs"}
ABSENT = "nirmaan-no-such-tool"


def test_each_shared_helper_has_one_copy():
    defined = {}
    for path in sorted(TESTS.glob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef) and node.name in SHARED:
                defined.setdefault(node.name.lstrip("_"), []).append(path.name)
    assert defined == {"imports": ["laws.py"], "needs": ["laws.py"]}


def test_imports_lists_modules_and_imported_names_but_not_prose(tmp_path):
    source = tmp_path / "m.py"
    source.write_text('"""Mentions veritriage.engine in prose."""\nimport os.path\n'
                      "from nirmaan.models import Actor\nfrom . import sibling\n"
                      "def f():\n    import json\n", encoding="utf-8")
    assert imports(source) == {"os.path", "nirmaan.models", "nirmaan.models.Actor", "json"}


def test_needs_skips_a_missing_tool(monkeypatch):
    monkeypatch.delenv("NIRMAAN_REQUIRE_EDA", raising=False)
    mark = needs("sh", ABSENT)
    assert mark.args == (True,) and mark.kwargs["reason"] == f"not on PATH: {ABSENT}"
    assert needs("sh").args == (False,)


def test_needs_runs_a_required_tool_so_its_absence_fails(monkeypatch):
    monkeypatch.setenv("NIRMAAN_REQUIRE_EDA", f"verilator,{ABSENT}")
    assert needs(ABSENT).args == (False,)


def test_needs_any_of_wants_one_of_a_group_named_by_its_first(monkeypatch):
    monkeypatch.delenv("NIRMAAN_REQUIRE_EDA", raising=False)
    assert needs(any_of=(ABSENT, "sh")).args == (False,)
    mark = needs(any_of=(ABSENT, ABSENT + "-2"))
    assert mark.args == (True,) and mark.kwargs["reason"] == f"not on PATH: {ABSENT}"
    monkeypatch.setenv("NIRMAAN_REQUIRE_EDA", ABSENT)
    assert needs(any_of=(ABSENT, ABSENT + "-2")).args == (False,)

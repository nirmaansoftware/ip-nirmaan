"""Milestone 64: worked examples run inside the existing CI jobs, within a budget.

Each ``examples/<name>/example.json`` lists tool runs over committed fixtures,
each with the outcome it must have. The runs go through the tool bindings
(``src/nirmaan/integrations/eda.py``) via the broker, and a step passes or fails
on the run's own result, never on matching printed text. Every example declares
``budget_seconds``; together they add at most ``JOB_LIMIT_SECONDS`` to the one
job that runs this file. The examples need real tools, so they skip where a
tool is absent, except the tools CI names in ``NIRMAAN_REQUIRE_EDA``. Design:
``docs/WORKED_EXAMPLES.md``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from laws import needs
from test_nirmaan_eda import BRIDGE, invoke

from nirmaan.orchestrator import Orchestrator

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
JOB_LIMIT_SECONDS = 300
EXPECT = {"pass": True, "fail": False}
FILE_PARAMS = ("sources", "sby")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def example_files() -> list[Path]:
    return sorted(EXAMPLES.glob("*/example.json"))


def problems(example: dict, root: Path = ROOT) -> list[str]:
    """What is wrong with one example's declaration (empty when it is well formed)."""
    found = []
    budget = example.get("budget_seconds")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        found.append("budget_seconds must be a positive whole number")
    if not str(example.get("title", "")).strip():
        found.append("no title")
    fixture = root / str(example.get("fixture", ""))
    if not example.get("fixture") or not fixture.is_dir():
        found.append(f"fixture folder not found: {example.get('fixture')}")
    steps = example.get("steps") or []
    if not steps:
        found.append("no steps")
    for i, step in enumerate(steps):
        if step.get("expect") not in EXPECT:
            found.append(f"step {i}: expect must be pass or fail")
        if not step.get("needs"):
            found.append(f"step {i}: needs names no executable")
        for key in FILE_PARAMS:
            for name in filter(None, str(step.get("params", {}).get(key, "")).split(",")):
                if not (fixture / name).is_file():
                    found.append(f"step {i}: {key} file not found: {name}")
    return found


def over_budget(examples: list[dict], limit: int = JOB_LIMIT_SECONDS) -> int:
    """Seconds by which the declared budgets exceed the job limit (0 when within it)."""
    return max(0, sum(e["budget_seconds"] for e in examples) - limit)


def resolved(step: dict, fixture: Path) -> dict[str, str]:
    params = dict(step["params"])
    for key in FILE_PARAMS:
        if key in params:
            params[key] = ",".join(str(fixture / n) for n in params[key].split(","))
    return params


# --- The declarations (no tool needed) ---------------------------------------------------


def test_there_is_at_least_one_example():
    assert example_files(), "examples/ holds no example.json"


@pytest.mark.parametrize("path", example_files(), ids=lambda p: p.parent.name)
def test_each_example_is_well_formed(path):
    assert problems(load(path)) == []
    assert (path.parent / "README.md").is_file()


def test_the_examples_fit_the_job_budget():
    assert over_budget([load(p) for p in example_files()]) == 0


def test_an_over_budget_set_fails_the_budget_check():
    examples = [{"budget_seconds": 200}, {"budget_seconds": 150}]
    assert over_budget(examples) == 50
    assert over_budget(examples[:1]) == 0


def test_a_bad_declaration_is_reported():
    bad = {"title": "", "fixture": "tests/fixtures/rtl/sync_fifo", "budget_seconds": 0,
           "steps": [{"tool": "lint.run", "needs": [], "expect": "maybe",
                      "params": {"sources": "missing.v"}}]}
    found = problems(bad)
    assert "budget_seconds must be a positive whole number" in found
    assert "no title" in found
    assert any("expect must be pass or fail" in f for f in found)
    assert any("needs names no executable" in f for f in found)
    assert any("missing.v" in f for f in found)


# --- The runs (real tools) ---------------------------------------------------------------


def _run_params():
    for path in example_files():
        example = load(path)
        tools = sorted({t for step in example["steps"] for t in step["needs"]})
        yield pytest.param(path, id=path.parent.name, marks=needs(*tools))


@pytest.fixture()
def bridge(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)


@pytest.mark.parametrize("path", list(_run_params()))
def test_each_example_runs_as_declared_within_its_budget(bridge, tmp_path, path):
    example = load(path)
    fixture = ROOT / example["fixture"]
    start = time.monotonic()
    for i, step in enumerate(example["steps"]):
        run, _ = invoke(bridge, step["tool"], resolved(step, fixture), tmp_path / f"step{i}")
        assert run.id in bridge.state.tool_runs, f"step {i}: the run was not recorded"
        assert run.succeeded is EXPECT[step["expect"]], f"step {i} ({step['tool']}): {run.summary}"
    elapsed = time.monotonic() - start
    assert elapsed <= example["budget_seconds"], f"took {elapsed:.0f} s, budget {example['budget_seconds']} s"

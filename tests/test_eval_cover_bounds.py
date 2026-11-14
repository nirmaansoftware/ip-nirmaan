"""Cover bounds on the must-fail scorer (wave 2, W2-E5), judged with synthetic tool results.

A check's ``cover_bounds`` are metric bounds (the M48 text form) the ``cover_tool`` run is checked against, as a
requirement's bounds are. These tests use a stand-in tool handle that returns made-up outcomes: no case, no real
tool and no measured figure is involved.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from nirmaan.evals import load_cases
from nirmaan.evals.cases import case_digest
from nirmaan.evals.scorers import ScoreContext, scorer_spec
from nirmaan.models import HeldOutCheck, ScoreStatus
from nirmaan.models.workflow import Bound

REPO = Path(__file__).resolve().parents[1]


class FakeTools:
    """Records every invoke and answers from a script: the cover run fails when it was given any bound."""

    def __init__(self, cover_meets: bool = True):
        self.calls: list[tuple[str, tuple[Bound, ...]]] = []
        self.cover_meets = cover_meets

    def invoke(self, tool_id, bounds=(), **params):
        self.calls.append((tool_id, tuple(bounds)))
        run_id = f"run-{len(self.calls)}"
        if tool_id == "cover.tool":
            ok = self.cover_meets or not bounds
            return run_id, SimpleNamespace(succeeded=ok, summary="covers" if ok else "limit not met", references=("log",))
        # The mutant runs fail on a check, having run and written a log.
        mutant = any("mutant" in str(v) for v in params.values())
        return run_id, SimpleNamespace(succeeded=not mutant, summary="x", references=("log",))


def _judge(tmp_path, tools, **fields):
    clean = tmp_path / "dut.v"
    clean.write_text("module m; endmodule\n")
    mutant = tmp_path / "mutant.v"
    mutant.write_text("module m; wire x; endmodule\n")
    check = HeldOutCheck(name="n", scorer="must-fail", tool="main.tool", cover_tool="cover.tool",
                         case_files={"files": [str(clean)]}, mutants={str(clean): [str(mutant)]}, **fields)
    ctx = ScoreContext(SimpleNamespace(state=SimpleNamespace(artifacts={}, tool_runs={})),
                       SimpleNamespace(id="t", artifacts=[]), check, tmp_path, tools, tmp_path / "work")
    return scorer_spec("must-fail").fn(ctx)


def test_the_bounds_go_to_the_cover_run_only(tmp_path):
    tools = FakeTools()
    score = _judge(tmp_path, tools, cover_bounds=("line>=90", "toggle>=75"))
    assert score.status is ScoreStatus.PASSED, score.summary
    expected = (Bound.parse("line>=90"), Bound.parse("toggle>=75"))
    by_tool = {tool: bounds for tool, bounds in tools.calls}
    assert by_tool["cover.tool"] == expected
    assert by_tool["main.tool"] == ()  # the clean and every mutant run carry no bounds
    assert [b for t, b in tools.calls if t == "main.tool"] == [(), ()]


def test_a_cover_run_that_misses_the_bounds_is_covers_not_reached(tmp_path):
    tools = FakeTools(cover_meets=False)
    score = _judge(tmp_path, tools, cover_bounds=("line>=90",))
    assert score.status is ScoreStatus.FAILED
    assert score.summary.startswith("covers not reached on the clean inputs: cover.tool"), score.summary
    assert [t for t, _ in tools.calls] == ["main.tool", "cover.tool"]  # no mutant ran


def test_a_check_without_bounds_runs_the_cover_tool_as_before(tmp_path):
    tools = FakeTools(cover_meets=False)  # fails only when bounds are given
    score = _judge(tmp_path, tools)
    assert score.status is ScoreStatus.PASSED, score.summary
    assert all(bounds == () for _, bounds in tools.calls)


def test_a_check_without_cover_bounds_dumps_as_it_always_did():
    """No case digest changes: the new field is left out of a dump while it is empty."""
    plain = HeldOutCheck(name="n", scorer="must-fail", tool="simulator.run", cover_tool="formal.cover")
    assert "cover_bounds" not in plain.model_dump() and "cover_bounds" not in plain.model_dump(mode="json")
    bounded = HeldOutCheck(name="n", scorer="must-fail", cover_bounds=("line>=90",))
    assert bounded.model_dump(mode="json")["cover_bounds"] == ["line>=90"]
    assert HeldOutCheck.model_validate(bounded.model_dump(mode="json")) == bounded


def test_a_cover_bound_must_read_as_a_bound():
    with pytest.raises(ValueError, match="needs a number|reads metric"):
        HeldOutCheck(name="n", cover_bounds=("line>=lots",))
    with pytest.raises(ValueError, match="reads metric"):
        HeldOutCheck(name="n", cover_bounds=("line",))


def test_no_shipped_case_dump_carries_cover_bounds():
    for case in load_cases(REPO / "evals"):
        assert all("cover_bounds" not in h.model_dump(mode="json") for h in case.held_out), case.id
        assert case_digest(case, REPO)

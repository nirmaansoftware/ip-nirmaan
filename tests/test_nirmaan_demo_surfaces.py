"""Milestone 54: what a demo audience reads is plain text, not Python.

Audit C found raw reprs and JSON dicts in everyday commands (``task escalate``,
``status``, ``workflows``), a quoted ``KeyError`` for an unknown project, and
``gaps`` reporting "0 of 0" as if that were a result. Each test runs the real
CLI on a freshly planned project. No test calls a model API.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from nirmaan.cli import app
from nirmaan.work import ProjectStore

AXI_BLOCK = "Create an AXI4-Lite register block."
RAW = ("EscalationKind.", "EscalationState.", "<", "{\"", "{'", "('")


@pytest.fixture
def planned(tmp_path):
    runner = CliRunner()
    result = runner.invoke(app, ["plan", AXI_BLOCK, "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    state = ProjectStore(tmp_path).list()[0]
    return runner, tmp_path, state


def test_escalate_prints_one_readable_line(planned):
    runner, root, state = planned
    task = next(t for t in state.tasks.values() if t.stage == "requirements")
    result = runner.invoke(app, ["task", "escalate", state.project.id, "requirements", "need clocking answer",
                                 "--as", task.owner, "--kind", "uncertainty", "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert not any(r in result.output for r in RAW), result.output
    assert "esc-001" in result.output and "uncertainty" in result.output and "need clocking answer" in result.output


def test_status_sections_are_not_json(planned):
    runner, root, state = planned
    task = next(t for t in state.tasks.values() if t.stage == "requirements")
    runner.invoke(app, ["task", "escalate", state.project.id, "requirements", "need clocking answer",
                        "--as", task.owner, "--kind", "uncertainty", "--root", str(root)])
    result = runner.invoke(app, ["status", state.project.id, "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert "Escalations (1)" in result.output and "need clocking answer" in result.output
    assert not any(r in result.output for r in RAW), result.output


def test_workflow_conditions_are_not_python():
    result = CliRunner().invoke(app, ["workflows", "new-ip"])
    assert result.exit_code == 0, result.output
    assert "when " in result.output
    assert "{'" not in result.output and "('" not in result.output, result.output


@pytest.mark.parametrize("command", ["show", "status", "gaps", "export"])
def test_unknown_project_is_not_a_quoted_key_error(tmp_path, command):
    args = [command, "nope", "--root", str(tmp_path)]
    if command == "export":
        args += ["--out", str(tmp_path / "out")]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1
    assert "Unknown project 'nope'" in result.output and "\"Unknown" not in result.output, result.output


def test_gaps_with_no_requirements_says_so(planned):
    runner, root, state = planned
    result = runner.invoke(app, ["gaps", state.project.id, "--root", str(root)])
    assert "0 of 0" not in result.output
    assert "No requirements are recorded yet" in result.output and "nirmaan vplan import" in result.output

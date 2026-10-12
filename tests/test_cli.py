"""CLI tests: end-to-end `veritriage analyze` producing all artifacts."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from veritriage.cli.main import app

runner = CliRunner()


def _analyze(fixture_log, tmp_path, *names, extra=()):
    return runner.invoke(
        app,
        [
            "analyze",
            *(str(fixture_log(n)) for n in names),
            "-o",
            str(tmp_path),
            "--db",
            str(tmp_path / "regressions.db"),
            # Tests run inside the veritriage repo; live git context would make
            # outputs vary per commit, so CLI tests pin context off. The
            # engineering path has dedicated tests in test_engineering.py.
            "--no-context",
            *extra,
        ],
    )


def test_analyze_writes_json_graph_and_html(fixture_log, tmp_path):
    result = _analyze(fixture_log, tmp_path, "uvm_scoreboard.log")
    # Failing run: exit code 1 by design (CI gating), but artifacts exist.
    assert result.exit_code == 1, result.output

    data = json.loads((tmp_path / "analysis.json").read_text())
    assert data["schema_version"] == "14"
    assert data["classification"]["category"] == "testbench_failure"
    assert data["classification"]["confidence"] == 80
    assert data["classification"]["evidence"]
    assert data["classification"]["evidence"][0]["node_id"].startswith("ev-")

    # Reasoning output: ranked hypotheses with evidence and traceable confidence.
    hypotheses = data["reasoning"]["hypotheses"]
    assert hypotheses, "expected ranked hypotheses in analysis.json"
    assert hypotheses[0]["category"] == "testbench_issue"
    confidences = [h["confidence"] for h in hypotheses]
    assert confidences == sorted(confidences, reverse=True)
    assert all(h["evidence_ids"] for h in hypotheses)
    assert data["reasoning"]["recommendations"]
    assert "Hypotheses" in result.output

    # Regression intelligence: the run is recorded and the report knows it.
    assert data["history"]["regression_id"].startswith("reg-")
    assert data["history"]["seen_before"] is False
    assert "Seen before" in result.output

    graph = json.loads((tmp_path / "evidence_graph.json").read_text())
    assert graph["nodes"]
    assert all(node_id.startswith("ev-") for node_id in graph["nodes"])

    html = (tmp_path / "report.html").read_text()
    assert "Failure Classification" in html
    assert "Evidence Graph" in html
    assert "Historical Context" in html

    assert "Testbench Failure" in result.output


def test_analyze_second_run_sees_history(fixture_log, tmp_path):
    assert _analyze(fixture_log, tmp_path, "uvm_scoreboard.log").exit_code == 1
    result = _analyze(fixture_log, tmp_path, "uvm_scoreboard.log")
    assert result.exit_code == 1, result.output
    data = json.loads((tmp_path / "analysis.json").read_text())
    assert data["history"]["seen_before"] is True
    assert data["history"]["times_seen"] == 1
    assert data["history"]["similar"][0]["signature_match"] is True
    # The historical precedent shows up as an extra debugging step.
    actions = [r["action"] for r in data["reasoning"]["recommendations"]]
    assert any("Compare against regression" in a for a in actions)
    html = (tmp_path / "report.html").read_text()
    assert "Seen before" in html


def test_analyze_no_history_writes_no_database(fixture_log, tmp_path):
    result = _analyze(
        fixture_log, tmp_path, "uvm_scoreboard.log", extra=("--no-history",)
    )
    assert result.exit_code == 1, result.output
    assert not (tmp_path / "regressions.db").exists()
    data = json.loads((tmp_path / "analysis.json").read_text())
    assert data["history"] is None


def test_analyze_multiple_artifacts(fixture_log, tmp_path):
    result = _analyze(
        fixture_log, tmp_path, "uvm_scoreboard.log", "coverage.txt", "test_metadata.json"
    )
    assert result.exit_code == 1, result.output
    graph = json.loads((tmp_path / "evidence_graph.json").read_text())
    types = {n["artifact_type"] for n in graph["nodes"].values()}
    assert {"simulation_log", "coverage", "test_metadata"} <= types
    relations = {e["relation"] for e in graph["edges"]}
    assert "part_of" in relations
    assert "correlates_with" in relations


def test_analyze_clean_log_exits_zero(fixture_log, tmp_path):
    result = _analyze(fixture_log, tmp_path, "uvm_pass.log")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "analysis.json").is_file()
    assert (tmp_path / "evidence_graph.json").is_file()


def test_analyze_missing_file_errors(tmp_path):
    result = runner.invoke(
        app, ["analyze", str(tmp_path / "nope.log"), "-o", str(tmp_path), "--db", str(tmp_path / "r.db")]
    )
    assert result.exit_code == 2


def test_dashboard_command(fixture_log, tmp_path):
    _analyze(fixture_log, tmp_path, "uvm_scoreboard.log")
    result = runner.invoke(
        app,
        ["dashboard", "-o", str(tmp_path), "--db", str(tmp_path / "regressions.db")],
    )
    assert result.exit_code == 0, result.output
    html = (tmp_path / "dashboard.html").read_text()
    assert "Regression Intelligence Dashboard" in html
    assert "Recent Regressions" in html


def test_dashboard_without_database_errors(tmp_path):
    result = runner.invoke(
        app, ["dashboard", "-o", str(tmp_path), "--db", str(tmp_path / "none.db")]
    )
    assert result.exit_code == 2


def test_history_command(fixture_log, tmp_path):
    _analyze(fixture_log, tmp_path, "uvm_scoreboard.log")
    result = runner.invoke(app, ["history", "--db", str(tmp_path / "regressions.db")])
    assert result.exit_code == 0, result.output
    assert "Regression history" in result.output
    assert "1 total" in result.output
    assert "Testbench" in result.output  # cells may wrap in a narrow terminal


def test_feedback_command(fixture_log, tmp_path):
    _analyze(fixture_log, tmp_path, "uvm_scoreboard.log")
    data = json.loads((tmp_path / "analysis.json").read_text())
    regression_id = data["history"]["regression_id"]
    result = runner.invoke(
        app,
        [
            "feedback",
            regression_id,
            "--diagnosis",
            "correct",
            "--root-cause",
            "scoreboard predictor bug",
            "--db",
            str(tmp_path / "regressions.db"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "recorded feedback" in result.output


def test_feedback_rejects_unknown_regression(fixture_log, tmp_path):
    _analyze(fixture_log, tmp_path, "uvm_scoreboard.log")
    result = runner.invoke(
        app,
        ["feedback", "reg-nope", "--db", str(tmp_path / "regressions.db")],
    )
    assert result.exit_code == 2


def test_parsers_command_lists_all_artifact_parsers():
    result = runner.invoke(app, ["parsers"])
    assert result.exit_code == 0
    for name in ("simulation_log", "compile_log", "coverage", "test_metadata"):
        assert name in result.output


def test_version_command():
    import veritriage

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert veritriage.__version__ in result.output

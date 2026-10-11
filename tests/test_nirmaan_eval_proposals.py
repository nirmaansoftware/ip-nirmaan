"""Milestone 42: recorded evaluation results propose skill, model, or check changes; only a person decides.

Every result used here is a synthetic test fixture: the committed ones under
``tests/fixtures/eval_results_synthetic/`` and the ones written below into a
temporary directory. None came from a model, and nothing here calls one.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import agent, human

import nirmaan
from nirmaan.cli import app
from nirmaan.eval_proposals import (
    eval_proposals,
    load_results,
    register_eval_rule,
    run_id,
    unregister_eval_rule,
)
from nirmaan.evals import load_cases
from nirmaan.models import EvalProposalThresholds, EvalResult, Level
from nirmaan.orchestrator import Orchestrator
from nirmaan.proposals import Proposal, ProposalError, decide_proposal, proposal_id, providers
from nirmaan.records import decision_records
from nirmaan.work import ProjectStore, WorkError

REPO = Path(__file__).resolve().parents[1]
SYNTHETIC = REPO / "tests" / "fixtures" / "eval_results_synthetic"
CASE = "rtl/axi4-lite-regs"
LABEL = "SYNTHETIC TEST FIXTURE (M42): not a real evaluation run"


@pytest.fixture(scope="module")
def cases():
    return load_cases(REPO / "evals")


def _result(passed: bool, day: int, *, case: str = CASE, runtime: str = "fixture-model-a", submitted: bool = True,
            judge: str = "failed", replay: bool = False, audit_ok: bool = True, version: str = "1.22.0") -> EvalResult:
    status = "passed" if passed else judge
    return EvalResult(
        case=case, case_digest="sha256:" + "c" * 64, runtime=runtime, replay=replay, version=version,
        started_at=datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(days=day), duration_s=1.0, seat="t-rtl",
        seat_status="in_review" if submitted else "in_progress", submitted=submitted, attempts=1,
        gate_runs=({"tool": "fixture.lint", "run": f"gate-{day}", "succeeded": submitted,
                    "summary": "lint clean" if submitted else "lint: undeclared port"},),
        scores=({"scorer": "held-out-run", "name": "reference testbench",
                 "status": status if submitted else "not_run",
                 "summary": f"judge on day {day}: {status}", "runs": (f"run-{day}",) if submitted else ()},),
        passed=passed, detail=LABEL, audit_ok=audit_ok, sandbox=LABEL)


def _write(root: Path, results: list[EvalResult]) -> Path:
    for i, r in enumerate(results):
        target = root / f"run-{i:02d}" / r.runtime / (r.case.replace("/", "_") + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(r.model_dump(mode="json"), indent=2), encoding="utf-8")
    return root


def _proposals(org, cases, root, **kw):
    return eval_proposals(org, load_results(root), cases, **kw)


def _manager(org):
    from nirmaan.models import Criticality, DecisionKind
    from nirmaan.org import AuthorityService

    authority = AuthorityService(org)
    return next(r.id for r in sorted(org.roles.values(), key=lambda r: r.id) if r.level is Level.MANAGER
                and authority.check(r.id, DecisionKind.CROSS_TEAM_DECISION, Criticality.MEDIUM, None).allowed)


# --- Reading recorded results --------------------------------------------------------------


def test_the_committed_fixtures_are_labelled_synthetic():
    runs = load_results(SYNTHETIC)
    assert len(runs) == 5
    assert all(LABEL in r.result.detail and LABEL in r.result.sandbox for r in runs)
    assert all(r.result.runtime.startswith("fixture-model-") for r in runs)


def test_a_run_id_is_stable_and_one_file_read_twice_is_one_run(tmp_path):
    result = _result(False, 1)
    assert run_id(result) == run_id(EvalResult.model_validate(result.model_dump(mode="json")))
    _write(tmp_path / "a", [result])
    _write(tmp_path / "b", [result])
    assert len(load_results(tmp_path)) == 1


def test_a_list_as_printed_by_eval_run_json_is_read(tmp_path):
    (tmp_path / "runs.json").write_text(json.dumps([_result(False, 1).model_dump(mode="json"),
                                                    _result(True, 2).model_dump(mode="json")]))
    assert len(load_results(tmp_path)) == 2


# --- Proposals -----------------------------------------------------------------------------


def test_a_recurring_eval_failure_proposes_with_its_evidence(nirmaan_org, cases):
    proposals = _proposals(nirmaan_org, cases, SYNTHETIC)
    [p] = [p for p in proposals if p.rule == "recurring-eval-failure"]
    assert p.source == "evaluation" and p.subject == f"{CASE}@fixture-model-a"
    assert p.capability == "rtl.implement" and p.targets == ("rtl_design",)
    assert p.count == 2 and p.projects == 0 and p.status == "open"
    runs = {r.id: r for r in load_results(SYNTHETIC)}
    for e in p.evidence:
        assert e["run"] in runs and e["case"] == CASE and e["runtime"] == "fixture-model-a" and not e["passed"]
        assert e["file"].endswith(".json")
        [verdict] = e["verdicts"]
        assert verdict["check"] == "reference testbench" and verdict["status"] == "failed"
        assert "s_axil_awaddr" in verdict["summary"] and verdict["runs"]
    # fixture-model-b passed the same case: the suggestion is a different model, through M31 selection
    assert "Model:" in p.suggestion and "fixture-model-b" in p.suggestion


def test_a_single_failure_or_failures_below_the_threshold_propose_nothing(nirmaan_org, cases, tmp_path):
    # rtl/sync-fifo failed once in the committed fixtures: nothing about it
    assert not [p for p in _proposals(nirmaan_org, cases, SYNTHETIC) if "sync-fifo" in p.subject]
    _write(tmp_path / "one", [_result(False, 1)])
    assert _proposals(nirmaan_org, cases, tmp_path / "one") == []
    # two failures, but not within the latest five runs
    old = [_result(False, 1), _result(False, 2)] + [_result(True, d) for d in range(3, 8)]
    _write(tmp_path / "old", old)
    assert not [p for p in _proposals(nirmaan_org, cases, tmp_path / "old") if p.rule == "recurring-eval-failure"]


def test_replays_and_broken_audit_chains_are_not_read(nirmaan_org, cases, tmp_path):
    _write(tmp_path, [_result(False, 1, replay=True), _result(False, 2, replay=True),
                      _result(False, 3, audit_ok=False), _result(False, 4, audit_ok=False)])
    assert _proposals(nirmaan_org, cases, tmp_path) == []


def test_the_id_survives_new_runs(nirmaan_org, cases, tmp_path):
    _write(tmp_path / "x", [_result(False, 1), _result(False, 2)])
    first = _proposals(nirmaan_org, cases, tmp_path / "x")[0]
    _write(tmp_path / "y", [_result(False, 1), _result(False, 2), _result(False, 3)])
    again = _proposals(nirmaan_org, cases, tmp_path / "y")[0]
    assert again.id == first.id and again.count == 3


def test_a_pass_rate_regression_proposes(nirmaan_org, cases, tmp_path):
    history = [_result(True, d, version="1.21.0") for d in range(1, 5)]
    history += [_result(True, 5), _result(True, 6), _result(True, 7), _result(False, 8)]
    _write(tmp_path, history)
    [p] = _proposals(nirmaan_org, cases, tmp_path)  # one failure: no recurring-failure proposal
    assert p.rule == "eval-pass-rate-regression" and p.source == "evaluation"
    assert "100%" in p.statement and "75%" in p.statement
    assert "1.21.0" in p.suggestion and "1.22.0" in p.suggestion
    assert [e["passed"] for e in p.evidence] == [True] * 7 + [False]


def test_thresholds_are_data(nirmaan_org, cases, tmp_path):
    from nirmaan.company.learning import EVAL_PROPOSAL_THRESHOLDS

    assert EVAL_PROPOSAL_THRESHOLDS == EvalProposalThresholds()
    _write(tmp_path, [_result(False, 1)])
    strict = EvalProposalThresholds(min_failures=1, within_runs=1)
    [p] = _proposals(nirmaan_org, cases, tmp_path, thresholds=strict)
    assert p.rule == "recurring-eval-failure"
    with pytest.raises(ValueError):
        EvalProposalThresholds(min_failures=0)


def test_the_suggestion_follows_the_evidence(nirmaan_org, cases, tmp_path):
    _write(tmp_path / "gates", [_result(False, 1, submitted=False), _result(False, 2, submitted=False)])
    [procedure] = _proposals(nirmaan_org, cases, tmp_path / "gates")
    assert procedure.suggestion.startswith("Procedure:") and "fixture.lint" in procedure.suggestion
    _write(tmp_path / "judge", [_result(False, 1), _result(False, 2)])
    [check] = _proposals(nirmaan_org, cases, tmp_path / "judge")
    assert check.suggestion.startswith("Check:") and "reference testbench" in check.suggestion


def test_reading_changes_no_organization_data(nirmaan_org, cases):
    before = nirmaan_org.fingerprint
    _proposals(nirmaan_org, cases, SYNTHETIC)
    assert nirmaan_org.fingerprint == before


# --- Deciding ------------------------------------------------------------------------------


def test_adopting_is_a_recorded_human_decision_that_edits_nothing(nirmaan_org, cases, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create an AXI4-Lite register block.")
    [p] = _proposals(nirmaan_org, cases, SYNTHETIC)
    skill = nirmaan_org.skills["rtl_design"]
    decision = decide_proposal(engine, p, human(_manager(nirmaan_org)), adopt=True, reason="Two failures; try B.")
    assert p.id in decision.statement and decision.rationale.startswith("Two")
    assert [r for r in decision_records(engine.state) if r.source == "decision_record"]
    [again] = eval_proposals(nirmaan_org, load_results(SYNTHETIC), cases, states=[engine.state])
    assert again.status == "adopted"
    assert nirmaan_org.skills["rtl_design"] == skill  # no auto-adoption: nothing is edited


def test_only_an_authorized_human_may_decide(nirmaan_org, cases, fixed_clock):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create an AXI4-Lite register block.")
    [p] = _proposals(nirmaan_org, cases, SYNTHETIC)
    with pytest.raises(ProposalError, match="human"):
        decide_proposal(engine, p, agent(_manager(nirmaan_org)), adopt=True, reason="x")
    junior = next(r.id for r in sorted(nirmaan_org.roles.values(), key=lambda r: r.id) if r.level is Level.ENGINEER)
    with pytest.raises(WorkError):
        decide_proposal(engine, p, human(junior), adopt=True, reason="x")
    assert not engine.state.decisions


def test_the_cli_lists_with_provenance_and_decides(nirmaan_org, fixed_clock, tmp_path):
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan("Create an AXI4-Lite register block.")
    root = tmp_path / "store"
    ProjectStore(root).save(engine.state)
    pid = engine.state.project.id
    base = ["learn", "--evals", str(SYNTHETIC), "--cases", str(REPO / "evals"), "--root", str(root)]
    text = CliRunner().invoke(app, base)
    assert text.exit_code == 0, text.output
    assert "[evaluation]" in text.output and "fixture-model-a" in text.output and "ev-" in text.output
    [p] = json.loads(CliRunner().invoke(app, [*base, "--json"]).output)
    assert p["source"] == "evaluation" and p["evidence"][0]["verdicts"]
    decided = CliRunner().invoke(app, [*base, pid, "--decide", p["id"], "--in", pid, "--as", _manager(nirmaan_org),
                                       "--reject", "--reason", "Fixture noise."])
    assert decided.exit_code == 0, decided.output
    [again] = json.loads(CliRunner().invoke(app, [*base, pid, "--json"]).output)
    assert again["status"] == "rejected"
    assert CliRunner().invoke(app, ["learn", "--root", str(root)]).exit_code != 0  # nothing to read


# --- Laws ----------------------------------------------------------------------------------


def _source():
    return (Path(nirmaan.__file__).parent / "eval_proposals.py").read_text(encoding="utf-8")


def test_eval_proposals_name_no_stage_tool_kind_or_role(nirmaan_org):
    org = nirmaan_org
    engineering_tools = {t for t, spec in org.tools.items() if spec.category != "platform"}
    vocabulary = (set(org.units) | set(org.skills) | set(org.capabilities) | set(org.roles) | engineering_tools
                  | {s.id for w in org.workflows.values() for s in w.stages}
                  | {k for w in org.workflows.values() for s in w.stages for k in s.outputs})
    for node in ast.walk(ast.parse(_source())):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in vocabulary, f"eval_proposals.py hard-codes {node.value!r}"


def test_eval_proposals_do_not_import_veritriage():
    for node in ast.walk(ast.parse(_source())):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            assert not any(n.startswith("veritriage") for n in names)


# --- Crown jewel ---------------------------------------------------------------------------


def test_a_new_eval_rule_needs_no_core_changes(nirmaan_org, cases, tmp_path):
    """A rule for judges that keep not running, registered here, proposes from recorded results."""

    @register_eval_rule("judge-keeps-not-running")
    def judge_not_running(org, history):
        proposals = []
        for (case, runtime), runs in history.groups().items():
            idle = [r for r in runs if any(s.status.value == "not_run" for s in r.result.scores)]
            if len(idle) >= history.thresholds.min_failures:
                capability = history.capability(case)
                subject = f"{case}@{runtime}"
                proposals.append(Proposal(
                    id=proposal_id("judge-keeps-not-running", capability, subject), rule="judge-keeps-not-running",
                    capability=capability, subject=subject, targets=providers(org, capability),
                    statement="A judge keeps not running.", suggestion="Check: install the judge's tool.",
                    count=len(idle), projects=0, evidence=tuple(r.evidence() for r in idle), source="evaluation"))
        return proposals

    try:
        _write(tmp_path, [_result(False, 1, submitted=False), _result(False, 2, submitted=False)])
        rules = {p.rule for p in _proposals(nirmaan_org, cases, tmp_path)}
        assert rules == {"recurring-eval-failure", "judge-keeps-not-running"}
    finally:
        unregister_eval_rule("judge-keeps-not-running")
    assert {p.rule for p in _proposals(nirmaan_org, cases, tmp_path)} == {"recurring-eval-failure"}

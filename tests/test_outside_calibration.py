"""Outside calibration (M76): the RTLLM adapter, on tiny synthetic designs written for these tests.

Nothing here is a benchmark problem: each design is a few lines in the benchmark's layout (a description with a
``Module name`` line, a testbench that prints its pass message, a reference named ``verified_<design>``). The real
copy lives outside both repositories (``docs/OUTSIDE_CALIBRATION.md``); no test reads it or calls a model.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan.cli import app
from nirmaan.company import build_organization
from nirmaan.eval_proposals import load_results
from nirmaan.evals import EvalError, load_record
from nirmaan.evals.levels import compute
from nirmaan.evals.outside import OutsideError, calibrate, check_reference, locate, stage_cases, with_verdict
from nirmaan.runtime.harness import harness_sha256

COMMIT = "0123456789abcdef0123456789abcdef01234567"
GOOD = """module verified_inv(input wire a, output wire y);
  assign y = ~a;
endmodule
"""
WRONG = GOOD.replace("~a", "a")
TB = """`timescale 1ns/1ps
module tb;
  reg a; wire y; integer error = 0;
  inv uut(.a(a), .y(y));
  initial begin
    a = 0; #1 if (y !== 1'b1) error = error + 1;
    a = 1; #1 if (y !== 1'b0) error = error + 1;
    if (error == 0) begin
      $display("===========Your Design Passed===========");
    end else begin
      $display("===========Error===========");
    end
    $finish;
  end
endmodule"""
#: a testbench that ends nothing itself, like several of the benchmark's
TB_NO_FINISH = TB.replace("    $finish;\n", "")
DESCRIPTION = "Please act as a designer.\n\nModule name:\n    inv\nInput ports:\n    a: input.\nOutput ports:\n    y: not a.\n"


@pytest.fixture(scope="module")
def org():
    return build_organization()


def _design(root: Path, name: str, *, reference: str = GOOD, tb: str = TB, folder: str = "Group") -> None:
    where = root / folder / name
    where.mkdir(parents=True)
    (where / "design_description.txt").write_text(DESCRIPTION.replace("inv", name), encoding="utf-8")
    (where / "testbench.v").write_text(tb.replace("inv", name), encoding="utf-8")
    (where / f"verified_{name}.v").write_text(reference.replace("inv", name), encoding="utf-8")


@pytest.fixture()
def bench(tmp_path) -> Path:
    root = tmp_path / "rtllm"
    _design(root, "inv")
    _design(root, "inv2", tb=TB_NO_FINISH)
    _design(root, "badinv", reference=WRONG)
    (root / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    (root / "UPSTREAM_COMMIT").write_text(COMMIT + "\n", encoding="utf-8")
    # model-generated answers are never problems
    _design(root / "_chatgpt4" / "t1", "inv", folder="x")
    return root


# --- Mapping ----------------------------------------------------------------------------------


def test_designs_are_found_by_name_and_model_output_folders_are_never_entered(bench):
    assert [d.name for d in locate(bench)] == ["badinv", "inv", "inv2"]


def test_a_missing_benchmark_path_fails_with_a_clear_message(tmp_path):
    with pytest.raises(OutsideError, match="not at .*nowhere.*outside the repositories.*git clone"):
        locate(tmp_path / "nowhere")
    result = CliRunner().invoke(app, ["eval", "outside", "--check", "--benchmark", str(tmp_path / "nowhere")])
    assert result.exit_code == 1 and "nowhere" in result.output and "outside the repositories" in result.output


def test_a_folder_that_is_not_the_benchmark_is_refused(tmp_path):
    with pytest.raises(OutsideError, match="not an RTLLM copy"):
        locate(tmp_path)


def test_the_cli_needs_the_path_and_one_mode(tmp_path):
    runner = CliRunner()
    assert runner.invoke(app, ["eval", "outside", "--check"], env={"NIRMAAN_RTLLM_DIR": ""}).exit_code == 1
    assert runner.invoke(app, ["eval", "outside", "--benchmark", str(tmp_path)]).exit_code == 1


def test_the_licence_and_the_commit_must_travel_with_the_copy(bench, org):
    (bench / "LICENSE").unlink()
    with pytest.raises(OutsideError, match="MIT notice"):
        stage_cases(bench, bench.parent / "stage")
    (bench / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    (bench / "UPSTREAM_COMMIT").unlink()
    with pytest.raises(OutsideError, match="which upstream commit"):
        calibrate(org, bench, runtime=None, trials=1, out=bench.parent / "out")


def test_a_design_maps_to_a_case_with_the_description_as_spec_and_the_benchmarks_testbench_as_judge(bench, tmp_path):
    cases = {c.id: c for c in stage_cases(bench, tmp_path / "stage", ["inv"])}
    case = cases["rtllm/inv"]
    assert case.seat == "rtl-implementation" and case.skills == ("rtl_design",)
    spec = Path(case.upstream["interface-spec"][0].path).read_text(encoding="utf-8")
    assert spec.strip() == DESCRIPTION.replace("inv", "inv").strip()
    assert [f.kind for f in case.reference] == ["rtl_source", "testbench"]
    assert case.reference[0].entry == "inv"  # the reference's top is renamed to the module the spec names
    assert "module inv(" in Path(case.reference[0].path).read_text(encoding="utf-8")
    [check] = case.held_out
    assert check.scorer == "held-out-run" and check.tool == "simulator.run" and check.params == {"top": "tb"}
    # the reference answer never reaches the seat: only the spec and our note are upstream
    assert all("verified" not in Path(f.path).read_text(encoding="utf-8")
               for files in case.upstream.values() for f in files)


def test_the_verdict_line_goes_beside_the_benchmarks_own_pass_message_and_nowhere_else():
    staged = with_verdict(TB)
    assert staged.count("NIRMAAN-SIM") == 1 and staged.count("Your Design Passed") == 1
    assert "$finish" in staged and "$finish" not in with_verdict(TB_NO_FINISH).split("NIRMAAN-SIM")[0]
    assert "$finish;" in with_verdict(TB_NO_FINISH, finish=True)
    for bad in ("module tb; endmodule", TB + TB):
        with pytest.raises(OutsideError, match="needs one"):
            with_verdict(bad)


# --- Judging through the broker ---------------------------------------------------------------


def test_the_benchmarks_testbench_passes_a_right_reference_and_fails_a_wrong_one(bench, org):
    verdicts = {name: ok for name, ok, _ in check_reference(org, bench)}
    assert verdicts == {"badinv": False, "inv": True, "inv2": True}


def test_the_check_command_reports_how_many_map(bench):
    result = CliRunner().invoke(app, ["eval", "outside", "--check", "--benchmark", str(bench)])
    assert result.exit_code == 0, result.output
    assert "NOT MAPPED badinv" in result.output and "MAPPED inv:" in result.output
    assert "2 of 3 designs map" in result.output


# --- Records ----------------------------------------------------------------------------------


@pytest.fixture()
def record(bench, org, tmp_path) -> Path:
    return calibrate(org, bench, runtime=None, trials=1, out=tmp_path / "out")


def test_a_calibration_record_is_labelled_names_its_source_and_carries_the_harness(record):
    run = load_record(record)
    assert run.manifest.purpose == "calibration" and record.name.endswith("-calibration")
    assert COMMIT in run.manifest.source and "MIT" in run.manifest.source
    assert "2 of 3 designs mapped, not mapped: badinv" in run.manifest.source
    assert [t.result.case for t in run.trials] == ["rtllm/inv", "rtllm/inv2"]
    for trial in run.trials:
        assert trial.purpose == "calibration"
        assert trial.result.harness == harness_sha256(attempts=None, knowledge=True, cli=None)
        assert trial.result.passed, trial.result.detail  # the reference passes the benchmark's own testbench


def test_levels_list_calibration_records_as_not_counting_and_never_count_them(record, org, tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(record, repo / "evals" / "results" / record.name)
    levels = compute(org, repo)
    assert levels["skills"] == {} and levels["refused_records"] == []  # a replay is no refusal here: it is labelled
    assert [(c["case"], c["trial"], c["passed"]) for c in levels["calibration"]] == [
        ("rtllm/inv", 1, True), ("rtllm/inv2", 1, True)]
    assert all("outside calibration" in c["reason"] and "never counts toward a level" in c["reason"]
               for c in levels["calibration"])


@pytest.mark.parametrize("where", ["manifest", "trial"])
def test_either_label_alone_keeps_the_trial_out_of_the_levels(record, org, tmp_path, where):
    repo = tmp_path / "repo"
    copy = repo / "evals" / "results" / record.name
    shutil.copytree(record, copy)
    for path in copy.rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["format"] != "nirmaan.eval-summary" and (where == "manifest") == (data["format"] == "nirmaan.eval-run"):
            data["purpose"] = "evidence"  # someone edits one label back
            path.write_text(json.dumps(data), encoding="utf-8")
    levels = compute(org, repo)
    assert levels["skills"] == {} and len(levels["calibration"]) == 2
    assert all(f"labelled in the {'trial' if where == 'manifest' else 'run manifest'})" in c["reason"]
               for c in levels["calibration"])


def test_learning_never_reads_calibration_trials(record):
    assert load_results(record.parent) == []


def test_a_record_without_purpose_is_evidence_as_before(record):
    for path in record.rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("purpose", None)
        data.pop("source", None)
        path.write_text(json.dumps(data), encoding="utf-8")
    assert load_record(record).manifest.purpose == "evidence"


def test_naming_only_a_bad_design_is_an_error_not_an_empty_record(bench, org, tmp_path):
    with pytest.raises(OutsideError, match="no design maps"):
        calibrate(org, bench, runtime=None, trials=1, out=tmp_path / "out", names=["badinv"])
    with pytest.raises(EvalError, match="unknown design nothere"):
        stage_cases(bench, tmp_path / "stage", ["nothere"])

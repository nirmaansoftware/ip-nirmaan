"""A run record's purpose: ``nirmaan eval run --purpose evidence|calibration``.

A calibration run on our own cases (a harness comparison's default arm on the
pilot cases, before the default is named) is labelled ``purpose: calibration``
in its name, its manifest and every trial, the same label ``eval outside``
(M76) writes, so the levels generator lists it and never counts it. The
levels side is in ``tests/test_capability_levels.py``. No test calls a model:
the seat is the case's reference answer (``--replay``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan.cli import app
from nirmaan.eval_proposals import load_results
from nirmaan.evals import load_cases, load_record, record_run
from nirmaan.evals.records import MANIFEST, PURPOSES
from nirmaan.models import EvalRunManifest

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
SPEC_CASE = "spec/axi4-lite-interface"


def _run(out: Path, *extra: str):
    return CliRunner().invoke(app, ["eval", "run", "--replay", "--seats", "spec", *extra, "--cases", str(EVALS),
                                    "--repo", str(REPO), "--out", str(out)])


def test_the_purposes_are_the_manifests_own():
    assert PURPOSES == ("evidence", "calibration")


def test_the_cli_writes_a_calibration_purpose_into_the_name_the_manifest_and_every_trial(tmp_path):
    out = tmp_path / "results"
    ran = _run(out, "--purpose", "calibration")
    assert ran.exit_code == 0, ran.output
    assert "purpose calibration; this record never counts toward an evidence level" in ran.output
    [path] = list(out.iterdir())
    assert path.name.endswith("-calibration")
    assert json.loads((path / MANIFEST).read_text(encoding="utf-8"))["purpose"] == "calibration"
    record = load_record(path)
    assert record.manifest.purpose == "calibration" and record.trials
    assert all(t.purpose == "calibration" for t in record.trials)
    history = CliRunner().invoke(app, ["eval", "history", "--results", str(out)])
    assert history.exit_code == 0 and "purpose calibration" in history.output
    # M42 learning never reads it, as for an outside calibration.
    assert load_results(out) == []


def test_the_default_purpose_is_evidence_as_before(tmp_path):
    out = tmp_path / "results"
    ran = _run(out)
    assert ran.exit_code == 0, ran.output
    assert "note: purpose" not in ran.output
    [path] = list(out.iterdir())
    assert not path.name.endswith("-calibration")
    record = load_record(path)
    assert record.manifest.purpose == "evidence" and all(t.purpose == "evidence" for t in record.trials)
    history = CliRunner().invoke(app, ["eval", "history", "--results", str(out)])
    assert history.exit_code == 0 and ", purpose " not in history.output


def test_an_unknown_purpose_is_refused_before_anything_runs(tmp_path):
    out = tmp_path / "results"
    ran = _run(out, "--purpose", "practice")
    assert ran.exit_code != 0 and "unknown purpose 'practice'" in ran.output
    assert not out.exists()


def test_record_run_refuses_an_unknown_purpose_before_writing(nirmaan_org, fixed_clock, tmp_path):
    case = next(c for c in load_cases(EVALS) if c.id == SPEC_CASE)
    with pytest.raises(ValueError, match="unknown purpose"):
        record_run(nirmaan_org, [case], None, trials=1, repo=REPO, out=tmp_path / "out", clock=fixed_clock,
                   purpose="practice")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("purpose", PURPOSES)
def test_the_manifest_field_round_trips(nirmaan_org, fixed_clock, tmp_path, purpose):
    case = next(c for c in load_cases(EVALS) if c.id == SPEC_CASE)
    path = record_run(nirmaan_org, [case], None, trials=1, repo=REPO, out=tmp_path, clock=fixed_clock,
                      purpose=purpose)
    manifest = load_record(path).manifest
    assert manifest.purpose == purpose
    again = EvalRunManifest.model_validate_json(manifest.model_dump_json())
    assert again == manifest and again.purpose == purpose


def test_every_committed_record_still_validates_and_reads_as_evidence():
    manifests = sorted((EVALS / "results").rglob(MANIFEST))
    assert manifests
    for manifest in manifests:
        record = load_record(manifest.parent)
        assert record.manifest.purpose == "evidence", manifest
        assert all(t.purpose == "evidence" for t in record.trials), manifest

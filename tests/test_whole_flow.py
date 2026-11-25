"""Whole-flow cases: the label, the reader and the case checks (M87, council record 2026-11-17).

A whole-flow trial seats every work stage and judges only the final block. It credits no skill and no level:
the levels list it under ``whole_flow`` (tests/test_capability_levels.py). Here: a single-seat case, manifest and
trial dump exactly as before the label existed, so no case digest and no record file changes; a whole-flow case
is in no default case set and never runs as a single-seat case; and a whole-flow case names no skill in
``skills``, fixes no upstream stage, and lists the skills it exercises instead.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nirmaan.company import build_organization
from nirmaan.evals import EvalError, load_cases, record_run, validate_case
from nirmaan.evals.flow import flow_digest
from nirmaan.evals.records import flow_labels, is_whole_flow, load_record
from nirmaan.models import EvalCase, EvalResult, EvalRunManifest, EvalStage, EvalTrial
from nirmaan.runtime import harness

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
AT = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
TIMER = "Create an AXI4-Lite timer peripheral with an interrupt."
#: What each seated stage of the timer request is given (the planner's tasks and their seats' skills).
EXERCISED = {"requirements": ["requirements_engineering"], "interface-spec": ["interface_specification"],
             "microarchitecture": ["rtl_microarchitecture"], "rtl-implementation": ["axi", "fsm_design", "rtl_design"]}


@pytest.fixture(scope="module")
def org():
    return build_organization()


def _whole(**overrides) -> EvalCase:
    data = {"id": "flow/timer", "request": TIMER, "seat": "rtl-implementation", "flow": "whole",
            "exercised": EXERCISED, **overrides}
    return EvalCase.model_validate(data)


def _trial(flow: str = "seat", case: str = "c", **extra) -> EvalTrial:
    result = EvalResult(case=case, case_digest="sha256:x", runtime="claude-code", replay=False, version="t",
                        started_at=AT, duration_s=1.0, seat="rtl-implementation", seat_status="done",
                        submitted=True, attempts=1, passed=True, audit_ok=True, sandbox="s")
    return EvalTrial(record="r", trial=1, stage="rtl-implementation", result=result, flow=flow, **extra)


def _manifest(flow: str = "seat") -> EvalRunManifest:
    return EvalRunManifest(id="r", runtime="claude-code", replay=False, nirmaan_version="t", started_at=AT,
                           finished_at=AT, trials=1, cases=("c",), seats=("rtl-implementation",), flow=flow)


# --- Nothing changes for a single-seat case, manifest or trial ------------------------------------------------


def test_a_single_seat_case_dumps_as_before_so_no_case_digest_changes():
    for case in load_cases(EVALS):
        dumped = case.model_dump(mode="json")
        assert "flow" not in dumped and "exercised" not in dumped, case.id
        assert set(dumped) == set(EvalCase.model_fields) - {"flow", "exercised"}, case.id


def test_a_single_seat_trial_and_manifest_are_written_as_before():
    assert not {"flow", "stages", "flow_digest"} & set(_trial().model_dump(mode="json"))
    assert "flow" not in _manifest().model_dump(mode="json")


def test_a_whole_flow_case_trial_and_manifest_carry_the_label():
    assert _whole().model_dump(mode="json")["flow"] == "whole"
    assert _whole().model_dump(mode="json")["exercised"] == EXERCISED
    stage = EvalStage(stage="requirements", task="t1", status="not run")
    trial = _trial("whole", stages=(stage,), flow_digest="sha256:f").model_dump(mode="json")
    assert trial["flow"] == "whole" and trial["flow_digest"] == "sha256:f" and trial["stages"][0]["status"] == "not run"
    assert _manifest("whole").model_dump(mode="json")["flow"] == "whole"
    assert EvalTrial.model_validate_json(_trial("whole").model_dump_json()).flow == "whole"


#: Where a committed whole-flow record may live: one folder per slot, the record name as record_run wrote it. The
#: timer's folder is the plan's section 15; the register block's is named by its dated addition before slot 21.
SLOT_RECORD = re.compile(r"(g3-timer|g3-regs-driver)/slot-\d{2}/[^/]+")
#: Each case's slot folder under evals/results: its case and its first slot (the plan's section 10).
BATCHES = {"g3-timer": ("flow/axil-timer", 1), "g3-regs-driver": ("flow/axi4-lite-regs-driver", 21)}


def _check_record_structure(root: Path, folder: Path) -> None:
    """A committed record loads; a single-seat record is entirely single-seat (as before the label existed); a
    whole-flow record is entirely whole-flow, sits in a timer slot folder and carries each trial's stages and
    flow digest."""
    record = load_record(folder)  # raises on a record that does not load
    where = folder.relative_to(root).as_posix()
    if not is_whole_flow(record):  # also raises when the record mixes the two kinds
        assert all(t.flow == "seat" and t.stages == () and t.flow_digest is None for t in record.trials), where
        return
    assert SLOT_RECORD.fullmatch(where), (f"{where}: a whole-flow record belongs in g3-timer/slot-NN/<record name> "
                                          "or g3-regs-driver/slot-NN/<record name>")
    case = BATCHES[where.split("/")[0]][0]
    assert record.trials, where
    # The measured run (purpose calibration) is outside the forty (plan, section 10), so a slot folder holds
    # evidence records only.
    assert record.manifest.purpose == "evidence", f"{where}: a slot folder holds no calibration record"
    for trial in record.trials:
        assert trial.purpose == "evidence", f"{where} trial {trial.trial}: a slot folder holds no calibration record"
        assert trial.flow == "whole" and trial.stages and trial.flow_digest, f"{where} trial {trial.trial}"
        assert trial.result.case == case, (f"{where} trial {trial.trial}: a record of {trial.result.case} in "
                                           f"{case}'s folder")
        assert all(isinstance(stage, EvalStage) for stage in trial.stages), where


def test_every_committed_record_still_loads_and_a_whole_flow_one_has_its_structure():
    root = EVALS / "results"
    manifests = sorted(root.rglob("manifest.json"))
    assert manifests
    for path in manifests:
        _check_record_structure(root, path.parent)


def test_a_nested_slot_record_is_read_as_a_whole_flow_record_and_a_misplaced_or_unlabelled_one_fails(tmp_path):
    stage = EvalStage(stage="requirements", task="t1", status="done")

    def write(rel: str, manifest: EvalRunManifest, trial: EvalTrial) -> Path:
        folder = tmp_path / rel
        (folder / "flow_timer").mkdir(parents=True)
        (folder / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
        (folder / "flow_timer" / "trial-01.json").write_text(trial.model_dump_json(), encoding="utf-8")
        return folder

    whole_trial = _trial("whole", "flow/axil-timer", stages=(stage,), flow_digest="sha256:f")
    # Two slots of one arm on one day: the same record name under two slot folders, both fine.
    for slot in ("slot-01", "slot-02"):
        _check_record_structure(tmp_path, write(f"g3-timer/{slot}/2026-11-23-claude-code-m", _manifest("whole"),
                                                whole_trial))
    assert len(list(tmp_path.rglob("manifest.json"))) == 2
    with pytest.raises(AssertionError, match="belongs in g3-timer"):  # a whole-flow record in the flat layout
        _check_record_structure(tmp_path, write("2026-11-23-claude-code-m", _manifest("whole"), whole_trial))
    with pytest.raises(AssertionError):  # a whole-flow trial that lost its stages or its digest
        _check_record_structure(tmp_path, write("g3-timer/slot-03/m", _manifest("whole"), _trial("whole")))
    with pytest.raises(AssertionError):  # the manifest says whole but the trial does not: both must say so
        _check_record_structure(tmp_path, write("g3-timer/slot-04/m", _manifest("whole"), _trial()))
    with pytest.raises(AssertionError, match="in flow/axil-timer's folder"):  # a case's record in the other's folder
        _check_record_structure(tmp_path, write("g3-timer/slot-07/m", _manifest("whole"),
                                                whole_trial.model_copy(update={"result": whole_trial.result.model_copy(
                                                    update={"case": "flow/axi4-lite-regs-driver"})})))
    _check_record_structure(tmp_path, write("g3-regs-driver/slot-21/m", _manifest("whole"), whole_trial.model_copy(
        update={"result": whole_trial.result.model_copy(update={"case": "flow/axi4-lite-regs-driver"})})))
    calibration = _trial("whole", "flow/axil-timer", stages=(stage,), flow_digest="sha256:f", purpose="calibration")
    with pytest.raises(AssertionError, match="no calibration record"):  # the measured run is no slot
        _check_record_structure(tmp_path, write("g3-timer/slot-05/m", _manifest("whole"), calibration))
    with pytest.raises(AssertionError, match="no calibration record"):
        _check_record_structure(tmp_path, write("g3-timer/slot-06/m",
                                                _manifest("whole").model_copy(update={"purpose": "calibration"}),
                                                whole_trial))
    _check_record_structure(tmp_path, write("seat-run", _manifest(), _trial()))  # a single-seat record is as before
    with pytest.raises(AssertionError):  # a single-seat record may not carry whole-flow detail
        _check_record_structure(tmp_path, write("seat-run-2", _manifest(), _trial(flow_digest="sha256:f")))


def test_either_label_is_enough_and_the_name_is_never_read():
    assert flow_labels(_manifest("whole"), _trial()) == ("the run manifest",)
    assert flow_labels(_manifest(), _trial("whole")) == ("the trial",)
    assert flow_labels(_manifest(), _trial()) == ()


def test_the_label_reader_and_the_list_are_outside_the_harness_code():
    # Editing these files never restarts a harness group: none is in harness.CODE (docs/HARNESS.md).
    for rel in ("nirmaan/models/evaluation.py", "nirmaan/evals/records.py", "nirmaan/evals/levels.py",
                "nirmaan/evals/cases.py"):
        assert rel not in harness.CODE


# --- The reach folders of the timer's slots (gate ET16) ---------------------------------------------------------
#
# Each run of a slot has a folder `g3-timer/slot-NN/reach/<run id>/`: the files its jobs uploaded, byte for byte, each
# at `<artifact name>/<file name>`, and `reach-index.json`. The folder sits beside the slot's `<record name>/` and
# never inside it (council record 2026-11-22-eda-tools-seat-account.md, addenda, decisions A1, R1 and R3). The index
# names its `format`, `slot` (the number), `run`, `attempt` and `commit`; `files` (each `path` and `sha256`, the digest
# written `sha256:<hex>`); `missing` (the name of each of the four artifacts the run did not upload); `recorded` (whether
# this run wrote the slot's record); `no_record_cause`, the words that say why a run that wrote no record wrote none;
# and the runner's own `reach_held`, which this test does not read: it reads the records.

SLOT_FOLDER = re.compile(r"slot-(\d{2})")
REACH_ARTIFACT = re.compile(r"live-eval-(tool|fw)-reach-(trials|rejudge)-(\d+)")
INDEX = "reach-index.json"
INDEX_FORMAT = "nirmaan.slot-reach-index/1"
JOB = {"trials": "live-eval", "rejudge": "rejudge"}
REACH_FILE = {"tool": "tool-reach.json", "fw": "fw-reach.json"}
ARTIFACTS = tuple(f"live-eval-{kind}-reach-{job}" for job in ("trials", "rejudge") for kind in ("tool", "fw"))
SHA256 = "sha256:"


def _json_object(path: Path, where: str) -> dict:
    """A reach file is UTF-8 text that is a JSON object with a ``format`` field (what the case loader skips too)."""
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError) as error:
        raise AssertionError(f"{where}: not UTF-8 JSON text ({error})") from error
    assert isinstance(data, dict) and "format" in data, f"{where}: not a JSON object with a format field"
    return data


def _check_run_folder(folder: Path, slot: str, root: Path) -> tuple[dict, dict[str, dict]]:
    """One run's folder: only what the index names, every digest equal, every record naming the run and commit.
    Returns the index and the loaded files by path."""
    where = folder.relative_to(root).as_posix()
    assert folder.is_dir() and folder.name.isdigit(), f"{where}: a run folder is named by the run id"
    for path in folder.rglob("*"):
        assert path.name not in ("manifest.json", "causes.md") and not path.name.startswith("trial-"), (
            f"{where}: {path.relative_to(folder).as_posix()} takes a record's file name")
    index = _json_object(folder / INDEX, f"{where}/{INDEX}")
    assert index.get("format") == INDEX_FORMAT, f"{where}: the index's format is not {INDEX_FORMAT}"
    assert (f"slot-{index.get('slot')!s:0>2}", str(index.get("run"))) == (slot, folder.name), (
        f"{where}: the index names another slot or run")
    assert index.get("commit") and index.get("attempt"), f"{where}: the index names no commit or attempt"
    listed = {f.get("path"): f.get("sha256") for f in index.get("files", ())}
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p != folder / INDEX}
    assert set(listed) == actual and len(listed) == len(index.get("files", ())), (
        f"{where}: the index names {sorted(listed)}, the folder holds {sorted(actual)}")
    loaded: dict[str, dict] = {}
    seen = set()
    for rel, digest in sorted(listed.items()):
        artifact, _, name = rel.partition("/")
        match = REACH_ARTIFACT.fullmatch(artifact)
        assert match and match.group(3) == folder.name and "/" not in name and name == REACH_FILE[match.group(1)], (
            f"{where}: {rel} is not an uploaded reach file of run {folder.name}")
        assert SHA256 + hashlib.sha256((folder / rel).read_bytes()).hexdigest() == digest, f"{where}: {rel} differs from its digest"
        data = loaded[rel] = _json_object(folder / rel, f"{where}/{rel}")
        kind, job = match.group(1), match.group(2)
        seen.add(artifact.rsplit("-", 1)[0])
        if kind == "tool":
            ids = (str(data.get("run_id")), data.get("job"), data.get("commit"))
        else:
            run = data.get("run") or {}
            ids = (str(run.get("id")), run.get("job"), data.get("head"))
        assert ids == (folder.name, JOB[job], index["commit"]), f"{where}: {rel} names {ids}, not this run, job and commit"
    missing = {m.rsplit("-", 1)[0] for m in index.get("missing", ())}
    assert all(m == f"{m.rsplit('-', 1)[0]}-{folder.name}" for m in index.get("missing", ())), (
        f"{where}: a missing artifact is named with this run's id")
    assert missing <= set(ARTIFACTS) and not missing & seen and missing | seen == set(ARTIFACTS), (
        f"{where}: each of the four artifacts is in the folder or in missing, and not both")
    assert isinstance(index.get("recorded"), bool), f"{where}: recorded is not stated"
    if not index["recorded"]:
        assert isinstance(index.get("no_record_cause"), str) and index["no_record_cause"].strip(), (
            f"{where}: a run that wrote no record states why")
    return index, loaded


def _denied(index: dict, loaded: dict[str, dict], job: str) -> bool:
    """Every probe of the run's tool reach record of this job denied; a missing record counts as not denied."""
    data = loaded.get(f"live-eval-tool-reach-{job}-{index['run']}/tool-reach.json")
    probes = (data or {}).get("probes")
    return bool(probes) and data.get("every_denied") is True and all(
        isinstance(p, dict) and p.get("denied") is True for p in probes)


def _check_slot_reach(slot: Path, root: Path) -> bool:
    """One slot folder; returns whether it holds a record."""
    where = slot.relative_to(root).as_posix()
    reach = slot / "reach"
    assert reach.is_dir(), f"{where}: the slot's reach records are not committed (reach/ is missing)"
    assert not [p for p in slot.iterdir() if p.is_file()], f"{where}: only folders sit in a slot folder"
    records = sorted(p.parent for p in slot.rglob("manifest.json") if reach not in p.parents)
    assert len(records) <= 1, f"{where}: a slot holds one record, found {len(records)}"
    assert sorted(p.name for p in slot.iterdir()) == sorted({"reach", *(r.name for r in records)}), (
        f"{where}: a slot folder holds reach/ and its record, nothing else")
    runs = {}
    for folder in sorted(reach.iterdir()):
        runs[folder.name] = _check_run_folder(folder, slot.name, root)
    assert runs, f"{where}: reach/ holds no run"
    wrote = [name for name, (index, _) in runs.items() if index["recorded"]]
    if not records:  # a slot whose record is still to come: at most one run says it will write it
        assert len(wrote) <= 1, f"{where}: more than one run says it wrote the slot's record"
        return False
    manifest = json.loads((records[0] / "manifest.json").read_text(encoding="utf-8"))
    head = manifest.get("head_sha")
    assert head, f"{where}: the record's manifest names no head_sha"
    assert len(wrote) == 1, f"{where}: exactly one run folder says it wrote the record, found {len(wrote)}"
    index, loaded = runs[wrote[0]]
    assert index["commit"] == head, f"{where}: the recording run is on {index['commit']}, the record on {head}"
    assert _denied(index, loaded, "trials"), f"{where}: a probe of run {wrote[0]}, job live-eval, was not denied"
    if (records[0] / "rejudge.json").exists():
        assert _denied(index, loaded, "rejudge"), f"{where}: a probe of run {wrote[0]}, job rejudge, was not denied"
    return True


def _check_slots_reach(root: Path) -> None:
    for batch, (_, first) in BATCHES.items():  # each case's slots, numbered as the plan's section 10 numbers them
        numbered = {}
        for slot in sorted(root.glob(f"{batch}/*")):
            match = SLOT_FOLDER.fullmatch(slot.name)
            assert slot.is_dir() and match, f"{slot.relative_to(root)}: not a slot folder"
            assert first <= int(match.group(1)) < first + 20, f"{slot.relative_to(root)}: not a slot of {batch}"
            numbered[int(match.group(1))] = _check_slot_reach(slot, root)
        with_record = sorted(n for n, has in numbered.items() if has)
        assert with_record == list(range(first, first + len(with_record))), (
            f"{batch}: the slots with a record run from {first:02d} with none missing")
        without = sorted(n for n, has in numbered.items() if not has)
        assert without in ([], [first + len(with_record)]), (
            f"{batch}: only the highest slot folder may hold reach records and no record")


def test_every_committed_timer_slot_has_its_reach_folders_and_its_record_on_their_commit():
    # With no slot folder yet this passes, and the fixture tests below show the checks bite once one exists.
    _check_slots_reach(EVALS / "results")


SHA = "a" * 40


def _put(folder: Path, rel: str, data: dict) -> None:
    path = folder / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _reindex(folder: Path, **change) -> None:
    """Rewrite a run folder's index from what the folder holds (the digests), with the given fields changed."""
    index = json.loads((folder / INDEX).read_text(encoding="utf-8"))
    files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p != folder / INDEX)
    index["files"] = [{"path": rel, "sha256": SHA256 + hashlib.sha256((folder / rel).read_bytes()).hexdigest()} for rel in files]
    index.update(change)
    (folder / INDEX).write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


def _run(slot: Path, run: str, *, wrote: bool, jobs=("trials", "rejudge"), head: str = SHA, cause: str | None = None) -> Path:
    """A synthetic run folder: the reach files the given jobs uploaded, and its index."""
    folder = slot / "reach" / run
    for job in jobs:
        tool = {"format": "nirmaan.tool-reach", "every_denied": True, "commit": head, "run_id": run,
                "run_attempt": "1", "job": JOB[job], "probes": [{"tool": "vvp", "denied": True}]}
        fw = {"format": "nirmaan.fw-reach/1", "head": head, "run": {"id": run, "attempt": "1", "job": JOB[job]}}
        _put(folder, f"live-eval-tool-reach-{job}-{run}/tool-reach.json", tool)
        _put(folder, f"live-eval-fw-reach-{job}-{run}/fw-reach.json", fw)
    missing = [f"{a}-{run}" for a in ARTIFACTS if a.rsplit("-", 1)[1] not in jobs]
    index = {"format": INDEX_FORMAT, "slot": int(slot.name[-2:]), "run": run, "attempt": "1", "commit": head,
             "files": [], "missing": missing, "recorded": wrote,
             "no_record_cause": None if wrote else cause}
    (folder / INDEX).write_text(json.dumps(index), encoding="utf-8")
    _reindex(folder)
    return folder


def _slot(tmp_path: Path, n: int = 1, *, record: bool = True, rejudged: bool = True, head: str = SHA,
          batch: str = "g3-timer") -> Path:
    """A synthetic slot folder with one recording run (111) and, if asked, its record."""
    slot = tmp_path / batch / f"slot-{n:02d}"
    if record:
        folder = slot / "2026-11-23-claude-code-m"
        folder.mkdir(parents=True)
        (folder / "manifest.json").write_text(json.dumps({"id": "r", "head_sha": head}), encoding="utf-8")
        if rejudged:
            (folder / "rejudge.json").write_text("{}", encoding="utf-8")
    _run(slot, "111", wrote=True, jobs=("trials", "rejudge") if rejudged else ("trials",), head=head)
    return slot


def _edit(folder: Path, rel: str, change) -> None:
    data = json.loads((folder / rel).read_text(encoding="utf-8"))
    change(data)
    (folder / rel).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _reindex(folder)


def test_slots_whose_reach_folders_hold_every_check_pass(tmp_path):
    _check_slots_reach(tmp_path)  # no g3-timer folder at all: an empty set passes
    one = _slot(tmp_path, 1)
    # A failed gate's run (no record, its cause stated) is kept beside the run that recorded the slot.
    _run(one, "90", wrote=False, jobs=("trials",), cause="the live-eval job's reach gate failed")
    _slot(tmp_path, 2, rejudged=False)  # an unjudged record: the rejudge job's probes are not asked for
    _check_slots_reach(tmp_path)
    # An unjudged record (no rejudge.json): a rejudge tool record that shows a probe not denied is not asked of it.
    unjudged = _slot(tmp_path, 3, rejudged=False)
    _run(unjudged, "111", wrote=True)  # the recording run's rejudge job did upload its tool reach record ...
    _edit(unjudged / "reach" / "111", "live-eval-tool-reach-rejudge-111/tool-reach.json",
          lambda d: d.update(every_denied=False))  # ... and one probe of it was not denied
    _check_slots_reach(tmp_path)
    # The highest slot may hold reach records and no record yet, or only a run that wrote none.
    _slot(tmp_path, 4, record=False)
    _check_slots_reach(tmp_path)
    shutil.rmtree(tmp_path / "g3-timer" / "slot-04")
    _run(tmp_path / "g3-timer" / "slot-04", "95", wrote=False, jobs=("trials",), cause="exit 4, a fingerprint mismatch")
    _check_slots_reach(tmp_path)
    # The register block's slots are numbered from 21 in their own folder, under the same checks.
    _slot(tmp_path, 21, batch="g3-regs-driver")
    _slot(tmp_path, 22, record=False, batch="g3-regs-driver")
    _check_slots_reach(tmp_path)
    for n, match in ((24, "run from 21 with none missing"), (1, "not a slot of g3-regs-driver")):
        shutil.rmtree(tmp_path / "g3-regs-driver" / "slot-22")
        _slot(tmp_path, n, batch="g3-regs-driver")
        with pytest.raises(AssertionError, match=match):
            _check_slots_reach(tmp_path)
        shutil.rmtree(tmp_path / "g3-regs-driver" / f"slot-{n:02d}")
        _slot(tmp_path, 22, record=False, batch="g3-regs-driver")


@pytest.mark.parametrize("what, match", [
    ("no reach folder", "reach/ is missing"),
    ("a probe not denied in live-eval", "job live-eval, was not denied"),
    ("a probe not denied in rejudge", "job rejudge, was not denied"),
    ("no probes", "was not denied"),
    ("the live-eval tool record missing", "was not denied"),
    ("the rejudge tool record missing", "each of the four artifacts"),
    ("a digest that differs", "differs from its digest"),
    ("a file the index does not name", "the index names"),
    ("a record on another commit", "not this run, job and commit"),
    ("a seat C record on another run", "not this run, job and commit"),
    ("the recording run on another commit than the manifest", "the record on"),
    ("a manifest with no head_sha", "names no head_sha"),
    ("a file named reach-index.json inside an artifact folder", "the index names"),
    ("a reach file named manifest.json", "takes a record's file name"),
    ("a reach file that is not UTF-8 JSON", "not UTF-8 JSON text"),
    ("a reach file with no format field", "not a JSON object with a format field"),
    ("a run that wrote no record and states no cause", "states why"),
    ("two runs that wrote the record", "exactly one run folder says it wrote"),
    ("no run that wrote the record", "exactly one run folder says it wrote"),
    ("an index of another run", "names another slot or run"),
    ("a slot folder missing before a later one", "run from 01 with none missing"),
    ("a slot without a record that is not the highest", "only the highest slot folder"),
    ("a file in a slot folder", "only folders sit"),
])
def test_a_timer_slot_whose_reach_folders_fail_a_check_is_refused(tmp_path, what, match):
    slot = _slot(tmp_path)
    run = slot / "reach" / "111"
    tool_live, tool_rej = "live-eval-tool-reach-trials-111/tool-reach.json", "live-eval-tool-reach-rejudge-111/tool-reach.json"
    if what == "no reach folder":
        shutil.rmtree(slot / "reach")
    elif what == "a probe not denied in live-eval":
        _edit(run, tool_live, lambda d: d["probes"].append({"tool": "vvp", "denied": False}))
    elif what == "a probe not denied in rejudge":
        _edit(run, tool_rej, lambda d: d.update(every_denied=False))
    elif what == "no probes":
        _edit(run, tool_live, lambda d: d.update(probes=[]))
    elif what == "the live-eval tool record missing":
        (run / tool_live).unlink()
        shutil.rmtree(run / "live-eval-tool-reach-trials-111")
        _reindex(run, missing=["live-eval-tool-reach-trials-111"])
    elif what == "the rejudge tool record missing":
        shutil.rmtree(run / "live-eval-tool-reach-rejudge-111")
        _reindex(run)
    elif what == "a digest that differs":
        (run / tool_live).write_text((run / tool_live).read_text(encoding="utf-8") + "\n", encoding="utf-8")
    elif what == "a file the index does not name":
        (run / "extra.json").write_text('{"format": "x"}', encoding="utf-8")
    elif what == "a record on another commit":
        _edit(run, tool_rej, lambda d: d.update(commit="b" * 40))
    elif what == "a seat C record on another run":
        _edit(run, "live-eval-fw-reach-trials-111/fw-reach.json", lambda d: d["run"].update(id="999"))
    elif what == "the recording run on another commit than the manifest":
        (slot / "2026-11-23-claude-code-m" / "manifest.json").write_text(json.dumps({"head_sha": "c" * 40}), encoding="utf-8")
    elif what == "a manifest with no head_sha":
        (slot / "2026-11-23-claude-code-m" / "manifest.json").write_text("{}", encoding="utf-8")
    elif what == "a file named reach-index.json inside an artifact folder":
        (run / "live-eval-tool-reach-trials-111" / INDEX).write_bytes(b"\xff")
    elif what == "a reach file named manifest.json":
        (run / "live-eval-tool-reach-trials-111" / "manifest.json").write_text("{}", encoding="utf-8")
    elif what == "a reach file that is not UTF-8 JSON":
        (run / tool_live).write_bytes(b"\xff\xfe\x00")
        _reindex(run)
    elif what == "a reach file with no format field":
        _edit(run, tool_live, lambda d: d.pop("format"))
    elif what == "a run that wrote no record and states no cause":
        _run(slot, "90", wrote=False, jobs=("trials",), cause=None)
    elif what == "two runs that wrote the record":
        _run(slot, "222", wrote=True)
    elif what == "no run that wrote the record":
        _reindex(run, recorded=False, no_record_cause="none")
    elif what == "an index of another run":
        _reindex(run, run="222")
    elif what == "a slot folder missing before a later one":
        _slot(tmp_path, 3)
    elif what == "a slot without a record that is not the highest":
        _slot(tmp_path, 2, record=False)
        _slot(tmp_path, 3, record=False)
    elif what == "a file in a slot folder":
        (slot / "notes.txt").write_text("x", encoding="utf-8")
    with pytest.raises(AssertionError, match=match):
        _check_slots_reach(tmp_path)


def test_a_slot_redispatched_after_a_stop_may_record_on_a_later_commit_than_the_next_slot(tmp_path):
    # Seventh addendum, decision T2, item 7: at width two, slot 1's first run stops at job level with no trial while
    # slot 2 runs and records on commit A; slot 1 is dispatched again from a later commit B and records there.
    earlier, later = "a" * 40, "b" * 40
    one = tmp_path / "g3-timer" / "slot-01"
    record = one / "2026-11-23-claude-code-m"
    record.mkdir(parents=True)
    (record / "manifest.json").write_text(json.dumps({"id": "r", "head_sha": later}), encoding="utf-8")
    (record / "rejudge.json").write_text("{}", encoding="utf-8")
    _run(one, "90", wrote=False, jobs=("trials",), head=earlier, cause="exit 2, bad input")
    _run(one, "113", wrote=True, head=later)
    _slot(tmp_path, 2, head=earlier)  # run 111, dispatched between slot 1's two runs
    _check_slots_reach(tmp_path)


# --- The overlap of the timer's slots (seventh addendum, decision T5, item 2) ------------------------------------
#
# Two slots are in flight at most, always two adjacent slots, one of each arm (decision T1). The committed records show
# it: among the timer's slot records, any two whose manifests' times overlap are records of adjacent slots. The check
# reads the times and states none.


def _manifest_times(folder: Path, where: str) -> tuple[datetime, datetime]:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    try:
        start, finish = (datetime.fromisoformat(manifest[key]) for key in ("started_at", "finished_at"))
    except (KeyError, TypeError, ValueError) as error:
        raise AssertionError(f"{where}: the manifest's started_at and finished_at do not read as times") from error
    assert start <= finish, f"{where}: the manifest finishes before it starts"
    return start, finish


def _check_slot_overlap(root: Path) -> None:
    timed = []
    for slot in sorted(root.glob("g3-timer/slot-*")):
        match = SLOT_FOLDER.fullmatch(slot.name)
        if not (slot.is_dir() and match):
            continue  # not a slot folder: the reach check refuses it
        for path in sorted(slot.rglob("manifest.json")):
            if slot / "reach" not in path.parents:
                where = path.parent.relative_to(root).as_posix()
                timed.append((int(match.group(1)), where, *_manifest_times(path.parent, where)))
    for i, (n, where, start, finish) in enumerate(timed):
        for m, other, start2, finish2 in timed[i + 1:]:
            if start < finish2 and start2 < finish:
                assert abs(n - m) == 1, f"{where} and {other} overlap in time and are not adjacent slots"


def test_committed_timer_slot_records_overlap_only_with_an_adjacent_slot():
    # With no slot record yet this passes; the fixture tests below show the check bites once records exist.
    _check_slot_overlap(EVALS / "results")


def _timed_slot(root: Path, n: int, start: int, finish: int, *, times: bool = True) -> None:
    """A slot record whose manifest runs from `start` to `finish` hours after AT."""
    folder = root / "g3-timer" / f"slot-{n:02d}" / "2026-11-23-claude-code-m"
    folder.mkdir(parents=True)
    hour = AT.timestamp()
    manifest = {"id": "r", "head_sha": SHA}
    if times:
        manifest.update(started_at=datetime.fromtimestamp(hour + 3600 * start, timezone.utc).isoformat(),
                        finished_at=datetime.fromtimestamp(hour + 3600 * finish, timezone.utc).isoformat())
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_slot_records_that_overlap_only_with_an_adjacent_slot_pass(tmp_path):
    _check_slot_overlap(tmp_path)  # no record at all
    for n, start, finish in ((1, 0, 4), (2, 1, 6), (3, 5, 9), (4, 9, 12), (5, 12, 14)):
        _timed_slot(tmp_path, n, start, finish)  # 1 with 2, 2 with 3; 3 ends as 4 starts; 4 ends as 5 starts
    # A reach folder's files are no record and carry no times.
    _put(tmp_path / "g3-timer" / "slot-01" / "reach" / "111", "live-eval-tool-reach-trials-111/tool-reach.json",
         {"format": "nirmaan.tool-reach"})
    _check_slot_overlap(tmp_path)


@pytest.mark.parametrize("slots, match", [
    (((1, 0, 4), (2, 5, 8), (3, 2, 6)), "slot-01/.* and .*slot-03/.* overlap"),  # two of one arm together
    (((1, 0, 6), (2, 1, 6), (3, 2, 6)), "not adjacent slots"),  # three in flight at once
    (((1, 0, 2), (2, 1, 3), (5, 2, 4)), "slot-02/.* and .*slot-05/.* overlap"),  # a slot outside the window
])
def test_slot_records_that_overlap_with_a_slot_that_is_not_adjacent_are_refused(tmp_path, slots, match):
    for n, start, finish in slots:
        _timed_slot(tmp_path, n, start, finish)
    with pytest.raises(AssertionError, match=match):
        _check_slot_overlap(tmp_path)


def test_a_slot_record_whose_manifest_holds_no_times_is_refused(tmp_path):
    _timed_slot(tmp_path, 1, 0, 1, times=False)
    with pytest.raises(AssertionError, match="do not read as times"):
        _check_slot_overlap(tmp_path)


# --- The plan's per-stage values (gate WF28; fifth addendum, decision F3, item 1) ----------------------------------
#
# A dated addition to the plan states, for each arm of each case, every stage's skills and skill digests and the digest
# over the first n stages (the timer's before slot 1; the register block's before slot 21, fifth addendum, decision F4,
# item 2). A later dated addition may state a table again, which then replaces the earlier one for that case and arm.
# The stated values must give the stated digests with `flow_digest`, and the digest over every stage must be the arm's
# flow digest in the latest values table of the plan that states it for that case. A values table names its case in
# its first row (`Case, <id>, case digest`); the rows after it in the same section are that case's.

PLAN = EVALS / "plans" / "2026-11-22-g3-whole-flow.md"
TIMER_CASE, REGS_CASE = "flow/axil-timer", "flow/axi4-lite-regs-driver"
_CASE = r"`(flow/[^`]+)`"
_ARM = r"(with documents \(on\)|without documents \(off\))"
_DIGEST = r"`(sha256:[0-9a-f]{64})`"
STAGE_ROW = re.compile(rf"^\| {_CASE} \| {_ARM} \| (\d+) \| `([^`]+)` \| `([^`]+)` \| {_DIGEST} \|$")
PREFIX_ROW = re.compile(rf"^\| {_CASE} \| {_ARM} \| (\d+) \| `([^`]+)` \| {_DIGEST} \|$")
CASE_ROW = re.compile(rf"^\| Case, {_CASE}, case digest \|.* {_DIGEST} \|$")
VALUE_ROW = re.compile(rf"^\| (Whole-flow fingerprint|Flow digest), (with|without) documents \|.* {_DIGEST} \|$")
ARMS = {"with documents (on)": "with", "without documents (off)": "without"}


def _plan_values(text: str) -> dict[str, dict[str, str]]:
    """Per case, the latest case digest, whole-flow fingerprint and flow digest of each arm the plan's values tables
    state (keys `case digest`, `whole-flow fingerprint, with`, `flow digest, without` and so on)."""
    values: dict[str, dict[str, str]] = {}
    case = None
    for line in text.splitlines():
        if line.startswith("## "):
            case = None
        elif match := CASE_ROW.match(line):
            case = match.group(1)
            values.setdefault(case, {})["case digest"] = match.group(2)
        elif match := VALUE_ROW.match(line):
            assert case, f"a value row with no case row before it in its section: {line[:60]}"
            values[case][f"{match.group(1).lower()}, {match.group(2)}"] = match.group(3)
    return values


def _stage_tables(text: str, case: str = TIMER_CASE) -> tuple[dict, dict, dict]:
    """The case's latest stage table, digest table and flow digest of each arm; a restated table is in a dated
    addition."""
    stages: dict[str, dict[int, tuple[str, dict[str, str]]]] = {}
    prefixes: dict[str, dict[int, tuple[str, str]]] = {}
    values = _plan_values(text).get(case, {})
    flows = {arm: values[f"flow digest, {arm}"] for arm in ARMS.values() if f"flow digest, {arm}" in values}
    section, dated, seen = 0, False, {}
    for line in text.splitlines():
        if line.startswith("## "):
            section, dated = section + 1, "Dated addition" in line
            continue
        match, kind = STAGE_ROW.match(line), "stages"
        if not match:
            match, kind = PREFIX_ROW.match(line), "prefixes"
        if not match or match.group(1) != case:
            continue
        arm, n = ARMS[match.group(2)], int(match.group(3))
        table = stages if kind == "stages" else prefixes
        if seen.get((kind, arm), section) != section:
            assert dated, f"the {kind} table of the {arm}-documents arm is stated again outside a dated addition"
            table.pop(arm, None)
        seen[(kind, arm)] = section
        rows = table.setdefault(arm, {})
        if kind == "stages":
            name, skills = rows.setdefault(n, (match.group(4), {}))
            assert name == match.group(4), f"{arm}: stage {n} is named {name!r} and {match.group(4)!r}"
            assert match.group(5) not in skills, f"{arm}: stage {n} states skill {match.group(5)!r} twice"
            skills[match.group(5)] = match.group(6)
        else:
            assert n not in rows, f"{arm}: the digest over the first {n} stages is stated twice"
            rows[n] = (match.group(4), match.group(5))
    return stages, prefixes, flows


def _check_stage_tables(text: str, exercised: dict, case: str = TIMER_CASE) -> None:
    stages, prefixes, flows = _stage_tables(text, case)
    for arm in ARMS.values():
        st, pr = stages.get(arm), prefixes.get(arm)
        assert st and pr, f"the {arm}-documents arm has no stage table or no digest table"
        count = list(range(1, len(st) + 1))
        assert sorted(st) == count and sorted(pr) == count, f"{arm}: the stages and the digests are not both 1 to N"
        assert [st[n][0] for n in count] == list(exercised), f"{arm}: the stages are not the case's, in order"
        for n in count:
            assert sorted(st[n][1]) == sorted(exercised[st[n][0]]), f"{arm}: stage {n}'s skills are not the case's"
            assert pr[n][0] == st[n][0], f"{arm}: the digest over the first {n} stages names another stage"
            given = {st[i][0]: st[i][1] for i in range(1, n + 1)}
            assert flow_digest(given) == pr[n][1], f"{arm}: the stated values do not give the digest over {n} stages"
        assert pr[count[-1]][1] == flows.get(arm), f"{arm}: the digest over every stage is not the arm's flow digest"


def _exercised(case_id: str) -> dict[str, list[str]]:
    case = {c.id: c for c in load_cases(EVALS, flow="whole")}[case_id]
    return {stage: list(skills) for stage, skills in case.exercised.items()}


def _committed_slot_trials(root: Path) -> list[tuple[Path, int, dict]]:
    """Every trial of every committed whole-flow record under ``root``, with the slot its folder names."""
    found = []
    for manifest in sorted(root.rglob("manifest.json")):
        if json.loads(manifest.read_text(encoding="utf-8")).get("flow") != "whole":
            continue
        slot = next((int(m.group(1)) for part in manifest.parts if (m := SLOT_FOLDER.fullmatch(part))), None)
        for path in sorted(manifest.parent.glob("*/trial-*.json")):
            found.append((path, slot, json.loads(path.read_text(encoding="utf-8"))))
    return found


@pytest.mark.parametrize("case_id", [TIMER_CASE, REGS_CASE])
def test_the_plan_states_each_stage_of_each_case_and_its_digests_give_the_stated_flow_digests(case_id):
    """The timer's tables are stated (gate WF28). The register block's are checked the same way once stated, and no
    record of a case whose tables the plan does not state may be committed (wave 2 close, decision M7, item 2)."""
    text = PLAN.read_text(encoding="utf-8")
    stages, prefixes, _ = _stage_tables(text, case_id)
    if not stages and not prefixes and case_id != TIMER_CASE:
        recorded = [p for p, _, t in _committed_slot_trials(EVALS / "results") if t["result"]["case"] == case_id]
        assert not recorded, f"the plan states no stage tables for {case_id}, yet its records are committed: {recorded}"
        return
    _check_stage_tables(text, _exercised(case_id), case_id)


def _tables(rows: dict, flows: dict, stages=None, case: str = TIMER_CASE, values: dict | None = None) -> str:
    """A plan-like text with a values table and one dated addition holding both tables for both arms."""
    values = values or {}
    lines = ["## 1. Values", f"| Case, `{case}`, case digest | `{values.get('case digest', 'sha256:' + '9' * 64)}` |",
             *(f"| Whole-flow fingerprint, {arm} documents | `{values[f'whole-flow fingerprint, {arm}']}` |"
               for arm in ARMS.values() if f"whole-flow fingerprint, {arm}" in values),
             *(f"| Flow digest, {arm} documents | `{d}` |" for arm, d in flows.items()),
             "## 2. Dated addition (2026-11-24): stages", "| Case | Arm | n | Stage | Skill | Skill digest |"]
    order = list(stages or rows["with"])
    for words, arm in ARMS.items():
        for n, stage in enumerate(order, start=1):
            lines += [f"| `{case}` | {words} | {n} | `{stage}` | `{skill}` | `{rows[arm][stage][skill]}` |"
                      for skill in sorted(rows[arm][stage])]
    lines.append("| Case | Arm | n | Last stage | Digest over the first n stages |")
    for words, arm in ARMS.items():
        for n, stage in enumerate(order, start=1):
            digest = flow_digest({s: rows[arm][s] for s in order[:n]})
            lines.append(f"| `{case}` | {words} | {n} | `{stage}` | `{digest}` |")
    return "\n".join(lines) + "\n"


def _synthetic(exercised: dict = EXERCISED):
    rows = {arm: {stage: {skill: "sha256:" + hashlib.sha256(f"{arm}{skill}".encode()).hexdigest() for skill in skills}
                  for stage, skills in exercised.items()} for arm in ARMS.values()}
    return rows, {arm: flow_digest(rows[arm]) for arm in ARMS.values()}


@pytest.mark.parametrize("case_id", [TIMER_CASE, REGS_CASE])
def test_stage_tables_whose_digests_follow_from_their_values_pass(case_id):
    exercised = EXERCISED if case_id == TIMER_CASE else _exercised(case_id)
    rows, flows = _synthetic(exercised)
    text = _tables(rows, flows, case=case_id)
    _check_stage_tables(text, exercised, case_id)
    # A later dated addition may state the tables again; the latest rules.
    later = {arm: {stage: {skill: "sha256:" + "0" * 64 for skill in skills} for stage, skills in exercised.items()}
             for arm in ARMS.values()}
    again = _tables(later, {arm: flow_digest(later[arm]) for arm in ARMS.values()}, case=case_id).replace(
        "## 1.", "## 3.").replace("## 2. Dated addition", "## 4. Dated addition")
    _check_stage_tables(text + again, exercised, case_id)


def test_one_case_s_tables_and_values_are_never_read_as_the_other_s():
    """Both cases in one plan: each case's tables are its own, and each flow digest is read from its own case's values
    table, so the timer's four stages never stand for the register block's five, nor its digests for theirs."""
    regs = _exercised(REGS_CASE)
    timer_text = _tables(*_synthetic(EXERCISED))
    regs_text = _tables(*_synthetic(regs), case=REGS_CASE).replace("## 1.", "## 3.").replace("## 2.", "## 4.")
    for text in (timer_text + regs_text, regs_text + timer_text):
        _check_stage_tables(text, EXERCISED, TIMER_CASE)
        _check_stage_tables(text, regs, REGS_CASE)
    assert _stage_tables(timer_text, REGS_CASE) == ({}, {}, {})  # no fall back to the timer's
    with pytest.raises(AssertionError, match="no stage table"):
        _check_stage_tables(timer_text, regs, REGS_CASE)
    with pytest.raises(AssertionError, match="no case row before it"):
        _plan_values("## 1. Values\n| Flow digest, with documents | `sha256:" + "0" * 64 + "` |\n")


@pytest.mark.parametrize("what, match", [
    ("a skill digest changed", "do not give the digest"),
    ("a digest over n stages changed", "do not give the digest"),
    ("a flow digest that is not the last", "is not the arm's flow digest"),
    ("a skill missing", "skills are not the case's"),
    ("an arm missing", "no stage table"),
    ("the tables stated again outside a dated addition", "outside a dated addition"),
    ("a stage out of order", "not the case's, in order"),
])
def test_stage_tables_that_do_not_give_their_digests_are_refused(what, match):
    rows, flows = _synthetic()
    text = _tables(rows, flows)
    lines = text.splitlines()
    if what == "a skill digest changed":
        old = rows["with"]["microarchitecture"]["rtl_microarchitecture"]
        text = text.replace(f"| `{old}` |", f"| `sha256:{'1' * 64}` |", 1)
    elif what == "a digest over n stages changed":
        row = next(i for i, line in enumerate(lines) if PREFIX_ROW.match(line))
        lines[row] = re.sub(r"sha256:[0-9a-f]{64}", "sha256:" + "2" * 64, lines[row])
        text = "\n".join(lines) + "\n"
    elif what == "a flow digest that is not the last":
        text = text.replace(flows["without"], "sha256:" + "3" * 64, 1)
    elif what == "a skill missing":
        text = "\n".join(line for line in lines if "`fsm_design`" not in line or "with documents" not in line) + "\n"
    elif what == "an arm missing":
        text = "\n".join(line for line in lines if "without documents (off)" not in line) + "\n"
    elif what == "the tables stated again outside a dated addition":
        start = next(i for i, line in enumerate(lines) if line.startswith("## 2.")) + 1
        text = text + "## 3. Not dated\n" + "\n".join(lines[start:]) + "\n"
    elif what == "a stage out of order":
        text = _tables(rows, flows, stages=["interface-spec", "requirements", "microarchitecture",
                                            "rtl-implementation"])
    with pytest.raises(AssertionError, match=match):
        _check_stage_tables(text, EXERCISED)


# --- Every committed slot record against the plan (fifth addendum, decision F3, item 3; wave 2 close, decision M7) ---
#
# The check the plan's section 24.2 states in words, made here on every committed slot record so that it controls what
# merges: every comparison made before decision F3 (case and arm of the slot, purpose, flow label, harness variant, case
# digest, fingerprint, CLI), and in place of the one flow digest comparison its four items, against the latest tables
# the plan states for the record's case and arm. A record whose case has no stage tables in the plan is refused, with
# no fall back to another case's. It runs in the ordinary test job: no secret, no dispatch.

SLOT_ROW = re.compile(r"^\| (\d+) \| (flow/[^ |]+) \| (?:with|without) documents \((on|off)\) \|$", re.M)
CLI_PIN = re.compile(r"Claude Code (\d+\.\d+\.\d+), the pin")
KNOWLEDGE = {"on": "with", "off": "without"}
NOT_RUN, COMPLETED = "not run", "completed"


def _slot_record_problems(trial: dict, slot: int | None, text: str) -> list[str]:
    """Why a slot record does not meet the check of decision F3, item 3 against the plan ``text``, or []."""
    result = trial.get("result") or {}
    case, arm = result.get("case"), KNOWLEDGE.get(trial.get("knowledge"))
    planned = {int(n): (c, KNOWLEDGE[k]) for n, c, k in SLOT_ROW.findall(text)}
    if (case, arm) != planned.get(slot):
        return [f"case {case!r} and arm {arm!r}, planned for slot {slot}: {planned.get(slot)!r}"]
    stages_t, prefixes_t, _ = _stage_tables(text, case)
    plan, prefixes = stages_t.get(arm), prefixes_t.get(arm)
    if not plan or not prefixes:
        return [f"the plan states no stage tables for {case}, arm {arm} documents"]
    plan = [plan[n] for n in sorted(plan)]
    prefixes = [prefixes[n][1] for n in sorted(prefixes)]
    values, cli = _plan_values(text).get(case, {}), CLI_PIN.search(text)
    want = {"purpose": (trial.get("purpose"), "evidence"), "flow label": (trial.get("flow"), "whole"),
            "harness variant": (trial.get("harness_variant"), "default"),
            "case digest": (result.get("case_digest"), values.get("case digest")),
            "fingerprint": (result.get("harness"), values.get(f"whole-flow fingerprint, {arm}")),
            "CLI": (result.get("cli"), cli.group(1) if cli else None), "replay": (result.get("replay"), False)}
    out = [f"{k} {got!r}, planned {exp!r}" for k, (got, exp) in want.items() if got != exp or exp is None]
    stages = [st if isinstance(st, dict) else {} for st in trial.get("stages") or []]
    # 1. The stage names, in order.
    if [st.get("stage") for st in stages] != [name for name, _ in plan]:
        out.append(f"stage names {[st.get('stage') for st in stages]!r}, planned {[name for name, _ in plan]!r}")
    # 2. The seated stages first; every later one "not run" with nothing done; a stop after an incomplete stage.
    seated = next((i for i, st in enumerate(stages) if st.get("status") == NOT_RUN), len(stages))
    for st in stages[seated:]:
        if st.get("status") != NOT_RUN:
            out.append(f"stage {st.get('stage')!r} is {st.get('status')!r} after a stage not run")
        done = [k for k in ("skills", "attempts", "model_calls", "gate_runs") if st.get(k)]
        if done:
            out.append(f"stage {st.get('stage')!r} is not run but records {', '.join(done)}")
    if seated < len(stages):
        if not seated:
            out.append("no stage was seated")
        out += [f"stage {st.get('stage')!r} is {st.get('status')!r} before the last seated stage"
                for st in stages[:max(seated - 1, 0)] if st.get("status") != COMPLETED]
        if seated and stages[seated - 1].get("status") == COMPLETED:
            out.append(f"stage {stages[seated - 1].get('stage')!r} completed, yet the next stage was not run")
    # 3. Each seated stage's skills and digests, exactly.
    for i, st in enumerate(stages[:seated]):
        expected = plan[i][1] if i < len(plan) else None
        if st.get("skills") != expected:
            out.append(f"stage {st.get('stage')!r} skills {st.get('skills')!r}, planned {expected!r}")
    # 4. The flow digest: recomputed from its own seated stages, and the plan's over that many stages.
    got = trial.get("flow_digest")
    mine = flow_digest({st.get("stage"): st.get("skills") or {} for st in stages[:seated]})
    if got != mine:
        out.append(f"flow digest {got!r}, recomputed from the record's seated stages {mine!r}")
    if got != (prefixes[seated - 1] if 0 < seated <= len(prefixes) else None):
        out.append(f"flow digest {got!r} is not the plan's digest over the first {seated} stages")
    return out


def test_every_committed_slot_record_meets_the_check_of_decision_f3():
    text = PLAN.read_text(encoding="utf-8")
    found = _committed_slot_trials(EVALS / "results")
    assert len(found) >= 20  # the timer's twenty slots are committed
    for path, slot, trial in found:
        assert not _slot_record_problems(trial, slot, text), (path, _slot_record_problems(trial, slot, text))


def _committed(slot: int) -> dict:
    [(_, _, trial)] = [f for f in _committed_slot_trials(EVALS / "results" / "g3-timer" / f"slot-{slot:02d}")]
    return trial


def _seated(trial: dict) -> list[int]:
    return [i for i, st in enumerate(trial["stages"]) if st["status"] != NOT_RUN]


def _skill_digest_changed(t):
    skills = t["stages"][_seated(t)[0]]["skills"]
    skills[sorted(skills)[0]] = "sha256:" + "0" * 64


def _skills_removed(t):
    t["stages"][_seated(t)[-1]]["skills"] = {}


def _seated_after_not_run(t):
    t["stages"][0].update(status=NOT_RUN, skills={}, attempts=0, model_calls=0, gate_runs=[])


def _flow_digest_changed(t):
    t["flow_digest"] = "sha256:" + "1" * 64


#: Decision F3, item 5: the copies of a record the check must refuse, each for the change made to it.
REFUSED_COPIES = {"a stage's skill digest changed": (_skill_digest_changed, "skills"),
                  "a stage's skills removed": (_skills_removed, "skills {}"),
                  "a seated stage after a stage not run": (_seated_after_not_run, "after a stage not run"),
                  "the flow digest changed": (_flow_digest_changed, "flow digest 'sha256:1111")}


def test_a_stopped_slot_record_is_accepted_and_each_copy_of_decision_f3_item_5_is_refused():
    text = PLAN.read_text(encoding="utf-8")
    stopped = _committed(4)  # slot 4: its flow stopped at the microarchitecture stage, a failed trial of its slot
    assert [st["status"] for st in stopped["stages"]][-1] == NOT_RUN
    assert _slot_record_problems(stopped, 4, text) == []
    assert _slot_record_problems(stopped, 3, text)  # the slot of the other arm: refused
    for what, (edit, match) in REFUSED_COPIES.items():
        copy = json.loads(json.dumps(stopped))
        edit(copy)
        problems = _slot_record_problems(copy, 4, text)
        assert any(match in p for p in problems), (what, problems)
    full = _committed(3)  # a flow that seated every stage: the same copies are refused
    assert _slot_record_problems(full, 3, text) == []
    for what, (edit, match) in REFUSED_COPIES.items():
        copy = json.loads(json.dumps(full))
        edit(copy)
        assert _slot_record_problems(copy, 3, text), what


def _regs_plan() -> tuple[str, dict, dict]:
    """The plan with a synthetic dated addition for the register block: both tables of both arms and its values."""
    rows, flows = _synthetic(_exercised(REGS_CASE))
    values = {"case digest": "sha256:" + "c" * 64, "whole-flow fingerprint, with": "sha256:" + "a" * 64,
              "whole-flow fingerprint, without": "sha256:" + "b" * 64}
    addition = _tables(rows, flows, case=REGS_CASE, values=values).replace("## 1. Values", "## 90. Dated addition "
                                                                             "(test): the register block's values")
    return PLAN.read_text(encoding="utf-8") + addition.replace("## 2. Dated addition", "## 91. Dated addition"), rows, \
        values


def _regs_trial(rows: dict, values: dict, arm: str, statuses: list[str]) -> dict:
    """A register block slot record of the given arm and stage statuses, as record_run writes one."""
    words = KNOWLEDGE[arm]
    stages = [{"stage": stage, "status": status,
               **({"skills": {}, "attempts": 0, "model_calls": 0, "gate_runs": []} if status == NOT_RUN else
                  {"skills": dict(rows[words][stage]), "attempts": 1, "model_calls": 1, "gate_runs": []})}
              for stage, status in zip(rows[words], statuses)]
    digest = flow_digest({st["stage"]: st["skills"] for st in stages if st["status"] != NOT_RUN})
    return {"flow": "whole", "knowledge": arm, "purpose": "evidence", "harness_variant": "default",
            "flow_digest": digest, "stages": stages,
            "result": {"case": REGS_CASE, "case_digest": values["case digest"], "cli": "2.1.325", "replay": False,
                       "harness": values[f"whole-flow fingerprint, {words}"]}}


def test_a_register_block_record_is_checked_against_its_own_tables_including_the_firmware_stage():
    """The register block's five stages, on synthetic tables: a full flow and a flow stopped at the RTL stage are
    accepted; item 5's copies and firmware-engineer's two (the firmware stage's skill digest changed, and the firmware
    stage not run after a completed RTL stage) are refused; and without its tables the record is refused."""
    text, rows, values = _regs_plan()
    full = _regs_trial(rows, values, "on", [COMPLETED] * 4 + ["in_review"])
    stopped = _regs_trial(rows, values, "off", [COMPLETED] * 3 + ["escalated", NOT_RUN])
    assert _slot_record_problems(full, 21, text) == [] and _slot_record_problems(stopped, 22, text) == []
    for what, (edit, match) in REFUSED_COPIES.items():
        copy = json.loads(json.dumps(stopped))
        edit(copy)
        assert any(match in p for p in _slot_record_problems(copy, 22, text)), what
    firmware = json.loads(json.dumps(full))
    firmware["stages"][4]["skills"]["device_drivers"] = "sha256:" + "0" * 64
    assert any("stage 'firmware' skills" in p for p in _slot_record_problems(firmware, 21, text))
    after_rtl = _regs_trial(rows, values, "on", [COMPLETED] * 4 + [NOT_RUN])
    assert any("'rtl-implementation' completed, yet the next stage was not run" in p
               for p in _slot_record_problems(after_rtl, 21, text))
    untabled = "\n".join(line for line in text.splitlines() if not line.startswith(f"| `{REGS_CASE}` |"))
    assert _slot_record_problems(full, 21, untabled) == [
        f"the plan states no stage tables for {REGS_CASE}, arm with documents"]
    assert _slot_record_problems(full, 1, text)  # a timer slot: refused


# --- Default case sets never hold a whole-flow case -----------------------------------------------------------


def _write(root: Path, name: str, case: EvalCase) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(case.model_dump_json(), encoding="utf-8")


def test_a_whole_flow_case_is_in_no_default_case_set(tmp_path):
    single = EvalCase(id="spec/x", request=TIMER, seat="interface-spec")
    _write(tmp_path, "single.json", single)
    _write(tmp_path / "flow", "timer.json", _whole())
    assert [c.id for c in load_cases(tmp_path)] == ["spec/x"]
    assert [c.id for c in load_cases(tmp_path, flow="whole")] == ["flow/timer"]
    assert [c.id for c in load_cases(tmp_path, flow=None)] == ["flow/timer", "spec/x"]


def test_one_id_is_one_case_across_both_flows(tmp_path):
    _write(tmp_path, "single.json", EvalCase(id="flow/timer", request=TIMER, seat="interface-spec"))
    _write(tmp_path / "flow", "timer.json", _whole())
    with pytest.raises(EvalError, match="two cases are named"):
        load_cases(tmp_path)


def test_a_run_never_mixes_whole_flow_and_single_seat_cases(org, tmp_path):
    out = tmp_path / "results"
    single = EvalCase(id="spec/x", request=TIMER, seat="interface-spec")
    with pytest.raises(EvalError, match="one record never mixes whole-flow and single-seat"):
        record_run(org, [_whole(), single], None, trials=1, repo=ROOT, out=out)
    assert not out.exists()  # refused before anything was written


# --- The case checks -------------------------------------------------------------------------------------------


def test_a_whole_flow_case_that_credits_nothing_and_fixes_nothing_is_valid(org):
    assert validate_case(org, _whole(), ROOT) == []


@pytest.mark.parametrize("overrides, why", [
    ({"skills": ["rtl_design"]}, "a whole-flow case credits no skill, so it names none in skills"),
    ({"upstream": {"interface-spec": [{"path": "evals/spec/axi4_lite/requirements.md", "kind": "interface_spec"}]}},
     "a whole-flow case fixes no upstream stage"),
    ({"exercised": {}}, "lists the skills each stage exercises in exercised"),
    ({"exercised": {"rtl-implementation": ["no_such_skill"]}}, "exercised skill 'no_such_skill'"),
    ({"exercised": {"firmware": ["device_drivers"]}}, "exercised skills for stage 'firmware', which is not in"),
])
def test_a_whole_flow_case_is_refused_when(org, overrides, why):
    problems = validate_case(org, _whole(**overrides), ROOT)
    assert any(why in p for p in problems), problems


def test_a_single_seat_case_lists_nothing_exercised(org):
    case = EvalCase(id="spec/x", request=TIMER, seat="interface-spec", exercised={"interface-spec": ("x",)})
    assert "only a whole-flow case lists exercised skills" in validate_case(org, case, ROOT)


def test_the_shipped_whole_flow_cases_are_valid(org):
    for case in load_cases(EVALS, flow="whole"):
        assert validate_case(org, case, ROOT) == [], case.id
        assert case.skills == () and case.upstream == {}
        assert json.loads(case.model_dump_json())["flow"] == "whole"

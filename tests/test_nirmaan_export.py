"""Stage 4 (M23): the project deliverable export.

The export is a view over project state: a numbered deliverable tree whose
layout is a declared table, with provenance sidecars, an evidence folder, and a
signoff report. It never raises an assurance level, lists what is missing as
missing, flags a broken audit chain loudly, is byte-for-byte deterministic, and
writes nothing back into project state.

Every project here is built by the engine: planned, then driven the way the
other Nirmaan tests drive work.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nirmaan_helpers import GATE_TOOLS, agent, drive, gated_submit, tid
from laws import needs

from nirmaan.company.deliverables import DELIVERABLE_FOLDERS
from nirmaan.export import (
    ExportError,
    export_project,
    folders,
    register_folder,
    unregister_folder,
    validate_folders,
)
from nirmaan.models import Assurance, DeliverableFolder, EvidenceKind, ExportSection, Verdict
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ToolBroker
from nirmaan.work import ProjectStore

RTL = Path(__file__).parent / "fixtures" / "rtl"
COUNTER = RTL / "counter.v"
BRIDGE = "Create a 4-port AXI-to-NoC bridge."


@pytest.fixture()
def bridge(nirmaan_org, fixed_clock):
    return Orchestrator(nirmaan_org, clock=fixed_clock).plan(BRIDGE)


@pytest.fixture()
def midway(bridge, tmp_path):
    """Approved work up to RTL, a verification plan that is verified but not approved,
    and a lint report that is only executed. Two gates signed off, the rest not.

    M38: the plan is a plan file that passed a real ``vplan.check`` against the approved requirements
    spec before review, where it was a Markdown document with no check before."""
    drive(bridge, until=tid(bridge, "rtl-lint"))
    plan = tid(bridge, "dv-plan")
    owner = agent(bridge.task(plan).owner)
    bridge.start(plan, owner)
    gated_submit(bridge, plan, workspace=tmp_path / "inputs")
    bridge.review(plan, agent(bridge.task(plan).reviewer), Verdict.APPROVE, "complete and testable")
    lint = tid(bridge, "rtl-lint")
    lint_owner = agent(bridge.task(lint).owner)
    bridge.start(lint, lint_owner)
    bridge.submit(lint, lint_owner, [{"kind": "lint_report", "title": "Lint of the bridge"}])
    return bridge


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _sidecars(root: Path) -> dict[str, dict]:
    found = {}
    for path in root.rglob("*.provenance.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        found[data["artifact"]] = {**data, "_path": path.relative_to(root).as_posix()}
    return found


# --- The folder table drives the layout -----------------------------------------------------


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_the_folder_table_drives_the_layout(midway, tmp_path):
    out = tmp_path / "out"
    export_project(midway.org, midway.state, out)
    table = folders()
    assert sorted(p.name for p in out.iterdir() if p.is_dir()) == sorted(f.id for f in table)
    assert [f.id for f in table] == sorted(f.id for f in DELIVERABLE_FOLDERS)
    by_kind = {k: f.id for f in table for k in f.artifact_kinds}
    for art_id, data in _sidecars(out).items():
        kind = midway.state.artifacts[art_id].kind
        assert data["_path"].startswith(by_kind[kind] + "/"), (art_id, data["_path"])
    assert (out / "INDEX.md").is_file()


def test_every_workflow_output_is_routed_and_the_table_is_valid(nirmaan_org):
    validate_folders(folders())
    routed = {k for f in folders() for k in f.artifact_kinds}
    for workflow in nirmaan_org.workflows.values():
        for stage in workflow.stages:
            for kind in stage.outputs:
                assert kind in routed, (workflow.id, stage.id, kind)


def test_a_table_that_claims_a_kind_twice_is_refused():
    clash = [*folders(), DeliverableFolder(id="99_clash", title="Clash", artifact_kinds=("rtl_source",))]
    with pytest.raises(ExportError, match="rtl_source"):
        validate_folders(clash)


# --- Honesty ---------------------------------------------------------------------------------


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_assurance_is_preserved_and_labelled_never_raised(midway, tmp_path):
    out = tmp_path / "out"
    export_project(midway.org, midway.state, out)
    sidecars = _sidecars(out)
    assert set(sidecars) == set(midway.state.artifacts)
    for art_id, art in midway.state.artifacts.items():
        data = sidecars[art_id]
        assert data["assurance"] == art.assurance.value
        assert f".{art.assurance.value.upper()}." in data["_path"]
    levels = {a.assurance for a in midway.state.artifacts.values()}
    assert {Assurance.EXECUTED, Assurance.VERIFIED, Assurance.APPROVED} <= levels
    index = (out / "INDEX.md").read_text(encoding="utf-8")
    lint = next(a for a in midway.state.artifacts.values() if a.kind == "lint_report")
    assert lint.assurance is Assurance.EXECUTED
    line = next(ln for ln in index.splitlines() if lint.id in ln)
    assert "EXECUTED" in line and "not verified" in line


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_the_sidecar_carries_provenance_and_hashes(midway, tmp_path):
    out = tmp_path / "out"
    export_project(midway.org, midway.state, out)
    art = next(a for a in midway.state.artifacts.values() if a.kind == "verification_plan")
    data = _sidecars(out)[art.id]
    task = midway.state.tasks[art.task]
    assert data["produced_by"] == art.produced_by
    assert data["task"]["id"] == task.id and data["requirement"]["id"] == task.requirement
    assert data["inputs"]["artifact_kinds"] == list(task.inputs)
    assert data["evidence"] and all(e["id"] in midway.state.evidence for e in data["evidence"])
    content = out / data["files"]["content"]
    assert hashlib.sha256(content.read_bytes()).hexdigest() == data["hashes"]["content_sha256"]
    copy = out / data["files"]["location_copy"]
    assert copy.read_text(encoding="utf-8").startswith('{\n  "format": "nirmaan.vplan"')
    assert hashlib.sha256(copy.read_bytes()).hexdigest() == data["hashes"]["location_sha256"]
    assert any(e["action"] == "task.submit" for e in data["audit"])
    assert data["hashes"]["recorded_digest"] == "sha256:" + data["hashes"]["location_sha256"]
    assert "matches the digest recorded" in data["location"]["note"]


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_a_location_that_changed_since_recording_is_flagged(midway, tmp_path):
    art = next(a for a in midway.state.artifacts.values() if a.kind == "verification_plan")
    Path(art.location).write_text("# Verification plan\n\nQuietly edited.\n", encoding="utf-8")
    out = tmp_path / "out"
    export_project(midway.org, midway.state, out)
    data = _sidecars(out)[art.id]
    assert "DOES NOT MATCH" in data["location"]["note"]
    assert data["hashes"]["recorded_digest"] == art.digest != "sha256:" + data["hashes"]["location_sha256"]


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_missing_deliverables_are_reported_not_filled(midway, tmp_path):
    out = tmp_path / "out"
    report = export_project(midway.org, midway.state, out)
    formal = tid(midway, "formal")
    assert any(m.task == formal and m.kind == "formal_report" for m in report.missing)
    formal_dir = next(f.id for f in folders() if "formal_report" in f.artifact_kinds)
    files = sorted(p.name for p in (out / formal_dir).iterdir())
    assert files == ["README.md"]  # no stand-in for the missing report
    readme = (out / formal_dir / "README.md").read_text(encoding="utf-8")
    assert "Missing" in readme and formal in readme and "planned" in readme
    index = (out / "INDEX.md").read_text(encoding="utf-8")
    assert "MISSING" in index and formal in index
    produced = {a.task for a in midway.state.artifacts.values()}
    assert not any(m.task in produced for m in report.missing)


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_signoff_shows_only_what_the_engine_recorded(midway, tmp_path):
    out = tmp_path / "out"
    export_project(midway.org, midway.state, out)
    signoff_dir = next(f.id for f in folders() if ExportSection.SIGNOFF in f.sections)
    data = json.loads((out / signoff_dir / "signoff.json").read_text(encoding="utf-8"))
    gates = {t.id: t for t in midway.state.tasks.values() if t.gate}
    assert {g["task"] for g in data["gates"]} == set(gates)
    approvals = {e.subject: e for e in midway.state.audit if e.action == "gate.approve"}
    for gate in data["gates"]:
        assert gate["signed_off"] == (gate["task"] in approvals)
        if gate["signed_off"]:
            assert gate["audit"]["hash"] == approvals[gate["task"]].hash
    assert 0 < data["signed_off"] < len(gates)
    text = (out / signoff_dir / "signoff.md").read_text(encoding="utf-8")
    assert "Not signed off" in text


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_a_tampered_audit_chain_is_exported_loudly(midway, tmp_path):
    root = tmp_path / "store"
    path = ProjectStore(root).save(midway.state)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["audit"][3]["reason"] = "quietly rewritten"
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="audit"):
        ProjectStore(root).load(midway.state.project.id)
    state = ProjectStore(root).load(midway.state.project.id, verify=False)
    out = tmp_path / "out"
    report = export_project(midway.org, state, out)
    assert report.chain_problems and "entry 3" in report.chain_problems[0]
    index = (out / "INDEX.md").read_text(encoding="utf-8")
    assert "AUDIT CHAIN FAILED VERIFICATION" in index.splitlines()[2]
    evidence_dir = next(f.id for f in folders() if ExportSection.AUDIT_CHAIN in f.sections)
    chain = json.loads((out / evidence_dir / "audit_chain.json").read_text(encoding="utf-8"))
    assert chain["verify_chain"]["intact"] is False and chain["verify_chain"]["problems"]


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_an_intact_chain_is_reported_intact(midway, tmp_path):
    out = tmp_path / "out"
    report = export_project(midway.org, midway.state, out)
    assert report.chain_problems == []
    evidence_dir = next(f.id for f in folders() if ExportSection.AUDIT_CHAIN in f.sections)
    chain = json.loads((out / evidence_dir / "audit_chain.json").read_text(encoding="utf-8"))
    assert chain["verify_chain"] == {"intact": True, "problems": []}
    assert chain["head_hash"] == midway.state.audit[-1].hash
    assert len(chain["entries"]) == len(midway.state.audit)


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_the_evidence_folder_holds_trace_reviews_and_tool_runs(midway, tmp_path):
    out = tmp_path / "out"
    export_project(midway.org, midway.state, out)
    evidence_dir = out / next(f.id for f in folders() if ExportSection.TRACE in f.sections)
    trace = json.loads((evidence_dir / "requirement_trace.json").read_text(encoding="utf-8"))
    assert trace["requirement"]["id"] == midway.state.project.requirement.id
    traced = {a["id"] for t in trace["tasks"] for a in t["artifacts"]}
    assert traced == set(midway.state.artifacts)
    reviews = json.loads((evidence_dir / "reviews.json").read_text(encoding="utf-8"))
    assert {r["id"] for r in reviews} == set(midway.state.reviews)


# --- Determinism and read-only ---------------------------------------------------------------


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_the_export_is_deterministic(midway, tmp_path):
    export_project(midway.org, midway.state, tmp_path / "a")
    export_project(midway.org, midway.state, tmp_path / "b")
    first, second = _tree(tmp_path / "a"), _tree(tmp_path / "b")
    assert first == second and len(first) > 20


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_a_saved_and_reloaded_state_exports_identically(midway, tmp_path):
    export_project(midway.org, midway.state, tmp_path / "a")
    ProjectStore(tmp_path / "store").save(midway.state)
    loaded = ProjectStore(tmp_path / "store").load(midway.state.project.id)
    export_project(midway.org, loaded, tmp_path / "b")
    assert _tree(tmp_path / "a") == _tree(tmp_path / "b")


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_the_export_refuses_a_non_empty_directory(midway, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "stale.txt").write_text("old", encoding="utf-8")
    with pytest.raises(ExportError, match="not empty"):
        export_project(midway.org, midway.state, out)


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_the_cli_export_changes_nothing(midway, tmp_path):
    from nirmaan.cli import app

    root = tmp_path / "store"
    path = ProjectStore(root).save(midway.state)
    before = path.read_bytes()
    audit_before = list(midway.state.audit)
    result = CliRunner().invoke(app, ["export", midway.state.project.id, "--out", str(tmp_path / "out"),
                                      "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert path.read_bytes() == before
    assert sorted(p.name for p in (root / "projects").iterdir()) == [path.name]
    assert midway.state.audit == audit_before
    assert (tmp_path / "out" / "INDEX.md").is_file()


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_the_cli_exports_a_broken_chain_and_says_so(midway, tmp_path):
    from nirmaan.cli import app

    root = tmp_path / "store"
    path = ProjectStore(root).save(midway.state)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["audit"].pop(5)
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["export", midway.state.project.id, "--out", str(tmp_path / "out"),
                                      "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert "AUDIT CHAIN FAILED VERIFICATION" in result.output


# --- Real tool runs --------------------------------------------------------------------------


@needs("verilator", *GATE_TOOLS)  # M27: the RTL stage before it is gated
def test_a_real_lint_runs_log_and_result_are_copied(bridge, tmp_path):
    lint = tid(bridge, "rtl-lint")
    drive(bridge, until=lint)
    owner = agent(bridge.task(lint).owner)
    bridge.start(lint, owner)
    bridge.submit(lint, owner, [{"kind": "lint_report", "title": "Lint of counter"}])
    run, _ = ToolBroker(bridge).invoke(owner, "lint.run", {"sources": str(COUNTER), "workdir": str(tmp_path / "w")}, lint)
    bridge.record_evidence(lint, owner, EvidenceKind.TOOL_RUN, run.summary, reference=run.references[0], tool_run=run.id)
    out = tmp_path / "out"
    export_project(bridge.org, bridge.state, out)
    evidence_dir = out / next(f.id for f in folders() if ExportSection.TOOL_RUNS in f.sections)
    record = json.loads((evidence_dir / "tool_runs" / run.id / "run.json").read_text(encoding="utf-8"))
    assert record["tool"] == "lint.run" and record["succeeded"] is True
    for ref, copied in zip(run.references, record["references"]):
        assert copied["reference"] == ref and copied["copied_as"]
        data = (out / copied["copied_as"]).read_bytes()
        assert data == Path(ref).read_bytes()
        assert hashlib.sha256(data).hexdigest() == copied["sha256"]


def test_a_reference_that_is_not_a_file_is_recorded_as_such(bridge, tmp_path):
    """A VeriTriage run cites a session ID: recorded as given, never turned into a file."""
    from nirmaan.org import AuthorityService

    authority = AuthorityService(bridge.org)
    role = next(r for r in bridge.org.roles if authority.may_use_tool(r, "veritriage.investigate")[0])
    params = {"paths": str(RTL.parent / "axi_timeout.log"), "workspace": str(tmp_path / "vt")}
    run, _ = ToolBroker(bridge).invoke(agent(role), "veritriage.investigate", params)
    out = tmp_path / "out"
    export_project(bridge.org, bridge.state, out)
    evidence_dir = out / next(f.id for f in folders() if ExportSection.TOOL_RUNS in f.sections)
    record = json.loads((evidence_dir / "tool_runs" / run.id / "run.json").read_text(encoding="utf-8"))
    assert record["references"]
    assert all(r["copied_as"] is None and "not a readable file" in r["note"] for r in record["references"])


def test_the_export_names_no_folder_and_no_organization_vocabulary(nirmaan_org):
    """The layout lives in the table: no string constant in the export code names a folder."""
    import ast

    import nirmaan.export

    org = nirmaan_org
    forbidden = ({f.id for f in folders()} | set(org.units) | set(org.skills) | set(org.capabilities)
                 | set(org.roles)) - {"note"}
    tree = ast.parse(Path(nirmaan.export.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in forbidden, f"export.py hard-codes {node.value!r}"
            assert not any(f"{f}/" in node.value for f in (x.id for x in folders())), node.value


# --- Crown jewel -----------------------------------------------------------------------------


@needs(*GATE_TOOLS)  # M46: the fixture drives gated RTL work, so real lint runs
def test_a_new_folder_or_a_remap_needs_zero_core_changes(midway, tmp_path):
    """Software gets its own folder and lint moves under verification: two table edits, no code."""
    docs = next(f for f in folders() if "driver" in f.artifact_kinds)
    lint_home = next(f for f in folders() if "lint_report" in f.artifact_kinds)
    verification = next(f for f in folders() if "verification_plan" in f.artifact_kinds)
    register_folder(DeliverableFolder(id="11_software", title="Software", artifact_kinds=("driver", "firmware")))
    register_folder(docs.model_copy(update={"artifact_kinds": tuple(k for k in docs.artifact_kinds if k != "driver")}))
    register_folder(lint_home.model_copy(update={"artifact_kinds": ()}))
    register_folder(verification.model_copy(update={"artifact_kinds": (*verification.artifact_kinds, "lint_report")}))
    try:
        out = tmp_path / "out"
        report = export_project(midway.org, midway.state, out)
        assert (out / "11_software" / "README.md").is_file()
        lint = next(a for a in midway.state.artifacts.values() if a.kind == "lint_report")
        assert _sidecars(out)[lint.id]["_path"].startswith(verification.id + "/")
        assert not list((out / lint_home.id).glob("*.provenance.json"))
        driver = tid(midway, "driver")
        assert any(m.task == driver and m.folder == "11_software" for m in report.missing)
    finally:
        for folder_id in ("11_software", docs.id, lint_home.id, verification.id):
            unregister_folder(folder_id)
    assert folders() == sorted(DELIVERABLE_FOLDERS, key=lambda f: f.id)

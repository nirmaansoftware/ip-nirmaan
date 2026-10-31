"""The ablation switch (M67): ``nirmaan eval run --without-knowledge``.

The seat's packet keeps its skills, cards and everything else and carries no
knowledge document; the run record says ``knowledge: off`` in its name, its
manifest and every trial, and M42 learning does not read such trials. The
levels side (they never count) is in ``tests/test_capability_levels.py``. No
test calls a model: the seat is ``ReplayLLM`` or a runtime that declines.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from test_knowledge_packet import Spy, _org_citing, _write

from nirmaan.cli import app
from nirmaan.eval_proposals import load_results
from nirmaan.evals import evaluate, load_cases, load_record, record_run, rejudge, replay_llm, skill_digest
from nirmaan.org import knowledge
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ModelRuntime, assemble, render_work_prompt, run_task

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
ARBITER = "rtl/rr-arbiter"
SPEC_CASE = "spec/axi4-lite-interface"
SPEC_SKILL = "interface_specification"
SPEC_REF = f"architecture/{SPEC_SKILL}"
MARKER = "M67 fixture: every interface names its reset value."


def _case(case_id: str):
    return next(c for c in load_cases(EVALS) if c.id == case_id)


class Declines(Spy):
    """Counts that it was asked, then declines, so nothing is worked."""

    def accepts(self, packet) -> bool:
        super().accepts(packet)
        self.packet = packet
        return False


def _without_documents(packet) -> dict:
    data = packet.model_dump(mode="json")
    data["domain"].pop("documents")
    return data


def test_without_knowledge_the_packet_drops_the_documents_and_nothing_else(nirmaan_org, fixed_clock):
    case = _case(ARBITER)
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(case.request)
    rtl = next(t for t in engine.state.tasks.values() if t.stage == case.seat)
    for seat in (rtl.owner, rtl.reviewer):
        with_docs = assemble(engine, rtl.id, role=seat)
        without = assemble(engine, rtl.id, role=seat, knowledge=False)
        assert [d.ref for d in with_docs.domain.documents] == ["design/arbitration"]
        assert without.domain.documents == () and without.domain.declines is None
        # The skills and their cards stay, including the card's pointer to its document.
        assert "arbitration" in [s.id for s in without.domain.skills]
        assert _without_documents(without) == _without_documents(with_docs)
        assert "Knowledge document design/arbitration" not in render_work_prompt(without).render()


def test_without_knowledge_a_document_never_makes_the_seat_decline(root, fixed_clock):
    # A cited document that is missing declines the seat (M61); with no documents carried, nothing is missing.
    engine = Orchestrator(_org_citing(SPEC_REF, SPEC_SKILL), clock=fixed_clock).plan(_case(SPEC_CASE).request)
    seat = next(t.id for t in engine.state.tasks.values() if t.stage == "interface-spec")
    assert "missing" in assemble(engine, seat).domain.declines
    assert assemble(engine, seat, knowledge=False).domain.declines is None
    spy = Declines()
    run_task(engine, seat, spy, knowledge=False)
    assert spy.asked == 1 and spy.packet.domain.documents == ()  # reached the runtime: no decline for a document


@pytest.fixture()
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "KNOWLEDGE_ROOT", tmp_path / "knowledge")
    return tmp_path / "knowledge"


def test_the_evaluated_seat_is_asked_without_the_documents(root, fixed_clock, tmp_path):
    _write(root, SPEC_REF, f"# Interface specification\n\n{MARKER}\n")
    org, case = _org_citing(SPEC_REF, SPEC_SKILL), _case(SPEC_CASE)
    prompts = {}
    for on in (True, False):
        llm = replay_llm(case, REPO)
        result, _ = evaluate(org, case, ModelRuntime(llm, runtime_id="replay"), replay=True, repo=REPO,
                             sandbox=tmp_path / f"sb-{on}", clock=fixed_clock, knowledge=on)
        assert result.passed, result.detail  # the reference answer still passes: only the packet changed
        prompts[on] = "".join(p.render() for p in llm.calls)
    assert MARKER in prompts[True] and MARKER not in prompts[False]


def test_a_run_without_knowledge_is_labelled_in_its_name_manifest_and_every_trial(nirmaan_org, fixed_clock,
                                                                                    tmp_path):
    case = _case(SPEC_CASE)
    path = record_run(nirmaan_org, [case], None, trials=2, repo=REPO, out=tmp_path, clock=fixed_clock,
                      knowledge=False)
    assert path.name.endswith("-replay-replay-without-knowledge")
    record = load_record(path)
    assert record.manifest.knowledge == "off" and len(record.trials) == 2
    card = skill_digest(nirmaan_org, SPEC_SKILL, REPO, knowledge=False)
    for trial in record.trials:
        assert trial.knowledge == "off" and trial.skills == {SPEC_SKILL: card}
        assert json.loads(Path(path, "spec_axi4-lite-interface", f"trial-{trial.trial:02d}.json")
                          .read_text())["knowledge"] == "off"
    # Re-judging replays the answers the way they were given: without the documents.
    outcomes = rejudge(nirmaan_org, record, {case.id: case}, repo=REPO, sandbox=tmp_path / "sb")
    assert all(o.same for o in outcomes), [o.differences for o in outcomes]
    # A run with knowledge, as before, says on.
    plain = load_record(record_run(nirmaan_org, [case], None, trials=1, repo=REPO, out=tmp_path, clock=fixed_clock))
    assert plain.manifest.knowledge == "on" and plain.trials[0].knowledge == "on"
    assert not plain.path.name.endswith("without-knowledge")


def test_the_cli_switch_runs_without_knowledge_and_says_so(tmp_path):
    out = tmp_path / "results"
    ran = CliRunner().invoke(app, ["eval", "run", "--replay", "--without-knowledge", "--seats", "spec",
                                   "--cases", str(EVALS), "--repo", str(REPO), "--out", str(out)])
    assert ran.exit_code == 0, ran.output
    assert "without knowledge documents" in ran.output and "never counts toward an" in ran.output
    [path] = list(out.iterdir())
    record = load_record(path)
    assert record.manifest.knowledge == "off" and all(t.knowledge == "off" for t in record.trials)
    history = CliRunner().invoke(app, ["eval", "history", "--results", str(out)])
    assert history.exit_code == 0 and "without knowledge" in history.output


def test_learning_does_not_read_trials_run_without_knowledge(nirmaan_org, fixed_clock, tmp_path):
    case = _case(SPEC_CASE)
    record_run(nirmaan_org, [case], None, trials=2, repo=REPO, out=tmp_path, clock=fixed_clock, knowledge=False)
    record_run(nirmaan_org, [case], None, trials=1, repo=REPO, out=tmp_path, clock=fixed_clock)
    runs = load_results(tmp_path)
    assert len(runs) == 1 and "without-knowledge" not in runs[0].source
    # The manifest's label is enough: a trial file edited back to on is still not read.
    edited = list(tmp_path.glob("*-without-knowledge/*/trial-*.json"))
    for trial in edited:
        text = trial.read_text()
        assert '"knowledge": "off"' in text
        trial.write_text(text.replace('"knowledge": "off"', '"knowledge": "on"'))
    assert len(edited) == 2
    assert len(load_results(tmp_path)) == 1

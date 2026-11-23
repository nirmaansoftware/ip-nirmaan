"""What a later whole-flow stage is sent of the pass-through (G3, council record 2026-11-17, sixth addendum, gate WF31).

A replay of each whole-flow case's reference answer, with no model, in both arms (documents and controls). For every
stage after the first, the prompt it is sent holds, for each stage it builds on, one evidence line with
"review_record, substantiated: Independent review by", that stage's reviewer role and that stage's whole note. Every
stage's recorded note is one of the two texts of decision P2, item 3, and the words "reviewed in the repository"
appear in no prompt, note or evidence record.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from laws import needs
from nirmaan.evals import load_cases
from nirmaan.evals.flow import NOTE_CHECKED, NOTE_UNCHECKED, PASSTHROUGH, FlowReplayLLM, run_flow
from nirmaan.runtime import ModelRuntime

ROOT = Path(__file__).resolve().parents[1]
TOOLS = needs("verilator", "iverilog", "vvp", "yosys", "cc", "make")
NOT_JUDGED = ("No reviewer judged this stage: the evaluation harness recorded this review and approval itself, by "
              "the evaluation's rule, so that later stages receive it as input; 'approved' here records that rule, "
              "not a judgement.")


def test_both_notes_say_who_made_the_record_and_by_what_rule():
    """Decision P2, item 3: each note keeps its first and last sentence and gains the one sentence between them."""
    assert NOTE_CHECKED == f"Whole-flow evaluation: not reviewed. {NOT_JUDGED} Before-review checks passed: {{runs}}."
    assert NOTE_UNCHECKED == (f"Whole-flow evaluation: not reviewed. {NOT_JUDGED} This stage has no before-review "
                              "check: submitted, not checked.")


@TOOLS
@pytest.mark.parametrize("knowledge", [True, False], ids=["documents", "controls"])
@pytest.mark.parametrize("case_id", ["flow/axil-timer", "flow/axi4-lite-regs-driver"])
def test_every_later_stage_is_sent_each_upstream_review_record_with_its_whole_note(nirmaan_org, tmp_path, fixed_clock,
                                                                                  case_id, knowledge):
    [case] = [c for c in load_cases(ROOT / "evals", flow="whole") if c.id == case_id]
    llm = FlowReplayLLM(case, ROOT)
    run = run_flow(nirmaan_org, case, ModelRuntime(llm, runtime_id="replay"), replay=True, repo=ROOT,
                   sandbox=tmp_path / "flow", clock=fixed_clock, knowledge=knowledge)
    assert [s.stage for s in run.stages] == list(case.exercised)
    assert all(s.status != "not run" for s in run.stages)

    # Every stage's note is one of the two texts: the checked one names exactly the gate runs that passed.
    for stage in run.stages:
        passed = [g.run for g in stage.gate_runs if g.succeeded]
        assert stage.note == (NOTE_CHECKED.format(runs=", ".join(passed)) if passed else NOTE_UNCHECKED), stage.stage
    stage_of = {s.task: s for s in run.stages}

    # Every stage after the first: one review-record line per stage it builds on, with that stage's whole note.
    # The replay answers each stage once, in stage order, so the n-th prompt is the n-th stage's.
    assert [s.attempts for s in run.stages] == [1] * len(run.stages) and len(llm.calls) == len(run.stages)
    later = list(zip(run.stages, llm.calls))[1:]
    assert later
    for stage, prompt in later:
        upstream = [stage_of[dep] for dep in run.engine.task(stage.task).depends_on]
        assert upstream, stage.stage
        records = [line for line in prompt.render().splitlines()
                   if "review_record, substantiated: Independent review by" in line]
        assert len(records) == len(upstream), (stage.stage, records)
        for up in upstream:
            reviewer = run.engine.task(up.task).reviewer
            assert up.reviewed_by == f"{reviewer} ({PASSTHROUGH})"
            tail = f" on {up.task}: review_record, substantiated: Independent review by {reviewer}: {up.note}"
            mine = [line for line in records if line.startswith("- Evidence ") and line.endswith(tail)]
            assert len(mine) == 1, (stage.stage, up.stage, records)

    # "reviewed in the repository" is never used: not in a prompt, a note or an evidence record.
    assert not any("reviewed in the repository" in p.render() for p in llm.calls)
    assert not any("reviewed in the repository" in s.note for s in run.stages)
    assert not any("reviewed in the repository" in e.description for e in run.engine.state.evidence.values())

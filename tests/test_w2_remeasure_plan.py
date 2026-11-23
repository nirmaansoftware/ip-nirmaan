"""The wave 2 re-measure plan's window (decision P1 of the addendum of 2026-11-23 to
council/records/2026-11-23-wave-2-close-meeting-1.md; gate W2C12).

At most `width` trials of the batch run at once, inside a window of `width` consecutive slots. The plan's order
must then keep any two arm E slots whose cases name a skill in common more than `width - 1` places apart, so that
one event can fail at most one arm E trial of any group. These tests read the width the plan states and its section
12, and fail if any window of that width holds two such slots.
"""

from __future__ import annotations

import re
from pathlib import Path

from nirmaan.evals import load_cases

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "evals" / "plans" / "2026-11-23-w2-remeasure.md"
WIDTH_ROW = re.compile(r"^\| Width: trials of the batch in flight at once \| `(\d+)` \|$", re.MULTILINE)
SLOT_ROW = re.compile(r"^\| (\d+) \| (\d+) \| ([EN]) \([^)]*\) \| ([\w/-]+) \|$", re.MULTILINE)


def _sections(text: str) -> dict[str, str]:
    parts = re.split(r"^## (\d+)\. [^\n]*$", text, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


def _slots(text: str) -> list[tuple[int, str, str]]:
    return [(int(n), arm, case) for n, _, arm, case in SLOT_ROW.findall(_sections(text)["12"])]


def _skills(text: str) -> dict[str, list[str]]:
    """Section 2's table: each case and the skills it names."""
    out = {}
    for line in _sections(text)["2"].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 7 and "/" in cells[0] and cells[5].isdigit():
            out[cells[0]] = [s.strip() for s in cells[2].split(",")]
    return out


def _width(text: str) -> int:
    found = WIDTH_ROW.findall(text)
    assert len(found) == 1, found  # stated once
    assert WIDTH_ROW.search(_sections(text)["3"]), "the width is stated in section 3"
    return int(found[0])


def _crowded(slots: list[tuple[int, str, str]], skills: dict[str, list[str]], width: int) -> list[tuple[int, int]]:
    """Every pair of arm E slots fewer than `width` places apart whose cases name a skill in common."""
    arm_e = [(n, case) for n, arm, case in slots if arm == "E"]
    return [(a, b) for i, (a, ca) in enumerate(arm_e) for b, cb in arm_e[i + 1:]
            if b - a < width and set(skills[ca]) & set(skills[cb])]


def test_section_12_lists_the_117_slots_in_order():
    slots = _slots(PLAN.read_text(encoding="utf-8"))
    assert [n for n, _, _ in slots] == list(range(1, 118))
    cases = {case for _, _, case in slots}
    assert len(cases) == 13
    for case in cases:
        assert sum(1 for _, arm, c in slots if c == case and arm == "E") == 8, case
        assert sum(1 for _, arm, c in slots if c == case and arm == "N") == 1, case


def test_the_skills_section_2_names_are_the_case_files():
    text = PLAN.read_text(encoding="utf-8")
    skills = _skills(text)
    assert set(skills) == {case for _, _, case in _slots(text)}
    cases = {c.id: c for c in load_cases(REPO / "evals", flow=None)}
    for case, names in skills.items():
        assert list(cases[case].skills) == names, case


def test_the_width_is_three():
    assert _width(PLAN.read_text(encoding="utf-8")) == 3


def test_no_window_of_the_width_holds_two_arm_e_slots_whose_cases_share_a_skill():
    text = PLAN.read_text(encoding="utf-8")
    assert _crowded(_slots(text), _skills(text), _width(text)) == []


def test_the_check_sees_a_crowded_window():
    """The check has teeth: fact PF6 of the addendum says five consecutive slots can hold two arm E trials of one
    group (slots 12 and 16), and an order with two such slots side by side fails at any width above one."""
    text = PLAN.read_text(encoding="utf-8")
    slots, skills = _slots(text), _skills(text)
    assert (12, 16) in _crowded(slots, skills, 5)
    assert _crowded(slots, skills, 4) == []
    swapped = list(slots)
    swapped[1], swapped[7] = (2, *slots[7][1:]), (8, *slots[1][1:])  # dv/equiv-updown beside dv/equiv-gray
    assert (1, 2) in _crowded(swapped, skills, 2)


def test_the_amendment_states_the_moved_workflow_digest_with_its_commit():
    text = PLAN.read_text(encoding="utf-8")
    row = re.search(r"^\| Workflow, tool set and CLI pin \|.*\| `(sha256:[0-9a-f]{64})` \|$", text, re.MULTILINE)
    assert row, "the workflow group's row"
    moved = text.split("**The moved workflow digest**", 1)[1].split("\n\n", 1)[0]
    assert "`sha256:09083077" in moved and "ip#464" in moved and "ip#470" in moved
    assert re.search(r"computed on `main` at `[0-9a-f]{40}`", moved), "the commit the moved digest was computed on"
    assert row.group(1) != "sha256:09083077e0237a7e2b1ed89152d3d5b8f31836a03c8b78500b471d802f8e64d7"


def test_one_at_a_time_is_said_of_this_batch_only_after_a_limit():
    """Decision P7: after the amendment no text says "one at a time" of this batch, except of the width after a
    limit. (A check made "one check at a time" is not a trial run one at a time.)"""
    text = PLAN.read_text(encoding="utf-8")
    for paragraph in re.split(r"\n\s*\n|\n- ", text):
        if re.search(r"\bone (slot |trial |dispatch |run )?at a time\b", paragraph):
            assert "limit" in paragraph or "W2-L1 ran" in paragraph, paragraph

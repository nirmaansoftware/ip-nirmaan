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


GROUP_ROW = re.compile(r"^\| ([^|]+?) \| [^|]+ \| \d+ \| `(sha256:[0-9a-f]{64})` \|$", re.MULTILINE)


def _groups(text: str) -> dict[str, str]:
    return dict(GROUP_ROW.findall(_sections(text)["6"]))


def test_the_amendment_states_each_moved_group_digest_with_the_pull_requests_that_moved_it():
    """Decision P7, item 3, and gate W2C2 (ET7 shown): every group digest that moved after the plan was committed is
    in section 6's table at its last value, and the amendment names each value it passed through, with the pull
    request and merge that set it."""
    text = PLAN.read_text(encoding="utf-8")
    groups = _groups(text)
    assert groups["Workflow, tool set and CLI pin"] == (
        "sha256:82e264d9903a5c5d9f580f8ad8219b46f00db8c0aba367097df6d8d951ec3595")
    assert groups["Seat account"] == "sha256:6530c15123fabd55cdaf7142af49ee7306eea1ef09d7675338c561e42099c93b"
    other = " ".join(text.split("**The other moved digests.**", 1)[1].split("**Gate ET7, shown**", 1)[0].split())
    seat = other.split('- "Seat account"', 1)[1].split('- "Gate backends"', 1)[0]
    for value, pr in (("4abec1ad", None), ("1b7309f1", "ip#471 (merge `a15b8c1d`"), ("6530c151", "ip#475 (merge `f8dcc97e`")):
        assert f"`sha256:{value}" in seat, value
        assert pr is None or pr in seat, pr
    backends = other.split('- "Gate backends"', 1)[1]
    assert "`sha256:eac184ec" in backends and f"`{groups['Gate backends']}`" in backends and "ip#475" in backends
    shown = text.split("**Gate ET7, shown**", 1)[1].split("\n\n**", 1)[0]
    for pr in ("ip#464 (`c0ba283c`)", "ip#471 (`a15b8c1d`)", "ip#475 (`f8dcc97e`)", "ip#470 (`97324c78`)"):
        assert f"| {pr} |" in shown, pr


def test_the_concurrency_block_is_the_workflows_word_for_word():
    """Decision P7, item 2: the block as it is on `main` (with the seventh addendum's first clause), word for word."""
    text = PLAN.read_text(encoding="utf-8")
    workflow = (REPO / ".github" / "workflows" / "live-eval.yml").read_text(encoding="utf-8")
    block = re.search(r"^concurrency:\n  group: .*\n  cancel-in-progress: false$", workflow, re.MULTILINE)
    assert block and f"```\n{block.group(0)}\n```" in _sections(text)["3"]


def test_each_case_of_the_batch_runs_in_a_group_of_its_own_with_the_input():
    """The seventh addendum's decision T3 left the group per run for single-seat cases: with `parallel` true, a case
    that is neither `flow/` nor `firmware/` gets `live-eval-run-<run id>`, and both guards let each of the 13 IDs
    through (no `flow/` or `firmware/` prefix; written in its exact form)."""
    workflow = (REPO / ".github" / "workflows" / "live-eval.yml").read_text(encoding="utf-8")
    assert ("inputs.parallel && !startsWith(inputs.case, 'flow/') && !startsWith(inputs.case, 'firmware/') && "
            "format('live-eval-run-{0}', github.run_id)") in workflow
    assert "form='^[a-z0-9][a-z0-9/_.-]*$'" in workflow
    cases = {case for _, _, case in _slots(PLAN.read_text(encoding="utf-8"))}
    assert len(cases) == 13
    for case in cases:
        assert not case.startswith(("flow/", "firmware/")), case
        assert re.fullmatch(r"[a-z0-9][a-z0-9/_.-]*", case) and ".." not in case, case


def test_no_placeholder_is_left_in_the_plan():
    """The amendment is drafted before gate ET20's pull request (ip#522) merges; its merge commit and the value
    recomputed on it are filled in before the amendment merges."""
    text = PLAN.read_text(encoding="utf-8")
    assert not re.findall(r"MERGE-COMMIT-OF-[A-Z0-9]+|GATE-BACKENDS-AFTER-[A-Z0-9]+", text)

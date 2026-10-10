"""M43: status documents that stop colliding and stop drifting.

* Milestone history lives in docs/history/, one file per entry, and no heading
  of the old context.md section 2 is lost.
* context.md holds current facts only, and stays short.
* The counts the roadmap states are generated from the code, and a drift fails.
* The landing page reads its numbers from site/stats.json (a release snapshot),
  so adding a workflow breaks no site check.
* A milestone number is reserved in the roadmap before a branch is cut.

See docs/STATUS_DOCS.md.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "docs" / "history"


def _load_status():
    spec = importlib.util.spec_from_file_location("nirmaan_status", ROOT / "scripts" / "status.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


status = _load_status()


def _history_files() -> list[Path]:
    return sorted(p for p in HISTORY.glob("*.md") if p.name != "README.md")


# --- History ----------------------------------------------------------------------


def test_every_old_heading_is_in_exactly_one_history_file() -> None:
    headings = (ROOT / "tests" / "fixtures" / "history_headings.txt").read_text(
        encoding="utf-8").splitlines()
    assert len(headings) == 67
    titles = {p.name: p.read_text(encoding="utf-8").splitlines()[0] for p in _history_files()}
    for heading in headings:
        owners = [name for name, title in titles.items() if title == f"# {heading}"]
        assert len(owners) == 1, (heading, owners)


def test_history_files_sort_by_milestone() -> None:
    for path in _history_files():
        assert re.fullmatch(r"(M\d\d(-[a-z0-9.-]+)|release-v\d+\.\d+\.\d+|context-before-M43)\.md",
                            path.name), path.name


def test_the_index_links_every_history_file_once() -> None:
    index = (HISTORY / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)]+\.md)\)", index)
    assert sorted(links) == sorted(p.name for p in _history_files())


def test_this_milestone_has_its_own_history_file() -> None:
    assert (HISTORY / "M43-status-docs.md").is_file()


# --- context.md ---------------------------------------------------------------------


def test_context_md_holds_current_facts_only() -> None:
    text = (ROOT / "context.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 400
    assert not re.search(r"^#{2,3} Milestone", text, re.M)
    assert "docs/history/" in text


def test_claude_md_states_the_new_convention() -> None:
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "docs/history/MNN-" in text
    assert "does not append to `context.md`" in text


# --- Counts -------------------------------------------------------------------------


def test_the_roadmap_counts_match_the_code() -> None:
    assert status.check_roadmap() == []


def test_the_counts_are_the_ones_the_code_reports() -> None:
    from nirmaan.company import build_organization
    from nirmaan.models.org import ToolStatus

    org = build_organization()
    counts = status.structural_counts()
    assert counts["workflows"] == len(org.workflows)
    assert counts["units"] == org.stats()["units"]
    assert counts["tools_available"] + counts["tools_contract_only"] == len(org.tools)
    assert counts["tools_contract_only"] == sum(
        t.status is ToolStatus.CONTRACT_ONLY for t in org.tools.values())


def test_a_drifted_roadmap_number_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    real = status.structural_counts()
    monkeypatch.setattr(status, "structural_counts", lambda: {**real, "tools_available": 999})
    problems = status.check_roadmap()
    assert problems and "tools_available" in problems[0]


def test_stats_json_is_a_complete_release_snapshot() -> None:
    stats = json.loads((ROOT / "site" / "stats.json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d+\.\d+\.\d+", stats["version"])
    for key in (*status.STRUCTURAL, "tests"):
        assert isinstance(stats[key], int) and stats[key] > 0, key


# --- The landing page ---------------------------------------------------------------


def test_the_site_shows_what_stats_json_says() -> None:
    assert status.check_site() == []


def test_adding_a_workflow_breaks_no_site_check(monkeypatch: pytest.MonkeyPatch) -> None:
    real = status.structural_counts()
    monkeypatch.setattr(status, "structural_counts", lambda: {**real, "workflows": real["workflows"] + 1})
    assert status.check_site() == []
    assert status.check_roadmap() != []


def test_site_tests_do_not_read_the_organization() -> None:
    source = (ROOT / "tests" / "test_landing_site.py").read_text(encoding="utf-8")
    assert "build_organization" not in source
    assert "available_packs" not in source


# --- Numbering and dashes -----------------------------------------------------------


def test_the_roadmap_reserves_milestone_numbers() -> None:
    roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    assert "reserve the number here before cutting a branch" in roadmap.lower()
    for number in range(43, 50):
        assert re.search(rf"^\| M{number} \|", roadmap, re.M), number


NEW_FILES = ["context.md", "CLAUDE.md", "docs/ROADMAP.md", "docs/STATUS_DOCS.md",
             "scripts/status.py", "site/stats.json"]


DASHES = {chr(0x2014), chr(0x2013)}  # em dash, en dash


def test_no_dashes_in_status_documents() -> None:
    paths = [ROOT / p for p in NEW_FILES] + sorted(HISTORY.glob("*.md"))
    dashed = [str(p.relative_to(ROOT)) for p in paths if DASHES & set(p.read_text(encoding="utf-8"))]
    assert dashed == []

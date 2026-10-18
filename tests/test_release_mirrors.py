"""M59: the release checks the landing page's two hand-written org mirrors.

* The org figure's division names are compared with the divisions the code
  builds (active, outside the business function).
* Every role title in the hero's plan excerpt must be printed by a real
  `nirmaan plan` of the excerpt's own request.
* A mismatch stops `scripts/status.py --release` before anything is written.
  The per-PR checks (`--check` and the test suite's site and roadmap checks)
  never run it, so the page catches up at a release, as the tiles do.

The checks compare against whatever the code builds, so these tests never pin
today's division names or role titles. See docs/STATUS_DOCS.md, section 9.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RENAMED = ROOT / "tests" / "fixtures" / "site" / "hero-renamed-role.html"


def _load_status():
    spec = importlib.util.spec_from_file_location("nirmaan_status_m59", ROOT / "scripts" / "status.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


status = _load_status()


def _figure(names: list[str]) -> str:
    items = "".join(f'<li style="--k:{i}">{name}</li>' for i, name in enumerate(names))
    return f'<figure class="org"><ul class="org__divs" role="list">{items}</ul></figure>'


@pytest.fixture
def release_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the release at copies, so a test can watch what it writes."""
    for name, source in (("STATS", ROOT / "site" / "stats.json"), ("ROADMAP", ROOT / "docs" / "ROADMAP.md")):
        copy = tmp_path / source.name
        shutil.copyfile(source, copy)
        monkeypatch.setattr(status, name, copy)
    monkeypatch.setattr(status, "SITE", tmp_path / "index.html")
    return tmp_path


# --- The crown-jewel case: a renamed hero role fails the release, not a PR ------------


def test_a_renamed_hero_role_fails_release(release_files: Path, monkeypatch: pytest.MonkeyPatch,
                                           capsys: pytest.CaptureFixture[str]) -> None:
    hero = RENAMED.read_text(encoding="utf-8")
    page = hero + _figure(status.code_divisions())  # the figure matches, so only the hero is wrong
    (release_files / "index.html").write_text(page, encoding="utf-8")
    stats_before = (release_files / "stats.json").read_text(encoding="utf-8")

    def no_tests() -> int:
        raise AssertionError("a stopped release must not collect tests")

    monkeypatch.setattr(status, "collect_test_count", no_tests)
    assert status.main(["--release"]) == 1
    err = capsys.readouterr().err
    assert "'Senior AXI Interface Wrangler'" in err
    assert "release stopped, nothing written" in err
    assert (release_files / "stats.json").read_text(encoding="utf-8") == stats_before
    assert (release_files / "index.html").read_text(encoding="utf-8") == page


def test_the_per_pr_checks_never_run_the_mirror_check(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(page: str) -> list[str]:
        raise AssertionError("the mirror check runs at a release only")

    monkeypatch.setattr(status, "check_mirrors", refuse)
    assert status.main(["--check"]) == 0
    assert status.check_site() == []
    assert status.check_roadmap() == []


# --- The two comparisons ---------------------------------------------------------------


def test_a_matching_page_passes_and_the_release_goes_on(release_files: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    hero = RENAMED.read_text(encoding="utf-8")
    request, titles = status.hero_excerpt(hero)
    monkeypatch.setattr(status, "plan_titles", lambda req: set(titles) if req == request else set())
    monkeypatch.setattr(status, "code_divisions", lambda: ["Architecture", "Verification"])
    (release_files / "index.html").write_text(hero + _figure(["Architecture", "Verification"]), encoding="utf-8")
    monkeypatch.setattr(status, "collect_test_count", lambda: 1)
    assert status.check_mirrors((release_files / "index.html").read_text(encoding="utf-8")) == []
    assert status.release()["tests"] == 1
    assert '"tests": 1' in (release_files / "stats.json").read_text(encoding="utf-8")


def test_the_figure_is_compared_with_the_built_divisions(monkeypatch: pytest.MonkeyPatch) -> None:
    hero = RENAMED.read_text(encoding="utf-8")
    monkeypatch.setattr(status, "plan_titles", lambda req: set(status.hero_excerpt(hero)[1]))
    monkeypatch.setattr(status, "code_divisions", lambda: ["Architecture", "Quality and Process"])
    problems = status.check_mirrors(hero + _figure(["Architecture", "Documentation"]))
    assert problems == [
        "org figure shows division 'Documentation', which the organization does not build",
        "org figure is missing division 'Quality and Process', which the organization builds",
    ]


def test_hero_titles_are_checked_against_the_real_plan() -> None:
    request, titles = status.hero_excerpt(RENAMED.read_text(encoding="utf-8"))
    assert request == "Create a 4-port AXI-to-NoC bridge."
    real = status.plan_titles(request)
    assert "Senior AXI Interface Wrangler" in titles
    assert "Senior AXI Interface Wrangler" not in real
    assert real  # the plan printed owners and leads, and the pattern read them


def test_a_page_without_mirrors_fails_the_release_check() -> None:
    problems = status.check_mirrors("<html></html>")
    assert any("no org figure" in p for p in problems)
    assert any("no hero plan excerpt" in p for p in problems)


# --- The parsers read today's page ------------------------------------------------------


def test_the_parsers_read_the_real_page() -> None:
    page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    request, titles = status.hero_excerpt(page)
    assert request == "Create a 4-port AXI-to-NoC bridge."
    assert "VP, Verification" in titles and "Director, RTL Engineering" in titles
    assert "Architecture" in status.figure_divisions(page)


def test_the_figure_stands_for_active_non_business_divisions() -> None:
    from nirmaan.company import build_organization
    from nirmaan.models.org import Function, UnitKind

    org = build_organization()
    built = status.code_divisions()
    assert built
    for unit in org.units.values():
        if unit.kind is UnitKind.DIVISION and unit.function is Function.BUSINESS:
            assert unit.name not in built

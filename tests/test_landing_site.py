"""The landing page (site/) may not claim more than the code can back.

* Every stat tile shows what site/stats.json says. That file is the release
  snapshot scripts/status.py generates from the code (M43), so adding a
  workflow or a skill breaks no test here; the page catches up at release.
* The constitution cards are the constitution: same IDs, same order.
* The copy follows the brief's rules: no dashes, no hype words, no claims the
  project cannot substantiate.
* Motion is opt-in and switched off under prefers-reduced-motion.
* The launch list (Nirmaan's docs/engineering/list.md) is met: 404 page,
  robots and sitemap, social preview image, icons, and legal links.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from nirmaan.company import CONSTITUTION

SITE = Path(__file__).resolve().parent.parent / "site"
HTML = (SITE / "index.html").read_text(encoding="utf-8")


def test_stat_tiles_match_stats_json() -> None:
    stats = json.loads((SITE / "stats.json").read_text(encoding="utf-8"))
    tiles = re.findall(r'data-stat="(\w+)" data-count="(\d+)">(\d+)<', HTML)
    assert [key for key, _, _ in tiles] == [
        "units", "roles", "skills", "workflows", "principles", "knowledge_packs", "tests"]
    for key, count, shown in tiles:
        assert int(count) == int(shown) == stats[key], key


def test_stat_tiles_show_their_final_value_without_javascript() -> None:
    for count, shown in re.findall(r'data-count="(\d+)">(\d+)<', HTML):
        assert count == shown


def test_constitution_cards_are_the_constitution() -> None:
    assert re.findall(r'data-principle="(P\d+)"', HTML) == [p.id for p in CONSTITUTION]


TEXT_SUFFIXES = {".html", ".css", ".js", ".md", ".svg", ".txt", ".xml", ".json"}
# nirmaan.online's own files, copied unchanged so the two sites share every
# component; they follow that repository's conventions, not this one's.
VENDORED = {"nirmaan.css", "site.js", "hero.js"}


@pytest.mark.parametrize(
    "path",
    sorted(p.name for p in SITE.iterdir()
           if p.is_file() and p.suffix in TEXT_SUFFIXES and p.name not in VENDORED),
)
def test_no_dashes(path: str) -> None:
    text = (SITE / path).read_text(encoding="utf-8")
    assert "\u2014" not in text and "\u2013" not in text


@pytest.mark.parametrize(
    "phrase",
    ["revolutionary", "unleash", "supercharge", "10x", "production-ready",
     "AI employee", "verified RTL", "designs chips"],
)
def test_copy_avoids_hype_and_unbacked_claims(phrase: str) -> None:
    assert phrase.lower() not in HTML.lower()


def test_motion_is_opt_in_and_respects_reduced_motion() -> None:
    assert "prefers-reduced-motion: reduce" in HTML
    css = (SITE / "styles.css").read_text(encoding="utf-8")
    motion_layer = re.sub(r"/\*.*?\*/", "", css[css.index("@layer motion {"):], flags=re.S)
    # Every animated rule in the motion layer is scoped to html.motion, or to
    # the pinned scene (.build.is-pinned), which site.js sets only with motion.
    keyframe_step = re.compile(r"^(from|to|[\d%, ]+)$")
    for selector in re.findall(r"^\s*([^@\s{}][^{}]*)\{", motion_layer, re.M):
        selector = selector.strip()
        if not keyframe_step.match(selector):
            assert selector.startswith((".motion", ".build.is-pinned")), selector


def test_launch_list_items_are_present() -> None:
    for name in ("404.html", "robots.txt", "sitemap.xml", "favicon.svg", "apple-touch-icon.png"):
        assert (SITE / name).is_file(), name
    assert "Sitemap: https://ip.nirmaan.online/sitemap.xml" in (SITE / "robots.txt").read_text()
    assert 'name="robots" content="noindex"' in (SITE / "404.html").read_text()

    png = (SITE / "og-image.png").read_bytes()
    width, height = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
    assert (width, height) == (1200, 630)
    assert 'property="og:image" content="https://ip.nirmaan.online/og-image.png"' in HTML
    assert 'property="og:image:alt"' in HTML

    for link in ("https://www.nirmaan.online/privacy.html", "https://www.nirmaan.online/terms.html"):
        assert f'href="{link}"' in HTML


def test_the_scene_is_written_in_its_finished_state() -> None:
    # Motion only animates toward what the HTML says: each task's visible
    # state is the last one its timeline reaches, and gates end approved.
    import json

    rows = re.findall(
        r"data-states='([^']+)'>.*?<span class=\"order__state task__state\" data-state=\"([^\"]+)\">([^<]+)<",
        HTML, re.S,
    )
    assert len(rows) == 7
    for states, attr, text in rows:
        final = json.loads(states)[-1][1]
        assert attr == text == final
    assert HTML.count('data-state="approved">approved<') == 2


def test_pages_load_nothing_from_third_parties() -> None:
    # Fonts are self-hosted: a third-party stylesheet would block the first
    # paint. Links to other sites are fine; loaded resources are not.
    for name in ("index.html", "404.html"):
        text = (SITE / name).read_text(encoding="utf-8")
        assert not re.search(r'src="https?://', text), name
        assert not re.search(r'<link[^>]+href="https?://(?!ip\.nirmaan\.online)', text), name
    for name in ("styles.css", "nirmaan.css"):
        assert "url(http" not in (SITE / name).read_text(encoding="utf-8"), name
    for font in ("archivo", "hanken-grotesk", "jetbrains-mono"):
        assert (SITE / "assets" / "fonts" / f"{font}.woff2").is_file(), font


def test_shared_components_come_from_nirmaan_online() -> None:
    # Both pages load nirmaan.online's stylesheet first and this site's own
    # after it, so every shared component is nirmaan.online's, unchanged.
    for name in ("index.html", "404.html"):
        text = (SITE / name).read_text(encoding="utf-8")
        assert text.index('href="/nirmaan.css"') < text.index('href="/styles.css"'), name
        assert 'src="/site.js"' in text, name
    for name in VENDORED:
        assert (SITE / name).is_file(), name


def test_the_site_does_not_send_visitors_to_github() -> None:
    # Owner decision: the repository is the factory, not the storefront.
    for name in ("index.html", "404.html"):
        assert "github.com" not in (SITE / name).read_text(encoding="utf-8").lower(), name

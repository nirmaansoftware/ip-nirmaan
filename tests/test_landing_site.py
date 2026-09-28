"""The landing page (site/) may not claim more than the code can back.

* Every stat tile matches what the organization and the Knowledge Pack
  registry actually report.
* The constitution cards are the constitution: same IDs, same order.
* The copy follows the brief's rules: no dashes, no hype words, no claims the
  project cannot substantiate.
* Motion is opt-in and switched off under prefers-reduced-motion.
* The launch list (Nirmaan's docs/engineering/list.md) is met: 404 page,
  robots and sitemap, social preview image, icons, and legal links.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from nirmaan.company import CONSTITUTION, build_organization
from veritriage.knowledge.registry import available_packs

SITE = Path(__file__).resolve().parent.parent / "site"
HTML = (SITE / "index.html").read_text(encoding="utf-8")


def _stat(label: str) -> int:
    match = re.search(
        r'data-count="(\d+)">\d+</span><span class="stat__label">' + re.escape(label), HTML
    )
    assert match, f"no stat tile labelled {label!r}"
    return int(match.group(1))


def test_stat_tiles_match_the_organization() -> None:
    stats = build_organization().stats()
    assert _stat("organizational units") == stats["units"]
    assert _stat("roles, from intern to CEO") == stats["roles"]
    assert _stat("engineering skills") == stats["skills"]
    assert _stat("engineering workflows") == stats["workflows"]
    assert _stat("constitution principles") == stats["principles"]
    assert _stat("verification knowledge packs") == len(available_packs())


def test_stat_tiles_show_their_final_value_without_javascript() -> None:
    for count, shown in re.findall(r'data-count="(\d+)">(\d+)<', HTML):
        assert count == shown


def test_constitution_cards_are_the_constitution() -> None:
    assert re.findall(r'data-principle="(P\d+)"', HTML) == [p.id for p in CONSTITUTION]


TEXT_SUFFIXES = {".html", ".css", ".js", ".md", ".svg", ".txt", ".xml", ".json"}


@pytest.mark.parametrize(
    "path", sorted(p.name for p in SITE.iterdir() if p.is_file() and p.suffix in TEXT_SUFFIXES)
)
def test_no_dashes(path: str) -> None:
    text = (SITE / path).read_text(encoding="utf-8")
    assert "—" not in text and "–" not in text


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
    # Every animated rule in the motion layer is scoped to html.motion.
    keyframe_step = re.compile(r"^(from|to|[\d%, ]+)$")
    for selector in re.findall(r"^\s*([^@\s{}][^{}]*)\{", motion_layer, re.M):
        selector = selector.strip()
        if not keyframe_step.match(selector):
            assert selector.startswith(".motion"), selector


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


def test_the_site_does_not_send_visitors_to_github() -> None:
    # Owner decision: the repository is the factory, not the storefront.
    for name in ("index.html", "404.html"):
        assert "github.com" not in (SITE / name).read_text(encoding="utf-8").lower(), name

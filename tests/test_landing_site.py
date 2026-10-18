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
* The Content-Security-Policy in site/vercel.json allows inline scripts by
  hash only, and has the hash of every inline script on every page.
"""

from __future__ import annotations

import base64
import hashlib
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


# The vendored files are byte for byte the files of one named Nirmaan commit
# (nirmaansoftware/Nirmaan, website/src/static/: styles.css as nirmaan.css,
# site.js, hero.js). site/README.md records the same commit. To update them,
# change Nirmaan first, copy the three files from the new commit, and change
# this commit and these hashes together.
VENDORED_SOURCE_COMMIT = "6655f013517b766ecd979f618c75201c0428f93c"
VENDORED_SHA256 = {
    "nirmaan.css": "0b2654089eabd45809cb37a91fda2098c3beb24b7db84140064c6e0967b2d72d",
    "site.js": "000caeb5771cd62ef84f7377542b52119693d8b293cdf38876a43fd3a9e3134a",
    "hero.js": "2d37c298d19a488e2a7d86b123f94da86929726915f72e6846d703bd479984e0",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("name", sorted(VENDORED))
def test_vendored_file_is_the_pinned_nirmaan_commit(name: str) -> None:
    assert set(VENDORED_SHA256) == VENDORED
    actual = _sha256((SITE / name).read_bytes())
    assert actual == VENDORED_SHA256[name], (
        f"site/{name} is not Nirmaan {VENDORED_SOURCE_COMMIT}'s copy; "
        "change Nirmaan first, then copy the file unchanged and update the pin"
    )


def test_vendored_commit_is_recorded_in_the_readme() -> None:
    readme = (SITE / "README.md").read_text(encoding="utf-8")
    assert VENDORED_SOURCE_COMMIT in readme


@pytest.mark.parametrize("name", sorted(VENDORED))
def test_vendored_pin_catches_a_one_byte_change(name: str) -> None:
    data = bytearray((SITE / name).read_bytes())
    for index in (0, len(data) // 2, len(data) - 1):
        changed = bytearray(data)
        changed[index] ^= 0x01
        assert _sha256(bytes(changed)) != VENDORED_SHA256[name], index


def test_github_is_one_quiet_footer_link() -> None:
    # Founder decision 2026-10-16 (council record of that date): the source is
    # linked once, in the footer, never from the hero, the navigation or a
    # call to action.
    for name in ("index.html", "404.html"):
        page = (SITE / name).read_text(encoding="utf-8")
        assert page.lower().count("github.com") == 1, name
        footer = page.split('class="footer__base', 1)[1]
        assert "github.com/nirmaansoftware/ip-nirmaan" in footer, name


def test_partner_offer_stays_early_and_unpriced() -> None:
    # Council record 2026-10-16: the design-partner offer shows no price and
    # claims no partner until one has signed.
    section = HTML.split('id="partners"', 1)[1].split('class="cta-band"', 1)[0]
    assert "early" in section.lower()
    for mark in ("\u20b9", "$", "usd", "lakh"):
        assert mark not in section.lower(), mark
    assert "We have no design partners yet." in HTML


# Content-Security-Policy (council item I4, the ip copy of Nirmaan's N14). It
# ships as Report-Only; enforcing it is a later change after a preview check.
CSP_KEYS = ("content-security-policy", "content-security-policy-report-only")
RUNNABLE_TYPES = {"", "text/javascript", "application/javascript", "module", "speculationrules"}


def _csp() -> dict[str, list[str]]:
    # The one CSP header on /(.*). Enforcing it renames the Report-Only header;
    # two at once would let one go unchecked, so that fails here.
    config = json.loads((SITE / "vercel.json").read_text(encoding="utf-8"))
    values = [header["value"]
              for rule in config["headers"] if rule["source"] == "/(.*)"
              for header in rule["headers"] if header["key"].lower() in CSP_KEYS]
    assert len(values) == 1, "site/vercel.json needs exactly one CSP header on /(.*)"
    directives = (d.split() for d in values[0].split(";") if d.strip())
    return {name: sources for name, *sources in directives}


def _inline_script_hashes(page: str) -> set[str]:
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    hashes = set()
    for attrs, body in re.findall(r"<script(\s[^>]*)?>(.*?)</script\s*>", page, re.S | re.I):
        if re.search(r"\ssrc\s*=", attrs, re.I):
            continue
        kind = re.search(r'\stype\s*=\s*"([^"]*)"', attrs, re.I)
        if (kind.group(1).strip().lower() if kind else "") not in RUNNABLE_TYPES:
            continue
        digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
        hashes.add(f"'sha256-{digest}'")
    return hashes


def test_csp_script_src_has_exactly_the_inline_script_hashes() -> None:
    # A changed inline script (the theme bootstrap) changes its hash: put the
    # new one in site/vercel.json and drop the old one.
    used = set()
    for path in sorted(SITE.glob("*.html")):
        used |= _inline_script_hashes(path.read_text(encoding="utf-8"))
    assert used, "expected the inline theme bootstrap"
    allowed = {s for s in _csp()["script-src"] if s.startswith("'sha256-")}
    assert allowed == used


def test_csp_hash_catches_a_one_byte_change() -> None:
    page = "<script>a</script>"
    assert _inline_script_hashes(page) != _inline_script_hashes(page.replace(">a<", ">b<"))
    assert _inline_script_hashes('<script src="/x.js"></script><script type="application/ld+json">{}</script>') == set()


def test_csp_is_strict_where_this_site_allows() -> None:
    csp = _csp()
    assert "'unsafe-inline'" not in csp["script-src"]
    assert "'unsafe-eval'" not in csp["script-src"]
    assert csp["default-src"] == ["'self'"]
    assert csp["frame-ancestors"] == ["'none'"]
    assert csp["object-src"] == ["'none'"]
    assert csp["base-uri"] == ["'self'"]
    # This site posts no form and calls no third party (no Web3Forms).
    assert csp["connect-src"] == ["'self'"]
    assert csp["form-action"] == ["'self'"]

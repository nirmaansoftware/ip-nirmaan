"""Milestone 19: reference resolution.

``Reference.uri`` shipped in M5 as a hook with nothing behind it. These tests
cover the seam that fills it, and the two properties that make it safe to run
inside a deterministic pipeline: resolution is pure, and a company adds its
own resolver without touching anything here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import veritriage.references as references_pkg
from veritriage.knowledge.model import Reference
from veritriage.pipeline import analyze
from veritriage.references import (
    CATALOGUE,
    ReferenceResolver,
    available_resolvers,
    default_resolvers,
    register_resolver,
    resolve_reference,
    resolve_references,
    unregister_resolver,
)

PKG = Path(references_pkg.__file__).parent


# --- The built-in catalogue -------------------------------------------------


def test_known_specifications_resolve():
    assert resolve_reference(
        Reference(source="AMBA AXI Protocol Specification (IHI 0022)")
    ) == "https://developer.arm.com/documentation/ihi0022/latest/"


def test_unknown_sources_resolve_to_nothing():
    assert resolve_reference(Reference(source="Acme Internal Bus Note v2")) is None


def test_the_longest_matching_fragment_wins():
    """'AMBA AXI-Stream' must not resolve through the shorter 'AMBA AXI'."""
    stream = resolve_reference(
        Reference(source="AMBA AXI-Stream Protocol Specification (IHI 0051)")
    )
    axi = resolve_reference(Reference(source="AMBA AXI Protocol Specification"))
    assert stream != axi
    assert "ihi0051" in stream


def test_matching_ignores_case_and_revision_suffixes():
    a = resolve_reference(Reference(source="amba apb protocol specification"))
    b = resolve_reference(Reference(source="AMBA APB Protocol Specification (IHI 0024C)"))
    assert a == b is not None


def test_every_catalogue_entry_is_an_https_url():
    for fragment, uri in CATALOGUE.items():
        assert uri.startswith("https://"), f"{fragment} -> {uri}"


# --- Purity -----------------------------------------------------------------


def test_the_references_package_performs_no_io():
    """A network call here would put I/O in the middle of a pure pipeline."""
    forbidden = {
        "urllib", "urllib.request", "requests", "httpx", "socket", "http",
        "http.client", "aiohttp", "subprocess",
    }
    for path in PKG.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {node.module or ""}
            else:
                continue
            assert not (names & forbidden), f"{path.name} imports {names & forbidden}"


def test_resolution_is_deterministic():
    ref = Reference(source="PCI Express Base Specification")
    assert len({resolve_reference(ref) for _ in range(10)}) == 1


def test_resolution_never_mutates_the_pack_reference():
    """Packs are process-wide constants; resolution must copy, never edit."""
    original = Reference(source="AMBA AHB Protocol Specification")
    out = resolve_references([original])
    assert original.uri is None
    assert out[0].uri is not None
    assert out[0] is not original


def test_an_existing_uri_is_never_overwritten():
    minted = Reference(
        source="AMBA AXI Protocol Specification", uri="https://wiki.acme.test/axi"
    )
    assert resolve_reference(minted) == "https://wiki.acme.test/axi"


# --- The seam ---------------------------------------------------------------


def test_new_resolver_needs_only_registration():
    """The crown jewel: a company spec database is one registered class."""

    @register_resolver
    class _AcmeWiki(ReferenceResolver):
        resolver_id = "acme-wiki"
        priority = 10  # above the public catalogue

        def resolve(self, reference: Reference) -> str | None:
            if "acme" in reference.source.lower():
                return "https://wiki.acme.test/specs"
            return None

    try:
        assert "acme-wiki" in available_resolvers()
        assert (
            resolve_reference(Reference(source="Acme Internal Bus Note v2"))
            == "https://wiki.acme.test/specs"
        )
        # It leaves everything it does not claim to the catalogue.
        assert "developer.arm.com" in resolve_reference(
            Reference(source="AMBA APB Protocol Specification")
        )
    finally:
        unregister_resolver("acme-wiki")
    assert "acme-wiki" not in available_resolvers()


def test_priority_decides_who_wins():
    @register_resolver
    class _Shadow(ReferenceResolver):
        resolver_id = "shadow-mirror"
        priority = 1

        def resolve(self, reference: Reference) -> str | None:
            if "amba" in reference.source.lower():
                return "https://mirror.acme.test/amba"
            return None

    try:
        assert (
            resolve_reference(Reference(source="AMBA AXI Protocol Specification"))
            == "https://mirror.acme.test/amba"
        ), "an internal mirror should shadow the public page"
    finally:
        unregister_resolver("shadow-mirror")


def test_duplicate_resolver_ids_are_refused():
    @register_resolver
    class _First(ReferenceResolver):
        resolver_id = "clashing"

        def resolve(self, reference: Reference) -> str | None:
            return None

    try:
        with pytest.raises(ValueError, match="already registered"):

            @register_resolver
            class _Second(ReferenceResolver):
                resolver_id = "clashing"

                def resolve(self, reference: Reference) -> str | None:
                    return None

    finally:
        unregister_resolver("clashing")


def test_resolvers_run_in_deterministic_order():
    ids = [r.resolver_id for r in default_resolvers()]
    assert ids == [
        c.resolver_id
        for c in sorted(
            available_resolvers().values(), key=lambda c: (c.priority, c.resolver_id)
        )
    ]


def test_a_resolver_returning_none_defers_to_the_next():
    @register_resolver
    class _Abstains(ReferenceResolver):
        resolver_id = "abstains"
        priority = 1

        def resolve(self, reference: Reference) -> str | None:
            return None

    try:
        assert "developer.arm.com" in resolve_reference(
            Reference(source="AMBA CHI Architecture Specification")
        )
    finally:
        unregister_resolver("abstains")


# --- Reaching the report ----------------------------------------------------


def test_report_citations_carry_resolved_links(fixture_log):
    outcome = analyze(fixture_log("axi_timeout.log"))
    assert outcome.report.knowledge is not None
    refs = [r for p in outcome.report.knowledge.patterns for r in p.references]
    assert refs, "the AXI timeout fixture should cite a specification"
    assert any(r.uri for r in refs), "at least one citation should have resolved"


def test_html_report_renders_a_citation_as_a_link(fixture_log, tmp_path):
    from veritriage.reports import HtmlReportGenerator

    outcome = analyze(fixture_log("axi_timeout.log"))
    html = HtmlReportGenerator().render(outcome.report, outcome.graph)
    assert 'href="https://developer.arm.com' in html
    assert 'rel="noreferrer noopener"' in html


def test_resolution_changes_no_conclusion(fixture_log):
    """Links are decoration; the deterministic result is unaffected."""

    @register_resolver
    class _EverythingResolver(ReferenceResolver):
        resolver_id = "everything"
        priority = 1

        def resolve(self, reference: Reference) -> str | None:
            return "https://example.test/spec"

    bare = analyze(fixture_log("axi_timeout.log"))
    try:
        lensed = analyze(fixture_log("axi_timeout.log"))
    finally:
        unregister_resolver("everything")

    assert bare.report.classification == lensed.report.classification
    assert [p.pattern_id for p in bare.report.knowledge.patterns] == [
        p.pattern_id for p in lensed.report.knowledge.patterns
    ]
    assert [s.name for s in bare.report.reasoning.signals] == [
        s.name for s in lensed.report.reasoning.signals
    ]

"""Milestone 10: Collaborative Investigation Platform.

Covers the milestone's guarantees: bundles are deterministic and
content-addressed, export/import is lossless, reviews and annotations layer on
top without ever mutating the session or affecting reasoning, validation is
reproducible and catches tampering and dangling references, comparison
explains what changed, the collaboration code cannot bypass Workspace
Services, the core is untouched, and a new annotation type requires only
registration (the crown-jewel architecture test at the bottom of this file).
"""

from __future__ import annotations

import ast
import gzip
from pathlib import Path

import pytest
import pydantic

from laws import imports

import veritriage.collab.model as model_module
from veritriage.collab import (
    BundleFormatError,
    add_annotation,
    add_review,
    available_targets,
    compare_bundles,
    export_bytes,
    import_bundle,
    import_bytes,
    make_bundle,
    register_annotation_target,
    unregister_annotation_target,
    validate_bundle,
)
from veritriage.reports import HtmlReportGenerator
from veritriage.workspace import WorkspaceServices

# .../src/veritriage/collab/model.py -> parents[2] is the src/ root.
SRC = Path(model_module.__file__).parents[2]


def _module_imports(path: Path) -> set[str]:
    """Only the file's top-level imports (a client may lazily import inside a
    handler; a module-level import is a hard dependency)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


@pytest.fixture()
def services(tmp_path):
    return WorkspaceServices(session_root=tmp_path / "sessions", db=tmp_path / "reg.db")


@pytest.fixture()
def session(services, fixture_log):
    return services.investigate(
        [
            fixture_log("uvm_assertion.log"),
            fixture_log("axi_handshake_stall.wave.json"),
            fixture_log("change_context.engctx.json"),
        ]
    )


@pytest.fixture()
def bundle(session):
    return make_bundle(session, exported_by="asha", title="AR stall")


# --- Bundle identity and determinism ----------------------------------------


def test_bundle_is_content_addressed_and_sealed(bundle, session):
    assert bundle.bundle_id.startswith("vtb-")
    assert bundle.metadata.fingerprint.startswith("sha256:")
    assert bundle.metadata.session_id == session.session_id


def test_bundles_are_deterministic(session):
    a = make_bundle(session, exported_by="asha", title="AR stall")
    b = make_bundle(session, exported_by="asha", title="AR stall", now=a.metadata.created_at)
    assert a.bundle_id == b.bundle_id
    assert export_bytes(a) == export_bytes(b)


def test_export_bytes_are_gzip_and_deterministic(bundle):
    first = export_bytes(bundle)
    second = export_bytes(bundle)
    assert first == second
    assert first[:2] == b"\x1f\x8b"  # gzip magic
    assert b"vtb-" in gzip.decompress(first)


# --- Round-trip -------------------------------------------------------------


def test_export_import_is_lossless(services, bundle, session, tmp_path):
    path = services.export_bundle(session, tmp_path / "inv.vtb", exported_by="asha", title="AR stall")
    recovered = import_bundle(path)
    # The bundle round-trips (created_at differs since services builds fresh);
    # the session inside is byte-for-byte identical.
    assert recovered.session == session
    assert recovered.bundle_id == bundle.bundle_id


def test_plain_and_compressed_round_trip(bundle):
    assert import_bytes(export_bytes(bundle, compress=True)) == bundle
    assert import_bytes(export_bytes(bundle, compress=False)) == bundle


def test_import_rejects_garbage(tmp_path):
    bad = tmp_path / "bad.vtb"
    bad.write_bytes(b"not a bundle")
    with pytest.raises(BundleFormatError):
        import_bundle(bad)


# --- Reviews and annotations (immutability) ---------------------------------


def test_reviews_layer_on_top_without_touching_the_session(bundle):
    reviewed = add_review(bundle, "incorrect_diagnosis", "diego", "looks like TB")
    assert len(reviewed.reviews) == 1
    assert reviewed.session == bundle.session  # unchanged
    assert reviewed.bundle_id != bundle.bundle_id  # new identity
    with pytest.raises(pydantic.ValidationError):
        reviewed.reviews[0].verdict = "approved"


def test_reviews_never_affect_reasoning(bundle):
    before = bundle.session.report.reasoning.model_dump_json()
    reviewed = bundle
    for verdict in ("approved", "false_positive", "needs_investigation"):
        reviewed = add_review(reviewed, verdict, "r", "c")
    assert reviewed.session.report.reasoning.model_dump_json() == before


def test_annotations_never_mutate_sessions(bundle):
    node_id = next(iter(bundle.session.graph.nodes))
    before = bundle.session.model_dump_json()
    annotated = add_annotation(bundle, "evidence", node_id, "diego", "inspect this")
    assert len(annotated.annotations) == 1
    assert annotated.session.model_dump_json() == before
    assert annotated.session == bundle.session


def test_unknown_verdict_and_dangling_annotation_rejected(bundle):
    with pytest.raises(ValueError):
        add_review(bundle, "looks-bad", "r", "c")
    with pytest.raises(ValueError):
        add_annotation(bundle, "evidence", "ev-nonexistent", "a", "t")
    with pytest.raises(ValueError):
        add_annotation(bundle, "no-such-kind", "x", "a", "t")


def test_all_builtin_annotation_targets_resolve(bundle):
    assert set(available_targets()) >= {
        "evidence",
        "knowledge-pattern",
        "waveform-observation",
        "engineering-commit",
        "recommendation",
        "execution-step",
    }
    report = bundle.session.report
    node_id = next(iter(bundle.session.graph.nodes))
    add_annotation(bundle, "evidence", node_id, "a", "t")
    add_annotation(bundle, "knowledge-pattern", report.knowledge.patterns[0].pattern_id, "a", "t")
    add_annotation(
        bundle, "waveform-observation", report.waveform.observations[0].observation_id, "a", "t"
    )
    add_annotation(bundle, "engineering-commit", report.engineering.commits[0].revision, "a", "t")
    add_annotation(bundle, "recommendation", "0", "a", "t")


# --- Validation -------------------------------------------------------------


def test_validation_passes_clean_and_is_reproducible(bundle):
    first = validate_bundle(bundle)
    second = validate_bundle(bundle)
    assert first.ok and not first.errors
    assert first.model_dump_json() == second.model_dump_json()


def test_validation_detects_tampering(bundle):
    tampered = bundle.model_copy(update={"reviews": ()})  # bytes changed, fingerprint stale... but
    # bundle had no reviews, so instead tamper the metadata classification.
    tampered = bundle.model_copy(
        update={"metadata": bundle.metadata.model_copy(update={"classification": "no_failure"})}
    )
    result = validate_bundle(tampered)
    assert not result.ok
    assert "fingerprint-mismatch" in {f.code for f in result.errors}


def test_validation_flags_dangling_annotation(bundle):
    from veritriage.collab.model import Annotation, seal_bundle
    from datetime import datetime, timezone

    forged = seal_bundle(
        bundle.model_copy(
            update={
                "annotations": (
                    Annotation(
                        id="ann-forged",
                        target_type="evidence",
                        target_id="ev-missing",
                        author="x",
                        text="t",
                        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    ),
                )
            }
        )
    )
    result = validate_bundle(forged)
    assert not result.ok
    assert "annotation-dangling" in {f.code for f in result.errors}


def test_unknown_extension_is_a_warning_not_an_error(bundle):
    extended = bundle.model_copy(update={"future_field": {"x": 1}})
    sealed = model_module.seal_bundle(extended)
    result = validate_bundle(sealed)
    assert result.ok  # forward-compatible
    assert "unknown-extension" in {f.code for f in result.warnings}


# --- Comparison -------------------------------------------------------------


def test_comparison_explains_what_changed(services, fixture_log, bundle):
    other = make_bundle(services.investigate([fixture_log("uvm_timeout.log")]))
    comparison = compare_bundles(bundle, other)
    assert "different investigations" in comparison.summary
    facets = {d.facet for d in comparison.deltas}
    assert "classification" in facets
    identical = compare_bundles(bundle, bundle)
    assert "identical" in identical.summary and not identical.deltas


# --- Report -----------------------------------------------------------------


def test_report_renders_collaboration_section(services, session, tmp_path):
    path = services.export_bundle(session, tmp_path / "inv.vtb")
    services.review_bundle(path, "approved", "asha", "ship it")
    view = services.collaboration_view(path)
    html = HtmlReportGenerator().render(session.report, graph=session.graph, collaboration=view)
    assert "Collaboration" in html
    assert "approved" in html
    # Escapes, not literals, so this source file itself stays dash-free.
    assert "\u2014" not in html and "\u2013" not in html
    # Without the side-channel the collaboration section is absent.
    assert "Collaboration" not in HtmlReportGenerator().render(session.report, graph=session.graph)


# --- Architecture guards ----------------------------------------------------


def test_collab_never_bypasses_services():
    allowed = ("veritriage.workspace", "veritriage.models", "veritriage.collab")
    for path in (SRC / "veritriage" / "collab").rglob("*.py"):
        for module in imports(path):
            if module.startswith("veritriage"):
                assert module.startswith(allowed), f"{path.name} imports {module}"
    # Clients reach bundles through services: no module-level collab import
    # (a lazy import inside a handler for the exception type is fine).
    assert "veritriage.collab" not in _module_imports(SRC / "veritriage" / "cli" / "main.py")
    for path in (SRC / "veritriage" / "mcp").rglob("*.py"):
        assert "veritriage.collab" not in _module_imports(path), path.name


def test_core_unchanged_by_collaboration():
    core = (
        "graph", "parsers", "rules", "reasoning", "knowledge", "waveform",
        "engineering", "history", "signatures", "similarity", "storage",
        "analytics", "feedback", "models", "reports", "dashboard", "orchestrator",
    )
    for package in core:
        for path in (SRC / "veritriage" / package).rglob("*.py"):
            assert "veritriage.collab" not in path.read_text(encoding="utf-8"), path
    pipeline = (SRC / "veritriage" / "pipeline.py").read_text(encoding="utf-8")
    assert "veritriage.collab" not in pipeline


def test_no_ai_in_collab():
    banned = ("anthropic", "reasoning.ai", "AIReasoner")
    for path in (SRC / "veritriage" / "collab").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in text, f"{path.name} references {term}"


def test_collaboration_over_mcp(services, session, tmp_path):
    from veritriage.mcp import call_tool

    services.save(session)
    path = str(tmp_path / "inv.vtb")
    exported = call_tool(
        services, "export_investigation", {"session_id": session.session_id, "path": path}
    )
    assert exported["bundle_path"] == path
    validation = call_tool(services, "validate_bundle", {"path": path})
    assert validation["ok"]
    metadata = call_tool(services, "get_bundle_metadata", {"path": path})
    assert metadata["review_status"] == "unreviewed"
    imported = call_tool(services, "import_investigation", {"path": path})
    assert imported["session_id"] == session.session_id


# --- The crown jewel: a new annotation type is one registration --------------


def test_new_annotation_target_needs_only_registration(bundle):
    # A throwaway annotation target kind defined entirely in this test: it
    # validates and round-trips through export/import with zero changes to the
    # bundle model, validation, exchange, or Workspace.
    def _resolve_classification(session, target_id: str) -> bool:
        return session.report.classification.category.value == target_id

    register_annotation_target("test-classification", _resolve_classification)
    try:
        classification = bundle.session.report.classification.category.value
        annotated = add_annotation(
            bundle, "test-classification", classification, "asha", "expected class"
        )
        assert annotated.annotations[0].target_type == "test-classification"
        # Validation accepts it, and it survives a full export/import round-trip.
        assert validate_bundle(annotated).ok
        assert import_bytes(export_bytes(annotated)) == annotated
        # A bad target for the same new kind is rejected.
        with pytest.raises(ValueError):
            add_annotation(bundle, "test-classification", "no_failure", "a", "t")
    finally:
        unregister_annotation_target("test-classification")

"""Architectural guards: the AI reasons over the Evidence Graph only.

These tests pin the boundary rather than the AI output (which needs a live
API): the AI stage must not touch the filesystem, its payload must contain
only normalized graph objects (never raw parser output), and its failure
mode without the optional dependency must be clean.
"""

from __future__ import annotations

import inspect
import json

import pytest

import veritriage.reasoning.ai as ai_module
from veritriage.reasoning import AIReasoner, AIReasoningError, build_ai_payload
from veritriage.pipeline import analyze


def test_reasoner_signature_takes_graph_objects_not_paths():
    params = inspect.signature(AIReasoner.review).parameters
    assert "graph" in params and "result" in params
    assert "path" not in params and "paths" not in params


def test_ai_module_source_never_reads_files():
    # The module's only inputs are the graph view and reasoning models.
    # A file read here would break the evidence-first architecture.
    source = inspect.getsource(ai_module)
    assert "read_text" not in source
    assert "open(" not in source
    assert "Path(" not in source


def test_ai_payload_contains_only_normalized_evidence(fixture_log):
    outcome = analyze(
        [
            fixture_log("uvm_scoreboard.log"),
            fixture_log("coverage.txt"),
            fixture_log("test_metadata.json"),
        ]
    )
    payload = build_ai_payload(outcome.graph, outcome.report.reasoning)

    # Raw artifact text must be structurally absent from the AI input.
    blob = json.dumps(payload)
    assert "raw_line" not in blob
    assert "UVM_ERROR /tb/scoreboard.sv" not in blob  # a verbatim log line

    # Selected evidence is exactly the working set: nothing outside it.
    working_ids = set(outcome.report.reasoning.working_set.node_ids)
    for node in payload["selected_evidence"]["nodes"]:
        assert node["id"] in working_ids

    # The payload carries the deterministic stages, so the AI refines rather
    # than re-derives.
    assert payload["signals"]
    assert payload["hypotheses"]
    assert payload["recommendations"]


def test_every_reported_hypothesis_references_graph_evidence(fixture_log):
    outcome = analyze([fixture_log("uvm_assertion.log")])
    for hypothesis in outcome.report.reasoning.hypotheses:
        assert hypothesis.evidence_ids
        assert all(i in outcome.graph.nodes for i in hypothesis.evidence_ids)


def test_missing_sdk_raises_clean_error(fixture_log):
    if AIReasoner.available():  # pragma: no cover - environment-dependent
        pytest.skip("anthropic installed; this test covers the missing-SDK path")
    outcome = analyze(fixture_log("uvm_assertion.log"))
    with pytest.raises(AIReasoningError, match="not installed"):
        AIReasoner().review(outcome.graph, outcome.report.reasoning)


def test_missing_credentials_raise_clean_error(fixture_log, monkeypatch):
    """The SDK reports missing credentials as a TypeError; the CLI must see one clean AIReasoningError."""
    import sys
    import types

    fake = types.ModuleType("anthropic")

    class APIError(Exception):
        pass

    class Anthropic:
        class messages:
            @staticmethod
            def create(**_):
                raise TypeError('"Could not resolve authentication method. Expected either api_key or auth_token"')

    fake.APIError, fake.Anthropic = APIError, Anthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    outcome = analyze(fixture_log("uvm_assertion.log"))
    with pytest.raises(AIReasoningError, match="no Anthropic credentials"):
        AIReasoner().review(outcome.graph, outcome.report.reasoning)

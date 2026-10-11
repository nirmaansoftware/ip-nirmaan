"""Optional AI reasoning stage: refine hypotheses, never invent facts.

The AI boundary, restated for this module because it is the one place it
matters most:

* Input is ONLY the selected evidence (the working set's graph view), the
  deterministic signals, the ranked hypotheses, and the recommendations.
  No file is opened here; no raw artifact text is transmitted.
* The model is prompted as an experienced CPU DV engineer whose job is to
  improve hypothesis quality, explain reasoning, point at missing evidence,
  and cite node IDs for every statement.
* Output is structured (:class:`~veritriage.models.AIReview`) and attached
  alongside the deterministic result; it can never alter the graph, the
  signals, the hypothesis ranking, or the recommendations.

The dependency is optional (``pip install ip-nirmaan[ai]``); without it the
reasoning pipeline is complete and deterministic.
"""

from __future__ import annotations

import json

from veritriage.graph.graph import EvidenceGraph
from veritriage.models import AIReview, ReasoningResult

# Equal to Nirmaan's model profile (M47); a test keeps the two in sync.
DEFAULT_MODEL = "claude-opus-5-5"

_SYSTEM_PROMPT = """\
You are an experienced CPU Design Verification engineer reviewing a
regression failure investigation produced by a deterministic reasoning
engine.

You are given: the selected evidence (typed graph nodes with IDs, severities,
times, scopes, and typed relationships), the deterministic signals that
fired, the ranked competing hypotheses, and the current recommendations.

Your job:
- Improve hypothesis quality: sharpen or challenge each hypothesis based on
  the evidence, in one or two sentences each.
- Explain the failure the way you would to a colleague at a whiteboard.
- Identify missing evidence: what artifact or observation would best
  discriminate between the competing hypotheses.

Hard rules:
- Never fabricate signals, modules, times, or causes. Every statement must
  reference the supporting evidence node id(s) in parentheses.
- If the evidence cannot support a claim, say what is missing instead.
- Do not repeat the recommendations verbatim; add judgment, not bulk."""

_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative": {
            "type": "string",
            "description": "Engineer-style walkthrough of the failure, citing node IDs.",
        },
        "missing_evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Artifacts/observations that would discriminate between hypotheses.",
        },
        "hypothesis_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hypothesis_id": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["hypothesis_id", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["narrative", "missing_evidence", "hypothesis_notes"],
    "additionalProperties": False,
}


class AIReasoningError(RuntimeError):
    """Raised when an AI review was requested but could not be produced."""


def build_ai_payload(graph: EvidenceGraph, result: ReasoningResult) -> dict:
    """The complete AI input: selected evidence view + deterministic outputs.

    Kept as a standalone function so tests can pin exactly what crosses the
    AI boundary.
    """
    return {
        "selected_evidence": graph.to_reasoning_view(node_ids=set(result.working_set.node_ids)),
        "selection_reasons": [item.model_dump() for item in result.working_set.items],
        "signals": [s.model_dump(mode="json") for s in result.signals],
        "hypotheses": [h.model_dump(mode="json") for h in result.hypotheses],
        "recommendations": [r.model_dump(mode="json") for r in result.recommendations],
    }


class AIReasoner:
    """Runs the optional AI review over a completed deterministic result."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model

    @staticmethod
    def available() -> bool:
        """True if the optional ``anthropic`` package is installed."""
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def review(self, graph: EvidenceGraph, result: ReasoningResult) -> AIReview:
        """Produce a structured AI review of the deterministic reasoning.

        Raises:
            AIReasoningError: If the SDK is missing or the API call fails.
        """
        try:
            import anthropic
        except ImportError as exc:
            raise AIReasoningError(
                "AI review requested but the 'anthropic' package is not installed. "
                "Install with: pip install ip-nirmaan[ai]"
            ) from exc

        payload = build_ai_payload(graph, result)
        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,  # reviews are deliberately short
                thinking={"type": "adaptive"},
                system=_SYSTEM_PROMPT,
                output_config={"format": {"type": "json_schema", "schema": _REVIEW_SCHEMA}},
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Review this failure investigation:\n\n"
                            f"{json.dumps(payload, indent=2)}"
                        ),
                    }
                ],
            )
        except anthropic.APIError as exc:
            raise AIReasoningError(f"Anthropic API call failed: {exc}") from exc

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise AIReasoningError("Model returned an empty review.")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIReasoningError(f"Model returned non-JSON output: {exc}") from exc
        notes = {
            item["hypothesis_id"]: item["note"] for item in data.get("hypothesis_notes", [])
        }
        return AIReview(
            narrative=data.get("narrative", ""),
            missing_evidence=data.get("missing_evidence", []),
            hypothesis_notes=notes,
        )

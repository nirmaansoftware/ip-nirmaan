"""VeriTriage - verification intelligence for semiconductor regression debug.

VeriTriage ingests verification artifacts (simulation logs, compile logs,
coverage summaries, test metadata), normalizes everything into a typed
Evidence Graph, runs a deterministic rule engine over the graph to classify
the failure, and emits structured JSON, the serialized graph, and an
engineering-grade HTML report. An optional AI layer reasons exclusively over
the graph's normalized view: it can narrate the evidence, never invent it.
"""

__version__ = "1.22.0"

__all__ = ["__version__"]

"""The models IP Nirmaan can seat, as data (M31): what each offers and what it costs.

Prices are USD per million tokens, from the claude-api skill's model table
(cached 2026-09-25): Claude Opus 5.5 is $4 input, $20 output, $0.20 cache
reads; cache writes are 1.25 times input. ``context_chars`` is the prompt
budget the provider declares to VeriTriage's registry (400,000 characters),
not the model's raw window, so the two never disagree.
"""

from __future__ import annotations

from nirmaan.models import ModelProfile

# The one place Nirmaan names the Claude model (M47). The anthropic provider and the
# claude-code runtime read it from here; VeriTriage keeps an equal constant of its
# own (it may not import Nirmaan), held equal by tests/test_review_cleanups.py.
DEFAULT_MODEL = "claude-opus-5-5"

PROFILES: list[ModelProfile] = [
    ModelProfile(id=DEFAULT_MODEL, provider="anthropic", model=DEFAULT_MODEL,
                 offers=("structured_output", "files"), context_chars=400_000,
                 input_per_mtok=4.0, output_per_mtok=20.0, cache_read_per_mtok=0.2, cache_write_per_mtok=5.0,
                 description="Claude Opus 5.5 through the Anthropic provider (the ai extra and credentials)."),
    ModelProfile(id="mock-llm", provider="mock-llm", model="mock-llm",
                 offers=("structured_output", "files"), context_chars=10_000_000,
                 input_per_mtok=0.0, output_per_mtok=0.0, cache_read_per_mtok=0.0, cache_write_per_mtok=0.0,
                 for_testing=True, description="The deterministic MockLLM; never chosen unless testing."),
]

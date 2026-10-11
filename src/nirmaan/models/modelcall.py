"""Model profiles and model calls (M31): which models can serve a seat, and what each call cost.

A profile declares what a model offers and what it costs. A call record is
written by the engine for every model call a seat made, with the usage the
provider reported; nothing unreported is guessed.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    provider: str = Field(description="An M17 provider name, or 'mock-llm' for the deterministic MockLLM.")
    model: str = Field(description="The model ID the provider is asked for and reports.")
    offers: tuple[str, ...] = Field(description="What it can do, e.g. 'structured_output', 'files'.")
    context_chars: int = Field(ge=1, description="The largest rendered prompt it accepts, in characters.")
    input_per_mtok: float | None = Field(default=None, description="USD per million input tokens; None: unknown.")
    output_per_mtok: float | None = None
    cache_read_per_mtok: float | None = None
    cache_write_per_mtok: float | None = None
    for_testing: bool = Field(default=False, description="Chosen only when a caller asks for testing profiles.")
    description: str = ""


class ModelCall(BaseModel):
    """One call a seat made to a model, as reported. Recorded even when the call failed."""

    model_config = ConfigDict(frozen=True)

    id: str
    task: str
    actor: str
    purpose: str = Field(description="'work' or 'review'.")
    provider: str = ""
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    cost_usd: float | None = Field(default=None, description="From the model's profile; None when unknown.")
    succeeded: bool = True
    error: str | None = None

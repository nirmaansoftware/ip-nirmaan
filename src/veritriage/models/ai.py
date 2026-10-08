"""AI provider vocabulary (Milestone 17).

The structured objects exchanged with a generative provider. Like every model
in this package these are plain data importing nothing from the graph or engine
layers.

The shape encodes the milestone's law: a provider is handed a frozen
:class:`Prompt` built from cited platform objects and returns text. It never
receives a raw artifact, a store, a service, or a graph, so "providers render,
never reason" holds by construction rather than by convention.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RenderStyle(str, Enum):
    """Who a rendered view is written for."""

    EXECUTIVE = "executive"
    ENGINEER = "engineer"
    DIGEST = "digest"
    EXPLANATION = "explanation"
    WALKTHROUGH = "walkthrough"

    @property
    def display_name(self) -> str:
        return self.value.title()


class ProviderCapabilities(BaseModel):
    """What a provider can do, declared rather than discovered.

    Honest capability declaration is the same posture the waveform adapters
    take: a provider that cannot do something says so, and the caller degrades
    visibly instead of silently getting worse output.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    version: str = "1.0.0"
    generates: bool = Field(
        default=True, description="False for the null provider, which generates nothing."
    )
    deterministic: bool = Field(
        default=False,
        description="True when identical prompts always yield identical text.",
    )
    local: bool = Field(default=True, description="False when generation leaves the machine.")
    max_prompt_chars: int = Field(
        default=100_000, ge=0, description="Prompt budget this provider accepts."
    )
    supports_citations: bool = Field(
        default=True, description="Whether the provider is asked to echo citation tokens."
    )
    notes: str | None = None


class Citation(BaseModel):
    """One artifact a generation is allowed to reference."""

    model_config = ConfigDict(frozen=True)

    kind: str = Field(description="evidence / hypothesis / knowledge / design / agent / plan / learning / history.")
    ref_id: str
    label: str = ""

    @property
    def token(self) -> str:
        """The exact string a provider must use to cite this artifact."""
        return f"[{self.kind}:{self.ref_id}]"


class PromptSection(BaseModel):
    """One typed part of a prompt, built from platform objects."""

    model_config = ConfigDict(frozen=True)

    heading: str
    lines: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = ()


class Prompt(BaseModel):
    """A frozen, inspectable generation request.

    Everything a provider will see. Built purely from structured input, so what
    a provider is about to be asked can be audited without asking it.
    """

    model_config = ConfigDict(frozen=True)

    template_id: str
    template_version: str = "1"
    style: RenderStyle = RenderStyle.ENGINEER
    system: str = Field(description="Role and hard rules, from a versioned template.")
    task: str = Field(description="What this particular generation should produce.")
    sections: tuple[PromptSection, ...] = ()
    citations: tuple[Citation, ...] = Field(
        default=(), description="The complete set of artifacts the response may reference."
    )

    @property
    def allowed_tokens(self) -> set[str]:
        return {c.token for c in self.citations}

    def render(self) -> str:
        """The prompt as the provider receives it. Deterministic."""
        parts = [self.system, "", f"TASK: {self.task}", ""]
        if self.citations:
            parts.append("CITE ONLY THESE ARTIFACTS, using the token exactly as written:")
            parts.extend(f"  {c.token}  {c.label}" for c in self.citations)
            parts.append("")
        for section in self.sections:
            parts.append(f"## {section.heading}")
            parts.extend(f"- {line}" for line in section.lines)
            parts.append("")
        return "\n".join(parts).strip()

    @property
    def size(self) -> int:
        return len(self.render())


class GenerationRequest(BaseModel):
    """What crosses the provider boundary. Nothing else does."""

    model_config = ConfigDict(frozen=True)

    prompt: Prompt
    max_output_chars: int = Field(default=4_000, ge=1)


class GenerationResponse(BaseModel):
    """What a provider returns: text, and nothing that could be a conclusion."""

    model_config = ConfigDict(frozen=True)

    text: str = ""
    provider: str = ""
    model: str | None = None
    failed: bool = False
    error: str | None = None
    #: Token usage, when the provider reports it; None means not reported (never guessed).
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None


class GeneratedView(BaseModel):
    """Prose plus the structured object it restates.

    Both are always present. A client that does not trust generation renders
    the structured object and ignores the prose; nothing is lost, which is what
    makes generated text an additional view rather than the source of truth.
    """

    style: RenderStyle
    prose: str = ""
    provider: str = ""
    grounded: bool = Field(
        default=True, description="False when the provider cited artifacts it was not given."
    )
    citations: list[Citation] = Field(
        default_factory=list, description="Artifacts the prose actually referenced."
    )
    stripped_citations: list[str] = Field(
        default_factory=list, description="Invented citations removed from the prose."
    )
    prompt_id: str = ""
    limitations: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.prose.strip()


class ProviderStatus(BaseModel):
    """One provider's health and capabilities, for discovery and diagnostics."""

    name: str
    available: bool
    active: bool = False
    capabilities: ProviderCapabilities | None = None
    error: str | None = None

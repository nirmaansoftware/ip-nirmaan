"""Model selection (M31): a seat states what it needs; a model that can serve it is chosen, or none is.

What a seat needs is derived from its work: ``structured_output`` always (every
seat answers with one JSON object), ``files`` when any of the task's evidence
requirements runs over files the task produces, and whatever its capability
declares in ``model_needs``. ``select_model`` keeps the profiles that offer
every need and whose prompt budget holds the rendered prompt, leaves testing
profiles out unless asked, and picks the cheapest known price; every profile
it rejects is listed with the reason. The ``auto`` runtime selects per call.
"""

from __future__ import annotations

import dataclasses
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from nirmaan.company.model_profiles import PROFILES
from nirmaan.models import ModelProfile
from nirmaan.registry import Registry
from nirmaan.runtime.base import register_runtime
from nirmaan.runtime.context import WorkPacket
from nirmaan.runtime.model import LLM, NO_CALL, Completion, MockLLM, ModelRuntime, RegistryLLM
from nirmaan.runtime.prompt import WorkPrompt

_PROFILES: MutableMapping[str, ModelProfile] = Registry("runtime.model_profiles")
_PROFILES.update({p.id: p for p in PROFILES})
#: Providers served by something other than the M17 registry. Everything else is ``RegistryLLM(provider)``.
_LLM_FACTORIES: MutableMapping[str, Callable[[ModelProfile], LLM]] = Registry("runtime.llm_factories")
_LLM_FACTORIES["mock-llm"] = lambda p: MockLLM(model=p.model)


def register_model_profile(profile: ModelProfile) -> ModelProfile:
    if profile.id in _PROFILES and _PROFILES[profile.id] != profile:
        raise ValueError(f"Model profile {profile.id!r} is already registered")
    _PROFILES[profile.id] = profile
    return profile


def unregister_model_profile(profile_id: str) -> None:
    _PROFILES.pop(profile_id, None)


def model_profiles() -> list[ModelProfile]:
    return [_PROFILES[k] for k in sorted(_PROFILES)]


def register_llm_factory(provider: str, factory: Callable[[ModelProfile], LLM]) -> None:
    _LLM_FACTORIES[provider] = factory


def llm_for(profile: ModelProfile) -> LLM:
    factory = _LLM_FACTORIES.get(profile.provider)
    return factory(profile) if factory else RegistryLLM(profile.provider)


# --- Needs and selection -------------------------------------------------------------------


def seat_needs(packet: WorkPacket) -> tuple[str, ...]:
    """What a model must offer to serve this seat, derived from its work."""
    needs = ["structured_output"]
    if any(not b.upstream for req in packet.task.evidence_requirements for b in req.files):
        needs.append("files")
    needs += list(packet.task.model_needs)
    return tuple(dict.fromkeys(needs))


@dataclass(frozen=True)
class ModelChoice:
    profile: ModelProfile | None
    needs: tuple[str, ...]
    prompt_chars: int
    rejected: dict[str, str] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        if self.profile is not None:
            return f"{self.profile.id} serves {', '.join(self.needs)} ({self.prompt_chars} prompt characters)"
        reasons = "; ".join(f"{pid}: {why}" for pid, why in sorted(self.rejected.items())) or "no profiles"
        return f"no model fits {', '.join(self.needs)} ({self.prompt_chars} prompt characters): {reasons}"


def _price(profile: ModelProfile) -> float:
    known = [p for p in (profile.input_per_mtok, profile.output_per_mtok) if p is not None]
    return sum(known) if len(known) == 2 else float("inf")


def select_model(needs: Sequence[str], prompt_chars: int, profiles: Iterable[ModelProfile] | None = None,
                 include_testing: bool = False) -> ModelChoice:
    """The cheapest profile that offers every need and holds the prompt, or None with every reason."""
    candidates = list(model_profiles() if profiles is None else profiles)
    fits, rejected = [], {}
    for profile in candidates:
        missing = [n for n in needs if n not in profile.offers]
        if profile.for_testing and not include_testing:
            rejected[profile.id] = "a testing profile, not chosen outside tests"
        elif missing:
            rejected[profile.id] = f"does not offer {', '.join(missing)}"
        elif prompt_chars > profile.context_chars:
            rejected[profile.id] = f"the prompt ({prompt_chars} characters) exceeds its context ({profile.context_chars})"
        else:
            fits.append(profile)
    best = min(fits, key=lambda p: (_price(p), p.id)) if fits else None
    return ModelChoice(best, tuple(needs), prompt_chars, rejected)


def cost_of(call: dict[str, Any]) -> float | None:
    """A call's cost from its model's profile; None when the model, a price, or the usage is unknown."""
    profile = next((p for p in _PROFILES.values() if p.model == call.get("model")), None)
    if profile is None or call.get("input_tokens") is None or call.get("output_tokens") is None:
        return None
    total = 0.0
    for tokens_key, price in (("input_tokens", profile.input_per_mtok), ("output_tokens", profile.output_per_mtok),
                              ("cache_read_tokens", profile.cache_read_per_mtok),
                              ("cache_write_tokens", profile.cache_write_per_mtok)):
        tokens = call.get(tokens_key) or 0
        if tokens and price is None:
            return None
        total += tokens * (price or 0.0) / 1_000_000
    return round(total, 6)


class SelectingLLM:
    """An LLM that chooses a model per call from the prompt's needs and size (the ``auto`` runtime)."""

    name = "auto"

    def __init__(self, profiles: Iterable[ModelProfile] | None = None, include_testing: bool = False) -> None:
        self._profiles = list(profiles) if profiles is not None else None
        self._include_testing = include_testing
        self.choices: list[ModelChoice] = []

    def complete(self, prompt: WorkPrompt) -> Completion:
        choice = select_model(prompt.needs or ("structured_output",), len(prompt.render()), self._profiles,
                              self._include_testing)
        self.choices.append(choice)
        if choice.profile is None:
            return Completion("", error=NO_CALL + choice.summary)
        completion = llm_for(choice.profile).complete(prompt)
        return dataclasses.replace(completion, provider=completion.provider or choice.profile.provider,
                                   model=completion.model or choice.profile.model)


register_runtime("auto")(lambda: ModelRuntime(SelectingLLM(), runtime_id="auto"))

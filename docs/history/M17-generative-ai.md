# Milestone 17 (v1.13.0) - Generative AI providers

The milestone that introduces LLMs without letting them near a conclusion. New
top-level package `ai/`, above `conversation/`, below `workspace/`. It owns
provider integration and no verification intelligence.

**The critical evaluation that simplified the milestone.** The spec asked for
`ai/LLMProvider` as a fresh abstraction, but M12 had already shipped
`agents.ReasoningProvider` with NullProvider, DeterministicProvider, a registry,
and a documented promise that a vendor is "one class plus one registration". A
parallel registry would have meant two registries, two NullProvider semantics,
two config paths, and two places to register Anthropic.

But the M12 seam genuinely could not carry M17: it is **agent-shaped**
(`elaborate(ProviderRequest with agent_id/domain/observations/hypotheses)`),
with no way to ask for a project digest or a design walkthrough.

**Adopted design:** `ai/` owns ONE `LLMProvider` shaped like a *vendor* (frozen
prompt in, text out) rather than like a use case. The M12 contract stays frozen
and untouched, and `ai/adapters.LlmReasoningProvider` satisfies it by delegating
to an `LLMProvider`. Registering a vendor once therefore serves both agent
narration and every renderer. Pinned by
`test_the_m12_contract_is_untouched` (agents/providers.py must not mention
veritriage.ai).

**The load-bearing decision:** providers render, never reason. A provider's
entire input is a frozen `Prompt`: no path, no store, no service, no graph, no
report. "Read-only" therefore holds by construction, because a provider has
nothing to mutate anything with.

**Grounding is enforced, not requested.** The `Prompt` declares its citation
set; `grounding.enforce()` scans the response and strips any token outside it,
recording the omission. Deterministic, and no model is needed to check a model.
Same pattern as the M12 Coordinator `_verify` and the M16 Conversation `_verify`.
Tested against a `MockProvider` that deliberately invents citations.

Structure: `provider.py` (LLMProvider Protocol + BaseProvider whose `generate`
returns failures rather than raising), `registry.py`
(`@register_llm_provider`; named apart from M12's `register_provider`),
`providers/` (null, deterministic-echo, mock, reference), `prompt.py`
(PromptTemplate/PromptContext/PromptBuilder + 7 versioned templates; building is
pure and the prompt is inspectable), `grounding.py`, `renderers.py` (7 named
views, an enumerable closed list), `adapters.py` (the M12 bridge), `service.py`
(AIService: selection, capability discovery, health, degradation).

Additive edits only: five WorkspaceServices methods, 6 MCP tools (59 -> 65), CLI
`render` and `providers` commands. **No report schema bump**: generated prose is
a view, never a report field.

**Honest note carried in the docs:** `reasoning/ai.py` (M3 `AIReasoner`) is the
only file in the repo importing a vendor SDK and hardcoding a model name. The
non-goal forbade changing reasoning, so it stays and keeps working via
`analyze --ai`. It is now explicitly the *legacy* path, superseded by `ai/`;
saying so in AI_PROVIDERS.md rather than leaving it as a trap.

38 new tests (647 total). Design doc: `docs/AI_PROVIDERS.md` (approved before
implementation). Crown jewel `test_new_provider_needs_only_registration`: a
throwaway ACME vendor defined in the test renders, has its hallucinated citation
stripped by the same enforcement as every built-in, appears in discovery
honestly declaring it is not local, and serves the M12 agent seam through the
same registry. Caught during implementation: the vendor-SDK guard matched vendor
names in a docstring listing *future* integrations, fixed by checking imports
via AST rather than substrings (the same false-positive class as M14's
`requests.`).

Deferred to M17.x: actual vendor integrations (OpenAI, Anthropic, Google, local
models, MCP-hosted); per-provider grounding reliability aggregated by the
Learning Engine via `grounding.grounded_ratio`; retiring `reasoning/ai.py` in
favour of an `ai/` provider.

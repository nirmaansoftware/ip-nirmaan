# Milestone 20 - AI workers in verification seats (roadmap Stage 1)

The first language-model workers, seated where their output can be checked:
verification debug. Three seats from the regression-investigation workflow
(Demo 4): failure triage (runs `veritriage.investigate`), root cause (a
decision over the declared outcomes), and debug review (a different seat and a
separate model call). Everything they return goes through `run_task` /
`review_task` and the engine, exactly like a human's work. Off by default:
`unbound` stays the default runtime. Version number left to the coordinator
at merge.

**The open decision (settled in `docs/AI_WORKERS.md`).** The runtime reaches a
model through the bridge, not through its own adapter. The bridge gained
`render_prompt`, `generate`, and `ground`, which wrap the M17 registry, its
frozen `Prompt`, and `grounding.enforce`. So one vendor registry still serves
the whole platform, and citation stripping has one implementation. The
Anthropic provider (`claude-opus-5-5`, adaptive thinking, effort high,
`fallbacks: "default"` under `server-side-fallback-2026-07-01`, SDK imported
lazily) is registered into the M17 registry by the bridge, because
`test_no_vendor_sdk_in_ai` forbids vendor SDKs in `veritriage/ai/` and
VeriTriage was not to change. A refusal or truncation is a failed generation.

Structure:
- `runtime/prompt.py`: `WorkPrompt`, `render_work_prompt(packet, mode)`. Only
  the four scopes (Company, Domain, Project, Task) are rendered; memory never
  is. Evidence and tool runs become citation tokens; Nirmaan IDs have `:` and
  `#` replaced by `.` to fit M17's token grammar, with the mapping kept.
- `runtime/model.py`: `ModelRuntime` (one class for every seat), the `LLM`
  protocol, `RegistryLLM` (any M17 provider), `MockLLM` (deterministic,
  scriptable). Registered runtimes: `mock-llm`, `anthropic`.
- `runtime/base.py`: `review_task` (P6 checked before any model call),
  `ReviewResult`, `unregister_runtime`, `RunReport.review`.
- `runtime/context.py`: `assemble(..., role=)` builds a packet for another
  seat; the task scope now carries evidence (own and upstream) and the task's
  own artifacts. `Artifact.summary` (new optional field) stores an agent's
  cited write-up.
- `cli.py`: `nirmaan run PROJECT TASK --runtime ID [--review] [--dry-run]
  [--input key=value]`. Inputs are recorded as task memory `input.<key>`.

Key design points worth not re-deriving:
- Seat behaviour is derived from the packet, never from a role or stage name:
  tools named by tool-backed evidence requirements run before the model is
  asked (with `input.*` params); outcomes come from the task.
- Prose citations are stripped when undeclared; an artifact left uncited is
  dropped (then P4 refuses an empty completion). Declared `tool_runs` go to
  the engine unfiltered, so a fabricated run is refused by P5 rather than
  silently cleaned.
- A failed or non-JSON model answer is DECLINED with uncertainty 1.0: any
  tool runs that really happened are still recorded, nothing else is.
- An uncited review is not recorded.

20 new tests in `tests/test_nirmaan_ai_workers.py` (879 -> 899). Demo 4 runs
triage, root cause, and review on agents with `tests/fixtures/axi_timeout.log`
and ends at a human approval that picks the fix branch. The Anthropic
provider is tested against a fake `anthropic` module; no test calls an API.
Crown jewel `test_a_new_runtime_registers_with_zero_core_changes` registers a
new model runtime and runs it through `nirmaan run`; a second test proves any
M17 provider (VeriTriage's `mock`) serves a seat through the one registry.
Deferred: seating from `AgentProfile.runtime`, model-chosen tool calls, seats
outside verification, token and cost accounting.

# Milestone 31 - Model selection by capability, and every model call counted

The fifth structural-review milestone. Design
doc: `docs/MODEL_SELECTION.md`. No version bump.

Key design points worth not re-deriving:
- **Accounting is the engine's.** `ModelRuntime` lists every call it made in its
  `WorkResult`/`ReviewResult` (`model_calls`); `run_task` and `review_task`
  record each through `TaskEngine.record_model_call` (audited `model.call`)
  before anything else, so a declined, refused, or failed call is still
  counted. `ProjectState.model_calls` is a new, defaulted field (old projects
  load). Usage travels VeriTriage `GenerationResponse` (new optional token
  fields, the only VeriTriage change) -> bridge `Generation` -> `Completion`.
  The Anthropic provider reads `response.usage` (`input_tokens`,
  `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`);
  a missing `usage` is `None`, never zero. Cost comes from the model's profile
  (`cost_of`); unknown price or usage is `None`.
- **Prices** (claude-api skill, cached 2026-09-25): Opus 5.5 $4 input, $20
  output, $0.20 cache read per million tokens; cache write 1.25 times input.
  `context_chars` is 400,000, matching the provider's declared prompt budget.
- **Needs are derived, not hand-written**: `structured_output` always, `files`
  when an evidence requirement runs over files the task produces, plus the new
  `Capability.model_needs`. `select_model` keeps profiles offering every need
  whose budget holds the rendered prompt, excludes `for_testing` profiles unless
  asked, picks the cheapest known price (ties by ID), and lists every rejection.
- **The `auto` runtime** is `ModelRuntime(SelectingLLM())`; with nothing fitting,
  it declines with the reasons and makes no call (the `NO_CALL` prefix keeps it
  out of the accounting). `MockLLM(model=...)` reports a profile's model.
- `nirmaan costs PROJECT [--json]`; evaluation results gain `model_calls`,
  `input_tokens`, `output_tokens`, `cost_usd`.

`tests/test_nirmaan_model_selection.py` (14), crown jewel
`test_a_new_model_profile_needs_no_core_changes`. The standard local run is
1401 passed, 3 skipped.

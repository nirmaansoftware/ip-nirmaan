# Model selection and model-call accounting (M31)

The fifth structural-review milestone (`docs/architecture/target-state.md`
section 5). Two gaps: a seat is bound to a
model by runtime name (`--runtime anthropic`), and nothing records what a model
call cost. A seat should state what it needs, the platform should pick a model
that can serve it (or refuse, and say why), and every call should leave a record
that can be added up per task, per project, and per evaluation.

## Accounting first

Every model call becomes a **`ModelCall`** record in project state, written by
the engine (`TaskEngine.record_model_call`, audited as `model.call`), never by
a runtime:

| Field | Meaning |
|---|---|
| `task`, `actor`, `purpose` | Which seat called, for `work` or `review` |
| `provider`, `model` | As the provider reported them |
| `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` | As reported; `None` when the provider does not report usage |
| `cost_usd` | From the model's profile prices; `None` when the price or the usage is unknown, never guessed |
| `succeeded`, `error` | A failed call is recorded too: it may still have cost money |

The path: VeriTriage's `GenerationResponse` gains optional token fields (a
generic addition; providers that do not know leave them empty), the Anthropic
provider fills them from `response.usage`, the bridge passes them on,
`Completion` carries them, `ModelRuntime` lists every call in its `WorkResult`
or `ReviewResult`, and `run_task` / `review_task` record each one through the
engine, including calls whose answer was declined or refused.

Views: `nirmaan costs PROJECT [--json]` totals calls, tokens, and cost by model,
purpose, and task, and says how many calls have no known cost. An evaluation
result (M27) gains the calls, tokens, and cost of its seat run, so model
choices can be compared on evidence.

## Selection

**`ModelProfile`** (data, `company/model_profiles.py`, extendable with
`register_model_profile`): `id`, `provider` (an M17 provider name), `model`,
`offers` (capabilities such as `structured_output`, `files`), `context_chars`,
prices per million tokens (input, output, cache read, cache write; `None` when
unknown), and `for_testing`. Two ship:

- `claude-opus-5-5` on provider `anthropic`: offers `structured_output` and
  `files`; `context_chars` 400,000, the prompt budget the provider declares to
  VeriTriage's registry (the model's own window is 1M tokens); $4 input and $20
  output per million tokens, $0.20 cache reads, $5 cache writes (1.25 times
  input);
- `mock-llm` (the deterministic MockLLM), `for_testing`, cost 0.

**What a seat needs** is derived from its work, not written by hand:
`structured_output` always (every seat answers with one JSON object), `files`
when any of the task's evidence requirements runs over files the task produces,
plus anything its capability declares in a new optional field,
`Capability.model_needs`.

**`select_model(needs, prompt_chars)`** keeps the profiles that offer every
need and whose context holds the rendered prompt, drops `for_testing` profiles
unless asked, and picks the cheapest known price (unknown prices last, ties by
ID). Every rejected profile is listed with its reason. When nothing fits, the
answer is a refusal with those reasons: the seat declines, no call is made.

**The `auto` runtime** is the one `ModelRuntime` with a selecting LLM: per call
it derives the needs, selects, and delegates to the chosen profile's provider,
and the call record names the model chosen. `--runtime anthropic` and
`--runtime mock-llm` are unchanged.

## Tests (`tests/test_nirmaan_model_selection.py`)

- Selection: a need no profile offers is refused with every reason; a prompt
  larger than a context is refused; the cheaper of two fitting profiles wins;
  testing profiles are used only when asked.
- Needs: an RTL seat (checks over its files) needs `files`; a triage seat does
  not; a capability's `model_needs` are added.
- Accounting: a work run and a review run each record their calls with tokens
  and cost; a declined answer still records its call; a provider with no usage
  records `None` tokens and `None` cost; `nirmaan costs` adds them up;
  the Anthropic provider reads `usage` from a fake SDK response; an evaluation
  result carries the totals.
- Crown jewel `test_a_new_model_profile_needs_no_core_changes`: a profile
  registered in the test, offering a need a capability declares, is selected
  by the `auto` runtime.

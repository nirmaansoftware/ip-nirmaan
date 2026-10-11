# The claude-code runtime

A seat filled through Claude Code's non-interactive mode (`claude -p`), on the
person's own Claude plan. The `anthropic` runtime calls the Messages API and
needs API credits, which are billed separately from a Claude subscription; this
runtime needs only a signed-in Claude Code.

```
NIRMAAN_CLAUDE_CODE=/path/to/claude nirmaan eval run --runtime claude-code
nirmaan run PROJECT TASK --runtime claude-code
```

The executable is `NIRMAAN_CLAUDE_CODE`, else `claude` on PATH (the VS Code
extension bundles one under `resources/native-binary/claude`; its path changes
with each update). The model is `NIRMAAN_CLAUDE_CODE_MODEL`, else Claude Opus 5.5.

## What is the same

Everything around the model: the work packet and prompt, grounding (undeclared
citations stripped, uncited artifacts dropped), the tools that must pass before
review, the repair loop, the held-out judges of an evaluation, and the engine
recording every call. The runtime is `ModelRuntime(ClaudeCodeLLM())`; only the
LLM differs.

## How the call is kept clean and honest

| Concern | What the runtime does |
|---|---|
| The prompt is the packet and nothing else | `--system-prompt` carries the system prompt, stdin the rest; the process runs in an empty temporary directory, so no `CLAUDE.md` or project memory is loaded; `--strict-mcp-config` loads no MCP servers; `--no-session-persistence` |
| The seat answers, it does not act | `--tools ""`: no tools. Seats answer in text, and only the broker runs tools |
| The plan pays, not a key | `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` are removed from the process environment (with a key present, Claude Code bills the key) |
| No invented cost | Tokens are recorded as Claude Code reports them; the cost is recorded as unknown. A subscription has no per-call price, and Claude Code's `total_cost_usd` is an API-equivalent estimate, not a charge (`Completion.priced = False`) |
| Failures are facts | An error result, output that is not JSON, or a timeout is a recorded failed call; no executable is a decline with nothing called or counted |

`--bare` would skip memory more thoroughly, but it refuses the OAuth login a
plan uses, so it cannot serve this purpose.

## Tests

`tests/test_nirmaan_claude_code.py` (6), all against a fake `claude` the test
writes: the exact command, stdin, empty working directory, and stripped
credentials; a reply recorded with tokens and no cost; error and non-JSON
results recorded as failed; no executable declined without a call; an
evaluation run on this runtime.

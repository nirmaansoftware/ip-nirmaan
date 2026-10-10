# Claude Code runtime, and the first live evaluation (after v1.22.0)

A `claude-code` runtime (`runtime/claude_code.py`, `docs/CLAUDE_CODE_RUNTIME.md`)
fills a seat through `claude -p` on the owner's Claude plan; the `anthropic`
runtime needs API credits, which a subscription does not include, and the
owner's key had none. Key points: system prompt in `--system-prompt`, the rest
on stdin, `--tools ""`, `--strict-mcp-config`, `--no-session-persistence`, an
empty working directory (no `CLAUDE.md` or memory reaches the prompt), and
`ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` stripped so the plan login is used.
Tokens are recorded as reported; cost is unknown (`Completion.priced=False`),
because Claude Code's `total_cost_usd` is an API-equivalent estimate. `--bare`
refuses OAuth, so it cannot be used. The bundled binary's path changes with each
extension update; pass it as `NIRMAAN_CLAUDE_CODE`.

The first live evaluation (Opus 5.5) failed the AXI4-Lite case on both held-out
judges with RTL that passed its own gates: ports named without the `s_axil_`
prefix and no `DATA_WIDTH`. The RTL seat had never seen the interface spec
(its `block-design` stage depended only on the microarchitecture). It now
depends on `interface-spec` and `microarchitecture`; all four RTL cases then
passed on the first attempt (`docs/SEAT_EVALUATION.md`, "First live results").
`tests/test_nirmaan_claude_code.py` (6); a verification-plan test now asserts
the new dependencies and keeps its intent (nothing waits on the plan).

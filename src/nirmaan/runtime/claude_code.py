"""A seat filled through Claude Code (``claude -p``), on the person's own Claude plan.

The ``anthropic`` runtime calls the API and needs API credits. This one hands
the same work prompt to Claude Code's non-interactive mode, which runs on the
subscription the person is signed in to. Everything around the model is
unchanged: grounding, the tools that must pass before review, the held-out
judges, and the call record.

How the call is kept honest and clean:

* the system prompt goes in ``--system-prompt``, the rest of the prompt on
  stdin; ``--tools ""`` gives the model no tools (the seat answers in text, as
  every seat does), and ``--strict-mcp-config`` loads no MCP servers;
* it runs in an empty temporary directory, so no ``CLAUDE.md`` or project
  memory reaches the prompt, with ``--no-session-persistence``;
* ``ANTHROPIC_API_KEY`` and ``ANTHROPIC_AUTH_TOKEN`` are removed from its
  environment, so Claude Code uses the plan login rather than billing a key;
* tokens are recorded as Claude Code reports them, and the cost as unknown:
  a subscription has no per-call price, and its ``total_cost_usd`` is an
  API-equivalent estimate, not a charge.

The executable is ``NIRMAAN_CLAUDE_CODE`` or ``claude`` on PATH; the model is
``NIRMAAN_CLAUDE_CODE_MODEL`` or the model profiles' ``DEFAULT_MODEL`` (Claude Opus 5.5). With no executable, the seat
declines and nothing is called or counted.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

from nirmaan.company.model_profiles import DEFAULT_MODEL
from nirmaan.runtime.base import register_runtime
from nirmaan.runtime.model import NO_CALL, Completion, ModelRuntime
from nirmaan.runtime.prompt import WorkPrompt

DEFAULT_TIMEOUT = 1800
PROVIDER = "claude-code"
_CREDENTIAL_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


def find_claude() -> str | None:
    """The Claude Code executable: ``NIRMAAN_CLAUDE_CODE`` if set, else ``claude`` on PATH."""
    return os.environ.get("NIRMAAN_CLAUDE_CODE") or shutil.which("claude")


def _int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class ClaudeCodeLLM:
    """An LLM that answers through ``claude -p --output-format json``."""

    name = PROVIDER

    def __init__(self, executable: str | None = None, model: str | None = None, timeout: int = DEFAULT_TIMEOUT):
        self._executable = executable
        self.model = model or os.environ.get("NIRMAAN_CLAUDE_CODE_MODEL") or DEFAULT_MODEL
        self.timeout = timeout

    def complete(self, prompt: WorkPrompt) -> Completion:
        from nirmaan.integrations.veritriage import render_parts

        executable = self._executable or find_claude()
        if not executable:
            return Completion("", error=NO_CALL + "no Claude Code executable (set NIRMAAN_CLAUDE_CODE or put "
                                                  "claude on PATH)")
        system, user = render_parts(prompt)
        argv = [executable, "-p", "--output-format", "json", "--model", self.model, "--system-prompt", system,
                "--tools", "", "--no-session-persistence", "--strict-mcp-config"]
        env = {k: v for k, v in os.environ.items() if k not in _CREDENTIAL_VARS}
        with tempfile.TemporaryDirectory(prefix="nirmaan-claude-code-") as cwd:
            try:
                proc = subprocess.run(argv, input=user, capture_output=True, text=True, cwd=cwd, env=env,
                                      timeout=self.timeout)
            except subprocess.TimeoutExpired:
                return Completion("", self.model, error=f"Claude Code did not answer within {self.timeout}s",
                                  provider=PROVIDER, priced=False)
            except OSError as exc:
                return Completion("", error=NO_CALL + f"Claude Code could not start: {exc}")
        try:
            data = json.loads(proc.stdout)
        except ValueError:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            return Completion("", self.model, error=f"Claude Code exited {proc.returncode} without a JSON result: "
                              f"{detail[-1] if detail else 'no output'}", provider=PROVIDER, priced=False)
        usage = data.get("usage") or {}
        reported = list((data.get("modelUsage") or {}).keys())
        common = dict(provider=PROVIDER, priced=False, input_tokens=_int(usage.get("input_tokens")),
                      output_tokens=_int(usage.get("output_tokens")),
                      cache_read_tokens=_int(usage.get("cache_read_input_tokens")),
                      cache_write_tokens=_int(usage.get("cache_creation_input_tokens")))
        model = reported[0] if reported else self.model
        if data.get("is_error") or data.get("subtype") != "success":
            return Completion("", model, error=f"Claude Code reported {data.get('subtype') or 'an error'}: "
                              f"{str(data.get('result') or '')[:300]}", **common)
        return Completion(str(data.get("result") or ""), model, **common)


register_runtime("claude-code")(lambda: ModelRuntime(ClaudeCodeLLM(), runtime_id="claude-code"))

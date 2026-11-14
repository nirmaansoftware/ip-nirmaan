# The harness and its fingerprint (M73)

A skill level is earned by a model and a harness together. The harness is
everything around the model in a seat's run (`run_task`): what the packet
carries, how the prompt is built and worded, how many times the seat may try,
what it is told when it tries again, and how the runtime calls the model.
Until this milestone the evidence levels (M63, `docs/CAPABILITY_LEVELS.md`)
grouped trials by skill, model and skill digest only, so a change to the
harness (M68 edited `runtime/prompt.py` and `runtime/model.py`) would have
mixed trials from two harnesses into one level without anyone seeing it.

## One place

`src/nirmaan/runtime/harness.py` holds every harness setting. The code reads
each one from there when it runs (`harness.NAME`), so there is one copy of
each and a test fails if another module defines one.

| Setting | Value | What it shapes | Read by |
|---|---|---|---|
| `DOMAIN_CAP` | 40,000 characters | knowledge documents in one packet; over it the seat declines (M61) | `org/knowledge.py` |
| `MAX_CONTENT` | 60,000 characters | one recorded file's content in a packet; larger is withheld | `runtime/context.py` |
| `DEFAULT_LIMITS` | attempts 1, review rounds 1, retries 1, retry then escalate | the limits when no override, stage or capability sets one (M48) | `work/limits.py` |
| `SCOPES` | Company, Domain, Project, Task | the prompt's sections, in this order (M20) | `runtime/prompt.py` |
| `WORK_SYSTEM`, `REVIEW_SYSTEM` | the system prompts, with the answer formats | every work and review prompt | `runtime/prompt.py` |
| `REPAIR_AFTER_REVIEW` | "Repair after review: submission N was sent back ..." | the work prompt after a review sent it back (M27) | `runtime/prompt.py` |
| `REPAIR_AFTER_REFUSAL` | "Repair: your previous attempt N was refused ..." | the work prompt after a refused attempt (M26) | `runtime/prompt.py` |
| `EXCERPT_LINES`, `EXCERPT_WIDTH` | 20 lines, 240 characters | the failed run's log excerpt on a retry (M26) | `runtime/files.py` |
| `EXCERPT_NOTABLE` | error, warning, fail, fatal, assert, mismatch | which log lines that excerpt shows first | `runtime/files.py` |
| `CLAUDE_CODE_TIMEOUT` | 1,800 seconds | one Claude Code answer (M33) | `runtime/claude_code.py` |
| `CLAUDE_CODE_FLAGS` | `--output-format json --tools "" --no-session-persistence --strict-mcp-config` | JSON out, no tools, no session, no MCP servers | `runtime/claude_code.py` |
| `CLAUDE_CODE_CLEARED_ENV` | `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` | removed so Claude Code answers on the plan login | `runtime/claude_code.py` |
| `ANTHROPIC_MAX_TOKENS` | 16,000 | the anthropic runtime's answer length | `integrations/veritriage.py` |
| `ANTHROPIC_THINKING`, `ANTHROPIC_EFFORT` | adaptive, high | the anthropic runtime's thinking and effort | `integrations/veritriage.py` |
| `MAX_OUTPUT_CHARS` | 64,000 characters | a registry provider's answer text | `integrations/veritriage.py` |

## The code

Some of a seat's run is code rather than a value: how each line of the prompt
is worded (M68's line about approved files beside the seat's own is one), how
a packet is assembled, how an answer is parsed and grounded, and how the eval
runner fixes the upstream stages. `harness.CODE` names those files and the
fingerprint carries the sha256 of each one's bytes:

- `nirmaan/runtime/`: `base.py`, `context.py`, `prompt.py`, `model.py`,
  `files.py`, `selection.py`, `claude_code.py`;
- `nirmaan/org/knowledge.py`, `nirmaan/integrations/veritriage.py` (the
  bridge: rendering, grounding, the anthropic provider),
  `nirmaan/evals/runner.py` (the eval harness);
- `veritriage/models/ai.py` (how a prompt renders to text) and
  `veritriage/ai/grounding.py` (which citations survive).

Any edit to one of them, even a comment, changes the fingerprint, and the
trials are run again: on purpose, so a harness change is never missed. File
bytes are hashed, not a parse tree, because the parse tree differs between
the Python versions CI runs (3.11 and 3.12) and the fingerprint must not.

The other runtime files are not harness code, and the test says why:
`__init__.py` (re-exports), `loop.py` (the drive loop; an eval seat runs
through `run_task` alone), `tools.py` (the tool broker; every tool run is
recorded on its own) and `writer.py` (the concurrency writer, which keeps
state in the same order for any number of jobs). A new runtime file must be
put in `CODE` or in that list, and those four files may not gain a constant.

## The fingerprint

`harness_sha256(attempts=None, knowledge=True, cli=None)` is the sha256 of
`fingerprint()`: format, version, every setting by name and value, the code
digests, and the run's own options (an `eval run --attempts` override,
whether the seat was given its knowledge documents, M67, and `cli`, the
version of the command-line program the runtime calls the model through).
With no options it is the current default harness.

`cli` is the Claude Code version on the claude-code runtime and None on every
other. The runtime asks `claude --version` once per seat runtime, so once per
trial (`ClaudeCodeLLM.cli_version`), before the seat runs; the trial records
it as `EvalResult.cli` and it is in the harness on the result and on every
answer. A version that cannot be read is recorded as `unknown`.

Every eval trial records it: `EvalResult.harness` and `RecordedAnswer.harness`
on each answer, written by `record_trial` and `evaluate`, with `EvalResult.cli`
beside it. A record written before this milestone has neither.

## How levels use it

`practised()` groups trials by skill, model, skill digest, harness and CLI
version. A trial's harness is the one on its result when every answer records
the same one; otherwise it has none. Each group in `capability/levels.json`
shows its `harness` and `cli`, and:

- a group whose harness is not the current default at the group's own CLI
  version (`harness_sha256(cli=...)`) is stale ("stale: the harness changed
  after these trials") and never counts, as a group whose skill
  digest changed is stale. A run with `--attempts` (any value, even 1: the
  override is recorded as given, since what it changes depends on the stage)
  or without knowledge is a different harness, so it never pools with the
  default;
- a group with no harness ("harness not recorded") never counts. No live
  record exists yet (only replays, which never count), so nothing is lost;
- trials on two Claude Code versions have two harnesses, so they are two
  groups, like trials on two models, and never pool. A version edited on the
  trials no longer matches the harness it entered, so the group is stale; a
  group whose version is `unknown` never counts.

Five trials under one harness and three under another are two groups, never
eight trials. Knowledge levels come from check records, not trials, and are
unchanged.

## Changing the harness

Change the setting in `harness.py` (or the code in a `CODE` file), say so in
the pull request, and regenerate `capability/levels.json`
(`scripts/capability_levels.py --write`): every Practised group from before
becomes stale, and its skills need a new batch under the new harness. This is
control plane: level computation decides what counts as evidence. The
control-plane founder class in `.github/review-teams.yml` lists `harness.py`,
`evals/levels.py` and every `CODE` file by name, so a change to any of them
gets the Founder Proxy's review. A file added to `CODE` is added to that class
in the same pull request.

## Changes to the harness since M73

- 2026-11-14, `runtime/claude_code.py`: the trial records the model asked
  for, not the first key of Claude Code's `modelUsage` (a side call on a small
  model was listed first). A `CODE` file changed, so the fingerprint changed.
  No live record existed, so no group went stale.
- 2026-11-14, gate input contracts and the CLI version, in one change so the
  fingerprint changes once:
  - `runtime/context.py`, `runtime/prompt.py`: a work prompt states, after
    each evidence requirement the platform runs over the seat's files, the
    input contract of each of its tools: every parameter the requirement
    fills, whether it takes one path or a list, whether it is required, the
    tool's own description of it, and which file kinds fill it, with "submit
    exactly one" where a one-path parameter is filled from the seat's files.
    It is generated from the tool's definition (`ToolSpec.params`, carried in
    the packet as `TaskScope.gates`) and the requirement's `FileInput`
    bindings, never written per case, so a new tool is covered with no core
    change. Cause: in the pilot's live batch, 3 of 5 rr-arbiter trials wrote
    two `.sby` files and `formal.run` and `formal.cover` refused them before
    review ("sby takes one path, not a list"); nothing the seat read said so.
    The review prompt is unchanged: a reviewer submits no files.
  - `runtime/harness.py`, `runtime/claude_code.py`, `evals/runner.py`,
    `evals/records.py`, `evals/levels.py`: the Claude Code version is a run
    option of the fingerprint (above). Cause: the CLI went from 2.1.311 to
    2.1.325, and trials from the two would have pooled.
  `CODE` files changed, so the fingerprint changed. No live record is
  committed, so no group went stale.

## What is not the harness

- The model: its own group key, recorded on the trial. The program the
  runtime calls it through is the harness: its version is a run option. On the claude-code
  runtime it is the model asked for when Claude Code reports it, never the
  first key of `modelUsage` (`docs/LIVE_EVAL_EVIDENCE.md`).
- The skill card and knowledge document: the skill digest (M58).
- The case and its judges: the case digest, checked by `rejudge`.
- The tools a seat or a judge runs: each run is recorded with its tool.
- Limits a workflow stage or capability sets: company data. Today none sets
  attempts or review rounds; one stage sets retries, which only the owner's
  reported failures use.

## Tests

`tests/test_harness.py`: every constant in `harness.py` is a setting in the
fingerprint; no other module defines one; every runtime file is harness code
or says why not, and those that are not hold no new constant; the code reads
the cap, the limits, the excerpt bounds and the timeout from the harness;
changing any one setting, or any byte of any code file, changes the
fingerprint, and so do the run options; a recorded trial carries it on its
result and every answer. `tests/test_capability_levels.py`: a group that
counts goes stale when one setting changes (the must-fail); two harnesses
make two groups and only the current one counts; a run option other than the
default is stale; no harness recorded, or a result and an answer that
disagree, never counts. `tests/test_review_teams.py`: `harness.py`,
`evals/levels.py` and each file in `CODE` (read from `CODE`, so a new entry
is checked too) is listed in the control-plane class, and a change to it is
classified control-plane.

Since M73: `tests/test_harness.py` also checks that the CLI version is a run
option; `tests/test_nirmaan_claude_code.py`, with fake `claude` executables
reporting 2.1.311 and 2.1.325, that the version is read, asked once per seat
runtime, and in the harness of every trial and answer, two versions making two
harnesses; `tests/test_capability_levels.py` that two versions are two groups
never pooled, an edited version is stale and an unread one never counts;
`tests/test_gate_contracts.py` that the rr-arbiter seat is told each proof
gate takes one `.sby`, that every planned seat gets a contract for every gate
tool its stage runs, that every gate tool declares the parameters its files
fill, and that a new tool gets its contract with no core change.

## Not in this milestone

No model call and no record. Named harness variants (`--harness <name>`) to
compare two harnesses on the same cases are a later milestone.

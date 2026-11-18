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
| `DEFAULT_LIMITS` | attempts 1, review rounds 1, retries 1, retry then escalate | the limits when no override, stage or capability sets one (M48); an eval seat's attempts come from the run instead (the default variant sets 3 since H3, below) | `work/limits.py` |
| `SCOPES` | Company, Domain, Project, Task | the prompt's sections, in this order (M20) | `runtime/prompt.py` |
| `WORK_SYSTEM`, `REVIEW_SYSTEM` | the system prompts, with the answer formats | every work and review prompt | `runtime/prompt.py` |
| `REPAIR_AFTER_REVIEW` | "Repair after review: submission N was sent back ..." | the work prompt after a review sent it back (M27) | `runtime/prompt.py` |
| `REPAIR_AFTER_REFUSAL` | "Repair: your previous attempt N was refused ..." | the work prompt after a refused attempt (M26) | `runtime/prompt.py` |
| `EXCERPT_LINES`, `EXCERPT_WIDTH` | 20 lines, 240 characters | the failed run's log excerpt on a retry (M26) | `runtime/files.py` |
| `EXCERPT_NOTABLE` | error, warning, fail, fatal, assert, mismatch | which log lines that excerpt shows first | `runtime/files.py` |
| `CLAUDE_CODE_TIMEOUT` | 1,800 seconds | one Claude Code answer (M33) | `runtime/claude_code.py` |
| `CLAUDE_CODE_FLAGS` | `--output-format json --tools "" --no-session-persistence --strict-mcp-config --safe-mode` | JSON out, no tools, no session, no MCP servers, no user-level instruction file, hook, skill or plugin (M74, intended; unverified until the canary's output is committed) | `runtime/claude_code.py` |
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

G3 (council record 2026-11-17, decision 2; fact 10): `context.py` also carries
a customer document for one task. Task memory `document.<name>` (`<digest>
<path>`) enters that task's packet as an upstream file of kind
`customer_document`, marked as customer input (not as approved by the
organization), read whole only while its bytes match. `prompt.py` makes it
citable as a `document`, never as an artifact, so no draft derives from a
record the engine does not hold. Only the whole-flow runner (part 4b,
`evals/flow.py`) writes a `document.` key, to give a stage its case's fixed
documents: seat answers write no memory, and the CLI and the single-seat eval
runner write only `input.` keys. No single-seat case gives one, so every
shipped case's seat prompts are byte for byte as before
(`tests/test_flow_requirements_document.py`). The change touched two `CODE`
files, so every fingerprint changed. It is the second half of the window
decision 4 of the council record allows: the dispatch edit merged as ip#330
(merge commit 91cb482); the gate WF1 status is in `docs/WHOLE_FLOW.md`, "Gate
status".

## The tool definitions (M74)

A seat reads its gate tools' parameter descriptions as their input contract
(below, "Changes to the harness since M73"), so the tool catalog is harness
too, though it is company data, not code (`src/nirmaan/company/tools.py`). The
fingerprint carries `tools`: each tool's ID and the sha256 of its definition
(name, category, risk, status, description, and every parameter with its
kind, whether it is required, and its description). An edited description
changes the fingerprint; a comment in `tools.py` does not, since a comment
reaches no prompt.

## The fingerprint

`harness_sha256(attempts=None, knowledge=True, cli=None, variant="default")`
is the sha256 of `fingerprint()`: format, version (2 since M74), every
setting by name and value, the code digests, the tool digests, and the run's
own options (the attempts the run sets, from an `eval run --attempts`
override or else the variant, whether the seat was given its knowledge
documents, M67, `cli`, the version of the command-line program the runtime
calls the model through, and `variant`, the named variant the run chose,
M74). With no options it is the current default harness, whose `run`
section has said `attempts: 3` since H3.

`cli` is the Claude Code version on the claude-code runtime and None on every
other. The runtime asks `claude --version` once per seat runtime, so once per
trial (`ClaudeCodeLLM.cli_version`), before the seat runs; the trial records
it as `EvalResult.cli` and it is in the harness on the result and on every
answer. A version that cannot be read is recorded as `unknown`.

Every eval trial records it: `EvalResult.harness` and `RecordedAnswer.harness`
on each answer, written by `record_trial` and `evaluate`, with `EvalResult.cli`
beside it. A record written before this milestone has neither.

## Named variants (M74)

`nirmaan eval run --harness <name>` runs on a named variant from
`harness.VARIANTS`: the default harness with the run options the variant
sets. Council record 2026-11-14 (pilot retrospective), decision 4, chose the
variants to compare; M74 has two names and M75 adds the third:

| Name | Run options | What changes for the seat |
|---|---|---|
| `default` | attempts 3 (since H3; none before) | the default harness: a refused attempt is answered again, up to three, with the repair text (`REPAIR_AFTER_REFUSAL`) and the failed run's log excerpt (M26) |
| `attempts-3` | attempts 3 | the same seat as `default` since H3; H3's arm, kept so its records are read and re-judged as they ran |
| `tools-in-loop` | tools | M75: during its attempt the seat calls brokered lint, simulation and formal on files it passes, every call recorded and every run advisory (`docs/TOOLS_IN_THE_LOOP.md`). It sets no attempts, so its seat has the case's attempts (one), as in H3 |

The variant's name is a run option of the fingerprint, so `--harness
attempts-3` and the default are two harnesses though their seats are the
same, and `--harness attempts-3` with `--attempts` is refused (the variant
sets the attempts). On the default, `--attempts` still overrides the three:
`--attempts 3` is the default harness itself, and any other number is
another harness. An unknown name is refused before anything runs. The record's name ends in
`-harness-<name>`, and its manifest and every trial carry `harness_variant`.
A variant trial never counts toward a level: the levels generator lists it
under `variants` in `capability/levels.json`, with the name and where it is
labelled (either label is enough, as for the ablation), and M42 learning does
not read it. A variant's settings can only be run options (a test checks it),
so a setting cannot hide in the variant table; editing a variant changes its
own fingerprint and never the default's. Tools in the loop, decision 4's
other variant, is its own milestone (M75): its fingerprint adds a `loop`
section with its settings (`LOOP_SETTINGS`), the digests of the brokered
server's code (`LOOP_CODE`) and the versions of the tools it runs
(`tool_pins`), none of which is in the default's.

## The default since H3

Council record 2026-11-14 (pilot retrospective), decision 4, asked for the
default harness and its two variants to be compared in one batch, on one
commit, with the counts and the rule fixed before the first trial. That batch
(H3) planned 69 trials, one per record, every one run with `--purpose
calibration` on model claude-opus-5-5 and Claude Code 2.1.325. 66 ran to a
verdict. 3 got no model verdict (a killed process, a plan-limit stop, a
machine restart), one in each arm and all on the same frontier case; they
count as failed and none was run again. The results were read once, after
the last planned trial.

The rule, fixed before the first trial: a variant qualifies when its
frontier passes are at least the default's plus 3 (of 15) and its pilot
passes at least the default's minus 1 (of 7). With no qualifier `default`
stays; of two, more frontier passes wins, and a tie goes to `attempts-3`.

| Arm | Frontier passes (of 15) | Wilson 95 percent | Pilot passes (of 7) | By the rule |
|---|---|---|---|---|
| `default` | 10 | 0.42 to 0.85 | 6 | the baseline: the bar is frontier 13, pilot 5 |
| `attempts-3` | 13 | 0.62 to 0.96 | 6 | qualifies, at the frontier bar exactly |
| `tools-in-loop` | 10 | 0.42 to 0.85 | 7 | does not: frontier 10, under 13 |

So `attempts-3` is the default harness from this change. Plainly:

- The margin is zero: 13 against a bar of 13. One pass fewer and no variant
  would have qualified, and `default` would have stayed. The rule is a fixed
  threshold, not a significance test, and the intervals overlap. The result
  holds by the rule written before the first trial; as evidence it is weak.
- The gain is on one of the three frontier cases (default 4 of 9,
  `attempts-3` 7 of 9); the other two were already 3 of 3 on the default.
- The pilot differences (6, 6 and 7 of 7) are inside one trial. The default
  and `attempts-3` failed the same pilot check (rtl/apb-gpio: the reference
  testbench reads `DATA_IN` after reset as x, expecting 0).
- `attempts-3` used 1.27 attempts per frontier trial on average. The tools of
  `tools-in-loop` were used (4.4 brokered calls per frontier trial), and it
  still did not beat the default on the frontier.
- An arm without knowledge documents (the default, 3 frontier trials, 2
  passed) is too small to compare and is reported only.

The frontier cases are private (decision 5, gate RT8): this file cites their
pass counts only, never a case's text or records. The pilot-case records are
public, labelled calibration, and never count toward a level: they are the
`evals/results/*-claude-code-claude-opus-5-5-calibration*` records on main
(the plain, `-harness-attempts-3` and `-harness-tools-in-loop` directories,
dated 2026-11-15 to 2026-11-18).

Pre-registration claim, unverified (the pilot retrospective, council record
2026-11-14, decisions 4 and 11, rules the counts and levels before the first
trial). The H3 plan stays private, so only its fingerprint is stated. The
claim is that the sha256 of the plan file version that held the rule word for
word is `3ec7b9f1ac4ace38cfab8ad4f037cd591265f0ea547a4af464a6872dd3721af9`,
that this version was committed to the private backup on 2026-11-15T16:26Z
(UTC), and that the first trial started at 2026-11-15T20:49Z, 4 hours 23
minutes later. No committed record backs the hash or the two times, and no
seat other than the author has checked them against the private backup, so
treat them as unverified. Only the hash and the two times are stated here,
never the plan text.

What changed, and what each name means now:

- `VARIANTS["default"]` sets attempts 3, the run option `attempts-3` sets. A
  run with no `--harness` gives the seat what `--harness attempts-3` gave it
  in H3: the same settings, code and tool definitions, three attempts over the
  case's own, and the repair text with the failed run's log excerpt after a
  refusal. Its prompts are the same, prompt for prompt
  (`tests/test_harness.py`). The two fingerprints differ by the variant's name
  alone.
- A default record is still labelled `default` (no name suffix,
  `harness_variant: default`); its fingerprint says which default it ran. A
  default trial recorded before this change has the old default's harness
  (`attempts: null` in its `run` section), so it is a group of its own, stale,
  and never pools with trials on the new default.
- `attempts-3` stays a name of its own, so H3's arm is read, re-judged and
  listed under `variants` as it ran, and never counts. A new `--harness
  attempts-3` trial is the default's seat under another name and never counts
  either: run the default instead.
- `tools-in-loop` is unchanged: it sets no attempts, so its seat has the
  case's attempts (one), as in H3. It is not the new default with tools.
- `--attempts` with the default still overrides the three; any number but 3
  is another harness.
- `DEFAULT_LIMITS` is unchanged (attempts 1). It is the limit a task gets
  when nothing else sets one, in the product's own runs (`nirmaan run`, the
  drive loop). An eval seat never reads its attempts: the runner passes the
  run's attempts, else the case's (`EvalCase.attempts`, 1). H3 measured eval
  seats only, so the product's own runs keep one attempt; giving them three
  is a separate decision, since it changes how many model calls a run makes.

## How levels use it

`practised()` groups trials by skill, model, skill digest, harness and CLI
version. A trial's harness is the one on its result when every answer records
the same one; otherwise it has none. Each group in `capability/levels.json`
shows its `harness` and `cli`, and:

- a group whose harness is not the current default at the group's own CLI
  version (`harness_sha256(cli=...)`) is stale ("stale: the harness changed
  after these trials") and never counts, as a group whose skill
  digest changed is stale. A run whose attempts are not the default's (since
  H3, `--attempts` with any number but 3) or without knowledge is a
  different harness, so it never pools with the default. A default trial
  recorded before H3 has the old default's harness (`attempts: null`), so it
  is its own stale group and never pools with the new default's;
- a group with no harness ("harness not recorded") never counts. No live
  record exists yet (only replays, which never count), so nothing is lost;
- trials on two Claude Code versions have two harnesses, so they are two
  groups, like trials on two models, and never pool. A version edited on the
  trials no longer matches the harness it entered, so the group is stale; a
  group whose version is `unknown` never counts.

A whole-flow trial (M87, `docs/WHOLE_FLOW.md`) is no skill group's trial: its
label and the `whole_flow` list live in `models/evaluation.py`,
`evals/records.py`, `evals/cases.py` and `evals/levels.py`, none of them a
`CODE` file, so adding them changed no fingerprint. For a whole-flow run only,
the fingerprint's `run` section says `flow: whole` and a `flow` section digests
`FLOW_CODE` (the flow module), as `loop` is for tools in the loop.
On the default harness a whole flow gives each seated stage three attempts; the CI command has no attempts option, so a whole-flow trial in CI runs the default's three (council record 2026-11-17, third addendum, gate WF21).

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
- M74, the bundle of council record 2026-11-14 (pilot retrospective),
  decision 4, in one change so the fingerprint changes once:
  - `company/tools.py`: the `sby` parameter of `formal.run` and
    `formal.cover` says the job file is a single-task setup and that one with
    a `[tasks]` section is refused before anything runs, so the rule reaches
    the seat's input contract. Cause: the council record reports that 6 of
    the batch's 9 failed trials with documents were refused before review for
    a `[tasks]` setup, and the tool descriptions said nothing of it (fact 3).
  - `runtime/harness.py`: the tool definitions are in the fingerprint (fact
    5); the named variants and the `variant` run option.
  - `runtime/harness.py`, `runtime/claude_code.py`: `--safe-mode` in
    `CLAUDE_CODE_FLAGS`. Cause: a seat call loaded the user-level
    `~/.claude/CLAUDE.md`. No committed record yet shows that the flag
    removes the file: an earlier manual probe on Claude Code 2.1.325 is not
    recorded, so treat the effect as unverified until the canary has run and
    its output is committed. `--safe-mode` is the flag whose help names
    `CLAUDE.md`; `--bare` drops the file too but never reads the plan
    login. `scripts/claude_code_canary.py` is the check: a control call
    without the flag must quote the file, a seat call must not (it calls a
    model, so it runs by hand after a Claude Code update, not in CI).
  - `evals/runner.py`, `evals/records.py`, `evals/levels.py`, `cli.py`:
    `--harness <name>`, the labels, and the `variants` list.
  The default fingerprint changed, so every Practised group recorded before
  it is stale. The control-plane class in `.github/review-teams.yml` lists
  `src/nirmaan/company/tools.py`: an edit to a tool definition changes the
  fingerprint, so the file is reviewed as control-plane.

- M75, tools in the loop (council record 2026-11-14, decision 4, the first
  variant): `runtime/model.py` makes a session of brokered tools for an
  attempt on the `tools-in-loop` variant and drops an advisory run the seat
  names; `runtime/base.py` gives the tool handle an advisory form;
  `runtime/claude_code.py` loads the brokered server for such an attempt;
  `evals/runner.py` turns the variant on for the seat and records its calls;
  `runtime/harness.py` adds the variant, the loop settings, `LOOP_CODE` and
  `tool_pins`. `CODE` files changed, so the default fingerprint changed too,
  inside decision 4's quiet window. New runtime files `runtime/seat_tools.py`
  and `runtime/seat_tools_relay.py` are `LOOP_CODE`, in the variant's
  fingerprint only.

- G3, the whole-flow runner option, part 4a (council record 2026-11-17,
  decision 3, gates WF6 and WF7): `evals/runner.py` sends a whole-flow case
  (`flow: whole`) to its own module, `evals/flow.py`, with every argument as
  given, and refuses one with a plain message while that module is absent;
  `runtime/harness.py` adds `FLOW_CODE` and, for a whole-flow run only, `flow`
  in the `run` section and a `flow` section with the flow module's digest. A
  `CODE` file changed, so every fingerprint changed once, inside the window
  before the pull request that names the default harness. The flow module is
  not a `CODE` file: an edit to it changes the whole-flow fingerprint and
  never the default (`tests/test_whole_flow_dispatch.py`).

- H3, the default harness named (council record 2026-11-14, decision 4, by
  the rule above): `runtime/harness.py`'s `VARIANTS["default"]` sets attempts
  3, and `cli.py` lets `--attempts` override the default's attempts. No `CODE`
  file changed and no setting: the default's `run` section changed
  (`attempts: null` to `attempts: 3`), so the default fingerprint changed and
  no other did. Every Practised group was already stale (M75 and G3 changed
  `CODE` files), so no level moves. This change ends decision 4's quiet
  window (gate RT4): evidence trials run on the new default.

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

Since M74: `tests/test_harness.py` checks that every tool definition is in
the fingerprint and an edited one changes it, that seat calls run in safe
mode, the two variants and their fingerprints, that a variant sets only run
options, that a trial on a variant records its name and harness, that the
attempts variant gives the seat three attempts, and the CLI switch and its
refusals; `tests/test_capability_levels.py` that variant trials are listed
apart with the name and never count, either label being enough;
`tests/test_gate_contracts.py` that the rr-arbiter seat is told the
single-task rule and that both proof gates refuse a `[tasks]` setup;
`tests/test_claude_code_canary.py` the canary script against fake
executables (clean, leaking, never quoting) and its leak detector.

Since M75: `tests/test_seat_tools.py` shows each condition of decision 4 (the
table in `docs/TOOLS_IN_THE_LOOP.md`), and that the loop settings, the server
code and the tool pins change the variant's fingerprint and never the
default's; `tests/test_harness.py` that the loop settings are the harness
module's other constants and the server files are `LOOP_CODE`.

Since H3: `tests/test_harness.py` checks that the default sets three
attempts, that a run with no `--harness` asks the seat for three attempts and
sends it the same prompts as `attempts-3`, prompt for prompt, with the repair
text after a refusal, that the two fingerprints differ by the name alone,
that editing the default changes no other fingerprint, and that `--attempts`
still overrides the default; `tests/test_capability_levels.py` that a default
trial recorded before the change is its own stale group and never pools with
the new default's, and that `--attempts 1` is now a run option other than the
default; `tests/test_seat_tools.py` that `tools-in-loop` still sets no
attempts.

## Not in this milestone

M73: no model call and no record. M74: no record; the only model calls were
the flag probe and the canary, on a small model, and no eval trial ran.
Tools in the loop (decision 4's first variant) is its own milestone.

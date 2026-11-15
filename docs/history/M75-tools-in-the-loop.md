# Milestone 75 - Tools in the loop

Decision 4 of the council record `council/records/2026-11-14-pilot-retrospective.md`
(the first variant, "tools in the loop is its own milestone"), gate RT5, and
capability gap G2. Design: `docs/TOOLS_IN_THE_LOOP.md`; `docs/HARNESS.md`
("Named variants", "Changes to the harness since M73"). Tests:
`tests/test_seat_tools.py`, `tests/test_harness.py`.

**The gap.** The seat answered in text and the checks ran after it submitted.
The retrospective's cause tally: most failures were gate refusals whose
message named the fault, and the seat never saw it.

**The variant.** `nirmaan eval run --harness tools-in-loop`. During its
attempt the seat calls the platform's lint, simulation and formal checks
through the tool broker, on files it passes, reads each run and the log
excerpt of a failed one, and then submits. The checks on its answer's files
judge it as on every harness.

**Decision 4's conditions**, each shown by a test (gate RT5):

- brokered tools only, under the seat's role: Claude Code runs with no
  built-in tool, one MCP server (a relay that holds no tool), only that
  server's tools allowed, in `dontAsk` mode; every call runs through the
  seat's own tool handle, and the broker checks the grant, the contract and
  the probe; anything not offered is refused;
- no credential in a tool run's environment (M53's runner), and the relay
  starts with an empty environment;
- paths limited to the seat's workspace: a call passes contents, written at
  relative paths under a fresh directory in the workspace, and a screen
  refuses a file that names an outside path, includes anything but a relative
  file, uses a system task that reads or writes files or runs code, or, in a
  `.sby`, a shell line or a yosys command or engine outside a short list;
- a cap of 8 calls and 1800 seconds per attempt (model and tools together, as
  the default's timeout), a timeout being a failed attempt;
- every call recorded on the trial's result (`tool_calls`), every run in the
  sandbox marked `advisory`;
- in-loop runs advisory: an advisory run never meets a requirement, and one
  the seat lists in `tool_runs` is dropped; the platform's runs alone judge;
- the server code, its settings and the tool versions in the variant's
  fingerprint (a `loop` section), never in the default's.

**Fingerprints.** `runtime/model.py`, `runtime/base.py`,
`runtime/claude_code.py` and `evals/runner.py` are `CODE` files, so the
default fingerprint changes too. This lands inside decision 4's quiet window,
before the pull request that names the default harness; no evidence trial
runs in that window.

**Order.** It merges after M74 (the bundle, ip#249), on which it is built.

No model was called and no trial ran. The seat in every test is a mock or a
fake `claude` that speaks MCP to the real relay. Whether Claude Code loads the
server under `--safe-mode` needs one hand-run call before the variant's first
trial.

## Fix: the loop call without `--safe-mode` (M75-SAFEMODE-FIX, 2026-11-16)

The hand-run call above was made before the H3 batch (H3 plan, section 8):
with the seat's own flags, `--safe-mode` included, the seat reached no broker
(0 calls) and wrote the tool call as text; the same call without
`--safe-mode` made 1 brokered call. Claude Code 2.1.325's help says
`--safe-mode` disables MCP servers, and `--mcp-config` is one.

The variant's command now drops `--safe-mode` (`LOOP_DROPPED_FLAGS`) and adds
`--restricted` (`LOOP_ISOLATION_FLAGS`: only managed settings and
`--settings` load, so no user, project or local settings file, hook or
plugin) and `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` (`LOOP_ENV`: no CLAUDE.md
memory file), in `seat_tools.loop_command`. `--bare` stays out: it never
reads the plan login.

Only the variant changes: `seat_tools.py` is a `LOOP_CODE` file and the three
settings are `LOOP_SETTINGS`, so the default and `attempts-3` fingerprints
are unchanged and the `tools-in-loop` fingerprint changes.
`scripts/claude_code_canary.py` gains a third call, made as the variant makes
it with a one-tool server behind the real relay: it fails when that call
quotes the user-level file or makes no brokered call.


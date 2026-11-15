# Tools in the loop (M75)

Council record `council/records/2026-11-14-pilot-retrospective.md`, decision
4, chose two harness variants to compare with the default. M74 added the
switch and the second one (`attempts-3`). This milestone adds the first:
`nirmaan eval run --harness tools-in-loop`. During its attempt the seat calls
the platform's own lint, simulation and formal checks through the tool
broker, reads what they say, and then submits. Capability gap G2: before it,
the seat answered in text, the checks ran after it submitted, and it never saw
a failure before its one answer.

Code: `src/nirmaan/runtime/seat_tools.py` (the session, the screen, the socket,
broker side), `src/nirmaan/runtime/seat_tools_relay.py` (the stdio relay
Claude Code starts), and the wiring in `runtime/model.py`,
`runtime/claude_code.py`, `runtime/harness.py`, `evals/runner.py` and
`evals/records.py`. Tests: `tests/test_seat_tools.py`.

## How a call goes

```
Claude Code (the seat)  --MCP stdio-->  relay  --private socket-->  SeatTools  --ToolHandle-->  ToolBroker
  --tools ""                            no tool, empty env           caps, screen     advisory     grant, contract,
  --strict-mcp-config: one server                                    records          handle       probe, records
  --allowedTools: its tools only, dontAsk
```

1. `ModelRuntime` makes a `SeatTools` session for the attempt when the
   variant is on and the model can call tools (`takes_seat_tools`). The seat
   is offered each of the loop tools (`company/tools.py` `IN_LOOP`: lint.run,
   simulator.run, formal.run, formal.cover) that the platform runs over the seat's own files for this
   task and that its role is granted; a seat offered none gets no session.
   `LOOP_SYSTEM` is added to the work system prompt.
2. The claude-code runtime opens a private socket for the attempt, writes a
   server config naming the relay, and runs `claude -p` with the seat's
   flags (`--tools ""`, `--strict-mcp-config`, `--safe-mode`) and
   `--mcp-config <config> --permission-mode dontAsk --allowedTools
   mcp__nirmaan-broker__<tool>,...`. It serves each request in the calling
   thread until the seat answers.
3. The relay answers MCP's handshake and hands `tools/list` and `tools/call`
   to the session with the attempt's token. It holds no tool.
4. A call passes file contents. The session checks the caps, the name and
   every file, writes the files under a fresh directory in the seat's
   workspace, and runs the runtime's own check of an answer's files
   (`ModelRuntime._postflight`), restricted to the requirements that name the
   tool, through an advisory handle. The seat reads each run as
   `[run:<id>] <tool> passed|failed: <summary>`, with the bounded log excerpt
   of a failed run (M26's excerpt), and how many calls and seconds it has
   left.
5. The seat answers as usual. The platform's checks run on the files of the
   answer exactly as on every harness, and they alone judge it.

A re-judge (`nirmaan eval rejudge`) replays the recorded answers: the runs
made in the loop were advisory, so none is made again.

## Decision 4's conditions, and the test for each

Gate RT5: tools in the loop merges only with every condition shown by a test.

| Condition | How it holds | Tests in `tests/test_seat_tools.py` |
|---|---|---|
| Brokered tools only, under the seat's role; no shell, file or network tool | `--tools ""` (no built-in tool), `--strict-mcp-config` with one server, `--allowedTools` naming only its tools, `dontAsk`. Every call runs through the seat's `ToolHandle`, so the broker checks the grant, the contract and the probe. Only the `IN_LOOP` tools that the task runs over the seat's files and the role is granted are offered | `test_the_seat_is_offered_only_the_loop_tools_its_task_runs_over_its_files`, `test_a_call_outside_the_allowlist_is_refused_recorded_and_runs_nothing` (Bash, Read, Write, WebFetch, synth_run, status_read, a dotted or prefixed name, a number, nothing), `test_through_claude_code_only_the_brokered_server_and_its_tools_are_loaded`, `test_the_variant_needs_a_seat_whose_model_can_call_tools`, `test_the_default_harness_gives_the_seat_no_tools` |
| No credential in a tool run's environment | The runs go through the EDA runner, whose steps see the environment with every credential removed (M53). The relay is started by `/usr/bin/env -i` in isolated mode and imports only the standard library; a request without the attempt's token is refused | `test_no_credential_reaches_a_brokered_run`, `test_the_relay_starts_with_an_empty_environment_in_isolated_mode` |
| Paths limited to the seat's workspace, so held-out files are unreachable | A call passes contents, never a path to read. Each file goes to a relative path (`safe_path`) under a fresh directory in the seat's workspace, with a suffix of `LOOP_SUFFIXES`; the run's `workdir` is that directory. The screen refuses a file that names an absolute, home or parent path, includes anything but a relative file, or uses a system task that reads or writes files or runs code (`$system`, `$c`, DPI, `$fopen`, `$readmem*`, `$writemem*`); in a `.sby`, a section, a yosys command or an engine outside a short list (no `!` shell line, no `exec`, `tee` or `script`) | `test_a_file_that_could_reach_outside_the_call_is_refused_before_anything_runs` (18 cases, two of them the case's own held-out `.sby` by absolute path), `test_a_proof_setup_that_could_run_a_command_or_read_outside_the_call_is_refused` (11 cases), `test_every_file_and_run_of_a_call_is_inside_the_seats_workspace`, `test_the_screen_passes_every_reference_file_of_the_rtl_cases` |
| A cap on calls and time per attempt, a timeout being a failed attempt | `LOOP_MAX_CALLS` calls, refused ones counted; `LOOP_SECONDS` from the start of the attempt, model and tools together; each run's timeout the least of `LOOP_CALL_SECONDS`, the time left and the requirement's own. Past the time every call is refused and the seat is killed with its process group: the call is a failed model call and the attempt fails | `test_a_call_over_the_cap_is_refused_and_recorded`, `test_a_call_after_the_time_cap_is_refused`, `test_each_run_is_given_no_more_time_than_the_cap_and_the_attempt_allow`, `test_through_claude_code_a_seat_past_the_time_cap_is_stopped_and_the_attempt_fails` |
| Every call recorded | Each call, refused or not, is a `SeatToolCall` on the trial's result (`EvalResult.tool_calls`): attempt, number, the name asked for, its runs, passed or not, why refused, seconds. Each run is a `ToolRun` in the sandbox with `advisory` set, and an audit entry that says so | `test_the_seat_reads_its_runs_and_every_call_is_on_the_record` |
| In-loop runs advisory; the platform's gate runs alone judge | `ToolRun.advisory`: `policy.satisfies` never accepts an advisory run, and `ModelRuntime._result` drops one the seat lists in `tool_runs` before the engine sees it. The checks on the answer's files are unchanged | `test_an_advisory_run_never_meets_a_requirement_and_the_gate_alone_judges` (a passing loop run named in `tool_runs` does not carry RTL that fails lint; cited directly it meets nothing; the same run without the flag would), `test_an_advisory_run_saves_and_loads_and_a_plain_one_saves_as_before` |
| The server code and tool pins in the fingerprint | The variant's fingerprint has a `loop` section: `LOOP_SETTINGS` by value, the `IN_LOOP` tools, the sha256 of each `LOOP_CODE` file, and `tool_pins()`, the version line of every executable the loop tools' backends run | `test_tools_in_the_loop_is_a_named_variant_beside_the_default_and_attempts_3`, `test_the_server_code_changes_the_variants_fingerprint_and_never_the_defaults`, `test_each_loop_setting_changes_the_variants_fingerprint_and_never_the_defaults`, `test_the_tool_pins_are_in_the_variants_fingerprint` |

## The settings

In `runtime/harness.py`, in the variant's fingerprint only, so editing one
changes `tools-in-loop` and never `default` or `attempts-3`:

| Setting | Value | Why |
|---|---|---|
| `IN_LOOP` (in `company/tools.py`: the runtime names no tool) | lint.run, simulator.run, formal.run, formal.cover | decision 4 names lint, simulation and formal |
| `LOOP_MAX_CALLS` | 8 | per attempt, refused calls counted; fixed before any trial |
| `LOOP_SECONDS` | 1800 | the default's `CLAUDE_CODE_TIMEOUT`: the variant gets no more time per attempt than the default |
| `LOOP_CALL_SECONDS` | 300 | a run's own default timeout |
| `LOOP_MAX_FILES`, `LOOP_MAX_CHARS` | 16, 200000 | one call's size |
| `LOOP_SUFFIXES` | .v .sv .vh .svh .sby | HDL and proof setups only: no script, no memory image |
| `LOOP_SERVER`, `LOOP_FLAGS` | nirmaan-broker; `--permission-mode dontAsk` | how Claude Code knows the server, and that nothing else is allowed |
| `LOOP_SYSTEM` | the added system text | the default's `FILE_FORMAT` says the seat cannot run checks |

The variant keeps one attempt (the case's). Attempts 1 against 3 is the
other variant.

A seat stopped at the time cap leaves an answer with no text and an error,
as a seat past the default's `CLAUDE_CODE_TIMEOUT` does. The trial is
recorded as failed, and RR5's stop (`no_model_answer`) ends the run after it,
as for the default: the batch's driver then goes on from the next slot it
never attempted.

## What the screen does not claim

The screen is for files the seat passes in the loop, where the seat reads the
output. It is a list of refusals, so it is conservative: a sentence of RTL
that names `/` in a string is refused even when harmless, and the seat is told
why. The files of the final answer are not screened: they go through the
gates as on every harness. On the default harness a seat reads no tool output
before it answers.

## Not checked here

- Whether Claude Code 2.1.325 loads a `--mcp-config` server under
  `--safe-mode` can only be seen with a model call. Before the first trial
  of the variant, one hand-run call (not a trial) must show a brokered run in
  its record; until then a trial on the variant may have no tool at all,
  which its record would show as no `tool_calls`.
- No live trial ran. The seat in every test is a mock or a fake `claude`
  that speaks MCP to the real relay.

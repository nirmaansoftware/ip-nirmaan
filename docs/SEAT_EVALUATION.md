# Seat evaluation (M27)

Does a seat's work actually work? Until M27 the suite proved the *mechanism*
around model seats (grounding, gating before review, the repair loop) on
`MockLLM` answers scripted from fixture files that are correct by
construction. Nothing measured a real model in a seat, and a seat's RTL was
judged only by the testbench the seat wrote itself. M27 adds evaluation cases
as data and a runner whose judges are real tool runs.

It is the first milestone of the structural review
(`docs/architecture/target-state.md`): every later change to seats (typed
packets, model choice, prompts, repair limits, new seats) needs this yardstick.

## What a case is

A JSON file under `evals/` (`EvalCase` in `nirmaan/models/evaluation.py`):

- a **request** that plans a workflow in which the **seat** stage is one work task;
- **upstream** reference documents that stand in for the approved output of the
  seat's upstream stages, so only the seat varies between runs;
- a **reference answer**, for `--replay`;
- **held-out checks** the seat never sees, each run by a registered scorer;
- `expected_behavior`, `constraints`, and `known_failure_modes`, for people.

Four cases ship, one per block designed on `block-design`: `rtl/axi4-lite-regs`,
`rtl/apb-regs`, `rtl/sync-fifo`, `rtl/rr-arbiter`. Each evaluates the
`rtl-implementation` seat, with the block's interface specification and
microarchitecture fixed upstream, and one held-out check: the block's
reference testbench simulated on the seat's RTL. The cases reference the
M23/M26 fixtures in place rather than copying them.

## How a run works

`run_case(org, case, runtime=None, repo=..., attempts=None, sandbox=None)`:

1. Validate the case (files exist, scorers registered, the seat is one task in
   the planned workflow, upstream kinds are what those stages produce).
2. Plan the request in a sandbox. The user's `.nirmaan/` is never touched; the
   sandbox project is saved under `<sandbox>/.nirmaan/` for inspection with
   `nirmaan status --root`.
3. Fix each upstream work stage, dependencies first: submit the reference
   documents (written into the sandbox with a digest, so the seat's packet
   carries their content), review, approve. The actor is `SYSTEM` named
   `eval-fixture`, and the review text names the documents and says they were
   reviewed in the repository, not here. No human attestation is recorded.
   A gate or decision among the seat's upstream stops the run with `EvalError`:
   no fixture can stand in for one.
4. Put the runtime in the seat through the unchanged `run_task` (its gates,
   grounding, and repair loop all apply). `runtime=None` replays the case's
   reference answer through `ReplayLLM`, a network-free LLM that answers with
   fixed files and cites whatever approved artifacts its prompt offers.
5. Judge. A held-out check runs only if the work reached review. The scorer
   gets the seat task and a tool handle bound to a `SYSTEM` actor named
   `eval-scorer` in the owner's role, so every judgement is a `ToolRun` the
   broker recorded.
6. Record an `EvalResult`: case, case digest, runtime, replay flag, version,
   start time, duration, seat status, attempts, the seat's own gate runs,
   scores, `passed`, detail, audit-chain check, sandbox path.

A case **passes** only when the work reached review and every held-out check
passed.

## Honesty rules

- **A pass is a recorded run.** The runner turns a scorer's `passed` into
  `failed` unless it cites runs recorded in the sandbox that all succeeded
  (`test_a_pass_needs_a_recorded_run`).
- **Not run is not a pass.** A tool the broker refuses (not granted, not
  installed, contract only) gives `not_run` with the broker's reason.
- **Replay is labelled.** `replay: true` and runtime `replay` mark results of
  the case's own reference answer; they prove the case, not a model.
- **The case digest** is SHA-256 over the case and every file it names, so a
  result is tied to exact inputs.

## Scorers

`register_scorer(id, requires_tool=False)` is the extension point, with
`unregister_scorer` and `available_scorers`. One ships: `held-out-run`,
which runs the check's `tool` with its `params`, filling each parameter from
the seat's submitted files of the kinds in `seat_files`, then the case's
`case_files`, comma-joined as every tool parameter is today (typed parameters
are M28). The runner and scorers name no stage, tool, artifact kind, or role
(`test_the_runner_names_no_stage_tool_kind_or_role`).

## CLI

```
nirmaan eval list [--cases evals]
nirmaan eval run [CASE...] (--runtime ID | --replay) [--attempts N] [--cases DIR] [--repo DIR] [--out DIR] [--json]
```

Exactly one of `--runtime` and `--replay`. Results go to
`.nirmaan/evals/<runtime>/<case>.json`; the command exits 1 when any case
fails. `--runtime anthropic` is the live path (the `ai` extra and credentials);
the suite never takes it.

## What the tests prove

`tests/test_nirmaan_evals.py` (15):

- every shipped case is valid; an invalid one is reported, not run;
- replaying each block's reference answer passes, with real lint, simulation,
  synthesis, and formal as the seat's gates and the reference testbench as the
  judge (about a second per case locally);
- **what the gates miss, the held-out check catches**: RTL with `reg3` reset to
  all ones, submitted with a testbench that only resets the block, passes its
  own lint, simulation, and synthesis and reaches review; the reference
  testbench fails it;
- an unusable model answer fails the case with the reason and no scores;
- a check the broker refuses is `not_run`;
- a scorer's unbacked pass is recorded as failed;
- a gate before the seat stops the run;
- the sandbox is separate and the result says what ran; the same inputs give
  the same case digest;
- crown jewel `test_a_new_case_or_scorer_needs_zero_core_changes`: a scorer
  registered in the test and a case written in the test run through
  `nirmaan eval run`;
- the CLI refuses an unclear request, and a failing case exits 1.

## First live results (2026-10-09)

Claude Opus 5.5 in the `rtl-implementation` seat, through the `claude-code`
runtime (`docs/CLAUDE_CODE_RUNTIME.md`) on the owner's Claude plan, one attempt
per case:

| Case | Own gates | Held-out judges | Output tokens | Time |
|---|---|---|---|---|
| `rtl/axi4-lite-regs` | lint, simulation, synthesis passed | 2/2 (reference testbench; register map, 25 bus transfers) | 29,205 | 246 s |
| `rtl/sync-fifo` | lint, simulation, synthesis passed | 1/1 | 19,071 | 167 s |
| `rtl/rr-arbiter` | lint, simulation, synthesis passed | 1/1 | 21,431 | 195 s |
| `rtl/apb-regs` | lint, simulation, synthesis passed | 1/1 | 12,854 | 114 s |

Cost is recorded as unknown: a subscription has no per-call price. No formal
proof ran: the model wrote no `.sby`, and on `block-design` formal applies only
when one is produced.

**What the first run found.** Before this, the AXI4-Lite case failed both
judges with RTL that passed its own lint, simulation, and synthesis: the model
named its ports `awaddr` instead of `s_axil_awaddr` and had no `DATA_WIDTH`.
Those names are in the interface spec, and the RTL seat never saw it: its stage
depended only on the microarchitecture. The stage now depends on both, and the
same case passed. Scripted answers could never have shown this; a held-out judge
on a real model did, which is what this milestone was for.

## Limits and what comes next

- The reference testbench encodes the fixture's choices (SLVERR on unmapped
  addresses, one-cycle latency). The upstream documents given to the seat
  state them, so a seat that ignores them fails, as intended. Each case lists
  this under `known_failure_modes`.
- Deferred: token and cost accounting per call (M31), mutation scoring of the
  seat's own testbench, held-out formal proofs, cases for the specification
  seats (no deterministic judge yet), and planning cases (planning is
  deterministic and covered by the orchestrator tests).

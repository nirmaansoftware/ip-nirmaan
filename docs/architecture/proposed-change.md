# Proposed change: M27, seat evaluation

The first milestone of the structural review (`target-state.md` section 5).
This is the design to implement; the milestone's design doc
(`docs/SEAT_EVALUATION.md`) is written from it when the code lands.

## 1. Current architecture (the part this touches)

A model seat is a `ModelRuntime` filled by an `LLM`. `run_task` hands it a
`WorkPacket`, and its answer goes through the engine: files are written with a
digest, the task's before-review checks (lint, simulation, synthesis, formal)
run on those files through the `ToolBroker`, and the submission is refused
unless they pass. Tests prove this mechanism on `MockLLM` answers scripted
from the fixture files, which by construction are correct. Nothing runs a
seat on a real model and records how well it did, and nothing checks a seat's
RTL with anything but the testbench the seat wrote itself.

## 2. Proposed architecture

An **evaluation case** is data: a request, the seat under evaluation, the
reference documents that stand in for its approved upstream, a reference
answer (for replay), and **held-out checks** the seat never sees. An
**evaluation run** plans the request in a sandbox, fixes the upstream to the
reference documents, puts a runtime in the seat, runs it through the
unchanged `run_task`, then runs the held-out checks through the broker and
writes an **evaluation result** record.

```
evals/rtl/<case>.json  --load-->  EvalCase
                                     |
          sandbox ProjectStore       v
  Orchestrator.plan(request) -> upstream stages fixed to reference documents
                                     |
                                     v
             run_task(seat, runtime)            (unchanged: gates, grounding, repair)
                                     |
                                     v
             held-out scorers (registry) -> ToolBroker runs -> Score
                                     |
                                     v
             EvalResult JSON  (runtime, replay or live, duration, attempts, gate runs, scores)
```

The judge is always a deterministic tool run the broker recorded, never model
text. A case passes only when the seat's work reached review (its own gates
passed) **and** every held-out check passed.

## 3. Affected components

| Component | Change |
|---|---|
| `src/nirmaan/models/evaluation.py` | **New.** `EvalCase`, `CaseFile`, `HeldOutCheck`, `Score`, `ScoreStatus`, `EvalResult`. Pydantic only (the models law). |
| `src/nirmaan/models/__init__.py` | Export the new types. |
| `src/nirmaan/evals/` | **New package.** `cases.py` (load and validate case files), `scorers.py` (`register_scorer`, one built-in scorer `held-out-run`), `runner.py` (sandbox, upstream fixing, seat run, scoring, result). Names no stage, tool, kind, or role: all of those come from case data (a test reads its string constants). |
| `src/nirmaan/cli.py` | **New commands** `nirmaan eval list` and `nirmaan eval run [CASE...] (--runtime ID | --replay) [--attempts N] [--out DIR] [--json]`. Exit 1 when any case fails, like `nirmaan gaps`. |
| `evals/` | **New.** `evals/README.md` and four RTL cases, one per shipped block (AXI4-Lite and APB register blocks, FIFO, arbiter), each referencing the existing fixtures rather than copying them. |
| `tests/test_nirmaan_evals.py` | **New.** See section 7. |
| Engine, policy, runtime, workflows, integrations | **No change.** |

## 4. New abstractions

- **`EvalCase`**: `id`, `request`, `seat` (a stage ID of the planned
  workflow), `expected_behavior`, `constraints`, `known_failure_modes`,
  `upstream` (stage ID -> reference `CaseFile`s: path, kind, entry),
  `reference` (the reference answer's files, for replay), `held_out`
  (`HeldOutCheck`s), `attempts` (default 1). Paths are relative to the
  repository root.
- **`HeldOutCheck`**: `scorer` (a registered scorer ID), `name`, and
  `params`. For the built-in `held-out-run` scorer, `params` name a `tool`,
  fixed tool parameters, `seat_files` (tool parameter -> artifact kinds from
  the seat's submitted files), and `case_files` (tool parameter -> case
  paths). Example: simulate the seat's `rtl_source` with the reference
  testbench, top `axi4_lite_regs_tb`.
- **`Score`**: scorer, name, status `passed` / `failed` / `not_run`, summary,
  tool-run IDs. `not_run` (tool missing, or the seat submitted no file of the
  needed kind) never counts as a pass.
- **`EvalResult`**: case ID, case digest (SHA-256 over the case file and
  every file it references, so a result is tied to exact inputs), runtime
  ID, `replay` flag, Nirmaan version, start time, duration, seat status,
  attempts used, the seat's gate runs (tool, succeeded), held-out scores,
  `passed`, detail, and whether the sandbox audit chain verified.
- **Scorer registry**: `register_scorer(id)(fn)`, `unregister_scorer`,
  `available_scorers`, the same shape as every other extension point. A
  scorer receives the engine, the seat task, the check, the repository root,
  and a broker handle bound to an evaluation actor, and returns a `Score`.

## 5. Honesty rules for evaluation

1. Every score is backed by a `ToolRun` the broker recorded in the sandbox
   project. A scorer cannot return `passed` without one.
2. A tool the machine cannot run gives `not_run` with the broker's reason;
   the case does not pass.
3. The sandbox is a fresh `ProjectStore` under a temporary directory. The
   user's `.nirmaan/` is never read or written.
4. Upstream stages are fixed to the case's reference documents by an actor
   of kind `SYSTEM` named `eval-fixture`, whose review comments name the
   fixture paths. No human attestation is recorded and no human gate is
   passed: if a human gate precedes the seat, the run stops with an error.
5. Replay results carry `replay: true` and the reference-answer source, so
   they can never be mistaken for a model's results.

## 6. Migration strategy

Purely additive. No existing module changes behaviour, no stored project
changes schema, and no test changes. `nirmaan eval` is new. The four cases
reuse the M23 and M26 fixtures in place.

## 7. Testing strategy

Test first (`tests/test_nirmaan_evals.py`), then the code:

1. Every shipped case loads, its files exist, its seat is a stage its request
   plans, and its scorers are registered (no tools needed).
2. Replaying the reference answer scores every held-out check `passed` for all
   four blocks (real Verilator, Icarus, Yosys, SymbiYosys; skipped without
   them, required in CI through `NIRMAAN_REQUIRE_EDA`).
3. **What the gates miss, the held-out check catches**: a seat answer whose
   RTL has a bug its own weak testbench does not exercise reaches review, and
   the reference testbench fails it; the case fails.
4. A model that answers with nothing usable fails the case with a reason and
   no `passed` score.
5. A held-out tool missing from PATH gives `not_run` with the broker's reason.
6. The sandbox leaves the working directory's `.nirmaan/` untouched; the
   result file carries the runtime ID, replay flag, and case digest.
7. The runner names no stage, tool, artifact kind, or role (string-constant
   test, like the orchestrator's).
8. Crown jewel `test_a_new_case_or_scorer_needs_zero_core_changes`: a scorer
   registered in the test and a case written to a temporary directory run
   through `nirmaan eval run`.
9. CLI: `eval list`, and `eval run --replay` on one case with exit codes.

The full suite must stay green (baseline: 1115 passed, 2 skipped).

## 8. Risks and trade-offs

- **Held-out testbench as judge.** A reference testbench encodes the fixture's
  choices (for example SLVERR on unmapped addresses, one-cycle latency). A
  live model that makes a different but valid choice fails. Mitigation: the
  upstream interface spec and microarchitecture given to the seat state those
  choices, so the judge only checks what the seat was told. Case files list
  this under `known_failure_modes`.
- **Port-name coupling.** The reference testbench instantiates the module by
  name and ports. The interface spec fixes both, so a seat that ignores the
  spec fails, which is the intended result.
- **CI time.** Four replays with formal add roughly the cost of the existing
  four end-to-end block tests.
- **Live runs cost money** and are never run by the suite; `--runtime
  anthropic` is opt-in and needs credentials.
- **Scope held back**: token and cost accounting (M31), mutation scoring of
  the seat's testbench, evaluation of the specification seats (no
  deterministic judge exists yet), and planning evaluations (planning is
  deterministic and already covered by tests).

## 9. What will not change

The task engine, constitution, policy checks, runtime, prompt, grounding,
repair loop, tool broker, EDA backends, workflows, vocabulary, export,
engineering graph, MCP, VeriTriage, and every existing test.

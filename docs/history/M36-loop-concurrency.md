# Milestone 36 - Concurrent tasks and a project wide call budget in the unattended loop (after Stage 6)

Post-roadmap work that builds two items M29 deferred. Design doc: `docs/LOOP_CONCURRENCY.md`. No version bump.

Key design points worth not re-deriving:
- **One writer, turns in plan order.** In project mode the tasks with a seat
  step form a batch (all actionable, so their dependencies are terminal and
  none depends on another). A batch of more than one runs a thread per task
  under `nirmaan.runtime.writer`: a thread reads or writes state only while it
  holds the turn, and gives it up only around `outside_writer()` (which
  `ModelRuntime._ask` puts around `llm.complete`) and when its task stops. The
  turn passes to the next unfinished task cyclically and waits for it, so the
  segment order, and with it every counter ID and audit hash, is a function of
  the batch alone. `--jobs` is the number of call slots; a slot is taken while
  the turn is still held, so `--jobs 1` is strictly sequential in turn order.
  A shared ordered script (one MockLLM script for several tasks) is
  reproducible only at `--jobs 1`; prompt-driven answers at any `--jobs`.
- **Tools, file writes, and saves stay inside the turn.** Bindings get the
  engine and may read it (`status.read` does), and `_attempt_dir` picks a
  directory by an exists check, so neither may race. Parallel tool runs are
  deferred.
- **Runtimes are shallow copied per task** in a concurrent batch (`private`),
  so `ModelRuntime`'s per-call `_calls` and `_purpose` stay with one task.
  A runtime that never calls `outside_writer()` just runs its tasks in turn.
- **Errors:** a failing step raises in its own turn; the other tasks finish
  the step in hand (so a call already made is recorded), see `stopping()`,
  and the first error in batch order is raised. Ctrl-C does the same.
- **The budget lives on the audit trail.** `TaskEngine.set_budget` (person
  only, reason required) appends `budget.set` with the new and previous
  limits; `nirmaan.work.budget.budget(state)` reads the latest. Spend is the
  recorded `ModelCall`s (M31), from any command. Before a step its worst case
  must fit `calls` minus the spend minus what in-flight steps may still make;
  a cost limit stops new steps once reached, and a call of unknown cost stops
  it (never free). The stop is `Stop.PROJECT_BUDGET` with a `loop.stop` entry
  (`record_step` gained an `action` limited to `loop.*`).
- `nirmaan drive ... --jobs N`; `--dry-run` adds the concurrent batch and the
  budget impact (`plan.concurrent`, `plan.project_budget`, `plan.spent`);
  `nirmaan budget PROJECT [--calls N] [--cost-usd X] [--clear] --as ROLE
  --reason TEXT`, or no limits to show the budget and spend.

`tests/test_nirmaan_loop_concurrency.py` (14), crown jewel
`test_a_new_runtime_on_a_new_workflow_runs_concurrently_with_no_core_changes`.

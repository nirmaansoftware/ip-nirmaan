# Milestone 26 - The repair loop (post-roadmap)

When a seat's submission is refused (a before-review check failed on its
files), `run_task` may ask the same seat again, bounded, handing it the failed
runs as citable evidence with a log excerpt. Off unless configured: a
capability's `max_attempts` defaults to 1 and no shipped capability sets it;
`run_task(..., attempts=N)` and `nirmaan run --attempts N` override per run.

Key design points worth not re-deriving:
- **The loop lives in `run_task`** (`runtime/base.py`) and names nothing. Only
  a constitution refusal at `engine.submit` starts another attempt; `blocked`
  (the broker refused a tool), `declined`, an escalation, and a P5 raise end it
  as before. With a limit of 1 no `Attempt` is recorded: state and audit are
  exactly M23's.
- **A refused attempt is an `Attempt`** (`models/work.py`, stored in the new
  `ProjectState.attempts`, ID `<task>#t<n>`), written only by
  `TaskEngine.record_attempt` and audited as `task.attempt`. Its files are full
  `Artifact` records held inside it, never in `state.artifacts`, so review,
  verification, approval, export, and the engineering links cannot see them.
  M23's per-attempt directories (`<workspace>/<task>/<n>/`) keep the bytes.
- **The repair prompt** (`prompt._repair`, work mode only): every refused
  attempt's reason; the latest one's failed runs with run and evidence tokens
  (already citable, since `run_task` recorded them as evidence), a log excerpt
  (`files.excerpt`: the run's first reference, notable lines first, at most 20
  lines of 240 characters), and its files, digest-checked.
- `evidence-before-review` is unchanged; a test hand-submits a refused
  attempt's files after an earlier attempt's lint passed and is refused with
  "no passing run ... covers".

`tests/test_nirmaan_repair.py` (10 tests): lint repaired to review; the repair
prompt's tokens and excerpt; limit 1 unchanged; exhaustion lists and audits
every attempt; broker refusal is blocked with one model call; CLI `--attempts`
with the SDK import poisoned; a firmware seat repaired from the wrong register
map to the fixture driver; crown jewel `test_a_new_check_gets_repair_with_no_core_changes`
(a capability with `max_attempts=2` and a `units.check` tool bound in the
test); the runtime names no seat or tool. Design doc: `docs/REPAIR_LOOP.md`.

Deferred: repair after a reviewer's `request_changes`, a per-stage limit, a
budget shared across separate runs, and file-level signoff evidence.

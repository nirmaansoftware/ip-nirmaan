# Milestone 29 (engineering records) - Decisions and failures, as views (structural review, milestone 3)

The third structural-review milestone, a part of the M29 batch.
"Why did we choose this?" and "what went wrong, and was it fixed?" answered
from the record. Design doc: `docs/ENGINEERING_RECORDS.md`. No version bump.

Key design points worth not re-deriving:
- **Views, not new fields.** Inspection found that nothing in the product calls
  `record_decision`: the decisions made are DECISION tasks, which already hold
  every decision-record field (outcomes as alternatives, outcome, artifacts as
  rationale, evidence, `task.submit`/`task.approve` audit entries, and the
  branches `_take_branch` cancelled as consequences). M27's review repair
  already moves superseded artifacts into an `Attempt`. So
  `nirmaan/records.py` reads state and stores, infers, and audits nothing.
- **Failure categories come from structure, never prose**: `check_failed` (a
  failed `ToolRun`; resolved by a later successful run of the same tool on the
  same task), `review_sent_back` (an `Attempt` with reviews), `submission_refused`
  (an `Attempt` with no failed run of its own), `blocked` (`task.block`,
  resolved by `task.unblock`), `failed` (`task.fail`), `escalated` (an
  `Escalation`, resolved with its resolution). Ordered by audit sequence.
  `failure_summary(states)` counts by category and subject across projects.
- Surfaces: `nirmaan decisions PROJECT`, `nirmaan failures PROJECT...` (both
  `--json`), export sections `decisions` (in `10_signoff`) and `failures` (in
  `09_evidence`) through the section-writer registry and the folder table, and
  MCP read tools `decisions` and `failures`.
- The records-names-nothing test leaves platform tools out of its vocabulary:
  `task.cancel` and `escalation.raise` are both platform tool IDs and the
  engine's audit actions.
- Two projects planned from the same request under a fixed clock share an ID;
  the cross-project test uses two requests.

`tests/test_nirmaan_records.py` (10), including Demo 4's `root-cause` decision
(four alternatives, `rtl_bug`, three cancelled branches) and the crown jewel
`test_a_new_decision_stage_is_recorded_with_no_core_changes`. With the M29 loop merged,
the standard local run is 1260 passed, 3 skipped. Deferred: recording explicit decisions
from the CLI or MCP, declined model answers (the engine records nothing for
them), principle IDs on refusals, learning from the summary.

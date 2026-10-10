# Milestone 40 - Recording explicit decisions from the CLI and over MCP (after Stage 6)

Closes the M29 engineering records deferral. Design doc:
`docs/DECISIONS_CLI_MCP.md`. No version bump.

Key design points worth not re-deriving:
- **One engine call per surface.** `nirmaan decide PROJECT TEXT --as ROLE
  --kind KIND --criticality LEVEL [--subject Q | --task STAGE] [--option ...]
  [--evidence ID ...] [--rationale R] [--supersedes dec-N] [--agent]` and the
  MCP action `record_decision` both call `TaskEngine.record_decision`; one
  `decision.record` audit entry, whose details now always carry
  `criticality`, plus `options` and `supersedes` when given.
- **`Decision` gains `subject`, `options`, `supersedes`** (all defaulted, so
  saved projects load). Superseding is a WorkError unless the old decision
  exists, is not already superseded, has the same kind, and the new
  criticality is no lower; the old decision is never edited.
- **Agents versus people is data:** `AuthorityRule.human_required`, set by the
  matrix's `human_from` column in `company/governance.py`. Gate approvals,
  waivers, and releases always need a person; every critical decision does;
  the rest an agent may record with its role's authority. Enforced by the new
  P12 check `human-decisions` in the engine, so it holds for the CLI's
  `--agent` too, not only MCP.
- **P2 tightened by one line:** a cited evidence ID must exist at every
  criticality. A low or medium decision may still cite none.
- **Views:** `DecisionRecord` gains `kind`, `criticality`, `supersedes`,
  `superseded_by`; a recorded decision's question is its subject, else its
  task's title, else its statement; alternatives are its options; status
  `superseded` once replaced. The export prints both links.

`tests/test_nirmaan_decisions_cli_mcp.py` (13), crown jewel
`test_making_a_decision_human_only_is_one_row_of_data`.

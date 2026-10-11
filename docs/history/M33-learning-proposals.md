# Milestone 33 - Learning proposals: recurring failures propose, a person decides

The seventh and last structural-review milestone . Design doc: `docs/LEARNING_PROPOSALS.md`. No version bump.

Key design points worth not re-deriving:
- **A view over failure records (M29)**, never a writer: `learning_proposals(org,
  states)` runs a registry of rules (`register_proposal_rule`) over every
  project's `failure_records`. Two ship: `recurring-check-failure` (one tool
  failing work of one capability in at least `MIN_TASKS` = 2 different tasks ->
  a failure mode and a procedure) and `recurring-review-send-back` (reviews
  sending one capability's work back in two tasks -> a validation criterion
  quoting the reviewers). Targets are the skills that provide the capability
  (`org.providers_of`). The ID hashes rule, capability, and subject, so it is
  the same proposal as evidence grows; every proposal cites every record.
- **Deciding is a recorded human decision**: `decide_proposal` refuses any actor
  that is not human, refuses a project the proposal does not rest on, and calls
  `TaskEngine.record_decision` (cross-team, medium: the authority matrix
  requires a manager or above). It shows in `nirmaan decisions`; a proposal's
  status is the latest such decision across the projects read.
- **Adopting edits no skill.** Skills are company data in
  `company/skills.py`; an adopted proposal is the reviewed reason for a person's
  pull request. No new workflow was added: the landing-site tests tie the
  public page's workflow count to the organization, so a workflow would have
  changed the live site.
- `nirmaan learn PROJECT... [--json]`; `--decide ID --in PROJECT --as ROLE
  (--adopt | --reject) --reason TEXT`.

`tests/test_nirmaan_learning_proposals.py` (9), crown jewel
`test_a_new_proposal_rule_needs_no_core_changes`. The standard local run is
1424 passed, 3 skipped.

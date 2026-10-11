# Milestone 50 - Constitution hardening

Audit A of v1.24.0 found the product's claim (nothing is verified or approved
without substantiated evidence and the right authority) broken in the engine
and policy layer. This milestone closes the findings assigned to it: C2, M1,
H1, L2, and M2. Design: `docs/CONSTITUTION_HARDENING.md`. Tests:
`tests/test_nirmaan_constitution_hardening.py`, one per audit probe, written
first and failing on v1.24.0.

**Evidence is about this task and this submission (C2).** P5 refuses a tool
run made for another task; the model runtime drops such runs a model names
(the mock model named every upstream run its prompt cited). A review that sends
work back now takes the submission's evidence with its files onto the
superseded `Attempt`, and a refused M26 attempt does the same, so neither can
verify a later submission; evidence IDs keep counting. DOCUMENT evidence
counts only for an approved artifact of another task, and REVIEW_RECORD only
for an approval of this task's current submission.

**A tool run is recorded only through the broker (M1).** `record_tool_run`
requires `BROKER_SEAL`, which only `runtime/tools.py` imports (a law test), and
refuses a run ID already recorded.

**The authority matrix's `human_required` holds for actions (H1).** The P12
check `human-decisions` now also covers approving work, signing a gate, and
cancelling a task, at the task's criticality: every gate and all critical work
is a person's. No constitution data changed, so project IDs are unchanged.

**One MCP session is one role.** The role configured at launch
(`nirmaan mcp --role`, `NIRMAAN_MCP_ROLE`), else the first role an accepted
action uses; any other role is refused. One client can no longer own, review,
and approve the same task.

**Escalating needs a stake (L2), completing needs output (M2).** Only the
task's owner, reviewer, approver, escalation path, management chain, a past
reviewer, or an escalation target on it may escalate it. P4 refuses completing
a work or decision task with no artifacts, or a decision with no outcome.

**Flows that relied on a hole.** `regression-investigation/change-correlation`
gains an independent review (its `documented(...)` requirement was met only by
the owner's own artifact). The test helper `drive` approves and signs gates as
a person and no longer cites the task's own document. MCP tests open one
session per role (`nirmaan_helpers.mcp_session`), and the MCP gate approval
test now shows the refusal.

**Deferred.** `--auto-gate` and MCP `auto_gates` no longer let an agent sign a
gate, but removing them waits for the parallel persistence work on the plan
command. The other audit A findings are outside this milestone.

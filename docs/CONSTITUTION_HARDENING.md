# Constitution hardening (M50)

The product's claim is that nothing is marked verified or approved without
substantiated evidence and the right authority. Audit A of v1.24.0 found that
claim broken in several places: evidence that said nothing about the submitted
files still verified them, a tool run nobody executed could be recorded, an AI
agent could approve critical work and sign any gate, and one MCP client could
own, review, and approve the same task. This milestone closes the holes the
audit assigned to the engine and policy layer: C2, M1, H1, L2, and M2.

Every fix is in the task engine (`work/engine.py`), the policy checks
(`work/policy.py`), or the broker the engine trusts (`runtime/tools.py`), so
the CLI, MCP, the runtimes, and the auto loop all get it. The one fix outside
that layer is MCP session identity (section 4), which is about who the caller
is, not what the engine allows. Tests: `tests/test_nirmaan_constitution_hardening.py`,
written first; every test in it failed on v1.24.0.

## 1. C2: evidence is about this task and this submission

`record_evidence` decided "substantiated" without asking whether the evidence
was about this task, and `unsatisfied_requirements` accepts any substantiated
evidence on the task. Four ways in, all reachable over MCP:

| Hole | Fix | Test |
|---|---|---|
| A passing run of another task backs this one (`run.task` was never compared) | P5 (`tool-claims-need-runs`) refuses a TOOL_RUN or VERITRIAGE_SESSION record whose run was made for another task | `test_a_run_of_another_task_cannot_back_this_one` |
| The model runtime passed every run ID a model named to the engine; the mock model itself names the upstream runs its prompt cites | `ModelRuntime` drops a named run that was recorded for another task, with the note "dropped runs not made for this task"; a run that was never recorded still goes to the engine, where P5 refuses it as before | `test_the_model_runtime_drops_runs_of_other_tasks` |
| A review that sends work back removed the artifacts but kept `task.evidence`, so the resubmitted file was verified by a run that never saw it | The superseded submission's evidence leaves the task with its files and is kept on its `Attempt` (`evidence`, and the runs it cited in `tool_runs`). Evidence IDs keep counting past moved evidence, so none is reused | `test_a_sent_back_submissions_evidence_does_not_verify_the_next` |
| DOCUMENT evidence was substantiated by any artifact in the project, including the owner's own just-submitted one | DOCUMENT is substantiated only by an artifact of another task that the organization approved | `test_an_owner_cannot_substantiate_its_own_work_with_its_own_document`, `test_a_document_counts_only_when_another_task_produced_it_and_it_was_approved` |
| REVIEW_RECORD evidence was substantiated by any review: a `request_changes` one, a superseded one, or another task's | REVIEW_RECORD is substantiated only by an `approve` review of this task's current submission, still that reviewer's latest verdict | `test_only_an_approval_of_this_submission_is_a_review_record` |

The DOCUMENT and REVIEW_RECORD cases record the evidence unsubstantiated
rather than refusing it, as a claim is: the record shows what was asserted, and
it satisfies nothing. A borrowed tool run is refused, because recording it would
say a tool ran for this task when it did not (P5).

## 2. M1: a tool run is recorded only through the broker

`record_tool_run`'s docstring said only the broker calls it; nothing enforced
that, and a run recorded under an existing ID replaced the old one.

- The engine module holds `BROKER_SEAL`, and `record_tool_run` refuses any call
  that does not pass it. Only `runtime/tools.py` (the broker) imports it, and a
  law test reads every source file's imports to keep it that way
  (`test_only_the_broker_holds_the_seal`).
- A run ID already recorded is refused (`test_a_recorded_run_cannot_be_replaced`),
  and a run naming an unknown task is refused.
- `test_a_run_nobody_executed_cannot_be_recorded` is the audit's probe.

In one Python process nothing stops code that deliberately imports a private
name. The seal makes the broker the only path any surface offers (MCP and the
CLI have no tool-run recording, and a runtime gets a `ToolHandle`, not the
engine), and the law test makes a second holder a visible, failing change.

## 3. H1: approving is a person's where the authority matrix says so

The authority matrix's `human_required` column (M40) says a person must take
`approve_artifact` at critical, `approve_gate` at every criticality, and
`cancel_task` at critical. It was enforced only when a decision was *recorded*
(`decision.record`); `approve`, `approve_gate`, and `cancel` never read it.

The fix extends the P12 check `human-decisions` (no new constitution data, so
the organization fingerprint and every project ID are unchanged): for
`task.approve`, `gate.approve`, and `task.cancel` it looks up the matrix row
for the decision that action takes, at the task's criticality, and refuses an
actor who is not a person. The engine's own system actor is not a person
either.

| Test | What it shows |
|---|---|
| `test_an_agent_cannot_approve_critical_work` | the audit's probe: an agent approver of `microarchitecture` (critical) is refused; a person is not |
| `test_an_agent_cannot_sign_a_gate_even_one_marked_for_agents` | `requirements.gate` has `human_required` False on the gate, and the matrix still asks for a person |
| `test_an_agent_cannot_cancel_critical_work` | cancelling critical work is a person's |

Consequence: every gate is now signed by a person, as `company/governance.py`
already said ("Gate approvals, waivers, and releases are always a person's").
`GateSpec.human_required`, the per-project `--human-gate`/`--auto-gate`
overrides, and the older `human-gates` check still run, but the matrix is now
the stricter rule, so `--auto-gate` (and MCP `plan_project`'s `auto_gates`) no
longer lets an agent sign anything. M52 removed both options
(`docs/RUNTIME_LOOP_FIXES.md` section 8).

## 4. MCP identity: one session is one agent in one role

The MCP server built every actor from the `role` argument of each call, so one
client could start and submit as the owner, review as the reviewer, and approve
as the approver. P6 held role by role while one agent did everything.

**Decision.** A server session acts as exactly one role:

1. the role configured when the server starts (`nirmaan mcp --role ROLE`, or
   the `NIRMAAN_MCP_ROLE` environment variable), else
2. the role of the session's first action that the engine accepts.

A call that names any other role is refused with `McpIdentityError` before
anything runs, and the call's `role` argument may be omitted once the session
has one. The caller is still always an AI agent.

**Why this design.** The identity has to come from something the model on the
other end of the pipe does not choose call by call. The MCP host's
configuration is that thing: whoever wires a model into a session decides which
seat it fills, in the same place they decide which projects directory it sees.
A per-task memory of "who touched what" (refusing a second seat on the same
task) was the alternative; it would let one session hold the owner seat of one
task and the reviewer seat of the next, which is the same conflict one step
removed, and it would need state across server restarts to mean anything.
Binding on the first accepted action keeps an unconfigured, single-role client
working with no setup, and a refused first call binds nothing, so a typo does
not lock a session to the wrong role. Running several sessions with different
roles is possible, but it is a person configuring several agents, which is
exactly what an organization of seats is.

Together with section 3 this gives the two rules the brief asks for: an agent
never reviews or approves its own task's work (the engine's P6 check refuses
the owner role, and a session cannot leave its role), and an agent never
approves where `human_required` applies (P12, for every surface).

Test: `test_an_mcp_session_acts_as_one_role`. The existing MCP tests open one
session per role through `nirmaan_helpers.mcp_session`.

## 5. L2: escalating a task needs a stake in it

`escalate` checked no relation between the actor and the task, so any role
(and any MCP agent naming any role) could move any task to ESCALATED, where
only the routed target can release it. Now the actor must be the task's owner,
reviewer, or approver, a reviewer who has reviewed it, someone in its
escalation path or management chain, the target (or above the target) of an
escalation already on it, or the engine itself. Escalations not about a task
are unchanged. Test: `test_an_unrelated_role_cannot_escalate_a_task`.

## 6. M2: completing needs something produced

`complete` checked status and requirements but not that anything was
submitted, so a WORK task with no review and no evidence requirement completed
with no artifacts, and a review-less DECISION completed with no outcome, which
then cancelled every branch. P4 (`no-fabricated-completion`) now also runs on
`task.complete`: a WORK or DECISION task with no artifacts, or a DECISION with
no outcome, is refused. Tests: `test_work_with_nothing_produced_cannot_complete`,
`test_a_decision_cannot_complete_without_an_outcome`.

## 7. Legitimate flows that relied on a hole

| Flow | What it relied on | How it works now |
|---|---|---|
| `regression-investigation/change-correlation` | its only evidence, `documented(...)`, was met by the owner citing its own artifact | the stage gains an independent review (`rtl.review`, as `feature-addition/impact` has); the review's approval meets `documented(...)` |
| `tests/nirmaan_helpers.py` `drive` | approved work and signed non-human gates as an agent; recorded DOCUMENT evidence on the task's own artifact | approves and signs as a person; records no self-document (the review meets `documented(...)`) |
| MCP tests acting as several roles on one server | per-call roles | one session per role, on the same store and bus (`mcp_session`) |
| MCP gate approval in `test_nirmaan_mcp.py` | an agent signed `requirements.gate` | the test now shows the refusal; a person signs gates with the CLI |
| Model seats downstream of a tool-backed stage | the mock model named the upstream runs its prompt cited, and they became this task's evidence | they are dropped with a note; the task's own runs back it |

## 8. Not in this milestone

- The other audit A findings (C1, C3, H2, H3, M3 to M6, L1, L3 to L6) are
  outside this change; C3, H3, and M3 are the parallel persistence work.
- Removing `--auto-gate` and `auto_gates` (section 3). Done in M52.
- An identity for people: a CLI `--as ROLE` is still whoever runs the command.
- Evidence recorded during a refused M26 attempt stays on the task, as M26
  designed ("the evidence stands"), so the repair prompt can cite the failed
  run. A failed run satisfies nothing; a passing run of a refused attempt can
  still meet a requirement with no file binding for the next attempt. Binding
  each evidence record to the submission it was recorded for would close that
  too, and would change the M26 repair prompt; it is left for a follow-up.
  Done in M52 (`docs/RUNTIME_LOOP_FIXES.md` section 5).
- A downstream model seat's prompt shows (golden `root-cause-*.txt`) that it
  no longer gets the upstream VeriTriage run recorded as its own evidence.

# Learning proposals (M33)

The seventh and last structural-review milestone
(`docs/architecture/target-state.md` section 5). The brief's learning loop, with its own rule: **knowledge never
changes automatically from one model-generated conclusion; every update has
provenance and validation.**

## What it is

`nirmaan.proposals.learning_proposals(org, states)` reads the failure records
(M29) of one or more projects and proposes changes to the skills whose work keeps
failing the same way. It is a view: it stores nothing, edits no skill, and calls
no model.

| Rule | When | Proposes |
|---|---|---|
| `recurring-check-failure` | A check (tool) failed on work of one capability in at least two different tasks | For each skill that provides the capability: a common failure mode naming the tool and the first failure, and a procedure to run the tool on one's own files before submitting |
| `recurring-review-send-back` | Reviews sent work of one capability back in at least two different tasks | For each skill that provides the capability: a validation criterion, quoting what the reviewers asked for |

Rules are a registry (`register_proposal_rule`). Each `Proposal` carries a
stable ID (from its rule, capability, and subject, so it survives new
evidence), the target skills, the statement, the suggested text, how many tasks
and projects it rests on, and **every record it rests on** (project, task,
attempt, runs, evidence, summary). A single occurrence proposes nothing.

## Deciding

A proposal is adopted or rejected by a person, as a recorded decision in one of
the projects it rests on: `decide_proposal(engine, proposal, actor, adopt,
reason)` records a cross-team decision through the engine, so the authority
matrix applies (a manager or above for this criticality) and the decision shows
in `nirmaan decisions` (M29) with its rationale and the evidence it cites. Only a
human actor may decide; an AI agent is refused. A proposal's status (`open`,
`adopted`, `rejected`) is read from those decisions.

**Adopting changes nothing by itself.** The skills are company data in
`src/nirmaan/company/skills.py`; an adopted proposal is a reviewed, recorded
reason for a person to change them in a pull request, which is where the
change is validated by the suite. That is deliberate: the organization's
knowledge is versioned code, and the engine is not its editor.

## Surfaces

`nirmaan learn PROJECT... [--json]` lists proposals across projects;
`nirmaan learn PROJECT... --decide ID --in PROJECT --as ROLE (--adopt | --reject)
--reason TEXT` records a decision as a human.

## Tests (`tests/test_nirmaan_learning_proposals.py`)

- A check that failed on RTL work in two projects proposes a failure mode and a
  procedure for the skill that provides RTL work, citing both runs; one failure
  proposes nothing; the ID is stable as evidence grows.
- Reviews that sent interface specifications back in two projects propose a
  validation criterion quoting the reviewers.
- Reading changes no project state and no organization data.
- A manager adopts a proposal: the decision is recorded with its evidence and
  shows in `nirmaan decisions`; the proposal reads as adopted; the skills are
  unchanged. An AI agent may not decide; a role without authority is refused.
- The CLI lists and decides.
- `proposals.py` names no stage, tool, artifact kind, or role.
- Crown jewel `test_a_new_proposal_rule_needs_no_core_changes`: a rule for
  recurring escalations, registered in the test, proposes from them.

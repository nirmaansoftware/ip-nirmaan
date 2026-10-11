# Recording explicit decisions from the CLI and over MCP (M40)

M29 made decisions readable (`nirmaan decisions`, the MCP `decisions` tool,
the export) and deferred one thing: **recording** an explicit engineering
decision, because nothing called `TaskEngine.record_decision`. M40 adds the
callers: `nirmaan decide` and the MCP tool `record_decision`. Both are one
engine call, so the authority matrix and the constitution decide, and one
audit entry records each decision.

## What a decision records

`Decision` (in `models/work.py`) gains three fields, all defaulted, so every
saved project still loads:

| Field | Meaning |
|---|---|
| `subject` | The question decided ("Which arbitration scheme?"). Empty when the decision is about a task, whose title then reads as the question. |
| `options` | The alternatives considered, as given. |
| `supersedes` | The ID of an earlier decision this one replaces. |

The existing fields stay: `kind` and `criticality` (they pick the authority
rule), `statement` (the decision text), `rationale`, `made_by`, `task`, and
`evidence` (the evidence IDs it rests on).

## Rules, all in the engine

`TaskEngine.record_decision` takes the new fields and refuses, saving nothing,
when:

1. **Authority (existing).** The actor's role lacks the level the authority
   matrix sets for this decision kind and criticality
   (`AuthorityError`, naming who to escalate to).
2. **P2, evidence for decisions.** Existing rule: a HIGH or CRITICAL decision
   needs evidence, and all of it substantiated. M40 adds one line that applies
   at every criticality: a cited evidence ID must exist in the project. A
   decision may never cite evidence that was never recorded. A LOW or MEDIUM
   decision may still be recorded with no evidence, as P2 says "important
   engineering decisions require evidence"; the view shows it with none.
3. **P12, human decisions (new check `human-decisions`).** The authority rule
   for this kind and criticality says `human_required` and the actor is not a
   human.
4. **Supersession (WorkError).** The superseded decision must exist, must not
   already be superseded, must be of the same kind, and the new decision's
   criticality may not be lower. So superseding needs at least the authority
   the original needed, and a human-only decision can only be replaced by a
   person.
5. **Unknown task (WorkError).** A named task must exist.

The audit entry stays `decision.record`, with the kind, criticality, options,
and `supersedes` in its details.

## The authority model: agents and people

Which kinds an AI agent may record is data: `AuthorityRule.human_required`,
set in `company/governance.py` by the matrix's `human_from` column. The
orchestrator and the MCP layer name no decision kind.

| Decision kind | An agent may record | A person is required |
|---|---|---|
| `execute_task`, `modify_artifact`, `review_artifact`, `create_task`, `assign_task` | every criticality | never |
| `cancel_task`, `approve_artifact`, `architecture_decision`, `cross_team_decision` | low, medium, high | critical |
| `approve_gate`, `waive_requirement`, `release` | never | every criticality |

The reasoning: waiving a requirement, releasing, and approving a gate commit
the company to something outside the engineering record, so a model never
records them. A critical decision of any kind (executive level in the matrix)
is a person's. Below that an agent may record a decision, but only with the
authority of the role it acts as and, at HIGH, with substantiated evidence. An
agent acting as a director still cannot record a critical architecture
decision.

Because the rule is in the engine, it holds for every caller, not only MCP:
`nirmaan decide --agent` is refused the same way.

## Surfaces

### CLI

```
nirmaan decide PROJECT "Use round-robin arbitration" --as ROLE \
    --kind architecture_decision --criticality medium \
    --subject "Which arbitration scheme?"   # or --task STAGE
    --option round-robin --option fixed-priority \
    --evidence EVIDENCE_ID --rationale "Bounded wait for every requester." \
    [--supersedes dec-001] [--agent]
nirmaan decisions PROJECT [--json]
```

`decide` acts as a human unless `--agent` is given, as `nirmaan task` does.
A refusal prints the engine's reason and exits 1. `decisions` now shows the
kind, criticality, and supersession of a recorded decision.

### MCP

`record_decision` (action) takes the same arguments. As everywhere over MCP
(M22), the caller is an AI agent, so a human-only kind or a critical decision
is a tool error carrying the `[P12]` reason. The tool is one `register_tool`
call; the transport and context are unchanged.

### Views and export

`DecisionRecord` gains `kind`, `criticality`, `supersedes`, and
`superseded_by` (None for decision tasks). For a recorded decision the
alternatives are its `options`, the question its subject (or its task's
title, or the statement), and the status `superseded` once a later decision
replaces it. History is kept: the superseded decision is never edited or
removed; `superseded_by` is read from the later record. The export's
`decisions` section prints both links.

## Tests (`tests/test_nirmaan_decisions_cli_mcp.py`)

- CLI decide, list, and supersede, with the history kept.
- No evidence at HIGH, or a missing evidence ID: refused by P2, nothing saved.
- Insufficient authority: refused, nothing saved.
- MCP decide works for an agent-recordable kind; a human-only kind and a
  critical decision are refused with the P12 reason; nothing saved.
- One `decision.record` audit entry per decision, with its details.
- Decisions, with supersession, appear in the view and the export.
- Crown jewel: making a decision human-only is one row of data, with no code
  change, and the new tool is listed over the transport.
- Import laws: the existing AST tests cover the changed modules.

## Not in M40

- Deciding the subject unit (`subject_unit`) for scope checks from the CLI or
  MCP; the matrix's level check applies, the scope check does not.
- Cross-functional sign-off on decisions that need it (the matrix records the
  flag; nothing collects the second sign-off yet).
- Withdrawing a decision without replacing it.

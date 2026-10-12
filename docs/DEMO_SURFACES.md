# Demo surfaces (M54)

Audit C read everything a user or a demo audience touches in v1.24.0: the
landing page, the CLI, the docs. M50 to M52 fixed what it found in the engine.
This milestone fixes what remained on the surface: claims the engine does not
back, and output that prints Python instead of words. Tests:
`tests/test_nirmaan_demo_surfaces.py` and
`tests/test_ai_boundary.py::test_missing_credentials_raise_clean_error`, each
failing on main first.

## 1. The landing page states only what the engine does

Each claim was checked against the code, not the docs.

| Was | Is | Why |
|---|---|---|
| "the refusal is written to the audit trail" | refused "before it changes anything"; a refused AI submission's attempt and reason are recorded | A BLOCK violation raises `PolicyViolationError` and leaves state untouched, so nothing reaches the trail. Runtime refusals are recorded as attempts (`task.attempt`). All twelve articles are BLOCK. |
| "every gate names the human who approves it" | "every gate waits for a person's sign-off" | Gate approval is human-only at every criticality (`APPROVE_GATE`, `human_from=L`); the plan names a role, not a person. |
| ladder: executed = "A recorded tool run" | "Submitted by its owner" | An artifact is EXECUTED on submission (`work/engine.py`). |
| ladder: verified = "An independent review" | "All required checks recorded" | VERIFIED means every evidence requirement of the task is met. |
| ladder: approved = "A named human's sign-off" | "An authorized sign-off" | Artifact approval needs a person only for critical work; below that an authorized AI role may approve, never its own work (P6). |
| "A first live evaluation ... passed all four RTL cases" | tests use scripted answers; one early live run passed, not recorded as data | `evals/results/` has no record of it (`docs/LIVE_EVAL_EVIDENCE.md`). |
| "The blocks it has designed end to end" | the reference blocks "prove the flow and its checks, not yet a model designing them unaided" | M26's seats were a scripted `MockLLM`. |

`docs/LANDING_PAGE_BRIEF.md` and `docs/ROADMAP.md` carry the same wording.

## 2. CLI output a person can read

- `task escalate` prints `esc-001 uncertainty -> <role>: <reason> (open)`, not
  the model's repr.
- `status` prints each blocked task, escalation, review, gate, risk, and
  assumption as labelled fields (`task: ...  gate: ...`), not JSON. `--json`
  is unchanged.
- `workflows <id>` prints `after requirements  when any_of: noc`, not Python
  lists and tuples.
- An unknown project reads `Unknown project 'nope'`, not a quoted `KeyError`
  (`show`, `status`, `gaps`, `export`, and every command that loads a project).
- `gaps` with no recorded requirements says so and points at
  `nirmaan vplan import`, instead of "0 of 0 ... are backed". The exit code is
  unchanged: nothing is unbacked.
- `veritriage analyze --ai` without credentials prints one warning ("AI review
  skipped - no Anthropic credentials ...") and finishes the deterministic run.
  The SDK reports missing credentials as a `TypeError`; the reasoner turns
  exactly that one into an `AIReasoningError` and re-raises any other.

## 3. Docs

- Eighteen design docs no longer open with "for the owner's review,
  implemented on branch ...": they say merged.
- `docs/NIRMAAN_MCP.md` lists all 19 tools (`decisions` and `failures` were
  missing).

## Left as they are

- Routing a PD audience will question (audit C M5: DRC and LVS to an antenna
  engineer). It is company data with its own scoring; changing it is a routing
  decision, not a surface fix.
- An artifact whose file does not exist can be approved on a review alone
  (audit C M2). That matches the engine's definition of VERIFIED for a task
  whose only requirement is a review; a submit-time existence check belongs
  with the engine, not here.
- `show` ordering, truncated project names, `eval` outside the repository, and
  the low items of audit C.

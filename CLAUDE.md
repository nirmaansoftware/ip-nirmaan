# CLAUDE.md

Guidance for AI coding agents working in the IP Nirmaan repository. Before
starting work, read `context.md` (what exists now), `docs/ROADMAP.md` (what
comes next, the reserved milestone numbers, and the resume checklist), and the
`docs/history/` files of the milestones you touch (how it got here).

## How to work

Adapted from the four principles in
[andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills)
(MIT). That repository is not Andrej Karpathy's own; it is derived from his
observations on where LLM coding agents go wrong.

1. **Think before coding.** State assumptions. If a request has several
   readings, say which you picked and why. Stop and ask only when a decision is
   genuinely the user's (naming, anything public, anything irreversible);
   otherwise pick the sensible default and say so.
2. **Simplicity first.** Write the minimum that solves the problem. Add no
   speculative features, and no configuration nobody asked for.
3. **Surgical changes.** Every changed line should trace to the request. Match
   the surrounding style. Mention unrelated problems rather than fixing them
   silently, and remove only what your own change made dead.
4. **Goal-driven execution.** Turn the task into checks: a failing test first,
   then the fix. For multi-step work, list the steps and how each is verified.

## Rules specific to this repository

- **No em dashes or en dashes** anywhere: code, comments, docs, commit messages.
  Use a hyphen, a colon, or rewrite the sentence.
- **Two packages, one direction.** `src/veritriage/` (the verification engine)
  never imports `src/nirmaan/`. Inside Nirmaan, only
  `src/nirmaan/integrations/veritriage.py` imports VeriTriage. Tests enforce
  both laws.
- **Data over code.** The organization, workflows, and routing vocabulary live
  in `src/nirmaan/company/`. The orchestrator must not name a unit, skill,
  role, or protocol (a test reads its string constants).
- **Never fake work.** Nothing may claim that a tool ran, or that work was
  verified or approved, without a record the engine can substantiate. New
  tools start as `CONTRACT_ONLY`.
- **Extension points are registries.** Add a crown-jewel test proving a new
  extension needs zero core changes.
- **Milestones ship complete:** code, tests, a design doc in `docs/`, and a
  history entry. Reserve the number in `docs/ROADMAP.md` ("Milestone numbers")
  before cutting the branch. The milestone adds its own
  `docs/history/MNN-<slug>.md` file and one line in `docs/history/README.md`;
  it does not append to `context.md`, which holds current facts only (edit it
  only when one changes). Counts in the roadmap are generated: run
  `python scripts/status.py --write` after adding a workflow, tool, unit,
  skill, or principle, never type them. See `docs/STATUS_DOCS.md`. Work on a
  feature branch, then open a PR.
- **Commit messages** end with the Co-Authored-By line from the session's
  attribution instructions. Never amend or force-push.

## Running tests

The repo may sit in iCloud-synced `~/Documents`, where evicted files make
imports hang. Keep bytecode outside iCloud:

```
PYTHONPYCACHEPREFIX=/tmp/nirmaan-pycache .venv/bin/python -m pytest -q \
  --deselect tests/test_ai_boundary.py::test_missing_sdk_raises_clean_error
```

The deselected test imports the `anthropic` SDK and can stall for a long time
while iCloud downloads it. Run it separately when the venv is fully local.

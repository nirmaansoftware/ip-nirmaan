# Structural review: staged plan and progress

A resumable tracker for the structural review requested on 2026-09-29 (the
"build the engineering engine, not an AI wrapper" brief). Each stage ends with
a commit on branch `review/structural`, so a new session resumes by reading
this file, then `git log --oneline main..review/structural`, and picking up at
the first stage not marked DONE.

Rule for the whole review: the brief itself says "do not rewrite working
systems merely to impose a new architecture." The repo already has most of the
brief's concepts under other names. The review maps them first, and builds
only what is genuinely missing.

## Working-tree caveat (found at start)

On `main`, before this branch was cut, the working tree had uncommitted work
from an earlier session: `context.md` (M23 export entry, version 1.18.0),
`docs/DELIVERABLE_EXPORT.md` (untracked), and `docs/ROADMAP.md` emptied to
zero bytes. None of it belongs to this review. Stage commits must stage only
this review's files (never `git add -A`). The owner decides what to do with
the empty `ROADMAP.md`; the committed copy is intact in git.

## Stages

| # | Stage | Output | Status |
|---|---|---|---|
| 0 | Branch and tracker | this file | DONE |
| 1 | Inventory: read every Nirmaan module and the VeriTriage seams it uses | `docs/architecture/current-state.md` | TODO |
| 2 | Gap analysis against the brief, concept by concept | `docs/architecture/target-state.md` | TODO |
| 3 | Milestone roadmap and the first milestone's design | `docs/architecture/proposed-change.md` | TODO |
| 4 | Implement milestone 1 only, test first | code + tests, full suite green | TODO |
| 5 | Design doc, `context.md` entry, PR | PR link | TODO |

## Notes carried between stages

(Each stage appends what the next stage must not re-derive.)

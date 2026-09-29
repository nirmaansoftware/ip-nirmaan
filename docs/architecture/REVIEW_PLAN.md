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

Local `main` was about 40 commits behind `origin/main` (v1.18.0 locally,
v1.20.0 on GitHub), and its working tree held stale uncommitted leftovers
(`context.md` M23 entry, `docs/DELIVERABLE_EXPORT.md`, and `docs/ROADMAP.md`
emptied to zero bytes), all of which are already merged upstream. They were
stashed, not deleted (`git stash list`: "pre-review leftovers on main"), and
this branch was rebuilt on `origin/main` (acbe52b, v1.20.0). Local `main`
itself was not moved. The venv was stale (it pointed at the old
`~/Documents/veritriage` path) and was rebuilt per the roadmap's resume
checklist. iCloud has evicted many files, including `.git` objects; a git
command that fails with "mmap failed: Operation timed out" should simply be
retried. Stage commits stage only this review's files (never `git add -A`).

## Stages

| # | Stage | Output | Status |
|---|---|---|---|
| 0 | Branch and tracker | this file | DONE |
| 1 | Inventory: read every Nirmaan module and the VeriTriage seams it uses | `docs/architecture/current-state.md` | DONE |
| 2 | Gap analysis against the brief, concept by concept | `docs/architecture/target-state.md` | TODO |
| 3 | Milestone roadmap and the first milestone's design | `docs/architecture/proposed-change.md` | TODO |
| 4 | Implement milestone 1 only, test first | code + tests, full suite green | TODO |
| 5 | Design doc, `context.md` entry, PR | PR link | TODO |

## Notes carried between stages

(Each stage appends what the next stage must not re-derive.)

- **After Stage 1.** The brief's core primitives mostly exist under other
  names (see current-state.md section 7). The real gaps, by leverage: (1) no
  evaluation of model seats against live models, (2) informal tool contracts
  with comma-joined string params, (3) untyped `WorkPacket`, (4) whole-state
  fingerprint per operation, (5) implicit artifact versions, (6) thin
  `Decision`, (7) unclassified failures, (8) design intent only as prose,
  (9) model chosen by name, (10) process-global registries. Do not create a
  parallel `nirmaan/engine/` package: `work/` + `runtime/` already are the
  engine, and the brief itself forbids rewrites for their own sake.

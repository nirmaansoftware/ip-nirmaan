# Status documents that stop colliding and stop drifting (M43)

Until M43 every milestone PR appended an entry to `context.md` and edited the
`docs/ROADMAP.md` "Where we are" table. Those two files were the shared
conflict points of every parallel batch: 65 "merge main into branch" commits
across 50 PRs, many titled "main's entries first, then MXX". They also drifted:
the roadmap said 1430 tests when the suite had 1,580, the resume checklist said
"continue with Stage 0", and the landing page's numbers were tied to the
organization by a test, which bent two design decisions (#30, #55: a feature
was shaped so that it would not change the site's workflow count).

The principal-engineer review (recommendations 5, 7, and 9) asked for three
things: retire `context.md` as a merge hotspot, generate the counts from code,
and decouple the landing page from domain counts. M43 does all three, and adds
a milestone-number registry so numbers stop colliding too.

## 1. One file per milestone

Milestone history moves out of `context.md` into `docs/history/`, one file per
entry, verbatim (only the heading is promoted from `###` to `#`).

- **Names sort by milestone.** `M01-traceiq.md` to `M43-status-docs.md`, two
  digits so that `ls` order is milestone order. Entries that share a number get
  a letter after it, in the order they were written: `M27-a-repair-after-review.md`
  to `M27-f-seat-evaluation.md`. Side work that happened between milestones is
  named after the milestone it followed (`M19-side-1-landing-page.md`), and
  releases are `release-vX.Y.Z.md`.
- **`docs/history/README.md` is the index,** in milestone order, one line and
  one link per file. Order is milestone number, then letter, not merge date:
  the old `context.md` had M25 before M24 and M39 after M42.
- **Nothing is lost.** `tests/fixtures/history_headings.txt` lists every
  heading of the old section 2, and a test asserts each one is the heading of
  exactly one history file. The old sections 1, 3, 4, and 5 (the VeriTriage
  description, the architecture map with its stale test count, the
  operational notes, and the VeriTriage-era future work) are kept verbatim in
  `docs/history/context-before-M43.md`, except the v1.21.0 and v1.22.0
  release paragraphs, which became their own release files.

`context.md` keeps only current facts: what the system is, the architecture
map, operational notes, conventions, and a pointer to `docs/history/`. A test
holds it under 400 lines and with no milestone headings, so it cannot grow back
into a log.

## 2. The convention that stops the collisions

A milestone adds its own `docs/history/MNN-<slug>.md` and a line in
`docs/history/README.md`. It does **not** append to `context.md`, and it does
not edit numbers in the roadmap by hand. Two parallel PRs then touch different
new files; the only shared line is the README index, where a conflict is two
adjacent lines and is resolved by keeping both. `context.md` changes only when
a current fact changes (a new top-level package, a new operational rule), which
is rare and deliberate. This rule is written into `CLAUDE.md` ("Milestones ship
complete").

## 3. Counts generated from code

`scripts/status.py` computes every count the roadmap and the site state:

| Count | Source | Cost |
|---|---|---|
| units, roles, skills, workflows, principles | `build_organization().stats()` | an import |
| tools `AVAILABLE`, tools `CONTRACT_ONLY` | the organization's tools by `ToolStatus` | an import |
| verification knowledge packs | `veritriage.knowledge.registry.available_packs()` | an import |
| tests | `pytest --collect-only -q`, the "N tests collected" line | about 2 s |

**The structural counts are checked on every PR; the test count is not.**

- The structural counts change only when a PR adds a workflow, a tool, a unit,
  a skill, or a principle. When they do, the generated block in the roadmap
  must change with them, by running `scripts/status.py --write`. A test
  (`tests/test_status_docs.py`) recomputes them and fails on drift, so the
  roadmap can never again claim a number the code does not have.
- The test count changes in almost every PR. Collecting it is cheap (about
  2 s), so cost is not the reason. The reason is churn: checking it per PR
  would make every PR edit the same number, which is exactly the collision
  this milestone removes. So the test count is a **release snapshot**: it is
  collected by `scripts/status.py --release`, stored in `site/stats.json` with
  the version, and shown everywhere as "at vX.Y.Z". A dated number is not
  drift; an undated stale one was.
- **Tests are counted as collected, not as passed.** The collection count
  includes the 7 tests that run only in CI's `physical-design` job and the one
  SDK test the local run deselects; all of them are real tests that CI runs.
  At v1.23.0 this is 1611 (the standard local run: 1603 passed, 7 skipped,
  1 deselected). Counting passes would need a full EDA run and a machine with
  every tool, which is a CI fact, not a document fact.

The roadmap block sits between `<!-- status:begin -->` and
`<!-- status:end -->` in `docs/ROADMAP.md`, one table row per count, so two PRs
that change different counts touch different lines.

## 4. The landing page reads `site/stats.json`

`site/stats.json` is written by `scripts/status.py --release` with every count
and the version. The site has no build step and must work without JavaScript,
so the same command writes each number into the stat tiles of
`site/index.html` (both `data-count` and the visible text), keyed by a
`data-stat` attribute on each tile. Nothing about the page's look changes: no
CSS or JS is touched, and nirmaan.online's vendored files stay byte-identical.

`tests/test_landing_site.py` no longer compares the tiles with the
organization. It checks that each tile equals `stats.json`, and that
`stats.json` has every key the page shows. So adding a workflow, a skill, or a
tool breaks no site test; the site catches up at the next release, and the
page copy now says so ("generated from the code at each release"). A test
proves it: with the organization reporting one more workflow, the site check
still passes while the roadmap check fails.

The constitution cards stay checked against `CONSTITUTION`: they are the
principles' text, not a count, and changing a principle is a deliberate act.

## 5. The milestone-number registry

`docs/ROADMAP.md` has a "Milestone numbers" table. The rule: **reserve the
number there, on `main`, before cutting a branch.** A number is never reused,
and a part of a batch takes the batch's number with a letter (`M27-c`) instead
of inventing one. This removes the six M27s and seven M29s of the last batches,
and the out-of-order assignment (M35 merged before M34). M44 to M49 are already
reserved by the owner.

## 6. Commands

```
python scripts/status.py            # print the live counts and what the docs say
python scripts/status.py --check    # exit 1 if the roadmap or the site disagree
python scripts/status.py --write    # rewrite the roadmap block (structural counts)
python scripts/status.py --release  # at a version release: collect tests, write
                                    # site/stats.json, the site tiles, the block
```

Run them with `PYTHONPATH=src` (or an installed package). `--check` imports the
organization but never runs pytest, so it is cheap enough for every PR; the
test suite runs the same checks, so CI needs no extra step.

## 7. Release checklist (replaces the hand-edited counts)

1. Bump `pyproject.toml` and the "Current version" line of `context.md`.
2. `python scripts/status.py --release`, then commit `site/stats.json`,
   `site/index.html`, and `docs/ROADMAP.md`.
3. Add `docs/history/release-vX.Y.Z.md` and its line in the index.
4. Tag the release.

## 8. Not done here

- **No CI job for the release snapshot.** The site's numbers trail the code
  between releases by design. A scheduled check could warn when they are far
  behind; nobody asked for it.
- **Older docs that cited the VeriTriage-era future work of the old
  `context.md`** (the VeriTriage-era design docs) were left as written here;
  that section is now in `docs/history/context-before-M43.md`, and M47
  repointed them to it. The source comment in
  `knowledge/packs/ddr.py` and `docs/architecture/current-state.md` are updated.
- **Version and tags.** M43 bumps no version.

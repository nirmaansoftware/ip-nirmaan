# Milestone 43 - Status documents that stop colliding and stop drifting

The first milestone after v1.23.0, run alone before the next batch, because
every earlier PR had to edit `context.md` and the roadmap table: 65 merge-fix
commits across 50 PRs, six PRs labelled M27 and seven M29, and status numbers
that were wrong (the review's section 5.4, recommendations 5, 7, and 9). This
is the first entry written under the new convention: its own file, no entry
appended to `context.md`. Design: `docs/STATUS_DOCS.md`.

**History split.** The 67 entries of `context.md` section 2 moved verbatim to
`docs/history/`, one file each, named to sort by milestone (`M01-traceiq.md`
to `M42-eval-proposals.md`; parts of one number take a letter, `M27-a` to
`M27-f` and `M29-a` to `M29-g`; side work is `MNN-side-<n>-...`; releases are
`release-vX.Y.Z.md`, with v1.21.0 and v1.22.0 lifted from the old section 3).
Only each heading changed (`###` to `#`) and the `---` separators were
dropped; a line-by-line comparison found nothing else missing. The old sections
1, 3, 4, and 5 are kept verbatim in `context-before-M43.md`.
`docs/history/README.md` indexes everything in milestone order, which is not
merge order (M25 before M24, M39 after M42 in the old file).

**`context.md`** went from 3,622 lines to 241, current facts only: what the
system is, an architecture map of both packages (Nirmaan's was a single
paragraph before), operational notes (iCloud, environment, tests, CI as it
really is, counts, releases, live models, the landing page), and conventions.
Stale facts were dropped rather than copied: the "854 tests" line, the
VeriTriage-era future work, and the commit attribution of an older model.

**Counts from code.** `scripts/status.py` computes units, roles, skills,
workflows, principles, tools `AVAILABLE` and `CONTRACT_ONLY`, and knowledge
packs from the organization and the pack registry, and the test count from
`pytest --collect-only`. It writes a generated block into `docs/ROADMAP.md`
("Counts", between `status:begin` and `status:end` markers), one row per count.
A test fails on every PR whose structural counts differ from the block
(`--write` fixes it); the test count is a release snapshot (`--release`), not
checked per PR, because checking it would make every PR edit one number,
which is the collision this milestone removes. Tests are counted as collected:
1611 at v1.23.0 (1603 passed, 7 CI-only skips, 1 deselected locally).

**The landing page** reads its numbers from `site/stats.json`, the release
snapshot. `--release` also writes each number into its tile (`data-stat` names
the key), so the page needs no JavaScript to show them, and no CSS or JS
changed. `tests/test_landing_site.py` compares the tiles with `stats.json`
only, no longer with `build_organization()`, so adding a workflow or a skill
breaks no site test (`test_adding_a_workflow_breaks_no_site_check` proves it).
The tests tile now shows 1611 (collected) instead of 1603 (passed locally), and
the section's copy says the numbers are generated at each release.

**Roadmap.** A "Milestone numbers" registry (M43 in progress, M44 to M49
reserved by the owner) with the rule "reserve the number here before cutting a
branch", a "Next milestones" section, numbers removed from the "Where we are"
prose, the resume checklist no longer quoting a count, the stages marked as a
historical summary pointing to `docs/history/`, and the structural-review
section marked done. `CLAUDE.md`'s "Milestones ship complete" rule now says a
milestone adds `docs/history/MNN-<slug>.md` and does not append to
`context.md`.

Tests: `tests/test_status_docs.py` (every old heading in exactly one history
file, file names sort by milestone, the index links every file once,
`context.md` under 400 lines with no milestone headings, `CLAUDE.md` states the
convention, roadmap counts match the code, a drifted number fails,
`stats.json` is complete, the site matches `stats.json`, a new workflow breaks
no site check, the site tests never read the organization, M43 to M49 are in
the registry, and no dashes in the status documents).

Deferred: a scheduled check that warns when the site's snapshot is far behind;
updating the VeriTriage-era design docs that cite "`context.md` section 5.x"
(that section is now `context-before-M43.md`). No version bump.

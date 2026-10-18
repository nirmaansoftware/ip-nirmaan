# Milestone 59 - Release check for the public org mirrors: the org figure and the hero's plan excerpt are checked against the code at each release

The landing page mirrors the organization in two hand-written places: the org
figure's division names and the role titles in the hero's "Real output of
`nirmaan plan`, trimmed" excerpt. Nothing checked them, so a renamed role or
division would silently falsify the page (site-engineer position, capability
build-out council record, item P1-12). Design: `docs/STATUS_DOCS.md`,
section 9. Tests: `tests/test_release_mirrors.py`.

**The release reads both mirrors first.** `scripts/status.py --release` now
compares the figure's names with the divisions the code builds (active,
outside the business function), and plans the hero's own request with the same
orchestrator and view the CLI uses, requiring every title the excerpt shows to
be one the plan prints. On a mismatch it prints each problem, writes nothing,
and exits 1.

**Release only.** `--check` and the test suite never run it, so code changes
break no PR check and the page catches up at a release, as the tiles already
do. A fixture hero with one role renamed fails `--release`; `--check` passes.

**Found on main.** The hero passes. The figure does not: it shows "Product",
"Infrastructure", "Documentation" and "Quality", where the code builds
"Product and Programs", "Engineering Infrastructure" and "Quality and
Process", and Technical Documentation is a department. The next release stops
until the figure's copy is updated, a public-page change for the founder; this
milestone does not edit `site/**`.

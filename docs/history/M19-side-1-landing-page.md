# Landing page (side work, 2026-09-28) - `site/` for ip.nirmaan.online

A static page built from `docs/LANDING_PAGE_BRIEF.md`: `index.html`,
`styles.css`, `motion.js`, no build step and no dependencies. It reuses the
nirmaan.online design system (tokens copied, not linked, since the two sites
deploy separately) and follows that site's motion standard
(`docs/engineering/motion.md` in `nirmaansoftware/Nirmaan`). Motion is opt-in
(`html.motion`, set only without a reduced-motion preference) and only animates
toward content already in the HTML. `tests/test_landing_site.py` ties the stat
tiles to `build_organization().stats()` and the pack registry, and the
constitution cards to `CONSTITUTION`; the test count (879, up from the brief's 853
with this change) is maintained by hand.
Not deployed yet: hosting and the `ip` CNAME are the owner's call. See
`site/README.md`.

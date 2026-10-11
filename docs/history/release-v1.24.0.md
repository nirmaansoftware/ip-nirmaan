# v1.24.0 (2026-10-12) - the plan from the principal-engineer review

One version bump for the seven milestones the review of v1.16.1 to v1.23.0
recommended, merged as #70 (M43 status docs that stop colliding), #74 (M44 an
end-to-end factory project), #73 (M45 live evaluation as recorded evidence), #71
(M46 tests and CI hardening), #72 (M47 small cleanups), #76 (M48 unified
applicability and limits), and #75 (M49 scoped registries).

What changed for anyone resuming work:
- Milestone history lives in `docs/history/`, one file per milestone; `context.md`
  holds current facts only, and numbers are reserved in the roadmap's registry.
- Counts come from `scripts/status.py`; this release's snapshot is 1710 tests
  collected, 36 tools that run and 17 contract-only, 9 workflows.
- CI jobs are `test` (3.12, real tools), `no-tools` (3.11, no EDA tools and no
  `anthropic`), `physical-design`, `test-union`, and `dashes`; actions are pinned
  by SHA and the OSS CAD Suite is cached and hash-checked.
- One AXI4-Lite request now runs through block design, DFT, firmware, and layout
  on sky130hd on the approved RTL, and its export fills all ten folders (M44).
- An evidence requirement's applicability is one list of conditions, bounds are a
  structured field, and stage limits are one `Limits` object (M48).

Still open: the first recorded live evaluation batch and a required-checks
ruleset, both the owner's call; see the roadmap's "Next milestones".

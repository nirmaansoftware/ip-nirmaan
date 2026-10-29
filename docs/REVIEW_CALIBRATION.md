# Review calibration: composite key 1 A/B (R10)

The record behind the composite key 1 switch (council record
`council/records/2026-10-18-review-loop.md`, decision 1 item 8 and decision 6).
The seeded sets stay outside both repositories, because reviewers can search
the head and `main`. Only aggregates and seed digests are committed here
(decision 6 item 1). Every run used the real `scripts/pr_review.py` in
production mode and posted nothing, with both review loops idle.

## Sample

Stratified, not the full corpus: 21 seeds (the -01 seed of each of 20 seat
groups, plus a second verification-lead seed) and 4 clean controls. Sample seed
digest `a7813556782675bf`.

## R10: one run per item, `main` f12dfc8

| | per-team key 1 | composite key 1 |
|---|---|---|
| seeds caught by key 1 | 21/21 | 21/21 |
| false fails on controls | 0/4 | 0/4 |
| reviewer deferrals | 0/25 | 0/25 |

Items that deferred on a session limit were rerun once it reset: digests
`226db57f500283a7` (per-team, 18 items) and `10dab299bbe26cac` (composite,
1 item).

## R10b: two runs per item, `main` 30a0d24

`main` 30a0d24 includes #146, which closed the record's checklist gaps
(below). 50 item-runs per arm. The per-team arm's second run was cut by a
session limit, and its 11 deferred items were rerun alone (digest
`79671b26dea22f85`). The composite arm ran whole on the sample digest.

| | per-team key 1 | composite key 1 |
|---|---|---|
| seed item-runs caught by key 1 | 41/42 | 42/42 |
| seed item-runs caught by any key | 42/42 | 42/42 |
| Verification seed item-runs caught by key 1 (2 verification-lead, 1 qa-evidence seed) | 6/6 | 6/6 |
| false fails on controls | 0/8 | 0/8 |
| reviewer deferrals | 0/50 | 0/50 |
| findings with a valid citation | all | all |

The per-team key 1 missed the founder-proxy seed once, and key 2 caught it.
Every other seat group was caught by key 1 in both runs in both arms (two
item-runs per seat group, four for verification-lead).

## Against the bar

The composite catches every domain seed at least as often as the per-team
calls, with no regression on Verification seeds, and its false fails and
deferrals are no higher. Limits: one seed per seat group (two for
verification-lead), so the sample says nothing about per-seat rates beyond
these. Seeds that the per-team calls already miss are not in it.

## Checklist gaps closed on `main` before the switch

The record lists gaps to close before the switch. Each is on `main`:
- brand-content, site-engineer and tax-accounts each have an "In a review"
  section in their seat files under `council/`.
- dft-engineer, firmware-engineer and physical-design-engineer member triggers
  are in `.github/review-teams.yml` (`members`): `at_least("test_coverage"`,
  `require_irq` and `require_bus_error_trap`, and the `physical-design-shard`
  job range in `.github/workflows/ci.yml`.
- legal-compliance: the `spec-text` and `export-sensitive` content rules (#146
  and #139). The latter routes export-sensitive content to legal-compliance's
  key 1 in place of a separate `export_control` flag.
- The site hero's review markers map to public names and claims (`hero`
  section, #146).
- `knowledge/design/**` to Silicon Design: no such document exists yet, and a
  guard in `tests/test_review_teams.py` fails when the first one lands without
  that rule.

A change back to the per-team calls, or any change to the composite, needs a
recorded calibration rerun first (decision 6 item 5).

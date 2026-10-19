# Milestone 60 - Span, depth and activation rules become a check

The capability build-out council record of 2026-10-18 (section 3) set the
span rule: every unit with child units has 3 to 8 of them, placeholders
count, leaves and staff executives are exempt, no role is more than 6 layers
below the Board, and an exception is data with a reason and a review date.
M57 made the chart meet it; this milestone checks it. Design:
`docs/ORG_SPAN_RULE.md`. Tests: `tests/test_org_span.py`.

`OrgUnit.span_exception` (a reason and a `review_by` date) is the only way a
unit may sit outside 3 to 8. `shape_issues(org, today)` in
`src/nirmaan/org/validate.py` reports units and executives outside the range,
roles deeper than 6, exceptions that are not needed or past their review
date, and placeholders with no mission. It binds the shipped chart through
its test, not every build, so an overlay or extension still builds.

The activation rule (record section 2, item 10) is in the test: an ACTIVE unit
outside the frozen list of 205 units active today
(`tests/fixtures/org/active-units-m60.txt`) must hold a skill that uses an
AVAILABLE tool and is named by an eval case judged by that tool.

The chart passes with zero exceptions. Each negative fixture (a 9-child unit,
a 2-child unit, a 7-deep chain, an executive at 9, an unneeded or stale
exception, a placeholder with no mission, an unbacked ACTIVE unit) fails. No
unit, role or skill changed.

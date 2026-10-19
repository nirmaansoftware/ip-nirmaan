# Span, depth and activation rules (M60)

The capability build-out council record of 2026-10-18 (section 3, the span
rule, and section 2, item 10, the activation rule) sets the shape the modelled
company must keep. M57 (`docs/HIERARCHY_FIXES.md`) changed the chart so it
meets the rule. This milestone makes the rule a check:
`shape_issues(org, today)` in `src/nirmaan/org/validate.py`, the
`span_exception` field on `OrgUnit` in `src/nirmaan/models/org.py`, and
`tests/test_org_span.py`.

## 1. What is counted

- **A unit.** Its span is the number of child units directly below it.
  Placeholders count: a head is accountable for a placeholder's area.
  Generated ladder roles never count: a leaf's ladder (at most four rungs and
  a tech lead) is that leaf's staffing. The company root is not checked as a
  unit, because its children report to the executives, counted next.
- **An executive** (an explicit role below the Board). Its span is the units
  it sponsors, the child units of the units it heads (not the company or the
  executive office), and the explicit roles reporting to it. This is who
  reports to it directly: the CPO heads Product, so Product's three
  departments report to the CPO, and so do the heads of Documentation and
  Commercial, which it sponsors (5). The CEO heads only the company and the
  office, so its span is the five executives.
- **Exempt.** Leaf units (no child units), the Board (the founder), and staff
  roles: an explicit role that heads or sponsors no unit (today the Chief of
  Staff).

Today's spans: CEO 5, CTO 5, COO 7, CPO 5, Chief Architect 4; every unit with
child units has 3 to 8.

## 2. The rules

| Rule | Fails with |
|---|---|
| A unit with child units has 3 to 8, unless it carries a `span_exception` | `unit <id>: <n> child units, outside 3 to 8` |
| An executive (not staff, not the Board) spans 3 to 8 | `role <id>: span <n>, outside 3 to 8` |
| No role is more than 6 layers below the Board (CEO, C-level, VP, director, manager, ICs) | `role <id>: <n> layers below the Board, more than 6` |
| An exception is only on a unit that needs one | `unit <id>: span exception not needed (<n> child units)` |
| An exception is looked at by its review date | `unit <id>: span exception review date <date> has passed` |
| A placeholder declares its mission | `unit <id>: a placeholder declares no mission` |

`span_exception` holds a `reason` (required, not empty) and a `review_by`
date. Exceptions exist only for units. An executive outside the range has no
exception: record section 2, item 5 sends a ninth area to an existing division
or to a council meeting. After M57 the chart passes with zero exceptions.

Depth counts reporting lines (`line_chain`), not unit nesting. The seniority
check in `validate_organization` already stops a nested unit from adding a
layer (a manager cannot report to a manager), so a chain grows past 6 only
through explicit roles; the check is there for those.

The record also asks each placeholder for the coverage-map area it holds.
That map is P2 work; until it exists, the check is the mission only.

## 3. Why it is not part of every build

`validate_organization` runs on every build and rejects a company that cannot
work (an unknown reference, a cycle, a stage no role can own). Span and depth
are a design rule for the shipped chart, not a condition for the org to
function. An overlay or a registered extension may add a practice to a team
of 8 between reorganizations, and that company must still build. So the rule
binds `org_chart.py` through `tests/test_org_span.py`, which runs in CI on
every pull request, and `shape_issues` is there for anyone who wants to hold
an overlay to it. The review-date check needs today's date, which a build
should not depend on; the test passes it.

## 4. The activation rule

A unit added after the record enters as PLACEHOLDER. It becomes ACTIVE only
in a pull request that shows one of its own skills uses an AVAILABLE tool and
has an eval case judged by that tool: the case names the skill (`skills`, M58)
and a held-out check runs that tool (`tool` or `cover_tool`).

The units that were ACTIVE when the rule took effect are frozen in
`tests/fixtures/org/active-units-m60.txt` (205 units, after M57, including the
two active teams M57 added under record item 6). The test fails on any ACTIVE
unit outside that list that is not backed this way. The list is never
extended by hand: a unit made ACTIVE later passes by its eval case, not by
being added.

The rule lives in the test, not in `org/`, because it reads the eval cases in
`evals/`, and the organization layer does not depend on the evals package.

## 5. Tests

`tests/test_org_span.py`: the chart passes with zero exceptions; executive
spans; depth exactly 6; every ACTIVE unit is frozen or backed. Negative
fixtures, each failing with its own message: a unit with 9 child units, a unit
with 2, a role 7 layers below the Board, an executive at 9, an exception that
is not needed, an exception past its review date (and the same exception with
a future date passing), an exception with no reason, a placeholder with no
mission, and an ACTIVE unit with no backed skill (and one backed by
`rtl_design`, which passes).

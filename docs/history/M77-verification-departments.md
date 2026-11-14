# Milestone 77 - Verification in five departments; four of them ACTIVE as grouping units, the frozen list changed by renames only

Wave 2 (Verification, W2-O1) of the capability build-out (council record
`council/records/2026-10-18-capability-buildout.md`, sections 4 and 10).
Design: `docs/HIERARCHY_FIXES.md` section 5 (accepted as the design doc by
council record `council/records/2026-11-14-g13-grouping-units.md`, decision
4), with the activation rule in `docs/ORG_SPAN_RULE.md` section 4. Tests:
`tests/test_verification_departments.py` and `tests/test_org_span.py`.

The number was reserved late, after the branch `org/w2-verification-cut` was
cut and its pull request (#178) opened; key 2 found no milestone on its first
head, and the reservation, this file and its README line were added to answer
that finding.

**The cut.** Verification had eight teams directly under its VP. It now has
five departments, each with a generated director: Methodology and Signoff
(`verification.methodology`), Simulation (`verification.dynamic`), Formal and
Static (`verification.formal`), Debug and Regression (`verification.debug`),
and Processor and Accelerator (`verification.processor`, a placeholder with
placeholder children). Spans: VP 5, departments 3 to 4; depth unchanged.
Every existing unit moved with its skills, tools, noun and ladder; two
practices (equivalence, triage) and the regression practice became teams.

**Activation.** Record item 10, as amended by the G13 record, lets a unit be
ACTIVE as a grouping unit: no skills, tools, ladder or explicit roles of its
own, at least one ACTIVE child, every ACTIVE child frozen or backed by an eval
case, never stacked on another new grouping unit, and a head that holds
nothing its parent's head does not. The four ACTIVE departments pass that
way. `unbacked_active_units` in `tests/test_org_span.py` reports each failing
unit with its condition, and the record's must-fail fixtures N1 to N9 each
break one condition.

**Frozen list.** `tests/fixtures/org/active-units-m60.txt` is `main`'s list
mapped through `MOVES`: 205 ids, no unit added; `verification.formal` and
`verification.debug`, reused for departments, left it. Its pin is 205 and
sha256 `30905852b486f1f2aa6ebf5c767f61f8056f4ff8a4b25626c705053316b3ab43`.

**Planning.** Every representative request (50: the M48 golden set, M68's
requests and M71's six requests) plans task for task as before
but for the changes listed in `INTENDED`, among them the coverage gate's move
from the VP to the Simulation director, and, on an investigation asked for a
reproduction, the debug work stream's move to the Debug and Regression
director. Routing verification signoff away
from the department that produced the evidence is a separate wave 2 pull
request (G13 record, decision 2c).

**Status report.** A project saved under an earlier chart that names a moved
unit shows the saved unit id instead of failing.

**Counts.** Units 222 to 232, derived roles 704 to 720 (`scripts/status.py
--write`).

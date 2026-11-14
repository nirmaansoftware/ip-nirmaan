# Council record: grouping units and the activation rule (gate G13, 2026-11-14)

Gate G13 of the capability build-out record
(`council/records/2026-10-18-capability-buildout.md:668`, "New units enter as
placeholders and activate only by the activation rule", owner product-lead)
was ruled on by its owner. The founder chose, in session on 2026-11-14, that
the gate owner rules and the chair confirms: product-lead ruled,
verification-lead and qa-evidence gave input, and the chair confirms with the
amendments below and writes this record. It is not a founder matter: it adds
no spending, contract, counsel, sending, public name or licence term.

Read against ip-nirmaan `main` at 2359e40 (the positions read 590153c; between
the two, only `docs/ROADMAP.md` and three lines of
`src/nirmaan/org/validate.py` after line 181 changed, none of them cited for
the activation rule) and pull request #178 at head 89035d6 (branch
`org/w2-verification-cut`). The chair ran its checks on scratch copies of
`main` and of the head, outside the repository; nothing in the repository or
on any branch was changed.

A key is an agent review. Nothing here is a person's approval, a release, or a
claim that a design is ready to be made in silicon.

This record amends one rule (item 10 of the 2026-10-18 record) and changes no
script, check or gate by itself. Each pull request that implements it is
reviewed on its own.

## The question

#178 cuts Verification into the five departments the 2026-10-18 record draws
(section 4, lines 247 to 256; wave order, line 536). Four of them (Methodology
and Signoff `verification.methodology`, Simulation `verification.dynamic`,
Formal and Static `verification.formal`, Debug and Regression
`verification.debug`) have no skills or tools of their own and only group
units that were ACTIVE at M60. The fifth, Processor and Accelerator
(`verification.processor`), is a placeholder with placeholder children.

Under the rule as written (record item 10, lines 114 to 117) a new unit is
ACTIVE only if one of its own skills uses an AVAILABLE tool and has an eval
case judged by that tool. The four departments have no skill, so they cannot
be ACTIVE. They cannot be PLACEHOLDER either: `Organization.is_active`
(`src/nirmaan/org/organization.py:564-567`) makes a role active only when
every ancestor unit is ACTIVE, so every verification role would go inactive,
and `validate_organization` fails each DV, formal and CDC stage with no active
holder (`src/nirmaan/org/validate.py:154-157`, `:170-171`). qa-evidence
reproduced this (48 issues). #178 as it stands adds the four departments to
the frozen list (`tests/fixtures/org/active-units-m60.txt`, 205 to 209 ids),
which key 2 failed as getting around G13.

Options in the brief: (A) a grouping unit may be ACTIVE when it adds no skill
or tool and its children are ACTIVE by the rule, and the frozen list changes
only by renames; (B) the record's section 4 and wave order count as the
activation, so the list may name the departments (the PR as it stands); (C)
change `is_active` so a PLACEHOLDER parent does not deactivate ACTIVE
children.

## Facts checked

Each fact below was checked by the chair on the scratch copies unless a seat
is named.

1. The brief's wording of (A), "all its children ACTIVE", is false for #178:
   `verification.dynamic` has two PLACEHOLDER children, `gate_level_power`
   and `emulation` (head `src/nirmaan/company/org_chart.py:191`, `:193`).
   Found by all three seats.
2. With the frozen list changed by renames only, `unbacked_active_units`
   (`tests/test_org_span.py:57-72`) flags exactly the four new departments and
   nothing else (verification-lead; confirmed). The renamed list has 205 ids:
   `MOVES` in the head's `tests/test_verification_departments.py:73` maps the
   26 verification ids frozen on `main` one to one. Its sha256, computed as the
   pin test computes it (`tests/test_org_span.py:105`), is
   `30905852b486f1f2aa6ebf5c767f61f8056f4ff8a4b25626c705053316b3ab43`
   (qa-evidence; the chair got the same digest).
3. Two frozen ids are reused for different units at the head:
   `verification.formal` and `verification.debug` now name departments, and
   the M60 units moved to `verification.formal.proof` and
   `verification.debug.analysis`. Frozen ids skip the backing check
   (`tests/test_org_span.py:62`), so a skill later given to either department
   would never be checked (verification-lead). One detail is corrected: at
   M60 `verification.debug` held skills of its own (`debugging`,
   `root_cause_analysis`), but `verification.formal` held none (its skills sit
   on its practices). The risk stands either way, because the skip is by id.
   `verification.debug.triage` and `verification.formal.equivalence` keep their
   ids and stay the same units (practices promoted to teams), so they stay in
   the list.
4. Grouping is already normal. `main` has 20 ACTIVE units with children and
   no skills or tools of their own (product-lead; confirmed). Three of them sit
   on another such unit (`implementation.pd.power`, `product.programs`,
   `product.projects`); all three are in the frozen list.
5. Every ACTIVE child of the four departments is in the renamed frozen list.
   None of the four needs a new grouping unit below it; two of their frozen
   children (`verification.dynamic.coverage`, `verification.formal.proof`) are
   themselves grouping units, which is allowed because they are frozen.
6. The four new directors hold `mgmt.delegate`, `mgmt.plan`, `mgmt.track` and
   `signoff.verification`, and their tools include `approval.grant`; every
   capability and tool of each is held by `verification.vp` (qa-evidence;
   confirmed). In today's code a generated head's capabilities come only from
   skills inherited from its ancestors and from its level profile
   (`src/nirmaan/org/organization.py:240-262`), so a unit with no skills,
   tools or explicit roles adds none.
7. Active holders of `signoff.verification` at DIRECTOR or above go from 2
   (`exec.cto`, `verification.vp`) to 6 (the four directors added). On 5 of 12
   `gate.verification` tasks in the 44 representative requests, the approver
   moves from the VP to the Simulation director (verification-lead's plan run;
   pinned as intended at the head's `tests/test_verification_departments.py:149-150`).
   The gate itself is unchanged: `signoff.verification`, minimum level
   DIRECTOR, `human_required` kept (`src/nirmaan/company/governance.py:93-95`).
8. Option (C), simulated by verification-lead: the chart builds, but the four
   inactive directors sit in the escalation paths of all 44 requests.
9. Section 4 draws Processor and Accelerator (lines 255 to 256) and
   gate-level and power-aware simulation without a placeholder mark (marks
   defined at lines 225 to 226), and #178 keeps both as placeholders
   (product-lead, qa-evidence).
10. At head 89035d6 no milestone number is reserved for #178: the last row of
    "Milestone numbers" on `main` is M73 (`docs/ROADMAP.md:125`), the branch
    adds no row, and it has no `docs/history/MNN-<slug>.md` file and no line
    in `docs/history/README.md`. CLAUDE.md lines 43 to 46 require all three.

## Decisions

### 1. G13: option A, amended as the owner ruled; confirmed

Supported by product-lead (owner, A amended), verification-lead (A, with an
amended test) and qa-evidence (A, corrected). (B) is rejected by all three:
section 4 also draws units that stay placeholders (fact 9), so treating it as
the activation proves too much, and it makes the frozen list untrue (fact 3).
(C) is rejected by product-lead and verification-lead (fact 8: it changes what
PLACEHOLDER means at every level and leaves inactive roles in live escalation
paths); qa-evidence took no view on (C) beyond noting that validation and
routing depend on `is_active`.

The chair confirms the owner's ruling. A unit that only groups ACTIVE units
adds no capability (facts 4 and 6), so making it ACTIVE is not an activation.
The chair amends the owner's wording in two places, both from the inputs: the
head-role condition (decision 2b) and the loss of the exemption when a
grouping unit later gains a skill, tool, ladder or explicit role
(verification-lead, must-have 3). Placeholder children are allowed (fact 1).

**New wording of record 2026-10-18, section 2, item 10** (replacing lines 114
to 117; the implementing pull request keeps the earlier wording beside it, as
below):

> 10. **Activation rule.** A unit added after this record enters as
>     PLACEHOLDER. It becomes ACTIVE only in a PR that shows either (a) one of
>     its skills uses an AVAILABLE tool and has an eval case judged by that
>     tool, or (b) it is a grouping unit: it has no skills, tools, ladder or
>     explicit roles of its own; at least one of its children is ACTIVE, and
>     every ACTIVE child is in the frozen list or meets (a); and its head holds
>     no capability or tool that the head of its parent unit does not hold. A
>     new grouping unit never counts as the ACTIVE child of another new
>     grouping unit. A grouping unit that gains a skill, tool, ladder or
>     explicit role must then meet (a). The frozen list never gains a unit: it
>     changes only when a unit in it is removed or moved, and an id reused for
>     a different unit leaves it. A unit in the chart is never an offer.
>     (Amended 2026-11-14 by council record 2026-11-14-g13-grouping-units.
>     Earlier wording: "A unit added after this record enters as PLACEHOLDER.
>     It becomes ACTIVE only in a PR that shows one of its skills uses an
>     AVAILABLE tool and has an eval case judged by that tool. A unit in the
>     chart is never an offer.")

"The frozen list" is `tests/fixtures/org/active-units-m60.txt`. "Its head" is
`Organization.head_of(unit)` (`src/nirmaan/org/organization.py:438`).

### 2. The open differences

**(a) A grouping unit may not sit on another new grouping unit.** product-lead
(owner): no stacking. qa-evidence: a child may count when it is itself a
grouping unit. verification-lead: "every child ACTIVE by the rule", read either
way. Chosen: no stacking, the owner's ruling. Reasons: #178 does not need it
(fact 5); the frozen units that already stack (fact 4) are untouched, because
the rule applies only outside the list; a narrow rule is cheap to widen by a
later ruling with its own fixture, while a wide one is hard to narrow once
units depend on it; and with stacking a chain of new units becomes ACTIVE with
the only real check one or more levels down, out of the reviewer's sight.
The cost is real and recorded: a new unit with two new grouping levels (for
example a placeholder division in section 4 activated with new departments
over new teams) cannot pass under this wording. The first wave that needs that
comes back to the gate owner before its pull request is cut, with
qa-evidence's form (every ACTIVE child frozen, backed, or a grouping unit that
itself passes) as the ready alternative. Dissent: qa-evidence.

**(b) The head-role guard: adopted.** Proposed by qa-evidence and
verification-lead; product-lead's wording did not have it and does not oppose
it. The head of a grouping unit holds no capability and no tool that the head
of its parent unit does not hold. It is checked on the head only
(`Organization.head_of`), as both inputs worded it: the other generated roles
of a grouping team (manager, tech lead) take level-profile grants that every
team has, and the "no explicit roles" condition already covers anything a unit
adds by hand. In today's code the condition follows from the first one
(fact 6); it is kept as a guard against a later change to how heads get
capabilities, and its fixture (N9 below) proves it can fail.

**(c) Verification signoff routing (verification-lead's F5): named here, fixed
in a later wave 2 pull request, not in #178.** The move in fact 7 stays in #178,
pinned in `INTENDED`. Reasons: the gate is unchanged and still needs a
DIRECTOR or above holding `signoff.verification` with `human_required`
(`src/nirmaan/company/governance.py:93-95`), so this is not a loosening under
verification-lead's own checklist; before the cut the approver, the VP, also
headed the unit that produced the coverage, so the cut does not remove an
independence the plan had; and #178 is a reorganisation that plans task for
task but for the listed changes, already over the soft size cap with two
owning teams, so a routing change belongs in its own pull request with its own
plan-equivalence test. verification-lead's assumption is adopted as the
constraint for that pull request: the approver of a `gate.verification` task
is never the head of the department whose unit produced the evidence. Whether
that approver is the VP or Methodology and Signoff (which holds the signoff
team, `verification.methodology.signoff`) is verification-lead's choice in
that pull request's design doc; no position chose between the two
(verification-lead's confidence on the remedy is medium), and the chair does
not choose for it. It takes its own milestone number, lands before wave 2 is
closed, and its founder class, if any, is whatever the review map computes.

### 3. What #178 changes before key 2 runs again

1. **Frozen list: renames only.** `tests/fixtures/org/active-units-m60.txt`
   is `main`'s list with each id mapped through `MOVES`: 205 ids, without
   `verification.methodology`, `verification.dynamic`, `verification.formal`
   or `verification.debug`. The pin (`tests/test_org_span.py:106-108`) becomes
   205 and the digest the author recomputes from the file. The chair and
   qa-evidence both computed
   `30905852b486f1f2aa6ebf5c767f61f8056f4ff8a4b25626c705053316b3ab43`; if the
   author's digest differs, the list is not the renamed list, and the
   difference is found before the pin is written, never copied from here.
2. **The moved-list test** (head `tests/test_verification_departments.py:254-260`)
   asserts the verification entries equal `{MOVES[u] for u in was_active}`,
   with no departments added.
3. **The guard.** `unbacked_active_units` (`tests/test_org_span.py:57-72`)
   passes a unit outside the frozen list when it meets (a) as today or is a
   grouping unit under the new item 10 (b). It reports each failing unit with
   the condition it fails, so each fixture asserts its exact list of units and
   reasons. The shipped chart passes with zero units reported.
4. **Must-fail fixtures**, each breaking one condition, built on the #178
   chart. The chair ran a prototype of each on the scratch copy of the head;
   every one fails as listed and the shipped chart passes.

   | Id | Mutation | Must fail with |
   |---|---|---|
   | N1 | `verification.methodology` gets skill `debugging` (held by `verification.vp`; it uses no tool, so it is never backed) | `verification.methodology`: own skill |
   | N2 | `verification.methodology` gets tool `git.read` (held by `verification.vp`) | `verification.methodology`: own tool |
   | N3 | `verification.methodology` gets `ladder=KNOWLEDGE_LADDER` | `verification.methodology`: own ladder |
   | N4 | an explicit role (`generated=False`) in `verification.methodology`, reporting to its director | `verification.methodology`: explicit role |
   | N5 | a new ACTIVE department `verification.fixture` under `verification` with two PLACEHOLDER children that declare missions | `verification.fixture`: no ACTIVE child |
   | N6 | a new ACTIVE department `verification.fixture` under `verification` with no children | `verification.fixture`: no ACTIVE child |
   | N7 | a new ACTIVE department `verification.fixture` whose only child is a new ACTIVE team with skill `code_coverage` (its tool is not AVAILABLE with a judging case) | `verification.fixture`: ACTIVE child neither frozen nor backed; the team: unbacked |
   | N8 | stacking: a new ACTIVE department `verification.fixture`, a new grouping team `verification.fixture.group` under it, and the frozen practices `verification.dynamic.coverage.code` and `verification.dynamic.coverage.functional` moved under that team | `verification.fixture` only: its one ACTIVE child is a new grouping unit (the team itself passes) |
   | N9 | the DIRECTOR level profile gains capability `signoff.implementation`, which `verification.vp` does not hold | the four new departments: head holds what the parent head does not (frozen departments are not checked) |

   N5 and N6 build (the chart validates) because the fixture units add no
   stage holder; N9 mutates a profile, not a unit, because in today's code
   that is the only way a grouping unit's head can exceed its parent's
   (decision 2b).
5. **Text.** `docs/ORG_SPAN_RULE.md` (head lines 72 to 86) and the module
   docstring and pin comment of `tests/test_org_span.py` (lines 7 to 9 and
   102 to 104) state the amended rule: the list never gains a unit, renames
   only, and grouping units pass by the test, not by the list. This closes
   key 2's minor finding on line 103.
6. **Kept.** The plan-equivalence test and its `INTENDED` set, with the
   coverage-gate move named (decision 2c). Every later grouping pull request
   keeps a plan-equivalence test of its own.

### 4. Key 2's milestone finding on #178

The finding (no milestone reserved, no history file; CLAUDE.md lines 43 to 46)
is open at head 89035d6 (fact 10). The author has claimed M77. That closes the
finding when, on a new head: `docs/ROADMAP.md` "Milestone numbers" has an M77
row marked reserved; `docs/history/M77-<slug>.md` exists and names its design
(`docs/HIERARCHY_FIXES.md` section 5 is accepted as the design doc, because
CLAUDE.md asks for a design doc in `docs/`, not a new file) and its tests; and
`docs/history/README.md` has its one line. M77 is free on `main` and on every
open branch today. The number is reserved late, after the branch was cut; the
history file says so rather than implying otherwise. A claim outside the
repository does not close a key-2 finding; key 2 re-runs on the new head and
checks the three files.

### 5. Order

1. A council pull request adds this record, its line in
   `council/records/README.md`, and the new item 10 wording in the 2026-10-18
   record. It merges first.
2. #178 merges `main`, makes the changes in decision 3 and the M77 files in
   decision 4, and gets its two keys on the new head. It merges only after
   step 1 is on `main`, so `main` never holds code that contradicts item 10.
3. The signoff routing pull request (decision 2c) follows, in wave 2.

The `needs-founder` stop on #178 came from the loop, not from a founder class
(the PR declares none); this ruling answers it, and the stop can be cleared
once step 2 is pushed.

## Gates

| Gate | Owner seat |
|---|---|
| Item 10 of the 2026-10-18 record carries the wording in decision 1, with the earlier wording kept, merged before #178 | product-lead |
| Frozen list is `main`'s list renamed through `MOVES` (205 ids); the author's recomputed digest matches the one in decision 3; the moved-list test asserts no unit added | qa-evidence |
| Grouping guard in `tests/test_org_span.py` with fixtures N1 to N9, each failing with its listed units and reasons; the shipped chart reports none | product-lead |
| Plan-equivalence test and `INTENDED` kept on #178 and on every later grouping pull request | verification-lead |
| M77 row, `docs/history/M77-<slug>.md` and its README line on #178's head; key 2 re-run on that head | chair |
| Verification signoff routing: a separate wave 2 pull request, before wave 2 is closed; the approver is never the head of the department that produced the evidence | verification-lead |
| A cut that needs a new grouping unit over another new grouping unit comes to the gate owner for a ruling before its pull request is cut | product-lead |

## Open questions, sent to owners

- verification-lead: VP or Methodology and Signoff as the approver of
  `gate.verification`, in the routing pull request's design doc.
- product-lead: which later wave, if any, needs two new grouping levels at
  once (the owner's assumption is none in the next waves).

## Dissent

- qa-evidence: a grouping unit should be allowed to sit on another grouping
  unit, so long as every ACTIVE unit below it is frozen, backed or itself a
  passing grouping unit. Overruled for now (decision 2a), with a trigger to
  revisit.
- qa-evidence also judged its confidence that the guard is enough as medium;
  the N1 to N9 fixtures and the routing gate are the chair's answer, not a
  proof.

No seat dissented from rejecting (B) or (C). verification-lead's request that
the ruling name the gate move and that wave 2 route verification signoff
elsewhere is adopted (decision 2c), not overruled.

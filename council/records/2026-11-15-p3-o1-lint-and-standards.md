# Council record: the lint and coding standards practices (P3-O1, 2026-11-15)

Item 11 of section 2 of the capability build-out record
(`council/records/2026-10-18-capability-buildout.md:131-134`) says sibling
practices with identical skill sets "get distinct skills or merge during their
department's wave. This is a wave exit criterion". In the RTL pilot's wave the
item applies to one pair: the Lint and Coding Standards practices of the RTL
Quality team. The pilot retrospective
(`council/records/2026-11-14-pilot-retrospective.md`, decision 1) keeps the
pilot's exit open and does not choose between the two. This record chooses.

Five seats gave round 1 positions independently (design-architect,
eda-tooling, verification-lead, qa-evidence, product-lead); the chair decided.
The meeting was kept to the seats that own what the choice touches: the RTL
practices and gate G11, the team that owns `org_chart.py`, the pilot's
evidence, the claims, and gate G13. Read against ip-nirmaan `main` at a518b7d.
The chair and qa-evidence ran their checks on scratch copies outside the
repository. This record changes no code, test, fixture or count: the pull
request that implements it is reviewed on its own.

A key is an agent review. Nothing here is a person's approval, a release, or a
claim that a design is ready to be made in silicon.

## Who decided what

The council decided every item below. The founder was away. That the council
rules now, instead of waiting, is the orchestrator session's answer on the
founder's in-session instruction of 2026-11-14 to go ahead with its own
recommended answer on open questions. It is not a founder decision, and the
founder can overrule it. The matter is not reserved for the founder: it adds
no spending, contract, counsel, sending, public name or licence term.

## The question

Options in the brief: (A) distinct: the standards practice drops `rtl_lint`
and keeps `coding_standards`; (B) merge the two practices into one unit; (C)
another option a seat can defend.

## Facts checked

Each fact was checked by the chair on a scratch copy of `main` at a518b7d,
and again by qa-evidence from the code, unless a seat is named.

1. `src/nirmaan/company/org_chart.py:148-153`: the team `design.rtl.quality`
   (RTL Quality) has four practices: lint (`rtl_lint`), standards
   (`coding_standards`, `rtl_lint`), synthesis (`synthesis_awareness`) and
   review (`code_review_practice`, `change_impact_analysis`). The team itself
   holds `rtl_lint` and `coding_standards` (line 153), and every role in the
   team inherits them.
2. `src/nirmaan/company/skills.py:336-342`: the `rtl_lint` card includes
   `coding_standards`, uses the tool `lint.run`, provides the capability
   `rtl.lint` and has a knowledge document. The `coding_standards` card has no
   tool, no document and provides no capability.
3. On the built organization (232 units, 720 roles), at each of the four
   ladder levels the lint role and the standards role hold the same skills,
   the same effective skills, the same capabilities and the same tools. It is
   the only such pair of ACTIVE sibling practices in the Design division.
4. Option A as worded changes nothing. With `rtl_lint` removed from the
   standards practice, all four comparisons of fact 3 are still identical,
   because of the team's own skills and the card's include.
5. A real option A needs more. If the team stops holding the two skills, the
   standards, synthesis and review roles, the manager and the tech lead lose
   the skill `rtl_lint` and the capability `rtl.lint` (holders fall from 14 to
   3), and the synthesis roles lose `coding_standards`, which the stage
   `rtl-quality` requires together with the capability `rtl.quality` before
   `gate.rtl` (`src/nirmaan/company/workflows.py:219-221`). Even then every
   non-intern role in the team keeps the tool `lint.run` (qa-evidence). The
   other way is to cut the include on the `rtl_lint` card, which changes that
   card and so its skill digest (`src/nirmaan/evals/cases.py:76-87`).
6. The flow has one stage for both: `rtl-lint`, titled "Lint and coding
   standards", with one piece of evidence, a `lint.run` run
   (`src/nirmaan/company/workflows.py:216-218`). `lint.run` has one backend, a
   Verilator lint run (`src/nirmaan/integrations/eda.py:428`). It is language
   lint: it checks no naming, reset or clocking rule (eda-tooling). The
   standard the `coding_standards` card names exists in the repository only as
   a name.
7. Option B: with `design.rtl.quality.standards` removed and
   `design.rtl.quality.lint` kept under its id, there are 231 units and 716
   roles. RTL Quality has 3 child units, inside the span rule's 3 to 8
   (`docs/ORG_SPAN_RULE.md`, section 2), and `shape_issues` is empty. Only the
   four standards roles go. No surviving role changes in skills, effective
   skills, capabilities or tools, whether or not the lint practice also lists
   `coding_standards` (qa-evidence measured both forms). Roles holding
   `rtl.lint` go from 14 to 11.
8. Both practices are in the frozen list
   (`tests/fixtures/org/active-units-m60.txt:57,59`). The list "changes only
   when a unit in it is removed or moved" (`docs/ORG_SPAN_RULE.md`, section
   4), and `tests/test_org_span.py:144-152` pins its count, 205, and a sha256.
   Under B the list holds 204 ids. A frozen id skips the backing check
   (`tests/test_org_span.py:98`), so the surviving lint id needs no eval
   case. A new id would need one: an eval case that names one of its skills
   and is judged by that skill's AVAILABLE tool. No case under `evals/` names
   `rtl_lint` or `coding_standards`.
9. `council/seat-map.yml` and `.github/review-teams.yml` name neither
   practice. `tests/test_nirmaan_org.py:59` names `design.rtl.quality.lint`.
   No file under `tests/fixtures`, `evals`, `docs`, `knowledge` or `site`
   names a role of either practice. The site's tiles are release snapshots
   and the hero shows no RTL Quality role (product-lead).
10. Levels and records. `capability/levels.json:301-311` shows `rtl_lint` with
    a document, no check record and no level; `coding_standards` is not
    listed. The committed trials record eight skills, neither of these two,
    and all seven pilot cases seat the stage `rtl-implementation`, owned by
    roles of `design.rtl.design` and `design.rtl.interface`
    (verification-lead). A skill digest covers the card and its document only
    (`src/nirmaan/evals/cases.py:76-87`), and `org_chart.py` is not in the
    harness fingerprint's code list (`src/nirmaan/runtime/harness.py:152-165`).
11. With B applied on a scratch copy (the lint practice listing both skills),
    the chair ran `tests/test_org_span.py`, `tests/test_nirmaan_org.py`,
    `tests/test_seat_map.py`, `tests/test_nirmaan_hierarchy.py`,
    `tests/test_capability_levels.py` and
    `tests/test_verification_departments.py`: all pass except the frozen
    list's pin, as intended. `scripts/status.py --check` reports the two
    counts in `docs/ROADMAP.md:56-57` (232 units, 720 roles) and nothing else.
    The chair's run of the whole suite was stopped part way with no failure
    by then; the whole suite is the follow-up pull request's CI.

## Decisions

### 1. Merge (option B)

The Coding Standards practice `design.rtl.quality.standards` is removed. The
Lint practice `design.rtl.quality.lint` is the one practice for lint and
coding standards. All five seats chose B.

Why. The two practices are one job today: one stage, one capability, one tool,
one piece of evidence (fact 6), and a standards practice has nothing of its
own to be checked on (fact 2). Option A as worded is a distinction in name
only (fact 4), which the rule against faked work does not allow. A real option
A either changes who can staff a stage before `gate.rtl` or edits a skill card
(fact 5), and both fall in the window the retrospective keeps quiet until the
one read of levels. B is a removal that changes no surviving role (fact 7).

### 2. What survives

- The id `design.rtl.quality.lint`, the unit name "Lint" and the role noun
  "Lint Engineer", all unchanged. No role title in the chart changes.
- The practice lists `rtl_lint` and `coding_standards`, so the chart shows it
  took the standards work over. The team `design.rtl.quality` keeps holding
  both skills.
- No new unit id, and `design.rtl.quality.standards` is not reused (product-lead,
  as owner of gate G13: a new id is a new unit and must meet the activation
  rule).
- A rename of the unit, if wanted, is its own pull request after the one read
  of levels, and shows first that no work packet changes.

### 3. The frozen list

The follow-up removes exactly one line, `design.rtl.quality.standards`, from
`tests/fixtures/org/active-units-m60.txt`, and moves the pin in
`tests/test_org_span.py` (204 ids and the new sha256) in the same pull
request. This is the removal the rule allows; the list gains nothing. RTL
Quality is then at 3 child units, the minimum: one more removal there fails
the span rule.

### 4. What the follow-up pull request changes, and what it never touches

Changes: `src/nirmaan/company/org_chart.py` (the two practice lines); the
frozen list and its pin; `docs/ORG_SPAN_RULE.md`, section 4 (the list's
current count and one sentence on this removal; its sentences about M57 and
M77 keep the counts of their day); a short entry in `docs/HIERARCHY_FIXES.md`;
`docs/ROADMAP.md` by `scripts/status.py --write` (231 units, 716 roles).
`capability/capability-map.md:154` names the team, not the practices, and
does not change.

Never touches: `src/nirmaan/company/skills.py`,
`src/nirmaan/company/workflows.py`, `src/nirmaan/company/tools.py`, any file in
the harness fingerprint's code list, the CLI, `evals/**`, `knowledge/**`,
`capability/levels.json` and `capability/records/**`, `site/**`,
`council/seat-map.yml`, `.github/**`, and history files (`docs/history/**`,
earlier council records), which keep the counts of their day.

### 5. Levels and records: nothing moves

B moves no level and makes no committed record stale. No skill card or
knowledge document changes, so no skill digest changes; the harness
fingerprint does not change; `rtl_lint` stays at no level until its check
record lands; `coding_standards` stays unlisted; no pilot trial seats a role
of either practice (fact 10). The quiet window of the retrospective (decisions
1d and 4, gate RT3) is respected: no harness code file, no tool definition and
no CLI change. Had the council chosen a real option A, it would have had to
say that the `rtl_lint` card's digest moves or that staffing before `gate.rtl`
changes; it did not choose it.

### 6. Item 11 for the RTL wave

With the merge on `main`, item 11 is met for the Design division: fact 3 found
no other pair. This closes the P3-O1 part of the retrospective's decision 1a.
It does not by itself meet the pilot's exit, which decision 1 of the
retrospective reads from `capability/levels.json`.

### 7. A Coding Standards practice later

It returns only as a new unit under the activation rule (a): its own skill
with a knowledge document and an AVAILABLE tool that checks the coding
standard, and an eval case judged by that tool. Until then, no text says that
a clean lint run shows conformance to the coding standard (design-architect).

## Dissent and positions not adopted

No seat dissented on the choice. Two smaller points:

- eda-tooling wanted the standards line deleted and the lint line left as it
  is. The chair has the lint practice list both skills, so the chart reads as
  a merge and not only a deletion; qa-evidence measured both forms and no role
  differs between them.
- The chair's scratch run used the unit name "Lint and Coding Standards". Four
  seats asked for no rename before the read; the chair agrees (decision 2).

## Gates

| Gate | Condition | Owner seat |
|---|---|---|
| O1-1 | The frozen list's diff is exactly one removed line, with the pin moved in the same pull request; no new id, no rename, no reused id | product-lead |
| O1-2 | The follow-up touches no file in decision 4's "never touches" list | eda-tooling |
| O1-3 | `scripts/capability_levels.py --check` passes with no diff to `capability/levels.json`, and the pull request shows the seven pilot cases' work packets identical before and after | verification-lead |
| O1-4 | The pull request shows 231 units, 716 roles and 204 frozen ids from CI on its head, and a role comparison with no surviving role changed | qa-evidence |
| O1-5 | No text claims that lint shows conformance to the coding standard | design-architect |

## Open, for the founder

1. The orchestrator's answer above (that the council rules now), to confirm or
   overrule.

Noted outside this decision: `docs/CAPABILITY_LEVELS.md` still says no result
record is committed on `main` (verification-lead), and the retrospective's
fact 1 predates the `rtl_lint` document (qa-evidence). Each is its owner's to
correct.

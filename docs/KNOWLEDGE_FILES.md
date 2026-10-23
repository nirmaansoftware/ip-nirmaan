# Knowledge file schema and checks (M62)

Item P1-07 of the 2026-10-18 council record on the capability build-out
(sections 9.2, 9.4, 9.11 and 9.12; gate G7): the rules every knowledge
document and skill card follows exist as checks before the first document is
written. The record is `council/records/2026-10-18-capability-buildout.md`; every rule this milestone takes from it
is also stated here in full, and the limits are this milestone's own.

## Where the rules live

- `knowledge/README.md`: the schema, for the writer.
- `src/nirmaan/org/knowledge_files.py`: the rules as code, so one test runs
  them over every document and over fixtures.
- `tests/test_knowledge_files.py`: every document under `knowledge/` (none
  yet) and every skill card pass; a good fixture passes; each rule has a bad
  variant that fails on that rule.
- `tests/test_status_docs.py`: the dash check also covers `knowledge/**` and
  `src/nirmaan/company/skills.py`.

## The tier is computed

`skill_tier(skill, tools)`: practising when one of the skill's tools is
`AVAILABLE`, otherwise knowledge only. A `CONTRACT_ONLY` tool gives knowledge
only: `c_programming`'s only tool is `compiler.run` (contract only), so its
static-analysis criterion computes as knowledge only. A document never
declares its tier; its first body line must open with the computed one
(`Practising:` or `Knowledge only:`).

## The skill card

The card is the skill's catalog entry, rendered for the size check as sorted
JSON of `Skill.model_dump(mode="json")` (the same form M58's skill digest
hashes). At most 2,000 characters: today the largest, `device_drivers`, is
1,828. The work item's figure of 1,388 matched none of the renderings tried
(sorted JSON, compact JSON, or the Domain section's lines), so the check fixes
this rendering and states it. A card also has no dash, level word or readiness
claim.

## A knowledge document

Front matter between `---` lines: `id` (`<division>/<skill_id>`, its own
path), `skill` (its file name), `as_of` and `review_by` (dates), `sources` (one
per line, `- <access> | <title> | <where>`), `licence_check`, `export_screen`
(`clear` or `flagged`), `writer` and `checker` (different). Checked:

| Rule | Fails |
|---|---|
| Every field present, dates as `YYYY-MM-DD` | a missing field or a bad date |
| Sources only `open` or `purchasable` | `member-only` or any other access |
| A different checker | the checker is the writer |
| Size | over 12,000 characters |
| Writing | an em or en dash; "expert", "industry level", "robust"; a readiness claim |
| Tier line | the first body line does not open with the computed tier |
| Held-out inputs | any line (30 characters or more) of a held-out eval input or a reference answer appears |
| `review_by` passed | a warning, not a failure |

What a test cannot judge stays with the reviewers: every claim cites a source;
nothing is copied from a specification; export-screened areas stay knowledge
only until counsel sets the scope.

## Not in this milestone

The loading path (M61), evidence levels (M63), any knowledge document, and the
review-teams rules for `knowledge/**` (P1-10, founder class).

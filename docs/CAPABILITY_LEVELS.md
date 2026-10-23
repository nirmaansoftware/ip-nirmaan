# Evidence levels (M63)

Item P1-09 of the 2026-10-18 council record on the capability build-out
(section 9; gates G4, G5 and G17): a skill's evidence level is computed from
committed records, never typed, and today it is none for every skill.
The record is `council/records/2026-10-18-capability-buildout.md`; every rule this milestone takes from it
is also stated here in full, and the thresholds are this milestone's own.

## The scale

| Level | Only from |
|---|---|
| Knowledge | the document `knowledge/<division>/<skill_id>.md`, passing the M62 checks (`docs/KNOWLEDGE_FILES.md`), and a check record `capability/records/knowledge/<skill_id>.json` by a different session, naming the document's current sha256 and the sources read |
| Practised | committed, tool-judged eval result records under `evals/results/` (M45, M58) |
| Proven | the product's own seat run records on delivered work that passed review; no such record kind exists yet, so no skill is Proven |

A skill's level is Practised when a Practised group counts, else Knowledge when
its check record counts, else none. The levels are not the seniority band
(M56), which comes from a role's ladder rung and says nothing about evidence.

## Practised

`practised()` reads every run record with `load_evidence` (M58), so a replay or
a trial with a human attestation refuses the whole record; refused records are
listed in `refused_records`. A trial counts only for the skills its case names
(`EvalCase.skills`), and only when every held-out check of the case uses a
scorer that requires a tool and the trial has judge runs; any other trial is
listed in `not_tool_judged` with its outcome and never raises a level.

Trials are grouped by skill, model and the skill digest recorded with the trial
(card plus knowledge document, M58). A group counts when all hold:

- at least 5 trials;
- a 95 percent Wilson lower bound of at least 0.5 (5 of 5 gives 0.566; 4 of 5
  gives 0.376);
- every trial re-judged clean: `rejudge.json` in the record, written by
  `nirmaan eval rejudge <record> --write`, says `same` for it;
- for a skill of the design or verification domain (`MUST_FAIL_DOMAINS`, data in
  `src/nirmaan/company/evidence.py`), every case it rests on has
  a must-fail control (a held-out check with `mutants`, M58);
- the group's digest is the skill's current digest. A changed card or
  document, including a knowledge document added later, makes the group stale.

Each group in `capability/levels.json` lists its records, cases, counts and
every reason it does not count.

## The generator

`scripts/capability_levels.py` prints the levels, `--write` writes
`capability/levels.json`, and `--check` exits 1 when the committed file
differs from what the records give. `tests/test_capability_levels.py` runs the
check, so a record committed without regenerating the file fails CI.

On main the file reports zero Knowledge, zero Practised and zero Proven: no
document, check record or result record is committed.

## Tests

Fixture repositories in `tests/test_capability_levels.py`: 5 of 5 with a clean
re-judge and a must-fail control is Practised; 4 of 5, fewer than 5 trials, no
re-judge, a failed re-judge or no must-fail control is not; a changed card or a
later document makes it stale; replays, attestations and trials not judged by a
tool never count; a case's other skills get nothing; nothing is Proven;
Knowledge needs a check record by a different session, with sources, naming the
current document.

## Not in this milestone

No level appears on a public page (section 9.1). Proven waits for a record kind
of delivered work. DFT (fault simulation) and physical design (the CI job on
the head SHA) grading rules are not encoded yet; their skills can be Practised
only through tool-judged eval records like any other.

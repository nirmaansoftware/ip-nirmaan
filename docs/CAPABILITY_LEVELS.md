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
scorer that requires a tool; a trial of any other case is listed in
`not_tool_judged` with its outcome and never raises a level. On a tool-judged
case, a trial with no judge run (the work was blocked, declined or refused
before it reached review) is a failed trial of its group, whatever its result
says, and the group's `unjudged` counts it. It is never left out: leaving it
out once read a 4 of 5 case as 4 of 4. This only makes a group harder to count
(section 9, item 6: Practised only from tool-judged trials, at least 5 of
them, with a Wilson lower bound of at least 0.5; a blocked trial is one of
those trials and it failed).
A trial run without knowledge documents (M67, `eval run --without-knowledge`,
the ablation; `docs/EVAL_ABLATION.md`) is labelled `"knowledge": "off"` in its
run manifest and in the trial. Labelled off in either, it is taken out first,
listed in `without_knowledge` with its outcome and the reason, and never counts
toward any level; its skill digests are the cards alone, so with both labels
edited back a skill with a document is still stale.
A calibration trial (M76, `nirmaan eval outside`, an outside benchmark;
`docs/OUTSIDE_CALIBRATION.md`) is labelled `"purpose": "calibration"` in its run
manifest and in the trial. Labelled so in either, it is listed in `calibration`
with the reason "outside calibration" and never counts toward any level; the
record is not judged as evidence at all, so a replay of one is no refusal. A
record that mixes calibration trials with evidence trials is refused, so one
stray label never takes the other trials out of the levels. A calibration
trial's skill digest covers the card and the knowledge document the seat was
given, as for any trial.

Trials are grouped by skill, model, the skill digest recorded with the trial
(card plus knowledge document, M58), the harness recorded with it (M73,
`docs/HARNESS.md`) and the CLI version the runtime called the model through
(the claude-code runtime's `claude --version`, which is in that harness). A
group counts when all hold:

- at least 5 trials;
- a 95 percent Wilson lower bound of at least 0.5 (5 of 5 gives 0.566; 4 of 5
  gives 0.376);
- every trial re-judged clean: `rejudge.json` in the record, written by
  `nirmaan eval rejudge <record> --write`, says `same` for it;
- for a skill of the design or verification domain (`MUST_FAIL_DOMAINS`, data in
  `src/nirmaan/company/evidence.py`), every case it rests on has
  a must-fail control (a held-out check with `mutants`, M58);
- the group's digest is the skill's current digest. A changed card or
  document, including a knowledge document added later, makes the group stale;
- the group's harness is the current default harness at the group's CLI
  version (`harness_sha256(cli=...)`). A changed harness setting or harness
  code file makes the group stale, and a trial that records no harness
  ("harness not recorded", a record written before M73) never counts. Trials
  on two Claude Code versions are two groups, never pooled; a version that
  could not be read (`unknown`) never counts.

Each group in `capability/levels.json` lists its records, cases, counts
(`n`, `passed`, `unjudged`) and every reason it does not count.

## The generator

`scripts/capability_levels.py` prints the levels, `--write` writes
`capability/levels.json`, and `--check` exits 1 when the committed file
differs from what the records give. `tests/test_capability_levels.py` runs the
check, so a record committed without regenerating the file fails CI.

On main the file reports eight Knowledge (`apb`, `arbitration`, `axi`,
`buffering_flow_control`, `control_logic_design`, `fsm_design`,
`pipeline_design` and `rtl_design`, each from its check record under
`capability/records/knowledge/`), zero Practised and zero Proven: no result
record is committed.

## Tests

Fixture repositories in `tests/test_capability_levels.py`: 5 of 5 with a clean
re-judge and a must-fail control is Practised; 4 of 5, fewer than 5 trials, no
re-judge, a failed re-judge or no must-fail control is not; 4 passes and 1
blocked trial are 5 trials with 4 passed, not Practised, and a trial with no
judge run on a tool-judged case is a failure even when its result says passed;
a changed card or a
later document makes it stale; replays, attestations, trials of a case not
judged by a tool and trials run without knowledge documents (either label)
never count; a changed harness makes the group stale and a trial with no harness recorded never counts (M73); trials on two CLI versions are two groups, a CLI version edited on the trials is stale, and an unread one never counts; a case's other skills get nothing; nothing is Proven;
Knowledge needs a check record by a different session, with sources, naming the
current document.

## Not in this milestone

No level appears on a public page (section 9.1). Proven waits for a record kind
of delivered work. DFT (fault simulation) and physical design (the CI job on
the head SHA) grading rules are not encoded yet; their skills can be Practised
only through tool-judged eval records like any other.

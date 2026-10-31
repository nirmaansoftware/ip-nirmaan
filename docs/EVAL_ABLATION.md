# Running evals without knowledge documents (M67)

The capability build-out council record of 2026-10-18
(`council/records/2026-10-18-capability-buildout.md`, section 9.3) asks the
pilot to run an ablation: the same cases with and without knowledge, to show
that the documents change what a seat produces. Its pilot exit (section 10)
names "the ablation run". This milestone adds the switch for it. It runs no
model; the recorded ablation batch is a later pull request.

## The switch

```sh
nirmaan eval run --runtime claude-code --trials 5 --seats rtl --without-knowledge
```

`--without-knowledge` works with `--runtime` and with `--replay`, and with
every other option of `eval run`.

## What the seat is given

`assemble(engine, task_id, role, knowledge=False)` builds the packet with no
knowledge document (M61, `docs/KNOWLEDGE_PACKET.md`): `domain.documents` is
empty. Everything else is what it is with knowledge: the skills the task
carries, their cards (procedures, constraints, failure modes, validation
criteria and the list of knowledge sources the card names), the role card,
the project, the upstream artifacts, the tools and the memory. Since no
document is read, none can make the seat decline for being missing or over
the domain cap.

`run_task(..., knowledge=False)` assembles every packet of the task that way,
also the ones it rebuilds after a refused attempt. `evaluate` and
`record_trial` pass the flag to the seat's `run_task`; the upstream stages a
case fixes are unchanged, since their answers are the case's own files.

## What the record says

A run without knowledge is labelled in three places, so one edited field
never turns it into evidence:

- the record's directory name ends in `-without-knowledge`, for people;
- `manifest.json` has `"knowledge": "off"`;
- every trial file has `"knowledge": "off"`, and its skill digests are the
  digests of the skill cards alone (`skill_digest(..., knowledge=False)`),
  which is what the seat was given.

A run with knowledge writes `"knowledge": "on"` in both files; a record
written before this milestone has no field and reads as `on`.

`knowledge_off(manifest, trial)` in `src/nirmaan/evals/records.py` says
where a trial is labelled off. Either label is enough.

## How it is used

- **Evidence levels** (M63, `docs/CAPABILITY_LEVELS.md`). Before anything
  else, `practised()` takes every trial labelled off, in its manifest or in
  the trial, out of the groups and lists it under `without_knowledge` in
  `capability/levels.json`: record, case, trial, outcome, and the reason
  ("run without knowledge documents (knowledge: off in ...): never counts
  toward a level"). Such a trial raises no skill to any level. To turn one
  into evidence someone would have to edit both labels, and even then, for a
  skill with a document, its card-only digest is not the skill's current
  digest, so the group is stale and does not count.
- **Re-judging** (M45). `rejudge` replays a trial with the knowledge setting it
  was recorded with, so its packets are the ones the seat answered.
- **Learning** (M42, `docs/EVAL_PROPOSALS.md`). `load_results` does not read a
  trial labelled off, in its manifest or in the trial: a seat failing without its documents shows what the
  documents add, not a regression to propose a change for.
- **History.** `nirmaan eval history` shows "without knowledge" beside such a
  record.

The ablation's comparison (pass rate with its interval, mutants killed,
attempts, refusals, tokens and time per trial, against the batch with
knowledge on the same commit) is made from the two records; it is not a
level and is not computed here.

## Tests

`tests/test_eval_without_knowledge.py`: on the arbiter case the owner's and
the reviewer's packets lose the arbitration document and nothing else; a
missing cited document no longer declines the seat; the evaluated seat's
prompts lack a cited document's text that they carry with knowledge; a run
record is labelled in its name, manifest and every trial with card-only
digests, re-judges clean, and a plain run still says `on`; the CLI switch
writes such a record and `eval history` shows it; M42 learning does not read
it, even with the trial files edited back to `on`. `tests/test_capability_levels.py`: trials labelled off never count and
are listed with the reason, beside a record that counts; either label alone
keeps them out; with both labels edited back the card-only digest leaves the
group stale.

## Not in this milestone

No model call and no committed result record: the recorded ablation batch,
with its rejudge, is its own pull request after the batch with knowledge, as
the pilot plans it.

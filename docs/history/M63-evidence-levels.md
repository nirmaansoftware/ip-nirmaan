# Milestone 63 - Evidence levels: Knowledge, Practised and Proven only from committed records, zero of each on main

A skill's evidence level must come from records, never from a typed claim
(capability build-out council record, section 9, item P1-09; pull request
#118, waiting for the founder). Design:
`docs/CAPABILITY_LEVELS.md`. Tests: `tests/test_capability_levels.py`.

**The generator.** `scripts/capability_levels.py` (`--write`, `--check`)
computes `capability/levels.json` with `nirmaan.evals.levels`. A test fails
when the committed file differs from what the records give.

**Knowledge** needs the skill's document and a check record by a different
session naming its current sha256 and the sources read
(`capability/records/knowledge/`).

**Practised** needs committed, tool-judged eval records for the case's own
skills: at least 5 trials, a 95 percent Wilson lower bound of at least 0.5, a
clean re-judge of every trial (`nirmaan eval rejudge --write` writes
`rejudge.json`), a must-fail control for design and verification skills, and
the skill's current digest; otherwise stale. Replays, attestations and trials
not judged by a tool never count.

**Proven** has no record kind yet, so nothing is Proven. On main every total is
zero.

# Milestone 67 - Evals without knowledge documents: the ablation switch

Part of the RTL small-block pilot (council record
`council/records/2026-10-18-capability-buildout.md`, sections 9.3 and 10).
Design: `docs/EVAL_ABLATION.md`. Tests: `tests/test_eval_without_knowledge.py`
and `tests/test_capability_levels.py`.

**The gap.** The record asks the pilot to run the same cases with and
without knowledge. `nirmaan eval run` had no way to leave the knowledge
documents out of the seat's packet, and nothing would have kept such a run
from counting toward an evidence level.

**The switch.** `eval run --without-knowledge` builds every seat packet with
no knowledge document (`assemble(..., knowledge=False)`, through `run_task`,
`evaluate`, `record_trial` and `record_run`). The skills and their cards
stay.

**The labels.** The record's name ends in `-without-knowledge`; its manifest
and every trial say `"knowledge": "off"`; each trial's skill digests are the
card alone. Records without the field read as `on`.

**Levels.** A trial labelled off in its manifest or in itself never counts
toward any level and is listed under `without_knowledge` in
`capability/levels.json` with the reason. Editing one label back changes
nothing; editing both still leaves a skill with a document stale.
`rejudge` replays with the recorded setting, and M42 learning does not read
such trials.

No model was called. The recorded ablation batch is a later pull request.

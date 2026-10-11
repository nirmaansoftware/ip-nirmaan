# Milestone 48 - Unified applicability, bounds, and limits

The principal-engineer review (section 5.1 items 1 to 3, risk 2,
recommendation 3) found the evidence-requirement vocabulary fragmenting:
five ways to say "this applies only when", three retry limits with two
precedence rules, and metric bounds encoded as a `max_`/`min_` prefix in the
tool-parameter namespace. Design: `docs/UNIFIED_APPLICABILITY.md`. Tests:
`tests/test_nirmaan_unified_applicability.py`, written first and failing, and
`tests/test_nirmaan_applicability_golden.py`, the characterization.

**Characterization first.** Before any change, a test planned 31
representative requests across all nine workflows and recorded, per task, its
limits and each requirement's tools, bindings, before-review flag, fixed
parameters and bounds, `yields`, and when it applies over every combination of
produced and upstream kinds (`tests/fixtures/applicability/plans.txt`). The
file is byte-identical after the refactor; only the test's accessors changed.

**One condition type.** `Condition` gained `on`, the name of a registered
condition kind with a declared phase (`plan` or `run`). Four are built in:
`features`, `produced`, `upstream`, `inputs`. `EvidenceRequirement.when` is a
tuple of clauses; `when_produced` and `when_upstream` are gone from the model.
One evaluator, `nirmaan.applicability.applies`, serves the planner, the
policy (`unsatisfied_requirements`, `evidence-before-review`), the runtime's
pre- and post-flight, and the work prompt (each kind describes its own
clauses). A clause of the other phase, or over facts the reader does not know
yet, is skipped. `FileInput.optional` stays a per-binding flag, since it is
per parameter, and is decided by the same evaluator over the `inputs` kind.
`validate` rejects an unknown kind, or a run-phase kind on a stage or variant.

**Bounds.** `EvidenceRequirement.bounds: tuple[Bound, ...]`, with
`Bound(metric, op, value)` and one text form (`latches<=0`). The broker checks
a passing run's reported metrics (`ToolOutcome.metrics`) against the bounds
it was given and records them on `ToolRun.bounds`; `satisfies` counts a run
only if it was checked against each of the requirement's bounds. The `max_`
and `min_` prefix families left the tool contracts, so such a parameter is
refused, and `max_chain_length` is only an input. `nirmaan task tool` takes
`--bound`. Every workflow and every test that fixed a bound as a parameter
was migrated.

**Limits.** `Limits(attempts, review_rounds, retries, on_failure)` on stages
and capabilities, with one resolver (`work/limits.py`): override, then stage,
then capability, then the default of 1. The runner and `TaskEngine.fail` both
use it, so retries are now resolved when used, like the other two, and a
capability can set them.

**Compatibility.** The old fields are accepted as constructor arguments and
migrate on load: a saved project loads, verifies its audit chain, and
re-saves stably. A fixed `max_`/`min_` parameter becomes a bound (it was one
then). A run saved before M48 has no `bounds` record and saves without the
key; it counts as checked against a bound it carried as a parameter.

**Intended differences** (outside the golden file): a bound passed as a
parameter is refused; a bound failure's summary is prefixed by the broker;
`nirmaan org tool` lists no `max_<metric>`; a saved run's legacy bound reads
as its stored text through `ToolRun.typed`; `runtime.limits` returns a
`Limits`.

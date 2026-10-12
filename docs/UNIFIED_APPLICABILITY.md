# Unified applicability, bounds, and limits (M48)

The principal-engineer review (section 5.1 items 1 to 3, risk 2,
recommendation 3) found the evidence-requirement vocabulary fragmenting. Each
parallel batch added a field to solve a local problem: five ways to say "this
applies only when", three retry limits with two precedence rules, and metric
bounds encoded as a prefix in the tool-parameter namespace. The code that
reads them (`work/policy.py`, the runtime's tool runs) is where silent
mis-gating would hide. This milestone gives each idea one representation and
one evaluator, and changes no behavior (section 6).

## 1. What existed before

### 1.1 Conditional applicability

| Mechanism | Added | Phase | Semantics | Read by |
|---|---|---|---|---|
| `StageTemplate.when: Condition` | M1 | plan | the stage is planned only when the request's features meet `all_of`, `any_of` and `none_of` | planner (`orchestrator/planner.py`: stage selection with all features; `_risk`, with the observed features, to name the assumptions a stage exists under); `org/validate.py` (feature names); `nirmaan org workflow` (prints it) |
| `Variant.when: Condition` | M1 | plan | one task per variant whose condition holds | planner, validate |
| `AssumptionRule.when: Condition` | M1 | analysis | an assumption is recorded only when the features meet it | `orchestrator/analyze.py`, validate |
| `EvidenceRequirement.when: Condition` | M27 | plan | the requirement is copied onto the planned task only when the features (observed and assumed) meet it | planner only |
| `EvidenceRequirement.when_produced: tuple[str]` | M26 | run | applies only when the task produced an artifact of one of these kinds; empty: always | `EvidenceRequirement.applies` (policy: `unsatisfied_requirements` over the task's recorded artifacts, `evidence-before-review` over the submitted drafts); runtime post-flight, inline, over the answer's files; the work prompt ("applies only if you produce a X file") |
| `EvidenceRequirement.when_upstream: tuple[str]` | M37 | run | applies only when the task builds on an upstream artifact of one of these kinds; empty: always | `applies` (policy, with `upstream_kinds`: the kinds of the dependencies' artifacts, seen through gates, computed only when some requirement asks); runtime pre- and post-flight (`_builds_on`, over the packet's upstream artifacts); the work prompt |
| `FileInput.optional: bool` | M41 | run | an upstream binding is left out when no approved upstream file of its kinds exists; when one exists, a passing run must have used it | runtime post-flight (no verified upstream path: the parameter is not filled); `evidence-before-review` (no approved, located upstream artifact: the binding asks nothing) |

`EvidenceRequirement.applies(kinds, upstream)` combined only `when_produced`
and `when_upstream`; the runtime's pre-flight checked only `when_upstream`
(the produced kinds are not known before the answer), its post-flight checked
both inline rather than through `applies`, and the plan-time `when` was read
by the planner alone. M44's `yields` is not a condition (it names files a
passing run writes) and is unchanged.

Readers that do not evaluate applicability: `views.py` and the export list a
task's requirements; `vplan.py` and `evals/runner.py` read `tools`, `files`
and `before_review`; upstream bindings are filled by the runtime and checked
by `evidence-before-review` (section 2.4).

### 1.2 Limits

| Field | Where | Counts | Precedence | Read by |
|---|---|---|---|---|
| `max_retries` (default 1), `on_failure` (default `retry_then_escalate`) | `StageTemplate`, copied onto `Task` at plan time | failures the owner reports (`TaskEngine.fail`): within `max_retries` the task returns to ready; after, it fails and, unless `on_failure` is `fail`, escalates | stage, else default; frozen on the task when planned | `work/engine.py` `fail` |
| `max_attempts` | `Capability` (default 1), `StageTemplate` (default None) | submissions the engine refuses in one review round (M26) | CLI, then stage, then capability, then 1; read when the seat runs | `runtime/base.py` `limits`, the runner and the loop |
| `max_review_rounds` | `Capability` (default 1), `StageTemplate` (default None) | submissions independent review sends back (M27) | as `max_attempts` | as `max_attempts` |

### 1.3 Metric bounds

A requirement's fixed parameters (`EvidenceRequirement.params`) were passed
to the tool, and a run counted only if it was made with each of them.
`integrations/eda.py` `_within_limits` then read every parameter named
`max_<metric>` or `min_<metric>` as a bound on the parsed metric of that
name: a passing run failed when the metric broke the bound, or was not
reported. The tool contracts declared `max_` (every EDA tool) and `min_`
(`sta.run`, `pv.run`, `dft.atpg`, `dft.atpg_transition`) as prefix families
so the broker would accept them. The workflows fixed these bounds:
`max_latches`, `min_test_coverage`, `max_text_bytes`, `max_drc_violations`,
`max_unconnected_supply_pins`, `max_lvs_mismatches`, `min_fill_shapes`,
`max_unannotated_nets` and `min_timing_corners`.

The namespace was shared with real inputs: `dft.scan_insert` takes
`max_chain_length`, which the runner also read as a bound on `chain_length`.

## 2. The design

### 2.1 One condition type

`Condition` stays the one predicate type and gains a field, `on`: the name of
a registered **condition kind** whose facts the clause tests. `all_of`,
`any_of` and `none_of` keep their meaning over that set. `on` defaults to
`features`, so every existing stage, variant and assumption condition is
unchanged, in code and in data.

A condition kind (`nirmaan/applicability.py`) declares:

- `name`, what `Condition.on` names;
- `phase`, `plan` or `run`: when its facts are known;
- `facts(Facts) -> Iterable[str] | None`: the set the clause tests, or None
  when this reader does not know it yet;
- an optional `describe(Condition)`: how the work prompt tells a seat about it.

Four kinds are built in:

| Kind | Phase | Facts |
|---|---|---|
| `features` | plan | the request's features |
| `produced` | run | the kinds of the artifacts the task produced (recorded, or the drafts being submitted) |
| `upstream` | run | the kinds of the artifacts the task builds on |
| `inputs` | run | the kinds of the approved upstream files actually available to the task |

`EvidenceRequirement.when` becomes `tuple[Condition, ...]`, a conjunction of
clauses of any kinds. `when_produced=K` is the clause `Condition(on="produced",
any_of=K)`, `when_upstream=K` is `Condition(on="upstream", any_of=K)`, and the
M27 feature condition is a `features` clause.

**One evaluator**, `applies(conditions, facts)`, is used by every reader. A
`Facts` names its phase and carries what the reader knows: the built-in fact
sets (values, or functions computed only if a clause asks, so the policy still
computes upstream kinds only when needed) and the reader's sources (`analysis`
and `requirement` at plan time; `state` and `task`, or `packet`, at run time)
for kinds that derive their own facts. The rules:

1. A clause whose kind has the other phase is skipped: plan-time clauses were
   decided when the task was planned, and run-time clauses cannot be decided
   at plan time.
2. A clause whose facts this reader does not know (None) is skipped. The
   runtime's pre-flight runs before the answer, so it does not know the
   produced kinds; as before, a check over other facts still runs.
3. Otherwise every clause must hold.
4. A clause naming an unregistered kind is an error, and `validate` reports it
   for every workflow, as it does for an unknown feature. A stage or variant
   condition must be of a plan-phase kind.

The readers, after:

| Reader | Phase | Facts it supplies |
|---|---|---|
| planner, stage and variant selection | plan | features (all), analysis, requirement |
| planner, requirements copied onto a task | plan | observed and assumed features, analysis, requirement |
| planner, `_risk` | plan | observed features |
| `unsatisfied_requirements` | run | produced (recorded artifacts), upstream (lazy), state, task |
| `evidence-before-review` | run | produced (submitted drafts), upstream (lazy), state, task |
| runtime pre-flight | run | upstream, packet (produced unknown) |
| runtime post-flight | run | produced (the answer's files), upstream, packet |
| optional upstream bindings (policy and post-flight) | run | inputs |
| work prompt | none | renders each clause with its kind's `describe` |

### 2.2 `FileInput.optional` stays a per-binding flag

The brief asked to fold `optional` into the condition where it fits. It does
not fit as a requirement condition, because it is genuinely per parameter:

- it never decides whether the requirement applies. The requirement still
  binds and its tool still runs (the firmware build runs with or without a
  map); only one parameter is left out;
- one requirement mixes optional and required bindings (`fw.test` takes `rtl`,
  required, and `map`, optional), so a requirement-level clause cannot say it;
- its predicate is fully determined by the binding's own kinds ("is an
  approved upstream file of these kinds available"), so a separate condition
  field would only repeat them, and could disagree with them;
- it carries an obligation a condition cannot: when the file exists, a
  passing run must have used it.

So the flag stays, and its test goes through the one evaluator as the clause
`Condition(on="inputs", any_of=binding.kinds)`. The `inputs` kind is also
usable in a requirement's `when`: every requirement reader (the policy's
`run_facts` and the runtime's facts) supplies the kinds of the approved,
located upstream artifacts available to the task (M52).

### 2.3 Bounds as a structured field

`EvidenceRequirement.bounds: tuple[Bound, ...]`, where
`Bound(metric, op, value)` with `op` `max` or `min` and a numeric value. Real
inputs stay in `params`.

- **Enforcement** moves from the EDA runner to the broker. `ToolBroker.invoke`
  takes `bounds`, and after a passing run checks each one against the metrics
  the binding reports (`ToolOutcome.metrics`, which the EDA runner fills from
  its parsed result). The semantics are the old ones: a passing run fails when
  a metric breaks its bound or was not reported, and the failure reads as
  before (`latches 1 exceeds max_latches 0`, `timing_corners 1 is below
  min_timing_corners 3`). Any tool that reports metrics can now be bounded.
- **Record.** `ToolRun.bounds` records the bounds a run was checked against.
  A run counts for a requirement only if it was checked against every one of
  the requirement's bounds, as it had to be made with every fixed parameter.
- **Tool parameters.** The `max_` and `min_` prefix families leave the tool
  contracts, so `max_latches=0` passed as a parameter is now refused by the
  broker, loudly, instead of being silently ignored. `max_chain_length` is an
  input of `dft.scan_insert` again and nothing else; the stitcher enforces it.
  `nirmaan task tool` takes `--bound latches<=0` (repeatable).
- **The runtime** passes each requirement's bounds with its fixed parameters,
  in pre- and post-flight.

### 2.4 Limits

The three limits count different events (a reported failure, a refused
submission, a review that sends work back), so they stay three numbers, but
in one object with one resolver.

`Limits(attempts, review_rounds, retries, on_failure)`, every field optional.
`StageTemplate.limits` and `Capability.limits` declare them. One resolver,
`work/limits.py` `limits_for(org, task, override)`, takes each field from the
first layer that sets it: the override (the CLI's `--attempts` and
`--review-rounds`), then the task's workflow stage, then its capability, then
the default (`attempts=1`, `review_rounds=1`, `retries=1`,
`on_failure=retry_then_escalate`). `runtime.limits` (the runner and the loop)
and `TaskEngine.fail` both use it.

How they relate: `attempts` bounds the engine's refusals within one review
round; `review_rounds` bounds the rounds; when either is spent, the runner
escalates. `retries` bounds the failures an owner reports with `fail`, and
`on_failure` says what happens after the last (`fail` fails without
escalating; the others escalate). A refusal or a review round is not a
reported failure, so the counts never mix.

The one change of rule: `retries` and `on_failure` were frozen onto the task
when it was planned, from the stage alone. They are now resolved when used,
like the other two, so a capability can set them. Every workflow resolves to
the values it planned before (the characterization checks it), and a project
saved before M48 drops the frozen copies on load.

## 3. Compatibility

**Old-form data** builds the new form: `EvidenceRequirement`, `StageTemplate`
and `Capability` accept the old fields as constructor arguments and convert
them in a `mode="before"` validator, so an extension written against the old
fields keeps working and a saved project migrates on load:

- `when=Condition(...)` (one condition, or its saved dict) becomes a one-clause
  tuple, or the empty tuple if unconditional;
- `when_produced` and `when_upstream` become `produced` and `upstream` clauses,
  after the feature clause, in that order (the prompt renders them in the same
  order as before);
- in a saved project written before M48, a fixed parameter named
  `max_<metric>` or `min_<metric>` becomes a `Bound`. Before M48 the runner
  read every such parameter as a bound, so the bound is what it did. M52
  narrowed this to old data: the store converts only in a schema version "1"
  file, and only a requirement saved with no `bounds` key
  (`nirmaan.models.workflow.legacy_requirement`). A requirement built today
  keeps every parameter, so `dft.scan_insert`'s real `max_chain_length` stays
  an input;
- `max_retries`, `on_failure`, `max_attempts` and `max_review_rounds` become
  `limits` fields.

**Saved projects** load, verify their audit chain (the chain covers audit
entries, never task records), and re-save stably: the first save writes the
new form, and a second load and save writes the same bytes. A task's saved
`max_retries` and `on_failure` are dropped (section 2.4).

**Runs saved with a bound as a parameter.** A `ToolRun` saved before M48 has
no `bounds` (it loads as None, and saves without the key, byte for byte). Such
a run was checked by the runner against every `max_`/`min_` parameter it
carried, so it counts as checked against a bound whose label (`max_latches`)
it carries with a matching value. A run made after M48 has a `bounds` record
(possibly empty), and only that counts, so a real input named `max_` can never
pass for a bound. The stored parameter is kept as it was saved; since the
contract no longer declares the prefix, `ToolRun.typed` returns it as the
stored text.

## 4. Extension: a new condition kind

`register_condition_kind(ConditionKind(name, phase, facts, describe))`, and
any stage, variant or requirement may name it. The crown-jewel test registers
`pdk`, a plan-phase kind whose facts are the process kits a request names, and
a workflow extension whose requirement applies only when the request names
sky130: the planner, the validator and the prompt handle it with no core
change. A run-phase kind gets the reader's sources in `Facts` (`state` and
`task` from the policy, `packet` from the runtime).

## 5. Tests

`tests/test_nirmaan_unified_applicability.py` (written first, failing): old-form
data and old projects load; one evaluator and its phase rules; bounds are
enforced from the field and a `max_` input is no longer read as one; retry
precedence; the crown jewel; the import laws.
`tests/test_nirmaan_applicability_golden.py` is the characterization (section
6).

## 6. Characterization

Before any change, `tests/test_nirmaan_applicability_golden.py` planned 31
representative requests (one per intent and feature set the suite plans, plus
combinations no test plans alone), reaching all nine workflows. For each
planned task it records its limits and each requirement: tools, accepted
kinds, file bindings (with `optional`), whether it is checked before review,
fixed parameters and bounds (one normalized list, so the move from parameters
to bounds is visible only if a value changes), `yields`, and when it applies
at run time over every combination of produced and upstream kinds in the plan.
The golden file, `tests/fixtures/applicability/plans.txt`, was written by the
code before M48 and is byte-identical after it. Only the test's accessors
changed with the API.

Intended differences, outside the golden file:

- a `max_`/`min_` tool parameter is refused by the broker, rather than read as
  a bound (section 2.3); the tests that passed bounds as parameters pass
  `bounds` instead;
- a bound failure's summary is prefixed by the broker, not the EDA runner:
  `limit not met: ... (the tool reported: yosys: ...)` rather than
  `yosys: limit not met: ... (the tool reported: ...)`. The words of each
  failure are unchanged. The runner's own result file records the tool's
  result; the run record carries the bound's verdict;
- `nirmaan org tool` no longer lists `max_<metric>` or `min_<metric>`;
- a saved run's legacy bound parameter reads as its stored text through
  `ToolRun.typed` (section 3);
- `runtime.limits` returns a `Limits` with all four fields, not an
  `(attempts, review_rounds)` pair.

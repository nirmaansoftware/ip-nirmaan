# Real STA on Timing Re-analysis, and Antecedents of Named Properties and Macros (Milestone 37)

Status: design for the owner's review, implemented on branch
`m37/sta-and-antecedents`. This closes the "Not yet" cell of the "Where we are"
table in `docs/ROADMAP.md` that read "A real `sta.run` (not an attestation) on
`timing-closure` `reanalysis`; antecedents of named properties and macros", and
the first and third items deferred in `docs/GATES_REST.md` section 6. Prose
here is free of em and en dashes per the standing style law.

Read `docs/GATES_REST.md` (M29) first: the RTL gates on the fix stages, why
M29 put no STA before review on `timing-closure` `rtl-fix`, and how a cover is
derived beside every assertion. Read `docs/PHYSICAL_DESIGN.md` and
`docs/PD_SIGNOFF.md` for the `sta.run` backends and the CI job that runs them.

---

## 1. What changes, in one table

| Piece | Where | Kind of change |
|---|---|---|
| `reanalysis` on the RTL branch needs a real `sta.run` over the approved fixed RTL, before review; the attestation stays only on the constraint and physical branches | `company/workflows.py` | data |
| `EvidenceRequirement.when_upstream`: a requirement applies only when the task builds on an upstream artifact of one of these kinds | `models/workflow.py`, read by `work/policy.py` and the model runtime | one generic field |
| `sta.run` takes `sources` (RTL) instead of a `netlist`: the run synthesizes to the PDK's Liberty, then times the netlist it wrote, in one recorded run | `integrations/physical.py`, the `sta.run` contract in `company/tools.py` | two backends, one contract |
| Named properties (with or without arguments) are inlined, and macros that assert are expanded, in the cover run's copy; a cover is derived for each as for any other assertion | `integrations/eda_antecedents.py`, `integrations/eda.py` | the deriver |
| A real timing-closure project in CI: the violated before-run and the met after-run | `tests/test_nirmaan_sta_antecedents.py`, CI's `physical-design` job | test, CI |

No seat, stage, tool, kind, or property style is named by the runtime, the
policy, the planner, or the models (a test reads their sources).

---

## 2. A real `sta.run` on `reanalysis`

### The requirement, as data

`timing-closure` ends in `reanalysis` (`sta.analyze`, the implementation
gate). Until now its tool evidence was `ran("Clean timing report", "sta.run")`,
which a named human's attestation also met. On the `rtl_path` branch it is now:

```python
RETIMED = checked("Timing met on the fixed RTL: synthesized to the target library, "
                  "then timed under the task's SDC", "sta.run",
                  FileInput(param="sources", kinds=("rtl_source",), upstream=True),
                  when_upstream=("rtl_source",))
```

* **A tool run only.** `checked` accepts `TOOL_RUN` and nothing else, and is
  met before review, so no attestation and no claim can stand in for it.
* **On the fixed RTL.** `sources` is filled from the approved upstream
  `rtl_source` (the `rtl-fix` answer, approved behind its RTL gates), and the
  M25 before-review check refuses submission unless a passing run's `sources`
  named those very files.
* **With the task's SDC and PDK inputs.** Everything else comes from the task's
  inputs, filtered by the `sta.run` contract (M28): `sdc`, `top`, `liberty`,
  `pdk_root`, and, for OpenROAD's embedded timer, `tech_lef` and `lef`. A
  `netlist` input is refused alongside `sources` (section 2.3), so the run
  cannot time an old netlist and claim the fixed RTL.
* **Clean.** `sta.run` passes only when timing is met (M25 parser: exit 0, a
  worst slack reported, and no negative slack anywhere).

The `constraint-fix` and `pd-fix` branches do not produce RTL, and timing them
needs an SDC or a layout, not a synthesis. Their `reanalysis` keeps the old
requirement, now marked `when_upstream=("constraints", "layout")`. Making those
real too is deferred (section 6).

### `when_upstream`: one generic field

Which branch was taken is known only when `classify` records its decision,
long after planning, so a planning condition (`when`) cannot express it, and
`when_produced` looks at the task's own outputs. The new field looks at what
the task builds on:

```python
when_upstream: tuple[str, ...] = ()
"""Applies only when the task builds on an upstream artifact of one of these kinds (M37). Empty: always."""
```

`EvidenceRequirement.applies(kinds, upstream=())` checks both. The policy
(`unsatisfied_requirements` and the before-review check) passes the kinds of
`upstream_artifacts`, the model runtime passes the kinds in the work packet's
upstream list (before and after the answer), and the seat's prompt says when a
requirement applies. On the RTL branch the untaken branches are cancelled and
produce nothing, so `reanalysis` builds on `rtl_source` only, and on the other
branches on `constraints` or `layout` only. The field names no kind; the
workflow data does.

### Synthesis inside `sta.run`

The fixed RTL is RTL; OpenSTA reads a gate-level netlist. Three ways to bridge
that were considered:

1. **A synthesis requirement on `reanalysis`, then STA on its netlist.** The
   evidence model fills tool parameters from files the task produced or
   approved upstream files, not from another run's outputs. Chaining runs would
   be a new core concept (a run's output as another's input) for one stage.
2. **A synthesis stage between `rtl-fix` and `reanalysis`.** It would change
   the workflow's shape on every branch, and the netlist it produced would be
   an artifact a seat answers with, not one a tool wrote.
3. **`sta.run` synthesizes when given `sources`.** One recorded run: Yosys maps
   the RTL to the Liberty (the same `yosys-liberty` script `synth.run` writes,
   M25), and the timer reads the `netlist.v` that synthesis wrote, in the same
   working directory. The log holds both steps; the result names the netlist.

M37 takes the third. The claim "the fixed RTL meets timing" is one claim, made
by one run whose log shows the synthesis and the timing of exactly the files
named in its parameters. No core concept is added, and `physical-implementation`
(which times a routed netlist) is unchanged.

### 2.3 The `sta.run` contract and backends

| | Before | After |
|---|---|---|
| `netlist` | required | optional |
| `sources` | not declared | the RTL to synthesize first (M37) |
| Neither given | "missing parameter netlist" (a recorded failed run) | the same, naming `sources` as the alternative |
| Both given | n/a | a recorded failed run: "give a netlist or sources, not both" |
| `sources` given, no `yosys` on PATH | n/a | refused by the probe, with the reason; no run recorded |

Both `sta.run` backends (`opensta`, `openroad-sta`) gain the synthesis step.
Their `environment` check now also asks for `yosys` when `sources` is given, so
a machine without Yosys refuses with a reason, the same as a machine without
`sta` or `openroad`. A failed synthesis is a recorded failed run whose summary
says synthesis failed and no netlist was written; the timer never runs on a
missing or stale netlist (the script deletes any old `netlist.v` first).

### Blocked, never faked

`RETIMED` is met before review, and the M26 runtime blocks a task when every
tool of a before-review requirement is refused. So on a machine with neither
`sta` nor `openroad` (the development machine, CI's main test job) a
`reanalysis` answer on the RTL branch is BLOCKED, with the broker's reasons in
the task's history ("opensta needs sta on PATH, not found; openroad-sta needs
openroad on PATH, not found"). Nothing is submitted and no attestation is
offered as a way around it. A test proves this with the tools hidden from PATH.

---

## 3. Antecedents of named properties and macros

M29 refused a named property and a macro whose body asserts. Both are now
derived.

### Named properties

```verilog
property no_wrap_past(c, l);
    c <= l;
endproperty
always @(posedge clk)
    if (seen_reset && count > LIMIT)
        assert property (no_wrap_past(count, LIMIT));
```

The deriver reads every `property ... endproperty` in the setup's files: its
name, its formal arguments (untyped or typed, with or without a default), and
its body. Each `assert`, `assume`, `cover`, or `restrict property (...)`
whose body is a named property, with an optional clocking event and
`disable iff` before it, is replaced in the copy by the property's body, with
each formal argument replaced by the actual one in parentheses (positional
arguments, then defaults). The declaration is blanked in the copy, newlines
kept. The inlined assertion is then derived exactly as a written one:

```verilog
if (seen_reset && count > LIMIT)
    begin cover property (1'b1); assert property ((count) <= (LIMIT)); end
```

A property whose body is `A |-> B` or `A |=> B` gets a cover of `A` with the
actual arguments substituted. A property that names another property as its
whole body is inlined through it (up to a depth of 8).

**Why inline, and not only derive.** Yosys's open-source frontend does not
parse `property` declarations (`syntax error, unexpected TOK_PROPERTY`).
Deriving a `cover property (...)` beside an untouched `assert property (p)`
would leave a copy no installed tool can read, so the cover run could never
show an antecedent reached or unreached. The inlined copy is the same
assertion and elaborates. The proof (`formal.run`) still reads the submitted
file, which this frontend rejects: with today's toolchain a seat that writes
named properties fails `formal.run` before the cover run matters, as with
implications in M29. The cover check is ready for a frontend that accepts them,
and a test runs the cover check on the named-property fixture for real.

### Macros

```verilog
`define ASSERT_IMPL(a, b) if (a) assert (b)
always @(posedge clk) `ASSERT_IMPL(seen_reset && count > LIMIT, !wrap);
```

The deriver collects every `` `define `` across the setup's Verilog files (a
macro defined in a `.vh` and used in a `.v` is found). Each use of a macro
whose body asserts (directly, or through another macro it uses) is expanded in
the copy: formal arguments replaced by the actual ones, continuation lines
joined, so the expansion never adds a line. Any newlines inside the use (its
arguments split over lines) follow the expansion, so every later line keeps its
number. The expansion is then derived as written code: here, an `if` guarding
an immediate assertion, so `cover (1'b1)` is wrapped beside the assertion on
the macro's own line. The derived cover reports the line of the macro's use.

Yosys would expand the macro itself, but it reports a statement from a macro
at a position the deriver could not predict; expanding in the copy keeps the
derived cover at a recorded file, line, and column, as M29 requires.

### What is still refused, each with its file, line, and reason

| Construct | Reason given |
|---|---|
| A named property used inside a larger property expression (`p and q`, `!p`, `p |-> q`) | "the named property p is used inside an expression; only a whole property body is inlined" |
| Named arguments to a property (`p(.c(x))`) | "named arguments to a property are not supported" |
| Too many or too few arguments, with no default | "property p takes N arguments, M given" |
| A clocking event on both the assertion and the property | "both the assertion and property p name a clock" |
| A named sequence in an asserted property | "the named sequence s is not expanded" |
| Inlining deeper than 8 properties | "property p is nested too deeply" |
| A macro that asserts, defined more than once in the setup | "the macro M is defined more than once" |
| Token pasting or stringification in a macro that asserts | "the macro M pastes or stringifies tokens" |
| A use of a macro that asserts, with the wrong number of arguments or none | "the macro M takes N arguments, M given" |
| Everything M29 refused that is not above: sequence and property operators, a nested or parenthesized implication, an action block, a deferred assertion | as in M29 |

A macro that asserts and is never used asserts nothing, so it is no longer
listed; a use of a macro defined outside the setup's files cannot be seen and
is not expanded (the setup's `[files]` is what the run reads; section 5).

---

## 4. Laws, each pinned by a test

In `tests/test_nirmaan_sta_antecedents.py`:

1. `reanalysis` on the RTL branch carries `RETIMED`: a tool run only, before
   review, over the approved upstream RTL, applying only when the task builds
   on `rtl_source`; the old requirement applies only on the other branches.
2. Planned and driven to `reanalysis`: on the RTL branch `RETIMED` is unmet and
   the attestation requirement does not apply; on the constraint branch the
   reverse.
3. With `sta` and `openroad` hidden, a `reanalysis` answer on the RTL branch is
   BLOCKED with the broker's reasons, and nothing is submitted.
4. `sta.run` with `sources` synthesizes then times, in one run, through a
   stand-in timer (the script reads the netlist the synthesis wrote); `netlist`
   and `sources` together, and neither, are recorded failed runs; `sources`
   without Yosys is a refusal.
5. Real, in CI's `physical-design` job: a timing-closure project whose
   `rtl-fix` pipelines the fixture. The before-run (the original RTL, the same
   SDC) is violated; `rtl-fix` passes its RTL gates and is approved;
   `reanalysis` submits with a met `sta.run` over the approved fix. Both runs
   are in the project's record with their slacks.
6. Named properties, with and without arguments, and macros: covers are derived
   on text, at the right line and column, and nothing else changes but the
   inlining and the blanked declaration.
7. Real cover runs: the named-property and macro fixtures reach every derived
   cover; an unreachable antecedent through a named property, and through a
   macro, fails the run with an `ANTECEDENT` diagnostic at the use's line.
8. Every refusal in the section 3 table, on text and through the backend.
9. Crown jewel: an extension's workflow adds a stage with its own
   `when_upstream` requirement, and it applies and blocks only on the branch
   that builds on that kind, with no core change.
10. The runtime, policy, planner, and models never name antecedents,
    properties, macros, STA, or synthesis; the deriver imports nothing of
    Nirmaan; the M19 import laws and the M28 contract scan hold.

---

## 5. Limits

* **Named properties are moot with Yosys today.** Its frontend rejects the
  declaration, so `formal.run` fails on such a file before the cover check
  runs. The derivation is real and tested by real cover runs on the copy.
* **Macros from the setup's files only.** A macro defined in a file the `.sby`
  does not list (an absolute `` `include ``) is not seen. sby copies only
  `[files]` into its run, so an `` `include `` it can resolve is normally among
  them.
* **Conditional definitions.** A macro defined in both branches of an
  `` `ifdef `` counts as defined twice and is refused, rather than guessing
  which branch the run takes.
* **One corner, Nangate45.** The CI project times the fixture at the one
  typical corner the image ships (`docs/PD_SIGNOFF.md` section 7).
* **Synthesis, not place and route.** `RETIMED` times the synthesized netlist
  with no wire parasitics. It shows the fix closes the path it was asked to
  close; signoff on a routed, extracted netlist stays in
  `physical-implementation`.

---

## 6. Deferred

* Real STA on the `constraint-fix` and `pd-fix` branches of `reanalysis`
  (the fixed SDC against the original netlist; the fixed layout's netlist and
  SPEF). They keep the attestation, now explicitly scoped to those branches.
* The `sta-analysis` requirement "Timing report with failing paths" is met by
  a passing run or an attestation; a run that finds the violations it reports
  is recorded but not substantiated. Accepting a failing run as evidence that
  a path fails is its own change to the evidence model.
* Named arguments, sequences, and properties inside expressions.
* Antecedents of implications written as booleans inside an immediate
  assertion (`!a || b`), and multi-task `.sby` setups (from M29).

---

## 7. Real numbers (CI)

Filled in from the CI run that passed (section 4, law 5).

# The RTL Gates on the Remaining Workflows, and Automatic Antecedent Covers (Milestone 29)

Status: design for the owner's review, implemented on branch
`m29/gates-rest`. This closes the "Not yet" cell of the "Where we are" table in
`docs/ROADMAP.md` that read "The same RTL gates on `parameter-change` and the
fix stages; automatic antecedent covers", and the first two items deferred in
`docs/GATES_EVERYWHERE.md` section 7. Prose here is free of em and en dashes
per the standing style law.

M27 put `RTL_GATES` (lint, simulation, synthesis with no latches, formal and a
cover run when the seat writes a `.sby`) on three RTL workflows, and left four
more stages that write RTL. It also made a proof count only if every cover the
seat wrote is reached, and left one hole open: an assertion whose guard never
holds is never checked, and the seat may simply not cover that guard. M29
gates the four stages, as data, and closes that hole without asking the seat
for anything: the cover run derives a cover for every assertion's antecedent.

---

## 1. What changes, in one table

| Piece | Where | Kind of change |
|---|---|---|
| `RTL_GATES` on `parameter-change` `rtl-change`, `regression-investigation` `rtl-fix`, `timing-closure` `rtl-fix`, and `new-ip` `cdc-design`; each also produces a `testbench` | `company/workflows.py` | data |
| `rtl.cdc_design` builds only on approved inputs | `company/capabilities.py` | data |
| The `cdc_design` skill may run the five gate tools | `company/skills.py` | data |
| `eda_antecedents.derive`: a cover beside every assertion, in a copy | `integrations/eda_antecedents.py` (new, imports nothing of Nirmaan) | one module |
| The `symbiyosys-cover` backend reads the instrumented copies, and refuses an assertion it cannot derive | `integrations/eda.py` | one backend |
| `parse_sby_cover` counts derived covers apart from the seat's | `integrations/eda_parsers.py` | parser |

No seat, stage, tool, or kind is named by the runtime, the policy, the planner,
or the models, and none of them names antecedents (a test reads their
sources). No fixture changed: every fixture assertion's antecedent is already
reachable, which is itself now checked.

---

## 2. The gates on the remaining stages

Every stage in `WORKFLOWS` that outputs `rtl_source` now carries exactly
`(REVIEWED, *RTL_GATES)`, and a test enumerates the registry to keep it so:

| Workflow, stage | Before | After |
|---|---|---|
| `parameter-change`, `rtl-change` (per variant) | outputs `rtl_source`; "Compiles and passes a smoke simulation", a `simulator.run` or a human attestation | outputs `rtl_source`, `testbench`; `RTL_GATES`, met by real runs over the submitted files, before review |
| `regression-investigation`, `rtl-fix` (on the `rtl_bug` branch) | outputs `rtl_source`; review only | the same as above |
| `timing-closure`, `rtl-fix` (on the `rtl_path` branch) | outputs `rtl_source`; review only | the same as above |
| `new-ip`, `cdc-design` (when the request has clock domains) | outputs `rtl_source`; review only | the same as above |

As in M27, the testbench is an output because the simulation check needs one,
and a human attestation no longer meets these stages: an RTL answer reaches
review only if it is lint-clean, simulates, synthesizes with no latches, and,
when it carries a proof, is proven and not vacuous.

**`cdc-design` is the one stage with a different capability.** It uses
`rtl.cdc_design`, served by the CDC design team, so two data edits come with
the gates:

* `rtl.cdc_design` gains `approved_inputs=True`, as `rtl.implement` has since
  M23. Its upstream is the microarchitecture behind the architecture gate, and
  M27's `upstream_artifacts` already looks through gates.
* The `cdc_design` skill gains the tools the gates run (`lint.run`,
  `simulator.run`, `synth.run`, `formal.run`, `formal.cover`). The runtime runs
  before-review checks as the seat, and the broker refuses a tool the seat's
  role may not use; without the grant every CDC answer would be blocked, not
  checked. The skill does not include `rtl_design`, so routing is unchanged:
  the CDC team still serves `rtl.cdc_design` and only that.

The `regression-investigation` `rtl-fix` is served by the RTL architecture
role and the `timing-closure` `rtl-fix` by the pipeline design role; both may
already run the gate tools (the tests run every check as those seats), so they
need no grant.

### STA on `timing-closure`: not before review, and why

The `timing-closure` `rtl-fix` exists to fix a failing timing path, so it is
tempting to add `sta.run` as a sixth before-review check there. M29 does not,
for three reasons:

1. **The workflow already re-runs STA, after the fix.** The next stage,
   `reanalysis`, depends on `rtl-fix` and needs a "Clean timing report" from
   `sta.run`, and it is the implementation gate (`gate.implementation`). A
   before-review STA on the fix would duplicate that stage, not add to it.
2. **STA needs inputs the RTL seat does not produce.** OpenSTA reads a
   Liberty-mapped netlist and an SDC under a PDK. The RTL seat writes RTL and a
   testbench; the constraints come from `sta-analysis` and the netlist from a
   synthesis to the target library. Gating the fix on STA would mean a
   Liberty synthesis and a PDK on the RTL seat's path.
3. **It would make the gate depend on the machine.** STA runs only where a PDK
   and OpenROAD exist: CI's `physical-design` job, not the main `test` job and
   not the development machine. A conditional check that silently does not
   apply on most machines is a gate that is not there; one that blocks on most
   machines stops every timing fix at the RTL stage. Neither is honest.

The RTL gates still apply in full: a restructured path must be lint-clean,
simulate, and synthesize with no latches before anyone reviews it, and the
timing claim is made where the tools for it run. Making `reanalysis` accept
only a real `sta.run` (not an attestation) belongs with the physical design
signoff work in progress in parallel, and is listed in section 7.

---

## 3. Automatic antecedent covers

### The problem

```verilog
always @(posedge clk)
    if (seen_reset && count > LIMIT)   // never true: the count never passes LIMIT
        assert (!wrap);
```

SymbiYosys proves this, and it should: the assertion is never checked, so it
never fails. M27's cover run catches it only if the seat also wrote
`cover (seen_reset && count > LIMIT)`. Nothing made it.

### The check

The `symbiyosys-cover` backend (`formal.cover`) now writes, for each Verilog
file the setup reads (`.v`, `.sv`, `.vh`, `.svh` in `[files]`), a copy into
`<run>/antecedents/` with a cover derived for every assertion, and points the
cover `.sby` at the copies. The seat's files are never edited, and nothing is
written beside them. A manifest, `<run>/antecedents.json`, lists every
assertion: its file, line, kind, the column of its derived cover, and the
submitted file it came from.

**How a cover is derived.** An assertion in procedural code (an `always` or
`initial` block, a task, a function) is wrapped in place:

```verilog
if (seen_reset && count > LIMIT)
    begin cover (1'b1); assert (!wrap); end
```

The cover sits on exactly the procedural path the assertion sits on: every
enclosing `if` and `else`, `case` arm, `for` iteration, generate instance, and
task call. Yosys builds the cover's enable from those guards when it
elaborates the design, so the deriver never parses a guard expression; it only
has to find the assertion statement and the procedural blocks. This handles
every style in the fixtures:

| Fixture | Style | Assertions | Covers after elaboration |
|---|---|---|---|
| counter | `if (seen_reset) assert` in a clocked block | 1 | 1 |
| AXI4-Lite | nested `if` in a clocked block, `$past` guards | 14 | 14 |
| FIFO (depth 8 and 5) | nested `if`, `$past` guards, `anyconst` slot | 18 | 18 |
| Arbiter (N 4 and 5) | nested `for` loops in `always @(*)`, an `if` inside the loops, `if`/`else` | 9 | 33 and 45, one per loop iteration |
| APB | `if`/`else` inside a `task` called four times, and a `for` in the task | 8 | 38, one per call and iteration |

A concurrent assertion with a top-level implication, `assert property (A |-> B)`
or `|=>`, gets a cover of `A`: inside procedural code `A` replaces `1'b1` in the
wrapper; at module scope `cover property (A);` follows the assertion, keeping
its clocking and `disable iff`. A module-scope assertion with no implication is
checked on every cycle; it has no antecedent and is listed as `unguarded`.

**Lines never move.** The inserted text never contains a newline, so a derived
cover reports the assertion's own line, and the parser tells derived covers
from the seat's by the exact file, line, and column the manifest records.

**Pass means** everything M27 required (`DONE (PASS)`, exit 0, at least one
seat cover reached, none unreached), and also that no derived cover instance
went unreached. An unreached one fails the run with one `ANTECEDENT`
diagnostic per assertion, at the assertion's file and line: "vacuous: 1 of 2
assertion antecedents never reached under the assumptions, so the assertion at
counter.v:40 is never checked". Metrics: `covers_reached` and
`covers_unreached` stay the seat's own (so M27's numbers are unchanged), and
`antecedents_reached`, `antecedents_unreached`, and
`antecedents_unelaborated` are added.

### What is refused, and what is only listed

Nothing the deriver cannot handle is skipped. Before any step runs, the
backend refuses the setup, as a recorded failed run that names each
assertion's file, line, and reason, if the RTL has:

* a sequence or property operator (`##`, `[*`, `[=`, `[->`, `throughout`,
  `within`, `until`, `s_eventually`, `and`, `or`, `not`, and the other
  property operators) in an asserted property;
* an implication inside parentheses, or a chain of implications;
* a named property (`assert property (p)` for a declared `property p`);
* an action block (`assert (x) else $error(...)`);
* a deferred assertion (`assert #0`, `assert final`);
* a `` `define `` whose body asserts (a macro is not expanded).

"A proof whose antecedents cannot be covered is not known to check anything."
The seat can rewrite the assertion in the supported forms, as every fixture
already is.

Listed, not failed: a derived cover that never appears in the cover run at all
(`antecedents_unelaborated`, a warning per assertion). That happens when the
assertion is not part of the elaborated design: a generate branch not taken
for these parameters, a task never called, or a module the setup's `prep -top`
does not reach. Such an assertion is not checked, but neither does the proof
claim it; the reviewer sees the warning.

### Limits

* **Reached within the proof's bound.** As in M27, the cover run uses the
  proof's `depth`, so "reached" means "reached within the bound the proof's
  base case explores". A guard reachable only deeper fails; the seat raises the
  depth.
* **The guard, not the implication inside an immediate assertion.** A
  boolean `assert (!a || b)` has no antecedent the deriver separates; only its
  procedural guard is covered. Written as `if (a) assert (b);` its antecedent
  is covered.
* **Implications are moot with this toolchain today.** Yosys's open-source
  Verilog frontend rejects `|->`, `|=>`, and clocking inside a property, so
  `formal.run` already fails on them before the cover run matters. The deriver
  handles them (and is tested on text) so a frontend that accepts them changes
  nothing here.
* **A pragmatic parser.** The deriver tokenizes Verilog (comments, strings,
  attributes, and directives handled) and follows statement structure; it is
  not a full SystemVerilog parser. A construct it misreads makes the copy fail
  to elaborate, which is a failed run, never a pass.

### Why inside `formal.cover` and not a new check

The claim is the same one `NOT_VACUOUS` already makes ("the proof is not
vacuous"), over the same setup, assumptions, and bound, so it is the same run.
A separate tool would add a sixth gate to every RTL stage and a second cover
run per answer for no new claim. Because it rides on `NOT_VACUOUS`, every
stage that carries `RTL_GATES`, and `block-design`, gains it with no data
edit, and an extension's workflow gains it by carrying the gates (the crown
jewel).

---

## 4. Migrated tests

None of their assertions was removed or loosened.

| Test | Why it changed | How |
|---|---|---|
| `test_nirmaan_gates_everywhere.py::test_the_cover_run_uses_the_seats_own_setup_and_writes_nothing_beside_it` | it asserted the cover `.sby` names the submitted `counter.v`; the run now reads an instrumented copy | it now asserts the `[files]` entry names the copy in the run's directory, the copy has the same number of lines, and the only changed line is the assertion, wrapped with its derived cover (stronger than before) |


No other test needed a change. Tests that drive a plan through one of the newly
gated stages were found by recording every gated submission during the suite:
only `new-ip` `cdc-design` is reached, by the bridge plans in
`test_nirmaan_work.py` (`test_signoff_needs_evidence_and_claims_never_count`,
`test_a_whole_project_completes_only_under_the_rules`), `test_nirmaan_eda.py`
(`test_real_lint_substantiates_the_rtl_lint_requirement`), and the
`test_nirmaan_export.py` fixtures. Each of those already drives the M27-gated
`rtl-implementation` stage first, so it already runs the same checks with the
same tools; `drive` now also works `cdc-design` in the gated order, and the
assertions pass unchanged. No test drove `parameter-change`,
`regression-investigation`, or `timing-closure` past their RTL stages before.

---

## 5. Laws, each pinned by a test

In `tests/test_nirmaan_gates_rest.py`:

1. The four stages carry exactly `RTL_GATES` and produce a testbench; every
   stage in the registry that produces `rtl_source` is gated.
2. `rtl.cdc_design` requires approved inputs, and the CDC skill may run the
   gate tools.
3. On each of the four stages, planned from a plain request (with the
   `rtl_bug` and `rtl_path` decisions on the branch stages): the task is
   gated, a latch blocks review, a failing self-check blocks review, and clean
   RTL with a proof passes all five checks, every antecedent reached, and is
   approved.
4. On each of the four stages, an assertion under a guard that never holds is
   refused, as a recorded, unsubstantiated failed cover run, while `formal.run`
   on the same files passes and the seat's own cover is reached.
5. Every fixture assertion gets a derived cover on its own line and column,
   and nothing else in the copy changes.
6. All seven fixture setups reach every derived cover, with nothing
   unelaborated, and the manifest names the submitted file.
7. An assertion the deriver cannot handle fails the run, with its line and
   reason; the deriver's refusals (macro, named property, nested implication,
   deferred, action block) and its handling of module-scope and procedural
   implications, `else` branches, and `case` arms, on text.
8. The parser counts derived covers apart from the seat's, and lists an
   unelaborated one as a warning.
9. Crown jewel: an extension's new workflow whose RTL stage carries
   `RTL_GATES` refuses a never-checked assertion and accepts clean RTL, with no
   core change.
10. `drive` works a newly gated stage in the gated order.
11. The runtime, policy, planner, and models never name antecedents; the
    deriver imports nothing of Nirmaan or VeriTriage; CI requires the formal
    tools and runs these tests. The M19 import laws are unchanged and still
    tested.

---

## 6. Deferred

* A real `sta.run` (not an attestation) on `timing-closure` `reanalysis`, with
  the physical design signoff work (section 2).
* Antecedents of implications written as booleans inside an immediate
  assertion (`!a || b`).
* Expanding named properties and macros before deriving, instead of refusing.
* Multi-task `.sby` setups in the cover check (from M27).
* A formal-properties seat separate from the RTL seat (from M26).

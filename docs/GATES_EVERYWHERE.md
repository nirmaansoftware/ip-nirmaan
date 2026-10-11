# The Design Gates on Every RTL Workflow, and Proofs That Are Not Vacuous (Milestone 27)

Status: design for the owner's review, implemented on branch
`m27/gates-everywhere`. This closes the "Not yet" cell of the "Where we are"
table in `docs/ROADMAP.md` that read "Approved-inputs, synthesis, and formal
gating on the `new-ip`, `feature-addition`, and `rtl-change` RTL stages;
non-vacuity checks for properties". Prose here is free of em and en dashes per
the standing style law.

M23 gated the `block-design` RTL stage on real lint and simulation, and made
design seats work only from approved inputs. M26 added synthesis with no
latches and, when the seat writes a `.sby`, a real proof. Both left the three
older RTL workflows alone (`docs/DESIGN_AGENTS.md` section 9, and
`docs/FORMAL_GATE.md` section 6), because their tests submitted first and
attached evidence later. M27 applies the same gates there, as data, migrates
those tests to the gated order, and closes the hole M26 named: a proof that
passes because it proves nothing.

---

## 1. What changes, in one table

| Piece | Where | Kind of change |
|---|---|---|
| `RTL_GATES`: the before-review checks, named once | `company/workflows.py` | data |
| The gates on `new-ip` `rtl-implementation`, `feature-addition` `rtl-change`, and `rtl-change` `change`; each stage also produces a `testbench` | same | data |
| `NOT_VACUOUS`: a cover run over the seat's `.sby`, tied to `formal_spec` | same, in `RTL_GATES` and on `block-design` | data |
| `formal.cover`, a tool, AVAILABLE, granted to the RTL and formal skills | `company/tools.py`, `company/skills.py` | data |
| The `symbiyosys-cover` backend and `parse_sby_cover` | `integrations/eda.py`, `integrations/eda_parsers.py` | one backend |
| `upstream_artifacts`: a stage behind a gate builds on the gated stage's artifacts | `work/policy.py`, read by `runtime/context.py` | one generic helper |
| Covers in the counter, AXI4-Lite, FIFO, arbiter, and APB fixtures; the APB proof depth 4 to 8 | `tests/fixtures/rtl/` | fixtures |
| `drive` works a gated task in the gated order | `tests/nirmaan_helpers.py` | test helper |

No seat, stage, tool, or kind is named by the runtime, the policy, the planner,
or the models (a test reads their sources for `formal.cover`).

---

## 2. The gates, as data

`company/workflows.py` now names the checks once:

```python
NOT_VACUOUS = checked("The proof is not vacuous: every cover is reached", "formal.cover",
                      FileInput(param="sby", kinds=("formal_spec",)),
                      FileInput(param="sources", kinds=("rtl_source",)),
                      when_produced=("formal_spec",))

RTL_GATES = (lint, simulation, synthesis with max_latches=0, formal (when a .sby), NOT_VACUOUS)
```

The four M23 and M26 checks are the exact requirements the `block-design` RTL
stage already carried; a test asserts the stage's evidence equals
`(REVIEWED, *RTL_GATES)` on all four workflows. `block-design` keeps its own
lines (the edit there is one added `NOT_VACUOUS`), so parallel work on that
workflow does not conflict.

Each of the three RTL stages changes in two ways:

| Workflow, stage | Before | After |
|---|---|---|
| `new-ip`, `rtl-implementation` (one task per variant) | outputs `rtl_source`; "Compiles and passes a smoke simulation", met by a `simulator.run` or a human attestation, after submission | outputs `rtl_source`, `testbench`; `RTL_GATES`, met by real runs over the submitted files, before review |
| `feature-addition`, `rtl-change` (per variant) | the same as `new-ip` | the same as `new-ip` |
| `rtl-change`, `change` | outputs `rtl_source`; "Compiles and lint-clean", a `simulator.run` or `lint.run` or an attestation | outputs `rtl_source`, `testbench`; `RTL_GATES` |

**Why the testbench is an output.** The old requirement already asked for a
smoke simulation, which needs a testbench; the seat now writes it, as the
`block-design` seat does. The verification stages downstream (`dv-environment`,
`directed-tests`, `tests`, `targeted`) are unchanged: a smoke self-check by the
designer is not verification closure.

**A human attestation no longer meets these stages.** A before-review check
accepts only a tool run over the submitted files. This is the point of the
milestone: an RTL answer on any of these workflows now goes to review only if
it is lint-clean, simulates, synthesizes with no latches, and, when it carries
a proof, is proven and not vacuous.

### Approved inputs, through gates

`rtl.implement` already had `approved_inputs=True` (M23), and all four RTL
stages use it. But on `new-ip` and `feature-addition` the RTL stage waits on
`microarchitecture.gate`, not on `microarchitecture`: the planner puts the
architecture gate between them. A gate produces no artifacts, so the seat saw
no upstream at all (nothing to build on, and nothing to cite), and the
approved-inputs check had nothing to check. The rule held vacuously.

`upstream_artifacts(state, task)` in `work/policy.py` fixes this generically:
a task's upstream is its dependencies' artifacts, and a dependency that is a
gate is looked through to the tasks behind it. Approving a gate approves the
stage behind it, so those are the artifacts that must be approved. It is read
in three places, none of which names a stage: the context packet (the seat's
upstream, trusted only when approved), the `approved-inputs` check, and the
`evidence-before-review` check's upstream bindings (M25). A test downgrades
the microarchitecture behind the gate and sees the start refused.

---

## 3. Non-vacuity: every cover is reached

### The problem

SymbiYosys in prove mode passes a proof whose assumptions rule out the
behavior the assertions talk about. Three shapes, all real mistakes:

1. **Over-constrained inputs:** `assume (!en);` on a counter. The count never
   moves, so "the count never passes LIMIT" holds trivially.
2. **A contradiction on the path:** `if (en && count == 5) assume (1'b0);`.
   Satisfiable (so smtbmc's `--presat` check, which catches a plain
   `assume (1'b0)`, does not fire), yet the counter can never reach the state
   the property is about.
3. **An antecedent that never fires:** `if (a && b) assert (c);` where `a && b`
   is unreachable. The assertion is never checked.

All three pass `formal.run`. M26 accepted that residual risk; M27 closes it.

### The check

A new tool, `formal.cover`, with one backend, `symbiyosys-cover`:

* **The seat's own setup, in cover mode.** The backend writes a copy of the
  seat's `.sby` into the run's own directory with two differences: `mode cover`
  replaces the `mode` option, and each `[files]` entry is named by absolute
  path (so nothing is written next to the submitted files). The script, the
  engines, the depth, and therefore every assumption are exactly the proof's.
  The cover bound is the proof's `depth`, so "reached" means "reached within
  the bound the proof's base case explores".
* **Covers live in the RTL** under `` `ifdef FORMAL ``, beside the assertions,
  as the properties do. The seat writes them; the reviewer reads them.
* **Pass means:** SymbiYosys reports `DONE (PASS)` with exit status 0, at least
  one cover statement was reached, and none was left unreached. A setup with no
  covers passes in SymbiYosys's own terms ("PASS", nothing to reach), and fails
  here: it says nothing about its assumptions. The parser counts the engine's
  "Reached cover statement" and "Unreached cover statement" lines, and records
  `covers_reached` and `covers_unreached` as metrics, with one `COVER`
  diagnostic (file and line) per unreached cover.
* **The same precheck as the proof:** the `.sby` must list every submitted RTL
  file in `[files]` (M26's `_sby_reads`). A multi-task setup (`[tasks]`) is a
  recorded failure: its options carry task prefixes the copy cannot rewrite
  safely.

It is wired as data: `NOT_VACUOUS` is a before-review requirement with
`when_produced=("formal_spec",)`, so it applies exactly when formal does. A
`.sby` whose proof passes but whose covers are unreachable is refused at
submission (P9), and the failed cover run stays on the task, unsubstantiated,
as evidence. With the repair loop on, it goes back to the seat like any other
refusal.

### What this catches, and what it does not

Caught: assumptions that contradict each other or the design on the way to a
covered state, over-constrained inputs, and an antecedent the seat covers that
cannot fire. A plain `assume (1'b0)` was already caught by `formal.run` (smtbmc
reports the assumptions unsatisfiable, an ERROR); it fails the cover run too.

Not caught, and left to the reviewer: an antecedent the seat did not cover,
and a cover written to be trivially true (`cover (1)`). A tool cannot decide
which behaviors matter; the covers make the seat say which ones it meant, in
the file the reviewer reads. Automatic antecedent covers (one per `if` guarding
an assertion) are deferred.

### Why a separate tool and not a mode of `formal.run`

A cover run is bounded model checking, not a proof. If it were `formal.run`
with `mode=cover`, a cover run would meet "Formal properties are proven",
since `satisfies` only checks the parameters a requirement names. A separate
tool keeps the two claims apart with no new rule.

---

## 4. The fixtures

Every fixture proof now has covers, each reached under its assumptions, and
each chosen to show that a guarded property fires:

| Block | Covers | What they show |
|---|---|---|
| `counter` | 1 | the count reaches `LIMIT` and wraps |
| AXI4-Lite | 8 | OKAY and SLVERR on both B and R; a written register read back nonzero; address before data and data before address; B and R held under backpressure |
| FIFO (depth 8 and 5) | 6 | full; a write while full and a read while empty (the overflow and underflow guards fire); simultaneous read and write; the write pointer wraps; the tracked word read out |
| Arbiter (N 4 and 5) | 2 per requester | every requester is granted, and every requester waits the full bound of N - 1 cycles (the fairness bound is tight) |
| APB | 4 | a full-word write, a partial-strobe write, a written register read back nonzero, and PSLVERR |

The APB proof's depth rises from 4 to 8: a write and a read back need reset,
two setup cycles, and two access cycles, which a bound of 4 cannot reach. The
proof still passes at 8. The covers are under `` `ifdef FORMAL ``, invisible to
Verilator lint, Icarus, and Yosys synthesis, so every fixture stays lint-clean
(the fixture tests lint them unchanged).

---

## 5. Migrated tests

Only tests whose flow reaches one of the three RTL stages changed. None of
their assertions was removed or loosened; where a set of tools is asserted
exactly, it gains `formal.cover`.

| Test | Why it changed | How |
|---|---|---|
| `tests/nirmaan_helpers.py`: `work` and new `gated_submit` | `drive` submitted every task first and attached attestations after; a gated task is now refused at submission | For a task with before-review checks, `drive` writes real files (`counter.v` as `rtl_source`, `counter_tb.v` as `testbench`), runs every applicable check through the broker with parameters filled from the requirement's own data, records the runs as evidence, and only then submits, with the files' locations. Tasks without such checks are driven as before. A gated kind with no fixture file is an error, never a skip. |
| `test_nirmaan_work.py::test_signoff_needs_evidence_and_claims_never_count` | drives `new-ip` past the RTL stage to `rtl-lint` | `@needs(*GATE_TOOLS)`; assertions unchanged |
| `test_nirmaan_work.py::test_a_whole_project_completes_only_under_the_rules` | drives all of `new-ip`, five RTL tasks | `@needs(*GATE_TOOLS)`; assertions unchanged, and every RTL task now completes on real runs |
| `test_nirmaan_eda.py::test_real_lint_substantiates_the_rtl_lint_requirement` | drives `new-ip` to `rtl-lint` | its `needs` gains `GATE_TOOLS` |
| `test_nirmaan_export.py::test_a_real_lint_runs_log_and_result_are_copied` | the same | the same |
| `test_nirmaan_design_agents.py::test_small_blocks_plan_the_block_workflow` | asserts the exact set of gated tools | the set gains `formal.cover` |
| `test_nirmaan_design_agents.py::test_the_axi4_lite_register_block_is_designed_by_agents` | asserts the exact set of runs on the RTL task | the set gains `formal.cover`; still every run passes |
| `test_nirmaan_formal_gate.py::test_passing_synthesis_and_formal_allow_review` | the same | the set gains `formal.cover`, and the cover run is asserted to cover the submitted `.sby` |

`GATE_TOOLS` is `verilator iverilog vvp yosys`. On a machine without them these
tests now skip, instead of passing on attestations; in CI they are required
(`NIRMAAN_REQUIRE_EDA`), so they fail rather than skip. The FIFO, arbiter, and
APB end-to-end tests (`test_nirmaan_more_blocks.py`) are unchanged: their seats
already write the fixture `.sby`, and the fixture covers make the new check
pass. The demos (`nirmaan/demos.py`) only plan, so they needed no change.

---

## 6. Laws, each pinned by a test

In `tests/test_nirmaan_gates_everywhere.py`:

1. The three RTL stages and `block-design` carry exactly `RTL_GATES`;
   `NOT_VACUOUS` is before-review, `formal.cover`, tied to `formal_spec`.
2. The planned RTL tasks are gated, their capability requires approved inputs,
   formal and non-vacuity are unmet only once a `.sby` exists, and the seat is
   told both apply only if it writes one.
3. Approved inputs are checked through a gate (`new-ip`), and an unapproved
   impact analysis cannot start an `rtl-change`.
4. On each of the three workflows: a latch in the RTL answer blocks review
   (lint and simulation pass, synthesis fails on `max_latches`); a failing
   self-check blocks review; clean RTL with a proof passes all five checks,
   reaches review, and is approved.
5. A vacuous proof is refused, as a recorded, unsubstantiated failed run,
   while `formal.run` on the same files passes: over-constrained, and
   contradictory on the path. A plain `assume (1'b0)` fails both runs.
6. A proof with no covers is refused.
7. Every fixture proof reaches all its covers (seven setups, four blocks plus
   the counter and the parameter variants).
8. The cover run writes nothing beside the submitted files and uses the
   seat's own bound and script; a `[tasks]` setup and a setup that does not
   read the RTL are recorded failures.
9. The parser, on captured SymbiYosys output, with no tools installed.
10. Crown jewel: a fourth workflow (`parameter-change`, via an extension) is
    gated by data alone, with no core change.
11. `drive` runs every check before it submits (read from the audit order).
12. The runtime, policy, planner, and models never name `formal.cover`;
    `eda.py` never imports VeriTriage; CI requires `sby` and `yices-smt2`
    alongside the gate tools. The M19 import laws are unchanged and still
    tested.

---

## 7. Deferred

* The same gates on the other stages that write RTL with `rtl.implement`:
  `parameter-change` `rtl-change`, `regression-investigation` `rtl-fix`, and
  `timing-closure` `rtl-fix` (the crown jewel shows it is a data edit), and on
  `new-ip` `cdc-design` (`rtl.cdc_design`).
* Automatic antecedent covers, derived from the `if` guarding each assertion.
* Multi-task `.sby` setups in the cover check.
* A formal-properties seat separate from the RTL seat.

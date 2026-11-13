# Block verification: verify an existing block's RTL, gated (M68)

Wave 2 of the capability build-out (council record
`council/records/2026-10-18-capability-buildout.md`, section 10: Verification).
A verification skill is judged at a seat of an eval case, the way the RTL
pilot's skills are judged at block-design's RTL seat (`docs/RTL_PILOT_ROUTING.md`).
The must-fail scorer (M58, `docs/EVAL_SKILLS_MUST_FAIL.md`) already judges a
seat's testbench or proof. This milestone gives a verification eval case a seat
to judge, and gives "bring your RTL, we verify it" a workflow.

## The gap

- No workflow fits a verification seat. The DV stages live inside new-ip,
  feature-addition, parameter-change, rtl-change, regression-investigation and
  the closure workflow, and none of them checks the seat's own testbench or
  proof before review: `dv.directed_tests` and `dv.random_tests` name tools
  but no files, and `dv.assertions` asks for no run at all. The must-fail
  scorer takes the testbench's top module from the seat's own passing run
  before review, so a DV seat needs that gate first. Only block-design's
  `dv-plan` (vplan.check) was gated.
- "Verify the existing interrupt controller RTL." matched no intent.

## The workflow

`block-verification` (intent `block_verification`), in
`company/workflows.py`:

| Stage | Capability | Depends on | Checked before review |
|---|---|---|---|
| `interface-spec`: the block's specification, handed over | `arch.interface` | | none (reviewed) |
| `design-under-test`: the RTL, as handed over | `rtl.implement` | interface-spec | none (reviewed) |
| `dv-plan`: verification plan | `dv.plan` | interface-spec | `vplan.check`: the plan covers every requirement of the approved spec |
| `testbench`: self-checking testbench | `dv.directed_tests` | interface-spec, design-under-test | `simulator.run` over the approved RTL and the seat's testbench, top from the testbench |
| `assertions-formal`: properties and proof | `formal.prove` | interface-spec, design-under-test | `formal.run` over the seat's .sby, the approved RTL and the seat's property files, at least one property proven; `formal.cover` over the same: every cover reached |
| `coverage` (when asked) | `dv.coverage` | testbench | none yet: `coverage.read` is a contract (recorded evidence) |
| `equivalence` (when asked) | `formal.equivalence` | design-under-test | none yet: `equivalence.run` is a contract (recorded evidence) |

The RTL is never written here: `design-under-test` records the existing RTL
and its review approves it, and every DV gate reads that approved file, never
a file of the seat's own. It is the one stage with `rtl_source` among its outputs
that does not carry the RTL gates (lint, the RTL's own testbench, synthesis): it
writes no RTL and has no testbench, and handed-over RTL that fails Verilator's
lint is still verified. `test_every_stage_that_produces_rtl_is_gated` names it
as that one exception. No gate task precedes a seat, so an eval case fixes
`interface-spec` and `design-under-test` from its own files and judges any DV
seat. The plan, the testbench and the proof run side by side, as block-design's
plan does: nothing waits on the plan.

**Intent.** A request that starts with "Verify" or "Formally verify", or with
"Write a testbench (tests, assertions, properties, a formal proof) for". It
sits after rtl-change and before every build intent (priority 47), so a request
that builds or changes something and also says "verify" keeps its intent:
"Create a FIFO and verify it" is still block-design, "Verify the RTL fix to
the arbiter" is still rtl-change.

## Two runtime additions

Both are data on a gate's file bindings; nothing names a stage or a tool.

1. **Two bindings of one parameter add up.** `simulator.run` takes one
   `sources` list. The testbench gate binds it twice: the approved upstream
   RTL and the seat's testbench. Before, a second binding of a parameter
   replaced the first; no workflow had one, so nothing else changes. The
   policy already checked each binding on its own (each approved upstream
   file, and each submitted file of the seat's, must be in a passing run).
2. **`FileInput.beside`.** A .sby names its files relative to itself, and the
   seat sees the approved RTL's file name, not its location. An upstream
   binding marked `beside` is linked, under its own name, into the folder of
   each of the task's own files that the same check reads, before the tool
   runs, so `[files] counter.v` reads the approved file itself. The formal
   backend's check that every given source is in the .sby's `[files]`
   compares resolved paths, so a run that read some other `counter.v` is
   refused. A seat file with that name is never replaced: the run then reads
   the seat's file and is refused, and the work does not reach review
   (tested). The prompt tells the seat the approved files sit beside its
   files under their own names. The must-fail scorer stages every input under
   its own name in one folder, so one setup serves the gate and the judge.

## Refinements

Features with no routing context of their own (M66's pattern): they refine
this workflow's tasks or plan its optional stages, and no other workflow reads
them.

| Feature (words) | Effect |
|---|---|
| `systemverilog` ("SystemVerilog") | testbench task adds `systemverilog` |
| `random_stimulus` ("random", "constrained-random", "randomized") | testbench task adds `constrained_random` |
| `unbounded_proof` ("unbounded", "induction", "k-induction") | proof task adds `model_checking` |
| `coverage` ("coverage") | plans the coverage stage (`code_coverage`) |
| `equivalence` ("equivalence", "equivalent") | plans the equivalence stage (`equivalence_checking`) |

Stage skills: `verification_planning` on the plan, `directed_testing` on the
testbench, `formal_verification`, `sva` and `assertion_coverage` on the proof
(every proof here must reach its covers). The testbench uses
`dv.directed_tests`, whose provider is `directed_testing`; with
`dv.testbench` the packet would carry the `uvm` card as the seat's provider,
and nothing here runs UVM.

## Who gets each task

| Request | Stage | Task skills | Owner | Reviewer |
|---|---|---|---|---|
| Verify the existing interrupt controller RTL. | dv-plan | verification_planning | planning engineer | planning senior |
| same | testbench | directed_testing | simulation SystemVerilog senior | simulation tech lead |
| same | assertions-formal | formal_verification, sva, assertion_coverage | formal property senior | formal model checking senior |
| ... with a SystemVerilog testbench | testbench | directed_testing, systemverilog | simulation SystemVerilog senior | simulation tech lead |
| ... with constrained-random stimulus | testbench | directed_testing, constrained_random | simulation testbench senior | simulation tech lead |
| ... with an unbounded proof | assertions-formal | adds model_checking | formal model checking senior | formal property senior |
| ... with coverage | coverage | code_coverage | code coverage engineer | code coverage senior |
| ... with an equivalence check | equivalence | equivalence_checking | formal equivalence engineer | formal model checking senior |

Every seat's packet, for the owner and the reviewer, carries every task skill,
within the domain cap, also for a request with every feature at once.

## What does not change

Every request that is not a block verification plans exactly as before, task
for task. The test builds the organization without M68's data (no new intent,
features or workflow) and compares every task of every representative request
in the golden suite, plus five that say "verify" mid-sentence or name a new
feature in another workflow. The golden file
(`tests/fixtures/applicability/plans.txt`) only gains the two
block-verification requests; the `[beside]` marker appears on those alone. No
existing stage, gate, evidence requirement or role changes; the RTL-gate law
test gains the one exception above, by name.

## Tests

`tests/test_block_verification.py`: planning and gates; each DV seat's task
skills, owner, reviewer and packet; the domain cap; the prompt's beside line;
the before-and-after comparison; and, with real tools through the eval harness
(`run_case`), a testbench seat and a proof seat on the M21 counter whose gates
pass over the approved RTL and whose must-fail checks catch a wrap mutant, and
a proof seat that ships its own `counter.v` and is refused.

## Not in this milestone

- Refinements that need new skill ids: scoreboard or reference model
  (`reference_modelling`) and cocotb (`python_verification`). Each is one
  feature and one `Refinement` when its skill lands.
- The coverage and equivalence gates: they wait for `coverage.read`
  (verilator_coverage) and `equivalence.run` (eqy) to be wrapped as
  AVAILABLE tools, each its own milestone.
- Repro testbenches on regression-investigation's root-cause and triage
  stages, and a scorer over several seat testbenches.
- The verification eval cases themselves, and the department cut. The role ids
  in the tests are today's; a cut that renames them moves the tests with it.

No count other than workflows changes (`scripts/status.py --write`): no new
skill, tool, unit or principle.

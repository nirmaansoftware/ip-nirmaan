# Formal and Synthesis Before Review, and Formal in CI (Milestone 26)

Status: design for the owner's review, implemented on branch `m26/formal-gate`.
This closes two items from the "Where we are" table in `docs/ROADMAP.md`:
"Formal and synthesis as before-review checks" and "formal in CI". Prose here
is free of em and en dashes per the standing style law.

M21 made `synth.run` (Yosys) and `formal.run` (SymbiYosys) real tools. M23
gated the `block-design` RTL stage on real lint and simulation before review.
M26 adds synthesis and formal to that gate, as data, and makes CI run formal
for real instead of skipping it.

---

## 1. What changes, in one table

| Piece | Where | Kind of change |
|---|---|---|
| Synthesis before review, no latches | `company/workflows.py`, the `block-design` rtl stage | data |
| Formal before review, when the seat supplies a `.sby` | same stage | data |
| `EvidenceRequirement.params`: fixed tool parameters | `models/workflow.py`, read by the runtime and `satisfies` | one generic field |
| `EvidenceRequirement.when_produced`: a requirement that applies only when a file of some kind was produced | `models/workflow.py`, read by the runtime and the policy | one generic field |
| `max_<metric>` limits on any EDA run | `integrations/eda.py`, `execute` | generic, not per tool |
| `formal.run` checks that the `.sby` reads the submitted RTL | `integrations/eda.py`, the SymbiYosys backend | backend precheck |
| SymbiYosys and Yices in CI, from the OSS CAD Suite | `.github/workflows/ci.yml` | CI |

No seat, stage, tool, or kind is named by the runtime, the policy, or the
engine. The two new fields are general: any future before-review check can use
them without touching core code (the crown-jewel test proves it).

---

## 2. Synthesis before review

The rtl stage gains:

```python
checked("Synthesizes with Yosys, with no latches", "synth.run",
        FileInput(param="sources", kinds=("rtl_source",)),
        FileInput(param="top", kinds=("rtl_source",), entry=True),
        params=(("max_latches", "0"),))
```

The run is over the produced RTL only (not the testbench), with the top the
RTL file declares as its entry. It is always required: every block that goes
to review must synthesize.

**Latches.** Yosys `synth` does not fail on an inferred latch, but the M21
parser already counts them (`metrics.latches`, from `stat -json`). An inferred
latch in a small synchronous block is nearly always an incomplete
`always @(*)`, so the stage forbids them. That is expressed as a fixed tool
parameter, `max_latches=0`, which reaches the tool through a new
`EvidenceRequirement.params` field.

**Limits are generic.** `eda.execute` treats every `max_<metric>` parameter as
a limit on the parsed result's metric of that name. A run over the limit is a
recorded failed run ("latches 2 exceeds max_latches 0"). A limit on a metric
the backend did not report also fails: a limit that could not be checked is
not a limit that was met. Nothing in `eda.py` names latches.

**A run with other options does not count.** `satisfies` (the P9 helper that
decides whether evidence meets a requirement) now also requires a tool run to
have been made with every fixed parameter the requirement names. A person who
synthesizes by hand without `max_latches` produces a real run, but not one that
meets this requirement.

---

## 3. Formal before review

### How the seat supplies properties

Formal needs two things synthesis does not: properties and a proof setup. The
seat supplies them as files, the same way it supplies RTL:

* **Properties** live in the RTL under `` `ifdef FORMAL `` (the SymbiYosys
  convention, and what both fixtures already do), so they are read by the
  reviewer with the RTL and are invisible to lint, simulation, and synthesis.
* **The setup** is a `.sby` file the seat writes, of a new artifact kind
  `formal_spec`. Its `[files]` section names the RTL by relative path; the
  runtime writes every file of an answer into the same attempt directory, so
  the path resolves to the exact bytes submitted.

The rtl stage gains:

```python
checked("Formal properties are proven", "formal.run",
        FileInput(param="sby", kinds=("formal_spec",)),
        FileInput(param="sources", kinds=("rtl_source",)),
        when_produced=("formal_spec",))
```

`sby` is the tool's own parameter. `sources` names the RTL files the proof
must cover. The M23 coverage law then applies unchanged: at submission the
passing formal run must name every submitted `formal_spec` and every
submitted `rtl_source`, so a proof over an earlier attempt's files does not
let a new attempt through.

### The run must read the RTL it claims to cover

A `.sby` is free to read any file. Passing `sources` alone would let a setup
prove a different module and still "cover" the submitted RTL by name. So the
SymbiYosys backend gains a precheck: when `sources` is given, every source
must be listed in the `.sby`'s `[files]` section (resolved against the `.sby`'s
own directory). If one is not, the run is a recorded failure that says which
file the setup does not read. This does not prove the `[script]` reads the
file (a setup could still list it and prove something else); that is left to
the independent RTL reviewer, who reads the `.sby` as one of the artifacts
under review.

### Required or conditional for `block-design`: conditional

Formal applies only when the seat produces a `formal_spec` file. The
requirement's new `when_produced=("formal_spec",)` field says so, as data:

| The answer | Formal | Task |
|---|---|---|
| No `.sby` | not run, not required, not claimed | reviewed on lint, simulation, and synthesis |
| A `.sby` and `sby` on PATH, proof passes | recorded passing run | may go to review |
| A `.sby`, counterexample or error | recorded failing run | refused at submission (P9) |
| A `.sby`, `sby` not on PATH | refused by the broker, nothing recorded | blocked, with the reason |

Why conditional and not required:

1. **Property quality cannot be checked by a tool.** A required `.sby` invites
   a vacuous one: a setup with no assertions, or assertions that hold
   trivially, passes `sby`. A gate that any seat can meet with an empty proof
   is a claim of formal verification that did not happen. When formal is
   present it is real and must pass; when it is absent, nothing says it ran.
2. **Not every small block has a useful property set at first.** A counter or
   a register block has protocol properties worth proving; a trivial glue
   block may not. The seat, and then the reviewer, decide.
3. **It does not couple unrelated blocks.** Other blocks on this workflow
   (FIFO, arbiter, APB, being added in parallel) keep working unchanged, and
   gain formal the moment their seat writes a `.sby`.

The residual risk is a seat that drops a failing `.sby` on its next attempt.
That is visible: the failed formal run stays on the task as evidence, and the
reviewer sees it. Making formal required for a particular block is one data
edit (remove `when_produced`), or later a feature condition on the stage.

`when_produced` is read in three places, none of which names formal:

* the runtime's post-flight step skips a requirement whose kinds were not
  produced (it neither runs nor reports the tool);
* the `evidence-before-review` check skips it when no submitted artifact is of
  those kinds;
* `unsatisfied_requirements` (approval, blockers, the dashboard) skips it
  when none of the task's artifacts is of those kinds.

The prompt tells the seat: "applies only if you produce a formal_spec file".

### Never counting a formal run that did not run

* A `formal.run` without `sby` on PATH is refused by the broker; no run is
  recorded, and the task is blocked with the reason (M23's rule).
* A model listing a formal run that never happened is refused by P5, as for
  any claimed run.
* An unknown status (a timeout, an engine error) is a failing run; only
  SymbiYosys's `DONE (PASS)` with exit status 0 passes (M21's parser).

---

## 4. Formal in CI

Ubuntu's apt has no `sby`. The test job now downloads the YosysHQ OSS CAD
Suite, pinned to release **2026-09-28**
(`oss-cad-suite-linux-x64-20260928.tgz`, 745 MB, 2.5 GB extracted), streamed
straight into `tar` under `$RUNNER_TEMP`. It is not cached: a cache of the
extracted suite is about as large as the download, and restoring it is no
faster than downloading and extracting from GitHub's own release storage.
YosysHQ keeps each daily release for over a year; moving the pin is a
one-line change.

**PATH choice: only `sby` and its solver.** The suite also ships Verilator,
Icarus, and Yosys, at versions different from apt's (Yosys 0.33 in apt). If
the suite's `bin` went on PATH, every lint, simulation, synthesis, DFT, and
firmware test would silently change tools. So CI writes two small wrapper
scripts, `sby` and `yices-smt2`, into a directory of their own and puts only
that directory on PATH. Each wrapper `exec`s the suite's own launcher, which
sets up the suite's environment for that process, so SymbiYosys runs the
suite's Yosys and `yosys-smtbmc` internally (a matched set), while the tests'
own `yosys`, `verilator`, and `iverilog` stay apt's. The job prints both
versions so the log shows which is which.

`NIRMAAN_REQUIRE_EDA` gains `sby` and `yices-smt2`, so every formal test fails
in CI if the tools are missing, instead of skipping.

---

## 5. Laws, each pinned by a test

In `tests/test_nirmaan_formal_gate.py`:

1. RTL that fails synthesis cannot reach review; the failed `synth.run` is a
   recorded run.
2. RTL that infers a latch cannot reach review; the run fails on
   `max_latches`.
3. A formal counterexample keeps RTL from review, even when lint, simulation,
   and synthesis pass (an AXI4-Lite read channel that accepts a second read
   while one is pending: the testbench never tries it, the proof finds it).
4. A `.sby` that does not read the submitted RTL fails its run.
5. Passing synthesis and formal allow review; without a `.sby`, formal is
   neither run nor required.
6. Without `sby` on PATH, a produced `.sby` blocks the task and no formal run
   is recorded.
7. A model claiming a formal pass it never ran is refused (P5).
8. A synthesis run made without the requirement's fixed parameters does not
   meet it.
9. Crown jewel: a new before-review check, with fixed parameters and a
   produced-kind condition, needs no core changes.
10. With the M26 repair loop (`docs/REPAIR_LOOP.md`), a counterexample is
    repairable like any before-review refusal: the refused attempt, its
    `.sby`, and its failed proof are kept as an `Attempt`, never as the task's
    artifacts, and the next attempt's proof covers only the new files.

The AXI4-Lite demo (`test_the_axi4_lite_register_block_is_designed_by_agents`)
now has the RTL seat answer with `axi4_lite_regs.sby` too; lint, simulation,
synthesis, and formal all pass before review. The import laws are unchanged
and still tested.

---

## 6. Deferred

* A formal-properties seat separate from the RTL seat (properties written by
  someone other than the designer). The vacuity check (cover statements that
  must be reachable) is done in M27, see `docs/GATES_EVERYWHERE.md`.
* Formal and synthesis on the `new-ip`, `feature-addition`, and `rtl-change`
  RTL stages: done in M27.
* Checking that the `.sby` `[script]` reads the listed RTL, beyond `[files]`.
* Switching all of CI to the OSS CAD Suite's tools.

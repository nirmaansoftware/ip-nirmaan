# Architecture and RTL Agents (Milestone 23)

Status: design for the owner's review, implemented on branch
`m23/design-agents`. This is Stage 4 of `docs/ROADMAP.md`. Prose here is free
of em and en dashes per the standing style law.

M20 seated language models where their output can be checked: verification
debug, against VeriTriage. M21 made lint, simulation, synthesis, and formal
real. M23 puts the two together and seats models in design: interface
specification, microarchitecture, and RTL implementation. Design work is the
place where a model's output is most tempting to trust and easiest to check,
because the RTL either passes Verilator and a self-checking testbench or it
does not.

```
nirmaan plan "Create an AXI4-Lite register block."
nirmaan run <project> interface-spec --runtime anthropic --input workspace=work/
nirmaan run <project> interface-spec --runtime anthropic --review
nirmaan task approve <project> interface-spec --as <approver>
...                                    # microarchitecture, then rtl-implementation
```

---

## 1. The laws (M20's, plus three)

M20's laws hold unchanged: agents propose and the engine decides; evidence is
a record, not a sentence; cite or be stripped; independence is structural; off
by default. M23 adds:

1. **Only approved inputs.** A design seat works only from upstream artifacts
   at assurance `APPROVED`. Anything less is refused before a model is asked,
   with the artifact and its assurance named.
2. **Checked before review.** Work whose evidence requirement is marked
   `before_review` cannot be submitted for review until that requirement is
   met, by runs over the exact files being submitted. RTL goes to a reviewer
   only after real lint and a real simulation passed on it.
3. **Files are artifacts with provenance.** A file a model writes is recorded
   with where it is, a digest of its bytes, who produced it, and which approved
   artifacts it was derived from. A reader can tell if it changed since.

None of these name a seat. Each is data on a capability or an evidence
requirement, enforced by a registered policy check or by the one
`ModelRuntime`.

---

## 2. The first IP: an AXI4-Lite register block

The roadmap's example was a round-robin arbiter. The first IP is instead an
AXI4-Lite register block: four 32-bit registers behind the five AXI4-Lite
channels (`axi4_lite_regs`, `ADDR_WIDTH = 4`, `DATA_WIDTH = 32`). It is still
small and self-contained, but it has a real protocol with a written
specification, handshakes a testbench can get wrong, and byte strobes, so the
three seats each have something to decide. FIFO, arbiter, and APB register
blocks follow as later blocks on the same workflow.

### A workflow for small blocks

`new-ip` plans roughly thirty tasks (documentation, DFT, STA, release) and fans
RTL out per feature, which is the right shape for a bridge and the wrong one
for a register block. So small blocks get their own workflow, as data in
`company/workflows.py`:

| Stage | Capability | Output | Evidence |
|---|---|---|---|
| `requirements` | `req.analyze` | `requirements_spec` | independent review |
| `interface-spec` | `arch.interface` | `interface_spec` | independent review |
| `microarchitecture` | `arch.microarchitecture` | `microarchitecture_spec` | independent review |
| `rtl-implementation` | `rtl.implement` | `rtl_source`, `testbench` | review; `lint.run` and `simulator.run` over the produced files, before review |

A new intent, `block_design`, recognizes register blocks, register files,
FIFOs, arbiters, and counters, ahead of `new_ip`. "Create a 4-port AXI-to-NoC
bridge" still plans `new-ip`. Demo 8 is "Create an AXI4-Lite register block."

The RTL seat writes the testbench as well as the RTL. A separate verification
seat for the testbench is the natural next refinement (it is one more stage);
for now the independent RTL reviewer reads both.

---

## 3. Approved inputs only

A capability gains one field:

```python
_cap("arch.interface", ..., approved_inputs=True)
_cap("arch.microarchitecture", ..., approved_inputs=True)
_cap("rtl.implement", ..., approved_inputs=True)
```

Two places read it, and neither names a capability:

* **The constitution.** A new check, `approved-inputs`, joins P8
  (Provenance). On `task.start` it refuses a task whose capability requires
  approved inputs while any artifact of a task it depends on is below
  `APPROVED`. `run_task` starts the task before it asks the model, so the
  refusal comes first and no prompt is rendered. It binds people too: a human
  RTL engineer does not start from a withdrawn microarchitecture either.
* **The prompt.** For such a task, an upstream artifact below `APPROVED` is
  withheld from the prompt (the line says so), which is what `--dry-run` shows.

How an upstream artifact can be unapproved while its task is finished: a
dependency that was cancelled after it was submitted (withdrawn before review)
counts as satisfied for readiness, but its artifacts stay `EXECUTED`. The test
builds exactly that.

Approved upstream artifacts also become **citable** for every seat, as
`[artifact:<id>]` (the ID with `:` and `#` replaced by `.`, as for evidence).
Unapproved ones never are. When an approved artifact is a file, its content is
rendered into the prompt after its digest is checked, so the RTL seat reads the
microarchitecture that was approved, byte for byte.

---

## 4. Model output that carries files

M20's answer is one JSON object. M23 adds an optional `files` list to it, and
the file contents follow the object in delimited blocks:

```
{"uncertainty": 0.2,
 "files": [
   {"path": "axi4_lite_regs.v", "kind": "rtl_source", "title": "AXI4-Lite register block",
    "summary": "Implements the approved microarchitecture [artifact:prj-1.microarchitecture.a1].",
    "entry": "axi4_lite_regs"},
   {"path": "axi4_lite_regs_tb.v", "kind": "testbench", "title": "Self-checking testbench",
    "summary": "Exercises every register [artifact:prj-1.microarchitecture.a1].",
    "entry": "axi4_lite_regs_tb"}],
 "artifacts": [], "tool_runs": [], "claims": [], "escalation": null, "notes": ""}
=== FILE: axi4_lite_regs.v ===
module axi4_lite_regs ...
endmodule
=== END FILE ===
=== FILE: axi4_lite_regs_tb.v ===
...
=== END FILE ===
```

**Why blocks and not a JSON string.** The content is taken verbatim: no JSON
escaping of quotes and backslashes in Verilog (escaped identifiers, `$display`
strings), and the line numbers in a lint diagnostic are the lines the model
wrote. The blocks are split off before the JSON is parsed, because Verilog is
full of braces and M20's parser takes the outermost `{...}`. The delimiter
lines (`=== FILE: <path> ===`, `=== END FILE ===`) do not occur at the start of
a Verilog, SystemVerilog, or Markdown line in practice.

**What is checked.**

| The answer | What happens |
|---|---|
| A `files` entry with a matching block, whose summary cites a declared token | Written, recorded as an artifact |
| A summary that cites nothing | Dropped and reported, not written (M20's rule for artifacts) |
| A `files` entry with no block, or a block with no entry | Dropped and reported |
| A path that is absolute, contains `..`, or has other characters | Dropped and reported |
| An unterminated or duplicate block | Dropped and reported |

File content is never grounded: `[3:0]` is a Verilog range, not a citation.
Only the summary is.

**Where files go.** Under the task's `workspace` input when one is given
(`nirmaan run ... --input workspace=DIR`), else a fresh temporary directory:
`<workspace>/<task>/<attempt>/<path>`. Each execution gets a new attempt
directory, so a later attempt never overwrites the files an earlier run
checked.

**Provenance.** Each kept file becomes an artifact with:

| Field | Value |
|---|---|
| `location` | the absolute path written |
| `digest` | `sha256:<hex>` of the bytes written (new optional `Artifact` field) |
| `derived_from` | the approved upstream artifacts its summary cites |
| `produced_by` | the actor label, set by the engine as for any artifact |
| `summary` | the grounded description |

The P8 `provenance` check already refuses `derived_from` IDs that do not exist.
When a later prompt renders the file, the digest is recomputed; a mismatch is
stated in the prompt and the content is withheld.

---

## 5. Checked before review

An evidence requirement gains two optional fields:

```python
EvidenceRequirement(
    description="Self-checking simulation passes", accepts=(K.TOOL_RUN,), tools=("simulator.run",),
    files=(FileInput(param="sources", kinds=("rtl_source", "testbench")),
           FileInput(param="top", kinds=("testbench",), entry=True)),
    before_review=True,
)
```

* `files` says how the task's own produced files feed the tool: each
  `FileInput` fills one tool parameter with the paths of the files of those
  kinds (joined with commas), or, with `entry=True`, with the entry point the
  first such file declared. A requirement with `files` runs **after** the model
  answers (it needs the files); one without runs before, as in M20.
* `before_review` makes a new check, `evidence-before-review` (joined to P9,
  Evidence for signoff), refuse `task.submit` until the requirement is met by
  substantiated evidence. When it has `files`, the passing runs must cover
  every submitted artifact of those kinds: a lint run over the previous
  attempt's files does not let a new attempt through.

**The sequence for an RTL seat.**

```
run_task
  engine.start                        P8 approved-inputs checked here
  ModelRuntime.execute
    pre-flight tools (M20)            requirements without files
    prompt -> model -> JSON + file blocks
    ground summaries, write kept files, digest them
    post-flight tools                 lint.run, simulator.run over the files
  record evidence for every run       failed runs are recorded, unsubstantiated
  engine.submit                       P9 evidence-before-review checked here
```

| Outcome of the runs | Result | Task |
|---|---|---|
| Lint and simulation pass | `submitted` | `in_review`, with the file artifacts |
| Lint or simulation fails | `refused`, with the engine's reason | stays `in_progress`; failed runs are on it as evidence; no artifacts |
| A tool cannot run here (executable missing) | `blocked`, with the broker's reason | `blocked`; nothing was simulated |
| The model lists a run that never happened | refused by P5, as in M20 | stays `in_progress` |

A refused submission is reported rather than raised. The runs that failed are
real, and saving them is the point: the next attempt, or a person, can read
the logs. (`run_task` catches only a constitution refusal at submission; every
earlier refusal still raises, exactly as in M20.)

The review gate is enforced by the engine, not the runtime: the runtime never
decides whether work may go to review, it only proposes a submission. A person
submitting through the CLI meets the same check.

---

## 6. What the seats see

| Seat | Upstream it reads | It cites | Its files |
|---|---|---|---|
| Interface specification | the approved requirements | `[artifact:...]` of the requirements | `interface_spec` (Markdown) |
| Microarchitecture | the approved interface spec, content included | the spec | `microarchitecture_spec` (Markdown) |
| RTL implementation | the approved microarchitecture, content included | the microarchitecture | `rtl_source`, `testbench` (Verilog) |
| Any reviewer | the files under review, content included, and the runs | the runs and evidence | none |

Every row comes from the packet: the task's expected outputs, its evidence
requirements, and its upstream artifacts. `ModelRuntime` has no branch for any
of them.

---

## 7. Extension points

| To add | Do this | Core changes |
|---|---|---|
| A new design seat | A capability with `approved_inputs=True`, a skill that provides it, a unit that holds the skill, a workflow stage | none |
| A new check over produced files | An `EvidenceRequirement` with `files` and `before_review`, naming any AVAILABLE tool | none |
| A new checking tool | A catalog entry plus `register_binding` (or an EDA `register_backend`) | none |

The crown jewel `test_a_new_design_seat_needs_no_core_changes` adds a register
map seat, with its own capability, skill, unit, intent, workflow, and a
`regmap.check` tool bound in the test. The seat writes a JSON file, the tool
checks it before review, a malformed map is refused, and a well-formed one is
reviewed and approved.

---

## 8. Laws, each pinned by a test (`tests/test_nirmaan_design_agents.py`)

1. An RTL seat with an unapproved upstream artifact is refused before any model
   call, and the prompt withholds that artifact.
2. RTL whose real lint fails cannot reach review; the failed run is recorded.
3. RTL that passes real lint and simulation goes to review with its files as
   artifacts, digested and derived from the approved microarchitecture.
4. A model claiming a lint or simulation run that never happened is refused
   (P5).
5. A design seat cannot review its own work (P6), and no model call is made.
6. An approved file reaches the next seat byte for byte; a file changed after
   it was recorded is withheld (digest mismatch).
7. With the tools absent, the broker refuses, nothing is recorded as a run, and
   the task is blocked with the reason.
8. The file-block parser rejects unsafe paths, orphans, and unterminated blocks.
9. Crown jewel: a new design seat with its own checking tool needs no core
   changes.
10. The AXI4-Lite demo: spec, microarchitecture, and RTL seats on scripted
    answers, real lint and simulation, reviewed and approved, every claim
    backed by a recorded run, against `tests/fixtures/rtl/axi4_lite/`.

---

## 9. Deferred

* A repair loop: handing the model its own lint or simulation log for a
  bounded number of retries. Today a failed attempt is refused and the next
  `nirmaan run` is a fresh attempt.
* A separate verification seat for the testbench.
* Applying `files` and `before_review` to the `new-ip`, `feature-addition`,
  and `rtl-change` RTL stages. It is a data edit, but the existing flows (and
  their tests) submit first and attach evidence later.
* FIFO, arbiter, and APB register blocks on the block workflow.
* Synthesis (`synth.run`) and formal (`formal.run`) as before-review checks.

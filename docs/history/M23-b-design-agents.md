# Milestone 23 - Architecture and RTL agents (roadmap Stage 4)

Model seats for interface specification, microarchitecture, and RTL
implementation, all filled by the one M20 `ModelRuntime` with no branch per
seat. The first IP is an AXI4-Lite register block (not the roadmap's original
arbiter). The mechanism is proven on the M21 counter, and end to end on the
AXI4-Lite fixture set above (`tests/fixtures/rtl/axi4_lite/`). Version bump
left to the coordinator.

**A small-block workflow, as data.** `block-design` (requirements ->
interface-spec -> microarchitecture -> rtl-implementation) with a new intent
`block_design` (register block/file/bank, FIFO, arbiter, counter; priority 55,
ahead of `new_ip`). Demo 8 is "Create an AXI4-Lite register block." The RTL
stage outputs `rtl_source` and `testbench`; the RTL seat writes both.

**Approved inputs only.** `Capability.approved_inputs` (True for
`arch.interface`, `arch.microarchitecture`, `rtl.implement`). A new check
`approved-inputs`, joined to P8, refuses `task.start` while any artifact of a
dependency is below APPROVED, so `run_task` fails before a prompt exists. The
prompt withholds such artifacts (for `--dry-run`). Approved upstream artifacts
are citable by every seat as `[artifact:<id>]`, and a recorded file's content
is rendered only while its digest matches.

**Files in model answers.** The JSON object gains `files` (path, kind, title,
summary, entry); contents follow as `=== FILE: <path> ===` ... `=== END FILE
===` blocks, split off before JSON parsing (Verilog braces) and kept verbatim
(`runtime/files.py`). Summaries are grounded like artifacts (uncited files are
dropped, not written); unsafe paths, orphans, duplicates, unterminated blocks
are rejected and reported. Kept files are written to
`<input.workspace or a temp dir>/<task>/<attempt>/` and become artifacts with
`location`, `digest` (`sha256:...`, new optional `Artifact` field),
`derived_from` (the approved artifacts cited).

**Checked before review.** `EvidenceRequirement` gains `files`
(`FileInput(param, kinds, entry)`: which produced files fill which tool
parameter) and `before_review`. Requirements with `files` run after the model
answers (post-flight); without, before (M20 pre-flight). A new check
`evidence-before-review`, joined to P9, refuses `task.submit` until each such
requirement is met by substantiated evidence whose runs cover every submitted
file of those kinds (so a pass on an earlier attempt's files does not count).
`run_task` now reports a constitution refusal at submission as
`ResultStatus.REFUSED` (task stays in progress, failed runs saved as evidence)
instead of raising; a runtime result `BLOCKED` (a before-review tool the broker
refused: executable missing) blocks the task with the reason. Earlier refusals
(P3, P4, P5, P8 at start) still raise.

Key design points worth not re-deriving:
- The review gate is the engine's (a policy check at submit), not the
  runtime's; a person submitting through the CLI meets it too.
- Upstream artifacts are "unapproved while the dependency is finished" only when
  the dependency was cancelled after submission; the test builds exactly that.
- `new-ip`, `feature-addition`, and `rtl-change` RTL stages are unchanged: their
  flows (and tests) submit before attaching evidence. Adopting `files` and
  `before_review` there is a data edit, deferred.

19 new tests in `tests/test_nirmaan_design_agents.py`, plus Demo 8 in the
demo test. `test_the_axi4_lite_register_block_is_designed_by_agents` runs the
spec, microarchitecture, and RTL seats on MockLLM answers scripted with the
fixture files, real Verilator lint and Icarus simulation, agent reviews and
human approvals, and checks every tool-run evidence record is a passing run. Crown jewel
`test_a_new_design_seat_needs_no_core_changes`: a register-map seat with its
own capability, skill, unit, intent, workflow, and `regmap.check` tool, refused
on an overlapping map and approved on a clean one. Design doc:
`docs/DESIGN_AGENTS.md`. Deferred: a repair loop feeding the lint/simulation
log back to the model, a separate testbench (DV) seat, synth and formal as
before-review checks, FIFO/arbiter/APB blocks.

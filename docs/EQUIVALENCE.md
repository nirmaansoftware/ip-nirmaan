# Logic equivalence through eqy (M69)

Wave 2 (Verification) of the capability build-out, item W2-T1, under the
founder's decision of 2026-10-30 (council record
`council/records/2026-10-18-capability-buildout.md`, "Founder decisions
(2026-10-30)", item "New tools for wave 2 (2026-11-13)": eqy,
verilator_coverage and cocotb may be wired into the tool broker, each in its
own milestone, no spending).

Until this milestone `equivalence.run` was `CONTRACT_ONLY`: the
block-verification workflow (M68) planned an equivalence stage when asked,
but its evidence could only be a recorded attestation. eqy, the equivalence
checker from YosysHQ, makes it a real run.

## The tool

eqy (ISC licence) reads a gold and a gate design with the Yosys scripts of an
`.eqy` setup, matches their signals by name, cuts the combined design into
partitions at the matched points, and proves each partition equivalent with
the setup's strategies (`sat`, or `sby` with a solver). It is installed beside
Yosys and run as a program; nothing of it is vendored here, so NOTICE does
not change.

| Tool ID | Backend | Executables | Parameters |
|---|---|---|---|
| `equivalence.run` | `eqy` (`nirmaan/integrations/equivalence.py`) | `eqy`, `yosys`, `make` | `eqy` (the setup, required), `sources` (RTL it must read), `workdir`, `timeout`, `backend` |

The backend is one `register_backend` call in its own module; the EDA core,
the broker, the engine and the policy do not change.

## What a run does

1. **Checks the setup before anything runs.** It is refused, and the refusal
   is a recorded failed run, when:
   - a script line reaches outside Yosys (`!`, `exec`, `tcl`, `python`,
     `script`, `plugin`): it could change the files the run compares;
   - a script writes a file (`write_*`, `tee`, `dump`): one side could read
     what the other wrote, and compare a design with itself;
   - the `[gold]` and `[gate]` scripts are the same, or one is missing;
   - it reads a file by an absolute path, outside its own folder (`..`), or
     one that is not there;
   - given `sources`, it does not read each of them (compared by resolved
     path, as `formal.run` compares a .sby's `[files]`).
2. **Runs over copies.** The setup and every file its scripts read are copied,
   under the names the setup uses, into `setup/` in the run's own directory
   (M53), and eqy runs there with its work directory beside it. A link (an
   approved file placed beside the seat's setup, M68) is copied as its
   content. Nothing is written next to the submitted files.
3. **Parses what eqy printed** (`eda_parsers.parse_eqy`). Only eqy's own
   lines count: eqy prefixes them `EQY <time> [<workdir>]`, and what a step
   prints comes after that step's name, so a design or script cannot print a
   line the parser reads as eqy's. A run passes only when eqy exited 0, said
   `DONE (PASS, ...)` and "Successfully proved designs equivalent", proved at
   least one partition, and failed none. A setup that proves nothing (every
   signal unmatched) is not equivalence.

The result's metrics: `status`, `exit_status`, `partitions`,
`partitions_proved`, `partitions_failed`, `equivalent` (1 only on a pass),
and `gold` and `gate`, the files each side read. The summary names them:
"equivalent: gate counter_refactor.v against gold counter.v: every partition
proved (2 of 2)". A partition eqy could not prove is an error diagnostic with
the reason its last strategy gave ("partitions not equivalent (strategy
sby)"). The log and the result JSON are the run's references, as for every
EDA tool (`docs/EDA_TOOLS.md`).

## The gate (gate semantics)

The block-verification workflow's `equivalence` stage (planned only when the
request asks for an equivalence check, M68) is now gated before review:

| Before | After |
|---|---|
| "Equivalence result with the compared versions named": a tool run or a human attestation, recorded, never checked before review | "The seat's setup proves the approved RTL versions equivalent, with the compared versions named": a passing `equivalence.run` over the seat's `.eqy` (kind `equivalence_setup`) and every approved upstream `rtl_source`, placed beside the setup, before review. A human attestation no longer meets it |

The approved RTL is linked beside the seat's setup under its own name
(`FileInput.beside`), so `read_verilog -sv counter.v` reads the approved file,
and the `sources` check refuses a run that read a seat file of that name. The
stage's outputs stay `equivalence_report`; the setup is the file the gate reads,
as the proof stage's gates read its `.sby`. No other stage, workflow or
requirement changes; the golden plans change in that one line.

The must-fail scorer (M58) needs nothing new: a held-out check with
`"tool": "equivalence.run"` and `"seat_files": {"eqy": ["equivalence_setup"]}`
runs the seat's setup with a non-equivalent refactor in place of the approved
one, and the setup must fail it.

## Tests

`tests/test_nirmaan_equivalence.py`: the catalog and backend; a refusal with
no eqy on PATH; the parser against captured output
(`tests/fixtures/eda/eqy_{pass,fail,error}.log`), including forged lines and
a pass with nothing proved; each refused setup; and real runs over
`tests/fixtures/eqy`: the M21 counter (gold) against a true refactor
(`counter_refactor.v`) passes over copies and writes nothing beside the
setup, and two single-change refactors must fail (`counter_wraps_early.v`
wraps one count early; `counter_reset_ignored.v` ignores reset while `en` is
low). `tests/test_block_verification.py`: the stage's gate, and an
equivalence seat through the eval harness (`run_case`) whose gate passes over
the two approved versions and whose must-fail check fails the early-wrap
refactor.

## Install

CI takes eqy from the pinned OSS CAD Suite build the formal tools already use
(2026-09-28), as a wrapper, and names it in `NIRMAAN_REQUIRE_EDA`, so the
real-run tests fail rather than skip there; the `no-tools` job checks it is
absent. On macOS, Homebrew has no eqy formula: build the tag that matches the
installed Yosys (`v0.69` for Yosys 0.69) from `github.com/YosysHQ/eqy` with
`make install PREFIX=$HOME/.local`, and give its script a Python with
`click`. Its plugins load from beside the script, so nothing is written into
Homebrew's Yosys.

## Not in this milestone

- Partition-level options as gate inputs (a stated `depth` or strategy): the
  seat's setup chooses them, and the must-fail check judges the choice.
- Equivalence in any workflow other than block verification, and the
  `dv/equiv-gray` eval case (W2-E3).
- The same copy-before-run protection for `formal.run`: SymbiYosys already
  copies its `[files]` into its own work directory.

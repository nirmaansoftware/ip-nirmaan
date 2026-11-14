# Outside calibration: public benchmarks through our harness (M76)

Our own cases measure a seat against our own taste. A public benchmark gives an
outside yardstick: how the RTL seat, in our harness, does on problems someone
else wrote and judged. The capability build-out's gap G4 asks for it. This
milestone is the adapter for the first benchmark, RTLLM. It runs no model; the
first live calibration waits for the owner's go-ahead on usage, at the pilot
retrospective.

**Calibration is never level evidence.** A public set may be in a model's
training data, so a pass says little about a skill. Results are labelled
`calibration`, listed in `capability/levels.json` under `calibration` as
"outside calibration", and never count toward Knowledge, Practised or Proven.
They are for one question: how does our harness compare with the bare model on
the same designs.

## The benchmark

RTLLM (https://github.com/hkust-zhiyao/RTLLM, "RTLLM: An Open-Source Benchmark
for Design RTL Generation with Large Language Model") is 50 small designs:
arithmetic, counters and state machines, memories, signal generators and a few
processor parts. Each has a natural-language description, a testbench and a
reference RTL. Licence record: the upstream repository is
hkust-zhiyao/RTLLM, read at commit 51ed553d0ffd32797a1a0a13e051656bf302c81f;
its `LICENSE` file, at the root of that repository, is the MIT licence
(copyright 2024, Nora Lu). The terms are that file's; this repository
commits no text of the benchmark, so it carries no NOTICE entry, and the
adapter requires the upstream `LICENSE` file to stay with the private copy.
This is a reading of the file, not legal advice. VerilogEval has no confirmed
licence for its problem text and CVDP needs a separate decision, so neither is
used here.

Credit: the problems, testbenches and the idea of judging generated RTL by a
testbench are RTLLM's authors'. This repository carries none of their text.

## Fetch it privately

The copy lives outside both repositories, in a private folder, and is never
committed (a public copy is crawled into training data and would spoil the
calibration; a committed copy would also need its notice kept in this
all-rights-reserved repository):

```sh
git clone https://github.com/hkust-zhiyao/RTLLM ~/Nirmaan-internal/benchmarks/rtllm
git -C ~/Nirmaan-internal/benchmarks/rtllm rev-parse HEAD   # record this commit
```

Keep the repository's `LICENSE` file with the copy; the adapter refuses a copy
without one. The adapter takes the commit from the clone's own `HEAD`, or from
a file `UPSTREAM_COMMIT` in the folder for a copy that is not a clone. The
`_chatgpt35` and `_chatgpt4` folders hold model-written answers, not problems;
the adapter never enters them. Point the adapter at the folder with
`--benchmark PATH` or the `NIRMAAN_RTLLM_DIR` variable.

## Run it

```sh
nirmaan eval outside --check --benchmark ~/Nirmaan-internal/benchmarks/rtllm
nirmaan eval outside --runtime claude-code --trials 1 --out ~/Nirmaan-internal/benchmarks/rtllm-results
```

`--check` calls no model. It judges each design's reference RTL with the
benchmark's testbench through the simulator broker and says which designs map.
`--runtime` puts a model in the RTL seat (`rtl-implementation`) for each mapped
design and writes a calibration record. `--only a,b` limits the designs. Keep
`--out` outside the repositories: the record holds the model's answers.

## What the adapter does

For each design, in a temporary folder:

* the description becomes the seat's approved interface specification, byte for
  byte; the benchmark gives no microarchitecture, so the second upstream
  document is a one-line note of ours. The request is one fixed sentence that
  the planner turns into the block-design workflow;
* the reference RTL is staged for the check only (the seat never sees it; the
  top module is renamed to the module the description names, since the copies
  call it `verified_<design>`);
* the benchmark's testbench is the judge. The simulator gate (M53) reads a
  verdict line that carries the run's nonce, which the benchmark's testbenches
  do not print. The staged copy adds one block beside the testbench's own
  "Your Design Passed" message that prints that line, and a `$finish` after it
  when the testbench has none. The testbench's own checks still decide whether
  the message is reached; a testbench that fails prints no verdict, and the run
  fails. Data files the testbench reads (`$readmemh`) are copied beside it and
  named in full;
* the one held-out check runs `simulator.run` over the seat's RTL and the staged
  testbench through the broker, scorer `held-out-run`, so a pass cites a run
  recorded in the sandbox like every other case.

The seat still passes our own gates (lint, its own self-checking simulation,
synthesis with no latches) before its RTL reaches the judge. That is the point:
the comparison is our harness against the bare model, and a design the harness
refuses is a failed trial.

## Mapping

A design maps when its reference passes its own testbench under our simulator
(Icarus). A design that does not map is left out of the run, and the record's
manifest names it (`source`). A design is mapped by what the simulator does
with it, not by a list kept here.

The count of mapped designs is unrecorded: the mapping was tried on a private
copy outside the repository (upstream commit
`51ed553d0ffd32797a1a0a13e051656bf302c81f`), and no run log from it is
committed. CI runs only synthetic designs. A figure becomes a claim only when
`nirmaan eval outside --check` output or a calibration record is committed.

## The record

A calibration record is a normal run record (`docs/LIVE_EVAL_EVIDENCE.md`)
with:

* `purpose: calibration` in the manifest and in every trial, and the record's
  directory name ending `-calibration`;
* the manifest's `source`: the benchmark, its licence, the upstream commit and
  how many designs mapped and which did not;
* every trial's harness fingerprint (M73, `docs/HARNESS.md`), written by the
  same code that writes any trial, so a calibration is tied to the harness it
  ran in.

Either label is enough to keep a trial out of the levels, so editing one back
changes nothing. The levels generator lists every calibration trial with the
reason "outside calibration" and never judges the record as evidence (a replay
of one is no refusal). Eval learning (M42) does not read these trials.

## What changed in code

New: `src/nirmaan/evals/calibration/` (the adapter) and `nirmaan eval outside`. A
`purpose` field on the run manifest and the trial, and `source` on the
manifest, default to evidence and calibration respectively, so every record
written before reads as before. `evals/levels.py` lists calibration trials.
No file in `harness.CODE` changed, so the harness fingerprint is the same as
on main and no trial recorded under it goes stale.

## Next

The live calibration (the designs that map, one or a few trials each) and the
bare-model comparison on the same designs, after the owner's usage go-ahead.
Tests: `tests/test_outside_calibration.py`, on tiny synthetic designs written
for the tests in the benchmark's layout.

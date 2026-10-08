# Structural review: staged plan and progress

A resumable tracker for the structural review requested on 2026-09-29 (the
"build the engineering engine, not an AI wrapper" brief). Each stage ends with
a commit on branch `review/structural`, so a new session resumes by reading
this file, then `git log --oneline main..review/structural`, and picking up at
the first stage not marked DONE.

Rule for the whole review: the brief itself says "do not rewrite working
systems merely to impose a new architecture." The repo already has most of the
brief's concepts under other names. The review maps them first, and builds
only what is genuinely missing.

## Working-tree caveat (found at start)

Local `main` was about 40 commits behind `origin/main` (v1.18.0 locally,
v1.20.0 on GitHub), and its working tree held stale uncommitted leftovers
(`context.md` M23 entry, `docs/DELIVERABLE_EXPORT.md`, and `docs/ROADMAP.md`
emptied to zero bytes), all of which are already merged upstream. They were
stashed, not deleted (`git stash list`: "pre-review leftovers on main"), and
this branch was rebuilt on `origin/main` (acbe52b, v1.20.0). Local `main`
itself was not moved. The venv was stale (it pointed at the old
`~/Documents/veritriage` path) and was rebuilt per the roadmap's resume
checklist. iCloud has evicted many files, including `.git` objects; a git
command that fails with "mmap failed: Operation timed out" should simply be
retried. Stage commits stage only this review's files (never `git add -A`).

## Stages

| # | Stage | Output | Status |
|---|---|---|---|
| 0 | Branch and tracker | this file | DONE |
| 1 | Inventory: read every Nirmaan module and the VeriTriage seams it uses | `docs/architecture/current-state.md` | DONE |
| 2 | Gap analysis against the brief, concept by concept | `docs/architecture/target-state.md` | DONE |
| 3 | Milestone roadmap and the first milestone's design | `docs/architecture/proposed-change.md` | DONE |
| 4 | Implement milestone 1 only, test first | code + tests, full suite green | DONE |
| 5 | Design doc, `context.md` entry, PR | https://github.com/nirmaansoftware/ip-nirmaan/pull/37 | DONE (CI green; awaiting owner review) |

## Notes carried between stages

(Each stage appends what the next stage must not re-derive.)

- **After Stage 1.** The brief's core primitives mostly exist under other
  names (see current-state.md section 7). The real gaps, by leverage: (1) no
  evaluation of model seats against live models, (2) informal tool contracts
  with comma-joined string params, (3) untyped `WorkPacket`, (4) whole-state
  fingerprint per operation, (5) implicit artifact versions, (6) thin
  `Decision`, (7) unclassified failures, (8) design intent only as prose,
  (9) model chosen by name, (10) process-global registries. Do not create a
  parallel `nirmaan/engine/` package: `work/` + `runtime/` already are the
  engine, and the brief itself forbids rewrites for their own sake.
- **After Stage 2.** Milestone order decided in target-state.md section 5:
  M27 seat evaluation, M28 typed contracts, M29 engineering records, M30
  register-map IR, M31 model selection, M32 scalable state, M33 learning
  proposals. The brief's eleven per-topic docs are NOT created; target-state
  section 4 indexes the existing documents instead (a deliberate choice,
  reported to the owner).
- **After Stage 3.** M27 design fixed in proposed-change.md. Baseline before
  any code: 1115 passed, 2 skipped (all EDA tools present locally except
  OpenSTA and OpenROAD). Stage 4 order: (a) failing tests
  `tests/test_nirmaan_evals.py`, commit; (b) `models/evaluation.py`; (c)
  `evals/cases.py` + the four case files; (d) `evals/scorers.py`; (e)
  `evals/runner.py`; (f) CLI; (g) full suite. Commit after each of (a), (c),
  (e), (g) so a resume can see progress in `git log`.
- **During Stage 4.** Failing tests committed (cd379ce), implementation
  committed (90d235f): `src/nirmaan/models/evaluation.py`,
  `src/nirmaan/evals/` (cases, scorers, runner), `nirmaan eval list/run`,
  four cases in `evals/rtl/`. 15 new tests pass. Found and fixed on the way:
  rich swallowed `[seat]` as markup in CLI output (now escaped, and a test
  asserts it). The `new-ip` interface-spec stage fans out into variants, so
  the gate test uses `microarchitecture` as its seat. Remaining for Stage 5:
  full suite result, `evals/README.md`, `docs/SEAT_EVALUATION.md`,
  `context.md` entry, ROADMAP bullet, PR.
- **After Stage 4.** Full suite: 1130 passed, 2 skipped (OpenSTA, OpenROAD).
  Docs written: `docs/SEAT_EVALUATION.md`, `evals/README.md`, `context.md`
  M27 entry, ROADMAP row and milestone list. iCloud evicted even freshly
  written docs mid-run; `brctl download <file>` forces them back when
  `cat` times out.
- **After Stage 5.** PR #37 open, CI green. The iCloud folder became
  unusable (git itself timed out), so work continues in a clone outside
  iCloud and every commit is pushed; GitHub is the durable record. Next:
  M28 (typed tool contracts) on branch `m28/typed-contracts`, stacked on
  this branch until #37 merges. The first live evaluation run waits for the
  owner (it costs API credits).

## M28: typed tool contracts (branch `m28/typed-contracts`, stacked on this one)

| # | Step | Status |
|---|---|---|
| a | Design: `docs/TOOL_CONTRACTS.md` | DONE |
| b | Failing tests `tests/test_nirmaan_contracts.py` | DONE |
| c | Vocabulary (`ParamKind`, `ParamSpec`, `ToolSpec.params`, `list_values`, `ToolRun.values`) and catalog contracts | DONE |
| d | Broker validation, runtime input filtering and list parameters, split sites replaced, `nirmaan org tool` | DONE |
| e | Full suite (1143 passed, 2 skipped), `context.md`, ROADMAP, PR | DONE |

Parameter inventory (from reading every integration, both quote styles):
eda runner `backend workdir timeout max_*`; lint/sim/test/synth/dft
`sources top`; formal `sby sources`; synth-liberty adds `liberty pdk_root`;
sta `netlist sdc spef top liberty pdk_root`; pnr `netlist sdc top liberty
tech_lef lef pdk_root site hor_layers ver_layers utilization aspect_ratio
core_space stop_after`; fw.build `sources`; fw.test `sources rtl top`;
veritriage.investigate `paths workspace`; explain_log `path`;
knowledge.search `query`; project.read `task`; artifact.read `artifact`.
Missing required inputs stay recorded failed runs (M21/M25 decision; a
physical test asserts it).

**After M28 (PR #41, stacked on #37).** Parallel sessions opened #38
(OpenROAD in CI), #39 (repair after review), and #40 (RISC-V firmware), all
also numbered "M27". Numbers collide with this review's M27/M28; the owner or
coordinator decides numbering and merge order. Overlaps: #39 shares
`runtime/base.py`, `runtime/__init__.py`, `models/org.py`, `models/work.py`,
`work/policy.py`, `cli.py`; #38 shares `integrations/physical.py` and its
test; #40 shares `company/tools.py` and `integrations/firmware.py`. Whichever
of #38/#40 merges after #41 must declare any new tool parameters it reads in
`company/tools.py`; `test_every_parameter_an_integration_reads_is_declared`
will say which. Do not start M29 until the owner has settled the order.

**2026-09-30.** #39 (M27 repair after review) merged into `main`. `main`
was merged into #37 (context.md conflict: both M27 entries kept, this
review's retitled "Milestone 27 (seat evaluation)"; 1141 passed, 2 skipped)
and #37 into #41 (1154 passed, 2 skipped). The disk was full (273 MB free),
which failed a firmware test with ENOSPC; stale test temp directories older
than an hour were removed (about 5 GB freed). The owner should look at the
disk: 182 GB of 228 GB is used, and a full disk also explains iCloud evicting
files.

Follow-up for whichever of #38/#40 merges after #41 (#41's tests will fail
until done): in `company/tools.py`, give #40's new tools contracts,
`fw.cross_build` (`sources` paths required, `*RUNNER`) and `fw.soc_test`
(`sources` and `rtl` paths required, `TOP`, `*RUNNER`); add `tie_high` and
`tie_low` (text) to `pnr.run` for #38. #40's `firmware_riscv.py` also splits
`rtl` itself; `list_values` is the helper to use.

**2026-10-07.** Everything else merged (#38, #40, #42, #43, v1.21.0). `main`
merged into #37 (1218 passed, 3 skipped; this review's context entry moved
after the DFT part, outside the v1.21.0 set) and #37 into #41 (1231 passed,
3 skipped). #41 now gives contracts to the five tools the M27 parts added and
the new parameters (`chains`, `max_chain_length`, ATPG's `patterns`,
`fault_sample`, `seed`, `min_<metric>`, `synth.run`'s tie cells, `sta.run`'s
LEFs). The static scan no longer reads `p["x"]`, which in `dft_atpg.py` is a
pattern record, not parameters.

**2026-10-07, merges.** The owner chose "merge both, then M29": #37 merged
(c36b53a) and #41 merged (d9e2bf0) after green CI.

## M29: engineering records (branch `m29/engineering-records`, from main d9e2bf0)

| # | Step | Status |
|---|---|---|
| a | Design: `docs/ENGINEERING_RECORDS.md` (views, not new stored fields) | DONE |
| b | Failing tests `tests/test_nirmaan_records.py` | DONE |
| c | `src/nirmaan/records.py` (decision and failure views, summary) | DONE |
| d | CLI `decisions`/`failures`, export sections, MCP read tools | DONE |
| e | Full suite (1241 passed, 3 skipped), `context.md`, ROADMAP, PR | DONE |

Inspection findings that shaped it: no product code calls
`record_decision`; decisions are DECISION tasks (outcomes, outcome,
artifacts, evidence, audit, branch cancellations by `_take_branch`). M27's
review repair already moves superseded artifacts into an `Attempt`.

## M31: model selection and model-call accounting (branch `m31/model-selection`)

The owner asked (2026-10-08) to resolve everything and complete the remaining
review milestones, merging each on green CI. Order: #52 (M30), then M31, M32
(scalable state), M33 (learning proposals). Out of scope without the owner: a
live-model evaluation (API credits), version bumps (coordinator), #45 (another
session's PR).

| # | Step | Status |
|---|---|---|
| a | Design: `docs/MODEL_SELECTION.md` (prices from the claude-api skill: Opus 5.5 $4/$20 per MTok, cache read $0.20) | DONE |
| b | Failing tests `tests/test_nirmaan_model_selection.py` | TODO |
| c | Accounting: VeriTriage `GenerationResponse` tokens, bridge, `Completion`, `ModelCall`, `record_model_call`, `nirmaan costs`, eval totals | TODO |
| d | Selection: `ModelProfile` data, derived needs, `select_model`, `auto` runtime | TODO |
| e | Full suite, docs, PR, merge | TODO |

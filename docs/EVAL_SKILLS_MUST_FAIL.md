# Eval cases name skills; must-fail scorer (M58)

The capability build-out council record of 2026-10-18 (section 9) decided how a
skill earns an evidence level. Practised comes only from committed, tool-judged
result records; a case lists the skills it judges, and only those get credit;
replays and human attestations never count; and before a verification or RTL
skill can be Practised, its case set carries negative controls: mutant RTL must
fail the seat's testbench or assertions, clean RTL must pass, and covers must
be reached. This milestone adds those parts to the evaluation harness. It
computes no level (that is the levels generator, a later milestone) and
commits no result record.

## 1. A case names the skills it judges

`EvalCase.skills` is a tuple of skill IDs. `validate_case` refuses a skill that
is not in the catalog (`org.skills`) and a skill named twice, so `nirmaan eval
run` will not run such a case. The field is empty by default; the six shipped
cases name theirs in a separate commit of the same pull request (section 5).

Why a list on the case and not the stage: one stage pass would otherwise credit
every skill the stage's role holds (the RTL seat's role holds `git`, `linux`,
and a dozen more). The case author names what the held-out judges actually
test, and the reviewer of the case can check that claim.

## 2. Skill digests and head SHA in the run record

A level is keyed by model ID plus skill digest, and is stale when either
changes. The run record now carries both:

- each trial's `skills`: skill ID -> `sha256:` over the skill's catalog entry
  (the skill card, as `Skill.model_dump`) and, when it exists, the knowledge
  document `knowledge/<division>/<skill_id>.md` (its path and bytes). No
  knowledge document exists yet; the digest includes one as soon as it does, so
  a record made before a document was written is stale after it;
- the manifest's `head_sha`: the commit the run was made on. `nirmaan eval run`
  reads it with `git rev-parse HEAD` in `--repo`; outside a repository it is
  `null`. The evaluation package itself never runs a command, so the CLI passes
  it in (`record_run(..., head_sha=...)`).

The full record format (model ID, skill digest, case ID, trials, judge tool,
head SHA, outcome) is documented in `evals/README.md`, "Result records".

## 3. The must-fail scorer

`must-fail` is a registered scorer, like `held-out-run`, that needs a tool. A
check gives:

- `seat_files` and `case_files` as before: the inputs of the clean run (for
  example, the seat's testbench and the case's clean RTL);
- `mutants`: case file -> files that each stand in for it, one run each;
- `seat_entries`: parameter -> artifact kinds whose entry fills it. A seat
  declares its testbench's top module on the file it submits, and that value is
  not kept on the artifact; the scorer takes it from the seat's own latest
  passing run over that file, which is the run its before-review gate made;
- `cover_tool`, optional: a tool that must also pass over the clean inputs.

The scorer passes only when, in order:

1. the clean run passes (otherwise `failed`: "the clean inputs do not pass");
2. the `cover_tool` run passes over the same clean inputs (otherwise `failed`:
   "covers not reached");
3. every mutant run fails, on a run that executed and wrote its log. A mutant
   that passes is reported by name as surviving. A refusal (a tool outcome with
   no log: a check problem, a missing file) is `not_run`, never a mutant caught.

A check with no mutants is `not_run`. A tool the broker refuses is `not_run`.

**Staging.** Every run reads a staged copy of its inputs in a fresh temporary
directory, each file under its own name, with the mutant written under the name
of the file it replaces. A simulator takes paths and does not care; a proof's
job file names its files relative to itself, so staging is what lets the same
`.sby` read the mutant. Two inputs with one file name are `not_run`.

**What it judges.** With the seat's testbench as a seat file and the reference
RTL as the case file, it judges the seat's testbench: a testbench that cannot
tell a mutant from the clean design proves nothing about either. With a case's
proof setup, it judges the assertions, and `formal.cover` makes sure the clean
proof is not vacuous.

**Formal at each parameter point.** The tests show why the council asked for
proofs at each parameter point: the `sync_fifo_pow2_wrap.v` mutant (pointers
that wrap only at a power of two) passes the DEPTH 8 proof `sync_fifo.sby` and
fails the DEPTH 5 proof `sync_fifo_depth5.sby`. The reference testbench, which
runs DEPTH 8 and DEPTH 5 lanes, catches both mutants.

### The runner keeps a negative control honest

`Score.failed_runs` lists the runs a control needed to fail. The runner already
turns a claimed pass into a failure unless every cited run is a recorded,
passing run; it now also requires every run in `failed_runs` to be a recorded,
failed run. A scorer cannot claim a mutant failed without a failed run in the
sandbox. The run record keeps those runs among the trial's `judge_runs`, with
`succeeded: false`.

### Fixtures

Two mutants in the style of the `_tb_fail` controls (a header comment says what
is wrong; everything else is identical), in
`tests/fixtures/rtl/sync_fifo/mutants/`:

| File | The one change |
|---|---|
| `sync_fifo_overflow.v` | `wr_acc = wr_en`: a write while full is accepted and count passes DEPTH |
| `sync_fifo_pow2_wrap.v` | `next = ptr + 1`: the pointers wrap only at a power of two |

No shipped case uses `must-fail` yet. A case and the content it grades never
change in one pull request, so negative controls join the shipped cases in the
pull request that adds the first skill's cases (P1-14 in the build-out plan).

## 4. The evidence loader

`load_evidence(path)` reads a run record (as `load_record` does) and raises
`EvalError` when it may not count as evidence about a model:

- **a replay**: the manifest says `replay` or its runtime is `replay`, or any
  trial's result does. A replay proves a case and its judges, never a model;
- **an attestation**: any trial whose `result.attestations` is not empty.
  `EvalResult.attestations` lists the human attestations recorded on the seat's
  task in the sandbox. A `dv_ran` verification requirement accepts a person's
  attestation in place of a tool run; a trial that leaned on one is not
  tool-judged.

`load_record` and `load_records` are unchanged: `nirmaan eval history` and
`nirmaan eval rejudge` still read replays, which is how cases are proven.

## 5. The six shipped cases

In a separate commit (no graded code changes in this pull request):

| Case | `skills` |
|---|---|
| `rtl/sync-fifo`, `rtl/rr-arbiter` | `rtl_design` |
| `rtl/axi4-lite-regs` | `rtl_design`, `axi` (the reference testbench drives AXI4-Lite transfers) |
| `rtl/apb-regs` | `rtl_design`, `apb` (the reference testbench drives APB transfers) |
| `spec/axi4-lite-interface` | `interface_specification` |
| `firmware/axi4-lite-driver` | `device_drivers` |

Each skill is one the seat's role holds and one the held-out judge exercises.
Adding the field changes every case digest; no run record is committed, so no
recorded trial becomes incomparable.

## Laws and tests

- The evaluation package still names no stage, tool, artifact kind, or role
  (`test_the_runner_names_no_stage_tool_kind_or_role` reads the new code too);
  the scorer takes every tool and kind from the check.
- `tests/test_nirmaan_eval_must_fail.py`: skills are validated against the
  catalog; a skill digest changes with its knowledge document and not with
  another skill's; a mutant must replace a case file and is part of the case
  digest; the reference testbench and the DEPTH 5 proof catch both mutants with
  covers reached while the DEPTH 8 proof misses one; a weak seat testbench that
  passes its own gates lets a mutant survive; failing clean inputs fail the
  control; no mutant is `not_run`; a claimed failed run that passed or does not
  exist is overturned; a record names the head SHA and each skill digest, and
  the CLI writes the head SHA; `load_evidence` refuses a replay (at the manifest
  and at a trial) and an attestation, and accepts a live, tool-judged record.
- Crown jewel: the must-fail checks in the tests are case data run through the
  unchanged runner; a new negative control needs a case and fixtures, no code.

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

**Staging.** Every run reads a staged copy of its inputs in its own folder
inside the evaluation's sandbox (`judge/check-<n>/must-fail-<random>/<run>`, a
fresh folder each time, so a second evaluation into the same sandbox never
meets the first one's files), each file under its own name, with the mutant
written under the name of the file it replaces. The staged copies stay with the
sandbox's record, so every run's parameters name files that still exist. A
caller that gives the scorer no sandbox folder gets a temporary one, removed
when the check ends. A simulator takes paths and does not care; a proof's job
file names its files relative to itself, so staging is what lets the same
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

A case and the content it grades never change in one pull request, so negative
controls joined the shipped cases in the pull request that added the first
skill's cases (P1-14 in the build-out plan): `rtl/rr-arbiter` now also judges
`arbitration`, with three mutants in `tests/fixtures/rtl/rr_arbiter/mutants/`:

| File | The one change |
|---|---|
| `rr_arbiter_winner_keeps_priority.v` | the pointer moves to the winner, not one past it: the winner keeps top priority |
| `rr_arbiter_no_wrap.v` | the search stops at `N-1`: a request below the pointer is never granted |
| `rr_arbiter_pow2_wrap.v` | the search index and the pointer wrap only at a power of two |

Its seat-testbench control fails all three. The N 5 proof fails all three; the
N 4 proof fails the first two and cannot see the third, so the case runs both
proofs, each with its covers.

The pilot's first eval pull request (P3-E1) gave the other three shipped RTL
cases the same controls. `rtl/sync-fifo` now runs the two FIFO mutants above:
its seat-testbench control and the DEPTH 5 proof fail both, and the DEPTH 8
proof fails the overflow mutant (the one wrong at DEPTH 8), each proof with its
covers. It also judges `buffering_flow_control` (full, empty and count at a
depth that is not a power of two). The register blocks got their own mutants:

| File | The one change |
|---|---|
| `apb_regs/mutants/apb_regs_pstrb_ignored.v` | any `pstrb` bit set writes every byte |
| `apb_regs/mutants/apb_regs_setup_write.v` | a write also takes effect in the setup phase |
| `apb_regs/mutants/apb_regs_no_pslverr.v` | `pslverr` is never raised |
| `apb_regs/mutants/apb_regs_decode_alias.v` | the decode ignores the bits above 0xC, so 0x10 and up alias the registers |
| `axi4_lite/mutants/axi4_lite_regs_wstrb_ignored.v` | any `wstrb` bit set writes every byte |
| `axi4_lite/mutants/axi4_lite_regs_okay_unmapped.v` | an unmapped write is answered OKAY, not SLVERR |
| `axi4_lite/mutants/axi4_lite_regs_b_before_w.v` | the write and B happen once AW is accepted, before W |

Paths are under `tests/fixtures/rtl/`. Each case runs a seat-testbench control
and a proof control, and every mutant fails at least one:

| Case | Seat testbench fails | Proof fails | Why one judge leaves a mutant out |
|---|---|---|---|
| `rtl/sync-fifo` | both | DEPTH 5: both; DEPTH 8: overflow | the power-of-two wrap is right at DEPTH 8 |
| `rtl/apb-regs` | pstrb, no pslverr, alias | all four | a manager that follows APB holds address and data into the access phase, so a setup-phase write leaves the same registers and only the proof's per-cycle register property sees it |
| `rtl/axi4-lite-regs` | all three | OKAY on unmapped, B before W | the proof checks handshakes and response codes, not register data |

A mutant fails a testbench check or an assertion, never a build error; the
tests check both, and that the judge a control leaves out really passes the
mutant it leaves out.

The pilot's second eval pull request (P3-E2) added two cases, each with a
seat-testbench control and proofs at two parameter points:

- `rtl/axil-timer` judges `rtl_design`, `axi` and `fsm_design`. Its reference
  RTL is the M29 firmware timer (`axil_timer/axil_timer.v`), extended with a
  periodic mode, a `CTRL` write that needs `wstrb[0]`, and an expiry that wins
  over a clear on the same edge; the firmware's driver writes `MODE` 0, so its
  tests are unchanged. The reference testbench runs lanes at `ADDR_WIDTH` 4
  and 8 and times every count to the edge.
- `rtl/apb-gpio` judges `rtl_design`, `apb` and `control_logic_design`: a new
  block (`apb_gpio/apb_gpio.v`) with output data and enable, a sampled input,
  edge and level detection, an enable mask and write-1-to-clear status. The
  reference testbench runs lanes at `N` 8 and 32.

| File | The one change |
|---|---|
| `axil_timer/mutants/axil_timer_oneshot_runs_on.v` | `MODE` is ignored when a count ends: a one-shot count reloads and runs on |
| `axil_timer/mutants/axil_timer_reload_off_by_one.v` | a periodic count reloads `LOAD + 1`: every period after the first is one cycle long |
| `axil_timer/mutants/axil_timer_stop_ignored.v` | a `CTRL` write of `EN` 0 does not stop a running count |
| `axil_timer/mutants/axil_timer_decode_alias.v` | the decode ignores the bits above 0xC, so at `ADDR_WIDTH` 8 offsets 0x10 and up alias the registers |
| `apb_gpio/mutants/apb_gpio_w1c_clears_all.v` | a write to `INTR_STATUS` clears every bit, not only those written 1 |
| `apb_gpio/mutants/apb_gpio_edge_on_level.v` | the rising-edge detector looks at the level, so a pin held high sets its bit again after every clear |
| `apb_gpio/mutants/apb_gpio_level_as_edge.v` | high-level detection fires only on the rising edge, so a clear sticks while the level holds |
| `apb_gpio/mutants/apb_gpio_mask_ignored.v` | `irq` ignores `INTR_ENABLE` |

| Case | Seat testbench fails | Proof fails | Why one judge leaves a mutant out |
|---|---|---|---|
| `rtl/axil-timer` | all four | `ADDR_WIDTH` 8: all four; `ADDR_WIDTH` 4: the first three | the aliasing decode is right at `ADDR_WIDTH` 4 |
| `rtl/apb-gpio` | all four | `N` 8 and `N` 32: all four | none |

Both proofs model the specification register by register (decode, byte
merge, count or detection written independently of the design's) and assert
that the design matches it after every edge, so each mutant fails an
assertion. The seat's testbench must catch every mutant: each is visible at
the ports, the aliasing decode at `ADDR_WIDTH` 8, which the case's
constraints and its specification require. Each reference testbench also
checks a race no mutant here covers: a clear on the very edge a new expiry or
detection lands must leave the status set.

The pilot's third eval pull request (P3-E3) added `rtl/skid-buffer`, which
judges `rtl_design`, `pipeline_design` and `buffering_flow_control`: a new
register slice (`skid_buffer/skid_buffer.v`) on a valid/ready stream, with
every output from a flop, full throughput, and a skid register that takes the
one beat accepted while the output stalls. Its request plans through M66's
`register_slice` feature. The reference testbench runs lanes at `WIDTH` 8 and
1 against its own queue model, and the proofs run at the same two widths.

| File | The one change |
|---|---|
| `skid_buffer/mutants/skid_buffer_stall_drops_beat.v` | a beat accepted while the output stalls is not kept in the skid register, so it is lost and `s_ready` stays high |
| `skid_buffer/mutants/skid_buffer_ready_from_downstream.v` | `s_ready` is computed from `m_ready`: no beat is lost, but ready is not registered and drops while one beat is held |
| `skid_buffer/mutants/skid_buffer_skid_not_emptied.v` | the skid register is not emptied when ready rises and its beat moves out, so that beat is sent again |
| `skid_buffer/mutants/skid_buffer_data_not_held.v` | a beat accepted while the output stalls also loads the output register, so `m_data` changes under a stall |

| Case | Seat testbench fails | Proof fails | Why one judge leaves a mutant out |
|---|---|---|---|
| `rtl/skid-buffer` | all four | `WIDTH` 8 and `WIDTH` 1: all four | none |

The proofs keep their own queue of up to two beats, moved only by the
handshakes at the ports, and assert that `m_valid`, `s_ready` and `m_data`
match it after every edge, so each mutant fails an assertion. The
combinational ready loses no beat, so a testbench that only compares the
stream in and out misses it; the reference testbench checks `s_ready` against
its model every cycle and flips `m_ready` and `s_valid` inside a cycle to
check that `s_ready` does not move.

### Verification seats (wave 2)

Wave 2's first eval pull request (W2-E1) judges verification seats of M68's
`block-verification` workflow (`docs/BLOCK_VERIFICATION.md`), where the RTL is
fixed and the seat writes the testbench or the plan. Both cases verify one
approved block, an interrupt controller (`tests/fixtures/dv/irq_ctrl/`): `N`
sources (2 to 32) with an enable mask, a high-level or rising-edge mode per
source, a write-1-to-clear pending register, and a claim register that names
the lowest-numbered pending, enabled source and acknowledges one source on a
write. The case fixes `interface-spec` (`interface_spec.md`, 14 tagged
requirements) and `design-under-test` (`irq_ctrl.v`) from its own files;
`microarchitecture.md` documents the RTL and is given to no seat.

- `dv/directed-irq-ctrl` judges the testbench seat on `directed_testing` and
  `systemverilog` (its request asks for a SystemVerilog testbench, which
  plans the `systemverilog` refinement). Its one control is the seat's own
  testbench with `simulator.run`: it must pass on the approved RTL and fail
  each RTL mutant below. The reference testbench (`irq_ctrl_tb.sv`) runs
  lanes at `N` 8 and 5 and fails every mutant on a check, not a build.
- `dv/plan-irq-ctrl` judges the dv-plan seat on `verification_planning`. Its
  one control runs `vplan.check` over the seat's plan: it must pass against
  the approved specification and fail against each specification mutant
  below. A plan that leaves out a requirement already fails the seat's own
  gate and never reaches review (tested). This control is weaker than a
  testbench's: it proves the plan is tied to the approved requirement set
  and wording, not that its items would catch a bug.

| File | The one change | Judge that fails it |
|---|---|---|
| `mutants/irq_ctrl_priority_inverted.v` | `irq_id` names the highest-numbered active source | seat testbench (`simulator.run`) |
| `mutants/irq_ctrl_ack_ignored.v` | a `CLAIM` write never clears a pending bit | seat testbench |
| `mutants/irq_ctrl_level_mask_ignored.v` | `ENABLE` masks rising-edge sources only, so a disabled high-level source raises `irq` | seat testbench |
| `mutants/irq_ctrl_clear_beats_set.v` | a clear wins over a detection at the same edge | seat testbench |
| `mutants/irq_ctrl_w1c_clears_all.v` | a `PENDING` write clears every bit | seat testbench |
| `mutants/interface_spec_added_req.md` | one requirement added (`IRQ-RECLAIM`) | seat plan (`vplan.check`: not in the plan) |
| `mutants/interface_spec_priority_changed.md` | `IRQ-PRIORITY` changed to highest number first | seat plan (`vplan.check`: does not quote it) |

Paths are under `tests/fixtures/dv/irq_ctrl/`. Every mutant is visible at
`N` 8, the default, through the ports and registers the specification names.
A testbench that never raises a source passes its own gate and the approved
RTL, and the first mutant survives it (tested in
`tests/test_dv_irq_ctrl_evals.py`).

Wave 2's second eval pull request (W2-E2) judges the proof seat,
`assertions-formal`, on two more approved blocks. The seat writes a property
file (`assertions`) and a single-task `.sby` (`formal_spec`) that names the
approved RTL by its file name (`FileInput.beside`); its gates ask for at
least one property proven and every cover reached. Each case's one control
runs `formal.run` over the seat's setup, with `formal.cover` as its
`cover_tool`: the proof must pass the approved RTL with every cover reached
and fail each RTL mutant below on a failed assertion.

- `dv/formal-credit-counter` judges `formal_verification`, `sva` and
  `assertion_coverage`. Its block (`tests/fixtures/dv/credit_counter/`) is a
  credit counter for credit-based flow control: `MAX` credits (1 to 255) at
  reset, a take spends one, a give returns one, both at once change nothing,
  a take at zero or a give at `MAX` is refused and sets a sticky `err`, with
  `avail` and `full` outputs (11 tagged requirements). The reference proof
  (`credit_counter_check.sv`, `credit_counter_check.sby`) checks the RTL
  against a model of the specification at `MAX` 4 and 5 in one setup, with
  immediate assertions and `$past` (the SVA subset open Yosys reads), and
  covers both refusals and a take with a give at zero and at `MAX`.
- `dv/prove-deep-counter` judges `model_checking`. Its request asks for an
  unbounded proof, which plans the `unbounded_proof` refinement. Its block
  (`tests/fixtures/dv/deep_counter/`) is a modulo counter, 0 to `LIMIT`
  (default 99), with enable, synchronous clear and a carry out on the
  wrapping cycle (7 tagged requirements). Every mutant goes wrong 64 or more
  cycles after reset. The reference proof ties `count` to a model, which is
  inductive, and runs in prove mode with a 20-cycle unrolling: the basecase
  passes on each mutant and the induction step fails on an assertion (sby
  reports UNKNOWN with the failed assertion, which the control counts as a
  mutant caught, since the run executed and wrote its log). The same
  properties checked in `bmc` mode at that depth pass every mutant, and the
  proof gate refuses that setup before review (no property proven).

| File | The one change | Judge that fails it |
|---|---|---|
| `credit_counter/mutants/credit_counter_both_takes.v` | a take and a give at the same edge spend a credit | seat proof (`formal.run`), `MAX` 4 and 5 |
| `credit_counter/mutants/credit_counter_underflow_wraps.v` | a take at zero is not refused: credits wrap to 255 | seat proof, `MAX` 4 and 5 |
| `credit_counter/mutants/credit_counter_err_not_sticky.v` | `err` clears at the edge after a refusal | seat proof, `MAX` 4 and 5 |
| `credit_counter/mutants/credit_counter_full_bit_test.v` | the `MAX` compare tests the bits of `MAX`: right only for a power of two | seat proof at `MAX` 5 only |
| `deep_counter/mutants/deep_counter_carry_lost.v` | no carry into the top bit: 63 goes to 0 (cycle 64) | seat proof, induction step |
| `deep_counter/mutants/deep_counter_last_low_bits.v` | the compare with `LIMIT` ignores bit 0: wraps at 98 (cycle 99) | seat proof, induction step |
| `deep_counter/mutants/deep_counter_wrap_to_one.v` | after `LIMIT` the count restarts at 1 (cycle 100) | seat proof, induction step |
| `deep_counter/mutants/deep_counter_saturates.v` | the count stops at `LIMIT` (cycle 100) | seat proof, induction step |

Paths are under `tests/fixtures/dv/`. The tests in
`tests/test_dv_formal_evals.py` show each control catches a weak property
set: a proof at `MAX` 4 alone passes its gates and the approved RTL, and the
bit-test mutant survives it; a prove-mode proof that only bounds the count
and defines the carry, true and inductive, lets the lost carry survive.

Wave 2's third eval pull request (W2-E3) adds a random-stimulus testbench case
and an equivalence case, each on an approved block of its own:

- `dv/random-crc` judges the testbench seat on `directed_testing` and
  `constrained_random`. Its request asks for constrained-random stimulus, which
  plans the `random_stimulus` refinement, and so a different owner (the
  testbench testing senior) from the directed case. Its block
  (`tests/fixtures/dv/crc8/`) is a byte-at-a-time CRC-8 engine: polynomial
  0x07, start value 0xFF, bytes taken bit 7 first with no reflection, check
  value inverted, `init` reloads and wins over a byte, `valid` low holds (8
  tagged requirements). Its one control is the seat's testbench with
  `simulator.run`. The reference testbench (`crc8_block_tb.sv`) drives random
  bytes, `init` and `valid` under stated constraints from a fixed-seed
  generator, compares `crc` with a model of the specification after every
  edge, and fails itself when the run is too short or never reaches `init`
  with `valid`, idle cycles or a mid-frame reset. Each of the five mutants
  fails a check, never a build.
- `dv/equiv-gray` judges the `equivalence` seat (M69) on
  `equivalence_checking`. Its block (`tests/fixtures/dv/gray_counter/`) is a
  4-bit Gray-code counter with enable, synchronous reset and a `wrap` flag at
  the last code (4 tagged requirements): the gold version decodes to binary,
  adds one and encodes again; the approved refactor steps the code by the
  parity rule, under the same state register. The seat writes the `.eqy`
  setup (`equivalence_setup`). The control runs `equivalence.run` over it with
  each mutant below in place of the refactor: it must prove the approved pair
  equivalent (the equivalence gate before review) and fail each mutant on an
  unproved partition.

| File | The one change | Judge that fails it |
|---|---|---|
| `crc8/mutants/crc8_block_poly_tap.v` | the polynomial is 0x03, without its x^2 tap | seat testbench (`simulator.run`) |
| `crc8/mutants/crc8_block_reflected_input.v` | each byte is taken bit 0 first | seat testbench |
| `crc8/mutants/crc8_block_no_final_xor.v` | `crc` is the running value, not inverted | seat testbench |
| `crc8/mutants/crc8_block_init_loses.v` | a byte offered with `init` wins over the reload | seat testbench, only if `init` meets `valid` |
| `crc8/mutants/crc8_block_hold_ignored.v` | `valid` is ignored: a byte is taken at every edge | seat testbench, only if `valid` goes low |
| `gray_counter/mutants/gray_counter_refactor_flip_wrong_bit.v` | after an odd code ending in 1 the wrong bit flips | seat setup (`equivalence.run`) |
| `gray_counter/mutants/gray_counter_refactor_wrap_off_by_one.v` | `wrap` is high at count 14, not 15 | seat setup |
| `gray_counter/mutants/gray_counter_refactor_reset_to_one.v` | reset loads 0001, not 0000 | seat setup |

Paths are under `tests/fixtures/dv/`. The tests in
`tests/test_dv_crc_gray_evals.py` show the control catches a weak testbench: a
testbench that sends one fixed message with `valid` held high passes its own
gate and the approved RTL and lets `init_loses` survive; a random testbench
whose constraint keeps `init` away from `valid` lets the same mutant survive;
and the reference over only 12 random cycles, with its own thinness check
removed, lets a mutant survive. The scorer stops at the first survivor.

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

Six cases shipped when this milestone landed; P3-E2 added `rtl/axil-timer`
and `rtl/apb-gpio`, and P3-E3 `rtl/skid-buffer`, with their skills (section 3). The six were named in #122,
in a separate commit from the harness. That commit added only
the `skills` field to each case and the test that checks them; nothing the
cases grade (their RTL, testbenches, proofs and reference documents) changed:

| Case | `skills` |
|---|---|
| `rtl/sync-fifo`, `rtl/rr-arbiter` | `rtl_design` (later also `buffering_flow_control` and `arbitration`, section 3) |
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

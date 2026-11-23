# Wave 2 re-measure batch: the committed plan

This file is the committed plan of the wave 2 re-measure batch. It is the plan that gate W2C1 asks for in
`council/records/2026-11-23-wave-2-close-meeting-1.md` (decision 4 and the gates table), and it holds what gates
W2C2 to W2C9 and W2C11 ask a plan to state. Where this file quotes or restates the ruling, the record is the source;
where the two differ, the record rules.

No trial of this batch has run. Nothing here is a result, and nothing here may be cited as one. This pull request
changes no code, no case, no record and no level: no file in `harness.CODE`, no tool definition, no CLI pin, no card
and no knowledge document is touched, so every fingerprint and digest below is the one `main` already has. It was
written on 2026-11-23, before trial 1.

## 1. What is fixed, and how it may change

Fixed here, before slot 1:

- Thirteen cases (section 2). On every case, eight trials with knowledge documents (arm E) and one without (arm N):
  104 and 13, 117 slots.
- The slot order of section 3, listed whole in section 12.
- The default harness, the seat model and the CLI of section 6, one trial per dispatch.
- Every group the batch's trials join, with the count and the passes W2-L1 recorded for it (section 4).
- Where every trial runs, and which account runs each tool (section 5).
- The values a dispatch is made on (section 6) and the freeze (section 7).
- The stop rules (section 8) and the one read (section 9).

Before slot 1, any of these changes only by a plan amendment pull request. From slot 1 on, a count, a case, an arm,
the order, a stop rule or the read changes only by a council ruling that records what was known when it was made. No
slot is added, dropped, moved or run again because of a result.

## 2. Cases, counts and arms

The cases are those of decision 4, in its three kinds: cases that start a new group for a skill whose card or
document changed since W2-L1 was read, or that had no trial; cases that add trials on a new case to a group W2-L1
read; and one case W2-L1 read that runs again.

| Case | Seat | Skills it names | New group for | Joins a group W2-L1 read | Arm E | Arm N |
|---|---|---|---|---|---|---|
| dv/equiv-gray | equivalence | equivalence_checking | equivalence_checking |  | 8 | 1 |
| dv/equiv-updown | equivalence | equivalence_checking | equivalence_checking |  | 8 | 1 |
| dv/plan-irq-ctrl | dv-plan | verification_planning | verification_planning |  | 8 | 1 |
| dv/plan-tick-timer | dv-plan | verification_planning | verification_planning |  | 8 | 1 |
| debug/triage-three-bugs | triage | failure_triage | failure_triage |  | 8 | 1 |
| debug/triage-pwm-gen | triage | failure_triage | failure_triage |  | 8 | 1 |
| debug/root-cause-uart-tx | root-cause | root_cause_analysis | root_cause_analysis |  | 8 | 1 |
| debug/root-cause-debounce | root-cause | root_cause_analysis | root_cause_analysis |  | 8 | 1 |
| rtl/apb-gpio | rtl-implementation | rtl_design, apb, control_logic_design | control_logic_design | apb, rtl_design | 8 | 1 |
| dv/fcov-lifo4 | coverage-closure | functional_coverage | functional_coverage (first group) |  | 8 | 1 |
| dv/formal-rr-arbiter | assertions-formal | formal_verification, sva, assertion_coverage |  | formal_verification, sva, assertion_coverage | 8 | 1 |
| dv/coverage-tick-timer | coverage | code_coverage |  | code_coverage | 8 | 1 |
| dv/cocotb-crc | testbench | directed_testing, python_verification | python_verification (first group) | directed_testing | 8 | 1 |

13 cases, 104 trials with documents and 13 without: 117 slots.

- **Arm E**: knowledge documents on. These trials are the evidence of the read.
- **Arm N**: `--without-knowledge` (the workflow's `knowledge=off`), labelled knowledge off. It counts toward no
  level and is reported beside the read only.
- **Counts.** As W2-L1 (`evals/plans/2026-11-18-w2-l1.md`, "Cases and counts"): eight trials with documents per case,
  the smallest count at which one failed trial still allows Practised, and one trial without documents per case.
- **The case that runs again.** `rtl/apb-gpio` is the one case W2-L1 read that runs again, because the document of
  control_logic_design changed (ip#439). Its trials start a new group for control_logic_design and also join the
  groups of apb and rtl_design that W2-L1 read (section 4).
- **The nine slots taken over.** W2-L1's plan gave `dv/cocotb-crc` a list of nine slots of its own, to run only in
  CI, outside its 153 slots; none of the nine ran. This plan takes those nine slots over: they are slots of this
  batch, under this plan's order, values and rules, and W2-L1's list is closed with no trial. The case's seat writes
  executable test code, so it runs only in CI, as every trial of this batch does.

Not in this batch:

- `dv/coverage-irq-ctrl` and `dv/formal-credit-counter`. Their skills are unchanged, so running them again would be
  a top-up of W2-L1 (decision 4).
- `rtl/apb-gpio-reset`. It is not a second case for control_logic_design and runs in no evidence batch until a
  ruling says how its trials would count (decision 3, item 2).
- Every other case W2-L1 read. No skill those cases name has changed.
- A second case for constrained_random, reference_modelling, model_checking, fsm_design, arbitration,
  pipeline_design or control_logic_design, and any case for systemverilog's document, log_analysis,
  regression_intelligence or regression_management (decisions 2, 3 and 8).

No case is left out under items 2 or 3 of decision 4, "Where it runs": gates W2C3 and W2C4 were met by the account
route (ip#451), so both equivalence cases and both coverage cases are in the plan and no evidence is owed to meeting
2 on that ground.

## 3. Slots, dispatch and records

**Order.** Eight rounds. Each round runs every case once on arm E, in a base order that keeps the two cases of a
skill apart and mixes the kinds. The base order is dv/equiv-gray, debug/triage-three-bugs, rtl/apb-gpio,
dv/plan-irq-ctrl, dv/formal-rr-arbiter, debug/root-cause-uart-tx, dv/fcov-lifo4, dv/equiv-updown,
dv/coverage-tick-timer, debug/triage-pwm-gen, dv/cocotb-crc, dv/plan-tick-timer, debug/root-cause-debounce. Each
round starts three places later in that order than the one before, so that a stop does not land on one case. The
13 arm N slots sit at the ends of the rounds, two after each of rounds 1 to 5 and one after each of rounds 6 to 8,
their cases in the base order. Section 12 lists every slot.

**Dispatch.** One dispatch is one slot. The workflow is `.github/workflows/live-eval.yml`, job `live-eval`,
dispatched from `main`, and the counting re-judge is its `rejudge` job on a fresh checkout of the same commit:

```
gh workflow run live-eval.yml -R nirmaansoftware/ip-nirmaan --ref main \
  -f case=<case> -f trials=1 -f knowledge=<on|off> -f purpose=evidence \
  -f harness=default -f expected_harness=<the arm's fingerprint of section 6>
```

`scripts/live_eval_ci.py` stops the job before any trial on a CLI that is not the pinned one or a fingerprint that
is not the expected one (exit 4), and after the trial on a record that is not the trial asked for. A slot is marked
attempted before its dispatch. The next slot is dispatched only after the whole run, `live-eval` and `rejudge`, has
finished, and never while another run of the workflow is queued or running: the `live-eval` concurrency group keeps
one pending run, so a second dispatch would cancel a queued one.

**Records.** The counted result of a slot is the re-judged record (`live-eval-rejudged-<run id>`): the record as the
trial job wrote it, with `rejudge.json`. Every record reaches `main` by pull request in slot order, none held out,
failed ones included. Every dispatch writes into a fresh folder, so two slots of one arm on one day get the same
record name; a slot's record is therefore committed at `evals/results/w2-remeasure/slot-NNN/<record name>/`, with
`NNN` the slot number in three digits and the name the one `record_run` wrote, unchanged. This is the form of the
whole-flow plan (`evals/plans/2026-11-22-g3-whole-flow.md`, section 15): `src/nirmaan/evals/levels.py` finds every
`manifest.json` under `evals/results` at any depth and lists a record by its path, and
`scripts/failure_curriculum.py` keys a failure by that path. The committed tests of nested slot records are the
whole-flow ones, so the first record pull request of this batch is where the repository's tests first run on a
nested single-seat record. A failed slot's `causes.md` sits beside its `manifest.json`. A record pull
request lists the slots it carries and their record names, packs whole records under the review's size limit, and
states no pass count: no figure of this batch is written in any text before the read.

## 4. The groups: new, and pooled with W2-L1's (gates W2C1 and W2C11)

A group is keyed by skill, seat model, skill digest, harness fingerprint and CLI version
(`src/nirmaan/evals/levels.py`). The case, the plan, the machine and the versions of the EDA tools are not in the
key (the record's fact 5). So this batch's trials start a new group where a skill's digest changed since W2-L1 was
read, and join the group W2-L1 read where it did not. A skill is Practised when its counted group has n of at least
5 and a Wilson lower bound of at least 0.5, with every trial re-judged clean (`docs/CAPABILITY_LEVELS.md`). By that
rule the smallest pass counts that count are 7 of 8, 12 of 16, 17 of 24, 22 of 32 and 40 of 64.

**New groups.** Arm E trials only; the digests are in section 6.

| Skill | Cases in this batch | Planned n | W2-L1's group for the skill |
|---|---|---|---|
| equivalence_checking | dv/equiv-gray, dv/equiv-updown | 16 | 5 of 8 on dv/equiv-gray, stale: the document changed (ip#431, ip#443, ip#453) |
| verification_planning | dv/plan-irq-ctrl, dv/plan-tick-timer | 16 | 6 of 8 on dv/plan-irq-ctrl, stale: the document changed (ip#439) |
| failure_triage | debug/triage-three-bugs, debug/triage-pwm-gen | 16 | 0 of 8 on debug/triage-three-bugs (no judge ran in any), stale: the card changed (ip#438) |
| root_cause_analysis | debug/root-cause-uart-tx, debug/root-cause-debounce | 16 | 7 of 8 on debug/root-cause-uart-tx, stale since ip#442 merged: the card changed |
| control_logic_design | rtl/apb-gpio | 8 | 6 of 8 on rtl/apb-gpio, stale: the document changed (ip#439) |
| functional_coverage | dv/fcov-lifo4 | 8 | none: no case named the skill |
| python_verification | dv/cocotb-crc | 8 | none: its nine slots never ran |

A stale group stays in `capability/levels.json` as recorded and counts toward nothing. No trial of this batch joins
one: `debug/root-cause-debounce` cannot join the old 7 of 8 group, because ip#442 merged before this plan was
committed (section 11).

**Pooled groups.** Each row is a group W2-L1 read, named here with its count and passes before trial 1, as the rule
of decision 4 requires. W2-L1's figures are those of its one read (the addendum of 2026-11-22 to
`council/records/2026-11-14-pilot-retrospective.md`) and are what `capability/levels.json` holds on the commit of
section 6. They stay as recorded: nothing here tops up, extends or reads W2-L1 again.

| Skill | W2-L1's cases | W2-L1: n | W2-L1: passed | This batch's case | This batch: planned n | Pooled n |
|---|---|---|---|---|---|---|
| formal_verification | dv/formal-credit-counter | 8 | 8 | dv/formal-rr-arbiter | 8 | 16 |
| sva | dv/formal-credit-counter | 8 | 8 | dv/formal-rr-arbiter | 8 | 16 |
| assertion_coverage | dv/formal-credit-counter | 8 | 8 | dv/formal-rr-arbiter | 8 | 16 |
| code_coverage | dv/coverage-irq-ctrl | 8 | 7 | dv/coverage-tick-timer | 8 | 16 |
| directed_testing | dv/directed-irq-ctrl, dv/random-crc, dv/scoreboard-mac | 24 | 24 | dv/cocotb-crc | 8 | 32 |
| apb | rtl/apb-gpio, rtl/apb-regs | 16 | 14 | rtl/apb-gpio | 8 | 24 |
| rtl_design | the seven RTL cases of W2-L1 | 56 | 54 | rtl/apb-gpio | 8 | 64 |

- Five of the seven rows add trials on a case the group has not run. The rows of apb and rtl_design add trials on
  `rtl/apb-gpio`, a case each group has run: that is the one exception decision 4 allows, for a case run again
  because the digest of a skill it names changed, and this table names every other group its trials join.
- Each pooled group is Practised today, so more trials can keep or lower its level (the record's fact 5). The
  level after the read is the one `capability/levels.json` computes on the pooled group.
- Both batches' trials are in one group only while the key is equal: seat model `claude-opus-5-5`, Claude Code
  2.1.325, the fingerprint and the skill digests of section 6. Those are W2-L1's values, and a dispatch is made only on them
  (section 7).
- What differs between the two batches and is not in the key: W2-L1's trials ran on the owner's machine, with that
  machine's versions of Verilator, Yosys and Icarus, which its records do not name; this batch's trials run in the
  CI job of section 5, with the tools as the seat account. The check that the second tool set judges as the first
  did is the replay of gate W2C5 (section 11), and the read states both environments (section 9).

## 5. Where it runs: the job, its tools, and the account of each tool (gates W2C2 to W2C4)

Every trial of this batch runs in the live evaluation's CI job (`.github/workflows/live-eval.yml`, job `live-eval`,
on GitHub's `ubuntu-24.04` runner), with the tools that read seat-written files running as the account
`nirmaan-seat`, and is re-judged in the `rejudge` job of the same run. No trial, replay or re-judge of this batch
runs on the owner's machine. Both jobs run the reach test (`scripts/live_eval_reach.py`) before any trial or
re-judge and stop unless every probe is denied and every control passed (`docs/LIVE_EVAL_EVIDENCE.md`, section 6).

**The job's tool set** (`.github/actions/live-eval-setup`, `.github/actions/oss-cad-suite`, `.github/live-eval`,
`pyproject.toml`):

| Tool | Where it comes from | Version |
|---|---|---|
| Claude Code | `.github/live-eval/package.json`, installed by `npm ci` against the lockfile's hashes | `2.1.325` |
| Python | `actions/setup-python` | `3.12` |
| Icarus Verilog (`iverilog`, `vvp`) | `apt-get install iverilog` on the runner image | `12.0-2build2` |
| Verilator (`verilator`, `verilator_coverage`) | `apt-get install verilator` on the runner image | `5.020-1` |
| Yosys (`yosys`, the `synth.run` gate) | `apt-get install yosys` on the runner image | `0.33-5build2` |
| SymbiYosys (`sby`), Yices (`yices-smt2`), `eqy`, and the Yosys and solvers they start | YosysHQ OSS CAD Suite, release 2026-09-28, checked by the sha256 in the action on every use | `2026-09-28` |
| cocotb | the `cocotb` extra of `pyproject.toml` | `2.1.0` |
| `make` and the C++ compiler of the Verilator model build | the runner image | not pinned |

The repository pins Claude Code, the OSS CAD Suite and cocotb. It does not pin the three apt packages or the runner
image: their versions above are the ones installed in run
[45073595509](https://github.com/nirmaansoftware/ip-nirmaan/actions/runs/45073595509), the replay on `main` that
`evals/flow/tool_reach_record.json` records. Every run's log states what it installed. The replays of gate W2C5 are
read against this table before slot 1, and a difference there means a plan amendment before trial 1. After slot 1,
a run whose log shows another version of a tool in this table stops the batch: no further slot is dispatched, the
trial that ran is a trial and stays, and the difference returns to the council before dispatch resumes. The read
names any such difference.

**Tools and accounts per case** (decision 4, "Where it runs", item 3). This is the table ip#451 stated when it met
gates W2C3 and W2C4, restated here; each case's held-out checks and their tools were read again from the case files
on the commit of section 6. "Seat" is the account `nirmaan-seat` in these jobs; "harness" is Python inside the
runner's own `nirmaan` process, which reads seat text as data.

| Case | Tools before review | Held-out checks | Programs, and the account that runs each |
|---|---|---|---|
| dv/equiv-gray, dv/equiv-updown | `equivalence.run` | must-fail `equivalence.run` | `eqy`, and the Yosys, SBY and solvers it starts: seat |
| dv/plan-irq-ctrl, dv/plan-tick-timer | `vplan.check` | must-fail `vplan.check` | none: `vplan.check` is harness code (`src/nirmaan/vplan.py`) |
| debug/triage-three-bugs, debug/triage-pwm-gen | `simulator.run` (Icarus), `veritriage.investigate` | must-fail-each `simulator.run` (Icarus) | `iverilog`, `vvp`: seat; `veritriage.investigate`: harness |
| debug/root-cause-uart-tx, debug/root-cause-debounce | `simulator.run` (Icarus); the fixed upstream triage stage runs `simulator.run` and `veritriage.investigate` | two must-fail `simulator.run` (Icarus) | `iverilog`, `vvp`: seat; `veritriage.investigate`: harness |
| rtl/apb-gpio | `lint.run`, `simulator.run`, `synth.run`, `formal.run`, `formal.cover` | held-out-run `simulator.run` on the staged reference testbench; must-fail `simulator.run`; two must-fail `formal.run`, each with `formal.cover` | `verilator --lint-only`, `iverilog`, `vvp`, `yosys`, `sby` with its Yosys and solver: seat |
| dv/fcov-lifo4 | `coverage.read`, `veritriage.investigate` | must-fail `coverage.read` | Verilator's `--coverage-line` model build with its `make` and compiler: seat; the built model, through `nirmaan-seat-model`: seat; the two `verilator_coverage` steps: runner, reading only the data file the backend names in the run's directory; `veritriage.investigate`: harness |
| dv/formal-rr-arbiter | `formal.run`, `formal.cover` | must-fail `formal.run` with `formal.cover` | `sby` with its Yosys and solver: seat |
| dv/coverage-tick-timer | `coverage.read`; the fixed upstream testbench stage runs `simulator.run` (Icarus) | must-fail `coverage.read` with its coverage bounds | as dv/fcov-lifo4 for `coverage.read`; `iverilog`, `vvp`: seat |
| dv/cocotb-crc | `simulator.run` (cocotb) | must-fail `simulator.run` (cocotb) | `iverilog`: seat; `vvp` with the seat's cocotb module inside it: seat |

So, by that table, one program runs as the runner over input a seat's run produced: `verilator_coverage`, twice per
`coverage.read`, on the coverage data file the model wrote as the account. It reads no seat HDL, and a fault in its
parser is within the residual decision 4 accepts (ip#451; `docs/LIVE_EVAL_EVIDENCE.md`, section 6). No case of the
batch runs seat-written C (`scripts/live_eval_ci.py` would refuse a live trial of one). In these jobs a wrapped tool
that cannot run as the account refuses the run and never falls back to the runner.

**What is claimed and what is not.** That the named tool steps run as `nirmaan-seat` in these jobs, and that in a
named run the listed probes were denied to that account through the named tools. Not claimed: anything about files
every account may read beyond the probed targets, a fault in a tool's own parser, or any screen class nobody has
found. That residual is the one the record states and accepts (decision 4, "Residual risk").

## 6. The values a dispatch is made on

Computed on `main` at `81bbaefd4a2dd8df50fce3a1fbe78065bfefefd2`, the commit this pull request was last merged
with (this file touches none of the files below), Claude Code 2.1.325.

| Item | Value |
|---|---|
| Default harness, with documents (arm E) | `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` |
| Default harness, without documents (arm N) | `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39` |
| Seat model | `claude-opus-5-5` |
| Claude Code, the pin of `.github/live-eval/package.json` | `2.1.325` |
| cocotb, the pin of `pyproject.toml` | `2.1.0` |

The harness is the default harness, named so since H3 (`docs/HARNESS.md`), with its three attempts; the dispatch
carries no other harness and no attempts option. Both fingerprints are `harness_sha256(...)` with the knowledge flag
of the arm, and both are the ones W2-L1's records carry (`evals/plans/2026-11-18-w2-l1.md`, "What ran"): no
fingerprint moved between W2-L1 and this plan.

Case digests (`case_digest`: the case and the bytes of every file it names, so its fixtures, its reference answer and
its mutants):

| Case | Case digest |
|---|---|
| `dv/equiv-gray` | `sha256:d3b0b6f5c5928296533c6b021b3a0fe6621ce317f2cba76e68ba071fd116f860` |
| `dv/equiv-updown` | `sha256:4b09a43c2c98a9316dd9fbc8279cd28f3e75f77982211d784ed8ee104afd80f5` |
| `dv/plan-irq-ctrl` | `sha256:1a553dafca71aece791fbac7921963f026cf0750fa3efd43e7f495dfd5ebb799` |
| `dv/plan-tick-timer` | `sha256:7737a5dbba68a1313cbd3ac54e330c5c6f56ae0d7b7a3cd3e59f7d8d1ccf21d4` |
| `debug/triage-three-bugs` | `sha256:7312c66195f8cdc8e7dee66f4984c56381a2c7c4d2bcbe49fc2b558750446941` |
| `debug/triage-pwm-gen` | `sha256:619d40ba18f41740d1fca50d12e45b6c3aa795938eb002f83d4f62ceef60fdf4` |
| `debug/root-cause-uart-tx` | `sha256:9be6d4f3a142bf825f6b7a8938d836e9acec0f3ad6b69bf4cc519d4f81a9f06c` |
| `debug/root-cause-debounce` | `sha256:5406d37bd5fd9afac83219fb4c0d70e9960300bbc2825cad507f52f9e09c2683` |
| `rtl/apb-gpio` | `sha256:99f32bda9197066b2e7ab67ef4cbdb2793259ae556a38257b5035f2e82d04cd5` |
| `dv/fcov-lifo4` | `sha256:95dd423e975cc32a31fe7743841b846370b88971758b080a8d197d1cf8723a3e` |
| `dv/formal-rr-arbiter` | `sha256:d87aa9e44e5d776badcfcf7ff7cb43f41cc3edf43a69a84bb811116f349518e5` |
| `dv/coverage-tick-timer` | `sha256:b4be7351302e30fcb73109e39941b7d05871cf99957c46a9495fda80e3cae17a` |
| `dv/cocotb-crc` | `sha256:33e82bcbc7ad3484867969aa9b51ed96ad9d218af263ee5e03cab58571c82542` |

Skill digests, with documents (`skill_digest`: the skill's card and its knowledge document), for every skill a batch
case names, the pooled ones included:

| Skill | Skill digest |
|---|---|
| `apb` | `sha256:5eb05f03c1201b9bd2acd8e66fea165abd5ba773977cacaf015ddc071119c38e` |
| `assertion_coverage` | `sha256:9a2e389eba23a86d1f98c45a933969b8cb2fd8dd38ff53d820dd31c0473d916f` |
| `code_coverage` | `sha256:b5a1c9b8bb5f208c1e3ffcae7e9a5da4f26811e68a36954bf58fc612c481ea9b` |
| `control_logic_design` | `sha256:19f9a617d8643c02b8bb4488d7c8d66483782a41654d3454627d2559eb59902f` |
| `directed_testing` | `sha256:6bf35095b83cbd9b641919c5b59bacdf5fc87ce7c569c2ad7df593ecddff70d6` |
| `equivalence_checking` | `sha256:3e5a9675b1f975732c708689218a173566da26d28321e898616b1f79b9db9bca` |
| `failure_triage` | `sha256:f94ee360df0608a5387e68952a4746f7b60c1a39ae395e3252bfd39f037d3317` |
| `formal_verification` | `sha256:496f8d92db14cfe796776c8c485fa2191df0c12e29c5a10bac2a86d7ac034dc7` |
| `functional_coverage` | `sha256:de690fa08b45794a7f2bb1e168a5aded6a571da2663bbf74bae5a4272f582f0f` |
| `python_verification` | `sha256:cc303244c1935cadc231a36fe79445481e3418ef00464b89b9e45ff366d45758` |
| `root_cause_analysis` | `sha256:f4d03c138a6b5294b9837be1fff05475a5b312326df7029c2da6250b8563bc34` |
| `rtl_design` | `sha256:012eb9b7155ed6eb7761adca880b338f10c8f978b15dfd92f5adbb3253307a52` |
| `sva` | `sha256:dd2c6a58cb270577169dd2af6f053c57a72ac38aaecfd5449d234887c78606ee` |
| `verification_planning` | `sha256:77aed8426f0d85155bdf20b574328b735932a9bd35c3c7a44ead921bcbe4b3e2` |

Digests of the gate code outside the fingerprint that the batch's checks run, and of the job. Each is the sha256 of
the lines `<sha256 of the file>  <path>` for the tracked files under the paths, in byte order of path
(`git ls-files -z -- <paths> | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256`), as in the whole-flow
plan:

| Group | Paths | Files | Digest |
|---|---|---|---|
| Gate backends | `src/nirmaan/integrations` | 60 | `sha256:eac184ecc60ae35bdc88e6f66c2fa3aceaabe4c32f62066e951d7d5e84e835f9` |
| Plan check | `src/nirmaan/vplan.py` | 1 | `sha256:9dfd92674fd08729156fb6b8cbedd3479d9a05bb69a6e890c07b77f62b4fb74a` |
| Triage engine | `src/veritriage` | 253 | `sha256:fc207ed693832819bef89910091a06e265e62185d98e111fdf69f93a765ef098` |
| Held-out scorers | `src/nirmaan/evals/scorers.py` | 1 | `sha256:5f4f7909a3207f3837d2af7ad60b85c0bae620e1d461afde57aea0d2a592ecb4` |
| Stage gates | `src/nirmaan/company/workflows.py` | 1 | `sha256:bcd15f8204e55f142f266afdd8e12a4947c7f6276382dd18f4c9893e616a9873` |
| Seat account | `scripts/live_eval_seat.py`, `.github/actions/live-eval-seat` | 2 | `sha256:4abec1ad1bb4fe9e48afb333c619c1d07ccd2e5df80b62f3142dc8ad750fa446` |
| Reach test | `scripts/live_eval_reach.py` | 1 | `sha256:581a4cebb61899090a1741fdbea49e51b57decdebdf0cb11c58562f60b4b93c0` |
| CI command | `scripts/live_eval_ci.py` | 1 | `sha256:3f396770975a7fcff4fc746c031e8694f768b921e90376c290e4fc023acf3e88` |
| Workflow, tool set and CLI pin | `.github/workflows/live-eval.yml`, `.github/actions/live-eval-setup`, `.github/actions/oss-cad-suite`, `.github/live-eval` | 5 | `sha256:09083077e0237a7e2b1ed89152d3d5b8f31836a03c8b78500b471d802f8e64d7` |

"Gate backends" holds every tool backend the tables of section 5 name. "Plan check" is `vplan.check`, which the
record asks this plan to pin by name. "Triage engine" is what `veritriage.investigate` runs. "Stage gates" is the
file that says which tools a seat's stage runs before review.

## 7. The freeze and the dispatch check (gate W2C7)

From slot 1 until the read, nothing merges that changes: a file in `harness.CODE`; a tool definition; the CLI pin; a
batch case's files; the card or the document of a skill a batch case names, the pooled ones included; the gate code
the batch's checks run (the groups of section 6); or the job's tool set (section 5). A change that would move a
default fingerprint returns to the council in any case.

**The dispatch check.** Before every slot the fingerprints, the seat model, the pins, the 13 case digests, the 14
skill digests and the nine group digests are recomputed on `main` as it is, and this file is compared with the copy
the values were read from. Any difference stops the dispatch: no trial runs on a value this committed plan does not
name. The same check is made on the commit slot 1 is dispatched from, before trial 1. Before slot 1 a difference is
settled by a plan amendment pull request. From slot 1 on a difference means the freeze was broken: dispatch stays
stopped and the matter returns to the council, since an amendment alone would let later slots run on other values
than the earlier ones and split a group inside the batch. The commit a run reports is compared with the commit just checked; if they differ, that commit is
checked too, and a run on a commit that fails the check is cancelled before its trial.

**One commit.** Decision 4 says the batch runs "from one commit, with one tool set". The workflow runs live trials
only from the head of `main`, and `main` moves when this plan merges and when each record pull request merges. This
plan therefore reads "one commit" as one set of the values of section 6: every dispatch is made from a head of
`main` on which each of those values is equal to this file's, so the code that seats, gates and judges a trial, its
case and the documents it is given are byte for byte the same in every slot. What may differ between two slots is
only what the freeze does not name: the batch's own merged records, `capability/levels.json`, and files that no
trial reads. Each record's manifest carries the commit it ran on, and the read lists every commit a slot ran on. If
the owner seats read "one commit" more narrowly than this, that is settled by an amendment before slot 1.

Record pull requests add records and regenerate `capability/levels.json`, and change nothing the freeze names. A
bypass found during the freeze stops dispatch, since no freeze keeps a known bypass in place (decision 5, item 1);
what follows is the council's to rule. The failure-to-curriculum rule applies to this batch's failed trials labelled
"model", as written; a change it produces to a card or a document of a batch skill merges only after the read.

## 8. Stop rules

- **Failed trials.** A trial that ends on a plan or usage limit, with no model answer, on a refusal by the input
  screen, or on a tool denied as the seat account is a failed trial. So is an interrupted trial. Each is committed as
  failed, never removed, never held out and never run again (decision 4, "Stops and the read"; decision 11 of the
  pilot retrospective; `council/records/2026-11-15-pilot-topup-reruns.md`).
- **No top-up, extension, replacement, early stop or second read.**
- **Limit stop.** `live_eval_ci.py trials` stops at exit 3 or a limit line. The slot is recorded failed, and the next
  slot is dispatched only after the limit has reset.
- **Job-level stops.** Exit 2 (bad input), exit 4 before the trial (a CLI or fingerprint that is not the expected
  one), a failed reach test, a missing secret or a failed tool install stop the job before the trials step, so no
  trial ran. The cause is fixed and the same slot is dispatched again. If a record exists for a dispatch, it is a
  trial and is committed as it is.
- **The re-judge.** A trial whose counting re-judge did not finish or did not hold is committed as the trial job
  wrote it. The level rule then gives its group the reason "trials without a clean re-judge", and that group does
  not count, a pooled group included. A re-judge is not a trial and changes no recorded answer; whether such a record
  may be re-judged again in the job is not decided here and goes to the council before the read. Dispatch waits for
  a person after any such slot.
- **A changed tool set** stops the batch as section 5 says.
- **Labels.** Each failed trial gets its cause label in `causes.md` before its record merges. A label is not changed
  after the outcome is seen (decision 8, item 4).
- **Counts are fixed here, never by outcome.**

## 9. The read (gate W2C11)

One read, taken once, after every one of the 117 records has merged. It is meeting 2 of the wave 2 close, an
addendum to the council record, and it is taken together with W2-L1's recorded figures; W2-L1 is not read again.

- **New groups.** For each skill of the first table of section 4: n, passes, the trials no judge ran, the Wilson
  interval and the level, from `scripts/capability_levels.py` on `main`.
- **Pooled groups.** For each skill of the second table: W2-L1's figure (n and passes, as section 4 states them),
  this batch's own figure (n and passes of its arm E trials on its case), and the pooled figure with its Wilson
  interval. The level is the one `capability/levels.json` computes on the pooled group; no level is computed from
  this batch's trials alone or from W2-L1's alone.
- **Per case.** For each of the 13 cases, the passes among its eight arm E trials, as a description. No interval and
  no level is given per case.
- **Commits and environments.** For W2-L1: `main` at 01adfe9, the owner's machine, the local CLI, tool versions not
  recorded. For this batch: every commit a slot ran on, the CI job, and the tool set of section 5 with any
  difference a run's log showed.
- **Arm N.** The 13 trials without documents, listed apart with their pass count. At one trial per case they show at
  most a batch-wide difference, and no conclusion per skill or per case follows.
- **Failures.** Every failed trial with its label, and the curriculum answers the record asks for (decision 8, item
  5: the eleven failures of W2-L1), each path existing on `main` by then.

Never said, in this plan, a record pull request, the read or any other text: a figure of this batch before the
read (a level or a count that `capability/levels.json` shows while only part of the batch is merged is an interim
figure and is never cited); a pooled figure without the two figures it is made of; a level as anything but what the
level rule computes; that the two batches ran on the same tools; that documents help, beyond the two arms' counts
stated side by side; anything decision 8 of `council/records/2026-11-22-eda-tools-seat-account.md` forbids; any
time, usage or cost figure.

## 10. The start (gate W2C8) and the order against the whole-flow batch (gate W2C9)

**The start.** Decision 5, item 4: this batch, and running it in CI, is a new ask to the founder; the founder's
approval of a wave 2 batch covered W2-L1 only. Slot 1 is dispatched only on the founder's answer on usage, or, if
the founder has not answered when gates W2C1 to W2C7 are met, on the orchestrator session's answer under the
founder's instruction, in the form of gate RT2 of the pilot retrospective. Whichever it is, it is recorded as what
it is in the dated addition of section 11 before slot 1; the second is never recorded as a founder decision.

**The order.** This batch and the whole-flow batch (`evals/plans/2026-11-22-g3-whole-flow.md`) draw on the same plan
limits and are never interleaved: one records its last trial before the other dispatches its first. The order is
left to the orchestrator session, and it is: the timer case's measured run and its twenty slots first, then this
batch. So slot 1 here is dispatched only after the timer case's last planned trial is recorded, and from slot 1
here until this batch's last trial is recorded no whole-flow dispatch is made, the register block's slots included.
The two batches never share a run window: no slot is dispatched while any run of the workflow is queued or running.

## 11. Conditions before slot 1

Each is met on `main` before trial 1. The pull request that meets a gate is its record; this table says where each
stood when this plan was committed.

| Gate | Condition | Where it stands |
|---|---|---|
| W2C1 | One committed plan | This file |
| W2C2 | No trial on the owner's machine; every trial in the job as the seat account; ET1 to ET4 met, ET8's documents merged, ET7's statement shown | Section 5. ET1: ip#445. ET2 to ET4: ip#444, with ET3's recorded replay on `main` in ip#452 (run 45073595509). ET8's documents, `docs/GATE_INPUTS.md`, `docs/GATE_INTEGRITY.md` and `docs/LIVE_EVAL_EVIDENCE.md`: changed by ip#444, ip#445, ip#451 and ip#452; whether every text follows decision 8 of that record is qa-evidence's to confirm. ET7: the two fingerprints of section 6 are W2-L1's |
| W2C3 | `eqy` installed and run as the seat account with its probe | ip#451; both equivalence cases are in the plan. Its probes ran in replays on that pull request's branch; their first runs on `main` are the replays of gate W2C5 |
| W2C4 | A build or run of a program from seat HDL outside the wrapped tools is made as the seat account with a probe; the table of tools and accounts | ip#451 (`coverage.read`), with the same note on its probes; the table of section 5 |
| W2C5 | Every batch case's reference answer replayed in the job on the batch's commit: passes, and every mutant fails | Not yet met: below |
| W2C6 | Merged before the plan: ip#443, ip#446, then ip#442 by itself; fresh check records; the `use sat` test; the text correction | ip#443 and ip#446 merged; ip#442 merged by itself as `81bbaefd`, after every other content change named in this row (ip#453 and ip#455 merged before it). Check records at the documents' present text: verification_planning and control_logic_design (ip#448), equivalence_checking (ip#455, after the corrections of ip#453). The `use sat` test for `dv/equiv-updown`: `tests/test_dv_second_formal_equiv_evals.py` (ip#449). The expected behaviour text of `dv/plan-tick-timer`: ip#449 |
| W2C7 | The freeze; a dispatch only on the plan's values | Section 7 |
| W2C8 | The start | Section 10; not yet met |
| W2C9 | Never interleaved | Section 10 |

Gates W2C10 and W2C11 are not conditions of slot 1: W2C10 is due before meeting 2 (its closed list and test merged
as ip#450), and W2C11 is the read (section 9).

**Gate W2C5, after this plan merges.** Each of the 13 cases is dispatched once as a replay (`replay=true`: the
case's reference answer, no model, no token) from `main`, on a commit that passes the dispatch check of section 7.
A replay passes when its `replay` job and its `rejudge` job succeed, the reference answer passes every tool before
review and every held-out check, which for a must-fail check means the clean file passes and every mutant fails,
the re-judge gives the same verdict, and both jobs' tool reach records show every probe denied. The versions each
replay's log shows are read against section 5. A replay is not a trial, counts toward nothing and is not committed
as a record. Slot 1 is not dispatched until all 13 have passed.

**The dated addition before slot 1.** One pull request adds a dated section to this file that names, for gate W2C5,
the 13 replay runs with their commits and results and the tool versions their logs show; for gate W2C8, which
answer the batch starts on; and for gate W2C9, that the timer case's last planned trial is recorded. It changes no
count, slot, arm, case or value. If a replay fails, the cause is fixed by a pull request of its own, and if that
moves a value of section 6, by a plan amendment as well, before any trial.

This plan is not a record and not a ruling. It is a document, committed once; before slot 1 it changes by an
amendment pull request, and from slot 1 on only by a council ruling or a dated addition that changes nothing fixed.

## 12. All 117 slots

| Slot | Round | Arm | Case |
|---|---|---|---|
| 1 | 1 | E (with documents, on) | dv/equiv-gray |
| 2 | 1 | E (with documents, on) | debug/triage-three-bugs |
| 3 | 1 | E (with documents, on) | rtl/apb-gpio |
| 4 | 1 | E (with documents, on) | dv/plan-irq-ctrl |
| 5 | 1 | E (with documents, on) | dv/formal-rr-arbiter |
| 6 | 1 | E (with documents, on) | debug/root-cause-uart-tx |
| 7 | 1 | E (with documents, on) | dv/fcov-lifo4 |
| 8 | 1 | E (with documents, on) | dv/equiv-updown |
| 9 | 1 | E (with documents, on) | dv/coverage-tick-timer |
| 10 | 1 | E (with documents, on) | debug/triage-pwm-gen |
| 11 | 1 | E (with documents, on) | dv/cocotb-crc |
| 12 | 1 | E (with documents, on) | dv/plan-tick-timer |
| 13 | 1 | E (with documents, on) | debug/root-cause-debounce |
| 14 | 1 | N (without documents, off) | dv/equiv-gray |
| 15 | 1 | N (without documents, off) | debug/triage-three-bugs |
| 16 | 2 | E (with documents, on) | dv/plan-irq-ctrl |
| 17 | 2 | E (with documents, on) | dv/formal-rr-arbiter |
| 18 | 2 | E (with documents, on) | debug/root-cause-uart-tx |
| 19 | 2 | E (with documents, on) | dv/fcov-lifo4 |
| 20 | 2 | E (with documents, on) | dv/equiv-updown |
| 21 | 2 | E (with documents, on) | dv/coverage-tick-timer |
| 22 | 2 | E (with documents, on) | debug/triage-pwm-gen |
| 23 | 2 | E (with documents, on) | dv/cocotb-crc |
| 24 | 2 | E (with documents, on) | dv/plan-tick-timer |
| 25 | 2 | E (with documents, on) | debug/root-cause-debounce |
| 26 | 2 | E (with documents, on) | dv/equiv-gray |
| 27 | 2 | E (with documents, on) | debug/triage-three-bugs |
| 28 | 2 | E (with documents, on) | rtl/apb-gpio |
| 29 | 2 | N (without documents, off) | rtl/apb-gpio |
| 30 | 2 | N (without documents, off) | dv/plan-irq-ctrl |
| 31 | 3 | E (with documents, on) | dv/fcov-lifo4 |
| 32 | 3 | E (with documents, on) | dv/equiv-updown |
| 33 | 3 | E (with documents, on) | dv/coverage-tick-timer |
| 34 | 3 | E (with documents, on) | debug/triage-pwm-gen |
| 35 | 3 | E (with documents, on) | dv/cocotb-crc |
| 36 | 3 | E (with documents, on) | dv/plan-tick-timer |
| 37 | 3 | E (with documents, on) | debug/root-cause-debounce |
| 38 | 3 | E (with documents, on) | dv/equiv-gray |
| 39 | 3 | E (with documents, on) | debug/triage-three-bugs |
| 40 | 3 | E (with documents, on) | rtl/apb-gpio |
| 41 | 3 | E (with documents, on) | dv/plan-irq-ctrl |
| 42 | 3 | E (with documents, on) | dv/formal-rr-arbiter |
| 43 | 3 | E (with documents, on) | debug/root-cause-uart-tx |
| 44 | 3 | N (without documents, off) | dv/formal-rr-arbiter |
| 45 | 3 | N (without documents, off) | debug/root-cause-uart-tx |
| 46 | 4 | E (with documents, on) | debug/triage-pwm-gen |
| 47 | 4 | E (with documents, on) | dv/cocotb-crc |
| 48 | 4 | E (with documents, on) | dv/plan-tick-timer |
| 49 | 4 | E (with documents, on) | debug/root-cause-debounce |
| 50 | 4 | E (with documents, on) | dv/equiv-gray |
| 51 | 4 | E (with documents, on) | debug/triage-three-bugs |
| 52 | 4 | E (with documents, on) | rtl/apb-gpio |
| 53 | 4 | E (with documents, on) | dv/plan-irq-ctrl |
| 54 | 4 | E (with documents, on) | dv/formal-rr-arbiter |
| 55 | 4 | E (with documents, on) | debug/root-cause-uart-tx |
| 56 | 4 | E (with documents, on) | dv/fcov-lifo4 |
| 57 | 4 | E (with documents, on) | dv/equiv-updown |
| 58 | 4 | E (with documents, on) | dv/coverage-tick-timer |
| 59 | 4 | N (without documents, off) | dv/fcov-lifo4 |
| 60 | 4 | N (without documents, off) | dv/equiv-updown |
| 61 | 5 | E (with documents, on) | debug/root-cause-debounce |
| 62 | 5 | E (with documents, on) | dv/equiv-gray |
| 63 | 5 | E (with documents, on) | debug/triage-three-bugs |
| 64 | 5 | E (with documents, on) | rtl/apb-gpio |
| 65 | 5 | E (with documents, on) | dv/plan-irq-ctrl |
| 66 | 5 | E (with documents, on) | dv/formal-rr-arbiter |
| 67 | 5 | E (with documents, on) | debug/root-cause-uart-tx |
| 68 | 5 | E (with documents, on) | dv/fcov-lifo4 |
| 69 | 5 | E (with documents, on) | dv/equiv-updown |
| 70 | 5 | E (with documents, on) | dv/coverage-tick-timer |
| 71 | 5 | E (with documents, on) | debug/triage-pwm-gen |
| 72 | 5 | E (with documents, on) | dv/cocotb-crc |
| 73 | 5 | E (with documents, on) | dv/plan-tick-timer |
| 74 | 5 | N (without documents, off) | dv/coverage-tick-timer |
| 75 | 5 | N (without documents, off) | debug/triage-pwm-gen |
| 76 | 6 | E (with documents, on) | rtl/apb-gpio |
| 77 | 6 | E (with documents, on) | dv/plan-irq-ctrl |
| 78 | 6 | E (with documents, on) | dv/formal-rr-arbiter |
| 79 | 6 | E (with documents, on) | debug/root-cause-uart-tx |
| 80 | 6 | E (with documents, on) | dv/fcov-lifo4 |
| 81 | 6 | E (with documents, on) | dv/equiv-updown |
| 82 | 6 | E (with documents, on) | dv/coverage-tick-timer |
| 83 | 6 | E (with documents, on) | debug/triage-pwm-gen |
| 84 | 6 | E (with documents, on) | dv/cocotb-crc |
| 85 | 6 | E (with documents, on) | dv/plan-tick-timer |
| 86 | 6 | E (with documents, on) | debug/root-cause-debounce |
| 87 | 6 | E (with documents, on) | dv/equiv-gray |
| 88 | 6 | E (with documents, on) | debug/triage-three-bugs |
| 89 | 6 | N (without documents, off) | dv/cocotb-crc |
| 90 | 7 | E (with documents, on) | debug/root-cause-uart-tx |
| 91 | 7 | E (with documents, on) | dv/fcov-lifo4 |
| 92 | 7 | E (with documents, on) | dv/equiv-updown |
| 93 | 7 | E (with documents, on) | dv/coverage-tick-timer |
| 94 | 7 | E (with documents, on) | debug/triage-pwm-gen |
| 95 | 7 | E (with documents, on) | dv/cocotb-crc |
| 96 | 7 | E (with documents, on) | dv/plan-tick-timer |
| 97 | 7 | E (with documents, on) | debug/root-cause-debounce |
| 98 | 7 | E (with documents, on) | dv/equiv-gray |
| 99 | 7 | E (with documents, on) | debug/triage-three-bugs |
| 100 | 7 | E (with documents, on) | rtl/apb-gpio |
| 101 | 7 | E (with documents, on) | dv/plan-irq-ctrl |
| 102 | 7 | E (with documents, on) | dv/formal-rr-arbiter |
| 103 | 7 | N (without documents, off) | dv/plan-tick-timer |
| 104 | 8 | E (with documents, on) | dv/coverage-tick-timer |
| 105 | 8 | E (with documents, on) | debug/triage-pwm-gen |
| 106 | 8 | E (with documents, on) | dv/cocotb-crc |
| 107 | 8 | E (with documents, on) | dv/plan-tick-timer |
| 108 | 8 | E (with documents, on) | debug/root-cause-debounce |
| 109 | 8 | E (with documents, on) | dv/equiv-gray |
| 110 | 8 | E (with documents, on) | debug/triage-three-bugs |
| 111 | 8 | E (with documents, on) | rtl/apb-gpio |
| 112 | 8 | E (with documents, on) | dv/plan-irq-ctrl |
| 113 | 8 | E (with documents, on) | dv/formal-rr-arbiter |
| 114 | 8 | E (with documents, on) | debug/root-cause-uart-tx |
| 115 | 8 | E (with documents, on) | dv/fcov-lifo4 |
| 116 | 8 | E (with documents, on) | dv/equiv-updown |
| 117 | 8 | N (without documents, off) | debug/root-cause-debounce |

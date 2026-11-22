# The CI path (step 5 of the build; WF9, WF13, WF17)

Both cases run in the live evaluation's own jobs,
`.github/workflows/live-eval.yml` (`docs/LIVE_EVAL_EVIDENCE.md`, section 6):
one CLI pin, one tool set, the seat account and its reach test, the tree hash
around the trials and the counting re-judge in a job of its own on a fresh
checkout. No new workflow and no new action.

- **Named, one trial per dispatch.** `scripts/live_eval_ci.py` knows a
  whole-flow case only by its ID (`flow/axil-timer`,
  `flow/axi4-lite-regs-driver`). It refuses `trials` other than 1 and a
  harness other than `default` for one, so each dispatch is one slot of the
  batch plan and the arms can be interleaved by dispatch order.
- **The fingerprint** it checks is the whole-flow one
  (`harness_sha256(flow="whole")`, digesting `harness.FLOW_CODE`), and every
  record must carry `flow: whole` as well as the purpose, knowledge label,
  variant, fingerprint and CLI asked for. The single-seat fingerprints are
  unchanged.
- **One tool set.** For a `flow/` case, `.github/actions/live-eval-setup`
  also installs the RISC-V cross compiler that `ci.yml` installs (RV32I
  multilib checked) and fails if any of `verilator`, `iverilog`, `vvp`,
  `yosys`, `sby`, `yices-smt2`, `cc`, `make`, `riscv64-unknown-elf-gcc` or
  `cocotb-config` is missing. Single-seat cases get the tool set they had.
- **The credential test for seat C** (decision 4; second addendum,
  decision 2, item 1). Every job that runs a `flow/` case runs
  `scripts/live_eval_fw_reach.py` after the cocotb reach test and before the
  checkout is hashed. It compiles a driver test in C for this run and runs it
  through `fw.test`'s co-simulation backend on the reference register block,
  under a parent process that holds two canaries in its real environment
  (one under `CLAUDE_CODE_OAUTH_TOKEN`). Its tests try to run as the runner
  or in another group, run `sudo -n`, create a file in the checkout, the
  installed package and the records folder, and in Actions open for writing
  every other target of the cocotb reach test, find a canary in any
  `/proc/<pid>/environ`, read its parent's environment at all, read a
  runner-only file and signal the harness; a control writes its own run
  directory. The result is uploaded as `live-eval-fw-reach-<job>-<run id>`.
  Since M90 `fw.test` runs the program it builds as `nirmaan-seat`
  (`docs/LIVE_EVAL_EVIDENCE.md`, section 6) and the step runs with
  `--require-denied`: a gate.
- **The first recorded result** (run 44401041085, job `replay`, head
  feda503, before M90; replaced on `main` by gate SC3, below):
  every probe not denied. The C ran as the runner (uid 1001), `sudo -n true`
  exited 0, it created a file in the checkout, `src/nirmaan`, `scripts`,
  `evals`, `site-packages` and the records folder, it read its parent's
  `/proc/<pid>/environ` holding both canaries (the credential-named one
  included), its own environment held the plain one, and it read the
  runner-only file and could signal the harness.
- **Since M90** every job that runs seat C runs the test with
  `--require-denied`, so each job shows its own result. The committed record
  (`evals/flow/credential_test_record.json`, gate SC3 of
  `council/records/2026-11-19-seat-c-live-refusal.md`) is from run
  44585417262, a replay of `firmware/axi4-lite-driver` on `main` at 0c4f45b:
  the `replay` and `rejudge` jobs, each in gate mode with all 9 probes denied.
  It reached `main` in a pull request of its own, which changed no code it
  grades. The re-judge gate on the register block flow (decision 2, addition
  3) is shown by a replay of that case on `main` at 45a22c8, run 45026197824:
  the credential test in gate mode and the `confined` step in both the
  `replay` and the `rejudge` job, and a re-judge with the same verdicts
  (`evals/flow/flow_rejudge_gate_record.json`; `gates/WF17.md`).
- **The register block flow stays refused.** Its firmware stage and its
  held-out checks run seat C, so `check --require-expected` and `trials`
  refuse it with exit 6 before any trial. Since M90 the program `fw.test`
  builds executes as the seat account, seat C is still compiled as the
  runner, and the credential test is a gate (`docs/LIVE_EVAL_EVIDENCE.md`,
  section 6). The refusal stays until gates WF15 to WF19 and the dated plan
  addition are met and a change of its own lifts it (`council/records/2026-11-19-seat-c-live-refusal.md`, decision 2). A replay of it still runs: its code is
  the reference answer.
- **The timer flow** links no seat C (its checks and stages run HDL, and its
  testbenches run in `vvp` as the seat account), so it runs live now.

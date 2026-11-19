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
  (one under `CLAUDE_CODE_OAUTH_TOKEN`). Its tests try to run as the runner,
  run `sudo -n`, create a file in the checkout, the installed package and the
  records folder, find a canary in any `/proc/<pid>/environ`, read its
  parent's environment at all, read a runner-only file and signal the
  harness; a control writes its own run directory. The result is uploaded as
  `live-eval-fw-reach-<job>-<run id>`. It is recorded, not a gate:
  `fw.test` runs seat C by path, as the runner. `--require-denied` makes it
  a gate.
- **The recorded result** (`evals/flow/credential_test_record.json`, run
  44401041085, job `replay`, head feda503): every probe not denied. The C ran
  as the runner (uid 1001), `sudo -n true` exited 0, it created a file in the
  checkout, `src/nirmaan`, `scripts`, `evals`, `site-packages` and the records
  folder, it read its parent's `/proc/<pid>/environ` holding both canaries
  (the credential-named one included), its own environment held the plain
  one, and it read the runner-only file and could signal the harness. So the
  register block flow waits, as below.
- **The register block flow stays refused.** Its firmware stage and its
  held-out checks run seat C, so `check --require-expected` and `trials`
  refuse it with exit 6 before any trial, as M89 refuses the single-seat
  firmware case. It runs live only once `fw.test` builds and runs seat C as
  the seat account (a harness change, after wave 2's first live batch is
  read), the credential test then shows every probe denied and is switched to
  a gate, and gates WF15 to WF19 are met. A replay of it still runs: its code
  is the reference answer.
- **The timer flow** links no seat C (its checks and stages run HDL, and its
  testbenches run in `vvp` as the seat account), so it runs live now.

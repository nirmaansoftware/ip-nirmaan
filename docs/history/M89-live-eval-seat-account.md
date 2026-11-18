# Milestone 89 - Live evaluation seat account

Gates WF9 and WF17 of the G3 council record
(`council/records/2026-11-17-g3-whole-flow-cases.md`, second addendum,
decision 2 item 1). In `.github/workflows/live-eval.yml` the trials ran
model-written code (a cocotb test module, inside `vvp`) as the runner user,
who has passwordless sudo, owns the checkout, the installed package and the
records, and whose `nirmaan` process holds the plan token. The re-judge ran in
the same job and checkout, nothing checked that the checkout was unchanged, and
no test showed what seat code could reach. Design:
`docs/LIVE_EVAL_EVIDENCE.md`, section 6. Tests: `tests/test_live_eval_seat.py`,
`tests/test_live_eval_ci.py`, `tests/test_nirmaan_live_eval.py`.

**The seat account.** `.github/actions/live-eval-seat` and
`scripts/live_eval_seat.py` make `nirmaan-seat` (no password, no sudo rule, no
group but its own) and put a root-owned `vvp` first on `PATH`. It runs the
real one through a root helper with `setpriv`: `no_new_privs`, an environment
of cocotb's settings only, write access to the run's own directory only. When
the run ends every seat process is killed, what it made goes back to the
runner (links and other non-regular files removed), and every grant is taken
back. The action also takes other accounts' write access from the hosted
runner's tool cache, its global `node_modules` and every folder on `PATH`,
which the first replays' reach tests found writable by every account (runs
44325101430 and 44326711465).

**The reach test.** `scripts/live_eval_reach.py` runs, before any trial or
re-judge, a cocotb module through `simulator.run`'s cocotb backend whose tests
try sudo, writes to the checkout, the package, `PATH`, the gate programs, the
records and the step's command files, two canaries in every reachable
environment, a runner-only file and a signal to the harness, with a control
that writes the run's own directory. It fails closed on a target it cannot
determine. The job stops unless every probe is denied.

**The tree hash and the counting re-judge.** `scripts/live_eval_ci.py tree`
hashes the checkout before and after the trials; a change fails the job. The
new `rejudge` job runs on a fresh checkout of the same commit with the records
only from the artifact, refuses records whose trial job's two hashes differ,
runs the reach test and re-judges with `--write`. Seat code the re-judge runs
runs as the seat account; reading WF17's "a job that ran no seat code" as "no
seat code before the re-judge" is stated for security and the Founder Proxy to
confirm.

**Seat C waits.** `fw.build` and `fw.test` run seat C by path, so a live trial
of a case that runs seat C is refused (exit 6) until they run as the account
too.

**No harness change.** Nothing under `src/` changes, so every fingerprint is
unchanged. Replays of `dv/cocotb-crc` (run 44327170136) and `rtl/sync-fifo`
(run 44329453905) passed through the account, the reach test, the hashes and
the `rejudge` job.

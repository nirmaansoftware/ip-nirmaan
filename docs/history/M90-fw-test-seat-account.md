# Milestone 90 - Seat C as the seat account

Gate WF17 of the G3 council record
(`council/records/2026-11-17-g3-whole-flow-cases.md`, second addendum,
decision 2 item 1; fourth addendum, decision 2 items 4 and 5). Since M89 the
live evaluation ran cocotb's `vvp` as `nirmaan-seat`, but `fw.test` ran the
program it builds from the seat's C by path, as the runner, and the
credential test recorded every probe not denied (run 44401041085). Design:
`docs/LIVE_EVAL_EVIDENCE.md`, section 6. Tests:
`tests/test_live_eval_seat.py`, `tests/test_live_eval_ci.py`,
`tests/test_nirmaan_live_eval.py`, `tests/test_nirmaan_firmware.py`.

**The wrapper.** `scripts/live_eval_seat.py install` also writes
`/opt/nirmaan-seat/bin/nirmaan-seat-exec`, root's. Where it is on `PATH`,
`fw.test`'s last step runs the built program through it
(`nirmaan.integrations.firmware.seat_run`), in a new folder `seat` of the
run's directory. The root helper's `run-built` mode runs it as
`nirmaan-seat` with `setpriv` (`no_new_privs`, no groups, no capabilities),
`env -i` with no setting of the caller's, an ACL that gives write access to
that folder only, and the M89 cleanup. It refuses a program that is not a
regular file the runner built in the same run directory, reached through no
link, writable by no other account and not set-id. A run ended by a signal
ends the helper by the same signal, so `fw.test` reports what it reports
without the account. Off the live-eval jobs there is no wrapper and the
steps are as before.

**The credential test is a gate.** `scripts/live_eval_fw_reach.py` now also
checks the probe's groups and, in Actions, tries every folder and file of the
cocotb reach test (`PATH`, the gate programs, both wrappers and `seat.py`,
the runner's temporary folder, the step's command files). The workflow runs
it with `--require-denied`, which also fails when `fw.test` found no wrapper.

**What stays.** The compile and link steps of `fw.build` and `fw.test` run
the compiler as the runner over the seat's C (they run none of it); that
residual is open for the security seat. The register block flow is still
refused live (exit 6) until gates WF15 to WF19 and the dated plan addition.

**The single-seat firmware case runs live (decision #35 of 2026-11-19).**
`scripts/live_eval_ci.py` lets `firmware/axi4-lite-driver` (`SEAT_C_LIVE`)
start trials only on the credential test record of the same job (the trials
step's `FW_REACH`): this run, attempt, job and commit, written with
`--require-denied`, every probe denied, the control written, the wrapper
found. The workflow runs the credential test for `firmware/` cases too.

**No fingerprint change.** The files changed are outside `harness.CODE`,
`LOOP_CODE` and `FLOW_CODE`, and no tool definition changes. With Claude Code
2.1.325 the default fingerprint stays
`sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` and
the whole-flow one
`sha256:d90b3c1840870ae9434b90188dbb3078473140d56b2dec9e295c515c1832adfc`
(`tests/test_live_eval_seat.py` checks the files against the lists).

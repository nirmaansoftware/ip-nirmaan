# Council record: seat C as the seat account, and the live refusal (2026-11-19)

Pull request ip#371 (M90) makes `fw.test` run the program it builds from
seat-written C as the unprivileged account `nirmaan-seat` in the live
evaluation jobs. On that basis the build lane asked for four things: (a) to
lift the live refusal (exit 6) for the single-seat case
`firmware/axi4-lite-driver` when the same job's credential test shows every
probe denied; (b) to keep `flow/axi4-lite-regs-driver` refused; (c) to make
the separate re-judge job run the credential test too, failing closed; and
(d) a ruling on what is left: seat C is still compiled and linked as the
runner.

Ruling, in short:

- **(a) is not ratified as it stands.** The lift is allowed only after gates
  SC1 to SC6 below are met, in a pull request of its own. Until then every
  case that runs seat C stays refused for live trials.
- **(b) is confirmed**, with three additions for the register block.
- **(c) is ratified**, and the reading of gate WF17 that M89 left open is
  confirmed with a narrower wording.
- **(d) is not accepted on a statement.** The compile reach is closed, by a
  screen or by compiling as the seat account, before any live trial of a case
  that compiles seat C. It does not hold ip#371, which leaves the refusal
  unchanged.

Four seats gave round 1 positions independently, each as its own read-only
process that saw no other position (security, firmware-engineer, qa-evidence,
eda-tooling); the chair decided. The meeting was kept to the seats that own
the account and gate WF17 (security), the driver case and its judge
(firmware-engineer), the claims and the evidence (qa-evidence), and the job
and the build (eda-tooling). Read against ip-nirmaan `main` at ffc69e3 and
ip#371 at head f03b2f7 (branch `fw-seat-account`, not merged), and the lift
as built on commit e6f96f4 (branch `fw-firmware-live`, not in ip#371). Seats
read run logs and uploaded run records; firmware-engineer compiled three
small probe files on a local machine, outside the repository. No trial ran,
no workflow was dispatched, and this record changes no code, case, eval
record, level or gate. Code it needs is listed as gates.

A key is an agent review. Nothing here is a person's approval, a release, or
a claim that a design is ready to be made in silicon.

## Who decided what

The council decided every item below. The orchestrator called the meeting
under the founder's standing instruction, after key 1 failed an earlier head
of ip#371 because it loosened a live refusal on decisions held in no
committed record. It is not a founder decision, and the founder can overrule
it. No seat found anything reserved for the founder: it adds no spending,
contract, counsel, sending, public name or licence term. A pull request that
changes what a gate refuses is in a founder class and goes to the Founder
Proxy (agent) by the usual rule.

## Facts checked

The chair checked each line below unless a seat is named as the source.
"Inference" marks what no seat ran in the live evaluation job.

1. The refusal on `main`. `scripts/live_eval_ci.py` (`seat_c_problem`)
   refuses with exit 6, before any trial, a live trial of every case that
   runs seat C: a case whose seat is `firmware`, whose held-out checks use
   `fw.build` or `fw.test`, or a whole flow with a `firmware` stage. That is
   `firmware/axi4-lite-driver` and `flow/axi4-lite-regs-driver`. A replay of
   a reference answer still runs.
2. Where it comes from. For the flow case, the G3 record
   (`council/records/2026-11-17-g3-whole-flow-cases.md`, decision 4, gates WF9
   and WF17). For the single-seat case no council record named it before this
   one: ip#342 (M89) refused it on the same reasoning.
3. The committed credential record,
   `evals/flow/credential_test_record.json` (run 44401041085, before M90):
   every probe not denied; seat C ran as the runner and read the parent's
   environment with the credential-named canary in it. It is still the
   record on `main` and on ip#371.
4. ip#371 at f03b2f7. `scripts/live_eval_seat.py` runs the built program
   through a root-owned wrapper with `setpriv` (`no_new_privs`, no groups, no
   capabilities), `env -i`, write access to one new folder `seat` of the run
   directory, then the M89 cleanup; it refuses a program that is not a
   regular file the runner built in the same run directory, or that is
   reached through a link, writable by another account, or set-id. Security
   found no race open to the seat account. The credential test
   (`scripts/live_eval_fw_reach.py --require-denied`) is a gate in the
   `replay`, `live-eval` and `rejudge` jobs for `flow/` and `firmware/`
   cases. The mode `confined` of `scripts/live_eval_ci.py` exits 6 in the
   replay and re-judge steps for a case that runs seat C unless that job's
   own record shows the gate mode, every probe denied, the control written
   and the wrapper found, for the same run, attempt, job and commit. It
   decides by the case's data, not its name, so a case under another prefix
   gets no record and is refused (eda-tooling). No step has
   `continue-on-error`. The live refusal is unchanged at this head. No file
   in `harness.CODE`, `LOOP_CODE` or `FLOW_CODE` and no tool definition
   changes (eda-tooling read the lists).
5. The replays. All are `workflow_dispatch` runs in replay mode on the
   branch; the live evaluation workflow is not a required check; no live
   trial of a case that runs seat C has ever run.
   - Run 44436318890 (91bbb2b, `flow/axi4-lite-regs-driver`), replay job:
     seven probes and the control, every probe denied; uid 999, no
     supplementary groups, `sudo -n` exit 1, 52 write targets refused, no
     canary found, the parent's and the harness's environment, the
     runner-only file and the signal refused. Its `rejudge` job had no
     credential test and no `confined` step: that head did not have them
     (qa-evidence, eda-tooling).
   - Run 44441146513 (22aac7d, `firmware/axi4-lite-driver`): concluded
     success; its `rejudge` job also had no credential test (qa-evidence).
   - Run 44442855035 (1727346, `firmware/axi4-lite-driver`): the replay and
     the `rejudge` job each ran the credential test in gate mode with every
     probe denied, `confined` passed in both, and the re-judge was `same`.
     From 1727346 to f03b2f7 the three confinement files change in comments
     and messages only (qa-evidence).
   - Run 44486616543 (f03b2f7, `firmware/axi4-lite-driver`): concluded
     success after round 1; its `rejudge` job ran the credential test step
     and the re-judge step, both green (the chair read the step list, not
     the record).
   - No concluded run shows the re-judge gate on the flow case. No run
     exercises the wrapper's refusals or the exit 6 path of `confined`;
     committed tests do.
6. What the probes show and what they do not (security). They show that the
   built program, when it executes, is the seat account and is denied each
   listed target. They show nothing about the compile and link steps, about
   network access (there is no probe), or about reading files every account
   may read.
7. The fallback. `seat_run` in `src/nirmaan/integrations/firmware.py` runs
   the built program as the caller when the wrapper is not on `PATH`, without
   saying so. The gate shows the credential test's own run used the wrapper,
   once at the start of a job that may run up to twenty trials; it does not
   show each trial's run did (security, eda-tooling).
8. The compile steps. `fw.build` and `fw.test` compile each C file of the
   seat with the host `cc` under the strict flags, as the runner, and the one
   `verilator --cc --exe --build` step links as the runner. No seat code
   executes there. No check of C `#include` exists: `eda_guard.py` screens
   Verilog only, and the object screen of gate WF16 runs for the whole-flow
   scorers only. The single-seat case names the scorer `held-out-run`, so
   that screen, its rule against asm included, never runs for it
   (`evals/firmware/axi4_lite_driver.json`; security, firmware-engineer,
   eda-tooling).
9. What the compile reach allows.
   - Fact, compiled on a local machine with the strict flags and the
     include order `fw.test` uses, not in CI (firmware-engineer): seat files
     that include the committed reference driver, its header and its map by
     an absolute path, or by a path with `..`, compile clean, and the
     held-out test compiles against them. A top-level asm line that makes
     the assembler copy a file into the object also compiles clean. The `-I`
     folders and the strict flags stop neither.
   - Inference: a seat's driver that is one such include line passes both
     held-out checks of the single-seat case without a driver being written.
     Including the held-out test shows its text in diagnostics, and a failed
     run's log excerpt returns to the seat on a retry.
   - Inference (security): the assembler route copies any file the runner
     can read into the program, which then holds it as the seat account. The
     model has no tools, so seat C is its only reach, but with retries one
     attempt can learn what a later one needs. Fact 3 shows the runner's
     account reads the environment of the process that holds the plan
     credential.
   - Fact (security): the M53 redaction replaces only the exact value of a
     credential-named variable. A changed or split value is not replaced, in
     the log, the retry text or the uploaded record.
   - Inference (eda-tooling): a `#line` directive in seat text makes the
     lines after it look like another file's, and the asm rule of the object
     screen then skips them. No test covers it.
   - Assumption (eda-tooling): the seat account can read the checkout. Only
     writes are probed. If so, compiling as the seat account alone does not
     stop an include of the reference answer.
10. The re-judge compiles stored seat C the same way, so a re-judge repeats
    an include of the reference answer identically and cannot detect one
    (security).
11. The nonce of a `fw.test` run now also appears on the command line of
    `sudo` and the root helper; the credential test has no probe of another
    process's command line (firmware-engineer; that such a line is readable
    by the seat account is an assumption).
12. The single-seat case has two held-out checks and no mutant, and
    `device_drivers` is outside the must-fail domains (G3 record, fact 11).
    Four broken fixtures are committed for the block: three drivers and a
    wrong map header (firmware-engineer).

## Decisions

### 1. The lift is not ratified as it stands

No seat would lift the refusal today. Security, firmware-engineer and
qa-evidence refused for now; eda-tooling ratified only with conditions, and
its conditions are the same things the other three asked for first.

Why. The rule the G3 record weighs against is that code a seat writes must
not reach anything the judge does not intend it to reach. M90 makes that
hold for the program when it executes. It does not hold while seat text is
compiled: by facts 8 and 9 a seat could pass the case with the reference
answer included, or carry a file the runner can read into its own program.
A same-job credential record cannot show otherwise, because it probes only
the executed program (fact 6). And the evidence is not yet on `main`: the
committed record says every probe was not denied (fact 3).

The lift is allowed when all of these are true on `main`, and only then:

1. **The compile reach is closed** as decision 4 asks, in force for the
   single-seat case, with its must-refuse fixtures recorded (gate SC1).
2. **No silent fallback.** A live trial of a case that runs seat C stops
   unless each `fw.test` run of that trial started through the wrapper: the
   trials step refuses a record whose run command does not, or `seat_run`
   refuses instead of falling back in these jobs (gate SC2).
3. **A committed credential record from `main`.** A replay dispatched on
   `main`, at the merge commit of ip#371 or a later commit with the same
   confinement files, with the record of the replay job and of the `rejudge`
   job, in gate mode, every probe denied. It replaces the record of fact 3,
   in a pull request of its own that changes no code the record grades
   (gate SC3).
4. **The refusal is shown.** A committed test or a recorded run, named in
   the lift's pull request, shows `confined` and the trials step exit 6 on a
   missing record, a record of another job or run, a record not in gate
   mode, and a record with a probe not denied (gate SC4).
5. **The judge is shown to fail a wrong driver on this build.** The four
   committed broken fixtures are recorded failing the case's held-out checks
   with the program run as the seat account (gate SC5).
6. **What is not tested is said.** The credential test gains a probe of
   network access, or the documents say there is none; they say the same of
   reading files every account may read (gate SC6).

The lift itself is then a pull request of its own. It cites this record,
shows the default fingerprint unchanged by the test of gate WF7, merges
outside any batch's freeze (gate WF25), and keeps the condition as built on
e6f96f4: the trials step runs only on this job's own credential record. That
per-job record gates the job; it is an artifact that expires and is not the
evidence. The evidence is the committed record of item 3.

Who disagreed. firmware-engineer asked for the broken fixtures and the
object screen on the single-seat check as conditions of the lift; qa-evidence
asked for a must-fail control only before a count is stated. The chair took
the fixtures as a condition of the lift: they exist already, and a trial
that runs before its judge is shown to fail a wrong driver is weaker
evidence that no later run can strengthen. The object screen is left to
decision 4, which says what must be refused, not which module refuses it.

Owners: security (items 1, 2 and 6), qa-evidence (items 3 and 4),
firmware-engineer (item 5).

### 2. The register block flow stays refused

Confirmed by all four seats. `flow/axi4-lite-regs-driver` stays refused
until gates WF15 to WF19 of the G3 record are met and the dated plan
addition of gate WF24 is committed. Three additions, each before the first
register block trial:

1. Decision 4 applies to it: the compile reach is closed for every check
   that compiles seat C in that flow, the firmware stage's own checks
   included.
2. Gate WF16 is not called met until the `#line` route of fact 9 is tested
   and, if open, closed (eda-tooling).
3. A replay on `main` shows the `rejudge` job's credential test and
   `confined` step on the flow case, which no run has yet (fact 5;
   qa-evidence).

Gate WF18 (the driver and its tests in a process of their own) gains one
line: the nonce does not travel on a command line that the seat account can
read, or a recorded probe shows it cannot read it (firmware-engineer).

### 3. The re-judge job: ratified, and gate WF17 read

Ratified as built in ip#371. The `rejudge` job runs the credential test with
`--require-denied`, then `confined`, before it re-judges a case that runs
seat C, and fails closed. All four seats agreed; the job has no environment
and no token (security).

The reading of gate WF17 that `docs/LIVE_EVAL_EVIDENCE.md` left for security
is confirmed in these words, and is now the council's reading: the job ran
no seat code before the re-judge; the seat code the re-judge itself runs
executes as the seat account, after that job's own reach and credential
tests showed every probe denied, between two hashes of its checkout; seat C
is compiled as the runner. The document drops "for security and the Founder
Proxy to confirm" and cites this record. Until gate SC1 is met it also says
that a re-judge compiles stored seat C the way the trial did, so it cannot
detect an included reference answer (fact 10).

Who disagreed. firmware-engineer would not confirm the reading until the
compile reach is closed. The chair confirmed it now because the wording
claims execution only and states the compile, and because no live record of
a case that runs seat C exists for a re-judge to be wrong about.

Owner: security.

### 4. The compile residual is closed, not stated

No seat accepted the residual on a statement for a live trial. The residual
is wider than ip#371's open item says: it is not only text in a diagnostic,
it is a pass without the work and a file carried into the seat's program
(fact 9).

1. **ip#371 is not held by this.** At f03b2f7 it leaves the live refusal
   unchanged, compiles only reference answers and stored replays, and only
   tightens. All four seats said it may merge. It cites this record where it
   speaks of the re-judge and of the lift, and its texts keep saying that
   seat C is built as the runner.
2. **Before any live trial of a case that compiles seat C**, the single-seat
   case included, one of two measures is merged, and the pull request says
   which:
   - a screen, before anything of the seat's is compiled: every file the
     seat's C pulls in resolves inside the run's source folders, the harness
     copy, the generated map folder or the compiler's own include folders;
     asm and `#line` in seat text are refused; a hit is a recorded failed
     check with its reason and nothing compiled; or
   - every compile step whose input holds seat text runs as the seat
     account, and a recorded reach test shows that account cannot read the
     reference answer, the held-out test or a runner-only canary file. The
     link step may stay with the runner: it takes objects only, and the
     wrapper requires a program the runner built (firmware-engineer).
3. **The measure is claimed only for what a recorded must-refuse fixture
   shows it stops**, as the G3 second addendum rules for the object screen.
   Recorded in CI: an include by absolute path, an include with `..`, the
   assembler route, a `#line` line, and a run with a runner-only canary in
   which the canary appears in no log, excerpt or record. Whether a fixture
   that reaches for a credential is committed to a public repository is
   security's choice in that pull request; a canary stands in for it.
4. **Where it sits and the fingerprint.** It changes no file in
   `harness.CODE` and no tool definition, shows the default fingerprint
   unchanged by the test of gate WF7, and merges outside a batch's freeze
   (gate WF25). If it sits in the shared `fw.build` and `fw.test` backends,
   its pull request shows by a recorded run that every committed fixture,
   reference answer and held-out test gets the result it got before, and
   says in `docs/GATE_INTEGRITY.md` that the gate changed without a
   fingerprint change.
5. **For the register block**, before its first trial: the compile of seat
   text runs as the seat account, or security records its reason for staying
   with the screen, in the pull request that closes gate WF17.
6. **Until item 2 is met** the documents state the residual as fact 9 gives
   it, with each inference labelled, in `docs/GATE_INTEGRITY.md` and
   `docs/LIVE_EVAL_EVIDENCE.md`.

Who disagreed. firmware-engineer required the compile as the seat account
before the single-seat lift. eda-tooling held that the screen is the smaller
change, and that the account alone does not stop an include of a file it can
read (fact 9, assumption). Security accepted either. The chair left the
choice to the pull request on the test of item 3: what counts is the
recorded refusal of each route, and the account is required, or reasoned
against on the record, before the register block, where the count is the
one the G3 record guards.

Owners: security (the measure, its conditions and the choice of item 5);
eda-tooling (the build and the screen); firmware-engineer (the fixtures).

### 5. What may and may not be said

May be said, once the named run or record supports it: that the program
`fw.test` builds executes as `nirmaan-seat` in the live evaluation jobs;
that in a named run the listed probes were denied; that the credential test
is a gate since M90; the run ids of fact 5 as replays on a branch.

Never said, in a document, a record, a pull request or a read:

- that seat C is confined, sandboxed or isolated, or "built and run as
  another account", while it is compiled as the runner. The mode name
  `confined` stays a name; prose says "executes as the seat account";
- "every probe denied" as a standing result before the record of gate SC3
  is on `main`;
- that the plan credential is safe from seat C, or anything about network
  access or readable files, beyond what a recorded probe shows;
- that the re-judge gate was shown on the flow case, before a run shows it;
- a pass rate, a level or a count for `firmware/axi4-lite-driver` from live
  trials without the case, its two held-out checks, the absence of a mutant
  and the control of gate SC5 stated beside it; and nothing more than host
  co-simulation on Verilator against the reference RTL;
- the orchestrator's private decision numbers as a source. Code, documents
  and history files cite this record.

Owner: qa-evidence.

## Positions not adopted, and dissent

- firmware-engineer: compile as the seat account before the single-seat
  lift. Not adopted in the letter (decision 4, items 2 and 5). Recorded as
  dissent.
- firmware-engineer: no confirmation of the WF17 reading until the compile
  reach is closed. Not adopted (decision 3). Recorded as dissent.
- eda-tooling: ratify the lift with conditions now. Adopted in substance:
  its conditions are gates SC1 to SC3; the ruling's words are "not ratified
  as it stands" because three seats refused and none of the conditions is
  met today.
- qa-evidence: a must-fail control only before a count is stated. The chair
  required it before the first live trial (decision 1, item 5).
- qa-evidence: the five required checks green on the head and run
  44486616543 concluded, before anything rests on that head. Both were true
  when the chair decided (fact 5); that is a statement about f03b2f7 only.
- Open, for security: the fixture question of decision 4, item 3.
- Open, for eda-tooling: whether the seat account can read the checkout
  (fact 9). The reach test of gate SC1 or the pull request for decision 4,
  item 5 answers it; nobody guesses.

No seat dissented from keeping the flow case refused, from the re-judge
gate, from letting ip#371 merge with the refusal unchanged, or from closing
the compile reach before any live trial of seat C.

## Gates

Each is met before the pull request that lifts the single-seat refusal
merges, unless it says otherwise.

| Gate | Condition | Owner seat |
|---|---|---|
| SC1 | The compile reach is closed for every case that compiles seat C (decision 4, items 2 to 4): the screen or the seat-account compile is merged; an absolute include, a `..` include, the assembler route and a `#line` line are recorded refused in CI; a canary run shows the canary in no log, excerpt or record; the default fingerprint is shown unchanged | security |
| SC2 | A live trial of a case that runs seat C stops unless each of its `fw.test` runs started through the wrapper (decision 1, item 2), shown by a test | security |
| SC3 | `evals/flow/credential_test_record.json` on `main` is from a replay dispatched on `main` at or after the merge commit of ip#371, holds the replay job's and the `rejudge` job's results in gate mode with every probe denied, and reached `main` in a pull request that changes no code it grades | qa-evidence |
| SC4 | A committed test or recorded run, named in the lift's pull request, shows exit 6 from `confined` and from the trials step on a missing, foreign, non-gate or not-denied record | qa-evidence |
| SC5 | The four committed broken fixtures of the block are recorded failing the single-seat case's held-out checks, with the program run as the seat account, on the build the trials will use | firmware-engineer |
| SC6 | The credential test probes network access, or the documents say it does not; the documents say that reading files every account may read is not probed | security |
| SC7 | The lift is its own pull request: it cites this record, keeps the same-job record condition, changes no fingerprint, and merges outside any batch's freeze (gate WF25). The flow case is not in it | eda-tooling |
| SC8 | Every text follows decision 5; the documents carry the residual of decision 4, item 6 until SC1 is met, and the WF17 reading of decision 3 in its words. Checked on ip#371 and on every pull request named here | qa-evidence |
| SC9 | Before the first register block trial, with gates WF15 to WF19 and WF24: the three additions of decision 2, the line added to gate WF18, and the choice of decision 4, item 5 | security |

Code these gates need, for the build lane (this meeting wrote none): the
screen or the seat-account compile with its fixtures and canary run (SC1);
the wrapper check in the trials step or the refusal in `seat_run` (SC2); the
replay on `main` and its record (SC3); the negative tests if they are not
already committed (SC4); the recorded run of the broken fixtures (SC5); the
network probe or the sentence (SC6); the lift (SC7); the document texts
(SC8); the `#line` test for the object screen and the flow-case replay
(SC9).

## Open, for the founder

1. This ruling, to confirm or overrule.

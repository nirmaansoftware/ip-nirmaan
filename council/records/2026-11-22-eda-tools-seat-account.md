# Council record: the runner-account tools on the timer path (2026-11-22)

The plan of the whole-flow batch (`evals/plans/2026-11-22-g3-whole-flow.md`,
section 14, ip#430) records the security seat's second reach question on the
timer path (`flow/axil-timer`): the tools that run over seat files as the
runner account (the Icarus compile, Verilator's lint, Yosys, and SBY if it
runs) do so in the job step whose parent process holds the plan credential;
the only control is the input screen `eda_guard` (M84, M85); and no recorded
probe covers them. Security named two ways to settle it: those tools run as
the seat account with a recorded reach test, or a council ruling names the
screen as the control. This meeting chose between them.

Ruling, in short:

- **The screen is not named as the control.** During the meeting three seats,
  each alone, and then the chair, found on a local machine that the screen
  passes seat Verilog which a tool then acts on by opening a file outside the
  run. A ruling that named the screen would name a control shown not to hold.
- **The seat account is the control (security's first way).** Before slot 1,
  every tool step of the timer path that reads seat-written Verilog runs as
  `nirmaan-seat` in the live evaluation's jobs, with reach probes through
  each such tool recorded, as gates ET2 to ET4 say. For the Icarus compile of
  the held-out checks, where the judge's files are compiled with the seat's,
  the account is given that run's own inputs and nothing else; a named
  fallback exists only on a shown build obstacle (decision 3).
- **The screen is repaired whatever the route.** The two classes of
  difference found are closed in `eda_guard`, with a must-refuse fixture and
  a bypass control per tool, before slot 1 (gate ET1). The screen stays in
  force as the first check on every machine; it is claimed only for what its
  recorded fixtures show refused.
- **Slot 1 still waits.** The question of the plan's section 14 is settled
  as to the way. The condition before slot 1 is met only when gates ET1 to
  ET8 are met on `main`.

Five seats gave round 1 positions independently, each as its own read-only
process that saw no other position (security, eda-tooling, qa-evidence,
ai-engineer, verification-lead); the chair decided. The meeting was kept to
the seats that own the account and gates WF9, WF17 and WF23 (security), the
tools, the job and the screen (eda-tooling), the claims and the evidence
(qa-evidence), the harness, the fingerprint and the freeze of gate WF25
(ai-engineer), and the plan, the counts and the read (verification-lead).
The precedent for a meeting kept to the owning seats is
`council/records/2026-11-19-seat-c-live-refusal.md`. Read against ip-nirmaan
`main` at 0dd7654b. Security, eda-tooling and qa-evidence ran small
experiments on a local machine, outside the repository; the chair repeated
two of them. No trial ran, no workflow was dispatched, and this record
changes no code, case, eval record, level, fingerprint or digest. Code it
needs is listed as gates and as a build specification.

A key is an agent review. Nothing here is a person's approval, a release, or
a claim that a design is ready to be made in silicon.

## Who decided what

The council decided every item below. The orchestrator called the meeting
because the plan's section 14 leaves this question to be settled in one of
two ways and one of them is a council ruling. It is not a founder decision,
and the founder can overrule it. No seat found anything reserved for the
founder in the ruling as made: it adds no spending, contract, counsel,
sending, public name or licence term, and it loosens no gate. Security said
that running slot 1 on the screen alone would be the founder's matter, since
it would accept a risk on the owner's credential; the council did not choose
that. A pull request that changes what a gate refuses, or a control file, is
in a founder class and goes to the Founder Proxy (agent) by the usual rule.

The first reach question of section 14 (a seat that declares a
`formal_spec`) was not on the agenda. It is being settled by a test in
another lane. Every decision below is written to hold for both results of
that test.

## Facts checked

The chair checked each line below at 0dd7654b unless a seat is named as the
source. "Local run" marks what was run on a local machine (macOS, Icarus
Verilog 13.0, Verilator 5.052, Yosys 0.69) and is not recorded evidence.
"Inference" marks what nobody ran.

1. Where the credential is. The `live-eval` job gives
   `CLAUDE_CODE_OAUTH_TOKEN` to the gate step and the trials step only
   (`.github/workflows/live-eval.yml:210-213`, `:249-254`). A tool run's own
   environment holds no credential-named variable
   (`src/nirmaan/integrations/eda.py:104`, `:418-424`, `:290`, `:597-608`).
   So the token is not in the environment of `iverilog`, `verilator`,
   `yosys` or `sby`.
2. The tools run as the runner user, as does the `nirmaan` process that
   holds the token, and a process of that user can read the other's
   `/proc/<pid>/environ` (`docs/LIVE_EVAL_EVIDENCE.md`, section 6). The seat
   C record's fact 3 names a committed record in which seat C, then run as
   the runner, read the parent's environment with a credential-named canary
   in it.
3. Inference: the token is reached from a runner-account tool only if a seat
   file makes the tool run code the seat chose, or read a file the seat
   named and print it. The M53 redaction replaces only the exact value of a
   credential-named variable (seat C record, fact 9). No seat tried to read
   a credential, and nothing here shows one read.
4. Where printed text goes. At the RTL stage a failed run's summary and a
   bounded log excerpt return to the seat on a retry (plan, section 12); a
   refusal's reason returns too (ai-engineer;
   `src/nirmaan/runtime/context.py:255-262`). The records are uploaded as an
   artifact and reach this public repository by pull request (plan, section
   3). The seat model has no tools and no MCP server
   (`src/nirmaan/runtime/harness.py:145-146`,
   `src/nirmaan/runtime/claude_code.py:143`); it chooses each file's path,
   kind and content (ai-engineer; `src/nirmaan/runtime/model.py:429-460`).
5. What runs on the timer path. RTL stage gates: `lint.run`,
   `simulator.run`, `synth.run`, and `formal.run` with `formal.cover` when a
   `formal_spec` was produced (`src/nirmaan/company/workflows.py:622-640`,
   `:95-98`). Steps: `verilator --lint-only` (`eda.py:678-679`); `iverilog`
   then `vvp` (`eda.py:687-690`); `yosys -s synth.ys`, a script the harness
   writes (`eda.py:864-869`); `sby` (`eda.py:894` on). At that stage the
   inputs are the seat's own files.
6. The held-out checks run after the last stage and return nothing to a
   seat. Check 1 hands `simulator.run` the seat's RTL with the held-out
   testbench by its path in the checkout
   (`src/nirmaan/evals/scorers.py:91-92`); check 2 stages copies of the
   reference RTL and of each mutant in the sandbox's judge folder
   (`scorers.py:130-145`, `src/nirmaan/evals/flow.py:228-229`;
   verification-lead). So each Icarus compile there holds seat text and the
   judge's files together.
7. Only `vvp` runs as `nirmaan-seat`: `WRAPPED = ("vvp",)`
   (`scripts/live_eval_seat.py:73`), a wrapper first on `PATH`. The account
   is granted the run's own directory only (`:201-205`), under
   `/tmp/nirmaan-*` (`:78-79`), and is denied read of the runner's home, the
   checkout and the runner's temporary folder
   (`.github/actions/live-eval-seat/action.yml:22`). The whole-flow sandbox
   is a `nirmaan-flow-` folder of the temporary folder
   (`src/nirmaan/evals/flow.py:166`), which the action sets to `/tmp`
   (`action.yml:24`). Sources reach a tool by absolute path (`eda.py:253`).
8. The screen. `eda.execute` calls `check_inputs` for every backend before
   any step (`eda.py:279`). It reads each file with regular expressions of
   its own (`src/nirmaan/integrations/eda_guard.py:118-119`, `:132-151`),
   not with a tool's parser. It screens input and does not confine a run
   (`eda_guard.py:12-17`).
9. The screen passes files a tool then acts on. Local run, by security,
   eda-tooling and qa-evidence separately, and repeated by the chair for
   Icarus and Yosys. Two classes:
   - what the screen takes for a comment or a string, a tool does not: the
     screen pairs quotes and comment marks by its own pattern, and the tools
     decide differently in some cases, so an include or a file-reading
     system task that the screen skips as comment or string text is live
     text to the tool;
   - a system task name the preprocessor assembles: the screen looks for a
     `$` followed by a name, and a name supplied by a macro after a bare `$`
     is not one to the screen and is one to the tool.

   With files that `check_inputs` passed: the Icarus preprocessor included a
   file outside the run by absolute path (security; the chair repeated it);
   Yosys opened a file outside the run while elaborating, where a missing
   file was an error and a present one changed the result (eda-tooling,
   qa-evidence, security; the chair repeated it); Verilator's lint read an
   included file outside the run and echoed a line of it (eda-tooling);
   through `eda.execute`, `simulator.run` on Icarus compiled a stand-in
   "judge" file in and the simulation printed its value, and `synth.run`
   read one (security). Controls: the plain forms of the same constructs
   were refused. Not run: any of this on Linux, in CI, or against a
   process's `environ` file. The exact files are kept outside the
   repository until the repair of gate ET1 merges with them as its
   fixtures; this record names the classes only, at security's and
   eda-tooling's request.
10. Inference (eda-tooling): the same two classes hide `$system`, `$fopen`
    and `$c` from the screen on every backend that builds or runs seat HDL,
    the runner-account Verilator simulator build included. Not run.
11. What is recorded about the screen today (qa-evidence, eda-tooling,
    verification-lead agree). Through `simulator.run` on the icarus and
    verilator-sim backends: seven constructs refused, with a marker file and
    one bypass control (`tests/test_gate_inputs.py:109-136`). Of `lint.run`
    and `synth.run`: only a `top` that is not a name, with one bypass
    control for `top` through `synth.run` (`tests/test_gate_inputs.py:61-79`,
    which also covers `simulator.run` and `dft.check`), and, for lint, an
    include linked out of the run (`tests/test_gate_reads.py:287-297`, which
    also covers `simulator.run` and the formal gates). No Verilog construct
    is recorded refused through `lint.run` or `synth.run`; no test shows
    what Icarus's compile, Verilator's lint or Yosys under `synth.run` do
    with a Verilog construct when the check is bypassed; through a gate,
    `$readmemh` is recorded for eqy only
    (`tests/test_gate_reads.py:179-190`; the screen's own function is tested
    on it directly, `tests/test_gate_inputs.py:192`). All are tests of CI's
    test job. No
    recorded run in the `replay`, `live-eval` or `rejudge` job probes a
    runner-account tool; the reach test goes through cocotb inside `vvp`
    only.
12. A refusal by the screen is already a failed check decided in advance
    (verification-lead): nothing runs and the run is recorded failed
    (`eda.py:279-281`); the held-out scorers score a refused run failed and
    never count a refused mutant as caught (`src/nirmaan/evals/scorers.py`);
    a trial passes only if every score passed
    (`src/nirmaan/evals/flow.py:245`).
13. What each route touches (ai-engineer). Neither needs a file in
    `harness.CODE`, `LOOP_CODE` or `FLOW_CODE`
    (`src/nirmaan/runtime/harness.py:258-294`) or a tool definition, so
    neither need change a fingerprint (inference; the test of gate WF7 shows
    it). `scripts/live_eval_seat.py` is the plan's "Seat account" group and
    `src/nirmaan/integrations` its "Gate backends" group (plan, section 6);
    a moved group digest stops every dispatch until a plan amendment merges
    (plan, section 7). `scripts/live_eval_reach.py`,
    `src/nirmaan/evals/scorers.py` and `src/nirmaan/company/workflows.py`
    are in no fingerprint and no group. `src/nirmaan/evals/runner.py` is in
    `harness.CODE`: an edit there changes the default fingerprint and makes
    wave 2's groups stale. The wrapper acts through `PATH` for every case
    run in those jobs, so wrapping more tools changes how single-seat
    trials' gates run too, with no fingerprint change. A re-judge replays
    recorded answers through the gates as they are, so a stricter screen can
    turn an earlier record's answer into a refusal on a later re-judge.
14. Not built, and nobody guesses (security, eda-tooling): whether the seat
    account can run each tool from the job's tool install, and how the
    account is given a held-out run's inputs without the rest of the
    checkout. `vvp` from the same install already runs as the account.
15. The plan's section 12 says of the screen: "so a testbench cannot print a
    host file into the log". By fact 9 that sentence is not supported
    (security, qa-evidence).

## Decisions

### 1. The screen is not named as the control

Security, eda-tooling and qa-evidence would not name the screen as it
stands: each had a file that passed it and that a tool then acted on.
ai-engineer and verification-lead chose the screen in round 1, and each said
what would move it: ai-engineer, a tool shown acting on a construct the
screen passed; verification-lead, at the RTL stage, an account route built
without a harness code change and shown not to change a result. The chair
reads ai-engineer's condition as met by fact 9, and takes
verification-lead's as a gate (ET5).

Why. The rule the G3 record weighs against is that what a seat writes must
not reach anything the judge does not intend it to reach. The screen is a
check of text by patterns; the tools read the text by their own rules; fact
9 shows the two differ, and a repair of the two classes found does not show
that no third exists. The seat C record's test (decision 4, item 3) is that
a measure is claimed only for what a recorded must-refuse fixture shows it
stops. By that test the screen can be claimed for its fixtures and for
nothing beyond them, which is not enough to be the one control between a
seat file and the account that holds the credential's parent process.

### 2. At the RTL stage the tools run as the seat account

Before slot 1, in the `replay`, `live-eval` and `rejudge` jobs, each step of
the timer's RTL stage that reads seat-written Verilog runs as `nirmaan-seat`:
`verilator --lint-only`, `iverilog`, `yosys`, and `sby` if the other lane's
test shows the formal gates can run on the timer path (then Yosys under SBY
and the solvers inherit the account). `vvp` already does. The account's
grants are that run's own directory and that run's own input files, and
nothing else; its environment holds no credential; when the run ends every
grant is taken back, as for `vvp` today.

Conditions, each a gate:

1. **No silent fallback** in those jobs, as gate SC2 rules for `fw.test`: a
   wrapper that is missing, not root's, or writable by another account stops
   the run before the tool starts (ET2).
2. **Reach probes through each wrapped tool**, by `PATH`, through the real
   backend, in `scripts/live_eval_reach.py`: that the tool's process is the
   seat account; that a canary file in the checkout, a runner-only canary
   file and a credential-named canary in the parent's environment are denied
   to it; and that no canary value is in the run's log, summary or record.
   Each target exists first, so a denial proves something. The job stops
   before any trial unless every probe is denied (ET3).
3. **Recorded where it counts.** A replay dispatched on `main`, on the
   merged head, records those probes denied in the `replay` and `rejudge`
   jobs. The `live-eval` job runs the same probes as a gate before its first
   trial. The `live-eval` job's first recorded probe run is the measured run
   of the plan's section 10; its reach records are committed before slot 1
   (gate ET10). Nobody says the `live-eval` job has a recorded probe run
   beyond a committed record that names the run and its commit (ET3).
   (Amended 2026-11-23 by the addendum, decision A2. It read: "Nobody says
   the `live-eval` job has a recorded run before slot 1: it has none until
   slot 1 (qa-evidence)".)
4. **No harness change.** No file in `harness.CODE`, `LOOP_CODE` or
   `FLOW_CODE` and no tool definition changes, shown by the test of gate WF7
   and by recomputing the four fingerprints of the plan's section 4 on the
   merge commit. If it cannot be built so, it returns to the council before
   it merges (ET7).
5. **No result changes.** A replay of `flow/axil-timer` on `main` shows the
   reference answer passing every gate and both held-out checks with the
   tools run as the seat account; the timer's mutant sweep and controls give
   the results they gave; every committed fixture still passes (ET5).

Who disagreed. eda-tooling and qa-evidence asked for exactly this at the RTL
stage. Security asked for it everywhere (decision 3). ai-engineer and
verification-lead chose the screen in round 1; see decision 1.

Owners: security (the account, the probes, the conditions); eda-tooling (the
build and the job); verification-lead (item 5); ai-engineer (item 4).

### 3. The held-out checks' compile: the account, given that run's inputs only

This is where the seats differed most. The compile holds the seat's file and
the judge's (fact 6), and the account must not read the judge's files in
general (fact 7).

- Security: the account there too, given only that run's own inputs, never
  the whole checkout.
- eda-tooling, qa-evidence and verification-lead: the repaired screen as the
  control for this step, on the reasoning of `docs/COMPILE_SCREEN.md` (a
  compile that holds the judge's file cannot run as an account that may not
  read it).

The chair decided for the account, with a fallback, for three reasons.
First, fact 9 was shown on Icarus's own preprocessor, the tool of this step,
so eda-tooling's ground for the screen there, that it found no
compile-time read in that tool, does not hold. Second, the
reasoning of `docs/COMPILE_SCREEN.md` is about an account that is denied the
judge's file while the step needs it; an account granted the files of one
run, for the length of that run, reads in that step nothing the compile does
not already put beside the seat's text, and is denied the reference RTL in
check 1, the other mutants, the checkout and the environment of the
credential's parent. Third, a miss here is a pass without the work
(verification-lead: a screen miss on an include could make the seat's files
the reference answer, with no channel back needed), which is the count the
G3 record guards.

So, before slot 1:

1. The Icarus compile of each held-out check runs as the seat account,
   granted only the input files of that run (ET4). Where a check hands the
   tool a file in the checkout (check 1), the file is staged for the run as
   check 2's files already are, or granted singly; the build chooses,
   without widening the account's read of the checkout.
2. A probe in the reach test shows, through that path, that the account can
   read the run's own judge file and cannot read a second canary file placed
   beside where the judge's files live (ET4).
3. **The fallback.** Only if the build shows that item 1 needs a file in
   `harness.CODE` or a tool definition, or cannot be done without giving the
   account more than the run's own inputs, the step may stay with the
   runner on two conditions: the repaired screen of decision 4, and a check
   of the list of files the tool itself read (asked of the tool, as M91's
   compile screen asks the compiler), refusing any file outside the run's
   inputs, with a recorded canary run. The pull request says which was
   built, and security records its reason there, as the seat C record's
   decision 4, item 5 does for the register block. The regular expression
   screen alone is not accepted for this step.

Owners: security (the choice and its conditions); eda-tooling (the build);
verification-lead (that both held-out checks still judge what they judged).

### 4. The screen is repaired whatever the route

All five seats asked for this. M84 and M85 claim the screen for every gate
on every machine, and most runs of this product are not in the live
evaluation's jobs.

1. `eda_guard` refuses both classes of fact 9. A repair by rule, not by
   example, is wanted: eda-tooling proposed refusing every escaped
   identifier and a `$` followed by a backtick; the pull request may choose
   a stricter or a different rule if every fixture below is refused.
2. Each file of fact 9 becomes a must-refuse fixture, through `lint.run`,
   `simulator.run` (icarus and verilator-sim) and `synth.run`, and through
   `formal.run` and `formal.cover` if the other lane's test shows they can
   run on the timer path. Each has a bypass control that shows what the tool
   does with the check removed, so the payload is shown live. A fixture
   reaches for a canary file, never for a credential. Recorded in CI's test
   job, in its JUnit file, with the run named and no test skipped.
3. Fixtures also show refused, through each of those gates, a seat file that
   reaches for the reference RTL, the held-out testbench and a mutant
   (verification-lead).
4. Every committed Verilog file still passes the screen, the timer's mutant
   sweep and controls give the results they gave, and the pull request lists
   any committed trial whose re-judge would now be a refusal (fact 13). It
   says in `docs/GATE_INTEGRITY.md` that the gate changed without a
   fingerprint change.
5. The fix and its fixtures land in one pull request, and the documents
   describe the classes in full from that merge on.

Owner: eda-tooling (gate ET1), with security's checklist in its key 1.

### 5. SBY and the formal gates

If the other lane's test shows that a timer seat can make `formal.run` and
`formal.cover` run: `sby` is wrapped under decision 2 before slot 1, with
its probes; decision 4's fixtures run through both gates; and the plan's
section 12 is corrected by the amendment of gate ET6. If the test shows they
cannot run: that test is the record, it stays in CI through the freeze, and
no document claims anything for SBY on the timer path. If the way they are
stopped is a change to a file in `harness.CODE`, it returns to the council
before it merges (ai-engineer).

The result, as far as it is known. After round 1 the other lane opened
ip#435 (open when this was written, so not yet on `main`). Its test,
`tests/test_whole_flow_reach.py`, replays the timer flow with a seat `.sby`
declared as a `formal_spec`, and its pull request reports that the RTL stage
then runs `formal.run` and `formal.cover` over the seat's setup and that a
failed formal run's log excerpt returns to the seat on a retry. If that test
merges with that result, the first branch above applies and every "if" on
the formal gates in decisions 2 and 4 and in gates ET1 to ET3 is met: `sby`
is wrapped, so SBY, Yosys under it and the solver run as the seat account
over the seat's `.sby`, with their probes and fixtures, before slot 1. The
build lane reads the test on `main`, not this paragraph.

Owners: security (the wrapping and its probes); eda-tooling (the fixtures);
qa-evidence (that no document claims anything for SBY if it cannot run, with
gate ET8).

### 6. Scope: the timer, with two things that reach further

This ruling is for the timer flow before slot 1. Two parts reach further by
their nature, and the pull requests say so:

- the screen repair is one function, in force for every gate and every case
  (decision 4);
- the wrappers act through `PATH` for every case run in the live
  evaluation's jobs (fact 13), so single-seat trials' gates run as the seat
  account too from that merge, with no fingerprint change.
  `docs/GATE_INTEGRITY.md` and `docs/LIVE_EVAL_EVIDENCE.md` say so.

For the register block flow nothing is decided here beyond those two. Its
Verilator model builds of seat HDL (`regmap.verify`, the `fw.test`
co-simulation build, the Verilator simulator build) are the same class
(security; fact 10), stay with the runner today, and return to security
before slot 21 with gates WF15 to WF19 and SC9 (gate ET9). Wrapping
`verilator` by name must not change those builds silently: the build either
runs them as the account, with replays that show every committed result
unchanged, or leaves them with the runner by a stated, tested rule.

Owners: security (gate ET9 and the rule for the other builds); eda-tooling
(the build).

### 7. The plan, the digests and the freeze

1. This record's pull request adds a dated section to the plan that names
   this record and says what slot 1 now waits for. It changes nothing in
   sections 1 to 11.
2. The build moves the "Seat account" and "Gate backends" group digests. One
   plan amendment, merged before slot 1, restates section 6 with the pull
   request that moved each value, corrects section 12 (fact 15; and the
   formal sentence if decision 5 requires), and states: that a screen
   refusal, or a tool denied as the seat account, is a failed run, and a
   trial that ends on it is a failed trial, never removed or repeated; that
   the timer's read lists, for each passed trial, whether a seat HDL file
   holds an include, changing no count (verification-lead); and which of
   `scripts/live_eval_reach.py`, `src/nirmaan/evals/scorers.py` and
   `src/nirmaan/company/workflows.py` the plan pins, or that it does not
   pin them (ai-engineer) (ET6).
3. Every pin is recomputed on the dispatch commit; the measured run of the
   plan's section 10 is made after the last of these merges (ET7).
4. All of it merges before slot 1. From slot 1 the freeze of gate WF25
   holds, and none of it may merge until the timer's last trial is recorded.

Owners: verification-lead (the plan and its amendment); ai-engineer (the
digests, the fingerprints and the freeze).

### 8. What may and may not be said

May be said, once the named test or run supports it: that the screen
refuses, before any step, the constructs its recorded fixtures name; that in
a named run the listed probes were denied to the seat account through the
named tools; that the named tool steps run as `nirmaan-seat` in the live
evaluation's jobs.

Never said, in a document, a record, a pull request or a read:

- that seat files are confined, sandboxed or isolated, that the screen is
  enough, that "no seat file can" do a thing, or that the credential is
  safe, beyond what a recorded probe shows;
- that the screen stops reads or code in general, matches a tool's
  preprocessor, or covers a fault in a tool's parser;
- anything about files every account may read, beyond the probed targets;
- that a credential was read, or could not be: neither was shown (fact 3);
- the local runs of fact 9 as recorded evidence; they are the reason for the
  ruling and are replaced by the fixtures of gate ET1;
- that the `live-eval` job has a recorded probe run, beyond a committed
  record that names the run and its commit; or that one run's reach record
  covers another run, another commit or a slot (amended 2026-11-23 by the
  addendum, decision A2; it read: "that the `live-eval` job has a recorded
  probe run, before slot 1");
- the orchestrator's private decision numbers as a source.

Until gate ET1 merges, `docs/GATE_INPUTS.md` keeps its text and this record
is the statement of the gap; with ET1 the document states the two classes,
the fixtures and the residual above.

Owner: qa-evidence.

## Positions not adopted, and dissent

- ai-engineer: the screen as the control for the timer. Not adopted (decision 1); its own
  condition for changing was met in the meeting. Its facts on files, groups
  and fingerprints are adopted whole (fact 13, decision 7).
- verification-lead: the screen as the control, firm for the held-out
  checks. Not adopted for
  the held-out checks (decision 3). Recorded as dissent. Its condition for
  the RTL stage is gate ET5, and its requirements for the plan and the
  fixtures are adopted (decisions 4 and 7).
- eda-tooling and qa-evidence: the repaired screen as the control for the
  held-out Icarus compile. Not adopted as the first choice; kept, with the
  tool's own file list added, as the fallback (decision 3). Recorded as
  dissent on that step.
- security: the account for every tool, including the held-out compile.
  Adopted, with the fallback of decision 3, item 3, which security named
  itself as the one thing that would change its answer.
- qa-evidence: the screen alone if the preprocessed text can be screened by
  asking the tool. Not taken as the route; it is the shape of the fallback.
- Open, for security and eda-tooling: fact 14. The build answers it; nobody
  guesses.
- Open, for security: live trials of other cases run today through the same
  runner-account tools and the same screen (fact 13). This meeting's
  question was the timer. Security states, in the pull request of gate ET1
  or before it, whether any live batch should wait for that gate; a refusal
  of live trials is a change to a gate and would come back here.

No seat dissented from repairing the screen before slot 1, from the reach
probes, from keeping slot 1 waiting, or from the plan amendment.

## Gates

Each is met on `main` before the timer's slot 1 unless it says otherwise.

| Gate | Condition | Owner seat |
|---|---|---|
| ET1 | The screen repair of decision 4: both classes of fact 9 refused; a must-refuse fixture and a bypass control per tool through `lint.run`, `simulator.run` and `synth.run` (and the formal gates if they can run), with the judge-file fixtures of item 3; recorded in CI's test job, none skipped; every committed Verilog file still passes; committed trials whose re-judge would change are listed; the default fingerprint is shown unchanged | eda-tooling |
| ET2 | In the `replay`, `live-eval` and `rejudge` jobs the RTL stage's `verilator --lint-only`, `iverilog` and `yosys` steps (and `sby` if it can run) run as `nirmaan-seat`, granted the run's own directory and input files only, with no fallback to the runner, shown by tests | security |
| ET3 | The reach test probes each wrapped tool through the real backend (decision 2, item 2); a replay on `main` on the merged head records every probe denied in the `replay` and `rejudge` jobs; the `live-eval` job runs them as a gate before any trial | security |
| ET4 | The held-out checks' Icarus compile runs as the seat account with that run's inputs only, with the probe of decision 3, item 2; or the fallback of decision 3, item 3 is built, with the obstacle shown and security's reason recorded in the pull request | security |
| ET5 | A replay of `flow/axil-timer` on `main` shows the reference answer passing every gate and both held-out checks with the tools as the seat account; the timer's mutant sweep and controls and every committed fixture give the results they gave | verification-lead |
| ET6 | The plan amendment of decision 7, item 2 is merged: section 6 restated, section 12 corrected, the failed-run rule, the include listing at the read, and what is pinned | verification-lead |
| ET7 | No file in `harness.CODE`, `LOOP_CODE` or `FLOW_CODE` and no tool definition changed by any of the above, shown by the test of gate WF7 and the four fingerprints recomputed on each merge commit; every pin recomputed on the dispatch commit; the measured run made after the last merge. Otherwise it returns to the council | ai-engineer |
| ET8 | Every text follows decision 8; `docs/GATE_INPUTS.md`, `docs/GATE_INTEGRITY.md` and `docs/LIVE_EVAL_EVIDENCE.md` state the classes, the fixtures, the account's scope and the residual from the merge of ET1 and ET2 on | qa-evidence |
| ET9 | Before slot 21, with gates WF15 to WF19 and SC9: the register block flow's builds of seat HDL into a Verilator model run as the seat account, or security records its reason and conditions for another control | security |

## Build specification, for the build lane

This meeting wrote no code. Two code pull requests are wanted, the first
small and first, then the plan amendment.

**A. The screen repair (gate ET1).** In
`src/nirmaan/integrations/eda_guard.py` only, with tests in
`tests/test_gate_inputs.py` and `tests/test_gate_reads.py` and fixtures
under `tests/fixtures/`. The files of fact 9 are handed to the build lane
outside the repository and become the fixtures. Requirements: decision 4,
items 1 to 5. It moves the "Gate backends" digest and no fingerprint.

**B. The tools as the seat account (gates ET2 to ET5).**

1. `scripts/live_eval_seat.py`: wrap `iverilog`, `verilator` and `yosys` by
   name beside `vvp` (and `sby` if decision 5 requires). Each wrapper runs
   the real program as `nirmaan-seat` with `no_new_privs`, an environment
   holding no credential and only what the tool needs, write access to the
   run's own directory, and read access to the input files named for that
   run and to nothing else outside the tool's own install; every grant is
   taken back and every seat process killed when the run ends, as for `vvp`.
   The root helper takes its arguments from the runner: it refuses an input
   that is not a regular file inside a run or sandbox folder the runner made
   under the temporary folder, reached through no link. What the tool wrote
   goes back to the runner as today, links and other non-regular files
   removed.
2. Other uses of the same names (the Verilator simulator build, the
   co-simulation builds of `fw.test` and `regmap.verify`): decision 6. No
   committed replay may change its result.
3. No fallback in the live evaluation's jobs (decision 2, item 1).
4. The held-out compile: decision 3. `src/nirmaan/evals/scorers.py` is in no
   fingerprint and no pinned group (fact 13); `src/nirmaan/evals/runner.py`
   is in `harness.CODE` and is not touched.
5. `scripts/live_eval_reach.py`: the probes of decision 2, item 2 and
   decision 3, item 2, added to the step the workflow already runs. A probe
   that needs a refused construct reaches the tool with the screen bypassed
   inside the probe only, and says so in its output.
6. Tests: `tests/test_live_eval_seat.py` and `tests/test_live_eval_ci.py`
   for the wrappers' refusals, the grants and the no-fallback rule.
7. Records: the replay on `main` of decision 2, item 3 and of gate ET5, each
   run named in the pull request that cites it.
8. Documents: `docs/LIVE_EVAL_EVIDENCE.md` section 6,
   `docs/GATE_INTEGRITY.md`, `docs/GATE_INPUTS.md`, following decision 8.
9. Then the plan amendment of gate ET6, by itself, changing no code.

Each pull request cites this record, states the fingerprints unchanged with
the recomputed values, and merges before slot 1.

Gates ET10 to ET14 were added on 2026-11-23 by the addendum below.

## Open, for the founder

1. This ruling, to confirm or overrule.

## Addendum (2026-11-23): the tool reach records of the measured run and of each slot

This addendum settles one conflict before the timer's measured run. The
security seat, asked to confirm gate WF23 for the timer flow, confirmed it
and gave must-haves that would commit a tool reach record of the `live-eval`
job before slot 1. Decision 2, item 3 and a bullet of decision 8 above say
that job has no recorded run until slot 1. The plan does not decide between
a seat's must-have and a council record, so the council met.

Ruling, in short:

- **Security's must-haves 1 and 2 are adopted.** Before slot 1 the reach
  records of the measured run's `live-eval` and `rejudge` jobs are committed
  beside the ET3 record, and slot 1 is dispatched only if they show every
  probe denied (gate ET10). Each slot's reach records are committed with its
  record (gate ET11).
- **Decision 2, item 3 and the bullet of decision 8 are reworded** (decision
  A2). The premise "none until slot 1" was wrong when written: the measured
  run is a dispatch of the `live-eval` job, made before slot 1.
- **No write or network probe through each wrapped tool before slot 1.** The
  denials rest on the account, and the six wrapped tools reach the account by
  one code path. Probes through `sby` and `eqy`, the two tools that would act
  on a construct of that kind, are added before slot 21 (gate ET12). Until
  then every text says the write and network denials were probed through
  `vvp` only.
- **A reach record is cited only in the words decision 8 already allows,**
  with its run and commit, and the measured run is never stated as a result
  (decision C).

It changes no code, case, eval record, level, fingerprint or digest, and no
decision above other than the two sentences named. It loosens no gate: it
adds conditions before slot 1. No trial ran and no workflow was dispatched
for the meeting.

### Who decided what

The council decided every item below. The orchestrator called the meeting
because the question lies between a seat's must-have and this record. It is
not a founder decision, and the founder can overrule it. No seat found
anything reserved for the founder in it: it adds no spending, contract,
counsel or sending. One thing touches the founder's ground and is not
decided here: a second measured run, if decision A3 ever asks for one, is a
new dispatch with a model, and this addendum approves no usage.

Five seats gave round 1 positions independently, each as its own read-only
process that saw no other answer to the brief (security, qa-evidence,
ai-engineer, verification-lead, eda-tooling); the chair decided. The brief
quoted security's earlier position and qa-evidence's reads, which are the
question. The seats read ip-nirmaan `main` at d53e8474 and a copy of the
plan file as ip#459 proposes it (head 3d491e95, open when this was written,
so its section 19 is a proposal and not on `main`). The seats had no shell;
nothing was run. The chair rechecked the facts below on `main` at 81bbaefd;
no file named below differs between the two commits.

### Facts checked

F1 to F9 number this addendum's facts; "fact" with a bare number still means
the list above.

- F1. The measured run of the plan's section 10 is one run of the timer
  case with purpose `calibration`, "by the same dispatch as a slot", made
  before slot 1. It never counts and is not stated as a result
  (`evals/plans/2026-11-22-g3-whole-flow.md`, section 10). Decision 7, item
  3 above already names it.
- F2. A dispatch that is not a replay runs the `live-eval` job, then the
  `rejudge` job. Each runs `scripts/live_eval_reach.py` before any trial or
  re-judge (`.github/workflows/live-eval.yml:250-253`, `:363-364`) and
  uploads the tool reach record whether or not the step passed, as
  `live-eval-tool-reach-trials-<run id>` and
  `live-eval-tool-reach-rejudge-<run id>` (`:255-261`, `:366-372`).
- F3. The reach test has two parts (`scripts/live_eval_reach.py:730`). The
  first (`reach`) runs a cocotb module inside `vvp`: identity, sudo, write
  targets, credential canaries, signals, read targets, five network
  targets and a control (`:100-107`). It writes no file: its result is in
  the job's log only (`:506-519`). The second (`tool_reach`) runs only when
  the first passed, and it alone writes the record (`:525-541`, `:710-714`).
  The upload ignores a missing file (`live-eval.yml:261`). So a job whose
  first part failed uploads no tool reach record (inference from the code:
  no such run is recorded).
- F4. The second part probes each other wrapped tool with read probes only:
  a seat file that includes one target by absolute path, and for
  `coverage.read` also a `$fopen` for reading while the model runs
  (`:156-160`, `:562-705`). No write probe and no network probe goes through
  `iverilog`, `verilator`, `yosys`, `sby` or `eqy`.
- F5. The committed ET3 record (`evals/flow/tool_reach_record.json`, ip#452)
  holds the `replay` and `rejudge` jobs of run 45073595509 on `main` at
  c99ef1fe, 19 entries each, every one denied. ip#451 merged afterwards
  (cec29b2f) and changed `scripts/live_eval_seat.py`,
  `.github/actions/live-eval-seat`, `scripts/live_eval_reach.py`, the
  workflow and `src/nirmaan/integrations/eda.py`; the reach test now also
  probes `eqy` and `coverage.read`. The plan names no run of the workflow
  after 45073595509 (plan, section 18.6). So no committed record covers the
  seat-account code as it is now (security).
- F6. How a wrapped tool becomes the account. All six wrapped programs
  (`scripts/live_eval_seat.py:106`) take one path: the wrapper calls `run`
  through `sudo` (`wrap_argv`, `:168-178`), and `run` starts the program
  with `setpriv`, the account's user and group, its other groups cleared,
  `no_new_privs` set and an environment built from nothing (`:551-552`).
  The network rule is an `OUTPUT` rule of `iptables` and `ip6tables` that
  matches the account's user id (`:630-637`). Writes are denied by file
  modes and by ACL entries for the account, which is granted the run's own
  directory only (`:544-548`; `.github/actions/live-eval-seat/action.yml`).
  None of these looks at which program runs (security, eda-tooling,
  verification-lead, each from the code; the chair read the same lines).
- F7. Which tool would act on a seat construct that writes a file or
  reaches the network (eda-tooling). `iverilog` and `verilator --lint-only`:
  none; `$fopen`, `$system` and `$c` act only in `vvp` or in a built model.
  `yosys` under `synth.run`: none; the harness writes the script and the
  seat gives Verilog only. `sby` and `eqy`: yes, through the setup file the
  seat writes: Yosys commands that write a file or run a program, and for
  `sby` a `--pycode-begin--` block. The screen refuses these today
  (`src/nirmaan/integrations/eda_guard.py:5`, `:370-380`, `:449-450`), so a
  probe of them needs the bypass the read probes already use
  (`scripts/live_eval_reach.py:582-592`).
- F8. `scripts/live_eval_reach.py` is the plan's pinned group "Reach test"
  (plan, sections 18.1 and 18.2). A change to it moves a pinned value, and a
  moved value stops every dispatch until a plan amendment merges (plan,
  section 7). The wave 2 re-measure batch runs in the same job with a freeze
  of its own (`council/records/2026-11-23-wave-2-close-meeting-1.md`,
  decision 4); its plan is not on `main` yet (ai-engineer).
- F9. A slot's record is committed at
  `evals/results/g3-timer/slot-NN/<record name>/` (plan, section 15). The
  record tests find a record by its `manifest.json`
  (`tests/test_whole_flow.py:83-104`), and a manifest names its commit
  (`head_sha`). A failed reach test is a job-level stop: "The cause is fixed
  and the same slot is dispatched again. If a record exists for that
  dispatch, it is a trial and is committed as it is", and "An unjudged trial
  counts as failed in its group" (plan, section 8).

### Decisions

#### A1. Security's must-haves 1 and 2 are adopted

All five seats said adopt both. Nobody dissented.

Why. Committing a record costs no run: both jobs already upload it (F2). The
gap security named is real (F5). And qa-evidence, whose line "none until
slot 1" is, withdrew it: the measured run is a dispatch of the `live-eval`
job before slot 1, and this record's own decision 7, item 3 says so.

**Before slot 1 (gate ET10).** All of this is true on `main`:

1. The measured run's tool reach records, of its `live-eval` job and of its
   `rejudge` job, are committed as each job uploaded them, byte for byte,
   in a folder of their own in `evals/flow/`, with one index file beside
   the ET3 record. The index names the run, its attempt, the commit and the
   purpose `calibration`, and each file with its sha256. The ET3 record is
   not changed. (Amended 2026-11-23 by the second addendum, decision R2. It
   read: "are committed as each job uploaded them, in one file of their own
   beside the ET3 record in `evals/flow/`. The file names the run, its
   attempt, the commit and the purpose `calibration`.")
2. Each of the two shows every probe denied and every control passed. Both
   name the same run and the same commit.
3. With them, for each job, the lines the reach step's first part printed
   (its `REACH` lines and its closing `reach test:` line), copied from the
   job's log. The tool reach record does not hold that part (F3), and it is
   the only part that probes writes and the network (security, qa-evidence,
   ai-engineer and verification-lead each found this alone).
4. The seat C reach records of the same two jobs
   (`live-eval-fw-reach-trials-<run id>`, `live-eval-fw-reach-rejudge-<run
   id>`) are committed as uploaded, byte for byte, in the same folder,
   named in the index with their sha256, by a pull request that merges
   before the index does (security). Nothing is claimed from them for the
   timer, which links no seat C; that statement is the register block's
   (gates WF17 to WF19). (Amended 2026-11-23 by the second addendum,
   decision R2. It read: "are committed with them, as uploaded".)
5. The index states the values of the plan's section 18.1, the seven group
   digests among them, as computed on the run's commit, and they equal the
   values on the commit slot 1 is dispatched from. If any differs, the
   measured run's records do not cover the code slot 1 would run: that is
   the gap of F5 again, and gate ET10 is not met on that commit (qa-evidence,
   ai-engineer, verification-lead, security).
6. A record that is missing counts as a probe not denied (F3).

The measured run's records never stand in for a slot's own gate: every slot
still runs the reach test before its trial and before its re-judge.

**Each slot (gate ET11).** The tool reach records, of both jobs, and the
seat C reach records of each run of a slot are committed as uploaded by a
pull request of their own for each run, merged before the slot's record
pull request, in the slot's folder beside `<record name>/` and never inside
it, so the record stays the re-judged record as the job wrote it
(verification-lead). They are records: a pull request that carries them
adds records only (plan, section 7). A reach record has no manifest and is
never counted or listed as a trial (ai-engineer). (Amended 2026-11-23 by
the second addendum, decision R3. It read: "A slot's tool reach records, of
both jobs, and its seat C reach records are committed in the same pull
request as the slot's record, in the slot's folder", and "a record pull
request that carries them still adds records only".)

Owners: security (ET10, ET11); verification-lead (the slot folders and the
record pull requests); ai-engineer (item 5).

#### A2. Decision 2, item 3 and the bullet of decision 8, reworded

The last sentence of decision 2, item 3 now reads:

> The `live-eval` job's first recorded probe run is the measured run of the
> plan's section 10; its reach records are committed before slot 1 (gate
> ET10). Nobody says the `live-eval` job has a recorded probe run beyond a
> committed record that names the run and its commit.

The bullet of decision 8 now reads:

> that the `live-eval` job has a recorded probe run, beyond a committed
> record that names the run and its commit; or that one run's reach record
> covers another run, another commit or a slot;

Both are amended in place above, with a note. The four seats that proposed
wording agreed in substance; the chair took verification-lead's form for
item 3 and joined qa-evidence's and security's second clause to the bullet.
Until the measured run's records merge, both sentences forbid what the old
ones forbade: no text says the job has a recorded probe run.

Gate ET3 stays as it was met: the replay of c99ef1fe is the record of that
commit and is cited for that commit only. The gap of F5 is closed by gate
ET10, not by changing ET3.

Owner: qa-evidence.

#### A3. A reach gate that fails

Decided in advance, for each place it can fail.

1. **The measured run, in either job.** No slot is dispatched. If the
   `live-eval` job's gate fails, no trial ran (`live-eval.yml:280-285`) and
   the run measured nothing. Whatever reach records and log lines the run
   left are committed, none held out, as a failed gate, before any further
   dispatch of the timer case. The cause is fixed; if the fix moves a pinned
   value, the plan amendment of the plan's section 7 merges first. Then a
   run records every probe denied in both jobs, and gate ET10 is read on
   that run. The plan's "one run" (section 10) is read with this: one run
   that passed its gates.
2. **A slot, in the `live-eval` job.** The plan's section 8 already rules
   it: a job-level stop, no trial ran, and the same slot is dispatched again
   once the cause is fixed. This addendum adds two things. The failing
   run's reach records are committed in the slot's folder, beside those of
   the run that later records the slot. And no slot is dispatched until the
   cause is known; a fix that changes anything the freeze of gate WF25
   holds returns to the council before it merges, since from slot 1 the
   plan changes only by a ruling (security, qa-evidence, ai-engineer). If
   slots then run on two values of a group, the read names which slot ran on
   which (ai-engineer).
3. **A slot, in the `rejudge` job, after the trial's record exists.** The
   plan's section 8 as written applies and this addendum does not change a
   count: the record is a trial and is committed as it is, and an unjudged
   trial counts as failed in its group (F9). The slot is not dispatched
   again. No further slot is dispatched until the cause is known, as in item
   2. verification-lead asked that the plan say this in so many words (gate
   ET14).

Which run meets gate ET10 again after a pinned value has moved (a further
measured run, or another recorded run of the same probes on the new commit)
is not guessed here: it goes to security, the gate's owner, when it arises.

Owners: security (the stops); verification-lead (the plan's words);
ai-engineer (the freeze).

#### B. Write and network probes through each wrapped tool: not before slot 1; through `sby` and `eqy` before slot 21

The seats differed.

- security: later, after the timer's last trial and before slot 21. Having
  read the wrapper code it now rates its inference high, not medium: "the
  control is per uid on one shared code path and per-tool probes add
  evidence, not a control".
- verification-lead: later, before slot 21, with the change gate ET9 makes
  to the reach test anyway.
- eda-tooling: no. The denials depend on the account, not the program; a
  probe through `iverilog`, `verilator` or the `yosys` of `synth.run` would
  use a construct that tool never acts on and would prove nothing; a probe
  through `sby` or `eqy` "would only retest the uid".
- qa-evidence: no view on the need, which is security's. On the evidence:
  the texts claim write and network denial through `vvp` only.
- ai-engineer: no view on the need ("for security to say"). On timing its
  answer was "before slot 1": if adopted, the change would have to merge
  before the measured run and before trial 1 of whichever batch runs first,
  with a plan amendment.

The chair decided: not a condition before slot 1; a condition before slot
21, through `sby` and `eqy` only.

Why not before slot 1. No seat that judged the need asked for it there;
ai-engineer's answer was on timing. The question was whether
a denial shown through `vvp` holds for the other tools, and the code answers
it as far as code can (F6): one path to the account, and rules that match
the account and not the program. What a probe must still show for each tool
is that its process is the account, and the read probes show that through
each tool each time the test runs: the runner-only canary is denied to it (decision 2,
item 2). Against that, the change moves a pinned group (F8), so it would
need a plan amendment and would land in the job of both batches before
either starts.

Why at all. This record's rule is that a measure is claimed for what a
recorded probe shows (decision 1). `sby` is on the timer path, its setup
file is seat-written, and Yosys under it acts on commands that write files
and run programs (F7). Today the screen is the only recorded refusal of
those, and decision 1 does not let the screen be the one control. A code
reading is an inference, however strong; security and verification-lead
both asked for the probe later, and the chair agrees with them over
eda-tooling. eda-tooling's facts set its scope: only `sby` and `eqy`, since
a probe through a tool that does not act on the construct shows nothing.

So:

1. Before slot 21, with gate ET9 (gate ET12): the reach test probes, through
   `sby` under `formal.run` and through `eqy` under `equivalence.run`, with
   the screen bypassed inside the probe only and said so in its output, a
   write to a target outside the run and a reach for the network. Denied
   means: the tool's own output says it could not, the target is unchanged
   as the runner sees it afterwards, and for the network the same rule as
   the `vvp` probe (`scripts/live_eval_reach.py:102-107`). Each has a
   control that shows the construct live: the same write inside the run's
   own directory succeeds.
2. The same change writes the first part's results into the tool reach
   record, so that a committed record holds every probe and item 3 of
   decision A1 is no longer needed for later runs (qa-evidence).
3. It merges outside both freezes: after the timer's last trial is
   recorded, and not while the re-measure batch's freeze holds if that
   batch's plan pins the reach test, with the plan amendment its moved
   digest needs.
4. Until it merges, a text says only this: in a named run the write and
   network probes were denied through `vvp`; the other wrapped tools run as
   the same account by the same wrapper code, which is a reading of the
   code and not a probe. No text says the write or network denial was
   probed through `iverilog`, `verilator`, `yosys`, `sby` or `eqy`.
5. The residual, added to the one decision 8 and the wave 2 close record
   state: no write or network probe has run through a tool other than
   `vvp`; and the network probes cover the five listed targets, so nothing
   is said of local sockets, which the rule on the account's packets does
   not cover (eda-tooling; not probed, and the same for every tool). Whether
   a local socket is a reach question is security's to answer with gate
   ET12.

Owners: security (ET12 and the residual); eda-tooling (the build).

#### C. What may cite a reach record of the `live-eval` job, and how

All five seats agreed on the words. They differed a little on the places;
the chair took the union that has an owner.

May cite the measured run's or a slot's reach records, once they are
committed: the committed file's own `about` field; a dated section of the
plan; `docs/LIVE_EVAL_EVIDENCE.md`, section 6, and `docs/GATE_INTEGRITY.md`,
section 6; and the pull request that commits them.

In these words and no wider (decision 8's allowed sentence): in run N,
dispatched on `main` at C with purpose `calibration`, in its `live-eval` and
`rejudge` jobs, the listed probes were denied to `nirmaan-seat` through the
named tools. For a slot: the same, with the slot in place of the purpose.

Never said, adding to decision 8:

- the measured run as a result, a trial or a pass, or anything of its
  trial's outcome, stages or attempts, or any time, usage or cost figure
  from it (plan, section 10);
- that a run's reach record covers another run, another commit or a slot;
- that a tool reach record holds the first part's probes, while it does not
  (F3): those are cited to the committed log lines;
- that write or network denial was probed through any tool but `vvp`
  (decision B, item 4);
- `eqy` or `coverage.read` as tools of the timer path, though a record
  lists their probes (verification-lead).

Who confirms. qa-evidence, under gate ET8, by a read made as a process apart
from the pull request's author, on the head of each pull request that
changes one of these texts, and on the head of the pull request that commits
the measured run's records, before it merges (gate ET13). That pull request
also brings every sentence on `main` that says the job has no recorded run
"before slot 1" in line with decision A2. security checks that the tools and
probes a text names match the record. A read is an agent's read, not a
person's approval.

Owner: qa-evidence.

### Positions not adopted, and dissent

- eda-tooling: no write or network probe through any further tool, at any
  time. Not adopted (decision B). Recorded as dissent. Its facts on the
  shared wrapper and on which tool acts on which construct are adopted
  whole, and they set the scope of gate ET12.
- ai-engineer: the committed file records the seven group digests of its
  commit "and a test holds them equal to the tree's". The first half is
  adopted (decision A1, item 5). The test is not: the tree's values move by
  design after the timer's last trial, and a test bound to them would then
  fail a record that is still true of its own commit. The equality is
  checked at each dispatch instead, as the plan's section 7 already checks
  every pinned value.
- ai-engineer: the re-measure batch's plan should pin the reach test and
  the seat account as groups. Not decided here: it is that plan's and the
  wave 2 close record's (gates W2C7 and W2C9). Sent to its owner.
- verification-lead: a test holds each slot's reach record to the run and
  commit of its slot's trial record. Adopted for the commit (the manifest
  names it, F9); for the run, where the record names it. In the build
  specification.
- verification-lead: the plan should say that the measured run's own trial
  record is not committed under `evals/results`. Not on this agenda, which
  was the reach records. It is the plan's, and verification-lead's to
  propose there; nothing here decides where that trial's record goes.
- verification-lead and security differed on whether
  `docs/GATE_INTEGRITY.md` may cite the records. The chair allowed it
  (decision C): the document already cites the ET3 record, and the same
  words bind it.
- eda-tooling: the `about` field of the ET3 record ("has no recorded run
  here") should change. Not adopted: the ET3 record is not changed, and the
  sentence is true of that file.
- security: no view on whether a stopped slot's number is used again. The
  plan's section 8 answers it (decision A3).

No seat dissented from adopting the two must-haves, from the rewording, or
from the words of decision C.

### Gates added

| Gate | Condition | Owner seat |
|---|---|---|
| ET10 | Before slot 1: the measured run's tool reach records of the `live-eval` and `rejudge` jobs and its seat C reach records are committed as uploaded in a folder of their own, with an index file beside the ET3 record, as decision A1 items 1 to 6 and decision R2 of the second addendum say: every probe denied in both, one run and one commit, every file equal to its sha256 in the index, the first part's log lines in the index, and the values of the plan's section 18.1 on that commit equal to those on slot 1's commit. The gate is met only on a commit that holds all of it. No slot is dispatched otherwise. (Reworded 2026-11-23 by the second addendum; it read "committed in a file of their own beside the ET3 record" and "the first part's log lines and the seat C reach records with them") | security |
| ET11 | The tool reach records and seat C reach records of each run of a slot are committed as uploaded, by a pull request of their own for each run, merged before the slot's record pull request, in the slot's folder beside the record, with a test that holds each to its slot's commit (gate ET16); a failed gate's records are committed too (decision A3). (Reworded 2026-11-23 by the second addendum, decision R3; it read "are committed with its record") | security |
| ET12 | Before slot 21, with gate ET9: write and network probes through `sby` and `eqy` with a live control each, and the first part's results written into the tool reach record (decision B), merged outside both freezes with its plan amendment | security |
| ET13 | Every text that cites a reach record of the `live-eval` job follows decision C; qa-evidence reads the head of each pull request that changes one, and of the one that commits the measured run's records, before it merges | qa-evidence |
| ET14 | Before slot 1: a dated addition to the plan takes up decisions A1 to A3 and C: security's items 1 and 2 as conditions, where the reach records sit, what a failed gate means for the measured run and for a slot in each job, and the words of decision C | verification-lead |

### Build specification, for the build lane

This meeting wrote no code. Nothing below touches a file in `harness.CODE`,
`LOOP_CODE` or `FLOW_CODE`, a tool definition, or a pinned group, until gate
ET12.

1. **The plan (ET14).** A dated addition, docs only, before slot 1.
2. **The measured run's records (ET10, ET13).** (Read with the second
   addendum, decision R2: a chain of pull requests, not one, and an index
   with the records in a folder, not one file.) One pull request after the
   measured run: the file of decision A1 in `evals/flow/`; a test beside the
   ET3 record's test in `tests/test_live_eval_seat.py` that holds its
   format, both jobs, every probe denied, one run and one commit, the
   purpose, and the presence of the first part's lines for each job; the
   texts of decision C. qa-evidence reads its head.
3. **The slots (ET11).** (Read with the second addendum, decision R3: each
   run's reach records in a pull request of their own, before the slot's
   record, and the test on `main` before slot 1 is dispatched.) The record
   pull requests carry each slot's reach
   records beside its record. A test in `tests/test_whole_flow.py` holds,
   for every committed slot folder, that its reach records are there, that
   those of the run that recorded the slot show every probe denied in both
   jobs, and that their commit is the record's `head_sha`. The test merges
   before slot 1's record does.
4. **The dispatch.** Whatever dispatches a slot refuses to unless gate ET10
   holds on the commit it dispatches from, and stops after any run whose
   reach record is missing or shows a probe not denied.
5. **Later (ET12).** `scripts/live_eval_reach.py`: the probes of decision B,
   item 1, and the first part's results in the record, with tests in
   `tests/test_live_eval_seat.py`, and the plan amendment for the moved
   "Reach test" digest.

### Open, for the founder

1. This addendum, to confirm or overrule.

## Second addendum (2026-11-23): the reach records and the review's size limit

This addendum settles one conflict before the timer's measured run. Gates
ET10 and ET11 of the addendum above, as worded, ask for more than one pull
request can carry: the review does not run on a diff over 200,000 bytes
(`docs/REVIEW_MECHANISM.md`, "The reviewers always get the whole diff, never
a cut one"). Raising or passing round that limit weakens a review gate, which
is the founder's alone, so it was not on the agenda. The council met on how
the same records reach `main` in pull requests that are each reviewed whole.

Ruling, in short:

- **Every reach record is committed as its job uploaded it, byte for byte,
  as text a reviewer reads.** No compressed, encoded, re-serialised or
  factored form (decision R1). A file git treats as binary would pass the
  size rule without being shown to a reviewer; all four seats found that
  this amounts to passing round the limit.
- **Gate ET10 is met by a chain of pull requests** (decision R2): the seat C
  reach records first, as records only; then an index file beside the ET3
  record, the tool reach records, the test and the texts. The gate is met
  only on a commit that holds all of it.
- **Gate ET11: each run's reach records go in a pull request of their own,
  merged before the slot's record pull request** (decision R3). Nothing of
  the timer case is dispatched while a finished run's reach records are not
  on `main` (gate ET15). A test holds the slot folders at every commit of
  `main` and is merged before slot 1 is dispatched (gate ET16).
- **A record that does not fit a pull request by itself stops the
  dispatch** and returns to the council; it is never cut, split or held out
  (decision R4).

It changes no code, case, eval record, level, fingerprint or digest. It
loosens no gate: every record the addendum above asks for still reaches
`main`, none held out, each tied to its run and commit, and two conditions
are added (gates ET15 and ET16). Three sentences of the addendum above and
two rows of its gate table are reworded in place, each with a note. No trial
ran and no workflow was dispatched for the meeting.

### Who decided what

The council decided every item below. The orchestrator called the meeting
because two gates of a council record could not be met as worded. It is not
a founder decision, and the founder can overrule it. One finding is sent to
the founder undecided (decision R4, item 6): it is about the review's size
rule, not about these records.

Four seats gave round 1 positions independently, each as its own read-only
process that saw no other answer to the brief (security, qa-evidence,
ai-engineer, verification-lead); the chair decided. The seats read
ip-nirmaan at 408d9ae6, which is `main` at c405e4a0 with the addendum above
(ip#462) merged in, and a sample: the four reach artifacts of replay run
45073595509 as GitHub served them, and a gate ET10 file built from them in
two layouts. The sample is a sample of sizes and shapes: it is not the
measured run, which had not been dispatched, and nothing is claimed from it.
The seats had no shell; the chair measured the sizes below and rechecked the
cited lines.

### Facts checked

S1 to S9 number this addendum's facts.

- S1. The limit is on the bytes of the diff of `main...head` as
  `git diff --no-ext-diff --no-textconv --no-color -M` prints it
  (`scripts/pr_review.py:100`, `:1267`, `:1311-1314`). Over it, both checks
  stay pending and the loop stops the pull request
  (`docs/REVIEW_MECHANISM.md:172-175`, `:418-423`). A file git treats as
  binary costs one line of that diff whatever its size, and the reviewers
  are shown none of its content (inference from the command: nothing in
  `scripts/pr_review.py`, `scripts/pr_loop.py` or
  `.github/review-teams.yml` names binary files, and the repository has no
  `.gitattributes`).
- S2. Sizes, measured by the chair on the sample, as bytes of diff when the
  files are added:

  | What | Bytes of diff |
  |---|---|
  | The gate ET10 file as one file: both tool reach records, both jobs' first-part lines, both seat C reach records, the values | 189,488 |
  | The same without the seat C reach records | 86,648 |
  | The two seat C reach records as uploaded | 113,154 |
  | One run's four reach artifacts as uploaded, in a slot folder | 130,264 |
  | of which the two tool reach records | 16,768 |
  | That run's whole-flow replay record | 75,177 |
  | That record and the four reach artifacts together | 205,441 |

  So the one-file layout leaves no room for its test and the texts of
  decision C, and a replay slot's record with its reach artifacts is already
  over the limit. A slot with a failed-gate run carries a second run's
  artifacts (decision A3, item 2).
- S3. A real slot's record is expected to be larger than the replay's: a
  whole-flow trial with a model runs several stages with up to three
  attempts each (plan, section 4), and committed single-seat trial files
  reach 117,088 bytes
  (`evals/results/2026-11-18-claude-code-claude-opus-5-5-14/rtl_axil-timer/trial-01.json`).
  This is an inference; the measured run exists to measure it (plan, section
  10).
- S4. What is large is the seat C reach record: 181 read targets, and nine
  probes that each list every target. The two jobs' seat C records of one
  run differ in 46 of about 618 lines, and the two jobs' first-part lines in
  34 and 35 of about 255. No line repeats inside one job. Each seat C record
  gzips to about 4,550 bytes.
- S5. Each uploaded record names its run and its commit: a tool reach record
  by `run_id`, `run_attempt`, `job` and `commit`; a seat C reach record by
  `run.id`, `run.attempt`, `run.job` and `head` (the sample's four files).
  Both writers write `json.dumps(..., indent=2)` and a newline
  (`scripts/live_eval_reach.py:714`; `scripts/live_eval_fw_reach.py:584`,
  `:615`).
- S6. The workflow sets no `retention-days` on the reach artifacts
  (`.github/workflows/live-eval.yml:255-261`). Whether GitHub keeps them for
  good was not checked; qa-evidence and verification-lead assume it does
  not, so that after a time the copy on `main` is the only one.
- S7. The review loop takes pull requests to `main` only, and stacked pull
  requests are never reviewed (`docs/REVIEW_MECHANISM.md:414-416`). Record
  pull requests "add records only" (plan, section 7), reach `main` "in slot
  order, none held out" and "pack whole records under the review's size
  limit" (plan, section 3). The plan lets the next slot be dispatched once
  the whole run has finished; it does not ask for the slot's record on
  `main` first (section 3).
- S8. What reads these folders. Levels are read from `manifest.json` files
  at any depth (`src/nirmaan/evals/levels.py:248`), so a pull request that
  adds reach records only changes no level (ai-engineer). The case loader
  reads every `*.json` under `evals/` and skips a file that is a JSON object
  with a `format` field (`src/nirmaan/evals/cases.py:21-27`, `:38-40`); the
  uploaded reach records carry one. A manifest names its commit and no CI
  run (`src/nirmaan/evals/records.py:233`, `:275`; verification-lead), so a
  record is tied to its run through the reach records of the same commit.
- S9. `evals/flow/*.json` and `evals/flow/*/**` are gate-semantics paths
  (`.github/review-teams.yml:576-577`): each pull request of the gate ET10
  chain goes to the Founder Proxy. `evals/results/**` is not listed there.
  None of these paths is in a harness fingerprint or in one of the seven
  groups of the plan's section 18.1, so committing the records moves no
  pinned value (ai-engineer; an inference from the paths).

### Decisions

#### R1. The form: as uploaded, byte for byte, readable

Three seats said as uploaded only (security, qa-evidence, ai-engineer).
verification-lead agreed for every slot folder and for any compressed or
encoded form, and would have allowed one thing more (below).

1. Every tool reach record and every seat C reach record on `main` is the
   file its job uploaded, byte for byte, under its artifact's name. It is
   text, and a reviewer reads it in the diff.
2. Never compressed, encoded as base64, re-serialised, factored, or kept as
   its differences from another record. Why. A compressed file is binary to
   git: the size rule counts one line and the reviewers see nothing (S1),
   which is a cut diff by another route. Base64 is counted but cannot be
   read. A factored or re-serialised form makes the reader trust a rebuild
   or a digest in place of the record (security, qa-evidence).
3. Each set of records has an index file that names every file with the
   sha256 of its bytes, and a test recomputes each digest from the committed
   file. The digest ties the files of a chain to one another across pull
   requests and shows any later change. It does not prove what GitHub
   served: once an artifact is gone (S6), the copy on `main` is the record.
4. A text says "as uploaded" only of a file the test checks byte for byte
   (qa-evidence). The first part's lines are a copy from the job's log with
   the timestamps cut, and are said to be that.
5. Every file in a reach folder is a UTF-8 JSON object with a `format`
   field; the test refuses any other file there, a binary one included. If
   a job ever uploads a reach file that is not one, nothing is dispatched
   and it goes to security: it is not decided here.

Not adopted: verification-lead would allow a tool reach record inside the
gate ET10 file as compact re-serialised JSON, with a test that rebuilds the
uploaded bytes (possible, S5). It saves a few thousand bytes of 200,000,
and security and qa-evidence each made "byte for byte" a must-have. Recorded
as dissent.

Owner: security.

#### R2. Gate ET10: an index beside the ET3 record, the records in a folder, a chain of pull requests

All four seats gave the same layout and order: the seat C reach records
first, by themselves, then the rest.

1. **The files.** In `evals/flow/tool_reach_measured_run/`, the four
   uploaded files, each at `<artifact name>/<file name>` as uploaded. Beside
   the ET3 record, `evals/flow/tool_reach_measured_run.json`, the index: a
   `format`; an `about` in the words of decision C; the run, its attempt,
   the commit and the purpose `calibration`; the values of the plan's
   section 18.1 on that commit; for each job the conclusion of its reach
   step, the first part's lines and closing line, and the path and sha256 of
   its tool reach record and of its seat C reach record. The index embeds no
   record. security and qa-evidence put the index inside the folder,
   ai-engineer and verification-lead beside the ET3 record; the chair kept
   it beside the ET3 record, where item 1 of decision A1 had it.
2. **The pull requests, in this order.**
   - First: the two seat C reach records, and nothing else. It adds records
     only. Its text says what the files are and that gate ET10 is not met
     by it. If the two do not fit one pull request, one each.
   - Then: the index, the two tool reach records, the test, and the texts
     of decision C. If that does not fit, the texts go in a pull request
     after it (verification-lead).
   - All of them are merged before slot 1, and qa-evidence reads the head
     of each (gate ET13).
3. **When the gate is met.** Only on a commit that holds the index and all
   four files with equal digests, each showing what items 2 to 6 of
   decision A1 ask. The dispatcher reads the gate from the commit it
   dispatches from, so no state between two pull requests of the chain lets
   slot 1 go (security). Only the pull request that completes the chain may
   say the gate is met; no text says it of a commit in between
   (qa-evidence).
4. **The test** (in `tests/test_live_eval_seat.py`, beside the ET3 record's)
   holds the format, both jobs, one run and one commit in the index and in
   each file (S5), the purpose, every digest, every probe denied and every
   control passed in each file, and the first part's lines for each job.
5. **A measured run whose gate failed** (decision A3, item 1) is committed
   in the same layout and order under `tool_reach_measured_run_failed_<run
   id>` (the index and the folder). Its index lists an artifact the run did
   not upload as missing, which counts as a probe not denied. It is never
   read as the gate ET10 file.
6. A single uploaded file over the limit by itself is the case of decision
   R4, item 4.

Items 1 and 4 of decision A1 are reworded in place above to say this.

Owners: security (the gate); qa-evidence (the reads); ai-engineer (item 5
of decision A1, unchanged).

#### R3. Gate ET11: each run's reach records in a pull request of their own, before the slot's record

All four seats said: one pull request for each run's reach records, records
only, merged before the slot's record pull request and never after it.

1. **The files.** At `evals/results/g3-timer/slot-NN/reach/<run id>/`: the
   run's uploaded files, each at `<artifact name>/<file name>`, and
   `reach-index.json`. The index names its `format`, the slot, the run, its
   attempt and its commit; each file with its sha256; each of the four
   artifacts the run did not upload, as missing (a probe not denied,
   decision A1, item 6); whether this run wrote the slot's record; and, if
   it did not, why in words: the job whose reach gate failed, or the
   job-level stop and its exit code (verification-lead). The folder sits
   beside `<record name>/` and never inside it, and holds no
   `manifest.json`, `causes.md` or `trial-*.json`. Three seats gave
   `reach/<run id>/`; ai-engineer gave `reach-<run id>/`; the chair took the
   three's.
2. **Every run of a slot has its folder**, none held out: the run that
   wrote the record, a run whose reach gate failed, and a run that stopped
   at job level for any other cause (security: "whatever the run left").
3. **The order on `main`.** For one slot: the reach records of each run
   that wrote no record, then those of the run that wrote the record, then
   the record (qa-evidence). Across slots: slot N's record is on `main`
   before the reach records of slot N+1 are (verification-lead). A pull
   request holds one run's reach records, or records; never both.
4. **The dispatch bound (gate ET15).** Nothing of the timer case is
   dispatched, a later slot or the same slot again after a stop, unless the
   commit it is dispatched from holds the reach folder of every earlier run
   of every slot, with digests equal to the files the dispatcher downloaded.
   The slot's record pull request may still be open, as the plan's section 3
   allows. Three seats asked for this bound (security, ai-engineer,
   verification-lead); qa-evidence left it to them. Why: it makes "none held
   out" a check and not a promise (security); a denial that failed is on
   `main` before any further trial (ai-engineer); and an artifact may not be
   kept (S6). security rates it "a bound I chose, not a control", with
   medium confidence; the chair adopts it because three seats arrived at it
   alone and nobody opposed it.
5. **The test (gate ET16)**, in `tests/test_whole_flow.py`, holds at every
   commit of `main`:
   - a reach folder holds only what item 1 names, every digest of its index
     equals the committed file, and every record in it names the index's
     run and commit (S5);
   - a slot folder with a record has exactly one run folder whose index
     says it wrote the record, and that run's commit is the record's
     `head_sha`;
   - that run's records show every probe denied in the `live-eval` job, and
     in the `rejudge` job unless the record is unjudged (it has no
     `rejudge.json`): decision A3, item 3 lets the re-judge's gate fail
     after the trial's record exists, and the test must not fail `main`
     for a record the plan says is committed as it is (ai-engineer);
   - every other run folder of the slot states why it wrote no record, and
     a run that shows every probe denied in both jobs with no record and no
     stated cause fails the test: that would be a trial held out
     (verification-lead);
   - the slot folders with a record are slot 01 onward with none missing,
     and only the highest-numbered slot folder may hold reach records and
     no record.
6. **The test is on `main` before slot 1 is dispatched**, not only before
   slot 1's record merges, so that its rules are fixed before any outcome
   is known (ai-engineer). The build specification above, item 3, said
   "before slot 1's record does"; this is stricter and replaces it.
7. **A record whose own run does not show the `live-eval` job's probes
   denied** (a record exists although a reach record is missing or shows a
   probe not denied). The index says so truthfully, the record is committed
   as it is, none held out, and the dispatch stops (build specification
   above, item 4). How such a trial counts is not decided here: it goes to
   security and verification-lead when it arises.

The sentence of decision A1 under "Each slot (gate ET11)" is reworded in
place above to say this. A pull request of reach records adds records only
(plan, section 7) and changes no level (S8).

Owners: security (ET11, ET15); verification-lead (ET16, the slot folders
and the record pull requests).

#### R4. What is said, the plan, and a record that does not fit

1. Decision C's "the pull request that commits them" now means each pull
   request of a chain. Its words bind each one. Gate ET13's read covers the
   head of every pull request of the gate ET10 chain.
2. A pull request of a slot's reach records names the slot, the run, the
   commit and the files. It states no outcome and no count (plan, section
   11), and it does not say gate ET11 is met.
3. Gate ET14's plan addition also states: the two layouts, the order of the
   pull requests, what the test of gate ET16 holds, the dispatch bound, and
   item 4 below. verification-lead asked that it merge once the measured
   run's sizes are known; when it merges is verification-lead's to choose,
   so long as it is before slot 1.
4. **A record, or one uploaded file, that is over the limit by itself.**
   No order of pull requests fixes it. Nothing further is dispatched, and
   it returns to the council before anything is committed. It is never cut,
   split across pull requests, compressed or held out. The council cannot
   raise the limit; that is the founder's (qa-evidence, ai-engineer,
   verification-lead).
5. The dispatch checks stay outside the seven pinned groups. A check placed
   in `scripts/live_eval_ci.py` or the workflow would move a pinned value
   and would need a plan amendment merged before the measured run, or item
   5 of decision A1 fails (ai-engineer).
6. **A finding for the founder, not decided here.** Any pull request can
   carry a binary file whose content the reviewers never see and the size
   rule never counts (S1; all four seats). Whether the review should count
   or refuse binary files is a question about a review gate. No reach
   record uses that route (decision R1), and the tests of decisions R2 and
   R3 refuse a file that is not text in a reach folder.

Owners: qa-evidence (items 1 and 2); verification-lead (items 3 and 4);
ai-engineer (item 5); security (item 6, to raise).

### Positions not adopted, and dissent

- verification-lead: a tool reach record may sit in the gate ET10 file as
  compact re-serialised JSON, rebuilt by a test. Not adopted (decision R1).
  Recorded as dissent.
- verification-lead stated as a fact that the sample's seat C record names
  no run and no commit. The chair read the sample: it names both (S5). The
  test therefore holds a seat C record to its run and commit by its
  content, not by its path alone.
- ai-engineer: `slot-NN/reach-<run id>/` for the folder. Not adopted: three
  seats gave `slot-NN/reach/<run id>/`. A difference of name only.
- security and qa-evidence: the gate ET10 index inside the folder. Not
  adopted: it stays beside the ET3 record. A difference of place only.
- qa-evidence: slot N+1's record pull request is not opened until all of
  slot N's are on `main`. Adopted in substance by the order of decision R3,
  item 3 and the last line of its test, which bind what merges; when a pull
  request is opened is left to its author.
- qa-evidence would send a record that does not fit straight to the
  founder; ai-engineer and verification-lead to the council. The chair: to
  the council first, which may find a way that keeps the limit; the limit
  itself is the founder's (decision R4, item 4).
- No seat proposed raising the limit, and no seat supported a compressed or
  encoded record.

No seat dissented from the order (reach records before the record), from
the dispatch bound, or from the seat C reach records being kept for every
job and every run.

### Gates changed and added

Gates ET10 and ET11 are reworded in the table of the addendum above, each
with a note. Added:

| Gate | Condition | Owner seat |
|---|---|---|
| ET15 | From slot 1: nothing of the timer case is dispatched unless the commit it is dispatched from holds the reach folder of every earlier run of every slot, each file equal by digest to what the run uploaded (decision R3, item 4) | security |
| ET16 | Before slot 1 is dispatched: the test of decision R3, item 5 is on `main`, and it holds at every commit of `main` after it, the commit between a slot's reach records and its record included | verification-lead |

Gate ET13 covers the head of every pull request of the gate ET10 chain, and
gate ET14's addition carries decision R4, item 3.

### Build specification, for the build lane

This meeting wrote no code. Nothing below touches a file in `harness.CODE`,
`LOOP_CODE` or `FLOW_CODE`, a tool definition, or a pinned group. Items 2
and 3 of the build specification above are read with these.

1. **The gate ET10 chain (decision R2).** The folder and the index as item
   1 says; the seat C reach records in the first pull request; the index,
   the tool reach records, the test and the texts after it; a failed
   measured run in the same shape under its own name.
2. **The gate ET10 test** in `tests/test_live_eval_seat.py` (decision R2,
   item 4). It passes on a commit that has the folder and no index, and
   holds everything once the index is there.
3. **The slot test (gate ET16)** in `tests/test_whole_flow.py` (decision
   R3, item 5), merged before slot 1 is dispatched. It passes while no slot
   folder exists.
4. **Whatever dispatches** refuses unless gates ET10 and ET15 hold on the
   commit it dispatches from, comparing digests with the files it
   downloaded; it stops when a record or an uploaded file does not fit a
   pull request by itself (decision R4, item 4).
5. **Whatever builds the pull requests** copies each uploaded file byte for
   byte, writes the index, builds one pull request for one run's reach
   records or for records and never both, and refuses a file in a reach
   folder that is not a UTF-8 JSON object with a `format` field.

### Open, for the founder

1. This addendum, to confirm or overrule.
2. Decision R4, item 6: whether the review's size rule should count or
   refuse binary files. Raised by all four seats; not decided by the
   council.

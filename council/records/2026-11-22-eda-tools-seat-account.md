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
   trial. Nobody says the `live-eval` job has a recorded run before slot 1:
   it has none until slot 1 (qa-evidence) (ET3).
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
- that the `live-eval` job has a recorded probe run, before slot 1;
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

## Open, for the founder

1. This ruling, to confirm or overrule.

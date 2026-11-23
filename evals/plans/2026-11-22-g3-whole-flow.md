# G3 whole-flow batch: the committed plan

This file is the committed plan of the G3 whole-flow batch. It is the plan that gate WF10 asks for (as amended by
the fourth addendum), the plan that gate WF20 describes, the plan and the timer's values that gate WF24 asks for,
and it carries the statement that gate WF23 asks for the timer flow. The gates are in
`council/records/2026-11-17-g3-whole-flow-cases.md` (decision 4, the gates table, and its second, third and fourth
addenda). Where this file quotes a ruling, the record is the source; where the two differ, the record rules.

No whole-flow trial has run. Nothing here is a result, and nothing here may be cited as one. This pull request
changes no code, no case, no record and no level: no file in `harness.CODE` or `harness.FLOW_CODE`, no tool
definition, no CLI pin, no card and no knowledge document is touched, so every fingerprint below is the one `main`
already has. It was written on 2026-11-22, before trial 1 of either case.

## 1. What is fixed, and how it may change

Fixed here, for both cases, before slot 1 (fourth addendum, decision 2, item 1):

- Ten trials per arm per case, two arms, two cases: forty trials, `flow/axil-timer` (the timer) and
  `flow/axi4-lite-regs-driver` (the register block).
- The arms: with documents (`--knowledge on`) and without (`--without-knowledge`, the workflow's `knowledge=off`).
- The slot order and the interleave of section 3.
- The default harness with its attempts (section 4), one trial per dispatch.
- The main count and the derived count of section 5, word for word.
- The stop rules of section 8: an interrupted or unjudged trial is a failed trial; no re-run, no top-up, no early
  stop, no extension.

None of these changes for the register block after the timer's slot 1, except by a council ruling that records that
the timer's results were known. A change to any fixed item after slot 1 is made only by a council ruling (gate
WF24). The values that cannot be computed until the register block flow can run are not guessed: section 6 gives
the timer's, and a dated addition to this file gives the register block's before its slot 21.

## 2. The plan of forty and its reads

Gate WF10, as amended by the fourth addendum: forty trials, ten per case per arm, fixed in one committed plan
before the first trial of either case; never beside wave 2's first live batch; one read per case, after that case's
last planned trial is recorded; no re-run counts.

- **Cases.** The timer (slots 1 to 20) and the register block (slots 21 to 40). The timer's twenty may start when
  the timer's own gates are met; the register block's twenty start when its gates are met. The register block flow
  is refused by `scripts/live_eval_ci.py` (exit 6) until its gates are met and a change of its own lifts the
  refusal; this plan does not lift it.
- **Order against wave 2.** No slot is dispatched before the last record of wave 2's first live batch (W2-L1,
  `evals/plans/2026-11-18-w2-l1.md`) is recorded and that batch is read, and none is dispatched while a W2-L1 CI
  slot is running or queued: the `live-eval` concurrency group keeps one pending run, so a second dispatch would
  cancel a queued one. The two batches never interleave and never share a run window.
- **One read per case.** Each case is read once, by itself, after its own last planned trial is recorded: two
  complete groups of ten. No split by arm and no other split. "The read" in gates WF9 and WF19 and in the third
  addendum means the read of the case concerned.
- **Groups.** Whole-flow trials group by case, case digest, model, harness fingerprint, CLI, flow digest and
  purpose (`src/nirmaan/evals/levels.py`). A count is written only from ten trials (`WHOLE_FLOW_MIN`). So there are
  four groups of ten and no figure for forty, for twenty or for a case across its arms.
- **If the register block flow never runs.** The timer's read stands alone. Slots 21 to 40 are then "not run":
  never failed trials, no count for them, and this plan is not closed by counting them. No date is set by which the
  register block must start. Until its read exists, every statement of a timer count carries the sentence "the
  register block case has not run".

## 3. Slots, dispatch and records

Arms are interleaved by dispatch order within each case, starting with documents: odd slots run with documents, even
slots without. The complete list is in section 10.

One dispatch is one slot. The workflow is `.github/workflows/live-eval.yml`, job `live-eval`, dispatched from
`main`, and the counting re-judge is its `rejudge` job on a fresh checkout:

```
gh workflow run live-eval.yml -R nirmaansoftware/ip-nirmaan --ref main \
  -f case=<case> -f trials=1 -f knowledge=<on|off> -f purpose=evidence \
  -f harness=default -f expected_harness=<the arm's whole-flow fingerprint of section 6>
```

`scripts/live_eval_ci.py` refuses `trials` other than 1 and a harness other than `default` for a whole-flow case,
refuses a whole-flow dispatch with no expected fingerprint, and stops the job before any trial on a fingerprint that
is not the expected one (exit 4). The next slot is dispatched only after the whole run, `live-eval` and `rejudge`,
has finished. The counted result of a slot is the re-judged record
(`live-eval-rejudged-<run id>`), and every record reaches `main` by pull request in slot order, none held out. A
record pull request lists the slots it carries; the record names are the ones `record_run` writes. The record pull
requests pack whole records under the review's size limit.

## 4. The harness and its attempts (gate WF20)

- **Harness.** The default harness, named so since H3 (`docs/HARNESS.md`, "The default since H3"), and only it:
  `scripts/live_eval_ci.py` refuses any other for a flow case.
- **Attempts.** Three for each seated stage. The default sets them (`VARIANTS["default"] = {"attempts": 3}` in
  `src/nirmaan/runtime/harness.py`); `docs/HARNESS.md` says it for a whole flow; the CI command carries no attempts
  option, and no whole-flow trial of the forty runs with one (tests in `tests/test_live_eval_ci.py` and
  `tests/test_whole_flow_attempts.py`). No split by attempts: twenty trials on each setting would leave five per case
  per arm, under the ten at which a count may be written.
- **CLI.** Claude Code 2.1.325, the pin of `.github/live-eval/package.json`.
- **Both expected fingerprints** (recomputed on the commit and the CLI pin of section 6; each one is
  `harness_sha256(flow="whole", ...)` with the knowledge flag of its arm):
  - with documents: `sha256:d90b3c1840870ae9434b90188dbb3078473140d56b2dec9e295c515c1832adfc`
  - without documents: `sha256:8d6590f7a66ac771abf360790643763e8c43d3c267d94a5145f1e4c8bf3ae975`
- **Single-seat fingerprints that must stay as they are** (the default harness of wave 2, same CLI): with documents
  `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00`, without `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39`. A whole-flow change of any kind leaves them as they are (gate WF7).
- **Re-check.** The fingerprints, the digests of section 6 and the case digests are recomputed on the commit that
  slot 1 is dispatched from, before trial 1. Any difference means a plan amendment pull request before trial 1: no
  trial runs on a fingerprint or a digest this committed plan does not name. The same check is made before each
  slot (section 7).

## 5. The counts, word for word (gate WF20)

**Main count.** The whole-flow pass count: for each group, k of n with its Wilson interval, n the group's planned
count (ten). It is written only at ten or more planned trials complete, per group, and is never pooled and never
called a level.

**Derived count.** The third addendum's decision 2 defines it, and it is quoted here:

> Definition. For each group, j of n: the trials that passed and in which every stage records one attempt. n is the
> group's planned count, the same n as the main count k of n. It is read from each stage's recorded attempts, at the
> same single read, and the read lists each stage's attempts for every trial.
>
> Its name in the repository's records: "passed with every stage on its first attempt". It is a description of
> trials on the default fingerprint.
>
> It is reported only if the committed plan (gate WF10) holds this definition word for word before the first trial.
> It changes no main figure, makes no group, arm or second read, and never enters a level.

This plan holds that definition, and the derived count changes no main figure. A derived count not in the plan
before the first trial is never reported.

**Never claimed** (third addendum, decision 3), here or in any record or read: what the record "meant" by one
attempt; that the derived count is a result on a one-attempt harness (no trial on that fingerprint exists); a
comparison of either count with the single-seat trials of the record's fact 14 or with wave 2's per-skill evidence as
the same measure; that retries help a whole flow; any per-stage rate pooled across cases or arms; H3's frontier
figures as a committed record; any time, usage or cost figure; that forty trials can run today.

## 6. The timer's values (gate WF24; fourth addendum, decision 2, item 2)

Computed on `main` at `45a22c84` (the commit this pull request was last merged with; this file touches none of the
files below), CLI 2.1.325.

| Item | Value |
|---|---|
| Case, `flow/axil-timer`, case digest | `sha256:ff8a4afc77caee105070d996f3e29142f2fe013c411752becdc46090b7553da3` |
| Whole-flow fingerprint, with documents | `sha256:d90b3c1840870ae9434b90188dbb3078473140d56b2dec9e295c515c1832adfc` |
| Whole-flow fingerprint, without documents | `sha256:8d6590f7a66ac771abf360790643763e8c43d3c267d94a5145f1e4c8bf3ae975` |
| Flow digest, with documents | `sha256:a1aea0d36022a54be56c8d5c31831ea8ac0994f2802bd8ee8f39f6a5246ec312` |
| Flow digest, without documents | `sha256:b8608edecf2013dddfaec85e947106316f9a561a8ec74c7e3d99a7f53f8323c0` |
| Single-seat default, with documents (must stay) | `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` |
| Single-seat default, without documents (must stay) | `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39` |

The flow digests are the `flow_digest` of a replay of the case on that commit, in each arm (the skills each seated
stage is given and their digests); a skill's digest covers its card and its document, so a card or document change
moves them (fact 6 of the fourth addendum).

Digests of the gate code outside the fingerprint that the timer's checks run (fact 5 of the fourth addendum). Each
is the sha256 of the lines `<sha256 of the file>  <path>` for the tracked files under the paths, in byte order of
path (`git ls-files -z -- <paths> | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256`):

| Group | Paths | Files | Digest |
|---|---|---|---|
| Gate backends | `src/nirmaan/integrations` | 60 | `sha256:ed76c4f2d90d64ccfc13964de8aecab0220c82146aa8761d6708c0af82ed7c75` |
| Seat account | `scripts/live_eval_seat.py`, `.github/actions/live-eval-seat` | 2 | `sha256:668a329a1515d233ce2ab2048d77dbf32b30c164af4cedaf73a375145a5de388` |
| CI command | `scripts/live_eval_ci.py` | 1 | `sha256:3f396770975a7fcff4fc746c031e8694f768b921e90376c290e4fc023acf3e88` |
| Workflow, tool set and CLI pin | `.github/workflows/live-eval.yml`, `.github/actions/live-eval-setup`, `.github/actions/oss-cad-suite`, `.github/live-eval` | 5 | `sha256:486f4fced07857758db2fd688cc362a8a844e25ee0eecfeebf8c40f2297bcc9f` |

The register block's values are not in this table. For the register block, the case digest today is
`sha256:c8c8607d1e093490d118240767e0d5ce30da050b2d2e73561f80df21c7995828`; it is not a value of this plan, because the case and its judge may change before its slot 21 for the
reasons of section 9. A dated addition to this file, committed before slot 21, states for the register block: the
commit; the case digest; both expected fingerprints and both expected flow digests, recomputed on that commit and
CLI pin; the digests of the same gate code groups; and, line by line, every one of these that differs from the
timer's, with the pull request that caused it.

## 7. The freeze inside a batch, and the dispatch check (gate WF25)

From a case's first slot until that case's last planned trial is recorded, nothing merges that changes: a file in
`harness.CODE` or `harness.FLOW_CODE`; a tool definition; the CLI pin; that case's files; the card or document of
a skill that case exercises; or the gate code outside the fingerprint that the case's checks run (the four groups of
section 6). A slot is dispatched only on the digests this plan states: before each dispatch the fingerprints, the
case digest, the flow digests and the four group digests are recomputed on `main` as it is, and a difference stops
the dispatch until a plan amendment pull request is merged. Record pull requests add records only and change none of
the above. The `fw.test` change merges before the timer's slot 1 or after the timer's last trial is recorded, with
the test of gate WF7 showing the default fingerprint unchanged; if it cannot be built without a file in
`harness.CODE` or a tool definition, it returns to the council before it merges.

## 8. Stop rules

- **Failed trials.** A trial that is interrupted, hits a plan or usage limit, or ends with no model answer is a
  failed trial of its group. It is committed as failed, never held out, never re-run, never replaced (decision 11 of
  the pilot retrospective; `council/records/2026-11-15-pilot-topup-reruns.md`). No top-up, no extension, no early
  stop, no second read. An unjudged trial counts as failed in its group.
- **Limit stop.** `live_eval_ci.py trials` stops at exit 3 or a limit line; the slot is recorded failed, and the
  next slot is dispatched only after the limit has reset.
- **Whole-flow stop rule (gate WF8).** A trial whose last recorded answer has no text and an error ends the run
  (`flow_stopped`); it stays failed. On three attempts, a stage whose second model call returns no answer ends the
  stage, the later stages do not run and the trial fails (test, gate WF22).
- **Job-level stops.** Exit 2 (bad input), exit 4 (fingerprint or record mismatch), exit 6 (a case that runs seat C
  that is not confined), a failed reach test, a changed checkout or a re-judge refusal stop the job before or without
  a counted trial. The cause is fixed and the same slot is dispatched again. If a record exists for that dispatch, it
  is a trial and is committed as it is.
- **Counts are fixed here, never by outcome.** No slot is added, dropped or moved because of a result.

## 9. What may change for the register block between the two batches

Only what a gate that exists today requires: its case files and controls (gates WF3, WF15, WF16), `fw.test` as the
seat account and the credential test (WF17), the texts of WF19, and what WF23 finds for it. Its held-out checks,
mutants and scorers change only as those gates require. Any other change to the case or its judge after the timer's
slot 1 returns to the council.

The failure-to-curriculum rule applies to the timer's failed trials labelled "model", as written; it is not
suspended. A change it produces merges only outside a batch's freeze: after the timer's last trial is recorded and
before the register block's slot 21, or after slot 40. Every change, from any cause, to the card or document of a
skill given to a register block stage between the timer's slot 1 and slot 21 is listed in the dated addition with
its pull request and the skill digest before and after. The register block's read says that those cards or
documents were changed after the timer's results were known, and names the pull requests.

## 10. The measured run, and the slots

**The measured run.** Before slot 1, after this plan is merged and after wave 2's first live batch is read, one run
of the timer case is made with purpose `calibration`, with documents, on the whole-flow fingerprint of section 6,
by the same dispatch as a slot (`purpose=calibration`). It is outside the forty, a group apart by its purpose, never
counts and is not stated as a result. It measures one real run, so that records can be packed into pull requests
under the review's size limit and slots scheduled; no time, usage or cost figure from it enters a record, a read or
a public text.

All forty slots:

| Slot | Case | Arm |
|---|---|---|
| 1 | flow/axil-timer | with documents (on) |
| 2 | flow/axil-timer | without documents (off) |
| 3 | flow/axil-timer | with documents (on) |
| 4 | flow/axil-timer | without documents (off) |
| 5 | flow/axil-timer | with documents (on) |
| 6 | flow/axil-timer | without documents (off) |
| 7 | flow/axil-timer | with documents (on) |
| 8 | flow/axil-timer | without documents (off) |
| 9 | flow/axil-timer | with documents (on) |
| 10 | flow/axil-timer | without documents (off) |
| 11 | flow/axil-timer | with documents (on) |
| 12 | flow/axil-timer | without documents (off) |
| 13 | flow/axil-timer | with documents (on) |
| 14 | flow/axil-timer | without documents (off) |
| 15 | flow/axil-timer | with documents (on) |
| 16 | flow/axil-timer | without documents (off) |
| 17 | flow/axil-timer | with documents (on) |
| 18 | flow/axil-timer | without documents (off) |
| 19 | flow/axil-timer | with documents (on) |
| 20 | flow/axil-timer | without documents (off) |
| 21 | flow/axi4-lite-regs-driver | with documents (on) |
| 22 | flow/axi4-lite-regs-driver | without documents (off) |
| 23 | flow/axi4-lite-regs-driver | with documents (on) |
| 24 | flow/axi4-lite-regs-driver | without documents (off) |
| 25 | flow/axi4-lite-regs-driver | with documents (on) |
| 26 | flow/axi4-lite-regs-driver | without documents (off) |
| 27 | flow/axi4-lite-regs-driver | with documents (on) |
| 28 | flow/axi4-lite-regs-driver | without documents (off) |
| 29 | flow/axi4-lite-regs-driver | with documents (on) |
| 30 | flow/axi4-lite-regs-driver | without documents (off) |
| 31 | flow/axi4-lite-regs-driver | with documents (on) |
| 32 | flow/axi4-lite-regs-driver | without documents (off) |
| 33 | flow/axi4-lite-regs-driver | with documents (on) |
| 34 | flow/axi4-lite-regs-driver | without documents (off) |
| 35 | flow/axi4-lite-regs-driver | with documents (on) |
| 36 | flow/axi4-lite-regs-driver | without documents (off) |
| 37 | flow/axi4-lite-regs-driver | with documents (on) |
| 38 | flow/axi4-lite-regs-driver | without documents (off) |
| 39 | flow/axi4-lite-regs-driver | with documents (on) |
| 40 | flow/axi4-lite-regs-driver | without documents (off) |

## 11. What may be said, and what never is (fourth addendum, decision 4; gate WF26)

After the timer's read: for each of its two groups, the whole-flow pass count as the ruling words it, k of 10 with
its interval, with the case, case digest, model, harness fingerprint, CLI, flow digest and arm; the derived count
for the same groups, from the same records, at that read; and that the register block case has not run. After the
register block's read: the same for its two groups, always with the residual of the second addendum (decision 2,
item 6), only after security's reading of the passed trials' seat C (gate WF19).

Never said, in this plan, a record, a read or any other text:

- a combined figure: none for forty, none for a case across its two arms, none across the two reads, and no
  percentage without its n;
- "the whole-flow batch", "the whole-flow result" or "the whole flow" for the timer's twenty alone: they are "the
  timer case's twenty trials";
- a comparison between the two cases, in either direction;
- that the two cases ran on the same harness because their fingerprints are equal: the digests of this plan, and of
  its dated addition, are what may be cited;
- that a later register block count shows the effect of a curriculum change, or that documents help beyond the two
  arm counts stated side by side with their intervals;
- a timer count in any text before the timer's read (the generated list in `capability/levels.json` writes a
  group's count when its tenth record merges; that is not the read, and nothing cites it before the read);
- a count for slots that did not run, or those slots as failed trials;
- anything the ruling and its addenda already forbid: a level, a score or a bar, a per-stage skill rate, the timer
  case as independent verification (gate WF11), any figure outside the repository's records (gates WF12 and WF18),
  any time, usage or cost figure.

## 12. Statement for the timer flow: what a failed run's log excerpt can carry back to a seat on a retry (gate WF23)

This is the statement of gate WF23 for the timer flow, made from the recorded reach tests and the committed code,
and put to security's key on this pull request. The fourth addendum also asks security to confirm here that the
timer path raises no reach question beyond this gate. The register block flow's statement is not made here: it
comes with gates WF17 to WF19, before its first trial.

**What returns.** On a retry within a stage, the seat is given the repair text and, for each failed tool run of the
refused attempt, the run's summary and a bounded excerpt of its log: at most 20 lines (`EXCERPT_LINES`), each cut to
240 characters (`EXCERPT_WIDTH`), the lines that match `error|warning|fail|fatal|assert|mismatch` first, else the
last lines (`src/nirmaan/runtime/harness.py`, `src/nirmaan/runtime/files.py:excerpt`,
`src/nirmaan/runtime/context.py:_failed_run`). Nothing else of a failed run comes back.

**Where it can arise.** Only at a stage with a tool gate. In the timer flow's workflow the requirements, interface
specification and microarchitecture stages carry the review requirement and no tool gate
(`src/nirmaan/company/workflows.py`, the `block_design` stages), so no log returns there. The RTL stage's gates are
`lint.run`, `simulator.run` and `synth.run`; `formal.run` applies only when the stage produces a `formal_spec`,
which the stage's outputs (`rtl_source`, `testbench`) do not include. The held-out checks run after the last stage
and return nothing to any seat: no retry follows them.

**What the logs hold.** Tool output: lint and synthesis messages that quote the seat's own source lines, and the
simulator's output, which includes what the seat's own testbench prints. The simulation runs as the account
`nirmaan-seat` through the `vvp` wrapper (`docs/LIVE_EVAL_EVIDENCE.md`, section 6).

**What the recorded reach tests show.** The reach test of that section runs through the same `vvp` before any trial
and fails the job unless every probe is denied. The recorded runs show, as that account, every read denied (130
files not read, 4 folders not listed, both read canaries denied: run 44555981466), the network refused for IPv4
TCP and UDP and with no route or refusal for IPv6 (runs 44555981466 and 44563164453), the writable tool trees taken
away (run 44327170136), and no credential canary in its environment or in any `/proc/<pid>/environ`. A canary value
in a run's log or results fails the job. So the excerpt of a timer run's log cannot carry the plan credential, a
reference answer, a held-out file or mutant, the records, or anything else under the probed targets. The reach test
is a set of named targets, and this statement goes no further than them.

**What stops the rest.** Before a gate runs seat HDL, `eda_guard` refuses a system task outside its allow list
(so `$fopen`, `$readmemh`, `$system`, `$c`), DPI, a `` `systemc_ `` block, and an `` `include `` that leads outside
the run's own folder (`docs/GATE_INPUTS.md`, section 2), so a testbench cannot print a host file into the log.
`$value$plusargs` and `$test$plusargs` are allowed; what they read is the command line of the seat's own simulator
run (inference: the files it names are the run's own).

**What it can carry.** The seat's own earlier output, the tools' messages about it, and the names of the run's own
files. From outside the run it carries nothing that the probes above show denied.

**What is not claimed.** That the account can read nothing the host's file modes allow every account to read, beyond
the probed targets; anything about a case that links seat-written C, which is the register block flow's and is not
run by this plan; and any effect of the retries on the result.

## 13. Conditions before slot 1

Each is a gate of the record, met on `main` before the timer's first trial, and recorded by the pull request that
meets it, not here: the read of wave 2's first live batch; gates WF3, WF4, WF8, WF9 and WF17 for the timer; WF10 as
amended and WF24 (this file); WF20 (sections 4 to 6 and 10); WF21 and WF22 (the tests named in sections 4 and 8 and
the line of `docs/HARNESS.md`); WF23 (section 12, with security's confirmation); WF25 (section 7); WF26 (section 11);
and the measured run of section 10. Slot 1 is dispatched only when each is true on the commit it runs from.

This plan is not a record and not a ruling. It is a document, committed once, and a change after slot 1 is made only
by a council ruling.

## 14. Dated addition (2026-11-22): security's position on the timer path

The fourth addendum leaves open, for security (not seated): "to confirm, in the plan's pull request, that the timer
path raises no reach question beyond gate WF23". This plan merged without that confirmation. The security seat then
gave its position as a read-only process of its own (`council/security.md`; a seat never changes the repository),
against `main` at d0ba269d, on that question alone. This section records what it said. It is the seat's position, not
a council ruling, and it changes nothing in sections 1 to 11: no count, slot, arm, harness, fingerprint or digest.

**Not confirmed.** Security found two reach questions on the timer path that section 12 does not cover, in its words:

1. "Can a timer seat that declares a `formal_spec` make `formal.run` and `formal.cover` run SBY, Yosys and a solver
   over its setup, which section 12 says does not happen? Settled by a test of the flow's RTL stage with a seat
   `.sby`." Its facts: the RTL stage of the block design workflow runs `formal.run` and `formal.cover` whenever a
   `formal_spec` was produced (`src/nirmaan/company/workflows.py:95-98`, `:635-640`); the seat names each file's
   kind itself and nothing checks it against the stage's expected outputs (`src/nirmaan/runtime/model.py:435-460`);
   earlier RTL seats wrote 15 `.sby` files in committed records (`docs/GATE_INPUTS.md:113`); SymbiYosys and Yices
   are installed in the job (`docs/LIVE_EVAL_EVIDENCE.md:203-206`). So the sentence of section 12 that `formal.run`
   applies only to a stage whose outputs include a `formal_spec` is, by security's reading, not what the code does.
   Security put its confidence that this can happen in practice at medium: no test it read runs a seat-declared
   `.sby` through this stage.
2. "Is the `eda_guard` allow list enough to keep seat files from causing code to run in the runner-account tools
   (Icarus compile, Verilator lint, Yosys, SBY), which run in the step whose parent process holds the plan
   credential, with no recorded probe? Settled by running them as the seat account with a recorded reach test, or
   by a council ruling that names the screen as the control." Its facts: only `vvp` runs as `nirmaan-seat`, and the
   other tool runs stay with the runner account (`docs/LIVE_EVAL_EVIDENCE.md:219-230`, `:320-326`); the trials step
   holds `CLAUDE_CODE_OAUTH_TOKEN` (`.github/workflows/live-eval.yml:249-254`), which any process of the runner
   user can read in `/proc/<pid>/environ` (`docs/LIVE_EVAL_EVIDENCE.md:221-223`); a tool run's own environment drops
   credential names (`src/nirmaan/integrations/eda.py:418-424`); `eda_guard` screens input before a run and does
   not confine it (`src/nirmaan/integrations/eda_guard.py:12-17`); the recorded reach test probes the cocotb path
   through `vvp` only.

**Where security saw no question beyond gate WF23.** The seat model in a trial is given no tools and no MCP server
(`src/nirmaan/runtime/harness.py:145-146`, `src/nirmaan/runtime/claude_code.py:143`); a retry carries back only the
run's summary and the bounded log excerpt of section 12 (`src/nirmaan/runtime/context.py:255-262`,
`src/nirmaan/runtime/files.py:94-114`); the `rejudge` job holds no secret and follows the council's reading of gate
WF17 (`council/records/2026-11-19-seat-c-live-refusal.md`, decision 3). Who can read the artifacts: no view.

**What it means for slot 1.** Section 13 lists "WF23 (section 12, with security's confirmation)" among the conditions
before slot 1. That condition is not met. Slot 1 is not dispatched until each question above is settled in the way
security named: the first by a test of the flow's RTL stage with a seat `.sby` (and section 12 corrected by a plan
amendment if the test shows the formal gates run), the second by the runner-account tools running as the seat account
with a recorded reach test, or by a council ruling that names the screen as the control. Each is recorded by the pull
request that settles it.

## 15. Dated addition (2026-11-22): where the timer's records are committed

Section 3 says the record names are the ones `record_run` writes. Every CI dispatch writes into a fresh folder, so
two slots of one arm on one day get the same record name. To keep the names as written and still tell the slots
apart, a slot's record is committed at `evals/results/g3-timer/slot-NN/<record name>/`, with `NN` the slot number in
two digits (a failed slot's `causes.md` sits beside its `manifest.json`). The name is never changed; the path is
the record's identity. The register block's folder is named in the dated addition that section 9 requires before its
slot 21. This changes no count, slot, arm, harness, fingerprint or digest, and no record. What reads records by
path:

- `tests/test_whole_flow.py` asserts the structure of any committed whole-flow record (all trials whole-flow, each
  with its stages and flow digest, and a place under a `g3-timer` slot folder) in place of the
  absence it asserted before the first record.
- `scripts/failure_curriculum.py` reads `causes.md` and trial files at any depth, and keys a failure by the
  record's path under `evals/results` (a flat record keeps its bare name); an answer in a pull request names
  that key.
- `src/nirmaan/evals/levels.py` and `scripts/capability_levels.py` already find manifests at any depth and list
  records by path; a test now covers two same-named records in two slot folders.

## 16. Dated addition (2026-11-22): question 1 of section 14 settled by a test, and section 12 corrected

Security's first question (section 14) is settled by `tests/test_whole_flow_reach.py`. The answer is yes: a timer
seat that declares a `formal_spec` makes `formal.run` and `formal.cover` run SymbiYosys, with Yosys and the solver
under it, over its own setup. This section records what the test shows and corrects the sentence of section 12 that
the code does not bear out. It changes nothing in sections 1 to 11: no count, slot, arm, harness, fingerprint or digest.

**What the test shows.** Both tests replay `flow/axil-timer` through `run_flow` on the default harness (three
attempts per stage), with no model call. Each stage gives the case's reference answer, and at the RTL stage the
answer also declares one more file, of kind `formal_spec`: the committed `tests/fixtures/rtl/axil_timer/axil_timer.sby`,
which reads only the seat's own `axil_timer.v`.
- `tests/test_whole_flow_reach.py:76`: the RTL stage's outputs are `rtl_source` and `testbench`, yet its prompt names
  the input contracts of `formal.run` and `formal.cover` and says the formal requirement "applies only if you produce
  a formal_spec file". Nothing refuses the extra kind: the stage reaches review on its first attempt with the `.sby`
  recorded, and its gate runs are `lint.run`, `simulator.run`, `synth.run`, `formal.run` and `formal.cover`. Both
  formal runs ran over the seat's own setup and RTL (their `sby` and `sources` are the seat's files), and each log is
  SymbiYosys's own (`DONE (PASS`). So the RTL stage runs the formal gates whenever the seat writes a `formal_spec`
  (`src/nirmaan/company/workflows.py:95-98`, `:635-640`), as security read.
- `tests/test_whole_flow_reach.py:110`: when the first attempt's setup is a bounded check of four steps, both formal
  runs fail, the attempt is refused, and the retry's prompt carries each failed formal run's summary and a log
  excerpt with lines SymbiYosys wrote. So a formal run's log returns to the seat on a retry, as any gate's does.

**Section 12, corrected.** Section 12 is read with these changes, for the timer flow:
- *Where it can arise.* The RTL stage's gates are `lint.run`, `simulator.run` and `synth.run`, and also `formal.run`
  and `formal.cover` on any attempt whose answer declares a file of kind `formal_spec`. The seat chooses that: the
  stage's outputs do not list the kind, its prompt names both gates, and nothing refuses it. The sentence of section
  12 that `formal.run` applies only when the stage's outputs include a `formal_spec` is withdrawn.
- *What the logs hold.* Also SymbiYosys's log: its own lines on the job (the run's temporary folder, the commands it
  started, the engine and the solver's status, the steps checked, and the assertions and covers by file and line of
  the seat's own source). The excerpt is bounded as section 12 says.
- *What the recorded reach tests show.* That paragraph does not cover the formal runs. They are not `vvp`, so in the
  `live-eval` job they run today as the runner account, not as `nirmaan-seat` (`docs/LIVE_EVAL_EVIDENCE.md:219-230`,
  `:320-326`), and no recorded probe runs through them. The only check before them is the input screen: the SBY
  checks of `docs/GATE_INPUTS.md:78-89` and the Verilog check on the files the setup reads (`docs/GATE_INPUTS.md`,
  section 2). This section makes no claim that the screen keeps a host file out of a formal log.
- *What it can carry.* Nothing is claimed here for a formal run beyond what the test shows: the seat's own setup and
  RTL go in, and SymbiYosys's summary and log excerpt come back on a retry. The formal runs are tools that read
  seat-written files as the runner account, in the step whose parent process holds the plan credential, so they fall
  under security's second question (section 14), which the council record of section 17 settles.

**What it means for slot 1.** Question 1 is settled: the formal gates can run on the timer path. This section
corrects only the formal sentence of section 12 and adds what the formal logs hold. With this test on `main`, decision
5 of `council/records/2026-11-22-eda-tools-seat-account.md` applies in its first branch (section 17): `sby` is wrapped,
so SymbiYosys, Yosys under it and the solver run as the seat account over the seat's `.sby` before slot 1, with their
probes and fixtures (gates ET1 to ET3), and what section 12 says of the formal gates' logs is restated by the plan
amendment of gate ET6. This section adds no condition before slot 1 and removes none; the WF23 condition of section
13 is met only as section 17 says. Refusing a seat `formal_spec` in the timer flow would have been another way to
close question 1; it is not taken, and the record's route is the seat account.

## 17. Dated addition (2026-11-22): the second question of section 14 is settled by a council record

Section 14 says the second question (the runner-account tools over seat files, with the `eda_guard` screen as the
only control) is settled by those tools running as the seat account with a recorded reach test, or by a council
ruling that names the screen as the control. The council met on it:
`council/records/2026-11-22-eda-tools-seat-account.md`. This section records what that record rules for this plan. It
changes nothing in sections 1 to 11: no count, slot, arm, harness, fingerprint or digest.

**The way is the first one.** The council did not name the screen as the control. In the meeting, seats found on a
local machine (not recorded evidence) that the screen passes seat Verilog which a tool then acts on by opening a
file outside the run (the record's fact 9). The record rules that every tool step of the timer path that reads
seat-written Verilog runs as the seat account in the live evaluation's jobs, with reach probes through each such
tool, and that the screen is repaired with recorded must-refuse fixtures whatever the route.

**What slot 1 now waits for.** The question is settled as to the way, not yet as to the condition. "WF23 (section
12, with security's confirmation)" in section 13 is met for this question only when gates ET1 to ET8 of that record
are met on `main`: the screen repair with its fixtures (ET1); the RTL stage's tools as the seat account with no
fallback (ET2); the reach probes through each wrapped tool, recorded in a replay on `main` and run as a gate in the
`live-eval` job (ET3); the held-out checks' compile as the seat account with that run's inputs only, or the record's
named fallback (ET4); a replay showing the reference answer and the controls unchanged (ET5); a plan amendment (ET6);
the fingerprints shown unchanged and every pin recomputed (ET7); and the texts (ET8). Slot 1 is not dispatched before
then.

**What the plan amendment of gate ET6 will change, before slot 1.** The build moves the "Seat account" and "Gate
backends" digests of section 6; the amendment restates them with the pull request that moved each. It corrects
section 12, whose sentence "so a testbench cannot print a host file into the log" is not supported as written (the
record's fact 15) and is not relied on from today. It states that a screen refusal, or a tool denied as the seat
account, is a failed run and a trial that ends on it is a failed trial, never removed or repeated; that the timer's
read lists, for each passed trial, whether a seat HDL file holds an include, changing no count; and what is pinned
beyond the four groups. The measured run of section 10 is made after the last of these merges.

**The first question of section 14** (a seat that declares a `formal_spec`) is settled separately, by a test, in a
pull request of its own (ip#435, open when this was written; its dated addition takes the number 16, which is why
this section is 17). The record's decision 5 says what follows for SBY
under each result of that test: if the test on `main` shows that the formal gates run over a seat's setup on the timer
path, `sby` is among the tools that run as the seat account before slot 1 (gates ET1 to ET3), and whatever section 12
says of the formal gates' logs is restated by the plan amendment of gate ET6.

## 18. Dated addition (2026-11-23): the plan amendment of gate ET6

This is the plan amendment that gate ET6 of `council/records/2026-11-22-eda-tools-seat-account.md` asks for
(decision 7, item 2). It also shows gate ET7 for the pull requests named below and holds the plan's part of gate ET8
(decision 8). `council/records/2026-11-23-wave-2-close-meeting-1.md` (decision 4, "The whole-flow batch", and
decision 5, item 1) has it merge before any dispatch of the timer case. It changes no code, no case, no record and no
level: no file in `harness.CODE`, `LOOP_CODE` or `FLOW_CODE`, no tool definition, no CLI pin, no card and no knowledge
document is touched. It changes no count, slot, arm, harness, attempt, fingerprint, main count or derived count.
Unlike sections 14 to 17 it does change what sections 6, 7 and 12 say, as the record asks; where those sections and
this one differ, this one rules.

### 18.1 The timer's values, restated (section 6)

Recomputed on `main` at `817cc0d6` (the commit this pull request was last merged with; this file touches none of the
files below), CLI 2.1.325: the fingerprints with `harness_sha256(flow="whole", ...)` and the single-seat ones with
`harness_sha256(...)`, each with the knowledge flag of its arm; the case digest with `case_digest`; the flow digests
as a replay computes them before any stage runs (the skills each seated stage is given, and their digests); the group
digests with the command of section 6.

| Item | Since section 6 | Value |
|---|---|---|
| Case, `flow/axil-timer`, case digest | unchanged | `sha256:ff8a4afc77caee105070d996f3e29142f2fe013c411752becdc46090b7553da3` |
| Whole-flow fingerprint, with documents | unchanged | `sha256:d90b3c1840870ae9434b90188dbb3078473140d56b2dec9e295c515c1832adfc` |
| Whole-flow fingerprint, without documents | unchanged | `sha256:8d6590f7a66ac771abf360790643763e8c43d3c267d94a5145f1e4c8bf3ae975` |
| Flow digest, with documents | unchanged | `sha256:a1aea0d36022a54be56c8d5c31831ea8ac0994f2802bd8ee8f39f6a5246ec312` |
| Flow digest, without documents | unchanged | `sha256:b8608edecf2013dddfaec85e947106316f9a561a8ec74c7e3d99a7f53f8323c0` |
| Single-seat default, with documents (must stay) | unchanged | `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` |
| Single-seat default, without documents (must stay) | unchanged | `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39` |

The gate code groups. The first four are section 6's; the last three are pinned from this amendment on (section
18.2). "Moved by" names each merge that changed a value, with the value on that merge commit.

| Group | Paths | Files | Moved by | Digest |
|---|---|---|---|---|
| Gate backends | `src/nirmaan/integrations` | 60 | ip#444 (`c99ef1fe`: `3a7ad495...`), ip#451 (`cec29b2f`: `72e5a814...`), ip#445 (`817cc0d6`: `eac184ec...`) | `sha256:eac184ecc60ae35bdc88e6f66c2fa3aceaabe4c32f62066e951d7d5e84e835f9` |
| Seat account | `scripts/live_eval_seat.py`, `.github/actions/live-eval-seat` | 2 | ip#444 (`c99ef1fe`: `00f3b35b...`), ip#451 (`cec29b2f`: `4abec1ad...`) | `sha256:4abec1ad1bb4fe9e48afb333c619c1d07ccd2e5df80b62f3142dc8ad750fa446` |
| CI command | `scripts/live_eval_ci.py` | 1 | none | `sha256:3f396770975a7fcff4fc746c031e8694f768b921e90376c290e4fc023acf3e88` |
| Workflow, tool set and CLI pin | `.github/workflows/live-eval.yml`, `.github/actions/live-eval-setup`, `.github/actions/oss-cad-suite`, `.github/live-eval` | 5 | ip#444 (`c99ef1fe`: `12c0fe97...`), ip#451 (`cec29b2f`: `09083077...`) | `sha256:09083077e0237a7e2b1ed89152d3d5b8f31836a03c8b78500b471d802f8e64d7` |
| Reach test | `scripts/live_eval_reach.py` | 1 | newly pinned | `sha256:581a4cebb61899090a1741fdbea49e51b57decdebdf0cb11c58562f60b4b93c0` |
| Held-out scorers | `src/nirmaan/evals/scorers.py` | 1 | newly pinned | `sha256:5f4f7909a3207f3837d2af7ad60b85c0bae620e1d461afde57aea0d2a592ecb4` |
| Stage gates | `src/nirmaan/company/workflows.py` | 1 | newly pinned | `sha256:bcd15f8204e55f142f266afdd8e12a4947c7f6276382dd18f4c9893e616a9873` |

Section 6's values for the first four groups were `ed76c4f2...`, `668a329a...`, `3f396770...` and `486f4fce...`;
section 6 keeps them as the record of what moved. Every check of sections 4 and 7 is made against this table: "the
four groups of section 6" in section 7 reads "the seven groups of section 18.1", and "the digests of section 6" in
sections 4 and 7 reads "the values of section 18.1".

### 18.2 What is pinned beyond the four groups

The record asks which of `scripts/live_eval_reach.py`, `src/nirmaan/evals/scorers.py` and
`src/nirmaan/company/workflows.py` this plan pins (its fact 13: they are in no fingerprint and were in no group). It
pins all three, each as a group of its own in section 18.1:

- `src/nirmaan/company/workflows.py` sets the timer's stages and which gates the RTL stage runs, the formal gates
  on a seat `formal_spec` included (section 16).
- `src/nirmaan/evals/scorers.py` runs the two held-out checks, and since ip#444 stages check 1's files for the run
  (`eda.HELD_OUT_STAGED`) so that the seat account compiles them; a change there changes the judge.
- `scripts/live_eval_reach.py` holds the probes that the `live-eval` job runs as a gate before its first trial
  (section 18.3); a change there changes what that gate shows.

So each falls under the dispatch check of section 7 (a moved digest stops the dispatch until a plan amendment
merges) and under its freeze from slot 1 until the timer's last trial is recorded. A change to one of them that a
register block gate needs merges before the timer's slot 1 or after its last trial is recorded, as section 7 already
says of `fw.test`.

### 18.3 Section 12, corrected

The record's fact 15 finds one sentence of section 12 not supported, and decision 5 has what section 12 says of the
formal gates restated here. Section 12 is read with these changes, for the timer flow; its parts not named here stand,
as section 16 corrects them.

- *What stops the rest.* The sentence "so a testbench cannot print a host file into the log" is withdrawn. The input
  screen (`eda_guard`) is the first check before any step, on every machine. Since ip#445 it refuses the two classes
  of the record's fact 9, by the rules of `docs/GATE_INPUTS.md`, section 7, and it is claimed only for the forms its
  recorded fixtures name (`tests/test_gate_inputs.py`, through `lint.run`, `simulator.run`, `synth.run`, `formal.run`
  and `formal.cover`; CI's test job in run 45085382759, on ip#445's merged head `cde63b5b`, holds 289 cases of that
  file in its JUnit files, none skipped). It screens input; it confines nothing. It is not claimed to read as a
  tool's preprocessor reads, to stop reads or code in general, or to cover a fault in a tool's parser.
- *What the recorded reach tests show.* In the `replay`, `live-eval` and `rejudge` jobs, the steps of the timer path
  that read seat-written Verilog run as `nirmaan-seat`, each by a wrapper in `/opt/nirmaan-seat/bin` with no
  fallback to the runner (ip#444): `verilator --lint-only` (`lint.run`), `iverilog` and `vvp` (`simulator.run`),
  `yosys` (`synth.run`), and `sby` with the Yosys and the solver it starts (`formal.run`, `formal.cover`). The
  account is given the run's own directory and that run's input files. The held-out checks' Icarus compile runs
  the same way, with check 1's files staged for the run as check 2's are (the record's decision 3, item 1; its
  fallback was not built). Replay run 45073595509, dispatched on `main` at `c99ef1fe`, records it
  (`evals/flow/tool_reach_record.json`, ip#452). In its `replay` job and again in its `rejudge` job, 19 of 19 were
  as required. Each of Icarus through `simulator.run`, Verilator through `lint.run`, Yosys through `synth.run` and
  SBY through `formal.run` (with a `formal.cover` control) passed a control on seat files and denied three probes: a
  canary in the checkout, a runner-only canary, and the parent's `/proc/<pid>/environ` holding a credential-named
  canary. The held-out compile read its own staged judge file, and a canary beside that file was denied. In both job
  records, no canary value was in the log, summary or result file of any of those probe runs. The `live-eval` job runs the same probes as a gate before its
  first trial and stops the job unless every probe is denied; it has no recorded run before slot 1. The vvp reach
  test and runs of section 12 stand as written.
- *The formal gates.* The paragraph of section 16 that says the formal runs run as the runner account with no
  recorded probe through them is withdrawn from ip#444 on: `sby` runs as `nirmaan-seat` in those jobs, and run
  45073595509 probes it as above. What section 16 says the formal logs hold, and that they return on a retry, stands.
- *What stays with the runner.* The `nirmaan` process (the screen, the harness, the scorers' reading of results),
  and any Verilator run that is neither a lint nor `coverage.read`'s build, by the stated rule of ip#444 and ip#451
  (`as_runner`, `eda.seat_tool`). No step of the record's facts 5 and 6, which list the timer path's tool steps, is
  such a build.
- *What it can carry.* The seat's own earlier output, the tools' messages about it, and the names of the run's own
  files. From outside the run, nothing is claimed beyond this: in run 45073595509 the probed targets were denied to
  those tools as that account.
- *What is not claimed*, adding to section 12's list (the record's decision 8): that seat files are confined,
  sandboxed or isolated; that the screen is enough; that the credential is safe, or that it was or could not be read;
  anything about files every account may read, beyond the probed targets; the local runs of the record's fact 9 as
  evidence (the fixtures of ip#445 replace them); and that the `live-eval` job has a recorded probe run before slot
  1. The residual, as the record and the wave 2 close record state it: screen classes nobody has found, faults in a
  tool's parser, and files any account may read.

### 18.4 A refused or denied run is a failed run

A run that the screen refuses, or that fails because a tool is denied as the seat account (the wrapper refuses an
input or the run, or the tool cannot open a file the account is not given, such as an include of a file the gate was
not given), is a failed run of that gate, decided in advance as the record's fact 12 says: nothing of it passes. At
a stage it is handled as any failed run, within the stage's attempts (section 4). A trial that ends on it is a failed
trial of its group: committed as failed, never removed, never repeated and never replaced (section 8). In a held-out
check it fails the check wherever the check needs that run to pass, and a refused mutant run is never counted as
caught (`src/nirmaan/evals/scorers.py`). This is not a job-level stop of section 8: the job-level stop is the reach
test before any trial, which, when a probe is not denied, stops the job with no trial run.

### 18.5 The include listing at the read

The timer's read lists, for each passed trial of each of its two groups, whether any HDL file a seat wrote in that
trial (a file of kind `rtl_source` or `testbench`, or named `*.v`, `*.sv`, `*.vh` or `*.svh`, in any stage's recorded
answer, at any attempt) holds an `` `include `` directive, and where one does, the stage, the attempt, the file and
the line. The listing is read from the committed records at the same single read. It changes no count, makes no
group, split or second read, and a passed trial stays passed.

### 18.6 Gate ET7, shown

The merges since section 6 was computed at `45a22c84` that meet gates ET1 to ET5 or move a value of section 18.1:
ip#444 (ET2 to ET4, `c99ef1fe`), ip#451 (gates W2C3 and W2C4 of the wave 2 close record, on the same account,
`cec29b2f`), ip#452 (the ET3 record, `fdf01d68`) and ip#445 (ET1, `817cc0d6`). ET5 is shown by the same run
45073595509: the timer's reference answer passed `lint.run`, `simulator.run` and `synth.run` with the tools as the
seat account; check 1 passed on its staged testbench; check 2 passed clean with 4 of 4 mutants failing; the re-judge
gave the same result. The record of that is `evals/flow/et5_replay_record.json`, copied from the run's uploads, with
`tests/test_live_eval_seat.py::test_the_committed_et5_replay_record_is_from_main_names_the_timer_and_shows_exactly_what_et5_claims`.
It holds no run of the timer's controls or of the committed fixtures, which the run's uploads do not hold; those are
this repository's tests on the same commit.
The timer's controls, its mutant sweep and the committed gate fixtures as the seat account are in run 45119522138 and
its record `evals/flow/et5_controls_record.json` (section 21).

- No file in `harness.CODE`, `LOOP_CODE` or `FLOW_CODE` and no tool definition changed:
  `git diff --name-only 45a22c84 817cc0d6` over those files and `src/nirmaan/company/tools.py` is empty, and these
  tests pass on `817cc0d6`: `tests/test_whole_flow_dispatch.py` (gate WF7),
  `tests/test_live_eval_seat.py::test_the_tools_as_the_seat_account_change_no_fingerprint` and
  `tests/test_gate_inputs.py::test_no_file_this_milestone_changes_is_harness_code`.
- The four fingerprints, recomputed with CLI 2.1.325 on each merge commit (`c99ef1fe`, `cec29b2f`, `fdf01d68` and
  `817cc0d6`, which is also the commit of section 18.1), are the values of section 18.1, unchanged.
- Every value of section 18.1 is recomputed again on the commit the measured run is dispatched from and on the commit
  of each slot (section 7); a difference stops the dispatch until a plan amendment merges.
- The measured run of section 10 is made after this amendment merges. No dispatch of the timer case with a model, no
  measured run and no slot, has happened before it: in every run of `.github/workflows/live-eval.yml` since ip#354
  made a whole-flow case dispatchable, the `live-eval` job was skipped (each was a replay, run 45073595509 the last
  before this amendment).

### 18.7 What slot 1 still waits for

With this merge, gate ET6 is met and ET7 is shown for every merge named above. ET1 to ET5 rest on the pull requests
and runs named in sections 18.3 and 18.6. For ET8, this section is the plan's part; the documents it names are
`docs/GATE_INPUTS.md` from ip#445, `docs/GATE_INTEGRITY.md` from ip#444, ip#451 and ip#445, and
`docs/LIVE_EVAL_EVIDENCE.md`, section 6, from ip#444 and ip#451, and that every text follows decision 8 is
qa-evidence's to confirm. Gate
ET9 is the register block's, before slot 21. This section adds no condition before slot 1 and removes none: section
13 stands, with the measured run of section 10 after this merge. The re-measure batch of the wave 2 close record and
the timer's twenty are never interleaved: one records its last trial before the other dispatches its first.

## 19. Dated addition (2026-11-23): security's confirmation of gate WF23, gate ET8, and the conditions before slot 1

Section 13 lists "WF23 (section 12, with security's confirmation)" among the conditions before slot 1, and section 17
has that condition met only when gates ET1 to ET8 of `council/records/2026-11-22-eda-tools-seat-account.md` are
met. Section 18.7 leaves ET8 to qa-evidence. Each seat gave its position as a read-only process of its own
(`council/security.md`, `council/qa-evidence.md`; a seat never changes the repository), against `main` at
`02cfa87f` (the merge of ip#454). This section records what each said; a seat's position is not a council ruling.
This pull request changes this file, `docs/GATE_INPUTS.md`, `docs/GATE_INTEGRITY.md` and `docs/LIVE_EVAL_EVIDENCE.md`
only. It changes no count, slot, arm, harness, attempt, fingerprint, main count, derived count or digest of section
18.1: no file in `harness.CODE`, `LOOP_CODE` or `FLOW_CODE`, no tool definition, no CLI pin, no card, no knowledge
document and no file of the seven groups is touched.

### 19.1 Security: gate WF23 confirmed, no reach question beyond it

In its words: "I confirm section 12, as corrected by sections 16 and 18.3", and "REACH QUESTION: none beyond WF23".
Its facts, as it cited them: all three jobs set `NIRMAAN_SEAT_TOOLS` and a seat tool starts only through the
account's wrapper or the run is refused (`.github/workflows/live-eval.yml`, `src/nirmaan/integrations/eda.py`); the
wrapped tools and the one Verilator use that stays with the runner (`scripts/live_eval_seat.py`), which no timer gate
is; 19 of 19 in both jobs of run 45073595509 (`evals/flow/tool_reach_record.json`); the `live-eval` job's reach step
stops the job unless every probe is denied, and the trials step does not run after it fails
(`scripts/live_eval_reach.py`, `.github/workflows/live-eval.yml`); a retry carries back only the summary and the
bounded excerpt of section 12. On what stays with the runner (the `nirmaan` process and Claude Code, in the step
that holds the token), it inferred that neither runs seat content as code, the CLI having no tools and no MCP server
(`src/nirmaan/runtime/harness.py`). It found the `live-eval` job's want of a recorded probe run not a reach
question, since that gate stops the job on the commit it runs from.

It named one gap, in its words: "the committed record tested the seat-account code as it was at c99ef1fe. ip#451
changed that code afterwards ... The gate covers the current code when a run is dispatched; the committed record does
not cover it." Its confidence: high on the code reading; medium on one inference, that the network and write denials,
probed through `vvp` only, hold for the other wrapped tools because they run as the same account.

Its must-haves, as it wrote them:

1. Before slot 1, the tool reach records of the measured run's `live-eval` and `rejudge` jobs
   (`live-eval-tool-reach-trials-<run id>` and `live-eval-tool-reach-rejudge-<run id>`) are committed beside the ET3
   record, with the run id and commit. If any probe was not denied, no slot is dispatched.
2. Each slot's tool reach records are committed with its record, in the slot's folder of section 15.
3. The residual stays as section 18.3 states it.

Item 3 holds (section 18.3). Items 1 and 2 are not taken into this plan here. Decision 2, item 3 of
`council/records/2026-11-22-eda-tools-seat-account.md` says "Nobody says the `live-eval` job has a recorded run before
slot 1: it has none until slot 1 (qa-evidence)", and decision 8 lists, among what is never said, "that the
`live-eval` job has a recorded probe run, before slot 1". Item 1 would commit such a record before slot 1. qa-evidence
asks the chair to reconcile the two (section 19.4), and this plan does not decide between a seat's must-have and a
council record. Security gave its confirmation with item 1 as a must-have before slot 1, so slot 1 waits for the
chair's word on it (section 19.6).

### 19.2 qa-evidence: gate ET8 not met on `02cfa87f`, and what this pull request changes

In its words: "ET8 is not met. The account texts follow decision 8. Six passages in the screen texts and in section
12 do not." It found that the reach record, `docs/LIVE_EVAL_EVIDENCE.md` section 6 on the account, the classes and
fixtures of `docs/GATE_INPUTS.md` section 7 and its residual, and the "What is not claimed" list of section 18.3
follow decision 8. Its six findings, each with what this pull request does:

1. Text that says the screen reads as a tool's preprocessor reads (`docs/GATE_INTEGRITY.md`, the heading and close
   of the ET1 paragraph; `docs/GATE_INPUTS.md`, section 2, on strings and comments). Reworded to what the record
   allows: the check refuses, before any step, the two classes of fact 9 in the forms its recorded fixtures name, and
   is not claimed to read as a tool reads.
2. "a reach test in each job shows the token unreadable" (`docs/GATE_INTEGRITY.md`, section 6). Reworded: the reach
   test shows its probes denied to the account, a credential-named canary in the parent's environment among them,
   with no claim about the token itself.
3. `docs/GATE_INTEGRITY.md` did not state the residual. It now states it in the ET1 paragraph and at the account
   paragraph of section 6, as the record and `council/records/2026-11-23-wave-2-close-meeting-1.md` state it: screen
   classes nobody has found, parser faults in a tool, and files any account may read.
4. Four sentences of `docs/GATE_INPUTS.md` that say the screen stops ways out or reads in general (the allow list
   paragraph, the history scan's "no committed trial reached the host", the log paragraph's "they carry no other
   file's content", and the C source paragraph). Each is reworded to what the fixtures and sections 2 and 7 show; the
   history scan is said to predate section 7.
5. "every gate refuses, before it runs, HDL with a way out to the host" (`docs/LIVE_EVAL_EVIDENCE.md`, section 6).
   Reworded: every gate refuses, before it runs, the constructs its recorded fixtures name.
6. Section 12's sentence "So the excerpt of a timer run's log cannot carry the plan credential, ..." stands by
   section 18.3 ("The vvp reach test and runs of section 12 stand as written") and contradicts 18.3's own list of
   what is not claimed. Withdrawn by section 19.3.

The wording changes keep each document's line count where a line of it is cited elsewhere (`docs/GATE_INPUTS.md`
and `docs/LIVE_EVAL_EVIDENCE.md`); `docs/GATE_INTEGRITY.md` gains lines only after the lines cited.

### 19.3 Section 12, one more sentence withdrawn

In *What the recorded reach tests show*, the sentence "So the excerpt of a timer run's log cannot carry the plan
credential, a reference answer, a held-out file or mutant, the records, or anything else under the probed targets."
is withdrawn. It reads instead: in those runs the probed targets, a credential-named canary among them, were denied
to that account through `vvp`; nothing is claimed of the credential itself, or of a target not probed. In section
18.3, "The vvp reach test and runs of section 12 stand as written" reads "stand as written, except the sentence that
section 19.3 withdraws". In section 18.3, "it has no recorded run before slot 1" reads "it has no recorded run on
this commit" (qa-evidence's wording, section 19.4), which is true whatever the chair rules on section 19.1. Nothing else
of sections 12, 16 or 18.3 changes.

### 19.4 qa-evidence: a second read, on the corrected texts

qa-evidence read the head `b73ce365` of this pull request (sections 19.1 to 19.3 and 19.5 to 19.6, and the reworded
documents) as a read-only process of its own. In its words: "Of the six findings from my first read, all are now
addressed, but five sentences still fail." It found the classes, the fixtures, the account's scope and the residual
stated in `docs/GATE_INPUTS.md`, `docs/GATE_INTEGRITY.md` and `docs/LIVE_EVAL_EVIDENCE.md`, and sections 18.3 and 19.3
following decision 8. Its five findings, and what this pull request does:

1. `docs/GATE_INPUTS.md`, opening paragraph: "M84 refuses such input before any step runs" said the screen refuses
   all such input. Reworded as it suggested: M84 refuses, before any step runs, the forms its recorded fixtures name.
2. `docs/GATE_INPUTS.md`, section 4: "with the M53 isolation only" used a word decision 8 bars. Reworded: "with the
   M53 measures only".
3. `docs/LIVE_EVAL_EVIDENCE.md`, section 6: "the account reads that run's own judge file and nothing beside it" went
   beyond the one probed canary. Reworded: the account reads that run's own judge file, and in run 45073595509 a
   canary beside it was denied.
4. Section 18.3 and `docs/LIVE_EVAL_EVIDENCE.md`, section 6, said the `live-eval` job has no recorded probe run
   "before slot 1", against section 19.1's item 1 as this head first took it. Reworded to "on this commit" (section
   19.3) and "yet"; section 19.1 no longer takes items 1 and 2, and leaves the reconciling of decision 2, item 3 and
   decision 8's bullet with section 19.1 to the chair, as qa-evidence asked.
5. Section 19.5 cited a section 19.4 that did not exist on that head. This section is it.

It also noted, as an inference, that section 14's citation `docs/GATE_INPUTS.md:113` points one line above the count
it quotes. That citation was so on `02cfa87f`; this pull request keeps `docs/GATE_INPUTS.md` at the same line count
and moves no line of it. Not checked by it: the JUnit count of run 45085382759, which the plan names and the
repository does not hold.

Its must-haves were findings 1 to 3 reworded, the "before slot 1" wording made consistent with section 19.1 and the
chair's word on decision 8's bullet, and this section.

**A third read**, on the head `9729c149`. In its words: "Ten of my eleven earlier findings hold as reworded." It found
four sentences that fail decision 8, and this pull request rewords each as it suggested:

1. `docs/GATE_INPUTS.md`, section 7: an escaped identifier "is read as one name, as the tools read it". Now: "as that
   section defines it" (IEEE 1364, section 3.7.1).
2. `docs/GATE_INPUTS.md`, section 3: "M85 closes that". Now: M85 refuses the forms section 6 names, and is claimed
   for those only.
3. `docs/LIVE_EVAL_EVIDENCE.md`, section 6: the refusal of "a system task outside an allow list" as a thing its
   fixtures name. Now: the constructs its recorded fixtures name, among them `$system`, `$fopen`, `$c`, DPI and a
   `` `systemc_ `` block (`tests/test_gate_inputs.py:111-156`), and the forms of `docs/GATE_INPUTS.md`, section 7.
4. `docs/GATE_INTEGRITY.md`, section 6: run 45073595509 cited for "the named tools" right after eqy and
   `coverage.read`. Now it names the four tools that run probed, on `c99ef1fe`, and says eqy and `coverage.read`
   have no recorded probe run there.

On section 19.1 it found, as an inference, that no text on this head says the `live-eval` job has a recorded probe
run, "so ET8 does not need the chair's word today", but that the measured run, a `live-eval` dispatch before slot 1,
"breaks the 'none until slot 1' premise of the record's lines 260-262 whatever the chair rules. ET8 needs the chair's
word before any text cites that run's reach records."

Outside decision 8, under its seat's own rule, it raised one more question, in its words: "the ET5 result claims
(`LIVE_EVAL_EVIDENCE.md:317-320`, plan `:627-630`, the fragment `:1`) have no committed record behind them. The only
committed file that names the run is the reach record, and it holds no gate or mutant results. This bears on ET5
(verification-lead), not ET8." Its must-haves: the four sentences reworded; "a committed record (or a withdrawn claim)
for ET5"; and the chair's word before the measured run's reach records are cited.

Gate ET8 is not confirmed by this section: qa-evidence has not read the texts as this pull request leaves them. Gate
ET5's evidence is open by qa-evidence's question, for verification-lead.

### 19.5 The conditions of section 13, checked on `main` at `02cfa87f`

Each line is what the repository shows on `02cfa87f`, with this pull request's text changes on top. The table adds
no condition; its last line is security's must-have, which section 19.1 leaves with the chair.

| Condition (section 13) | State | Evidence |
|---|---|---|
| The read of wave 2's first live batch | Met | `council/records/2026-11-14-pilot-retrospective.md:563`, the addendum of the W2-L1 read (ip#426) |
| WF3 for the timer | Met | the fixed documents and citations (ip#323, ip#327, ip#335); every judged tag exercised (ip#339); the first check records (ip#369), and `evals/flow/requirements_check_pending.json:4` lists none pending; `tests/test_whole_flow_cases.py:116` holds every check and mutant to a statement |
| WF4 for the timer | Met | `evals/flow/controls_record.json` (run 44415682628; ip#324, ip#325), which `tests/test_whole_flow_controls.py:291` holds every later CI run to, CI run 45094550416 on `02cfa87f` among them |
| WF8 for the timer | Met | `tests/test_whole_flow_runner.py:216` (ip#348); with WF22 below |
| WF9 for the timer | Met | the named job and its concurrency group (`.github/workflows/live-eval.yml:81-82`, `:199`); one trial per dispatch on the default harness (`scripts/live_eval_ci.py:117-118`); the expected fingerprint required and checked, exit 4 on a difference (`:254-257`); the checkout hashed before and after the trials (`.github/workflows/live-eval.yml:274-298`); the counting re-judge on a fresh checkout (`:309-346`). The credential test of WF9 is the register block's (gate WF17) |
| WF17 for the timer | Met, as the council reads it | `council/records/2026-11-19-seat-c-live-refusal.md`, decision 3 (`docs/LIVE_EVAL_EVIDENCE.md:562`); the reach test as a gate before the first trial (`.github/workflows/live-eval.yml:250-253`); seat code as `nirmaan-seat` (M89, ip#342; ip#444, ip#451) |
| WF10 as amended, and WF24 | Met | sections 1 to 3, 6 and 9 (ip#427), restated by section 18.1 (ip#454) |
| WF20 | Met | sections 4 to 6 and 10 |
| WF21 | Met | `tests/test_live_eval_ci.py:667` and `:680`; `tests/test_whole_flow_attempts.py:39`; `docs/HARNESS.md:261` |
| WF22 | Met | `tests/test_whole_flow_attempts.py:85` |
| WF23 | Not met | security confirms section 12 as corrected, with must-haves (section 19.1); ET1 ip#445, ET2 to ET4 ip#444, ET3 record ip#452, ET5 run 45073595509, with no committed record of its results (qa-evidence, section 19.4); ET6 ip#454, ET7 section 18.6 and below; ET8 not confirmed (sections 19.2 and 19.4) |
| WF25 | Met | sections 7, 18.1 and 18.2. On `02cfa87f`, CLI 2.1.325, the four fingerprints are the values of section 18.1 (with documents `d90b3c18...`, without `8d6590f7...`; single-seat `0ef27db1...` and `9aa7a333...`) and the other values of section 18.1 are equal; equal again on `d53e8474` (the merge of ip#457, merged into this pull request) |
| WF26 | Met | section 11 |
| The measured run of section 10 | Remaining | not dispatched; the last run of `.github/workflows/live-eval.yml` is still replay run 45073595509 |
| Security's item 1 (section 19.1) | Open | for the chair, against decision 2, item 3 and decision 8 of the record |

### 19.6 What slot 1 still waits for

In order: a committed record of the ET5 results of run 45073595509, or the claims withdrawn (verification-lead;
section 19.4); gate ET8, confirmed by qa-evidence on the texts as they then stand; the chair's word on security's
must-haves 1 and 2 against decision 2, item 3 and decision 8 of the record (section 19.1); the measured run of section
10, dispatched from `main` with every value of section 18.1 recomputed on its commit first (section 7), and whatever
the chair rules for its tool reach records; then slot 1, with the values recomputed again on its own commit. If a
probe of the measured run's `live-eval` job is not denied, that job stops before its trial, and no slot is dispatched
until the cause is fixed and a run records every probe denied. Section 13 stands.

## 20. Dated addition (2026-11-23): the reach records of the measured run and of each slot, the failed gates, and the words (gate ET14)

This section takes up decisions A1 to A3 and C of the addendum of 2026-11-23 in
`council/records/2026-11-22-eda-tools-seat-account.md`, and decisions R1 to R4 of its second addendum (the reach records
and the review's size limit). Where this section quotes a ruling the record is the source; where the two differ, the
record rules. It is the dated addition that gate ET14 asks for, before slot 1. It changes this file only: no count,
slot, arm, harness, attempt, fingerprint, main count, derived count or digest of section 18.1, no file in
`harness.CODE`, `LOOP_CODE` or `FLOW_CODE`, no tool definition, no CLI pin, no card, no knowledge document and no file
of the seven groups is touched, so no pinned value moves. No trial ran and nothing was dispatched.

### 20.1 Security's items 1 and 2 of section 19.1 are conditions

Section 19.1 left security's must-haves 1 and 2 with the chair. The chair has ruled (decision A1): both are adopted.
Section 13's list therefore also holds, before slot 1 and in addition to what it names:

- **Gate ET10, before slot 1.** The tool reach records of the measured run's `live-eval` and `rejudge` jobs are
  committed as each job uploaded them, with the first part's log lines and the seat C reach records of the same two
  jobs, in the layout of 20.2. Each of the two tool reach records shows every probe denied and every control passed;
  both name the same run and the same commit; and the values of section 18.1 on that commit equal those on the commit
  slot 1 is dispatched from. A missing record counts as a probe not denied. The gate is met only on a commit that holds
  the whole chain of 20.2, and no text says it is met of a commit in between. The measured run's records never stand in
  for a slot's own gate: every slot still runs the reach test before its trial and before its re-judge.
- **Gate ET11, for each slot.** The reach records of every run of the slot are committed as 20.2 says, in pull
  requests of their own that merge before the slot's record.
- **Gate ET15, from slot 1.** Nothing of the timer case is dispatched, a later slot or the same slot again, unless the
  commit it is dispatched from holds the reach folder of every earlier run of every slot, each file equal by digest to
  what the run uploaded.
- **Gate ET16, before slot 1 is dispatched.** The test of 20.3 is on `main`, and it holds at every commit of `main`
  after it.

The two sentences of the record that said the `live-eval` job has no recorded probe run until slot 1 are reworded there
(decision A2). Until the measured run's records merge, no text says the job has a recorded probe run. The write and
network probes through each wrapped tool are not a condition before slot 1: through `sby` and `eqy` they are a
condition before slot 21 (gate ET12), and until then every text says the write and network denials were probed through
`vvp` only. Section 19.6's wait for the chair's word on items 1 and 2 ends with this ruling; its other waits stand
(20.7).

### 20.2 Where the reach records sit

Every reach file is committed as its job uploaded it, byte for byte, as text a reviewer reads: never compressed,
encoded, re-serialised, factored or cut (decision R1). Every file in a reach folder is a UTF-8 JSON object with a
`format` field. An index names each file with the sha256 of its bytes; the digests tie the files to one another and
show a later change; they do not prove what GitHub served (decision R1, item 3). No reach folder holds a
`manifest.json`, a `causes.md` or a `trial-*.json`, so no record reader finds one and none is counted or listed as a
trial.

**The measured run (gate ET10).** In `evals/flow/tool_reach_measured_run/<artifact name>/<file>`, the four uploaded
files, and beside the ET3 record `evals/flow/tool_reach_measured_run.json`, the index (format `nirmaan.tool-reach-measured-run/2`). It has an `about` in the words of 20.5, and names the
run, its attempt, the commit and the purpose `calibration`; the values of section 18.1 on that commit; the artifacts the
run did not upload, as `missing`; for each job the conclusion of its reach step (`reach_step`), the lines the first part
printed (its `REACH` lines and its closing `reach test:` line,
copied from the job's log with the timestamps cut, and said to be that); and the path and sha256 of each job's tool
reach record (`tool_reach`) and seat C reach record (`fw_reach`). It embeds no record. The ET3 record is not changed. The tool reach record does
not hold the first part's probes (they are the only probes of writes and of the network through `vvp`), so those are
cited to the log lines. The pull requests of the chain merge in this order: the seat C reach records first, by
themselves, as records only (one pull request each if the two do not fit one); then the index, the tool reach records, the test of `tests/test_live_eval_seat.py` and the
texts of 20.5, or the texts in a pull request after them if these do not fit one. A measured run whose gate failed
(20.4) is committed in the same shape and order under `tool_reach_measured_run_failed_<run id>`, and is never read as
the gate ET10 file.

**The measured run's own trial record** is not committed anywhere in the repository: not under `evals/results`, not
under `evals/flow`. It is left as a workflow artifact of the run the index names, and no retention period is set for it
(`.github/workflows/live-eval.yml:304-306` sets no `retention-days`; second addendum, fact S6, finds the same for the reach
artifacts); the committed index names the run, so the run is on record. Verification-lead gave this position as a read-only process of its own
(`council/verification-lead.md`), and the plan adopts it for three reasons. Section 10 keeps every time, usage and cost
figure of that run out of every record, and a trial carries its start and duration. Under `evals/results` the levels
would list it as a whole-flow trial with its outcome and the failure-to-curriculum reader would take its failures, and
decision C forbids stating anything of its trial's outcome. And `tests/test_whole_flow.py` (the check of
`SLOT_RECORD`) refuses a whole-flow record outside a slot folder, which the measured run is not. Section 8's "committed as
failed, never held out" and section 3's "none held out" govern the trials of the forty; the measured run is none of them (section 10). Verification-lead's
open point also asked that a calibration record in a slot folder be refused; the test of 20.3 is to hold that, by an
assertion added to `_check_record_structure` in `tests/test_whole_flow.py`, which needs no change to any file of a pinned group.

**A slot (gate ET11).** For each run of the slot, `evals/results/g3-timer/slot-NN/reach/<run id>/` holds the run's
uploaded files, each at `<artifact name>/<file name>` (`live-eval-tool-reach-trials-<run id>`,
`live-eval-tool-reach-rejudge-<run id>`, `live-eval-fw-reach-trials-<run id>`, `live-eval-fw-reach-rejudge-<run id>`),
and `reach-index.json` (format `nirmaan.slot-reach-index/1`). The index names its `format`, the slot's number, the run,
its attempt and its commit; each file in `files` with its `sha256` (written `sha256:<hex>`); each of the four artifacts
the run did not upload, by name, in `missing` (a probe not denied); `recorded`, whether this run wrote the slot's
record; `reach_held`, which the runner states from the records (true only if every probe was denied in both jobs, or in the
`live-eval` job only for an unjudged record; the test reads the records, not this field); and, if the run wrote no record, `no_record_cause`, in words: the job whose reach gate failed, or the job-level
stop and its exit code. The folder sits beside `<record name>/` of section 15 and never inside it, so the record stays the re-judged
record as the job wrote it. Every run of a slot has its folder, none held out: the run that wrote the record, a run whose
reach gate failed, and a run that stopped at job level for any other cause.

The order on `main`, for one slot: the reach records of each run that wrote no record, then those of the run that wrote
the record, then the record. Across slots: slot N's record is on `main` before the reach records of slot N+1 are. A
pull request holds one run's reach records, or records, and never both; a pull request of reach records adds records
only (section 7), changes no level, names the slot, the run, the commit and the files, states no outcome and no count
(section 11), and does not say gate ET11 is met.

A record, or a single uploaded file, that is over the review's size limit by itself stops the dispatch and returns to
the council before anything is committed. It is never cut, split across pull requests, compressed or held out, and the
limit itself is not the council's to raise.

### 20.3 What the test holds (gate ET16)

`tests/test_whole_flow.py` holds, at every commit of `main`, for every folder under `evals/results/g3-timer/`:

- a reach folder holds only the files its index names, every digest equals the committed file, every file is a UTF-8
  JSON object with a `format` field, none takes a record's file name, and every record in it names the index's run, its
  job and its commit (a tool reach record by `run_id`, `job` and `commit`, a seat C reach record by `run.id`, `run.job`
  and `head`);
- each of the four artifacts is in the folder or listed as missing, and not both;
- a slot folder with a record has exactly one run folder whose index says `recorded`, that run's commit is the record's
  `head_sha`;
- that run's tool reach records show every probe denied in the `live-eval` job, and in the `rejudge` job unless the
  record has no `rejudge.json` (an unjudged record, which section 8 commits as it is);
- every other run folder states its `no_record_cause`, so a run that shows every probe denied in both jobs with no
  record and no stated cause fails, since that would be a trial held out;
- the slot folders with a record run from 01 with none missing, and only the highest-numbered slot folder may hold
  reach records and no record;
- a whole-flow record in a slot folder has purpose `evidence` in its manifest and in every trial.

It passes while no slot folder exists, and a synthetic fixture drives each check, one pass and one failure for each. It
holds a file's content to its path: it does not read the file's outcome as a count. A record whose own run does not
show the `live-eval` job's probes denied (a record exists although a reach record is missing or shows a probe not
denied) is to be committed as it is and none held out (decision R3, item 7), but the test above would fail on it, so it cannot
merge and the dispatch stops until security and verification-lead decide how such a trial counts. That is not decided
here.

### 20.4 A reach gate that fails

Decided in advance (decision A3), for each place it can fail:

1. **The measured run, in either job.** No slot is dispatched. If the `live-eval` job's gate fails, no trial ran and the
   run measured nothing. Whatever reach records and log lines the run left are committed, none held out, as a failed
   gate (the layout of 20.2), before any further dispatch of the timer case. The cause is fixed; if the fix moves a
   pinned value, the plan amendment of section 7 merges first. Then a run records every probe denied in both jobs, and
   gate ET10 is read on that run. Section 10's "one run" is read with this: one run that passed its gates. Which run
   meets gate ET10 again after a pinned value has moved goes to security when it arises.
2. **A slot, in the `live-eval` job.** Section 8 already rules it: a job-level stop, no trial ran, and the same slot is
   dispatched again once the cause is fixed. In addition: the failing run's reach records are committed in the slot's
   folder, beside those of the run that later records the slot (20.2), and no slot is dispatched until the cause is
   known. A fix that changes anything the freeze of section 7 holds returns to the council before it merges, since
   from slot 1 the plan changes only by a ruling. If slots then run on two values of a group, the read names which slot
   ran on which.
3. **A slot, in the `rejudge` job, after the trial's record exists.** Section 8 as written applies and no count changes:
   the record is a trial and is committed as it is, and an unjudged trial counts as failed in its group. The slot is not
   dispatched again. No further slot is dispatched until the cause is known, as in item 2.

### 20.5 The words of decision C, and where they may appear

A reach record of the `live-eval` job is cited in these words and no wider: in run N, dispatched on `main` at C with
purpose `calibration`, in its `live-eval` and `rejudge` jobs, the listed probes were denied to `nirmaan-seat` through the
named tools. For a slot: the same, with the slot in place of the purpose. The words may appear, once the records are
committed, in: the committed index's own `about` field; a dated section of this plan; `docs/LIVE_EVAL_EVIDENCE.md`,
section 6, and `docs/GATE_INTEGRITY.md`, section 6; and each pull request that commits them (every pull request of the
chain of 20.2).

Never said, in addition to decision 8 of the record: the measured run as a result, a trial or a pass, or anything of its trial's outcome, stages or attempts,
or any time, usage or cost figure from it (section 10); that a run's reach record covers another run, another commit or
a slot; that a tool reach record holds the first part's probes (those are cited to the committed log lines); that write
or network denial was probed through any tool but `vvp` until gate ET12 is met; `eqy` or `coverage.read` as tools of the
timer path, though a record lists their probes; and that a file is "as uploaded" unless the test checks it byte for byte.
qa-evidence reads, as a process apart from the pull request's author, the head of each pull request that changes one of
these texts and of each pull request of the chain, before it merges (gate ET13). Security checks that the tools and probes a text names match the record. A read is an agent's read, not a
person's approval.

### 20.6 Gate ET5 is not met as recorded (verification-lead)

Gate ET5 reads (table of the record): "A replay of `flow/axil-timer` on `main` shows the reference answer passing every
gate and both held-out checks with the tools as the seat account; the timer's mutant sweep and controls and every
committed fixture give the results they gave". Verification-lead reads "as the seat account" as applying to each part. Verification-lead, the gate's owner, gave its position as a
read-only process of its own (`council/verification-lead.md`) on `main` after ip#460, and a seat's position is not a
council ruling. It is that ET5 is **not met as recorded**:

- Run 45073595509, as `evals/flow/et5_replay_record.json` holds it, shows the reference answer's `lint.run`,
  `simulator.run` and `synth.run`, check 1 on its staged testbench, check 2 clean with 4 of 4 mutants failing (by check
  mismatches, not permission errors), and the re-judge the same. Those four mutants are check 2's. They are not the
  timer's mutant sweep, which is `evals/flow/axil_timer/mutant_sweep.json`, and the record holds no run of it.
- The record holds no run of the timer's controls (`evals/flow/controls.json`) or of the committed fixtures as the seat
  account, and says so. Those run in CI's test job, which does not set the seat tools (`NIRMAAN_SEAT_TOOLS` is set in
  `.github/workflows/live-eval.yml` only, not in `.github/workflows/ci.yml`), so that job cannot meet ET5: only
  a run as the account rules out a control that fails for want of a file the account may not read.
- Section 18.6's sentence "ET5 is shown by the same run" is withdrawn as to the controls, the sweep and the fixtures,
  and read as the reference answer, check 1 and check 2's four mutants only. The rows of section 19.5 and the first wait
  of section 19.6 stand read the same way.
- Owed before slot 1, and so before the measured run: a replay-only dispatch on `main` with no model, whose `replay`
  job runs as the account the timer's controls, its full mutant sweep and the committed gate fixtures; its results
  compared with `evals/flow/controls_record.json` and the sweep's committed results, and committed as a record of its own
  with a test (owner: eda-tooling; verification-lead then reads it and states ET5 met). A difference stops slot 1 and
  returns to the council. If that dispatch needs a change to `.github/workflows/live-eval.yml` or to a file of the seven
  groups, the change goes through gate ET7 and the plan amendment of section 7 before it merges, and it does not
  move a pinned value without one. Nobody narrows ET5's wording but the chair.
- Not a substitute: the measured run, whose `rejudge` job re-runs the trial's gates and not the controls, and which
  ET7 places after the last merge.
- The record owed here is `evals/flow/et5_controls_record.json`, from run 45119522138 (section 21). ET5 is not met on it
  (section 21.4).

### 20.7 What slot 1 still waits for

In order, each as section 13 and 19.6 say, with what 20.1 and 20.6 add: the record of 20.6, and verification-lead's read of it
stating whether ET5 is met; gate ET8 and gate ET13 confirmed by qa-evidence on the texts as they then stand; the test of gate ET16 on `main`; the measured run of section 10, dispatched
from `main` with every value of section 18.1 recomputed on its commit first (section 7); the chain of gate ET10 merged on a commit that holds the whole of it, with the values of
section 18.1 on the measured run's commit equal to those on the commit slot 1 is dispatched from; then slot 1, with
the values recomputed again on its own commit. Section 13 stands.

## 21. Dated addition (2026-11-23): gate ET5's controls, sweep and fixtures as the seat account, and the value ip#464 moved

Section 20.6 records verification-lead's position that gate ET5 is not met as recorded, and what is owed: a
replay-only dispatch on `main` with no model, whose `replay` job runs the timer's controls, its full mutant sweep and
the committed gate fixtures as the seat account, committed as a record of its own with a test. This section names the
change that made that dispatch possible, the value it moved, the run and its record. It changes no count, slot, arm,
harness, attempt, fingerprint, case or level, and it states no verdict on ET5: that is verification-lead's.

### 21.1 The change, and the value it moved

No input of `.github/workflows/live-eval.yml` ran the controls, the sweep or the fixtures: the `replay` job ran only
the case's reference answer. ip#464 (merge `c0ba283c`) added the input `controls`. With it, a replay of
`flow/axil-timer` also runs `scripts/live_eval_controls.py` in the `replay` job, after the reference answer's replay,
between the job's two tree hashes, where `NIRMAAN_SEAT_TOOLS` names the account's wrappers. It raised that job's
time limit to 150 minutes. The `live-eval`, `not-main` and `rejudge` jobs did not change. The workflow file is in the
group "Workflow, tool set and CLI pin", so that group's digest moved. `scripts/live_eval_controls.py` is in no group:
the `live-eval` job, where trials run, never runs it.

Every value of section 18.1, recomputed on `main` at `c0ba283c` with CLI 2.1.325, by the same commands as section
18.1:

| Item | Since section 18.1 | Value |
|---|---|---|
| Case, `flow/axil-timer`, case digest | unchanged | `sha256:ff8a4afc77caee105070d996f3e29142f2fe013c411752becdc46090b7553da3` |
| Whole-flow fingerprint, with documents | unchanged | `sha256:d90b3c1840870ae9434b90188dbb3078473140d56b2dec9e295c515c1832adfc` |
| Whole-flow fingerprint, without documents | unchanged | `sha256:8d6590f7a66ac771abf360790643763e8c43d3c267d94a5145f1e4c8bf3ae975` |
| Flow digest, with documents | unchanged | `sha256:a1aea0d36022a54be56c8d5c31831ea8ac0994f2802bd8ee8f39f6a5246ec312` |
| Flow digest, without documents | unchanged | `sha256:b8608edecf2013dddfaec85e947106316f9a561a8ec74c7e3d99a7f53f8323c0` |
| Single-seat default, with documents (must stay) | unchanged | `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` |
| Single-seat default, without documents (must stay) | unchanged | `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39` |

| Group | Paths | Files | Since section 18.1 | Digest |
|---|---|---|---|---|
| Gate backends | `src/nirmaan/integrations` | 60 | unchanged | `sha256:eac184ecc60ae35bdc88e6f66c2fa3aceaabe4c32f62066e951d7d5e84e835f9` |
| Seat account | `scripts/live_eval_seat.py`, `.github/actions/live-eval-seat` | 2 | unchanged | `sha256:4abec1ad1bb4fe9e48afb333c619c1d07ccd2e5df80b62f3142dc8ad750fa446` |
| CI command | `scripts/live_eval_ci.py` | 1 | unchanged | `sha256:3f396770975a7fcff4fc746c031e8694f768b921e90376c290e4fc023acf3e88` |
| Workflow, tool set and CLI pin | `.github/workflows/live-eval.yml`, `.github/actions/live-eval-setup`, `.github/actions/oss-cad-suite`, `.github/live-eval` | 5 | moved by ip#464 (`c0ba283c`) from `09083077...` | `sha256:4daa3c45ea748b0bfa77aad94173aa05341b4dee3e42a6fb61b7c5e467726481` |
| Reach test | `scripts/live_eval_reach.py` | 1 | unchanged | `sha256:581a4cebb61899090a1741fdbea49e51b57decdebdf0cb11c58562f60b4b93c0` |
| Held-out scorers | `src/nirmaan/evals/scorers.py` | 1 | unchanged | `sha256:5f4f7909a3207f3837d2af7ad60b85c0bae620e1d461afde57aea0d2a592ecb4` |
| Stage gates | `src/nirmaan/company/workflows.py` | 1 | unchanged | `sha256:bcd15f8204e55f142f266afdd8e12a4947c7f6276382dd18f4c9893e616a9873` |

From this addition on, every check of sections 4 and 7 is made against these two tables, which replace those of
section 18.1. Section 18.1 keeps its values as the record of what moved.

Gate ET7 for ip#464: `git diff --name-only de1e547b c0ba283c` (its merge's first parent, and the merge) names
`.github/workflows/live-eval.yml`, `scripts/live_eval_controls.py`, two test files, `docs/LIVE_EVAL_EVIDENCE.md` and a
history fragment, and no file in `harness.CODE`, `LOOP_CODE` or `FLOW_CODE` and no tool definition
(`src/nirmaan/company/tools.py`). These tests pass on `c0ba283c`: `tests/test_whole_flow_dispatch.py` (gate WF7),
`tests/test_live_eval_seat.py::test_the_tools_as_the_seat_account_change_no_fingerprint` and
`tests/test_gate_inputs.py::test_no_file_this_milestone_changes_is_harness_code`. The four fingerprints above are
those of section 18.1.

### 21.2 The run

Run 45119522138 is a replay of `flow/axil-timer` with `controls` set, dispatched on `main` at `c0ba283c` with no
model and no token. No other run of `.github/workflows/live-eval.yml` was queued or running when it was dispatched.
Its `live-eval` job was skipped, as in every replay. In its `replay` job the reach test denied every probe, the
reference answer's replay passed, and then the step of section 21.1 ran. That step failed, for the fixtures below. Its
`rejudge` job re-judged the replayed record, found it the same, and its reach test denied every probe.

### 21.3 The record, against the expectations

`evals/flow/et5_controls_record.json` is copied from the run's upload `live-eval-controls-45119522138`, with the
run's job ids. `tests/test_live_eval_controls.py::test_the_committed_et5_controls_record_is_from_main_and_shows_each_part_against_its_expectation`
holds it to the run, to `evals/flow/controls.json` and `evals/flow/controls_record.json`, and to
`evals/flow/axil_timer/mutant_sweep.json`.

- **Controls:** all seven timer controls gave, as the account, the verdicts the manifest expects and the controls
  record holds. `timer-rtl-decode-alias` was refused before review by the seat's own lint gate, as its manifest entry
  says.
- **Mutant sweep:** the reference passed with 44959 checks. Each of the 99 mutants, rebuilt from the same text (its
  sha256 equal to the record's), failed with the record's error count and first failure. That held on Icarus Verilog
  12.0, where the record was written on 13.0.
- **Gate fixtures:** 402 tests ran from the files of gate ET1 (`tests/test_gate_inputs.py`, `tests/test_gate_reads.py`)
  and the tests of the six committed `*_fail.v` testbenches; none was skipped. 390 passed, every must-refuse fixture
  among them. 12 failed, and the record names each with its message:
  - 11 bypass controls (`test_control_without_the_check_*`). Each removes the input screen inside the test to show that
    the tool acts on the payload. Run as the account, the tool did not reach the payload's target outside the run's
    view, a canary file or a marker, so the control's assertion that it did failed.
  - 1 must-pass test, `tests/test_gate_reads.py::test_a_setup_over_an_approved_file_linked_beside_it_still_proves`. A
    formal setup over an approved file linked beside it (the link M68 places,
    `src/nirmaan/runtime/model.py`, `_place_beside`) did not run as the account: `sby` could not open `m.v`, the link
    in the setup's folder, which the account's view of the run does not hold.

These 12 are differences from the results the fixtures gave in CI's test job. By section 20.6 a difference stops slot 1
and returns to the council. Section 21.4 gives verification-lead's read. Nobody narrows ET5's wording but the chair.

### 21.4 Verification-lead's read of the record

Verification-lead, the gate's owner, read this record as a read-only process of its own (`council/verification-lead.md`)
on the head of the pull request that commits it, and stated **ET5 not met**, as the gate is worded. A seat's read is
not a council ruling. In short:

- The controls, the sweep and the reference answer's replay match: all seven controls, all 100 sweep rows, the replay
  passed, its re-judge the same, every probe denied in both jobs.
- 12 of the 402 fixture tests did not give the results they gave, so "every committed fixture" is not met.
- The 11 bypass controls are probably the account stopping the tool, but the record does not show it. The 5 through
  `yosys` report no cell count at all, which does not tell a refused payload from a run that did not finish. The
  record's label "bypass control" is the record's own.
- The linked setup is a real change: as the account, `sby` cannot open the link that `src/nirmaan/runtime/model.py`
  (`_place_beside`) places beside a setup. A correct proof, cover or equivalence setup over approved RTL would fail as
  the account.
- No timer trial result depends on any of the 12. The timer's RTL stage runs `lint.run`, `simulator.run` and
  `synth.run`, so the gates that use the link do not run in it. The bypass controls act only with the screen removed
  inside the test.

What it says must happen, and who owns it:

1. Security reads the run's fixtures output and states the cause of each of the 11. The chair then rules whether "does
   not reach its target, as the account" is the result these controls should give as the account. Only the chair
   narrows ET5's wording.
2. Security, with eda-tooling, gives the account the link's target, which is already a named input of the run. Then a
   fresh controls dispatch on `main`, with its record and test, if the chair does not scope this change out of slot
   1. Verification-lead expects it is needed for any formal or block-verification flow, not for timer slot 1.

Verification-lead expects to state ET5 met without a new run if the chair rules the 11 as the account's expected
result and scopes the linked setup out of slot 1. That scoping is the chair's.

ET5 is not met. A council ruling on the 11 bypass controls and on the scope of the linked setup is pending. The fix of the
linked setup is in progress as its own change (lane SEAT-LINK-FIX), which this section does not wait on and does not
record as done.

### 21.5 What slot 1 still waits for

Section 20.7 stands, with these changes. The record of 20.6 is the one of section 21.3, and ET5 is not met on it
(section 21.4). Before the measured run come the steps of section 21.4: security's statement of the 11 causes, the
chair's rulings, and the fix and fresh dispatch of item 2 unless the chair scopes it out. Then verification-lead's
statement that ET5 is met. The measured run is dispatched with every value of section 21.1 recomputed on its commit
first (section 7).

## 22. Dated addition (2026-11-23): the value ip#471 moved

Section 21.4, item 2, asks that the seat account be given the link's target, so that a setup over approved RTL opens
the link M68 places beside it. ip#471 (head `d00f1d3a`, merge `a15b8c1d`) did that in `scripts/live_eval_seat.py`,
which is in the group "Seat account", so that group's digest moved. This section restates every value of section 21.1
with that one moved. It changes no count, slot, arm, harness, attempt, fingerprint, case or level. It states no
verdict on ET5, and it does not record a run.

### 22.1 The change, and the value it moved

The harness names the file a `[files]` entry leads to as the run's input (`nirmaan.integrations.eda`,
`seat_inputs`), never the link, and `sby` opens each `[files]` name in the setup's folder. ip#471 adds `beside_links`
to `scripts/live_eval_seat.py`. In each folder that holds an input outside the run's directory, a link of the
runner's whose text is exactly one input's path is placed in the account's view as that input's own file, read only.
The bind is made from the input's descriptor, which is held open since the input's check. No other link is placed,
and no new read grant is made. The same pull request has `scripts/live_eval_controls.py` record each bypass control's
tool outcome (`bypass.json`). That file is in no group (section 21.1).

Every value of section 21.1, recomputed with CLI 2.1.325 by the same commands as section 18.1, on `main` at
`6750a127`. That is the commit this pull request was cut from, after `a15b8c1d`: the only merge between them, ip#466,
changes no file of any group and no fingerprint file.

| Item | Since section 21.1 | Value |
|---|---|---|
| Case, `flow/axil-timer`, case digest | unchanged | `sha256:ff8a4afc77caee105070d996f3e29142f2fe013c411752becdc46090b7553da3` |
| Whole-flow fingerprint, with documents | unchanged | `sha256:d90b3c1840870ae9434b90188dbb3078473140d56b2dec9e295c515c1832adfc` |
| Whole-flow fingerprint, without documents | unchanged | `sha256:8d6590f7a66ac771abf360790643763e8c43d3c267d94a5145f1e4c8bf3ae975` |
| Flow digest, with documents | unchanged | `sha256:a1aea0d36022a54be56c8d5c31831ea8ac0994f2802bd8ee8f39f6a5246ec312` |
| Flow digest, without documents | unchanged | `sha256:b8608edecf2013dddfaec85e947106316f9a561a8ec74c7e3d99a7f53f8323c0` |
| Single-seat default, with documents (must stay) | unchanged | `sha256:0ef27db15df3066826c1eb942c46ad42ade809b1a71ebd4d39d8c37d793bca00` |
| Single-seat default, without documents (must stay) | unchanged | `sha256:9aa7a333cd961a23aa919616fac6428f9f29fed1ba44b2fa3f5c6ee49e745d39` |

| Group | Paths | Files | Since section 21.1 | Digest |
|---|---|---|---|---|
| Gate backends | `src/nirmaan/integrations` | 60 | unchanged | `sha256:eac184ecc60ae35bdc88e6f66c2fa3aceaabe4c32f62066e951d7d5e84e835f9` |
| Seat account | `scripts/live_eval_seat.py`, `.github/actions/live-eval-seat` | 2 | moved by ip#471 (`a15b8c1d`) from `4abec1ad...` | `sha256:1b7309f171f0e56d203b69d166f65e05eecf14cbccbc8403185a4490a11fb8a3` |
| CI command | `scripts/live_eval_ci.py` | 1 | unchanged | `sha256:3f396770975a7fcff4fc746c031e8694f768b921e90376c290e4fc023acf3e88` |
| Workflow, tool set and CLI pin | `.github/workflows/live-eval.yml`, `.github/actions/live-eval-setup`, `.github/actions/oss-cad-suite`, `.github/live-eval` | 5 | unchanged | `sha256:4daa3c45ea748b0bfa77aad94173aa05341b4dee3e42a6fb61b7c5e467726481` |
| Reach test | `scripts/live_eval_reach.py` | 1 | unchanged | `sha256:581a4cebb61899090a1741fdbea49e51b57decdebdf0cb11c58562f60b4b93c0` |
| Held-out scorers | `src/nirmaan/evals/scorers.py` | 1 | unchanged | `sha256:5f4f7909a3207f3837d2af7ad60b85c0bae620e1d461afde57aea0d2a592ecb4` |
| Stage gates | `src/nirmaan/company/workflows.py` | 1 | unchanged | `sha256:bcd15f8204e55f142f266afdd8e12a4947c7f6276382dd18f4c9893e616a9873` |

From this addition on, every check of sections 4 and 7 is made against these two tables, which replace those of
section 21.1. Section 21.1 keeps its values as the record of what moved.

Gate ET7 for ip#471: `git diff --name-only 656cd2a8 a15b8c1d` (its merge's first parent, and the merge) names
`scripts/live_eval_seat.py`, `scripts/live_eval_controls.py`, `tests/test_live_eval_seat.py`,
`tests/test_live_eval_controls.py`, `docs/LIVE_EVAL_EVIDENCE.md` and a history fragment. It names no file in
`harness.CODE`, `LOOP_CODE` or `FLOW_CODE`, no tool definition (`src/nirmaan/company/tools.py`) and not the CLI pin
(`.github/live-eval/package.json`). These tests pass on `a15b8c1d`: `tests/test_whole_flow_dispatch.py` (gate WF7),
`tests/test_live_eval_seat.py::test_the_tools_as_the_seat_account_change_no_fingerprint` and
`tests/test_gate_inputs.py::test_no_file_this_milestone_changes_is_harness_code`. The four fingerprints above are
those of section 21.1.

### 22.2 What this section does not say

Run 45135605510 is the replay on `main` after the fix, a replay of `flow/axil-timer` with `controls` set. This section
does not record it, quote its results or read them. Whether ET5 is met, and how the 11 bypass controls of section 21.3
are read, is for verification-lead and the chair (section 21.4). Section 21.5 stands, with the values of section 22.1
in place of those of section 21.1.

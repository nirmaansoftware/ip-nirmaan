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
  canary. The held-out compile read its own staged judge file, and a canary beside that file was denied. No canary
  value was in any run's log, summary or result file. The `live-eval` job runs the same probes as a gate before its
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
gave the same result.

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
  measured run and no slot, has happened before it: every run of the workflow on the timer case so far is a replay,
  whose `live-eval` job did not run.

### 18.7 What slot 1 still waits for

With this merge, gate ET6 is met and ET7 is shown for every merge named above; ET1 to ET5 and ET8 are met by the pull
requests named in sections 18.3 and 18.6 (for ET8, `docs/GATE_INPUTS.md` from ip#445, `docs/GATE_INTEGRITY.md` from
ip#444, ip#451 and ip#445, and `docs/LIVE_EVAL_EVIDENCE.md`, section 6, from ip#444 and ip#451; this section is the
plan's part). Gate
ET9 is the register block's, before slot 21. This section adds no condition before slot 1 and removes none: section
13 stands, with the measured run of section 10 after this merge. The re-measure batch of the wave 2 close record and
the timer's twenty are never interleaved: one records its last trial before the other dispatches its first.

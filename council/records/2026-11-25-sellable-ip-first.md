# Council record: the remaining work re-ordered around one reference block and a prospect checkpoint (2026-11-25)

The capability build-out
(`council/records/2026-10-18-capability-buildout.md`, section 10) orders
eleven waves. Wave 2 closed today
(`council/records/2026-11-23-wave-2-close-meeting-1.md`, addendum of
2026-11-25). The founder asked whether the whole effort is worth it, and
then asked for this meeting. It re-orders what is left around one aim: get
one small block, with its checks and its driver, in front of a real
prospect soon, and let what the prospect says decide what is built next.

Ruling, in short:

- **The offer does not change.** It is still "a custom small block with its
  evidence pack" (`council/records/2026-10-16-commercial-model-and-design-partners.md`,
  decision 1). Catalogue IP stays "Not now". The block shown is a sample of
  the offer, built to our own specification.
- **The reference block is the AXI4-Lite register block with its C driver**
  (`evals/flow/axi4_lite_regs_driver.json`).
- **On the path to the checkpoint:** the Wave 2 follow-ups that gate the
  register block case, the register block case and its read, a narrow cut of
  Wave 3 (the device driver skill on its one case), one case for
  rtl_microarchitecture, the evidence pack of the reference block, and the
  material for the founder's conversations.
- **After the checkpoint:** the part of Wave 6 that the first offer rests on,
  with verification batch 2 folded into its batch.
- **Parked, each with a revisit trigger:** the rest of Waves 3 and 6, Waves
  4, 5, 7, 8, 9, 10 and 11, the unplaced domains, the set-up of P6, the
  held-out store, the author loop and the harness restart of gate W2C21.
  Parked is not cancelled. Nothing parked restarts without a council
  meeting.
- **The checkpoint is 2026-12-09.** It is a conversation in which the
  founder shows the reference block's pack. Nothing of the prospect's is
  received and no work for a prospect starts. Gates 5 to 19 of the
  commercial record stand unchanged.
- **Two claims are kept apart:** what tools recorded about one named block,
  and what the level records say about our seats. Neither is stated as the
  other.
- **Process:** one batch fold is adopted. One change to the records fast
  lane is recommended to the founder. The council changes nothing in the
  review system.

Fourteen seats gave round 1 positions, each as a read-only process of its
own that saw no other seat's answer: product-lead, market-research,
partnerships, finance-licensing, legal-compliance, design-architect,
verification-lead, firmware-engineer, eda-tooling, security, qa-evidence,
ai-engineer, dft-engineer and physical-design-engineer. The last two were
seated because the wave that covers their work is parked. brand-content,
site-engineer, legal-counsel and tax-accounts were not seated: nothing here
changes a public page, drafts an agreement or raises an invoice. Effort
figures, usage figures and every position are in the internal minutes,
outside this repository.

## The founder's direction

Quoted as given, with UTC times.

- 2026-11-25T14:47:14Z, founder: "just plain CEO level question, is all
  these efforts worth it?"
- The orchestrator session answered:
  - Partly. Focus on what could be sold: RTL IP blocks with verification
    and firmware, which means finishing the G3 register block and Waves 3
    (firmware) and 6 (RTL design).
  - Defer the knowledge-only waves and the low-demand areas: analog/RF,
    photonics, the AI-accelerator domain, Web3-type areas.
  - Cut process overhead with the records-PR speed-up.
  - Set a checkpoint in about 2 weeks, after the register block and Wave 3:
    try to sell or pilot one verified IP block with a real prospect, and
    let that decide what follows.
  - It offered to have the council re-plan around "sellable IP first" with
    that checkpoint.
  - One further line of the answer was an effort estimate. It is left out
    here and is in the internal minutes.
- 2026-11-25T14:49:40Z, founder: "yes please do the meeting am going away,
  give me MoM when i come back"

Also from the founder on 2026-11-25: the present model plan is the most
that is approved. No larger plan and no paid usage.

**What this narrows.** On 2026-10-30 the founder set the priority as IP
Nirmaan first for the whole capability task, every phase from the exit of
P1 to P6, and the Nirmaan studio after it. Today's direction keeps "IP
Nirmaan first" and narrows "every phase": the work that leads to a block a
prospect can be shown goes first, a checkpoint follows, and the remaining
waves wait for its result. The orchestrator's answer is its own, not the
founder's; the founder's "yes please do the meeting" asks for the re-plan
and does not confirm each line of that answer. The council's decisions
below differ from the answer in four places, each stated where it occurs:
the size of Wave 3 before the checkpoint, where Wave 6 sits, the reasons
given for parking, and what "sell or pilot" can mean on that date.

## Who decided what

- The council decided every item below. The founder can overrule any of it.
- The founder was away, and asked for the minutes on return. The narrowing
  of the 2026-10-30 priority is recorded as the direction above and is put
  to the founder to confirm (Open, item 1).
- Reserved for the founder and not decided here: usage for each batch;
  whom to approach, every message sent and every conversation held;
  anything said to a prospect about money; any spending, including counsel;
  any licence or agreement; any public wording; any change to the review
  system; when the Nirmaan studio's skill work starts.
- This record loosens no gate and lifts no refusal. The register block
  case's gates, the freeze rules, the one read per case and gates 5 to 19
  of the commercial record are as they were.

## Facts checked

Read on `main` at `e3031ad0` by the seats named.

1. `capability/levels.json`: 20 skills Practised, 25 at Knowledge, none
   Proven; `scripts/capability_levels.py --check` reports a match
   (qa-evidence). Proven has no record kind in code
   (`docs/CAPABILITY_LEVELS.md`).
2. The register block case has five stages. axi and rtl_design are
   Practised. rtl_microarchitecture is at Knowledge with no trial.
   requirements_engineering, interface_specification and device_drivers
   have no level (qa-evidence, design-architect).
3. The whole-flow timer case was read once: 4 of 10 with documents and 4 of
   10 without, each with the interval 0.1682 to 0.6873
   (`council/records/2026-11-17-g3-whole-flow-cases.md`, eighth addendum).
   It credits no skill and is never pooled. The register block case has not
   run: the dispatcher refuses it until its gates are met
   (`scripts/live_eval_ci.py`).
4. In the timer case's twenty trials, eight passed, nine stopped at an
   escalation with the cause not established (eight of them at the
   microarchitecture stage), and three failed on the flow's own testbench
   (verification-lead, design-architect, from the per-slot table of that
   addendum).
5. Practised is not even across blocks. rtl_design counts 58 of 64, and
   every miss is on `rtl/apb-gpio` (10 of 16); the other six RTL cases are
   8 of 8 each. The single-seat timer case is 8 of 8 while the whole-flow
   timer case is 4 of 10: the same block under two different questions
   (qa-evidence, design-architect).
6. What the repository holds per block is a reference fixture, written as
   the case's answer. No export tree and no synthesis report file is
   committed for any block (design-architect).
7. For the AXI4-Lite register block, the required `test` job runs lint,
   simulation, a wrong testbench that must fail, synthesis with no latches
   and a proof in `mode prove`, with the tools required and not skipped
   (`tests/test_axi4_lite_fixture.py`, `.github/workflows/ci.yml`).
   `docs/IP_BLOCKS.md` still says formal skips in CI; that line is stale
   (eda-tooling, design-architect).
8. `sby`, Yices and `eqy` are pinned by digest. Verilator, Icarus, Yosys
   and the RISC-V compiler come from the runner's package manager with no
   version pin, and no tool run records a tool version (gate W2C25, open;
   eda-tooling).
9. Both whole-flow cases hold simulation, register map, must-fail and
   firmware held-out checks only. They hold no formal, coverage or
   equivalence check (verification-lead).
10. `SEAT_C_LIVE` holds one case, `firmware/axi4-lite-driver`. Every other
    case that runs seat C is refused. No live trial of that case is
    recorded. Gate SC9 part (a) is open: no security seat record backs the
    compile screen choice (`docs/COMPILE_SCREEN.md`; firmware-engineer,
    security).
11. The driver checks run as host co-simulation on Verilator against the
    block's RTL, and as an RV32I image on PicoRV32 or SERV in one Verilator
    model (`docs/FIRMWARE.md`, `docs/RISCV_FIRMWARE.md`). In both cases the
    seat writes the register map header by hand; the generated header is
    the check (firmware-engineer).
12. The required `physical-design` job already runs synthesis, place and
    route, timing and layout checks on SKY130 over the register block
    fixture (`docs/PD_SKY130_PILOT.md`). `dft.check` evaluates six
    scan-readiness rules with Yosys and no model seat (`docs/DFT.md`).
    Neither has been run on a seat-written block (physical-design-engineer,
    dft-engineer).
13. `LICENSE`: all rights reserved since 2026-10-30; no licence is granted
    except in writing. Versions of sync_fifo, rr_arbiter, apb_regs,
    apb_csr, axi4_lite_regs and axil_timer published before that date were
    offered under Apache-2.0 and stay so. Commits to the reference blocks
    carry a model co-author line (legal-compliance).
14. The commercial record's gates 5 to 19 bind "before the first partner's
    work starts". It also says "Start looking now" and that buyer
    interviews double as the search. No record of a held buyer interview
    exists. The founder's note of 2026-10-16 keeps spending at none, so the
    gates that need money stay open (partnerships, market-research).
15. The records fast lane, which the founder switched on on 2026-11-23,
    already merges a records-only pull request with no model review
    (`docs/REVIEW_MECHANISM.md`). The time such a pull request takes today
    is the required CI checks and the merge. The lane has no check that
    ties a record to a CI run (security, eda-tooling).
16. Only pull requests to `main` are reviewed; a stacked pull request is
    not (`docs/REVIEW_MECHANISM.md`).

## Decisions

### 1. The new order

**Before the checkpoint, in this order where order matters:**

1. Wave 2 follow-ups A4, A5 and A6, which gate slot 21 (gates W2C23 and
   W2C24). A1, A2, A3 and A7 finish on free lanes and never ahead of the
   register block's preparation.
2. The register block case: its gates as its plan and records state them,
   the change that lifts the refusal, slots 21 to 40, and its one read.
   Gate SC9 part (a) is met only by a security seat record that the chair
   convenes, not the author. It is a meeting of its own, not a line here.
3. The narrow cut of Wave 3 (below).
4. One eval case for rtl_microarchitecture with must-fail controls, taken
   forward from Wave 6. It runs in the same batch as item 3.
5. The evidence pack of the reference block (decision 2).
6. The material for the founder's conversations (decision 3). It needs no
   batch and no freeze, so it starts now on a free lane.

Items 3 and 4 run as one small single-seat batch under one committed plan
with fixed counts and one read. It is dispatched after slot 40 is recorded.
It may run earlier only if qa-evidence confirms in writing, against the
register block plan's freeze list, that it moves no pinned value (gate
SF3).

**Wave 3, the narrow cut.** device_drivers is measured on
`firmware/axi4-lite-driver`, whose refusal is already lifted. Knowledge
documents are written for device_drivers, register_programming and
embedded_firmware. No new firmware case is added before the checkpoint:
each one needs its own change to `SEAT_C_LIVE`, its own broken-driver
fixtures and its own must-refuse fixtures. The wave is not closed by this
cut. The skills left out are carried, owner firmware-engineer, and the
wave's exit items are written by product-lead before its batch, as for any
wave. One close meeting is enough for a cut this small.

This differs from the orchestrator's answer, which put all of Wave 3 before
the checkpoint. firmware-engineer would not promise the full wave by the
date, and the first block needs only the register driver path.

**After the checkpoint, unless its outcome says otherwise (decision 3):**
the part of Wave 6 the first offer rests on: control_logic_design,
reset_design, rtl_lint and synthesis_awareness, the second cases already
owed, the corrected answer for `rtl/apb-gpio`, and the re-measure of
rtl_design with the note of gate W2C22. Verification batch 2 is folded into
that batch: one plan, one freeze, one read, one close. Gates W2C20, W2C22
and W2C25 keep their conditions. code_coverage is measured again before any
text says a seat closed coverage. Wave 3 is not folded into this batch.

This also differs from the orchestrator's answer, which put Wave 6 before
the checkpoint. The reference block needs one Wave 6 skill measured,
rtl_microarchitecture; the rest serves the next blocks.

**Parked.** Each row waits for its trigger and for a council meeting.

| Item | Reason | Revisit trigger |
|---|---|---|
| Rest of Wave 3 (boot, board support, debug software, diagnostics, toolchains) | The first block needs a bare register driver only | A prospect asks for firmware beyond a register driver, or a block with an interrupt is chosen |
| Rest of Wave 6 (interface IP, IP qualification, deliverable kits, skills with no level that the first offer does not use) | Serves later blocks | A prospect asks for a block class these skills gate, or the checkpoint ends in a pilot ask |
| Wave 4, implementation and DFT | A block delivered as RTL is implemented and scanned by the buyer; no eval case exists; new tools are a founder class | A prospect asks for a netlist, a hardened block, scan or test patterns, or timing at their node; or a prospect's own checks reject our RTL; or a block gains a memory or a second clock |
| Wave 5, processor | Not in the first offer; its judge is not wrapped (gate G12 stays as written, and nothing is spent to meet it) | A prospect asks for a core, or the offer changes |
| Wave 8, FPGA | No open FPGA flow is wrapped; that needs a founder note | The prospect is FPGA based, or asks for FPGA resource or timing figures. market-research, product-lead and eda-tooling each named this as the parked wave most likely to return |
| Wave 7, product, documentation, commercial | Knowledge only; no buyer effect before the checkpoint | The checkpoint outcome |
| Wave 9, AI accelerator and GPU | Not addressable by us now: a buyer there expects silicon results, and no open tool judges the work | A route to silicon exists, or a prospect asks |
| Wave 10, security and silicon lifecycle | Waits on the export rule (gate G6), unchanged | Gate G6, then the checkpoint outcome |
| Wave 11, knowledge-only areas (foundation IP, analog, RF and photonics, technology and packaging, architecture research, domain IP) | Not addressable by us now, for the same reason as Wave 9 | A route to silicon exists, or a prospect asks |
| Unplaced domains and the placeholder units | No placement is needed for the first offer; placeholders stay placeholders (gate G13) | The waves restart |
| P6 set-up (monthly report, staleness warning, gap hunter) | It reports on records most of which do not exist yet | The end of the focused work |
| The held-out store (R2) | It helps no prospect, and repository visibility is the founder's | Before a frontier case result is cited, before any level is called Proven, or when a partner's acceptance testbench exists |
| The author loop | Control plane, founder class; session authoring is enough at this size | The waves restart |
| The harness restart (gate W2C21) | It would make every Practised group stale just before the checkpoint | The checkpoint outcome; or refusals on the form of a cited run appear in the register block or the Wave 3 read; or a planned change restarts every group anyway |
| The Nirmaan studio's skill work | The founder's order of 2026-10-30 stands until the founder changes it | The founder, at the checkpoint |

Three conditions hold while R2 is parked (security): the frontier cases stay
on no public branch; nothing shown or published calls a held-out check
secret, since ours are public in `evals/` and "held out" means only that
the seat account cannot read them during a run; and the store is not
created in a hurry to serve another purpose.

While the harness restart is parked, a trial that cites a run in the token
form is still refused. ai-engineer and verification-lead read the rule as
refusing only, never accepting, so affected figures can read low and not
high. That is their inference from the rule's text; the records were not
read again for this meeting.

**The reasons for parking** are written as above, not as "low demand".
market-research found no source for low demand in analog, RF, photonics or
AI accelerators, and said the honest reason is that we cannot address those
buyers now. This corrects the wording of the orchestrator's answer.

**What this changes in the build-out record.** Section 10's order: Waves 4
and 5 no longer follow Wave 3, part of Wave 6 moves ahead of them, and
Waves 7 to 11 wait. Its rule "market size orders the rest" is replaced, for
the parked waves, by the checkpoint's result. Section 11's meeting on the
author loop is put off. Gates G6, G11, G12 and G13 and each wave's exit
items are not weakened.

### 2. "Sellable", in evidence terms

**What is offered.** The custom small block with its evidence pack, as
decided on 2026-10-16. "Catalogue IP: not now" is not revisited. The
reference block is shown as a sample of that offer. If a prospect asks to
buy the reference block as it stands, that is recorded as a catalogue ask
and goes to the founder; licensing the block itself would also touch "we
do not sell the code" and "dual licensing: not now" in that record.

**Two claims, never joined in one sentence.**

*The block claim.* For one named block at one named commit: which tools
ran, at which versions and configurations, in which CI job, with what
result. This is the only thing "sellable" means at the checkpoint. The
wording is "checked with these tools at these versions", with the scope
statement beside it. The word "verified" is not used for it.

*The capability claim.* Only what `capability/levels.json` gives, per
skill, with its counts. A whole-flow count stands alone, with its interval,
with every trial in view, and with "the register block case has not run"
until that case is read. It is not a yield, it is not pooled, and it
supports no statement that the flow delivers unattended. No level appears
on a public page (build-out record, section 9).

**The pack.** It is the `nirmaan export` tree of the output of one passing
register block slot, never the reference fixture presented as a seat's
work. Beside it sits the case's pass count as read. On those exact files,
in CI, on the commit that is exported, these runs are made and recorded,
labelled as runs on the block and not as part of the whole-flow case:

- lint with no waivers; simulation on two simulators; a wrong testbench
  recorded as failing;
- formal in `mode prove` with a cover run and the assumptions listed; any
  bounded result is worded "no counterexample within N steps";
- a coverage read with the tool version named;
- the committed mutants, each with its run, and any survivor listed;
- synthesis with no latches; the register map check;
- the driver built strict, the header checked against the map, and the
  driver test against the block's RTL in host co-simulation and on the
  RV32I model;
- the version of every tool that ran, taken from the recorded run, and a
  line naming which tools are not pinned.

Two further runs are wanted and do not hold the checkpoint: one
`dft.check` run, and one run of the existing SKY130 flow at a stated clock
with its constraints file shipped. A figure from either is stated only
from a CI run on the exported commit. Without the first, the pack says
"DFT was not assessed". Without the second, it says the block was
synthesised to generic cells only and that no area, timing or power figure
exists on any library.

The pack also carries: the skills at Knowledge or with no level that the
block's stages rest on; the timer case's read; the open gate-integrity
items (gate 15 of the commercial record); a note that the export tree's
tenth folder has a name that gate 12 restricts and what that folder holds;
and that the code is model-assisted.

**The scope statement** (gate 12), in substance: one clock, a synchronous
active-low reset, no clock or reset domain crossing, AXI4-Lite as stated in
the block's own interface specification, the register count and widths,
and the parameter points that ran; open-source tools only, each named with
its version; no scan inserted, no test patterns, no test coverage figure,
no timing closure, no power analysis, no commercial tool, no silicon, no
FPGA board. The driver lines say "host co-simulation on Verilator against
the reference RTL" and name the two processor models.

**Levels.** Before the block is called sellable in our own records,
rtl_microarchitecture and device_drivers are each measured (decision 1).
reset_design, rtl_lint and synthesis_awareness may stay at Knowledge for
this block, because "lint clean" and "no latches" are tool facts and the
pack says which skills are at Knowledge. control_logic_design is not needed
for a register block; it is needed before a GPIO or timer block is shown.
With verification_signoff at Knowledge and nothing Proven, no seat's
judgement closes the block: the statement is a generated list of runs.

**Licence and wording** (legal-compliance flags; not legal advice).
Anything in the public repository may be shown and walked through.
Publishing grants no licence, so a prospect may look and may not use. No
file is handed over for use without a written licence from the founder,
and none is sent before the export screen (gate 10). No exclusivity is
offered on a block that had an Apache-2.0 version. No ownership or
non-infringement statement is made on model-assisted code. A block is
described as having an AXI4-Lite interface as its interface specification
states, never as compliant with or certified against a third party's
specification, and no specification text is reproduced. If the pack
includes the processor model run, the notices of PicoRV32 or SERV travel
with it.

**Proven is not a checkpoint outcome.** It needs a record kind that does
not exist, on delivered work, and gates 7, 9 and 11 keep that out of reach
under the no-spend rule. The checkpoint can produce the specification of
that record kind and nothing more.

**Public wording.** Nothing on ip.nirmaan.online changes before the
checkpoint. "We have no design partners yet" stays until a signature.

### 3. The checkpoint

**Date: 2026-12-09.** It is fixed and does not slide with the work. What
exists that day is shown, labelled as what it is.

**What it is.** A conversation in which the founder shows the pack of
decision 2 to a prospect and asks the questions the council prepared. It is
a buyer interview in the sense of the commercial record, and counts toward
the five that record asks for. The orchestrator's answer said "sell or
pilot". Under the commercial record's gates and the no-spend rule, neither
can start on that date: a request for a pilot is an outcome, and it leads
to a founder decision, not to work.

**It is not partner work**, on these conditions, which are part of the
decision:

- Only material already public at a named commit is shown, as a screen
  share of a local run or of the static tree. No network endpoint, no MCP
  server over a network (gate 18), no access to internal dashboards or
  machines. The tree is scanned for credential formats, absolute paths,
  account names and runner details before it is shown.
- Nothing of the prospect's is accepted: no specification, RTL, logs or
  testbench, and none is pasted into an agent session. Anything that
  arrives unasked is held by the founder, unopened by agents, outside this
  repository and outside any synced or backed-up folder.
- No price, discount or term appears in council material. Anything said
  about money is the founder's.
- Names and contact details stay with the founder. Council material says
  "Prospect A". This repository names nobody.
- Gates 10, 12, 15, 18 and 19 of the commercial record apply to the
  conversation itself. The rest of gates 5 to 19 apply from the moment a
  prospect's material is received or worked on. Gates 8 and 14 are not met
  today.

**Who does what.** The council prepares, privately: a one-page statement of
the offer with the scope line and our stage stated plainly; the pack; the
known-limits list; a question list; a prospect profile by type, never by
name; an outcome form; and a line asking the prospect to send nothing
confidential yet. The founder chooses whom to approach, sends every
message, holds every conversation and fills the form. The council contacts
nobody and proposes no name. market-research recommends three to five
conversations, since one is a sample of one.

**A real prospect** fits the commercial record's partner profile; is not a
friend doing a favour; and is a person who builds, buys or approves
block-level RTL. A live conversation took place in which the pack was
shown. A reply that says only "interesting" is not a conversation.

**What one conversation can and cannot tell us** (market-research). It can
tell us what they use today for such blocks, when they last built or
bought one, what evidence their engineer needs before taking outside RTL,
whether the open-source tool boundary rules us out, and whether they would
share a real specification. It cannot tell us a price, willingness to pay
or the size of a market. Results are graded by commitment: a specification
offered, an engineer brought to a second call, or terms requested.

**If work is late.** If the register block case has not been read by the
date, no partial count of it is shown. The founder shows what has been
read: the timer case's read and a single-seat block's records, each said
as exactly that, with the register block named as not yet run. The
reference fixture may be shown only as a reference written as the case's
answer. If the narrow Wave 3 cut is late, the driver is shown with its CI
runs and no level.

**Outcomes.**

| Outcome | What follows |
|---|---|
| A pilot is asked for | No work starts. The founder decides whether to reopen spending for gates 6, 7 and 9. The council meets within a week on the plan for gates 5 to 19. The work of decision 1 continues |
| Interest, no ask | The objection is recorded; one follow-up conversation; the order of decision 1 holds |
| No interest | The stated reason is recorded. A reason that names a parked area is that area's revisit trigger. After three such results from real prospects, the council revisits what we sell before more capability work is started |
| No conversation held by the date | Recorded as "not tested", never as "no demand". The checkpoint moves once, to 2026-12-23. The work of decision 1 continues and nothing parked restarts |

Each result is recorded privately by date and prospect type.

### 4. Process

| Idea | Ruling |
|---|---|
| Fold verification batch 2 into the Wave 6 batch | Adopted (decision 1). The counts, groups and the one read per case are fixed in the plan before its first trial. Every workflow or tool change, gate W2C25 included, merges before its freeze. A whole-flow case is never mixed with single-seat trials |
| One close meeting for the narrow Wave 3 cut | Adopted |
| (a) A higher size cap inside the records fast lane only | Recommended to the founder; not decided here. Conditions the recommendation carries: every other pull request keeps its cap; every lane condition is unchanged; the credential scan and founder-class detection still cover the whole diff and fail closed; text records only; each new case has a test. security adds that the lane has no check tying a record to a CI run, that a larger cap enlarges that gap, and that such a check should come with the cap |
| (b) Records whose bulk lives outside the diff | Rejected. The level check and the re-judge read a trial's content from the repository; run artifacts expire. It may be looked at again when the held-out store exists |
| (c) A deterministic check in place of the two model reviews for records-only pull requests | Nothing to adopt: the fast lane already does this (fact 15). The saving once expected from it is not available |
| (d) Dispatch that does not wait for earlier reach records to merge | Not adopted for the register block. Its plan's addition uses what gate ET15 and the G3 record's seventh addendum already allow, and no more. A change beyond that needs a security record and a dispatcher change inside the preparation of slot 21 |
| (e) Stacked pull requests | Rejected (fact 16) |
| (f) More trials at once | Put off; only between batches, never inside one, and only after (a) is settled |
| A standing answer on usage for the focused batches, with a ceiling per batch and the harness restart left out | Recommended to the founder, in two parts: the batches before the checkpoint, and the batch after it |

Not open to cutting, for any speed-up: one read per case, no top-up, failed
trials committed, slot order to `main`, counts fixed before the first
trial, every `_tb_fail.v`, mutant sweep and `mode prove` setup, the NOTICE
check and the licence class in review, and every required check as it is
named today.

### 5. Effort

The effort figures, before and after, are in the internal minutes and the
founder's minutes. This record holds none.

## Positions not adopted, and dissent

- finance-licensing, security and eda-tooling each favoured some form of
  idea (d) for the register block: finance-licensing for the time it saves,
  security on stated conditions and with a security record, eda-tooling as
  wording in the plan's addition before slot 21. Not adopted: qa-evidence
  asked that it not change before the register block is read, the
  checkpoint date holds without it, and it would add a security record and
  a dispatcher change to the register block's preparation. Recorded as
  their dissent.
- product-lead: all of the first-offer part of Wave 6 "critical", and Wave 3
  cut to the driver path "and what its case needs". Adopted in substance;
  the chair moved one skill, rtl_microarchitecture, ahead of the
  checkpoint on design-architect's must-have, and left the rest after it.
- design-architect: all of Wave 6 beyond rtl_microarchitecture parked until
  a prospect asks. Not adopted in full: the first-offer skills are measured
  after the checkpoint without waiting for a trigger, because GPIO and
  timer blocks are in the offer and their skills are the weakest on record
  (fact 5).
- ai-engineer had earlier asked for the harness restart to be brought
  forward. It withdrew that for this meeting, until the trigger in decision
  1.
- eda-tooling and security differ on whether idea (c) is "rejected as
  written" or "already in force". Both say the same thing of the code; the
  record uses the second wording.
- verification-lead, design-architect and qa-evidence each gave a rule for
  what is shown if the register block is late. They agree that no partial
  count is shown and that a fixture is not presented as a seat's work; the
  chair's wording in decision 3 joins them. product-lead's wording, that
  the register block is "shown as in progress", is adopted only as naming
  it as not yet run.
- legal-compliance reads gate 19 (a privacy notice for contact data) as
  applying to the conversation itself. partnerships asked for that ruling.
  The chair does not rule on a legal reading: it is gate SF8 and Open, item
  6.
- market-research: confidence is low on who buys. Its list of free
  alternatives to a generic small block (register generators with a C
  header, open block libraries, peripherals bundled with vendor tools) is
  from general knowledge, was not looked up again for this meeting, and
  must be checked before any public use.

No seat dissented from keeping the offer as it is, from leaving catalogue
IP at "Not now", from the reference block, from parking Waves 4, 5 and 7
to 11, from parking the harness restart, from the checkpoint being a
conversation in which nothing is received, or from keeping the two claims
apart.

## Gates

| Gate | Condition | Owner seat |
|---|---|---|
| SF1 | Gate SC9 part (a) is met by a security seat record convened by the chair, before slot 21. It states the choice, the seat's own check of the reasons in `docs/COMPILE_SCREEN.md` against the code, and the CI run on the build the trials use | security |
| SF2 | The narrow Wave 3 cut and the rtl_microarchitecture case run under one committed plan with fixed counts and one read; the wave's exit items and the carried skills are in a committed record before the first trial | product-lead |
| SF3 | That batch is dispatched after slot 40 is recorded, or earlier only on qa-evidence's written confirmation that it moves no value the register block plan pins | qa-evidence |
| SF4 | The pack is the export of a passing register block slot's output on a named commit. That such an output can be exported is confirmed before the pack is built; if it cannot, the council is told and nothing else is presented as a seat's work | design-architect |
| SF5 | Every run in decision 2's list is a recorded CI run on the exported commit, with tool versions from the run; mutants for the shown block are committed with their runs; no figure in the pack comes from another commit or a development machine | verification-lead |
| SF6 | Before the pack is shown: the stale line in `docs/IP_BLOCKS.md` is corrected; the pack names every tool version and which tools are unpinned | eda-tooling |
| SF7 | The pack and the one-page offer are read against the records before the founder shows them: the two claims kept apart, the scope statement present, the timer read and the skills below Practised stated, none of the three restricted words of gate 12 without scope, no level called Proven | qa-evidence |
| SF8 | Before the first conversation: the export screen (gate 10) for the prospect's country and use; what gate 19 needs for the founder's own notes; the licence wording of decision 2 in the material; the notices that travel with the processor model run | legal-compliance |
| SF9 | The shown tree is scanned as decision 3 states; nothing of a prospect's enters this repository, an agent session or a backed-up folder | security |
| SF10 | The council's material holds no price, no name and no term; each conversation's result is recorded privately on the outcome form, with "not tested" kept apart from "no interest" | partnerships |
| SF11 | Nothing parked restarts without a council meeting that cites its trigger | product-lead |
| SF12 | The folded Wave 6 batch keeps gates W2C20, W2C22 and W2C25, and its plan is committed before its first trial | verification-lead |
| SF13 | No change to the review system is made under this record; idea (a) goes to the founder as a recommendation only | security |

## Open

For the founder:

1. The narrowing of the 2026-10-30 priority as this record states it, and
   this ruling, to confirm or overrule.
2. Usage: the register block case, and a standing answer for the focused
   batches in two parts (decision 4).
3. Idea (a), the cap inside the records fast lane, with security's
   condition. It is a change to the review system, so it is the founder's
   alone.
4. Whom to approach, and the conversations, by 2026-12-09.
5. The harness restart (gate W2C21): the council recommends not now.
6. Questions that would need counsel, and so spending, if a prospect asks
   for files: an evaluation licence text, ownership of model-assisted code
   and the model plan's terms on commercial use of output, a third party's
   bus specification terms, export classification, and the privacy notice
   of gate 19. The council recommends deciding these when a prospect asks,
   not before.
7. When the Nirmaan studio's skill work starts. The council recommends
   deciding at the checkpoint.

For later meetings:

8. security, convened by the chair: the record for gate SC9 part (a).
9. The council, within a week of a pilot ask: the plan for gates 5 to 19.
10. The council, after the checkpoint's result: which parked items return,
    by their triggers.
11. qa-evidence and ai-engineer: the specification of a record kind for
    Proven.

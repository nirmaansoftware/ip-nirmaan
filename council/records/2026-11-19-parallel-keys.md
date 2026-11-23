# Council record: should key 1 and key 2 run in parallel? (2026-11-19)

The founder wants the pull request review loop faster and sent one item of the
loop-speed plan to the council: today key 2 (the chair) runs only after every
key 1 passes on a head, and the Founder Proxy (agent) only after both. Should
key 1 and key 2 run at the same time on the same head, with the proxy still
last?

Ruling: **no change now. The keys stay in sequence.** The measured saving is
under a minute on a passing head, the fix round that parallel keys could save
did not occur once in the sample, and a parallel pair would hold both model
slots. The question is heard again on the conditions in decision 4.

An addendum of 2026-11-24, at the end of this record, records the founder's
later direction on the loop's width (three pull requests at once) and what
follows from it for fact 5 and decision 4.

Three seats gave round 1 positions independently, each as its own read-only
process that saw no other position (qa-evidence, eda-tooling, security); the
chair decided. The meeting was kept to the seats that own the question: the
claims and the evidence (qa-evidence), the loop (eda-tooling) and the review
as a control (security). The chair's session wrote the brief and took the
measurements below before round 1; qa-evidence reran them. Read against
ip-nirmaan `main` at 82ac470. This record changes no code, prompt, seat file,
check or gate.

A key is an agent review. Nothing here is a person's approval, a release, or a
claim that a design is ready to be made in silicon.

## Who decided what

The council decided every item below, on the founder's request for a ruling.
It is not a founder decision, and the founder can overrule it. Nothing here is
reserved for the founder: it adds no spending, contract, counsel, sending,
public name or licence term.

## The question

- (a) Keep the keys in sequence.
- (b) Run key 1 and key 2 at once, each independent, neither seeing the
  other's verdict; a merge needs both.
- (c) Run them at once, and have key 2 read key 1's findings again after both
  finish, before the proxy.
- (d) Another option.

## Facts checked

Line numbers are those at 82ac470.

1. The order today. In `scripts/pr_review.py`, `_review()` runs key 1
   (lines 1478 to 1529) and posts its comment and the `review/team-lead`
   check. At lines 1545 to 1548, when key 1 is absent, failed or deferred,
   `review/executive` is posted pending as "not run: key 1 did not pass" and
   the review ends. Otherwise key 2 runs with key 1's results in its prompt
   (line 1557). The proxy runs only on a founder-class pull request whose
   key 2 passed, and receives both results (lines 1580 to 1593).
2. What key 2 receives. `key1_view()` (line 706) passes the team, the lead,
   the whole verdict with its findings, and the checklists loaded. It reaches
   key 2 inside the untrusted-data fence (lines 637 to 639). The key 2 prompt
   says "Read key 1's results and the diff; look for what key 1 missed; do
   not redo key 1" (`key2_system_prompt()`, line 585). Since key 2 runs only
   after a pass, every key 1 result it reads is a pass.
3. The chair's checklist (`council/chair.md`, "In a review") has two items
   that read key 1: key 1 ran for every owning team on this head; and "a
   key-1 finding is neither fixed nor answered, or the teams' verdicts
   disagree".
4. This was ruled once. Decision 4 of
   [the 2026-10-18 review loop record](2026-10-18-review-loop.md) kept key 2
   after key 1: in sequence a failing head never spends a key 2 call, and the
   parallel saving was under a minute on passing heads. security dissented.
   The decision said "Revisit if the turnaround split shows key-2 queueing
   dominates", and that no model, prompt or seat-section change is made
   without a recorded calibration rerun. Decision 6 planned to measure
   independence by testing key 2 alone on seeds with key 1 forced to pass.
   `docs/REVIEW_CALIBRATION.md` records no such result: it records the
   composite key 1 comparison, and one seed that key 1 missed and key 2
   caught (line 44).
5. Model slots. `model_cap` is 2 (`scripts/pr_review.py` line 116), shared by
   both repositories' loops, and the loop steps two pull requests at once
   (`parallel_reviews`, `scripts/pr_loop.py` line 182). A slot is taken per
   model call and never waited for (`acquire_slot()`, `scripts/pr_review.py`
   lines 822 to 833): with
   none free the pull request is "busy" until a later pass. The founder
   declined more slots for now.
6. Fix rounds. `findings_to_fix()` (`scripts/pr_loop.py` line 298) already
   sends the fixer the findings of every failed key together. Each fix push
   starts CI again on the new head.
7. Measured from GitHub on 2026-11-19, from the review App's comments on the
   last 120 pull requests (#239 to #358, all 120 reviewed), counted per head:

   | Measure | Result |
   |---|---|
   | Key 1, decided heads | 157: 146 pass, 11 fail. **Fail share 7.0%** |
   | Pull requests with a key 1 fail | 9 of 120 |
   | Key 2, decided heads (each after a key 1 pass) | 144: 130 pass, 14 fail (9.7%), on 13 pull requests |
   | Founder Proxy heads | 38, all pass |
   | A key 1 fail followed by a key 2 fail on a later head | 0 of the 9 |
   | Fix rounds by the loop's fixer, per pull request | none 104, one 14, two 2 |
   | Key 1's pass comment to key 2's verdict comment, same head | median 45 s, 75th percentile 57 s, 90th 75 s (144 heads) |
   | Open to merge, 118 merged pull requests | median 29 minutes, 75th percentile 51 |

   Twenty pull requests had a failed key: 9 with a key 1 fail and 13 with a
   key 2 fail, two of them (#248, #249) with both, the key 2 fail first.
   Sixteen of the twenty had a fix round by the loop; of the other four, the
   author pushed the fix on two, one was closed and one is still open.

   Limits. The 45 s is comment to comment, so it holds the key 2 call and the
   posting, and a verdict reused from the cache shortens it. The length of
   the key 1 call cannot be read from GitHub. The turnaround split of
   decision 5 of the 2026-10-18 record is internal and is not quoted here.

## Decisions

### 1. The keys stay in sequence

Option (a). qa-evidence and eda-tooling chose it. security chose (d), with
(a) until the evidence of decision 3 exists, so no seat asked for a change
now.

Why:

- **Speed.** Running the keys at once saves, on a passing head, at most the
  shorter of the two calls. The whole key 2 step is a median of 45 s (fact
  7), so the saving is under a minute against a median of 29 minutes from
  open to merge. No loop pass sits between the keys: they run in one review
  (fact 1). The condition the 2026-10-18 record set for a revisit, that key 2
  queueing dominates, is not shown.
- **Fix rounds.** Both keys' findings at once would save a round only where a
  key 1 fail is followed by a key 2 fail on a later head. That happened in 0
  of the 9 pull requests with a key 1 fail (fact 7). The claim is not
  supported by this sample. Nine is a small number, so it is not refuted
  either.
- **Slots.** With two slots, a pull request running both keys at once holds
  both, and the other pull request in the pass goes "busy" (fact 5).
  eda-tooling's inference, which the chair accepts: when two pull requests
  are ready the change moves calls around and adds none to the throughput;
  it gains only when one pull request is alone in review.
- **Spent calls.** Parallel keys run key 2, the longer call on the stronger
  model, on every head key 1 fails: 7.0% of heads (fact 7). Each of those
  holds a slot another pull request could have used.
- **The build.** The change needs threads inside `_review()`, with the
  slot, pause and head-moved errors carried across them and the posting
  moved after a join (eda-tooling), in the control plane, while another lane
  is changing the same two files for the loop-speed items already agreed.

Why not (c). It makes three calls on a passing head where the sequence makes
two, so it is slower in slot time than what runs today (eda-tooling).

Owner eda-tooling.

### 2. What a key 2 that does not see key 1 would lose

Recorded so a later meeting need not find it again. No seat disagreed.

- "Key 1 ran for every owning team on this head" needs no key 1 text. The
  script computes the owning teams and the required `review/team-lead` check
  holds the result, so it can be given to key 2 as a fact from the script,
  which is stronger than a model reading it.
- "A key-1 finding is neither fixed nor answered, or the teams' verdicts
  disagree" has no script replacement. Without it, nobody reads key 1's
  lesser findings on a pull request that has no proxy. With the composite
  key 1 there is one verdict per head, so disagreement between teams is rare.
- The key 2 prompt's "look for what key 1 missed" would change, and a prompt
  change needs a recorded calibration rerun (fact 4).

### 3. Evidence before any change to the order

No change to the order of the keys, to what key 2 receives, or to the key 2
prompt is switched on until all of these are recorded:

- the key 2 alone run that decision 6 of the 2026-10-18 record planned, in
  `docs/REVIEW_CALIBRATION.md`: key 2 without key 1's results against key 2
  as it runs today, on the same seeds, with one seed whose diff makes key 1
  write text aimed at the next reviewer. The blind key 2 must catch no fewer;
- a calibration rerun on the new prompt, with the catch rate not lower;
- a count of loop steps that ended "busy" for want of a slot, before and
  after, on a dry run;
- a test that no merge path opens without both keys and, on a founder-class
  pull request, the proxy.

This record schedules none of these runs. They are the price of a rehearing,
not work ordered now.

Owners: qa-evidence (the record of the runs), eda-tooling (the count and the
test), security (the seed aimed at the next reviewer).

### 4. When this is heard again

When any one of these is measured:

- `model_cap` is 3 or more, so a parallel pair no longer takes every slot;
- in a window of 120 pull requests, three or more show a key 1 fail followed
  by a key 2 fail on a later head (today none);
- the key 2 alone run of decision 3 is recorded. If the blind key 2 catches
  no fewer seeds, security's option below is heard on its merits, as a
  question about the control and not about speed.

The thresholds are the seats' proposals (the second is qa-evidence's), not
derived from data.

At that hearing the starting point for the build is eda-tooling's outline:
a `parallel_keys` setting that is off by default; the two calls in two
threads with the posting after a join, in the order key 1 then key 2; key 2
given the owning teams as a script fact in place of key 1's results; the
proxy still only after both keys pass, with both results; the existing tests
of the order rewritten, and new ones for a verdict on a head key 1 failed,
for one free slot, and for unchanged behaviour with the setting off. It is
not a gate today, because nothing is adopted.

## Positions not adopted

- security, option (d): run the keys at once with key 2 blind and its
  verdict fixed before key 1's output is loaded, then a second step that
  reads key 1's findings and may only turn a pass into a fail, never a fail
  into a pass. Its reason: the fence stops instructions, not anchoring. Key 2
  reads only passes, with findings written from a diff the author controls,
  and is told not to redo key 1; two readings that share nothing are harder
  to pass together. The chair did not adopt it now because the catch rate of
  a blind key 2 is unmeasured, as security's own position says, and the
  second step is a third call on every passing head. It is not rejected:
  decision 4 hears it once the key 2 alone run exists.

## Dissent

- security: the keys should run blind and at once, as above. This continues
  its dissent in the 2026-10-18 record. security agreed that the sequence
  stays until the evidence of decision 3 exists.

## Gates

| Gate | Condition | Owner seat |
|---|---|---|
| PK1 | The order of the keys, what key 2 receives from key 1, and the key 2 prompt do not change until every item of decision 3 is recorded and the council has heard the question again | eda-tooling |
| PK2 | Any later change keeps both checks required, keeps `review/executive` from passing on a head where key 1 failed or was deferred, and starts the proxy only after both keys pass on the head | security |
| PK3 | No page, record or pull request says that parallel keys shorten the review or cut fix rounds, beyond the figures of fact 7 | qa-evidence |

## Open, for the founder

1. This ruling, to confirm or overrule.

## Addendum (2026-11-24): the review loop at three pull requests at once

The founder, in session, 2026-11-23: approved the review loop reviewing up to
three pull requests at once. The direction is the founder's. This addendum
records the founder's words, says what they change in this record, and rules
on decision 4.

Ruling, in short:

- **The width is three** (decision A1): up to three pull requests stepped at
  once, with three model slots (`parallel_reviews` 3, `model_cap` 3). This
  replaces fact 5's "The founder declined more slots for now", for one more
  slot and no further.
- **The order of the keys does not change** (decision A2). Decision 4's first
  condition is heard here and is spent. Gate PK1 stands.
- **Five conditions hold the width** (decision A3, gates LW1 to LW5).

It changes no code, prompt, seat file, check or gate. The change itself is
made by its own pull request (#488 when this was written, not merged), which
this addendum does not review again and does not pass. A key is an agent
review; nothing here is a person's approval of any code.

### Who decided what

- The founder decided that the review loop reviews up to three pull requests
  at once.
- The council decided everything else below, and the founder can overrule
  any of it.
- Not decided by anyone here: any spending. The direction is for the plan as
  it is; a plan upgrade was a separate option the founder was shown and did
  not take up in these words.

Three seats gave round 1 positions, each as a read-only process of its own
that saw no other position: security, eda-tooling and qa-evidence (the seats
of this record's meeting); the chair decided. The seats read ip-nirmaan
`main` at c842c4d7 and the diff of #488 at its head ed97f4cb. No seat ran
the tests.

### The founder's words

From the transcript of the founder's session with the orchestrator on
2026-11-23. The transcript is not in this repository. The chair's session
read it and checked each quotation below against it; no seat read it. Times
are UTC.

1. 17:32:47, the orchestrator, in a list of ways to go faster, offered
   letting the review loop work two or three pull requests at once. In its
   words: who decides: "You"; the catch: "More plan usage at once; a
   control-plane change." Its recommendation was that option together with
   running the timer's slots two at a time. It added that the review loop
   change "needs your approval on GitHub, the same way the fast lane did."
2. 17:33:29, the founder: "why only 2 why not 5?" The answer given was about
   the timer's slots.
3. 17:34:36, the founder: "go with what you recommended , i just want to
   make things faster!!!"
4. 17:34:46, the orchestrator, naming the work it started: "lets the review
   loop work up to 3 PRs at once." It said again that the change would need
   the founder's approval on GitHub.

What this is and is not:

- The founder's own words are items 2 and 3. The recommendation they accept
  said two or three; "up to 3" is the orchestrator's, ten seconds later.
- The loop already stepped two at once (fact 5), so three is the only change
  the accepted range held. The council reads item 3 as the founder's
  direction for a width of three.
- The founder gave the word in session. It is not a review on GitHub: #488
  had no review by the founder when this was written. The orchestrator said
  twice that one was needed. Under `council/README.md` ("What stays with the
  founder") this change is none of the three things that always wait for the
  founder, so whether #488 merges is for the keys and the Founder Proxy
  (agent), which accepts a council record behind such wording
  (`council/founder-proxy.md`, "Fails").
- No time saving is recorded here. Nothing is measured at a width of three.

### Facts checked

AF1 to AF4 number this addendum's facts. Line numbers are those at c842c4d7.

AF1. On `main`, `LOOP["parallel_reviews"]` is 2 (`scripts/pr_loop.py` line
   189) and `CONFIG["model_cap"]` is 2 (`scripts/pr_review.py` line 121).
AF2. The diff of #488 raises both to 3. It adds one lock per listed head, so
   two pull requests at one commit are stepped one after the other, and it
   writes each pull request's state file and the pause file whole (a
   temporary file renamed into place). In `scripts/pr_review.py` it changes
   only the header, `model_cap` and a comment: the review itself, with the
   order of the keys and the proxy after them, is not touched. It adds no
   service, account, key or plan.
AF3. The pass is one run under one lock for the repository
   (`scripts/pr_loop.py` lines 845 to 858), and the workers are threads
   inside it, so the state has one writer as before. A slot is tried, never
   waited for (`scripts/pr_review.py` lines 952 to 963). The pause is read
   at the start of a pass and before every model call
   (`scripts/pr_review.py` lines 1523 to 1527), so a limit in one worker
   starts no new step and no further call in any worker. Calls already
   running finish: up to two more after a limit at this width, where it was
   one.
AF4. `docs/REVIEW_CALIBRATION.md` records none of the four items of
   decision 3.

### Decisions

#### A1. The width is three, and fact 5's "for now" ends for one slot

The council records the founder's direction: the loop steps up to three pull
requests at once. Three workers need three slots, since a slot is never
waited for (fact AF3), and more plan usage at once was the catch the founder
was shown. So the council reads the direction as also ending "The founder
declined more slots for now" (fact 5): `model_cap` 3, and no more than 3. A
fourth slot or a fourth worker is a new question for the founder.

No seat disagreed. qa-evidence asked that the reading be marked as the
council's and not the founder's words, and it is. Owner eda-tooling.

#### A2. The order of the keys is unchanged; decision 4's first condition is spent

Decision 4 hears the parallel-keys question again when `model_cap` is 3 or
more, "so a parallel pair no longer takes every slot". The pull request that
carries decision A1 meets the number when it merges. The council hears it
here, once, and rules: the keys stay in sequence, and gate PK1 stands.

Why:

- The reason behind the condition is not met. The workers rose with the
  slots, three and three, so a pull request running both keys at once would
  still leave another worker "busy" (eda-tooling).
- None of the evidence of decision 3 is recorded (fact AF4), and gate PK1
  allows no change without it.
- Of the reasons of decision 1, only "Slots" is weaker with a third slot.
  "Speed" and "Fix rounds" rest on fact 7, which has not moved (qa-evidence).

The first condition of decision 4 is spent: `model_cap` at 3 calls no further
hearing by itself. The second and third conditions stand as written, and the
third (the key 2 alone run) still brings security's option to a hearing on
its merits.

Owner eda-tooling.

#### A3. What holds the width

Each of these is true of the diff of #488 or of `main` today, as the seats
read them, and a later change keeps it:

1. `model_cap` is never less than `parallel_reviews`, and a slot is tried,
   never waited for.
2. One pass per repository under one lock, so one writer of the state.
3. One worker per pull request and per listed head; a stop labels only its
   own pull request.
4. A limit in any worker pauses all: no new step, and no further model call,
   in that pass or in a later one until the pause ends.
5. Gate PK2, unchanged: both checks required, `review/executive` never
   passing on a head where key 1 failed or was deferred, the proxy only
   after both keys pass.

Limits the seats stated:

- "At most three model calls at once across both repositories" is true only
  where the Nirmaan loop shares this loop's state folder. On two machines
  each loop has its own slots (this one three, the Nirmaan loop two), and
  neither sees the other's pause (eda-tooling).
- A head pushed during a pass to the same commit as another pull request's
  is not covered by the per-head lock, which is taken on the heads listed at
  the start of the pass (security, an inference).

### Positions not adopted

- security: leave the rehearing of decision 4 owed, to be held later, and
  not spent here. The chair chose eda-tooling's reading because a hearing
  held before decision 3's evidence exists can change nothing under gate
  PK1, and security's own route to a hearing, the key 2 alone run, is kept.
- eda-tooling: record its five conditions as five gates of its own. The
  chair kept the conditions and gave the two that are about the review as a
  control to security.

### Dissent

- security: its dissent above stands unchanged (the keys should run blind
  and at once). The width is across pull requests; key 2 still reads key 1's
  passes.

### Gates

| Gate | Condition | Owner seat |
|---|---|---|
| LW1 | `parallel_reviews` and `model_cap` are at most 3, and `model_cap` is never less than `parallel_reviews`; more than 3 of either is the founder's to say | eda-tooling |
| LW2 | One pass per repository under one lock; a pull request's state file has one writer and is written whole | eda-tooling |
| LW3 | One worker per pull request and per listed head; a stop labels only its own pull request | security |
| LW4 | A limit in any worker pauses every worker: no new step and no further model call until the pause ends | eda-tooling |
| LW5 | No page, record or pull request says that the width of three shortens the review by a stated amount until it is measured; none says the founder approved a pull request's code or reviewed it on GitHub on the strength of this addendum | qa-evidence |

Gates PK1 to PK3 stand as written.

### Open, for the founder

1. This addendum, to confirm or overrule. It rests on the founder's word in
   session, read by the council as a width of three with three slots.

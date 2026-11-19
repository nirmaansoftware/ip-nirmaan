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

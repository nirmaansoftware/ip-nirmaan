---
name: council-meeting
description: Run an IP Nirmaan council meeting. The seats in council/ give independent positions in parallel, then the chair decides, with dissent and gates recorded. Use when the user asks for a meeting or for a business or product decision about IP Nirmaan that is hard to reverse, public, priced, legal, or crosses several seats. Not for the product's own engineering decisions (nirmaan decide). The process is council/README.md.
---

# Council meeting

Follow `council/README.md`. Steps:

## 1. Brief
Write `brief.md` in a fresh folder in your scratchpad (not the repository):
- the decision, and whether the founder delegated it;
- facts with numbers and file paths, read from the repository, not recalled;
- the rules: CLAUDE.md ("never fake work", no em or en dashes), and that the
  repository is public, so internal economics never go into it;
- the agenda as numbered questions;
- the format: ROLE / POSITION / MUST-HAVE / CONFIDENCE, about 250 words,
  "no view" allowed, facts vs assumptions labelled, sources cited.

## 2. Round 1: every seat, in parallel
Seat every file in `council/` except `chair.md` and `README.md`. One background
agent per seat, all launched in one message (at most 20 run at once). Prompt:

> You are attending an IP Nirmaan council meeting as the <role>. Read your seat
> at council/<slug>.md and adopt it. Then read the brief at <brief path> and the
> files it points to. Do not modify the repository. Focus: <what this seat
> should judge>. Write your position in the brief's format to
> <folder>/<slug>.md and return it as your final message.

qa-evidence, legal-compliance and the domain seats must check claims against
the code and recorded evidence, not the docs. Wait for every position.

## 3. Round 2: the chair decides
One foreground agent with `council/chair.md`. It reads the brief and every
position, decides each item, names who disagreed and why, records dissent, and
sets gates with an owner seat each. It writes `minutes-internal.md` (may hold
margins, costs, effort) and `council-record.md` (must not).

## 4. Follow up, implement, verify
Ask the owning seat (SendMessage) for any number or fact a decision rests on.
Apply the decisions, then have the owning seat verify before anything ships.

## 5. Records
- `council/records/YYYY-MM-DD-<topic>.md` from `council-record.md`. Grep it for
  margins, unit costs and hours, and run `python scripts/check_dashes.py`.
- Copy the minutes and every position to `~/Nirmaan-internal/<date>-ip-<topic>/`.

## 6. Reserved for the founder
Contracts, spending money, legal counsel and public names. Report and ask; if
the founder overrules, record it. Merging follows the two-key review: a pull
request in one of the six founder classes (`council/README.md`, "What stays
with the founder") also waits for the founder's approval only when the Founder
Proxy (agent) returns `needs-founder`; any other merges once CI and both keys
(and, for a founder class, the proxy) pass.

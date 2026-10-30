---
id: design/arbitration
skill: arbitration
as_of: 2026-10-30
review_by: 2027-04-30
sources:
  - purchasable | Dally and Towles, Principles and Practices of Interconnection Networks (2004), chapter 18, Arbitration [DT] | Morgan Kaufmann (Elsevier)
  - open | McKeown, The iSLIP Scheduling Algorithm for Input-Queued Switches, IEEE/ACM Transactions on Networking 7(2), 1999 [iSLIP] | the author's copy on his Stanford University page
  - purchasable | Shin, Mooney and Riley, Round-robin Arbiter Design and Generation, International Symposium on System Synthesis (ISSS), 2002 [SMR] | ACM Digital Library
  - purchasable | Cerny, Dudani, Havlicek and Korchemny, SVA: The Power of Assertions in SystemVerilog, second edition (2015) [SVA] | Springer
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-SKILL-B session (P1-14 part b, 2026-10-30)
checker: pending, a different session reads the sources in P1-14 part (c) and writes the check record
---
Knowledge only: no tool run backs this.

# Arbitration

An arbiter decides which of N requesters uses a shared resource (a bus, a port,
a buffer slot) when more than one asks at once. This document covers how to
choose a scheme, how to build it as RTL, where arbiters usually go wrong, and
how a result is checked. Tags in brackets name the sources in the front matter.

## Terms

- **Grant.** The arbiter's output: at most one requester holds it per decision,
  and only a requester that is asking can hold it [DT].
- **Fairness.** Three strengths are worth naming [DT]: weak fairness (every
  request is served eventually), strong fairness (requesters that keep asking
  are served equally often), and FIFO fairness (requesters are served in the
  order they asked). Round robin gives strong fairness among requesters that
  keep their request up; fixed priority gives none of the three under load.
- **Starvation bound.** The most grants that go to others between a requester
  raising its request and receiving the grant, while it keeps asking. State it
  in grants, not cycles, unless every grant lasts one cycle. For round robin
  over N requesters it is N - 1 [DT].

## Choosing a scheme

- **Fixed priority.** A priority encoder: the lowest (or highest) index that
  asks wins. Smallest and fastest, but a busy high-priority requester can
  starve the rest indefinitely, so use it only when the spec accepts that or
  something upstream bounds the load [DT].
- **Round robin.** Priority rotates so that the requester just served becomes
  the lowest priority for the next decision, and the one after it becomes the
  highest. With everyone asking, grants go around in index order [DT].
  Common structures: a priority pointer driving a programmable priority
  encoder, or two fixed-priority encoders, one over the requests at or above
  the pointer and one over all requests, with the first used when it finds
  anyone. Shin, Mooney and Riley compare several such structures and how their
  area and delay grow with N, and generate them for a given N [SMR].
- **Weighted round robin.** Requester i may take up to w(i) grants per round
  before priority moves on, typically counted with a credit per requester that
  is refilled each round. It shares bandwidth in proportion to the weights
  while still bounding every requester's wait [DT].
- **Matrix arbiter.** One state bit per pair of requesters records which of
  the two has priority over the other; the winner loses priority to everyone
  else. This serves the least recently served requester first, at a cost of
  about N squared over two bits, so it suits small N [DT].
- **Queuing arbiter.** Requests are time stamped or queued and served in order
  of arrival, which gives FIFO fairness at the cost of storage [DT].

When several arbiters work together (an allocator, or the input and output
stages of a switch), their pointers can fall into step and keep choosing the
same pairs. iSLIP avoids this by moving a pointer only when its grant is
accepted, and then to one past the requester it served; that rule
desynchronises the pointers and is what removes starvation [iSLIP].

## How the work is done

1. **Read the spec for the shape.** Note N and whether it is a parameter (if it
   is, the design must be right for every legal N, including N that is not a
   power of two); whether the grant is combinational in the same cycle as the
   request or registered; whether a grant is held over a multi-cycle transfer;
   what the arbiter does when nobody asks; and the reset state of any pointer
   or priority state [DT].
2. **Write the invariants down as checkable statements** before writing RTL:
   at most one grant; a grant only to a requester that asks; a grant whenever
   anyone asks, if the spec says so; the pointer update rule; and the
   starvation bound [DT] [SVA].
3. **Update priority state only on a real grant.** If no one is granted, or the
   resource refuses the grant (backpressure), leave the pointer where it is;
   otherwise the arbiter skips requesters or repeats one, and the bound breaks
   [iSLIP].
4. **Move the pointer to one past the winner, not one past the old pointer.**
   Moving it from its old position lets the same requester win again when
   requesters between the old pointer and the winner are idle [DT] [iSLIP].
5. **Wrap explicitly.** The priority order is a circle over the N requesters
   [DT], so indexes and pointers run from 0 to N - 1 and the step after N - 1
   must be written as a return to 0. A counter of ceil(log2 N) bits left to
   overflow wraps at the next power of two instead, which is right only when
   N is itself a power of two.
6. **Hold the grant when transfers span cycles** (a grant-hold or lock input),
   and count a held grant as one grant in the starvation bound [DT].

## Common failure modes

- **Rotation that does not rotate.** If the winner keeps top priority, the
  arbiter is fixed priority in practice and starves the others under load
  [DT].
- **The pointer moves when nothing was granted**, so a waiting requester is
  passed over [iSLIP].
- **More than one grant, or a grant with no request**: either breaks the
  definition of a grant [DT]. In the two-encoder structure, check that only
  one encoder's result is used for each decision.
- **Wrong only for some N.** Arithmetic that is correct at N equal to 4 or 8
  and wrong at 3, 5 or 6 because the wrap happens at a power of two, not at N
  (step 5).
- **Unfair under backpressure.** Grants that are refused still move priority,
  so the requesters that happen to ask when the resource is ready are favoured
  [iSLIP].

## How a result is checked

- **Simulation must create contention.** Fixed priority and round robin give
  the same grants when only one requester asks, so a test that never has
  several requesters asking at once cannot tell a fair arbiter from a
  starving one. Include: all requesters asking for several rounds (grants
  must go around in order), one requester alone, random subsets, requests
  dropped and raised again, and backpressure if the interface has it. Check
  every grant against a reference model of the scheme rather than by eye
  [DT].
- **Measure the bound.** For each waiting requester, count grants to others
  until it is served and fail when the count passes the bound [DT].
- **Assertions.** At most one grant and a grant only with a request are safety
  properties. "Eventually granted" is a liveness property, which needs
  fairness assumptions and an unbounded proof; the counted bound above is a
  safety property instead, so a bounded or inductive proof can show it, and it
  says more [SVA].
- **Covers.** Cover each requester being granted, all requesters asking at
  once, and the pointer wrapping from N - 1 to 0, and check the covers are
  reached so the proof is not vacuous [SVA].
- **More than one parameter point.** Prove or simulate at a power of two and at
  a value that is not one, since wrap errors appear only at the second (step
  5).

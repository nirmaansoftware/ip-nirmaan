---
id: design/arbitration
skill: arbitration
as_of: 2026-10-30
review_by: 2027-04-30
sources:
  - open | McKeown, The iSLIP Scheduling Algorithm for Input-Queued Switches, IEEE/ACM Transactions on Networking 7(2), 1999 [iSLIP] | the author's copy, http://tiny-tera.stanford.edu/~nickm/papers/ToN_April_99.pdf
  - open | Shin, Mooney and Riley, Round-robin Arbiter Design and Generation, International Symposium on System Synthesis (ISSS), 2002 [SMR] | the authors' Georgia Tech copy, https://users.ece.gatech.edu/mooney/codesign/publications/eung/paper/isss_02.pdf
  - open | Becker, Efficient Microarchitecture for Network-on-Chip Routers, PhD dissertation, Stanford University, 2012, chapter 2, Arbiters [Becker] | Stanford Digital Repository, https://purl.stanford.edu/wr368td5072
  - open | YosysHQ, SBY (SymbiYosys) documentation: Reference for .sby file format, and Formal extensions to Verilog [SBY] | https://yosyshq.readthedocs.io/projects/sby/en/latest/reference.html and https://yosyshq.readthedocs.io/projects/sby/en/latest/verilog.html
licence_check: original writing that summarises and cites; no text, table, figure or code copied from any source
export_screen: clear
writer: IP-SKILL-B2 session (P1-14 part b, open-source revision, 2026-10-30), revising the IP-SKILL-B session's first version
checker: pending, a different session reads the sources in P1-14 part (c) and writes the check record
---
Knowledge only: no tool run backs this.

# Arbitration

An arbiter decides which of N requesters uses a shared resource (a bus, a port,
a buffer slot) when more than one asks at once. This document covers how to
choose a scheme, how to build it as RTL, where arbiters usually go wrong, and
how a result is checked. Tags in brackets name the sources in the front matter.
A line marked "inference" is this document's own reasoning from the cited
source, not a statement the source makes.

## Terms

- **Grant.** The arbiter's output: only a requester that asks can hold it, and
  at most one requester holds it per decision. Most arbiters also grant someone
  whenever anyone asks, but that third property is a design choice, not part of
  the definition [Becker].
- **Fairness.** Two strengths are worth naming [Becker]: weak fairness (every
  request is granted eventually) and strong fairness (grants are shared evenly
  among the requesters). Round robin gives strong fairness [Becker]. A fixed
  priority order can starve the lower-priority requesters [iSLIP], so it gives
  neither under load (inference).
- **Starvation bound.** The most grants that go to others between a requester
  raising its request and receiving the grant, while it keeps asking. For round
  robin over N requesters it is N - 1 [SMR] [iSLIP]. SMR count it in the time
  slots given to each winner, so state the bound in grants, not cycles, unless
  every grant lasts one cycle (inference from [SMR]).

## Choosing a scheme

- **Fixed priority.** The first asking requester in a fixed order wins, which
  is finding the first set bit of the request vector. A chain of one cell per
  requester is the smallest form; its delay grows linearly with N, and a prefix
  network brings that to logarithmic growth [Becker]. Strict priority can
  starve the lower levels [iSLIP], so use it only when the spec accepts that or
  something upstream bounds the load (inference).
- **Round robin.** After each grant, the requester just after the winner
  becomes the highest priority for the next decision [Becker], so the winner
  becomes the lowest [iSLIP]. Under heavy load every requester gets the same
  share and the pointer visits them in a fixed order [iSLIP]. Common
  structures:
  - a priority encoder with a programmable highest priority, a register that
    holds the pointer, and an incrementer [iSLIP];
  - a chain of cells whose priority signal wraps from the last cell back to the
    first. That wrap is a combinational loop that timing tools handle badly, so
    the loop is cut and a second, plain fixed-priority chain added: both chains
    are evaluated in parallel and the second chain's grants are used only when
    the first, which starts at the pointer, finds no one [Becker];
  - one-hot token in a ring counter enabling one of N priority blocks, each
    with the requests in a different rotated order [SMR]. SMR also build large
    arbiters as a tree of 2-input and 4-input arbiters, and generate both kinds
    for a given N [SMR].
- **Weighted round robin.** To give requesters unequal shares, the circular
  list a round-robin pointer walks can be lengthened so that each requester
  appears in it a number of times in proportion to its weight [iSLIP]. Every
  requester with a nonzero weight is still in the circle, so its wait stays
  bounded (inference).
- **Matrix arbiter.** One precedence bit per pair of requesters records which
  of the two wins; a granted requester takes the lowest precedence against all
  others, which gives a least recently served order and strong fairness. Only
  one triangle of the matrix needs registers, n(n - 1)/2 of them, and each
  grant signal fans out to 2n of them for the update, so the scheme suits
  small N [Becker].
- **Tree arbiter.** Requesters in groups: one arbiter per group and one over
  the groups, so grants are shared fairly among groups first [Becker].

When several arbiters work together (the input and output stages of a switch),
their pointers can fall into step and keep choosing the same pairs. iSLIP moves
an output's pointer to one past the input it granted only if that grant is
accepted, which desynchronises the pointers. It updates pointers only on
matches made in the first iteration, since updating them in later iterations
can starve a connection [iSLIP].

## How the work is done

1. **Read the spec for the shape.** Note N and whether it is a parameter (if it
   is, the design must be right for every legal N, including N that is not a
   power of two [SMR]); whether a grant is required whenever anyone asks
   [Becker]; whether priority moves when the grant is issued or when the
   transfer completes, as in SMR's arbiter, which rotates its token on an
   acknowledge that can come several cycles after the grant [SMR]; and the
   reset value of the pointer or token [SMR].
2. **Write the invariants down as checkable statements** before writing RTL:
   a grant only to a requester that asks, and at most one grant [Becker]; a
   grant whenever anyone asks, if the spec requires it [Becker]; the pointer
   update rule [iSLIP]; and the starvation bound [SMR] [iSLIP].
3. **Update priority state only on a completed grant.** iSLIP moves a pointer
   only when its grant is accepted [iSLIP]. Where a ready or acknowledge signal
   can refuse a grant, treat the refusal like a grant iSLIP's accept step
   declined, and leave the pointer where it is (inference from [iSLIP]: in
   iSLIP the refusal is the accept step, not resource backpressure). With no
   request at all there is no winner to move past, so the pointer stays
   (inference from [iSLIP]).
4. **Move the pointer to one past the winner** [iSLIP] [Becker]. SMR's bus
   arbiter instead steps its token one place from wherever it was [SMR];
   working that rule by hand, the same requester can win several decisions in
   a row while another waits, although the N - 1 bound still holds
   (inference from [SMR]).
5. **Wrap explicitly.** The pointer moves modulo N [iSLIP] and the priority
   order wraps from the last requester to the first [Becker], so the step after
   N - 1 must be written as a return to 0. A counter of ceil(log2 N) bits left
   to overflow wraps at the next power of two instead, which is right only when
   N is itself a power of two (inference).
6. **Hold the grant when transfers span cycles**, and count a held grant as one
   turn in the starvation bound: SMR rotate the token only when the transfer
   completes [SMR].

## Common failure modes

- **Rotation that does not rotate.** If priority state never moves, a round
  robin chain behaves as a fixed-priority one and can starve the others under
  load (inference from [Becker] and [iSLIP]).
- **The pointer moves when nothing was granted, or on a refused grant**, so a
  waiting requester is passed over or the bound breaks (inference from the
  iSLIP update rule, step 3).
- **More than one grant, or a grant with no request**: either breaks the
  definition of a grant [Becker]. In the two-chain structure, check that only
  one chain's grants are used for each decision [Becker].
- **Wrong only for some N.** Arithmetic that is correct at N equal to 4 or 8
  and wrong at 3, 5 or 6 because the wrap happens at a power of two, not at N
  (inference, step 5).
- **Unfair under backpressure.** If refused grants still move priority, the
  requesters that happen to ask when the resource is ready are favoured
  (inference from the iSLIP update rule, step 3).

## How a result is checked

- **Simulation must create contention.** With a single request, every arbiter
  that grants whenever anyone asks grants that one requester [Becker], so a
  test that never has several requesters asking at once cannot tell a fair
  arbiter from a starving one (inference). Include all requesters asking for
  several rounds (under heavy load the pointer must visit them in a fixed
  order [iSLIP]), one requester alone, random subsets, requests dropped and
  raised again, and refused grants if the interface has them; check each grant
  against the scheme's own rule, for round robin the first asking requester at
  or after the pointer [iSLIP].
- **Measure the bound.** For each waiting requester, count grants to others
  until it is served and fail when the count passes N - 1 [SMR] [iSLIP].
- **Formal checks.** Grant only with a request and at most one grant are
  assertions. A bounded check (SBY's bmc mode) looks only at the cycles up to
  its depth, so a pass shows a property only up to that depth; an unbounded
  safety proof (prove mode, for example by k-induction) covers every cycle and
  can also end unknown when the induction step fails. "Eventually granted" is a
  liveness property, which needs a liveness check (live mode) [SBY]. The
  counted bound above is a safety assertion instead, so prove mode can show it
  for all cycles, and it gives a number where "eventually" does not
  (inference from [SBY]).
- **Covers.** Assumptions narrow what the tool examines, and cover mode looks
  for a trace that reaches each cover statement within its depth, failing if
  one cannot be reached [SBY]. Cover each requester being granted, all
  requesters asking at once, and the pointer wrapping from N - 1 to 0; a cover
  that is reached shows the assumptions did not rule that case out, so a proof
  that passes is not passing because nothing was examined (inference from
  [SBY]).
- **More than one parameter point.** Prove or simulate at a power of two and at
  a value that is not one, since wrap errors appear only at the second
  (inference, step 5).

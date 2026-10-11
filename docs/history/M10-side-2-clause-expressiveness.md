# Clause expressiveness upgrade (v1.5.0) - the one sanctioned matcher change

The first change to `knowledge/matcher.py` and `EvidenceClause` since M5, and
the single legitimate one flagged in section 5.1. Strictly additive and
backward compatible (the 363 pre-existing tests passed unchanged before any
new pack was added):
- **Numeric clauses.** New `NumericConstraint` (op in gt/ge/lt/le/eq/ne +
  value) on `EvidenceClause.numeric`. The clause's regex locates a number
  (first capture group, else first number in the match) and the node matches
  only when the value satisfies the threshold. Turns "the word latency
  appears" into "latency over 1000 ns".
- **Omission clauses.** New `EvidenceClause.absent`: as a *required* clause it
  is satisfied when NO node matches, a first-class "this expected marker never
  appeared" replacing the old must_fail/pattern="." trick.
- **Unlocked packs.** `performance` (latency/bandwidth SLA misses via numeric
  clauses) and `security` (access-control bypass, unverified secure boot via
  omission clauses) - the two domains named in the M5 spec that presence-only
  matching could not express. Dedicated unit tests pin the numeric boundary
  (fires at 3200 ns, silent at 200 ns) and omission semantics (blocked the
  moment the expected check appears).

Final: **42 packs / 92 patterns / 90 playbooks / 90 concepts / 15 state
machines**; 373 tests. Section 5.1's numeric-comparison and
forbidden-by-omission items are now resolved.

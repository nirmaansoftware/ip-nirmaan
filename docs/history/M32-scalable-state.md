# Milestone 32 - Scalable state: hidden edits impossible, chains verified once

The sixth structural-review milestone. Design
doc: `docs/SCALABLE_STATE.md`. No version bump.

Measured first: one recorded tool run cost 3.6 ms on the 55-task NoC project,
95 ms at 5,000 runs; 68% was P10's whole-state fingerprint (twice per
operation), 32% P11's full chain re-verification. After: 0.25 ms at 5,000 runs.

Key design points worth not re-deriving:
- **P10 by construction, then identity.** `FrozenDict`/`FrozenList`
  (`models/frozen.py`, standard library only) are `dict`/`list` subclasses whose
  mutators raise `TypeError`; they serialize identically, and every copy
  (`dict()`, `copy.deepcopy`, pickle) is plain and writable. The engine freezes a
  state on takeover (`work/frozen.freeze_state`) and every container it
  commits; record dict fields (`ToolRun.params`, `AuditEntry.details`, the
  analysis's `feature_evidence`/`parameters`, `Project.gate_overrides`) are
  deep-frozen by field validators. With nothing editable in place, P10's check
  compares the engine's state with the one it committed by identity.
- **P11 incremental.** `verify_chain(trail, start, previous)`; the engine
  verifies a trail in full when it takes it over and remembers the verified
  length and head. A chain that arrives broken is never marked verified, so
  every operation re-checks it in full and is refused.
- A source law test: no Nirmaan module writes through `object.__setattr__` or
  `__dict__[...]`. `state_fingerprint` stays for stores and tools.
- Tests count hashing instead of timing it, so CI is stable.

`tests/test_nirmaan_scalable_state.py` (14). The standard local run is 1415 passed,
3 skipped. Found on the way: the vocabulary may import only `__future__`, `enum`,
`datetime`, `typing`, and pydantic, so the frozen containers copy through
`__reduce__` alone (no `copy` import).

# Scalable state (M32)

The sixth structural-review milestone (`docs/architecture/target-state.md`
section 5). Every engine operation used to
cost time in proportion to the whole project: a long project's total cost grew
with the square of its length. This milestone makes the two checks that caused
it cheap without weakening what they guarantee.

## What was measured

On the 55-task NoC bridge project, recording one tool run took 3.6 ms at the
start, 12 ms at 500 runs, 40 ms at 2,000, and 95 ms at 5,000. A profile of ten
operations at 3,000 runs:

| Share | Cause | Constitution article |
|---|---|---|
| 68% | `state_fingerprint`: the whole state serialized and hashed twice per operation (once to compare, once after committing) | P10, no hidden state changes |
| 32% | `verify_chain`: every audit entry re-hashed per operation | P11, auditability |

## P10: make hidden changes impossible, then check the one way left

The fingerprint existed to catch a change made outside the engine: a reassigned
state, or a container edited in place (`state.tasks[t] = ...`). The new design
removes the second possibility and checks the first in constant time.

- **Read-only containers.** Every dict and list the engine holds in project
  state is a `FrozenDict` or `FrozenList` (`work/frozen.py`): a `dict` or
  `list` subclass whose every mutating method raises `TypeError`. They
  serialize exactly like plain ones (same JSON, byte for byte), and copies of
  them (`dict(...)`, `copy.deepcopy`) are ordinary, writable containers, so
  every reader keeps working. Records with dict fields (`ToolRun.params`,
  `AuditEntry.details`, the analysis's feature evidence and parameters, a
  project's gate overrides) freeze them on validation, so deep edits are
  refused too. The engine freezes a state when it takes it over and every
  container it commits.
- **An identity check.** With nothing editable in place, the only remaining way
  to change state behind the engine's back is to replace the state object.
  `state-changes-audited` now compares the engine's state with the one it last
  committed by identity, not by hashing everything.
- **A source law.** No module may write through `object.__setattr__` or an
  object's `__dict__` (the last way round frozen models); a test reads the
  sources, beside the existing "only the engine constructs a `ProjectState`" law.

## P11: verify each entry once

Audit entries are produced only by `audit.append`, and the trail is now a
read-only list. The engine verifies the whole chain once when it takes a state
over, remembers the length and head hash it verified, and each operation's
check verifies only the entries after that point (`verify_chain(trail, start,
previous)`). A state that arrives with a broken chain (loaded with
`verify=False`) is never marked verified, so every operation re-checks it in
full and is refused, as before.

## The result

Measured the same way after the change: a `status.read` (which also builds a
status report) recorded at 5,000 runs costs 0.25 ms, against 95 ms before, and
the cost no longer grows with the project. Twenty calls recorded twenty runs and
twenty audit entries, all verified.

## What does not change

`state_fingerprint` stays (stores and tools use it), `ProjectStore` still
verifies the full chain on load, saved JSON is byte-identical, and the export
stays deterministic. Splitting the store into append-only files is not needed
yet: saving is once per command, not once per operation.

## Tests (`tests/test_nirmaan_scalable_state.py`)

- An operation on a large project hashes only the audit entries it adds, and
  never fingerprints the whole state (counted, not timed, so CI is stable).
- Every in-place edit of state is refused: tasks, tool runs, evidence, the
  audit trail, memory, and nested dicts such as a tool run's parameters.
- A replaced state is still refused by P10 (the existing test stays), and a
  broken chain loaded without verification is refused on the next operation.
- Copies are writable, saved JSON is unchanged, and pickling round-trips.
- The no-`object.__setattr__` law holds for every Nirmaan source file.

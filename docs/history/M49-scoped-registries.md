# Milestone 49 - Scoped registries

Review gap 10 (`docs/architecture/current-state.md`), and the
principal-engineer review's risk 7 and recommendation 8: Nirmaan's extension
points were module-level dicts, grown from about 12 to 23. Two organizations
or configurations could not coexist in one process, tests cleaned up with
global `unregister_*` calls, and M36's `--jobs` threads read them while
anything could write. Design: `docs/SCOPED_REGISTRIES.md`. Tests:
`tests/test_scoped_registries.py`, written first and failing.

**One abstraction.** `src/nirmaan/registry.py` (standard library only) holds
`Registry`, a named mapping handle declared where each dict was, and
`Registries`, the context object holding one layer per registry name over an
optional parent. The process has a default instance. Every `register_*` and
`unregister_*` function is unchanged: the handle is a `MutableMapping`, so the
lines that read and wrote the dicts still work, and they now go to the current
`Registries`. Two owners mutated values in place and were changed:
`register_backend` writes a new list, and `eda._BOUND` is a registry of
`True` instead of a set.

**Scopes.** `Registries.scoped()` makes a scope over the current instance;
`Registries()` plus `using()` keeps one per organization and enters it again.
Lookups fall through to the defaults (and to a parent scope), writes and
removals stay in the scope, so a scope cannot remove a default, and its
registrations vanish when it ends. A write made while a module is being
imported goes to the defaults, so a lazy first import inside a scope cannot
lose built-ins.

**How the scope travels.** A `ContextVar`, not an explicit argument: an
argument would change the signature of every reader (the policy engine, the
broker, bindings, EDA backends, the builder) and every chain that reaches one,
which M44 and every existing extension would have to absorb. Threads do not
inherit a context on Python 3.11 and 3.12, so `runtime/writer.together` (the
one place Nirmaan starts threads) runs each thread in a copy of the caller's
context. The concurrency test fails without that line. The M36 import law for
`writer.py` now allows `contextvars`.

**Thread safety.** Each `Registries` has a lock; writes take it, and
iteration takes a snapshot of the merged keys under it. Single-key lookups are
plain dict reads.

**Tests migrated** off global `unregister_*` cleanup, as the pattern (a
`registries` fixture in `tests/conftest.py` enters a scope for one test): the
photonics crown jewel in `test_nirmaan_architecture.py`, the `fan_org` fixture
in `test_nirmaan_loop_concurrency.py`, and the throwaway MCP tool in
`test_nirmaan_mcp.py`. The rest are listed in the design doc, section 6, as
optional follow-up, along with VeriTriage's own 20 registries (VeriTriage may
not import Nirmaan) and an `Organization` that carries its scope.

No version bump.

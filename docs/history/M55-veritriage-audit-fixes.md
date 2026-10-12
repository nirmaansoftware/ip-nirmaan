# Milestone 55 - VeriTriage audit fixes: a stale project cache is rebuilt, the RTL provider reads less into SystemVerilog, Wishbone and OCP concepts stay on their protocols

A read-only audit of the VeriTriage package (audit D) found that the cached
project model was never checked for staleness, that the RTL provider misread
two common SystemVerilog shapes, and that PR #4's Wishbone and OCP concept
markers fired on unrelated protocols. This milestone fixes them, plus four
small items. Design: `docs/VERITRIAGE_AUDIT_FIXES.md`. Tests:
`tests/test_veritriage_audit_fixes.py`, written first and failing on main.

**A stale project cache is rebuilt (H1).** `ProjectStore.load_for_root`
compares the cached model's `input_fingerprint` with the root's sources and
returns nothing when they differ, so `analyze` and the design commands rebuild
after an RTL edit instead of reporting the old modules.

**The RTL provider reads less (M1, M2).** A `virtual interface` handle no
longer opens an interface unit that swallows the next module, and a function's
user-defined or package-scoped return type is no longer a module instance.

**Concepts stay on their protocols (M3).** Generic Wishbone and OCP markers now
need the protocol beside them. Twelve unrelated fixtures lose a wrong concept;
the Wishbone and OCP fixtures keep theirs; no conclusion changes.

**Small items.** Knowledge ids are unique across item kinds (L6; four
renamed). `analysis.json` is schema 14 for PR #4's fields (L9). The `--ai` help
keeps `ip-nirmaan[ai]` (L3). Two tests keep their state under `tmp_path`
(L15). The `ocp`, `reset`, `uvm`, and `wishbone` packs go to 1.0.1.

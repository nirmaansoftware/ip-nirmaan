# VeriTriage audit fixes (Milestone 55)

Status: implemented on branch `m55/veritriage-audit-fixes`. Prose here is free
of em and en dashes per the standing style law.

A read-only audit of the VeriTriage package (audit D, on `main` at 6043ce1)
found one high, three medium, and several low findings in `src/veritriage/`.
This milestone fixes the ones that are small and safe. Tests:
`tests/test_veritriage_audit_fixes.py`, one or more per finding, written first
and failing on main.

---

## 1. A stale cached project model is rebuilt (H1)

**What was wrong.** `analyze`, `design`, `dut`, `env`, `flow`, the design-graph
services, and two MCP tools call `load_project_model(root) or
build_project_model(root)`. `ProjectStore.load_for_root` returned whatever was
cached for the root path. `input_fingerprint` was computed and stored but never
compared, so after a `.v` file was edited `analyze` reported the old modules.

**Decision.** `load_for_root` recomputes the root's input fingerprint (the same
`_input_fingerprint` the build uses: manifests plus `.v` and `.sv` files) and
returns `None` when it differs from the cached model's. Every caller already
rebuilds on `None`, so no caller changed. A cache written before the field
existed has an empty fingerprint and is rebuilt once.

## 2. RTL provider: `virtual interface` is a handle (M1)

**What was wrong.** The unit regex matched the keyword `interface` anywhere and
consumed text lazily to the next `endmodule` or `endinterface`. A testbench
class holding `virtual interface axi_if vif;` became an interface named
`axi_if` and hid the module after it.

**Decision.** The unit regex matches `virtual interface` first, as its own
alternative, and `parse_rtl` skips it. A real `interface ... endinterface`
declaration still registers.

## 3. RTL provider: a return type is not an instance (M2)

**What was wrong.** `function automatic my_t compute(...)` has the instance
shape `type name (`, so `my_t` became a module instantiated by the enclosing
module. `function pkg::word_t pick(...)` did the same for `word_t`.

**Decision.** The type position after `function` or `task` (with an optional
`automatic` or `static`) is never an instance type, and `:` joins the
characters that cannot precede an instance type.

## 4. Wishbone and OCP concepts stay on their protocols (M3)

**What was wrong.** PR #4's markers `\back\b`, `terminat`, `\bstall\b`,
`pipelined`, `outstanding` (Wishbone) and `out.of.order` (OCP) are generic
words. Twelve unrelated fixtures (AXI, AXI-Stream, CXL, I2C, USB, TileLink,
RISC-V, SVA, UVM phasing, performance) listed a Wishbone or OCP concept.

**Decision.** Each generic word needs its protocol beside it:
`\back_[io]\b` or `wishbone.*\back\b`, `wishbone.*terminat`, `\bstall_[io]\b`
or `wishbone.*(?:\bstall\b|pipelined|outstanding)`, and
`\bocp\b.*out.of.order`. The 12 fixtures lose those concepts; the 8 Wishbone
and OCP fixtures keep exactly the concepts they had. No classification or
hypothesis changes on any of the fixture logs (checked by a before and after
run over every fixture). Both packs go to 1.0.1.

## 5. Small items

- **Knowledge ids are unique (L6).** Four ids each named two items, which the
  Knowledge Graph (keyed by bare id) collapsed into self-loops. Renamed: the
  playbooks `uvm.phase-timeout-debug` and `ocp.response-error-debug`, the
  concept `reset.x-propagation-after-reset`, and the state machine
  `wishbone.bus-cycle`. Pattern ids, which reports and tests cite, are
  unchanged. The `uvm`, `reset`, `ocp`, and `wishbone` packs go to 1.0.1. A
  test checks that ids are unique across concepts, patterns, playbooks, and
  state machines in every built-in pack.
- **`analysis.json` schema 14 (L9).** PR #4 added `references[].uri` and
  `learning.rule_gaps` and `learning.recommendation_weights` without a bump.
  The tests that pin the version now pin 14.
- **The `--ai` help keeps `ip-nirmaan[ai]` (L3).** Rich read `[ai]` as markup;
  the help text escapes it.
- **Tests keep state under `tmp_path` (L15).** `test_analyze_missing_file_errors`
  passes `--db` and the full-investigation attribution test passes
  `output_dir`, so neither writes `.veritriage/` into the checkout.
- **Fingerprint docstring (L2, in part).** `_input_fingerprint` now says it
  hashes RTL files as well as manifests.

## Not done here

- **M4** (test-helper deduplication): too broad for this milestone.
- **L11** (`build_organization` mutates `org_chart.STRUCTURE`): in
  `src/nirmaan/`, outside this milestone's VeriTriage scope.
- **L15, third writer** (`tests/test_nirmaan_typed_values.py`): a Nirmaan test.
- **L1, L4, L5, L7, L8, L10, L12 to L14**, and the `--project` help text part
  of L2: not requested for this milestone.

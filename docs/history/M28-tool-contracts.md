# Milestone 28 - Tool contracts (structural review, milestone 2)

Every tool with a binding declares what it takes, and the broker holds
callers to it before anything runs. Design doc: `docs/TOOL_CONTRACTS.md`.
Version bump left to the coordinator.

- **Vocabulary** (`models/org.py`): `ParamKind` (text, path, paths, integer,
  number), `ParamSpec` (name, kind, required, description, `prefix` for
  families such as `max_<metric>`), `ToolSpec.params` (None: no contract,
  taken as given, which keeps extension tools working), `list_values`, and
  `ToolRun.values(param)`.
- **Catalog** (`company/tools.py`): all 24 bound tools declare parameters (19 when written; the M27 parts added
  `formal.cover`, `dft.atpg`, `dft.mbist`, `fw.cross_build`, `fw.soc_test`, given contracts at the merge),
  inventoried from what every binding and backend actually reads (both quote
  styles; OpenROAD's settings included though nothing here can run it).
  Shared tuples: `RUNNER` (backend, workdir, timeout, max_), `PDK`,
  `PDK_REQUIRED` (sta and pnr probes refuse without Liberty), `NETLIST`.
- **Broker** (`runtime/tools.py`): `check_params` after the authority check:
  an undeclared name or an ill-typed integer or number raises
  `ToolContractError` (a `ToolAccessDenied`, so every caller already reports
  it) and records no run. A `paths` value may be a list; an element with a
  comma is refused; lists are stored comma-joined as before, so stored
  projects and bindings are unchanged. A `path` takes a one-element list.
- **Runtime**: each tool gets only the task inputs its contract declares
  (`ToolHandle.declared`), so `input.workspace` no longer reaches lint; file
  parameters go to the broker as lists.
- **Required is declared, not enforced by the broker.** A missing required
  input stays a recorded failed run (the M21/M25 rule, asserted by a physical
  test); M28 does not re-decide it.
- `nirmaan org tool ID` prints a tool's contract and whether it runs here.

Found on the way: two refusal tests passed one parameter dict to every tool
(`top` to formal, the LEFs to OpenSTA); they now pass each tool its own
parameters. The runtime passed `sby` as a one-element list, which is why a
`path` accepts one.

`tests/test_nirmaan_contracts.py` (13), including a static scan that every
parameter an integration reads is declared, and the crown jewel
`test_a_new_tool_contract_needs_no_core_changes`. On v1.21.0 the standard local run is
1231 passed, 3 skipped. Deferred to the next M28 part: typed values end to end (a
`ToolRun` storing real lists) and the typed work packet.

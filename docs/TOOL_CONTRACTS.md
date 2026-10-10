# Tool contracts (M28)

The second milestone of the structural review
(`docs/architecture/target-state.md` section 5). A tool in the catalog said
what it is (category, risk, status) but not what it takes. Its parameters were
implicit, read by name wherever a backend happened to read them; list values
were comma-joined strings split again in about a dozen places; and a
misspelled parameter (`source=` for `sources=`) was silently ignored, so a run
could "pass" over nothing. M28 gives every executable tool a declared
parameter contract, checked by the broker before anything runs.

## What changes

**The vocabulary** (`models/org.py`):

- `ParamKind`: `text`, `path`, `paths`, `integer`, `number`.
- `ParamSpec`: `name`, `kind`, `required` (default false), `description`,
  and `prefix` (true for a family such as `max_<metric>`).
- `ToolSpec.params: tuple[ParamSpec, ...] | None`. `None` means the tool
  declares no contract and takes parameters as given, which keeps tools added
  by extensions (and every existing test that adds one) working unchanged.
  An empty tuple means "takes no parameters".
- `list_values(value)`: the one place a stored list value is split.
  `ToolRun.values(param)` uses it.

**The catalog** (`company/tools.py`): every tool with a binding declares its
contract. EDA tools share the runner's parameters (`backend`, `workdir`,
`timeout`, `max_<metric>`); each tool adds its own (`sources`, `top`, `sby`,
the PDK files, the OpenROAD settings, `rtl`, `paths`, `query`, ...), taken from
what its backends actually read.

**The broker** (`runtime/tools.py`) checks the call against the contract after
the authority check and before any probe or binding:

- an undeclared parameter is refused, naming the declared ones;
- `integer` and `number` values must parse;
- a `paths` value may be given as a list: the broker refuses an element that
  contains a comma (it could not be told apart from two paths) and joins the
  rest, so the stored `ToolRun` and every binding see the format they always
  have; a `path` is one value (a one-element list is accepted, several are
  refused).

A refusal raises `ToolContractError`, a subclass of `ToolAccessDenied`, so
every caller that already reports a refused tool (the runtime's pre-flight and
post-flight notes, the evaluation scorer, the CLI) handles it unchanged. **No
run is recorded**: the tool did not run.

**Required parameters are declared, not enforced by the broker.** M21 and M25
decided that a tool invoked without an input it needs (sources, a netlist) is
a *recorded failed run*, and the backends still say so. The contract states
which parameters are required, for people and for callers choosing
parameters; changing the recorded-failure behaviour is not part of M28.

**The runtime** passes each tool only the task inputs its contract declares
(`input.workspace` no longer reaches `lint.run`), and hands file parameters
to the broker as lists instead of joining them itself. Tools with no contract
still receive every input, as before.

**One helper for lists.** The policy check `evidence-before-review`, the
engineering graph, the EDA runner, the physical, firmware, and VeriTriage
bindings, and the evaluation scorer use `list_values` / `ToolRun.values`
instead of their own `split(",")`.

**Discovery.** `nirmaan org tool TOOL_ID` prints a tool's status, risk,
whether this machine can run it, and its parameters.

## What does not change

Stored projects (a `ToolRun`'s params stay `dict[str, str]`), tool results,
backends' behaviour, the recorded-failure rule for missing inputs, workflows,
policy semantics, and VeriTriage. Typed values end to end (a `ToolRun` storing
real lists) and the typed work packet are the next part of M28, done in M39
(`docs/TYPED_VALUES.md`).

## Tests

`tests/test_nirmaan_contracts.py`:

- every tool with a binding declares a contract, and every parameter name an
  integration reads is declared by some tool (a static scan, so an OpenROAD
  setting nobody can run here is still covered);
- an undeclared or ill-typed parameter is refused with a reason and records
  no run;
- a list of paths runs; a path containing a comma is refused;
- the runtime passes a tool only its declared inputs;
- `ToolRun.values` reads stored values, including ones saved before M28;
- a tool with no contract takes parameters as given;
- crown jewel `test_a_new_tool_contract_needs_no_core_changes`: an extension
  declares a tool with a contract and a binding, and the broker enforces it;
- `nirmaan org tool` shows the contract.

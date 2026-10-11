# Milestone 39 - Typed values end to end, and the typed work packet (after Stage 6)

The part of M28 that M28 deferred. Design doc: `docs/TYPED_VALUES.md`.

- **Typed values** (`models/org.py`): `ParamValue = str | int | float |
  tuple[str, ...]`; `ParamSpec.parse` is the one parser (text form, number, or
  list; a list is several values only for `paths`; a comma in a path and a
  boolean are still refused). `text_value`, `list_values`, and `param_matches`
  read typed values and text saved before M39 alike.
- **The broker** (`runtime/tools.py`): `check_params` returns typed values;
  the probe, the binding, and the stored `ToolRun` (`params: dict[str,
  ParamValue]`) see an `int`, a `float`, a tuple. Tools with no contract stay
  untyped (lists comma-joined), so extension bindings written against text
  keep working. An empty integer or number is not given. `nirmaan task tool`
  takes a repeated `--param` as a list. The bindings (EDA runner, physical,
  DFT, vplan) read numbers and lists through those readers; messages and
  command lines are unchanged.
- **Policy**: a requirement's fixed text parameters match a run by value
  (`param_matches`), so `"0"` matches a stored `0.0` and a saved `"0"`.
- **Compatibility, no migration**: a project saved before M39 loads as it is
  (its text values are `ParamValue`s), verifies (the audit chain never hashed
  run parameters), and re-saves byte for byte; `ToolRun.typed(spec)` parses
  its text by the contract. Fixture `tests/fixtures/projects/m28-tool-runs.json`
  was saved by v1.22.0 before the change.
- **The typed work packet** (`runtime/context.py`): `WorkPacket` is a frozen
  Pydantic model with `RoleCard`, `CompanyScope`, `DomainScope`,
  `ProjectScope`, and `TaskScope` (artifacts, evidence, attempts, failed runs,
  and reviews as views; requirements, assumptions, decisions, and memory as the
  recorded models themselves), unknown keys forbidden. `prompt.py`,
  `model.py`, and `selection.py` read attributes only.
- **Prompts unchanged**: five golden prompts (triage work, root-cause work and
  review, an RTL seat with approved upstream files, a repair with masked
  Verilator output), rendered by main's dict packet, match byte for byte.

Tests that compared stored lists with joined text now compare tuples; one
extension backend test spreads a typed `lef` list into its command line.
`tests/test_nirmaan_typed_values.py` (23), crown jewel
`test_a_new_typed_tool_needs_no_core_changes`.

# Typed values end to end, and the typed work packet (M39)

The part of M28 (`docs/TOOL_CONTRACTS.md`) that M28 deferred. M28 gave every
bound tool a parameter contract and had the broker check calls against it, but
kept every value as text: a list of paths was joined with commas, and an
integer or a number was checked and then stored as the text it came in as.
Every binding re-parsed what the broker had already checked. Separately, the
work packet a model runtime renders was four untyped dicts, so a misspelled
key in the prompt renderer was a `KeyError` at run time, not a type error.

## Typed values

**The types.** `ParamValue = str | int | float | tuple[str, ...]`
(`models/org.py`). Each `ParamKind` has one type:

| kind      | type              | text form                               |
|-----------|-------------------|-----------------------------------------|
| `text`    | `str`             | itself                                  |
| `path`    | `str`             | itself                                  |
| `paths`   | `tuple[str, ...]` | the elements joined with commas         |
| `integer` | `int`             | decimal digits                          |
| `number`  | `float`           | `40` for 40.0, otherwise Python's repr  |

**One parser.** `ParamSpec.parse(raw)` turns what a caller gives into the
kind's type, or raises `ValueError` saying why. It accepts the text form (what
the CLI's `--param`, a task's `--input`, and a workflow's fixed parameters
carry), a number, or a list. A list is many values only for `paths`; for any
other kind a one-element list is that element and a longer one is refused, as
in M28. A `paths` element containing a comma is still refused: every typed
value then has exactly one text form, and that text form parses back to the
same value. A boolean is never an integer.

**The broker.** `check_params` returns the typed values. The `ToolRun` the
broker records stores them (`params: dict[str, ParamValue]`), and the binding
and its probe receive them: `timeout` is an `int`, `utilization` a `float`,
`sources` a tuple of paths. A tool with no contract (`params` None) is not
typed: a list is kept as a tuple of text, anything else as text, as before.
An ill-typed value is refused before any probe, binding, or record, as in M28.

**From the CLI and task inputs.** Both stay text where they are written (a
task input is a `MemoryEntry`, whose value is text), and become typed at the
broker, by the contract of the tool they reach. `nirmaan task tool` also takes
a repeated `--param` as a list (`--param sources=a.v --param sources=b.v`).

**Readers.** `list_values(value)` gives a value's elements and
`text_value(value)` its text form; both accept a typed value or the text a
project saved before M39. `ToolRun.values(param)` uses the first. A policy
requirement's fixed parameters are text in the workflow data, so
`param_matches(stored, wanted)` compares them by value: `"60"` matches a stored
`60`, `"a.v,b.v"` a stored `("a.v", "b.v")`, and a stored text value is compared
as text, exactly as before.

**Compatibility, without a migration.** A project saved by an earlier version
loads unchanged: its `ToolRun` parameters are text, and text is a
`ParamValue`. Nothing rewrites them, so saving the project again writes the
same bytes. The audit chain hashes each entry's `details`, which name the tool
and the run but not its parameters, so it verifies whether a run's parameters
are text or typed. `ToolRun.typed(spec)` is the reader for code that wants the
typed values of an old run: it parses each stored text value by the tool's
contract, and keeps a value that no longer parses as the text it was. The test
fixture `tests/fixtures/projects/m28-tool-runs.json` was saved by v1.22 (before
M39) and is loaded, verified, re-saved byte for byte, and read typed.

## The typed work packet

`WorkPacket` (`runtime/context.py`) becomes a frozen Pydantic model, and each
scope a typed model:

- `role: RoleCard`, the agent card (`Organization.agent_card`), validated with
  unknown keys forbidden, so a card that grows a field must say its type;
- `company: CompanyScope` (name, constitution of `Principle`);
- `domain: DomainScope` (skills, as `SkillView`);
- `project: ProjectScope` (requirement, intent, features, parameters, and the
  recorded `Assumption` and `Decision` models themselves);
- `task: TaskScope`: the task's fields, its `EvidenceRequirement` models
  themselves, upstream and own artifacts as `ArtifactView`, evidence as
  `EvidenceView`, attempts as `AttemptView` with their `FailedRun`s, reviews as
  `ReviewView`;
- `memory: tuple[MemoryEntry, ...]`, the recorded entries themselves.

`prompt.py`, `model.py`, and `selection.py` read attributes. Nothing reads the
packet as a dict, and the packet carries no dict except the ones whose keys are
data (a project's parameters, a role's skill proficiencies).

**Prompts are unchanged.** `tests/fixtures/prompts/` holds prompts rendered by
the dict packet before this change: a triage seat's work prompt (with its
pre-flight VeriTriage run), a root-cause work and review prompt (evidence from
upstream tasks), an RTL seat's prompt (approved upstream files with content),
and a repair prompt (a refused attempt's failed runs, with the log lines
masked, since they come from the installed Verilator). The typed packet renders
each byte for byte.

## What does not change

Contracts and kinds, the refusal rules (an undeclared name, an ill-typed
value, a comma in a path, several values for a one-value kind), the
recorded-failure rule for a missing required input, tools without a contract,
stored projects, the audit chain, and prompt text.

## Tests

`tests/test_nirmaan_typed_values.py`:

- a typed round trip: the CLI's text and a caller's list reach the binding
  typed, are stored typed, and survive a save and a reload;
- bad types (`timeout=soon`, `utilization=wide`, `seed=1.5`, `seed=True`) are
  refused before any probe or binding, and record no run;
- the pre-M39 fixture loads, verifies, re-saves byte for byte, and reads typed;
- a requirement's fixed text parameters match typed and legacy runs;
- the packet is typed, end to end, and the golden prompts are byte-identical;
- crown jewel `test_a_new_typed_tool_needs_no_core_changes`: an extension
  declares a tool with an integer, a number, and a list of paths, and its
  binding receives them typed with no core change;
- the import laws and the contract scan stay green
  (`test_nirmaan_architecture.py`, `test_nirmaan_contracts.py`).

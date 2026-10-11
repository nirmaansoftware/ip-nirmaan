# Scoped registries (M49)

Review gap 10 (`docs/architecture/current-state.md`), the principal-engineer
review's risk 7 and recommendation 8: Nirmaan's extension points are
module-level dicts. They make extension cheap, but two organizations or two
configurations cannot coexist in one process, tests clean up with global
`unregister_*` calls, and since M36 several threads read them during one
`--jobs` run. This milestone keeps every `register_*` and `unregister_*`
function exactly as it is and changes what sits behind them.

## 1. Inventory

Nirmaan has 23 registries in 17 modules (the review counted 20 `register_*`
entry points; `_PROBES` and `_BOUND` ride along with bindings and backends,
and `register_link_kind` and `register_item_kind` each have one). Each is
now a `Registry` with the name in the first column.

| Registry name | Module, old variable | Holds | Read by |
|---|---|---|---|
| `org.extensions` | `org/organization.py` `_EXTENSIONS` | functions that add units, skills, workflows, policies | `OrganizationBuilder.build` |
| `policy.checks` | `work/policy.py` `_CHECKS` | constitution checks by ID | `PolicyEngine` (construction and `evaluate`) |
| `engine.approval_consumers` | `work/engine.py` `_APPROVAL_CONSUMERS` | what approving an artifact kind also records (M29) | `TaskEngine` approval |
| `runtime.runtimes` | `runtime/base.py` `_RUNTIMES` | agent runtime factories | `get_runtime` (CLI, loop, evals) |
| `runtime.bindings` | `runtime/tools.py` `_BINDINGS` | real implementations behind AVAILABLE tools | `ToolBroker`, `available_bindings` |
| `runtime.probes` | `runtime/tools.py` `_PROBES` | per binding "can it run here" probes | `unavailable_reason` (broker) |
| `runtime.model_profiles` | `runtime/selection.py` `_PROFILES` | model profiles (seeded from `company/model_profiles.py`) | `select_model`, pricing of recorded calls |
| `runtime.llm_factories` | `runtime/selection.py` `_LLM_FACTORIES` | providers served outside the M17 registry | `llm_for` |
| `eda.backends` | `integrations/eda.py` `_BACKENDS` | backends per EDA tool | `select_backend`, the tool binding and probe |
| `eda.bound` | `integrations/eda.py` `_BOUND` | tools whose broker binding a backend created | `register_backend`, `unregister_backend` |
| `dft.rules` | `integrations/dft.py` `_RULES` | DFT rules | `check_design` |
| `firmware.cosim_buses` | `integrations/firmware.py` `_COSIM_BUSES` | bus manager sources for host co-simulation (M41) | `cosim_bus`, the cosim runner |
| `firmware.cores` | `integrations/firmware_riscv.py` `CORES` | RISC-V cores for the SoC | the SoC build and backends |
| `firmware.buses` | `integrations/firmware_riscv.py` `BUSES` | SoC bridges, matched by ports | bus detection |
| `mcp.tools` | `mcp/tools.py` `_TOOLS` | Nirmaan MCP tools | `list_tools`, `call_tool` |
| `proposals.rules` | `proposals.py` `_RULES` | learning proposal rules (M33) | `propose` |
| `eval_proposals.rules` | `eval_proposals.py` `_RULES` | proposal rules over evaluation results (M42) | eval proposals |
| `evals.scorers` | `evals/scorers.py` `_SCORERS` | seat evaluation scorers (M27) | the evaluation runner |
| `regmap.lowerings` | `regmap.py` `_LOWERINGS` | register map lowerings (M30) | `lower`, `lowerings` |
| `engineering.link_kinds` | `engineering.py` `_LINK_OVERLAY` | link kinds over the declared table | `link_kinds` |
| `engineering.item_kinds` | `engineering.py` `_ITEM_OVERLAY` | verification item kinds over the declared table | `item_kinds` |
| `export.folders` | `export.py` `_OVERLAY` | deliverable folders over the declared table | `folders` |
| `export.section_writers` | `export.py` `_SECTION_WRITERS` | writers for sections that live outside `export.py` | `export_project` |

(`firmware.register_map_sources` is not a registry; its name only starts with
`register_`.)

VeriTriage has its own 20 registries (`agents`, `ai`, `automation` rules and
triggers, `collab` annotation targets, `conversation` handlers, `design`
extractors, `engineering` and `project` providers, `knowledge` packs,
`learning` learners, `mcp` tools, `orchestrator` profiles and steps,
`planning` sources, `project` insights and log origins, `reasoning`
generators, `waveform` adapters). They are out of scope: VeriTriage may not
import `nirmaan.registry`, Nirmaan runs it through one bridge, and nothing in
Nirmaan needs two VeriTriage configurations at once. See section 6.

## 2. The abstraction

`src/nirmaan/registry.py` holds two classes and nothing else.

* **`Registry(name)`** is a handle, declared once at module level where the
  old dict was (`_CHECKS = Registry("policy.checks")`). It is a
  `MutableMapping`, so every existing line that reads or writes the old dict
  (`in`, `[]`, `.get`, `.pop`, `.values()`, `sorted(...)`) works unchanged.
  It stores nothing itself: every operation goes to the current `Registries`.
  Declaring a name twice is an error, and `Registries.kinds()` lists every
  declared name.
* **`Registries`** is the context object: a dict of layers, one per registry
  name, and an optional parent. The process has one default instance
  (`Registries.default()`), with no parent. A scoped instance has a parent
  (the instance that was current when it was made):
  * a lookup checks the scope's own layer, then its parent's, down to the
    defaults;
  * iteration lists the defaults' keys first, then the scope's, so order (the
    first core is the default core) is kept;
  * a write goes to the scope's own layer only;
  * `pop` and `del` remove from the scope's own layer only, so a scope can
    never remove a default.

The `register_*` functions keep their checks (a duplicate ID is refused), so a
scope cannot silently replace a default: it would see the default and refuse,
as before. Registries whose functions already replace (folders, link kinds,
approval consumers) replace within the scope, and the default comes back when
the scope ends.

Two small changes in owners were needed because they mutated values in place:
`register_backend` built a list in place (`setdefault(...).append`), which in a
scope would have changed the defaults' list, so it now writes a new list; and
`_BOUND` was a set, now a registry of `True`.

## 3. How the scope travels: a ContextVar, propagated to threads

The current `Registries` is a `contextvars.ContextVar` whose unset value is
the defaults.

```python
with Registries.scoped() as scope:   # a new scope over the current one
    register_check("my-check")(fn)   # local to the scope
    ...                              # everything run here sees it
# gone here

acme = Registries()                  # or one kept per organization
with acme.using():                   # entered whenever that org is worked on
    ...
```

**Why not an explicit argument.** Passing a `Registries` to the engine,
broker and runtime would change the signature of every reader in the table
above and every call chain that reaches one: the engine calls the policy
engine, which calls checks; the broker calls bindings, which call EDA
backends, which read cores and buses; the builder calls extensions. That is
dozens of signatures across the core, and every one of them is an edit M44 and
every existing extension would have to absorb. The module-level `register_*`
functions would still need some implicit target. The ContextVar keeps all of
that unchanged, and still gives the explicit object the review asked for: a
`Registries` is a value an organization or a run can hold and enter.

**Threads.** A new `threading.Thread` starts with an empty context on the
Python versions CI runs (3.11, 3.12), so a ContextVar does not cross into it
on its own. Nirmaan starts threads in one place, `runtime/writer.together`
(M36's `--jobs`), and it now runs each thread's body in a copy of the
caller's context (`contextvars.copy_context().run`, one copy per thread,
since a context cannot be entered by two threads at once). Every thread of a
batch therefore sees the same `Registries` instance as the caller: a
consistent view. The test in section 5 fails without that line. Any future
place that starts a thread must do the same; asyncio tasks copy the context
already.

**Imports land in the defaults.** Most registration happens at import time
(decorators on module-level functions), and several modules are imported
lazily (`_ensure_builtin_bindings` imports every integration on first use). If
the first import of a module happened inside a scope, its built-ins would
otherwise be registered in that scope and vanish with it. So a write made
while a module is being imported (any frame on the stack is the body of a
module whose spec is still initializing) goes to the defaults, whatever scope
is current. Import-time registration is process-wide by definition.

## 4. Thread safety

Each `Registries` has a lock. Writes and removals take it; iteration takes a
snapshot of the merged keys under it, so a reader iterating while another
thread registers never sees "dictionary changed size during iteration".
Single-key lookups are plain dict reads (atomic under the GIL) and take no
lock. Registration is still expected at import time or before a run starts;
the lock makes a late write safe, not meaningful to a run already reading.

## 5. Tests

`tests/test_scoped_registries.py`, written first and failing:

* two scopes are isolated from each other (an extension and a lowering
  registered in one are invisible in the other and in the defaults);
* a scope falls through to the defaults (built-in checks, runtimes, cores)
  and nested scopes fall through to their parent;
* scoped registrations vanish when the scope ends, and a scope cannot remove
  or replace a default;
* an import made inside a scope registers in the defaults;
* every registry listed in section 1 is a `Registry` (no plain dict left);
* concurrency: under `loop(..., jobs=4)`, a scoped extension adds a principle
  whose scoped policy check is run from several worker threads, while another
  thread keeps registering and removing in the defaults; the run succeeds and
  the check is gone afterwards;
* crown jewel: a new registry kind, declared in the test file, joins
  `Registries.kinds()` and is scoped like the others with no change to
  `registry.py`;
* the import laws: `nirmaan.registry` imports only the standard library, and
  VeriTriage never imports it.

Migrated off global `unregister_*` cleanup, as the pattern (a `registries`
fixture in `tests/conftest.py` enters a fresh scope for one test):

* `test_nirmaan_architecture.py`: the photonics crown jewel;
* `test_nirmaan_loop_concurrency.py`: the `fan_org` fixture;
* `test_nirmaan_mcp.py`: the throwaway-tool test.

## 6. Deferred (optional follow-up)

* **The remaining tests.** About 30 test files still register globally and
  clean up with `unregister_*` (`git grep -l "unregister_" tests`): among the
  Nirmaan ones, `test_nirmaan_formal_gate.py`,
  `test_nirmaan_engineering_graph.py`, `test_nirmaan_live_eval.py`,
  `test_nirmaan_typed_values.py`, `test_nirmaan_review_repair.py`,
  `test_nirmaan_repair.py`, `test_nirmaan_physical.py`,
  `test_nirmaan_design_agents.py`, `test_nirmaan_contracts.py`,
  `test_nirmaan_auto_loop.py`, `test_nirmaan_verification_plan.py`,
  `test_nirmaan_verification_plan_more.py`, `test_nirmaan_model_selection.py`,
  `test_nirmaan_evals.py`, `test_nirmaan_eda.py`,
  `test_nirmaan_sta_antecedents.py`, `test_nirmaan_riscv_next.py`,
  `test_nirmaan_riscv_firmware.py`, `test_nirmaan_firmware_irq.py`,
  `test_nirmaan_regmap_adoption.py`. Each can take the `registries` fixture
  and drop its `try`/`finally`. They work as they are.
* **VeriTriage's registries.** Scoping them needs the same abstraction inside
  VeriTriage (it may not import Nirmaan), either a copy or a small shared
  package both depend on. Not needed until Nirmaan runs two VeriTriage
  configurations at once.
* **An organization that carries its scope.** `Organization` could hold its
  `Registries` and the engine could enter it, so callers never write
  `using()`. Today a caller that builds two organizations with different
  extensions keeps one `Registries` per organization and enters it.
* **The CLI and MCP server** run in the defaults; neither needs a scope yet.

"""Milestone 49: scoped registries.

Every Nirmaan extension point is a ``Registry`` in one ``Registries`` context
object. The process has a default instance, and the module-level
``register_*`` and ``unregister_*`` functions write to whichever instance is
current. A scope layers over the defaults: lookups fall through, registrations
stay local and vanish when it ends, and M36's ``--jobs`` threads see the scope
of the run that started them (docs/SCOPED_REGISTRIES.md).
"""

from __future__ import annotations

import importlib
import sys
import threading
from pathlib import Path

import pytest

from laws import imports

import nirmaan
from nirmaan.registry import Registries, Registry

NIRMAAN = Path(nirmaan.__file__).parent

#: Every registry Nirmaan had as a module-level dict, by module and variable (section 1 of the doc).
INVENTORY = {
    "nirmaan.org.organization": {"_EXTENSIONS": "org.extensions"},
    "nirmaan.work.policy": {"_CHECKS": "policy.checks"},
    "nirmaan.work.engine": {"_APPROVAL_CONSUMERS": "engine.approval_consumers"},
    "nirmaan.runtime.base": {"_RUNTIMES": "runtime.runtimes"},
    "nirmaan.runtime.tools": {"_BINDINGS": "runtime.bindings", "_PROBES": "runtime.probes"},
    "nirmaan.runtime.selection": {"_PROFILES": "runtime.model_profiles", "_LLM_FACTORIES": "runtime.llm_factories"},
    "nirmaan.integrations.eda": {"_BACKENDS": "eda.backends", "_BOUND": "eda.bound"},
    "nirmaan.integrations.dft": {"_RULES": "dft.rules"},
    "nirmaan.integrations.firmware": {"_COSIM_BUSES": "firmware.cosim_buses"},
    "nirmaan.integrations.firmware_riscv": {"CORES": "firmware.cores", "BUSES": "firmware.buses"},
    "nirmaan.mcp.tools": {"_TOOLS": "mcp.tools"},
    "nirmaan.proposals": {"_RULES": "proposals.rules"},
    "nirmaan.eval_proposals": {"_RULES": "eval_proposals.rules"},
    "nirmaan.evals.scorers": {"_SCORERS": "evals.scorers"},
    "nirmaan.regmap": {"_LOWERINGS": "regmap.lowerings"},
    "nirmaan.engineering": {"_LINK_OVERLAY": "engineering.link_kinds", "_ITEM_OVERLAY": "engineering.item_kinds"},
    "nirmaan.export": {"_OVERLAY": "export.folders", "_SECTION_WRITERS": "export.section_writers"},
}


def _lower(regmap) -> str:
    return "lowered"


# --- The inventory ---------------------------------------------------------------------------------


def test_every_registry_is_a_registry_in_the_context_object():
    for module, variables in INVENTORY.items():
        mod = importlib.import_module(module)
        for variable, name in variables.items():
            registry = getattr(mod, variable)
            assert isinstance(registry, Registry), f"{module}.{variable} is still a plain {type(registry).__name__}"
            assert registry.name == name
    declared = set(Registries.kinds())
    assert {n for v in INVENTORY.values() for n in v.values()} <= declared


def test_no_plain_dict_registry_is_left_behind_a_register_function():
    """A module with a ``register_*`` function keeps what it registers in a Registry, not a dict or set."""
    import ast

    for path in sorted(NIRMAAN.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not any(isinstance(n, ast.FunctionDef) and n.name.startswith("register_") for n in tree.body):
            continue
        for node in tree.body:
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
            target = (node.targets[0] if isinstance(node, ast.Assign) else getattr(node, "target", None))
            if value is None or not isinstance(target, ast.Name) or target.id != target.id.upper():
                continue
            empty = (isinstance(value, ast.Dict) and not value.keys) or (
                isinstance(value, ast.Call) and getattr(value.func, "id", "") in ("set", "dict") and not value.args)
            assert not empty, f"{path.name}: {target.id} is a module-level {ast.unparse(value)}"


# --- Scopes ----------------------------------------------------------------------------------------


def test_two_scopes_are_isolated_from_each_other_and_from_the_defaults():
    from nirmaan.company import builder
    from nirmaan.models import Function, OrgUnit, UnitKind
    from nirmaan.org import available_extensions, register_extension
    from nirmaan.regmap import lowerings, register_lowering

    acme, globex = Registries(), Registries()
    with acme.using():
        register_lowering("test-acme")(_lower)

        @register_extension("test-acme-unit")
        def acme_unit(b):
            b.add(OrgUnit(id="design.acme", name="Acme Design", kind=UnitKind.TEAM, function=Function.ENGINEERING,
                          parent="design", noun="Acme Engineer"))

        assert "test-acme" in lowerings() and "design.acme" in builder().build().units
    with globex.using():
        register_lowering("test-globex")(_lower)
        assert "test-acme" not in lowerings() and "test-globex" in lowerings()
        assert "test-acme-unit" not in available_extensions()
        assert "design.acme" not in builder().build().units
    assert not {"test-acme", "test-globex"} & set(lowerings())
    assert "test-acme-unit" not in available_extensions()
    with acme.using():  # a scope kept by its owner is the same scope when entered again
        assert "test-acme" in lowerings() and "test-globex" not in lowerings()


def test_a_scope_falls_through_to_the_defaults_and_nests():
    from nirmaan.integrations.firmware_riscv import CORES
    from nirmaan.regmap import lowerings, register_lowering
    from nirmaan.runtime import available_runtimes
    from nirmaan.work.policy import available_checks

    defaults = (available_checks(), available_runtimes(), list(CORES), lowerings())
    assert all(defaults)
    with Registries.scoped() as outer:
        assert (available_checks(), available_runtimes(), list(CORES), lowerings()) == defaults
        assert next(iter(CORES)) == "picorv32"  # order kept: the first core is the default core
        register_lowering("test-outer")(_lower)
        with Registries.scoped() as inner:
            assert inner is not outer and Registries.current() is inner
            register_lowering("test-inner")(_lower)
            assert {"test-outer", "test-inner"} <= set(lowerings())
            assert set(defaults[3]) <= set(lowerings())
        assert Registries.current() is outer
        assert "test-outer" in lowerings() and "test-inner" not in lowerings()
    assert Registries.current() is Registries.default()


def test_scoped_registrations_vanish_and_a_scope_cannot_remove_or_replace_a_default():
    from nirmaan.work.policy import available_checks, register_check, unregister_check

    builtin = available_checks()[0]
    with Registries.scoped():
        register_check("test-scoped-check")(lambda ctx: [])
        assert "test-scoped-check" in available_checks()
        unregister_check(builtin)  # removes only from the scope's own layer: nothing there
        assert builtin in available_checks()
        with pytest.raises(ValueError):
            register_check(builtin)(lambda ctx: [])  # the default is seen, so the duplicate is refused
    assert "test-scoped-check" not in available_checks() and builtin in available_checks()


def test_a_replacing_registry_replaces_within_the_scope_only():
    from nirmaan.export import folders, register_folder

    first = folders()[0]
    with Registries.scoped():
        register_folder(first.model_copy(update={"title": "test-remapped"}))
        register_folder(first.model_copy(update={"id": "test-extra-folder"}))
        assert folders()[0].title == "test-remapped" and "test-extra-folder" in {f.id for f in folders()}
    assert folders()[0] == first and "test-extra-folder" not in {f.id for f in folders()}


def test_a_backend_registered_in_a_scope_leaves_the_defaults_list_alone():
    from nirmaan.integrations.eda import Backend, backends_for, register_backend
    from nirmaan.runtime.tools import available_bindings

    tool = next(t for t in available_bindings() if backends_for(t))
    before = backends_for(tool)
    with Registries.scoped():
        register_backend(Backend(tool=tool, name="test-scoped-backend", executables=("nirmaan-no-such-tool",),
                                 steps=lambda job: [], parse=None))
        assert [b.name for b in backends_for(tool)] == [b.name for b in before] + ["test-scoped-backend"]
        register_backend(Backend(tool="test.scoped_tool", name="only", executables=(), steps=lambda job: [],
                                 parse=None))
        assert "test.scoped_tool" in available_bindings()
    assert backends_for(tool) == before and "test.scoped_tool" not in available_bindings()


def test_a_module_first_imported_inside_a_scope_registers_in_the_defaults(tmp_path, monkeypatch):
    from nirmaan.regmap import lowerings, unregister_lowering

    (tmp_path / "m49_late_extension.py").write_text(
        "from nirmaan.regmap import register_lowering\n\n\n"
        "@register_lowering('test-imported-in-scope')\ndef lower(regmap):\n    return ''\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        with Registries.scoped():
            importlib.import_module("m49_late_extension")
        assert "test-imported-in-scope" in lowerings()  # import-time registration is process-wide
    finally:
        unregister_lowering("test-imported-in-scope")
        sys.modules.pop("m49_late_extension", None)


def test_the_registries_fixture_gives_each_test_its_own_scope(registries):
    from nirmaan.regmap import lowerings, register_lowering

    assert Registries.current() is registries and registries is not Registries.default()
    register_lowering("test-fixture-scope")(_lower)  # no unregister: the scope ends with the test
    assert "test-fixture-scope" in lowerings()


# --- Concurrency: M36's --jobs threads read the run's scope ------------------------------------------


def test_jobs_threads_see_the_scope_while_the_defaults_change(fixed_clock):
    from nirmaan.company import builder
    from nirmaan.models import (
        Criticality,
        Enforcement,
        EvidenceKind,
        EvidenceRequirement,
        IntentRule,
        Principle,
        StageTemplate,
        WorkflowTemplate,
    )
    from nirmaan.orchestrator import Orchestrator
    from nirmaan.org import register_extension
    from nirmaan.runtime import MockLLM, ModelRuntime, loop
    from nirmaan.work.policy import available_checks, register_check, unregister_check

    seen: set[int] = set()
    lock = threading.Lock()
    stop = threading.Event()
    churned: list[BaseException] = []

    def witness(ctx) -> list[str]:
        available_checks()  # iterates the merged view while another thread writes the defaults
        with lock:
            seen.add(threading.get_ident())
        return []

    def churn() -> None:  # a fresh thread: its context is empty, so it writes the defaults
        try:
            i = 0
            while not stop.is_set():
                register_check(f"test-churn-{i % 7}")(witness)
                unregister_check(f"test-churn-{(i + 3) % 7}")
                i += 1
        except BaseException as exc:  # pragma: no cover - only on failure
            churned.append(exc)

    with Registries.scoped():
        register_check("test-scoped-witness")(witness)

        @register_extension("test-scoped-jobs")
        def jobs(b):
            read = EvidenceRequirement(description="Project status read", accepts=(EvidenceKind.TOOL_RUN,),
                                       tools=("status.read",))
            b.add(
                Principle(id="P-test-scoped", title="Scoped witness", statement="Seen by every worker.",
                          enforcement=Enforcement.WARN, checks=("test-scoped-witness",)),
                IntentRule(intent="scoped_jobs", patterns=(r"\bscoped jobs\b",), priority=5),
                WorkflowTemplate(
                    id="scoped-jobs", name="Scoped jobs", description="Independent stages.", intents=("scoped_jobs",),
                    stages=tuple(StageTemplate(id=f"sj-{s}", title=s, phase="Requirements", capability="req.analyze",
                                               criticality=Criticality.MEDIUM, outputs=("requirements_spec",),
                                               evidence=(read,)) for s in "abcd"),
                ),
            )

        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Run scoped jobs for a timer.")
        churner = threading.Thread(target=churn, daemon=True)
        churner.start()
        try:
            report = loop(engine, ModelRuntime(MockLLM()), ModelRuntime(MockLLM()), jobs=4)
        finally:
            stop.set()
            churner.join()
        assert report.steps and not churned
        assert len(seen - {threading.get_ident()}) >= 2  # several worker threads ran the scoped check
    assert "test-scoped-witness" not in available_checks()
    for i in range(7):
        unregister_check(f"test-churn-{i}")


# --- Crown jewel: a new registry kind needs no change to the registry module --------------------------

WIDGETS = Registry("test.widgets")


def register_widget(name: str, widget: str) -> None:
    if name in WIDGETS:
        raise ValueError(f"widget {name!r} is already registered")
    WIDGETS[name] = widget


def unregister_widget(name: str) -> None:
    WIDGETS.pop(name, None)


def test_a_new_registry_kind_joins_registries_with_zero_core_changes():
    assert "test.widgets" in Registries.kinds()
    with pytest.raises(ValueError):
        Registry("test.widgets")  # one name, one registry
    register_widget("default-widget", "d")
    try:
        with Registries.scoped():
            register_widget("scoped-widget", "s")
            assert dict(WIDGETS) == {"default-widget": "d", "scoped-widget": "s"}
            unregister_widget("default-widget")
            assert "default-widget" in WIDGETS
        assert dict(WIDGETS) == {"default-widget": "d"}
    finally:
        unregister_widget("default-widget")
    assert not WIDGETS


# --- Laws ------------------------------------------------------------------------------------------


def test_the_registry_module_imports_only_the_standard_library():
    for module in imports(NIRMAAN / "registry.py"):
        assert module.split(".")[0] in sys.stdlib_module_names or module == "__future__", module


def test_veritriage_never_imports_the_registry():
    for path in sorted((NIRMAAN.parent / "veritriage").rglob("*.py")):
        assert not any(m.startswith("nirmaan") for m in imports(path)), path

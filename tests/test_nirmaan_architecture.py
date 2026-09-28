"""Milestone 19: the laws that keep IP Nirmaan an organization, not a script.

* VeriTriage never imports Nirmaan; Nirmaan reaches VeriTriage through exactly
  one bridge module.
* The vocabulary imports nothing but pydantic and the standard library.
* The orchestrator and router name no department, protocol, or role: routing
  is data-driven (a test reads their string constants).
* The standing no-dash rule holds for everything this milestone added.
* Crown jewel: a whole new engineering domain plugs in through one registered
  extension and is planned, routed, reviewed, and gated with zero core changes.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from typer.testing import CliRunner

import nirmaan
from nirmaan.models import (
    Capability,
    CapabilityKind,
    Criticality,
    FeatureRule,
    Function,
    IntentRule,
    Level,
    OrgUnit,
    ReviewRequirement,
    Skill,
    StageTemplate,
    TaskKind,
    ToolRisk,
    ToolSpec,
    UnitKind,
    WorkflowTemplate,
)
from nirmaan.orchestrator import Orchestrator

NIRMAAN = Path(nirmaan.__file__).parent
SRC = NIRMAAN.parent
REPO = SRC.parent


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _sources(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def test_veritriage_never_imports_nirmaan():
    for path in _sources(SRC / "veritriage"):
        assert not any(m == "nirmaan" or m.startswith("nirmaan.") for m in _imports(path)), path


def test_only_the_bridge_imports_veritriage():
    bridge = NIRMAAN / "integrations" / "veritriage.py"
    for path in _sources(NIRMAAN):
        uses = any(m == "veritriage" or m.startswith("veritriage.") for m in _imports(path))
        assert uses == (path == bridge), path


def test_the_vocabulary_is_plain_data():
    allowed = {"__future__", "enum", "datetime", "typing", "pydantic"}
    for path in _sources(NIRMAAN / "models"):
        for module in _imports(path):
            assert module.split(".")[0] in allowed or module.startswith("nirmaan.models"), (path, module)


def test_routing_names_no_domain():
    """No string constant in the orchestrator or router names a unit, skill, capability, or role."""
    from nirmaan.company import build_organization

    org = build_organization()
    vocabulary = (set(org.units) | set(org.skills) | set(org.capabilities) | set(org.roles)
                  | {f.feature for f in org.features} | {i.intent for i in org.intents})
    vocabulary -= {"note"}
    for path in _sources(NIRMAAN / "orchestrator"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                      and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                assert node.value not in vocabulary, f"{path.name} hard-codes {node.value!r}"


def test_the_engine_is_the_only_writer():
    """Nothing outside the task engine constructs a new ProjectState (no hidden writes)."""
    for path in _sources(NIRMAAN):
        if path.name in ("engine.py", "planner.py", "work.py") or "models" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        assert "ProjectState(" not in text and "._state =" not in text, path


def test_no_em_or_en_dashes_in_milestone_19():
    targets = [*_sources(NIRMAAN), *REPO.joinpath("tests").glob("test_nirmaan_*.py"),
               REPO / "tests" / "nirmaan_helpers.py"]
    targets += [p for p in (REPO / "docs").glob("NIRMAAN*.md")]
    for path in targets:
        text = path.read_text(encoding="utf-8")
        assert chr(0x2014) not in text and chr(0x2013) not in text, path


# --- Crown jewel ---------------------------------------------------------------------------


def test_a_new_engineering_domain_needs_only_an_extension(fixed_clock):
    """Silicon photonics joins the company: unit, skill, capability, tool, workflow, intent.

    Nothing in the orchestrator, router, engine, or policy changes; the plan it
    produces is owned, independently reviewed, gated, and escalatable.
    """
    from nirmaan.company import builder
    from nirmaan.org import register_extension, unregister_extension

    @register_extension("test-photonics")
    def photonics(b):
        b.add(
            ToolSpec(id="photonics.sim", name="Photonic simulator", category="eda", risk=ToolRisk.EXECUTE),
            Capability(id="photonics.design", name="Photonic design", kind=CapabilityKind.EXECUTION,
                       description="Design waveguides and modulators.", produces=("photonic_layout",)),
            Capability(id="photonics.review", name="Photonic review", kind=CapabilityKind.REVIEW,
                       description="Review photonic designs."),
            Skill(id="silicon_photonics", name="Silicon photonics", domain="photonics",
                  provides=("photonics.design", "photonics.review"), tools=("photonics.sim",),
                  validation_criteria=("Insertion loss is within budget.",)),
            OrgUnit(id="design.photonics", name="Photonics Design", kind=UnitKind.TEAM,
                    function=Function.ENGINEERING, parent="design", noun="Photonics Engineer",
                    skills=("silicon_photonics",)),
            IntentRule(intent="photonic_block", patterns=(r"\bwaveguide|\bphotonic",), priority=5),
            FeatureRule(feature="optical", patterns=(r"\boptical|\bphotonic",), skills=("silicon_photonics",)),
            WorkflowTemplate(
                id="photonic-block", name="Photonic block", description="Design a photonic block.",
                intents=("photonic_block",),
                stages=(
                    StageTemplate(id="design", title="Photonic design", phase="Photonics",
                                  capability="photonics.design", criticality=Criticality.HIGH,
                                  review=ReviewRequirement(capability="photonics.review", min_level=Level.SENIOR)),
                ),
            ),
        )

    try:
        org = builder().build()
        engine = Orchestrator(org, clock=fixed_clock).plan("Design a photonic ring modulator.")
        task = next(t for t in engine.state.tasks.values() if t.kind is TaskKind.WORK)
        assert task.owner.startswith("design.photonics.") and task.reviewer.startswith("design.photonics.")
        assert task.reviewer != task.owner and task.approver == "design.photonics.tech_lead"
        assert task.escalation_path[0] == org.roles[task.owner].escalates_to
        assert "photonics.sim" in org.tools_of(task.owner)
    finally:
        unregister_extension("test-photonics")
    assert "design.photonics" not in builder().build().units


# --- The CLI is a thin client ------------------------------------------------------------------


@pytest.fixture()
def cli():
    from nirmaan.cli import app

    runner = CliRunner()
    return lambda *args: runner.invoke(app, list(args))


def test_cli_inspects_the_organization(cli):
    result = cli("org", "tree", "--depth", "1")
    assert result.exit_code == 0 and "Verification" in result.output and "IP Nirmaan" in result.output
    assert "Staff NoC Microarchitect" in cli("org", "role", "architecture.micro.noc.staff").output
    assert cli("org", "validate").exit_code == 0
    assert "P12" in cli("policies").output


def test_cli_plans_saves_and_explains(cli, tmp_path):
    result = cli("plan", "Create a 4-port AXI-to-NoC bridge.", "--root", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert "PROGRAM MANAGER" in result.output and "GATE Gate: Architecture approval" in result.output
    project = next((tmp_path / "projects").glob("*.json")).stem
    why = cli("why", project, "microarchitecture", "--root", str(tmp_path))
    assert why.exit_code == 0 and "IP architecture" in why.output
    status = cli("status", project, "--root", str(tmp_path))
    assert "Gates" in status.output
    refused = cli("task", "start", project, "requirements", "--as", "product.management.roadmap.junior",
                  "--root", str(tmp_path))
    assert refused.exit_code == 1 and "only the owner" in refused.output
    assert cli("audit", project, "--root", str(tmp_path)).output.count("intact") == 1
    html = tmp_path / "dash.html"
    assert cli("dashboard", project, "-o", str(html), "--root", str(tmp_path)).exit_code == 0
    assert "Assurance ladder" in html.read_text()


def test_cli_reports_unrecognized_requirements(cli, tmp_path):
    result = cli("plan", "Order pizza for the team.", "--root", str(tmp_path))
    assert result.exit_code == 1 and "does not recognize" in result.output

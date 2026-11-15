"""The harness is one module, and its fingerprint changes with every setting in it (M73).

``nirmaan.runtime.harness`` lists every setting around the model in a seat's
run; the code reads each from there, and no other module defines one.
``harness_sha256`` covers every setting, the code of the files that shape a
seat's run, and the run's own options. Every eval trial records it, on its
result and on each answer.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from nirmaan.evals import load_cases, load_record, record_run
from nirmaan.models import Limits, OnFailure
from nirmaan.org.knowledge import over_domain_cap
from nirmaan.runtime import harness
from nirmaan.runtime.claude_code import ClaudeCodeLLM
from nirmaan.runtime.files import excerpt
from nirmaan.runtime.harness import CODE, SETTINGS, fingerprint, harness_sha256
from nirmaan.work.limits import limits_for

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
HARNESS = SRC / "nirmaan" / "runtime" / "harness.py"
#: Names in harness.py that are not settings: its bookkeeping, and the pieces WORK_SYSTEM and REVIEW_SYSTEM
#: are built from (in the fingerprint through those two).
BOOKKEEPING = {"FORMAT", "VERSION", "SETTINGS", "SOURCE_ROOT", "CODE", "OUTPUT_WORK", "FILE_FORMAT", "OUTPUT_REVIEW",
               "VARIANTS"}
#: The runtime files that are not harness code, and why. A new runtime file must be put in ``CODE`` or here.
NOT_HARNESS = {
    "nirmaan/runtime/__init__.py": "re-exports only",
    "nirmaan/runtime/harness.py": "the settings themselves, in the fingerprint by value",
    "nirmaan/runtime/loop.py": "the drive loop over many tasks; an eval seat runs through run_task alone",
    "nirmaan/runtime/tools.py": "the tool broker: every tool run is recorded on its own",
    "nirmaan/runtime/writer.py": "the concurrency writer, which keeps the order of state the same for any jobs",
}
#: Module-level constants those files may hold; any other is a harness setting until shown otherwise.
NOT_HARNESS_CONSTANTS = {"_OWNER_STATES", "_DONE_STATES", "T", "_BINDINGS", "_PROBES"}


def _constants(path: Path) -> set[str]:
    """Module-level names assigned in a file that are spelled as constants (upper case, maybe one ``_``)."""
    names: set[str] = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(
            node, ast.AnnAssign) else []
        names.update(t.id for t in targets if isinstance(t, ast.Name) and t.id.lstrip("_").isupper())
    return names


def _other(value):
    """A value of the same kind that differs from ``value``."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return value + " changed"
    if isinstance(value, tuple):
        return (*value, "changed")
    if isinstance(value, Limits):
        return value.model_copy(update={"attempts": value.attempts + 1})
    raise AssertionError(f"no test value for {value!r}")


# --- One place ---------------------------------------------------------------------------------


def test_every_constant_in_the_harness_module_is_a_setting_in_the_fingerprint():
    constants = _constants(HARNESS)
    assert set(SETTINGS) == constants - BOOKKEEPING
    assert set(fingerprint()["settings"]) == set(SETTINGS)


def test_no_other_module_defines_a_harness_setting():
    offenders = [f"{path.relative_to(SRC)}: {name}" for path in sorted(SRC.rglob("*.py")) if path != HARNESS
                 for name in _constants(path) & set(SETTINGS)]
    assert not offenders, offenders


def test_every_runtime_file_is_harness_code_or_says_why_not():
    runtime = {p.relative_to(SRC).as_posix() for p in (SRC / "nirmaan" / "runtime").glob("*.py")}
    assert runtime - set(CODE) == set(NOT_HARNESS), "put a new runtime file in harness.CODE or in NOT_HARNESS"
    assert not set(NOT_HARNESS) & set(CODE)
    assert all((SRC / rel).is_file() for rel in CODE), [rel for rel in CODE if not (SRC / rel).is_file()]


def test_the_runtime_files_outside_the_code_hold_no_new_constant():
    """A constant added there would shape no fingerprint: it belongs in harness.py, or is shown not to matter."""
    for rel in set(NOT_HARNESS) - {"nirmaan/runtime/harness.py"}:
        extra = _constants(SRC / rel) - NOT_HARNESS_CONSTANTS
        assert not extra, f"{rel}: {sorted(extra)}: a harness setting goes in nirmaan/runtime/harness.py"


def test_the_code_reads_each_setting_from_the_harness(monkeypatch):
    monkeypatch.setattr(harness, "DOMAIN_CAP", 10)
    assert "over the domain cap of 10" in over_domain_cap(11) and over_domain_cap(10) is None
    monkeypatch.setattr(harness, "DEFAULT_LIMITS", Limits(attempts=4, review_rounds=2, retries=0,
                                                          on_failure=OnFailure.FAIL))
    org = SimpleNamespace(workflows={}, capabilities={})
    task = SimpleNamespace(workflow=None, stage=None, capability=None)
    assert limits_for(org, task, Limits(retries=3)) == Limits(attempts=4, review_rounds=2, retries=3,
                                                               on_failure=OnFailure.FAIL)
    monkeypatch.setattr(harness, "CLAUDE_CODE_TIMEOUT", 7)
    assert ClaudeCodeLLM().timeout == 7 and ClaudeCodeLLM(timeout=9).timeout == 9


def test_the_log_excerpt_reads_its_bounds_from_the_harness(monkeypatch, tmp_path):
    log = tmp_path / "run.log"
    log.write_text("".join(f"line {n} ok\n" for n in range(30)) + "ERROR here\n" + "x" * 500 + "\n")
    lines, _ = excerpt(str(log))
    assert lines == ["ERROR here"]
    monkeypatch.setattr(harness, "EXCERPT_NOTABLE", "nothing matches this")
    monkeypatch.setattr(harness, "EXCERPT_LINES", 2)
    monkeypatch.setattr(harness, "EXCERPT_WIDTH", 5)
    lines, note = excerpt(str(log))
    assert lines == ["ERROR", "xxxxx"] and note == "last 2 of 32 lines"


# --- The fingerprint ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", SETTINGS)
def test_changing_any_one_setting_changes_the_fingerprint(monkeypatch, name):
    before = harness_sha256()
    monkeypatch.setattr(harness, name, _other(getattr(harness, name)))
    assert harness_sha256() != before


def test_editing_any_harness_code_file_changes_the_fingerprint(monkeypatch, tmp_path):
    before = harness_sha256()
    for rel in CODE:
        copy = tmp_path / rel
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC / rel, copy)
    monkeypatch.setattr(harness, "SOURCE_ROOT", tmp_path)
    assert harness_sha256() == before
    for rel in CODE:
        path = tmp_path / rel
        original = path.read_bytes()
        path.write_bytes(original + b"# an edit\n")
        assert harness_sha256() != before, rel
        path.write_bytes(original)
    (tmp_path / CODE[0]).unlink()
    assert fingerprint()["code"][CODE[0]] == "missing" and harness_sha256() != before


def test_the_run_options_are_in_the_fingerprint():
    default = harness_sha256()
    assert harness_sha256(attempts=None, knowledge=True, variant="default") == default
    assert len({default, harness_sha256(attempts=3), harness_sha256(knowledge=False),
                harness_sha256(variant="attempts-3")}) == 4
    assert default.startswith("sha256:") and len(default) == len("sha256:") + 64


# --- The tool definitions (M74) ------------------------------------------------------------------


def test_every_tool_definition_is_in_the_fingerprint():
    # Council record 2026-11-14 (pilot retrospective), fact 5: a tool's parameter descriptions reach the prompt
    # as its input contract, so the catalog's definitions are harness.
    from nirmaan.company.tools import TOOLS

    assert set(fingerprint()["tools"]) == {spec.id for spec in TOOLS} and len(TOOLS) == len(fingerprint()["tools"])


@pytest.mark.parametrize("edit", ["description", "param"])
def test_editing_any_tool_definition_changes_the_fingerprint(monkeypatch, edit):
    from nirmaan.company import tools

    before = harness_sha256()
    spec = next(s for s in tools.TOOLS if s.id == "formal.run")
    if edit == "description":
        changed = spec.model_copy(update={"description": spec.description + " changed"})
    else:
        sby = spec.param("sby")
        changed = spec.model_copy(update={"params": tuple(
            p.model_copy(update={"description": p.description + " changed"}) if p is sby else p
            for p in spec.params)})
    monkeypatch.setattr(tools, "TOOLS", [changed if s is spec else s for s in tools.TOOLS])
    assert harness_sha256() != before
    monkeypatch.undo()
    assert harness_sha256() == before


# --- No user-level instruction file (M74) ----------------------------------------------------------


def test_seat_calls_run_claude_code_in_safe_mode():
    # --safe-mode is meant to keep the user-level CLAUDE.md, hooks, skills and plugins out of the seat's call;
    # this checks only the flag. The live check is scripts/claude_code_canary.py, unrecorded so far. --bare would too, but never reads the plan login.
    assert "--safe-mode" in harness.CLAUDE_CODE_FLAGS and "--bare" not in harness.CLAUDE_CODE_FLAGS


# --- Named variants (M74) --------------------------------------------------------------------------


def test_the_named_variants_are_the_default_and_three_attempts_with_the_repair_text():
    assert harness.VARIANTS == {"default": {}, "attempts-3": {"attempts": 3}}
    assert fingerprint()["run"]["variant"] == "default"
    assert fingerprint(variant="attempts-3")["run"] == {"attempts": 3, "knowledge": True, "cli": None,
                                                        "variant": "attempts-3"}
    # The variant's own attempts, given or not, is one harness; a plain --attempts 3 is not the variant.
    assert harness_sha256(variant="attempts-3") == harness_sha256(attempts=3, variant="attempts-3")
    assert harness_sha256(variant="attempts-3") != harness_sha256(attempts=3)
    with pytest.raises(ValueError, match="unknown harness variant 'nope'; known: default, attempts-3"):
        harness_sha256(variant="nope")


def test_every_variant_sets_only_run_options_a_run_can_take():
    # A variant is the default harness with run options; a setting it changed would hide in the variant table.
    for name, options in harness.VARIANTS.items():
        assert set(options) <= {"attempts"}, name
        assert all(isinstance(v, int) and v >= 1 for v in options.values()), name


def test_editing_a_variant_changes_its_fingerprint_and_never_the_default(monkeypatch):
    default, before = harness_sha256(), harness_sha256(variant="attempts-3")
    monkeypatch.setitem(harness.VARIANTS, "attempts-3", {"attempts": 4})
    assert harness_sha256(variant="attempts-3") != before and harness_sha256() == default


# --- Records -----------------------------------------------------------------------------------


def test_every_trial_records_its_harness_on_the_result_and_each_answer(nirmaan_org, fixed_clock, tmp_path):
    case = next(c for c in load_cases(ROOT / "evals") if c.id == "spec/axi4-lite-interface")
    plain = load_record(record_run(nirmaan_org, [case], None, trials=1, repo=ROOT, out=tmp_path,
                                   clock=fixed_clock))
    trial = plain.trials[0]
    assert trial.result.harness == harness_sha256() and trial.answers
    assert all(a.harness == harness_sha256() for a in trial.answers)
    ablation = load_record(record_run(nirmaan_org, [case], None, trials=1, repo=ROOT, out=tmp_path,
                                      clock=fixed_clock, knowledge=False, attempts=2))
    assert ablation.trials[0].result.harness == harness_sha256(attempts=2, knowledge=False)


def test_a_trial_on_a_variant_records_the_variant_and_its_harness(nirmaan_org, fixed_clock, tmp_path):
    case = next(c for c in load_cases(ROOT / "evals") if c.id == "spec/axi4-lite-interface")
    record = load_record(record_run(nirmaan_org, [case], None, trials=1, repo=ROOT, out=tmp_path,
                                    clock=fixed_clock, variant="attempts-3"))
    [trial] = record.trials
    assert record.path.name.endswith("-harness-attempts-3")
    assert record.manifest.harness_variant == "attempts-3" and trial.harness_variant == "attempts-3"
    assert trial.result.harness == harness_sha256(variant="attempts-3") != harness_sha256()
    assert all(a.harness == trial.result.harness for a in trial.answers)
    plain = load_record(record_run(nirmaan_org, [case], None, trials=1, repo=ROOT, out=tmp_path, clock=fixed_clock))
    assert plain.manifest.harness_variant == "default" and plain.trials[0].harness_variant == "default"
    with pytest.raises(ValueError, match="unknown harness variant"):
        record_run(nirmaan_org, [case], None, trials=1, repo=ROOT, out=tmp_path, clock=fixed_clock, variant="nope")


def test_the_cli_version_is_a_run_option_in_the_fingerprint():
    # The claude-code runtime's behaviour depends on the Claude Code version, so the version is in the harness.
    default = harness_sha256()
    assert fingerprint(cli="2.1.325")["run"]["cli"] == "2.1.325" and fingerprint()["run"]["cli"] is None
    assert len({default, harness_sha256(cli="2.1.311"), harness_sha256(cli="2.1.325")}) == 3
    assert harness_sha256(cli="2.1.325") == harness_sha256(cli="2.1.325")


def test_the_attempts_variant_gives_the_seat_three_attempts(nirmaan_org, fixed_clock, tmp_path, monkeypatch):
    # A refused attempt is then answered again with REPAIR_AFTER_REFUSAL and the log excerpt (M26's retry).
    from nirmaan.evals import evaluate, replay_llm, runner
    from nirmaan.runtime import ModelRuntime

    case = next(c for c in load_cases(ROOT / "evals") if c.id == "spec/axi4-lite-interface")
    asked: list = []
    real = runner.run_task

    def spy(*args, **kwargs):
        asked.append(kwargs["attempts"])
        return real(*args, **kwargs)

    monkeypatch.setattr(runner, "run_task", spy)
    for variant in ("attempts-3", "default"):
        seat = ModelRuntime(replay_llm(case, ROOT), runtime_id="replay")
        result, _ = evaluate(nirmaan_org, case, seat, replay=True, repo=ROOT, sandbox=tmp_path / variant,
                             clock=fixed_clock, variant=variant)
        assert result.harness == harness_sha256(variant=variant)
    assert asked == [3, case.attempts]


def test_the_cli_runs_a_named_variant_and_refuses_an_unknown_one_or_a_second_attempts(tmp_path):
    from typer.testing import CliRunner

    from nirmaan.cli import app

    base = ["eval", "run", "--replay", "--seats", "spec", "--cases", str(ROOT / "evals"), "--repo", str(ROOT)]
    ran = CliRunner().invoke(app, [*base, "--harness", "attempts-3", "--out", str(tmp_path / "out")])
    assert ran.exit_code == 0, ran.output
    assert "on the harness variant attempts-3" in ran.output and "never counts toward an" in ran.output
    [path] = list((tmp_path / "out").iterdir())
    record = load_record(path)
    assert record.manifest.harness_variant == "attempts-3"
    assert all(t.harness_variant == "attempts-3" and t.result.harness == harness_sha256(variant="attempts-3")
               for t in record.trials)
    unknown = CliRunner().invoke(app, [*base, "--harness", "nope", "--out", str(tmp_path / "none")])
    assert unknown.exit_code != 0 and "unknown harness variant 'nope'; known: default, attempts-3" in unknown.output
    twice = CliRunner().invoke(app, [*base, "--harness", "attempts-3", "--attempts", "2", "--out", str(tmp_path / "x")])
    assert twice.exit_code != 0 and "--harness attempts-3 sets the attempts" in twice.output
    assert not (tmp_path / "none").exists() and not (tmp_path / "x").exists()


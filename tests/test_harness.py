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
BOOKKEEPING = {"FORMAT", "VERSION", "SETTINGS", "SOURCE_ROOT", "CODE", "OUTPUT_WORK", "FILE_FORMAT", "OUTPUT_REVIEW"}
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
    assert harness_sha256(attempts=None, knowledge=True) == default
    assert len({default, harness_sha256(attempts=3), harness_sha256(knowledge=False)}) == 3
    assert default.startswith("sha256:") and len(default) == len("sha256:") + 64


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

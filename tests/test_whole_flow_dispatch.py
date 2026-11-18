"""The whole-flow runner option, part 4a: the one dispatch edit to runner.py and the fingerprint entries (G3).

Council record 2026-11-17 (whole-flow cases), decision 3 and gates WF6 and WF7. ``evaluate`` sends a whole-flow
case to its own module, ``nirmaan.evals.flow``, with every argument as given, and refuses one with a plain message
while that module is absent. The fingerprint's ``run`` says the flow is whole and a ``flow`` section digests the
flow module only for a whole-flow run: an edit to the flow module changes the whole-flow fingerprint and never the
default one, whose shape is as it was.
"""

from __future__ import annotations

import shutil
import sys
import types
from pathlib import Path

import pytest

from nirmaan.company import build_organization
from nirmaan.evals import EvalError, ReplayLLM, load_case, replay_llm
from nirmaan.evals.runner import evaluate
from nirmaan.models import EvalCase
from nirmaan.runtime import ModelRuntime, harness

ROOT = Path(__file__).resolve().parents[1]
TIMER = "Create an AXI4-Lite timer peripheral with an interrupt."
WHOLE = EvalCase(id="flow/x", request=TIMER, seat="rtl-implementation", flow="whole",
                 exercised={"rtl-implementation": ("rtl_design",)})


@pytest.fixture(scope="module")
def org():
    return build_organization()


def _source_tree(tmp_path: Path, flow_text: str | None) -> Path:
    """A copy of every file the fingerprints digest, with the flow module as given (None: absent)."""
    root = tmp_path / "src"
    for rel in (*harness.CODE, *harness.LOOP_CODE):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(harness.SOURCE_ROOT / rel, target)
    for rel in harness.FLOW_CODE:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.unlink(missing_ok=True)
        if flow_text is not None:
            target.write_text(flow_text, encoding="utf-8")
    return root


def test_the_default_fingerprint_keeps_its_shape_and_a_whole_flow_one_adds_its_own(monkeypatch):
    default = harness.fingerprint(cli="2.1.325")
    assert "flow" not in default and "flow" not in default["run"]
    assert harness.fingerprint(cli="2.1.325", flow="seat") == default
    whole = harness.fingerprint(cli="2.1.325", flow="whole")
    assert whole["run"]["flow"] == "whole" and set(whole["flow"]["code"]) == set(harness.FLOW_CODE)
    assert {k: v for k, v in whole.items() if k != "flow"} == {**default, "run": {**default["run"], "flow": "whole"}}
    for variant in harness.VARIANTS:  # every named variant, whole and not, is its own harness
        assert harness.harness_sha256(variant=variant, flow="whole") != harness.harness_sha256(variant=variant)


def test_an_edit_to_the_flow_module_changes_the_whole_flow_fingerprint_and_never_the_default(tmp_path, monkeypatch):
    """WF7: shown on a copy of the source, so it holds before and after the flow module exists."""
    seen = {}
    for label, text in (("absent", None), ("first", "# the flow module\n"), ("edited", "# the flow module, edited\n")):
        monkeypatch.setattr(harness, "SOURCE_ROOT", _source_tree(tmp_path / label, text))
        seen[label] = {v: (harness.harness_sha256(cli="2.1.325", variant=v),
                           harness.harness_sha256(cli="2.1.325", variant=v, flow="whole"))
                       for v in ("default", "attempts-3", "tools-in-loop")}
    for variant in ("default", "attempts-3", "tools-in-loop"):
        single = {seen[label][variant][0] for label in seen}
        whole = {seen[label][variant][1] for label in seen}
        assert len(single) == 1, variant  # the single-seat fingerprint never moves with the flow module
        assert len(whole) == 3, variant  # the whole-flow fingerprint moves with every edit


def test_the_real_default_fingerprint_does_not_read_the_flow_module(monkeypatch):
    before = harness.harness_sha256(cli="2.1.325")
    real = harness.code_digests

    def spy(files=None):
        assert files is None or not set(files) & set(harness.FLOW_CODE)
        return real(files)

    monkeypatch.setattr(harness, "code_digests", spy)
    assert harness.harness_sha256(cli="2.1.325") == before


def _flow_module(monkeypatch, module) -> None:
    """Stand in for ``nirmaan.evals.flow`` (None: absent), also as the package's attribute once it was imported."""
    import nirmaan.evals

    monkeypatch.setitem(sys.modules, "nirmaan.evals.flow", module)
    if module is None:
        monkeypatch.delattr(nirmaan.evals, "flow", raising=False)
    else:
        monkeypatch.setattr(nirmaan.evals, "flow", module, raising=False)


def test_a_whole_flow_case_is_refused_plainly_while_the_flow_module_is_absent(org, monkeypatch):
    _flow_module(monkeypatch, None)  # as if the module were not there
    with pytest.raises(EvalError, match="whole-flow runner is not merged yet"):
        evaluate(org, WHOLE, ModelRuntime(ReplayLLM([])), replay=True, repo=ROOT)


def test_a_whole_flow_case_goes_to_the_flow_module_with_every_argument(org, monkeypatch, tmp_path):
    calls = []
    module = types.ModuleType("nirmaan.evals.flow")
    module.evaluate = lambda *args, **kwargs: calls.append((args, kwargs)) or ("result", "engine")
    _flow_module(monkeypatch, module)
    runtime = ModelRuntime(ReplayLLM([]))
    clock = object()
    assert evaluate(org, WHOLE, runtime, replay=False, repo=ROOT, attempts=1, sandbox=tmp_path, clock=clock,
                    knowledge=False, variant="default") == ("result", "engine")
    [(args, kwargs)] = calls
    assert args == (org, WHOLE, runtime)
    assert kwargs == {"replay": False, "repo": ROOT, "attempts": 1, "sandbox": tmp_path, "clock": clock,
                      "knowledge": False, "variant": "default"}


def test_a_single_seat_case_never_reaches_the_flow_module(org, monkeypatch, tmp_path):
    module = types.ModuleType("nirmaan.evals.flow")
    module.evaluate = lambda *a, **k: pytest.fail("a single-seat case went to the flow module")
    _flow_module(monkeypatch, module)
    case = load_case(ROOT / "evals" / "spec" / "axi4_lite_interface.json")
    runtime = ModelRuntime(replay_llm(case, ROOT), runtime_id="replay")
    result, _ = evaluate(org, case, runtime, replay=True, repo=ROOT, sandbox=tmp_path)
    assert result.case == case.id

"""Milestone 32 (working name): an engine operation costs the same on a large project as on a small one.

P10 (no hidden state changes) used to hash the whole state twice per operation,
and P11 (auditability) re-hashed every audit entry. Now in-place edits are
impossible (read-only containers), a replaced state is caught by identity, and
each operation verifies only the audit entries it adds. Counted, not timed, so
the tests are stable in CI.
"""

from __future__ import annotations

import copy
import json
import pickle
import re
from pathlib import Path

import pytest

from nirmaan_helpers import agent, human, tid

import nirmaan
from nirmaan.demos import demo
from nirmaan.models import MemoryScope
from nirmaan.orchestrator import Orchestrator
from nirmaan.runtime import ToolBroker
from nirmaan.work import ProjectStore, TaskEngine, audit, engine as engine_module
from nirmaan.work.policy import PolicyViolationError


@pytest.fixture()
def big(nirmaan_org, fixed_clock):
    """The NoC bridge project with 300 recorded tool runs."""
    engine = Orchestrator(nirmaan_org, clock=fixed_clock).plan(demo("1").requirement)
    task = engine.task(tid(engine, "requirements"))
    broker, actor = ToolBroker(engine), agent(task.owner)
    while len(engine.state.tool_runs) < 300:
        broker.invoke(actor, "status.read", {}, task.id)
    return engine, broker, actor, task.id


def test_an_operation_hashes_only_what_it_adds(big, monkeypatch):
    engine, broker, actor, task = big
    hashed = []
    real_digest = audit._digest
    monkeypatch.setattr(audit, "_digest", lambda *a, **k: hashed.append(1) or real_digest(*a, **k))

    def no_fingerprint(state):
        raise AssertionError("an operation fingerprinted the whole state")

    monkeypatch.setattr(engine_module, "state_fingerprint", no_fingerprint)
    before = len(engine.state.audit)
    broker.invoke(actor, "project.read", {}, task)
    added = len(engine.state.audit) - before
    assert added >= 1 and len(hashed) <= 2 * added, (len(hashed), added)  # appended and verified, nothing else


@pytest.mark.parametrize("edit", [
    lambda s, t: s.tasks.__setitem__(t, s.tasks[t]),
    lambda s, t: s.tasks.pop(t),
    lambda s, t: s.tool_runs.clear(),
    lambda s, t: s.evidence.update({}),
    lambda s, t: s.audit.append(s.audit[-1]),
    lambda s, t: s.audit.__setitem__(0, s.audit[1]),
    lambda s, t: s.memory.extend([]),
    lambda s, t: next(iter(s.tool_runs.values())).params.__setitem__("sneaky", "1"),
    lambda s, t: s.audit[-1].details.__setitem__("sneaky", 1),
    lambda s, t: s.project.gate_overrides.__setitem__("x", True),
])
def test_every_in_place_edit_of_state_is_refused(big, edit):
    engine, _, _, task = big
    with pytest.raises(TypeError, match="read-only"):
        edit(engine.state, task)


def test_copies_are_writable_and_saved_state_is_unchanged(big, tmp_path):
    engine, _, actor, task = big
    copied = engine.state.model_copy(deep=True)
    copied.tasks[task] = copied.tasks[task]
    plain = dict(engine.state.tasks)
    plain.pop(task)
    assert pickle.loads(pickle.dumps(engine.state)).model_dump() == engine.state.model_dump()
    assert copy.deepcopy(engine.state.audit)[-1] == engine.state.audit[-1]
    path = ProjectStore(tmp_path).save(engine.state)
    text = path.read_text()
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    reloaded = ProjectStore(tmp_path).load(engine.state.project.id)
    assert reloaded.model_dump() == engine.state.model_dump()
    engine2 = TaskEngine(engine.org, reloaded)
    engine2.remember(MemoryScope.TASK, task, "note", "still works", actor)
    with pytest.raises(TypeError, match="read-only"):
        engine2.state.memory.append(engine2.state.memory[-1])


def test_a_broken_chain_is_refused_on_the_next_operation(big, tmp_path):
    engine, _, actor, task = big
    root = tmp_path / "store"
    path = ProjectStore(root).save(engine.state)
    raw = json.loads(path.read_text())
    raw["audit"][3]["reason"] = "quietly rewritten"
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n")
    tampered = TaskEngine(engine.org, ProjectStore(root).load(engine.state.project.id, verify=False))
    with pytest.raises(PolicyViolationError, match="P11"):
        tampered.remember(MemoryScope.TASK, task, "note", "x", actor)


def test_no_source_writes_round_frozen_models():
    """The last way round frozen records is object.__setattr__ or __dict__; no Nirmaan module uses either."""
    for path in sorted(Path(nirmaan.__file__).parent.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "object.__setattr__" not in text and not re.search(r"__dict__\s*\[", text), path

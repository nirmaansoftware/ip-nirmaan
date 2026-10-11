"""M48 characterization: what every workflow plans, and when each planned check applies.

Written before the refactor that unified conditional applicability, bounds,
and limits (docs/UNIFIED_APPLICABILITY.md), and run against the code before
it: the golden file is the behavior to preserve, byte for byte. For each
workflow and a set of representative requests it records the planned tasks
(stage and variant conditions), each task's evidence requirements (plan-time
conditions), when each applies at run time over the kinds a task produced and
built on, which checks run before review, their fixed parameters and metric
bounds, and each task's limits.

Only the accessors below may change with the API; the golden file may not.
Set NIRMAAN_WRITE_GOLDEN=1 to write it.
"""

from __future__ import annotations

import os
from pathlib import Path

GOLDEN = Path(__file__).parent / "fixtures" / "applicability" / "plans.txt"

#: Representative requests: one per (intent, feature set) found in the suite, plus feature combinations no
#: test plans by itself. Every workflow is reached.
REQUESTS = (
    "Create a 4-bit wrapping counter.",
    "Create an APB register block, with a register map, and its driver.",
    "Create an APB register block and its driver.",
    "Create an APB register block with four 32-bit registers.",
    "Build an N-way round-robin arbiter.",
    "Create a 4-bit wrapping counter with scan chains and at-speed test.",
    "Create an AXI4-Lite register block with a register map, a driver, scan chains, and a layout on sky130hd.",
    "Create an AXI4-Lite register block with an interrupt and its driver for a RISC-V core, "
    "reporting bus errors as precise traps.",
    "Create an AXI4-Lite register block with a register map and a driver.",
    "Create an AXI4-Lite register block and its driver for a RISC-V core.",
    "Create an AXI4-Lite register block.",
    "Create an AXI4-Lite register block with a verification plan.",
    "Create a parameterizable synchronous FIFO.",
    "Create a 4-bit wrapping counter with scan chains.",
    "Create a register file backed by a synchronous RAM.",
    "Create a register file backed by a synchronous RAM, with scan chains and memory BIST.",
    "Add QoS arbitration to an existing NoC router.",
    "Design a configurable 4-port AXI-to-NoC bridge supporting 256-bit data, 40-bit address and QoS arbitration.",
    "Create a 4-port AXI-to-NoC bridge with two clock domains.",
    "Design a single-clock 4-port AXI-to-NoC bridge.",
    "Design a low-power PCIe controller with scan chains, secure boot, and firmware.",
    "Design a photonic block.",
    "Change the data width of the timer from 32 to 64 bits.",
    "Change the AXI data width of the bridge from 64 to 128 bits.",
    "Place and route the AXI4-Lite register block.",
    "Investigate a regression failure introduced by a recent RTL commit.",
    "Investigate why the regression tests started failing.",
    "An RTL fix to the arbiter.",
    "Prepare the bridge for sign-off.",
    "Prepare the single-clock timer for sign-off.",
    "Close timing on the timer: negative slack on the count path.",
)


# --- Accessors: the only lines that follow the API --------------------------------------------------------


def _applies(req, produced, upstream) -> bool:
    return req.applies(produced, upstream)


def _fixed(req) -> list[str]:
    return [f"{k}={v}" for k, v in req.params if k[:4] not in ("max_", "min_")]


def _bounds(req) -> list[str]:
    return [f"{k[4:]}{'<=' if k[:4] == 'max_' else '>='}{_num(v)}" for k, v in req.params if k[:4] in ("max_", "min_")]


def _limits(engine, task) -> str:
    from nirmaan.runtime import limits

    budget = limits(engine, task.id)
    return (f"retries={task.max_retries} on_failure={task.on_failure.value} attempts={budget.attempts} "
            f"review_rounds={budget.review_rounds}")


def _condition_kinds(req) -> set[str]:
    """Every artifact kind a requirement's run-time conditions name."""
    return {*req.when_produced, *req.when_upstream}


# --- The snapshot ---------------------------------------------------------------------------------------


def _num(value) -> str:
    return format(float(value), "g")


def _kinds(engine) -> set[str]:
    kinds: set[str] = set()
    for task in engine.state.tasks.values():
        kinds |= set(task.inputs) | set(task.expected_outputs)
        for req in task.evidence_requirements:
            kinds |= {k for b in req.files for k in b.kinds} | _condition_kinds(req)
    return kinds


def _when(req, universe: set[str]) -> str:
    if _applies(req, (), ()):
        return "always"
    produced = sorted(k for k in universe if _applies(req, {k}, universe))
    upstream = sorted(k for k in universe if _applies(req, universe, {k}))
    show = lambda ks: "any" if set(ks) == universe else ",".join(ks) or "none"  # noqa: E731
    return f"produced={show(produced)} upstream={show(upstream)}"


def _files(req) -> str:
    return " ".join(f"{b.param}<-{'|'.join(b.kinds)}"
                    f"{'[entry]' if b.entry else ''}{'[upstream]' if b.upstream else ''}"
                    f"{'[optional]' if b.optional else ''}" for b in req.files)


def snapshot(org, clock) -> str:
    from nirmaan.orchestrator import Orchestrator

    lines: list[str] = []
    reached: set[str] = set()
    for text in REQUESTS:
        engine = Orchestrator(org, clock=clock).plan(text)
        state = engine.state
        reached |= set(state.project.workflows)
        lines += ["", f"## {text}",
                  f"intent={state.project.analysis.intent} features={','.join(sorted(state.project.analysis.features))}"
                  f" workflows={','.join(state.project.workflows)}"]
        universe = _kinds(engine)
        prefix = state.project.id + ":"
        for task in sorted(state.tasks.values(), key=lambda t: t.id):
            lines.append(f"- {task.id.removeprefix(prefix)} [{task.kind.value}] {_limits(engine, task)}")
            for req in task.evidence_requirements:
                extra = [*_fixed(req), *_bounds(req)]
                lines.append(
                    f"    * {req.description} | accepts={','.join(k.value for k in req.accepts)}"
                    f" | tools={','.join(req.tools) or '-'}"
                    f"{' | before-review' if req.before_review else ''}"
                    f"{' | files=' + _files(req) if req.files else ''}"
                    f"{' | fixed=' + ','.join(extra) if extra else ''}"
                    f"{' | yields=' + ','.join(f'{k}:{n}' for k, n in req.yields) if req.yields else ''}"
                    f" | applies {_when(req, universe)}")
    missing = sorted(set(org.workflows) - reached)
    assert not missing, f"no representative request reaches {missing}"
    return "\n".join(lines).lstrip("\n") + "\n"


def test_the_planned_requirements_and_their_applicability_are_unchanged(nirmaan_org, fixed_clock):
    text = snapshot(nirmaan_org, fixed_clock)
    if os.environ.get("NIRMAAN_WRITE_GOLDEN"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
    assert text == GOLDEN.read_text(encoding="utf-8"), f"the characterization changed; see {GOLDEN}"

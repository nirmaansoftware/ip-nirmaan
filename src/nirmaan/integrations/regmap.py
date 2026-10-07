"""Register map tools (M30): validation as a recorded run, and the map judging the RTL.

``regmap.check`` validates a map file. ``regmap.verify`` generates a test from
the map (``nirmaan.regmap.c_test``) and runs it on the RTL through the
AXI4-Lite co-simulation harness that ``fw.test`` uses (real VALID/READY
handshakes on a Verilator model). A map for a bus with no harness is a
recorded failed run that says so: nothing is simulated in its place.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from pydantic import ValidationError

from nirmaan.integrations.eda import Backend, Job, RunRecord, register_backend
from nirmaan.integrations.eda_parsers import EdaResult
from nirmaan.integrations.firmware import _cosim_steps, parse_fw_test
from nirmaan.regmap import c_test, load_map, map_summary, validate
from nirmaan.runtime.tools import ToolOutcome, register_binding
from nirmaan.work.engine import TaskEngine

#: Buses with a co-simulation harness. Only AXI4-Lite has one today.
HARNESSED_BUSES = ("axi4-lite",)
GENERATED_TEST = "regmap_test.c"


def _load(path: str):
    """The map at ``path`` and its problems (a map that cannot be read is all problem)."""
    try:
        regmap = load_map(path)
    except (OSError, ValueError, ValidationError) as exc:
        return None, [f"cannot read the register map {path}: {type(exc).__name__}: {exc}".splitlines()[0]]
    return regmap, validate(regmap)


@register_binding("regmap.check")
def check(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    path = params.get("map", "")
    regmap, problems = _load(path)
    if problems:
        return ToolOutcome(False, f"register map has {len(problems)} problem(s): {'; '.join(problems)}", (path,))
    return ToolOutcome(True, f"register map is valid: {map_summary(regmap)}", (path,))


def _verify_check(job: Job) -> str | None:
    regmap, problems = _load(job.params["map"])
    if problems:
        return "; ".join(problems)
    if regmap.bus not in HARNESSED_BUSES:
        return (f"no co-simulation harness for a {regmap.bus} map (harnesses exist for "
                f"{', '.join(HARNESSED_BUSES)}); nothing was simulated")
    return None


def _verify_steps(job: Job) -> list[list[str]]:
    test = job.workdir / GENERATED_TEST
    test.write_text(c_test(load_map(job.params["map"])), encoding="utf-8")
    return _cosim_steps(dataclasses.replace(job, sources=(str(test),)))


def _verify_parse(run: RunRecord) -> EdaResult:
    return parse_fw_test(run.log, run.returncodes, what="register map check")


register_backend(Backend("regmap-cosim", "regmap.verify", ("cc", "verilator", "make"), _verify_steps, _verify_parse,
                         ("map", "rtl"), files=("map",), check=_verify_check))

__all__ = ["HARNESSED_BUSES", "check"]

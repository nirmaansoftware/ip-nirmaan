"""Parsers for OpenSTA and OpenROAD output: pure functions of captured text.

Like ``eda_parsers``, they never run a tool. The formats read here are the
documented ``report_checks``, ``report_worst_slack``, ``report_tns``, and
``report_wns`` reports (OpenROAD embeds OpenSTA, so both print them), the
OpenROAD ``[ERROR XXX-0000]`` message format, ``report_design_area``, the
detailed router's violation count and wire length, and the
``nirmaan-stage`` markers the place-and-route script prints around each stage.
"""

from __future__ import annotations

import re
from typing import Any

from nirmaan.integrations.eda_parsers import Diagnostic, EdaResult, _first, _plural

#: The place-and-route stages, in flow order; timing is reported after the last one run.
PNR_STAGES = ("floorplan", "place", "route")
#: The violator report lists at most this many paths per check, so a count this high is a lower bound.
VIOLATOR_REPORT_LIMIT = 100

_TAGGED_RE = re.compile(r"^\[(?P<sev>ERROR|WARNING) (?P<code>[A-Z]+-\d+)\]\s*(?P<msg>.*)$")
_PLAIN_RE = re.compile(r"^(?P<sev>Error|Warning):\s*(?P<msg>.*)$")
_ENDPOINT_RE = re.compile(r"^Endpoint:\s*(?P<pin>\S+)")
_PATH_TYPE_RE = re.compile(r"^Path Type:\s*(?P<type>max|min)\b")
_SLACK_RE = re.compile(r"^(?P<slack>-?\d+(?:\.\d+)?)\s+slack \((?P<state>MET|VIOLATED)\)")
# ``report_worst_slack -max`` prints ``worst slack max 7.120``; an unlabelled figure is read in report order.
_WORST_RE = re.compile(r"^worst slack(?:\s+(?P<kind>max|min))?\s+(?P<value>\S+)")
_TNS_RE = re.compile(r"^tns(?:\s+(?:max|min))?\s+(?P<value>\S+)")
_WNS_RE = re.compile(r"^wns(?:\s+(?:max|min))?\s+(?P<value>\S+)")
_AREA_RE = re.compile(r"^Design area (?P<area>[\d.]+) um?\^2 (?P<util>[\d.]+)% utilization")
_WIRELENGTH_RE = re.compile(r"Total wire length = (?P<um>[\d.]+) um")
_DRC_RE = re.compile(r"Number of violations = (?P<n>\d+)")
_STAGE_RE = re.compile(r"^nirmaan-stage(?P<done>-done)?: (?P<stage>\w+)")


def _num(value: str | None) -> float | None:
    """A reported figure, or None for INF, a missing value, or anything unparseable."""
    try:
        number = float(value) if value is not None else None
    except ValueError:
        return None
    return number if number is not None and abs(number) < 1e29 else None


def _diagnostics(lines: list[str]) -> list[Diagnostic]:
    found = []
    for line in lines:
        if m := _TAGGED_RE.match(line):
            found.append(Diagnostic("error" if m["sev"] == "ERROR" else "warning", m["msg"].strip(), m["code"]))
        elif m := _PLAIN_RE.match(line):
            found.append(Diagnostic("error" if m["sev"] == "Error" else "warning", m["msg"].strip()))
    return found


def _timing(lines: list[str]) -> dict[str, Any]:
    """Worst slacks (setup and hold, by label or else in report order), TNS, WNS, and the violating endpoints."""
    worst: list[float | None] = []
    labelled: dict[str, float | None] = {}
    tns = wns = None
    endpoint, check = "", "setup"
    violators: dict[tuple[str, str], float] = {}
    for line in lines:
        if m := _ENDPOINT_RE.match(line):
            endpoint = m["pin"]
        elif m := _PATH_TYPE_RE.match(line):
            check = "setup" if m["type"] == "max" else "hold"
        elif m := _SLACK_RE.match(line):
            if m["state"] == "VIOLATED" and endpoint:
                key, slack = (endpoint, check), float(m["slack"])
                violators[key] = min(slack, violators.get(key, slack))
        elif m := _WORST_RE.match(line):
            if m["kind"]:
                labelled[m["kind"]] = _num(m["value"])
            else:
                worst.append(_num(m["value"]))
        elif m := _TNS_RE.match(line):
            tns = _num(m["value"])
        elif m := _WNS_RE.match(line):
            wns = _num(m["value"])
    ordered = sorted(violators.items(), key=lambda item: (item[1], item[0]))
    setup = labelled["max"] if "max" in labelled else (worst[0] if worst else None)
    hold = labelled["min"] if "min" in labelled else (worst[1] if len(worst) > 1 else None)
    return {
        "worst_slack": setup,
        "worst_hold_slack": hold,
        "tns": tns,
        "wns": wns,
        "violating_endpoints": [{"endpoint": e, "check": c, "slack": s} for (e, c), s in ordered],
    }


def _timing_met(t: dict[str, Any]) -> bool:
    hold = t["worst_hold_slack"]
    return (t["worst_slack"] is not None and t["worst_slack"] >= 0 and (hold is None or hold >= 0)
            and not t["violating_endpoints"])


def _slacks(t: dict[str, Any]) -> str:
    parts = [f"worst setup slack {t['worst_slack']:.3f}"]
    if t["worst_hold_slack"] is not None:
        parts.append(f"worst hold slack {t['worst_hold_slack']:.3f}")
    if t["tns"] is not None:
        parts.append(f"TNS {t['tns']:.3f}")
    return ", ".join(parts)


def _lines(log: str) -> list[str]:
    return [raw.strip() for raw in log.splitlines()]


# --- OpenSTA ----------------------------------------------------------------------------


def parse_opensta(log: str, returncode: int) -> EdaResult:
    """Pass means exit 0, no error, a worst setup slack reported, and no negative slack anywhere."""
    lines = _lines(log)
    diags = _diagnostics(lines)
    errors = [d for d in diags if d.severity == "error"]
    timing = _timing(lines)
    metrics = {**timing, "exit_status": returncode}
    if errors or returncode != 0:
        summary = f"timing analysis failed: {_plural(len(errors), 'error')}{_first(errors)}"
        if not errors:
            summary += f" (exit status {returncode})"
        return EdaResult(False, summary, tuple(diags), metrics)
    if timing["worst_slack"] is None:
        return EdaResult(False, "timing not met: no constrained timing paths (no worst slack reported)",
                         tuple(diags), metrics)
    if _timing_met(timing):
        return EdaResult(True, f"timing met: {_slacks(timing)}", tuple(diags), metrics)
    violators = timing["violating_endpoints"]
    count = _plural(len(violators), "violating endpoint")
    if len(violators) >= VIOLATOR_REPORT_LIMIT:
        count = f"at least {count}"
    summary = f"timing violated: {count}, {_slacks(timing)}"
    if violators:
        v = violators[0]
        summary += f"; worst: {v['endpoint']} ({v['check']}) {v['slack']:.3f}"
    return EdaResult(False, summary, tuple(diags), metrics)


# --- OpenROAD ---------------------------------------------------------------------------


def parse_openroad(log: str, returncode: int, stop_after: str = "route") -> EdaResult:
    """Pass means exit 0, no error, every requested stage and timing finished, 0 DRC, timing met."""
    lines = _lines(log)
    diags = _diagnostics(lines)
    errors = [d for d in diags if d.severity == "error"]
    started: list[str] = []
    completed: list[str] = []
    area = utilization = wirelength = None
    drc: int | None = None
    for line in lines:
        if m := _STAGE_RE.match(line):
            (completed if m["done"] else started).append(m["stage"])
        elif m := _AREA_RE.match(line):
            area, utilization = float(m["area"]), float(m["util"])
        elif m := _WIRELENGTH_RE.search(line):
            wirelength = float(m["um"])
        elif m := _DRC_RE.search(line):
            drc = int(m["n"])
    timing = _timing(lines)
    failed_stage = next((s for s in reversed(started) if s not in completed), None)
    expected = [*PNR_STAGES[:PNR_STAGES.index(stop_after) + 1], "timing"] if stop_after in PNR_STAGES else ["timing"]
    missing = [s for s in expected if s not in completed]
    routed = "route" in expected
    metrics: dict[str, Any] = {
        "stop_after": stop_after, "stages_completed": completed, "failed_stage": failed_stage,
        "design_area_um2": area, "utilization_pct": utilization, "wirelength_um": wirelength,
        "drc_violations": drc, **timing, "exit_status": returncode,
    }
    reasons = []
    if errors:
        reasons.append(f"{_plural(len(errors), 'error')}{_first(errors)}")
    if returncode != 0 and not errors:
        reasons.append(f"exit status {returncode}")
    if routed and drc != 0:
        reasons.append("no DRC count reported" if drc is None else _plural(drc, "DRC violation"))
    if "timing" in completed and not _timing_met(timing):
        reasons.append("no constrained timing paths" if timing["worst_slack"] is None
                       else f"timing violated ({_slacks(timing)})")
    if not reasons and not missing:
        reached = {"floorplan": "floorplanned", "place": "placed", "route": "routed"}.get(stop_after, stop_after)
        parts = [reached]
        if routed:
            parts += [_plural(drc or 0, "DRC violation"), f"wirelength {wirelength:.0f} um" if wirelength is not None
                      else "wirelength not reported"]
        if utilization is not None:
            parts.append(f"utilization {utilization:.0f}%")
        parts.append(_slacks(timing))
        return EdaResult(True, f"place and route passed: {', '.join(parts)}", tuple(diags), metrics)
    stage = failed_stage or (missing[0] if missing else None)
    if stage and not reasons:
        reasons.append(f"{stage} never finished")
    prefix = f"place and route failed in {stage}" if stage else "place and route failed"
    return EdaResult(False, f"{prefix}: {'; '.join(reasons)}", tuple(diags), metrics)

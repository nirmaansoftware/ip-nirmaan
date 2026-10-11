"""Parsers for OpenSTA and OpenROAD output: pure functions of captured text.

Like ``eda_parsers``, they never run a tool. The formats read here are the
documented ``report_checks``, ``report_worst_slack``, ``report_tns``, and
``report_wns`` reports (OpenROAD embeds OpenSTA, so both print them), the
OpenROAD ``[ERROR XXX-0000]`` message format, ``report_design_area``, the
detailed router's violation count and wire length, and the
``nirmaan-stage`` markers the place-and-route script prints around each stage.

M34 adds the per-corner ``report_checks -format end`` tables a multi-corner
``sta.run`` prints between ``nirmaan-corner`` markers, the metal fill count, and
``parse_klayout`` for ``pv.run``: the counts Nirmaan's own KLayout scripts print
from the DRC report database and the LVS cross-reference.
"""

from __future__ import annotations

import re
from typing import Any

from nirmaan.integrations.eda_parsers import Diagnostic, EdaResult, _first, _plural

#: The place-and-route stages, in flow order; timing is reported after the last one run.
#: M29 added clock-tree synthesis and parasitic extraction (``extract`` needs the PDK's OpenRCX rules).
PNR_STAGES = ("floorplan", "place", "cts", "route", "extract")
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
#: ``report_parasitic_annotation`` after ``read_spef`` (M29).
_UNANNOTATED_RE = re.compile(r"^Found (?P<n>\d+) unannotated drivers")
_FLOATING_RE = re.compile(r"^nirmaan-floating-outputs: (?P<n>\d+)")
_STAGE_RE = re.compile(r"^nirmaan-stage(?P<done>-done)?: (?P<stage>\w+)")
#: M34: one timing corner's reports, between these markers, as ``report_checks -format end`` tables.
_CORNER_RE = re.compile(r"^nirmaan-corner(?P<done>-done)?: (?P<corner>\S+)")
_END_GROUP_RE = re.compile(r"^(?P<kind>max_delay/setup|min_delay/hold) group")
_END_ROW_RE = re.compile(r"(?:^|\s)(?P<slack>-?\d+(?:\.\d+)?) \((?:MET|VIOLATED)\)$")


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


def _annotation(lines: list[str]) -> dict[str, int | None]:
    """How much of the design a read SPEF annotates (M29).

    ``report_parasitic_annotation -report_unannotated`` lists the drivers whose nets have no parasitics;
    the script lists the drivers that drive nothing (``nirmaan-floating-drivers``), which have no wire to
    extract. ``unannotated_nets`` counts the listed drivers that do drive something.
    """
    unannotated = floating = None
    listed: set[str] = set()
    idle: set[str] | None = None
    listing = False
    for line in lines:
        if m := _UNANNOTATED_RE.match(line):
            unannotated, listing = int(m["n"]), True
            continue
        if listing and line and not line.startswith("Found ") and " " not in line:
            listed.add(line)
            continue
        elif m := _FLOATING_RE.match(line):
            floating = int(m["n"])
        elif line.startswith("nirmaan-floating-drivers:"):
            idle = set(line.split(":", 1)[1].split())
        listing = False
    if unannotated is None or floating is None:
        nets = None
    elif idle is not None and len(listed) == unannotated:
        nets = len(listed - idle)
    else:
        nets = unannotated - floating
    return {"unannotated_drivers": unannotated, "floating_outputs": floating, "unannotated_nets": nets}


def _corners(lines: list[str]) -> dict[str, dict[str, float | None]]:
    """Worst setup and hold slack per timing corner (M34), from the tables each corner's section printed."""
    corners: dict[str, dict[str, float | None]] = {}
    current = check = None
    for line in lines:
        if m := _CORNER_RE.match(line):
            current, check = (None if m["done"] else m["corner"]), None
            if current:
                corners[current] = {"setup": None, "hold": None}
        elif current is None:
            continue
        elif m := _END_GROUP_RE.match(line):
            check = "setup" if m["kind"].startswith("max") else "hold"
        elif check and (m := _END_ROW_RE.search(line)):
            slack, worst = float(m["slack"]), corners[current][check]
            corners[current][check] = slack if worst is None else min(worst, slack)
    return corners


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
    corners = _corners(lines)
    timed = [c for c, t in corners.items() if t["setup"] is not None and t["hold"] is not None]
    metrics = {**timing, **_annotation(lines), "exit_status": returncode,
               # M34: one corner unless the run defined corners; a corner counts only with setup and hold.
               "slack_by_corner": corners,
               "timing_corners": len(timed) if corners else int(timing["worst_slack"] is not None)}
    if errors or returncode != 0:
        summary = f"timing analysis failed: {_plural(len(errors), 'error')}{_first(errors)}"
        if not errors:
            summary += f" (exit status {returncode})"
        return EdaResult(False, summary, tuple(diags), metrics)
    if timing["worst_slack"] is None:
        return EdaResult(False, "timing not met: no constrained timing paths (no worst slack reported)",
                         tuple(diags), metrics)
    untimed = [c for c in corners if c not in timed]
    if untimed:
        return EdaResult(False, f"timing not met: no setup or hold paths reported in corner {', '.join(untimed)}",
                         tuple(diags), metrics)
    across = (f" across {len(corners)} corners ("
              + ", ".join(f"{c} {t['setup']:.3f}/{t['hold']:.3f}" for c, t in corners.items()) + ")"
              if corners else "")
    if _timing_met(timing):
        return EdaResult(True, f"timing met: {_slacks(timing)}{across}", tuple(diags), metrics)
    violators = timing["violating_endpoints"]
    count = _plural(len(violators), "violating endpoint")
    if len(violators) >= VIOLATOR_REPORT_LIMIT:
        count = f"at least {count}"
    summary = f"timing violated: {count}, {_slacks(timing)}{across}"
    if violators:
        v = violators[0]
        summary += f"; worst: {v['endpoint']} ({v['check']}) {v['slack']:.3f}"
    return EdaResult(False, summary, tuple(diags), metrics)


# --- OpenROAD ---------------------------------------------------------------------------

# M29: the signoff steps. Each pattern is a line format seen in a captured OpenROAD log.
_TAPS_RE = re.compile(r"Inserted (?P<n>\d+) tapcells")
_ENDCAPS_RE = re.compile(r"Inserted (?P<n>\d+) endcaps")
_GRID_RE = re.compile(r"\[INFO PDN-\d+\] Inserting grid: (?P<grid>\S+)")
_OPEN_SUPPLY_RE = re.compile(r"^nirmaan-unconnected-supply-pins: (?P<n>\d+)")
_SUPPLY_NETS_RE = re.compile(r"^nirmaan-supply-nets:(?P<nets>.*)$")
_CTS_BUFFERS_RE = re.compile(r"Total number of Buffers Inserted: (?P<n>\d+)")
_CTS_SINKS_RE = re.compile(r"Total number of Sinks: (?P<n>\d+)")
_SKEW_RE = re.compile(r"^(?P<skew>-?\d+(?:\.\d+)?) (?:setup|hold) skew$")
_LATENCY_RE = re.compile(r"^(?P<min>-?\d+(?:\.\d+)?)\s+(?P<max>-?\d+(?:\.\d+)?) latency$")
_FILLERS_RE = re.compile(r"Placed (?P<n>\d+) filler instances")
_ANTENNA_RE = re.compile(r"Found (?P<n>\d+) (?P<kind>net|pin) violations")
_IR_NET_RE = re.compile(r"^Net\s*:\s*(?P<net>\S+)")
_IR_WORST_RE = re.compile(r"^Worstcase IR drop\s*:\s*(?P<v>\S+)\s*V")
_FILL_RE = re.compile(r"^nirmaan-fill-shapes: (?P<n>\d+)")  # M34: after density_fill


def _sections(lines: list[str]) -> dict[str, list[str]]:
    """The lines each stage printed, between its ``nirmaan-stage`` markers."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in lines:
        if m := _STAGE_RE.match(line):
            current = None if m["done"] else m["stage"]
            if current:
                sections[current] = []
        elif current:
            sections[current].append(line)
    return sections


def _clock_tree(lines: list[str]) -> dict[str, Any]:
    """Buffers and sinks (``report_cts``), skew (``report_clock_skew``), insertion delay (``report_clock_latency``)."""
    buffers = sinks = skew = latency = None
    for line in lines:
        if m := _CTS_BUFFERS_RE.search(line):
            buffers = int(m["n"])
        elif m := _CTS_SINKS_RE.search(line):
            sinks = int(m["n"])
        elif m := _SKEW_RE.match(line):
            skew = max(float(m["skew"]), skew if skew is not None else float("-inf"))
        elif m := _LATENCY_RE.match(line):  # min and max network latency, per transition: the largest max
            latency = max(float(m["max"]), latency if latency is not None else float("-inf"))
    return {"cts_buffers": buffers, "cts_sinks": sinks, "clock_skew": skew, "clock_insertion_delay": latency}


def _signoff_checks(lines: list[str]) -> dict[str, Any]:
    taps = endcaps = fillers = open_supply = fill = None
    grids: list[str] = []
    supply_nets: list[str] = []
    antenna: dict[str, int] = {}
    ir: dict[str, float | None] = {}
    ir_net = None
    for line in lines:
        if m := _TAPS_RE.search(line):
            taps = int(m["n"])
        elif m := _ENDCAPS_RE.search(line):
            endcaps = int(m["n"])
        elif m := _GRID_RE.search(line):
            grids.append(m["grid"])
        elif m := _OPEN_SUPPLY_RE.match(line):
            open_supply = int(m["n"])
        elif m := _SUPPLY_NETS_RE.match(line):
            supply_nets = m["nets"].split()
        elif m := _FILLERS_RE.search(line):
            fillers = int(m["n"])
        elif m := _ANTENNA_RE.search(line):
            antenna[m["kind"]] = int(m["n"])
        elif m := _FILL_RE.match(line):
            fill = int(m["n"])
        elif m := _IR_NET_RE.match(line):
            ir_net = m["net"]
        elif (m := _IR_WORST_RE.match(line)) and ir_net:
            ir[ir_net] = _num(m["v"])
    return {"tap_cells": taps, "endcap_cells": endcaps, "power_grids": grids, "supply_nets": supply_nets,
            "unconnected_supply_pins": open_supply, "filler_cells": fillers,
            "antenna_net_violations": antenna.get("net"), "antenna_pin_violations": antenna.get("pin"),
            "worst_ir_drop_v": ir, "fill_shapes": fill, **_annotation(lines)}


def parse_openroad(log: str, returncode: int, stop_after: str = "route",
                   planned: list[str] | tuple[str, ...] | None = None) -> EdaResult:
    """Pass means exit 0, no error, every planned stage and timing finished, 0 DRC, timing met.

    M29: and, when a power grid was inserted, every supply pin connected; no antenna violation; and,
    when the flow extracted parasitics, the final timing on them. ``planned`` defaults to every stage
    up to ``stop_after``.
    """
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
    sections = _sections(lines)
    timing = _timing(sections.get("timing", lines))
    checkpoints = {}
    for stage in PNR_STAGES:
        if stage in sections:
            t = _timing(sections[stage])
            if t["worst_slack"] is not None:
                checkpoints[stage] = {"setup": t["worst_slack"], "hold": t["worst_hold_slack"], "tns": t["tns"]}
    checks = _signoff_checks(lines)
    failed_stage = next((s for s in reversed(started) if s not in completed), None)
    if planned is None:
        planned = PNR_STAGES[:PNR_STAGES.index(stop_after) + 1] if stop_after in PNR_STAGES else ()
    expected = [*planned, "timing"]
    missing = [s for s in expected if s not in completed]
    routed = "route" in expected
    extracted = "extract" in completed
    metrics: dict[str, Any] = {
        "stop_after": stop_after, "stages_completed": completed, "failed_stage": failed_stage,
        "design_area_um2": area, "utilization_pct": utilization, "wirelength_um": wirelength,
        "drc_violations": drc, **timing, "exit_status": returncode,
        "slack_by_stage": checkpoints, "parasitics": "extracted" if extracted else "estimated",
        **_clock_tree(sections.get("cts", [])), **checks,
    }
    reasons = []
    if errors:
        reasons.append(f"{_plural(len(errors), 'error')}{_first(errors)}")
    if returncode != 0 and not errors:
        reasons.append(f"exit status {returncode}")
    if routed and drc != 0:
        reasons.append("no DRC count reported" if drc is None else _plural(drc, "DRC violation"))
    if checks["power_grids"] and routed and checks["unconnected_supply_pins"] != 0:  # counted after routing
        open_pins = checks["unconnected_supply_pins"]
        reasons.append("supply pin connections not reported" if open_pins is None
                       else _plural(open_pins, "unconnected supply pin"))
    antennas = (checks["antenna_net_violations"] or 0) + (checks["antenna_pin_violations"] or 0)
    if antennas:
        reasons.append(_plural(antennas, "antenna violation"))
    if "timing" in completed and not _timing_met(timing):
        reasons.append("no constrained timing paths" if timing["worst_slack"] is None
                       else f"timing violated ({_slacks(timing)})")
    if not reasons and not missing:
        last = planned[-1] if planned else stop_after
        reached = {"floorplan": "floorplanned", "place": "placed", "cts": "clock tree built",
                   "route": "routed", "extract": "routed and extracted"}.get(last, last)
        parts = [reached]
        if routed:
            parts += [_plural(drc or 0, "DRC violation"), f"wirelength {wirelength:.0f} um" if wirelength is not None
                      else "wirelength not reported"]
        if utilization is not None:
            parts.append(f"utilization {utilization:.0f}%")
        if checks["power_grids"]:
            parts.append("power grid connected")
        elif routed:
            parts.append("no power grid")
        if checks["fill_shapes"] is not None:
            parts.append(f"metal fill {_plural(checks['fill_shapes'], 'shape')}")
        if metrics["clock_skew"] is not None:
            parts.append(f"clock skew {metrics['clock_skew']:.3f}")
        parts.append(_slacks(timing) + (" on extracted parasitics" if extracted else ""))
        return EdaResult(True, f"place and route passed: {', '.join(parts)}", tuple(diags), metrics)
    stage = failed_stage or (missing[0] if missing else None)
    if stage and not reasons:
        reasons.append(f"{stage} never finished")
    prefix = f"place and route failed in {stage}" if stage else "place and route failed"
    return EdaResult(False, f"{prefix}: {'; '.join(reasons)}", tuple(diags), metrics)


# --- KLayout physical verification (M34) ------------------------------------------------

#: Printed by Nirmaan's own KLayout scripts (``physical.py``): the stream, the DRC count, the LVS count.
_GDS_EMPTY_RE = re.compile(r"^nirmaan-gds-empty-cells: (?P<n>\d+)")
_GDS_EMPTY_CELL_RE = re.compile(r"^nirmaan-gds-empty-cell: (?P<cell>\S+)")
_GDS_FILL_RE = re.compile(r"^nirmaan-gds-fill-shapes: (?P<n>\d+)")
_DRC_TOTAL_RE = re.compile(r"^nirmaan-drc-violations: (?P<n>\d+)")
_DRC_RULE_RE = re.compile(r"^nirmaan-drc-rule: (?P<rule>\S+) (?P<n>\d+)")
_LVS_KIND_RE = re.compile(r"^nirmaan-lvs-mismatched-(?P<kind>\w+): (?P<n>\d+)")
_LVS_CIRCUIT_RE = re.compile(r"^nirmaan-lvs-circuit: (?P<layout>\S+) (?P<schematic>\S+) (?P<status>\S+)")
#: KLayout reports a script or deck failure as ``ERROR: ...`` (a deck's own ``ERROR : ...`` text is not one).
_KLAYOUT_ERROR_RE = re.compile(r"^ERROR: (?P<msg>.*)$")
#: The checks ``pv.run`` can run, in order.
PV_CHECKS = ("drc", "lvs")


def parse_klayout(log: str, returncode: int, checks: list[str] | tuple[str, ...] = PV_CHECKS) -> EdaResult:
    """Pass means exit 0, no error, every layout cell has GDS, and each check run is clean.

    DRC is clean when the report database holds no item; LVS when no circuit, net, device, pin, or
    subcircuit pair of the cross-reference is a mismatch. A check that was run and printed no count fails.
    """
    lines = _lines(log)
    diags = _diagnostics(lines) + [Diagnostic("error", m["msg"].strip()) for line in lines
                                   if (m := _KLAYOUT_ERROR_RE.match(line))]
    errors = [d for d in diags if d.severity == "error"]
    empty = fill = drc = None
    empty_cells: list[str] = []
    rules: dict[str, int] = {}
    lvs: dict[str, int] = {}
    unmatched: list[str] = []
    for line in lines:
        if m := _GDS_EMPTY_RE.match(line):
            empty = int(m["n"])
        elif m := _GDS_EMPTY_CELL_RE.match(line):
            empty_cells.append(m["cell"])
        elif m := _GDS_FILL_RE.match(line):
            fill = int(m["n"])
        elif m := _DRC_TOTAL_RE.match(line):
            drc = int(m["n"])
        elif m := _DRC_RULE_RE.match(line):
            rules[m["rule"]] = int(m["n"])
        elif m := _LVS_KIND_RE.match(line):
            lvs[m["kind"]] = int(m["n"])
        elif (m := _LVS_CIRCUIT_RE.match(line)) and m["status"] in ("NoMatch", "Mismatch"):
            unmatched.append(m["layout"] if m["layout"] != "-" else m["schematic"])
    mismatches = sum(lvs.values()) if lvs else None
    metrics: dict[str, Any] = {
        "checks": list(checks), "gds_empty_cells": empty, "empty_cells": empty_cells, "fill_shapes": fill,
        "drc_violations": drc, "drc_by_rule": dict(sorted(rules.items(), key=lambda r: (-r[1], r[0]))),
        "lvs_mismatches": mismatches, "lvs_mismatched": lvs, "lvs_unmatched_circuits": unmatched,
        "exit_status": returncode,
    }
    reasons = []
    if errors:
        reasons.append(f"{_plural(len(errors), 'error')}{_first(errors)}")
    if returncode != 0 and not errors:
        reasons.append(f"exit status {returncode}")
    if empty is None:
        reasons.append("no GDS written")
    elif empty:
        reasons.append(f"{_plural(empty, 'layout cell')} with no GDS ({', '.join(empty_cells[:3])})")
    if "drc" in checks:
        if drc is None:
            reasons.append("no DRC count reported")
        elif drc:
            worst = ", ".join(f"{r} {n}" for r, n in list(metrics["drc_by_rule"].items())[:3])
            reasons.append(f"{_plural(drc, 'DRC violation')} ({worst})")
    if "lvs" in checks:
        if mismatches is None:
            reasons.append("no LVS comparison reported")
        elif mismatches:
            kinds = ", ".join(_plural(n, f"mismatched {k[:-1]}") for k, n in lvs.items() if n)
            reasons.append(f"LVS mismatch: {kinds}" + (f"; unmatched {', '.join(unmatched)}" if unmatched else ""))
    if reasons:
        return EdaResult(False, f"physical verification failed: {'; '.join(reasons)}", tuple(diags), metrics)
    parts = ["GDS written" + (f" with {_plural(fill, 'fill shape')}" if fill else "")]
    if "drc" in checks:
        parts.append("DRC clean")
    if "lvs" in checks:
        parts.append("LVS clean (layout matches the netlist)")
    return EdaResult(True, f"physical verification passed: {', '.join(parts)}", tuple(diags), metrics)

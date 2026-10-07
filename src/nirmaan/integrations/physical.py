"""Physical design behind the tool broker: OpenSTA and OpenROAD, or an honest refusal.

Three backends on the M21 registry (``eda.register_backend``):

* ``yosys-liberty`` for ``synth.run``: synthesis mapped to a Liberty library,
  writing the gate-level ``netlist.v`` that STA and place-and-route consume.
* ``opensta`` for ``sta.run``: static timing of a netlist under an SDC; and
  ``openroad-sta``, the same script in OpenROAD's embedded OpenSTA, when only
  ``openroad`` is installed (packaged OpenROAD builds ship no ``sta``).
* ``openroad`` for ``pnr.run``: floorplan, placement, and routing in one
  OpenROAD session, stopping after ``stop_after``, with timing reported last.

The PDK is an input, never bundled. A missing executable or a missing PDK input
is a refusal with a reason (the probe), and no run is recorded; a missing
netlist, a timing violation, DRC violations, or a timeout is a recorded failed
run. See ``docs/PHYSICAL_DESIGN.md``.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable

from nirmaan.integrations.eda import Backend, EdaResult, Job, RunRecord, register_backend
from nirmaan.integrations.eda_parsers import parse_yosys
from nirmaan.integrations.pd_parsers import PNR_STAGES, VIOLATOR_REPORT_LIMIT, parse_openroad, parse_opensta
from nirmaan.models import list_values

#: Relative PDK paths resolve under this directory (or the ``pdk_root`` parameter).
PDK_ROOT_ENV = "NIRMAAN_PDK_ROOT"
#: PDK parameters that name files; every other PDK parameter is a setting (a site, layers).
PDK_FILES = ("liberty", "tech_lef", "lef", "pdn_tcl", "rc_tcl", "rcx_rules")

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.$]+$")


def pdk_paths(params: dict[str, str], key: str) -> list[Path]:
    """The comma-separated files a PDK parameter names, relative ones under the PDK root."""
    root = params.get("pdk_root") or os.environ.get(PDK_ROOT_ENV, "")
    paths = []
    for value in list_values(params.get(key, "")):
        path = Path(value)
        paths.append((Path(root) / path if root and not path.is_absolute() else path).resolve())
    return paths


def needs_pdk(**inputs: str) -> Callable[[dict[str, str]], str | None]:
    """An ``environment`` check: each named PDK parameter (``param="a label"``) is given, and its files exist."""

    def check(params: dict[str, str]) -> str | None:
        reasons = []
        for param, label in inputs.items():
            if not params.get(param, "").strip():
                how = (f"{param}=PATH, absolute or under {PDK_ROOT_ENV}; no PDK is bundled"
                       if param in PDK_FILES else f"{param}=VALUE")
                reasons.append(f"needs {label} ({how})")
            elif param in PDK_FILES:
                reasons += [f"{param} not found: {p}" for p in pdk_paths(params, param) if not p.is_file()]
        for param in (f for f in PDK_FILES if f not in inputs):  # an optional PDK file, when given, exists (M29)
            reasons += [f"{param} not found: {p}" for p in pdk_paths(params, param) if not p.is_file()]
        return "; ".join(reasons) or None

    return check


def _tcl(text: str) -> str:
    """A TCL double-quoted string with nothing substituted."""
    for char in ("\\", '"', "$", "[", "]"):
        text = text.replace(char, "\\" + char)
    return f'"{text}"'


def _token(params: dict[str, str], key: str) -> str:
    value = params.get(key, "").strip()
    if not _TOKEN_RE.match(value):
        raise ValueError(f"{key} must be a plain name, not {value!r}")
    return value


def _layers(params: dict[str, str], key: str) -> str:
    names = list_values(params.get(key, ""))
    for name in names:
        if not _TOKEN_RE.match(name):
            raise ValueError(f"{key} must name layers, not {params.get(key)!r}")
    return names[0] if len(names) == 1 else "{" + " ".join(names) + "}"


def _number(params: dict[str, str], key: str, default: str) -> str:
    value = params.get(key, "").strip() or default
    float(value)  # a ValueError here is a recorded failed run
    return value


def _design(job: Job, key: str) -> str:
    return _tcl(str(Path(job.params[key]).resolve()))


def _timing_reports() -> list[str]:
    return ["report_checks -path_delay max -digits 3",
            "report_checks -path_delay min -digits 3",
            "report_checks -path_delay min_max -slack_max 0 "
            f"-group_path_count {VIOLATOR_REPORT_LIMIT} -endpoint_path_count 1 -digits 3",
            "report_worst_slack -max -digits 3",
            "report_worst_slack -min -digits 3",
            "report_tns -digits 3",
            "report_wns -digits 3"]


# --- synth.run: yosys-liberty -------------------------------------------------------------


def _tie_cell(params: dict[str, str], key: str) -> list[str]:
    """``CELL/PORT`` from a tie parameter, as ``hilomap`` takes it, or nothing when it is not given."""
    value = params.get(key, "").strip()
    if not value:
        return []
    cell, _, port = value.partition("/")
    if not (_TOKEN_RE.match(cell) and _TOKEN_RE.match(port)):
        raise ValueError(f"{key} must be CELL/PORT, not {value!r}")
    return [cell, port]


def _synth_steps(job: Job) -> list[list[str]]:
    lib = f'"{pdk_paths(job.params, "liberty")[0]}"'  # the first Liberty file, quoted as eda.py quotes sources
    high, low = _tie_cell(job.params, "tie_high"), _tie_cell(job.params, "tie_low")
    # Constants become tie cells when the PDK names them: a router cannot route a
    # logic 0 or 1 net (OpenROAD's detailed router rejects it as a ground net).
    ties = ["hilomap -singleton" + (" -hicell {} {}".format(*high) if high else "")
            + (" -locell {} {}".format(*low) if low else "")] if high or low else []
    script = [*(f'read_verilog -sv "{src}"' for src in job.sources),
              f"synth -top {job.top}",
              f"dfflibmap -liberty {lib}",
              f"abc -liberty {lib}",
              *ties,
              "opt_clean -purge",
              f"tee -q -o stat.json stat -json -liberty {lib}",
              "write_verilog -noattr -noexpr -nohex -nodec netlist.v"]
    (job.workdir / "synth_liberty.ys").write_text("\n".join(script) + "\n", encoding="utf-8")
    for stale in ("stat.json", "netlist.v"):
        (job.workdir / stale).unlink(missing_ok=True)
    return [["yosys", "-s", "synth_liberty.ys"]]


def _synth_parse(run: RunRecord) -> EdaResult:
    stat = run.workdir / "stat.json"
    stat_json = stat.read_text(encoding="utf-8") if stat.is_file() else None
    result = parse_yosys(run.log, run.returncode, stat_json)
    metrics = dict(result.metrics)
    if stat_json:
        try:
            metrics["area"] = json.loads(stat_json).get("design", {}).get("area")
        except json.JSONDecodeError:
            pass
    netlist = run.workdir / "netlist.v"
    metrics["netlist"] = str(netlist) if netlist.is_file() else None
    passed = result.passed and metrics["netlist"] is not None
    summary = result.summary if passed or not result.passed else "synthesis failed: no netlist written"
    return EdaResult(passed, summary, result.diagnostics, metrics)


# --- sta.run: OpenSTA ---------------------------------------------------------------------


def _sta_script(job: Job, lefs: bool = False) -> None:
    lef_files = pdk_paths(job.params, "tech_lef") + pdk_paths(job.params, "lef") if lefs else []
    script = [*(f"read_lef {_tcl(str(f))}" for f in lef_files),
              *(f"read_liberty {_tcl(str(p))}" for p in pdk_paths(job.params, "liberty")),
              f"read_verilog {_design(job, 'netlist')}",
              f"link_design {_token(job.params, 'top')}",
              f"read_sdc {_design(job, 'sdc')}"]
    if job.params.get("spef", "").strip():  # M29: and say how much of the design the SPEF annotates
        script += [f"read_spef {_design(job, 'spef')}", "report_parasitic_annotation"]
    script += _timing_reports()
    (job.workdir / "sta.tcl").write_text("\n".join(script) + "\n", encoding="utf-8")


def _sta_steps(job: Job) -> list[list[str]]:
    _sta_script(job)
    return [["sta", "-no_init", "-no_splash", "-exit", "sta.tcl"]]


def _openroad_sta_steps(job: Job) -> list[list[str]]:
    """The same script in OpenROAD, which embeds OpenSTA: packaged OpenROAD builds ship no ``sta``.

    OpenROAD links a netlist into its database, so it reads the LEFs first.
    """
    _sta_script(job, lefs=True)
    return [["openroad", "-no_init", "-no_splash", "-exit", "sta.tcl"]]


def _sta_parse(run: RunRecord) -> EdaResult:
    return parse_opensta(run.log, run.returncode)


# --- pnr.run: OpenROAD --------------------------------------------------------------------


def _stage(name: str, commands: list[str]) -> list[str]:
    return [f'puts "nirmaan-stage: {name}"', *commands, f'puts "nirmaan-stage-done: {name}"']


def _cells(params: dict[str, str], key: str) -> list[str]:
    names = [n.strip() for n in params.get(key, "").split(",") if n.strip()]
    for name in names:
        if not _TOKEN_RE.match(name):
            raise ValueError(f"{key} must name cells, not {params.get(key)!r}")
    return names


def _source(params: dict[str, str], key: str) -> list[str]:
    """``source`` the PDK script a parameter names, when it is given (M29)."""
    return [f"source {_tcl(str(f))}" for f in pdk_paths(params, key)]


#: Worst slack and TNS at one point in the flow, printed inside the stage that reached it (M29).
_SLACK_CHECKPOINT = ["report_worst_slack -max -digits 3", "report_worst_slack -min -digits 3", "report_tns -digits 3"]

#: Counts instance supply pins with no net after the power grid's global connections (M29).
_SUPPLY_PIN_CHECK = '''set nirmaan_open 0
foreach inst [[ord::get_db_block] getInsts] {
  foreach iterm [$inst getITerms] {
    set kind [[$iterm getMTerm] getSigType]
    if {($kind eq "POWER" || $kind eq "GROUND") && [$iterm getNet] eq "NULL"} { incr nirmaan_open }
  }
}
puts "nirmaan-unconnected-supply-pins: $nirmaan_open"'''

#: Every supply net in the block, for the grid connectivity check (M29).
_SUPPLY_NETS = '''set nirmaan_supplies {}
foreach net [[ord::get_db_block] getNets] {
  if {[$net getSigType] eq "POWER" || [$net getSigType] eq "GROUND"} { lappend nirmaan_supplies [$net getName] }
}
puts "nirmaan-supply-nets: $nirmaan_supplies"'''

#: Each power net at the supply voltage and each ground net at 0 V, for IR-drop analysis (M29).
_SUPPLY_VOLTAGES = '''foreach net $nirmaan_supplies {
  set kind [[[ord::get_db_block] findNet $net] getSigType]
  set_pdnsim_net_voltage -net $net -voltage [expr {$kind eq "POWER" ? SUPPLY_VOLTAGE : 0}]
}'''


def _pnr_plan(params: dict[str, str]) -> list[str]:
    """The stages this run executes: up to ``stop_after``; ``extract`` only with OpenRCX rules (M29)."""
    extract = bool(params.get("rcx_rules", "").strip())
    stop_after = params.get("stop_after", "").strip() or ("extract" if extract else "route")
    if stop_after not in PNR_STAGES:
        raise ValueError(f"stop_after must be one of {', '.join(PNR_STAGES)}, not {stop_after!r}")
    if stop_after == "extract" and not extract:
        raise ValueError("stop_after=extract needs rcx_rules (the PDK's OpenRCX rules file)")
    return list(PNR_STAGES[:PNR_STAGES.index(stop_after) + 1])


def _pnr_steps(job: Job) -> list[list[str]]:
    p = job.params
    plan = _pnr_plan(p)
    tap, endcap = _cells(p, "tap_cell"), _cells(p, "endcap_cell")
    if tap and not p.get("tap_distance", "").strip():
        raise ValueError("tap_cell needs tap_distance (microns between tap columns, from the PDK)")
    script = ["set_thread_count [cpu_count]",  # M29: the detailed router is the long step
              *(f"read_lef {_tcl(str(f))}" for f in pdk_paths(p, "tech_lef") + pdk_paths(p, "lef")),
              *(f"read_liberty {_tcl(str(f))}" for f in pdk_paths(p, "liberty")),
              f"read_verilog {_design(job, 'netlist')}",
              f"link_design {_token(p, 'top')}",
              f"read_sdc {_design(job, 'sdc')}",
              *_source(p, "rc_tcl")]
    power = []
    if tap:
        power.append(f"tapcell -distance {_number(p, 'tap_distance', '0')} -tapcell_master {tap[0]}"
                     + (f" -endcap_master {endcap[0]}" if endcap else ""))
    grid = bool(p.get("pdn_tcl", "").strip())
    if grid:
        power += [*_source(p, "pdn_tcl"), "pdngen"]
    script += _stage("floorplan", [
        f"initialize_floorplan -utilization {_number(p, 'utilization', '40')} "
        f"-aspect_ratio {_number(p, 'aspect_ratio', '1')} -core_space {_number(p, 'core_space', '2')} "
        f"-site {_token(p, 'site')}",
        "make_tracks",
        *power,
        f"place_pins -hor_layers {_layers(p, 'hor_layers')} -ver_layers {_layers(p, 'ver_layers')}",
        "report_design_area"])
    density = f" -density {_number(p, 'place_density', '0')}" if p.get("place_density", "").strip() else ""
    if "place" in plan:
        script += _stage("place", [f"global_placement{density}",
                                   "estimate_parasitics -placement", "repair_design",
                                   "detailed_placement", "check_placement -verbose", "report_design_area",
                                   *_SLACK_CHECKPOINT])
    if "cts" in plan:
        buffers = _cells(p, "cts_buffers")
        script += _stage("cts", [
            "clock_tree_synthesis" + (f" -buf_list {{{' '.join(buffers)}}}" if buffers else ""),
            "set_propagated_clock [all_clocks]",
            "estimate_parasitics -placement",
            "repair_clock_nets",
            "detailed_placement",
            "repair_timing -setup -hold",
            "detailed_placement",
            "check_placement -verbose",
            "report_cts",
            "report_clock_skew -digits 3",
            "report_clock_latency -digits 3",
            "report_design_area",
            *_SLACK_CHECKPOINT])
    if "route" in plan:
        layers = (f"set_routing_layers -signal {_token(p, 'min_routing_layer')}-{_token(p, 'max_routing_layer')}"
                  if p.get("min_routing_layer", "").strip() else None)
        fillers = _cells(p, "filler_cells")
        voltage = p.get("supply_voltage", "").strip()
        ir = []
        if voltage:  # IR drop: each power net at the supply voltage, each ground net at 0 V
            ir = [_SUPPLY_VOLTAGES.replace("SUPPLY_VOLTAGE", _number(p, "supply_voltage", "0")),
                  "foreach net $nirmaan_supplies { analyze_power_grid -net $net }"]
        script += _stage("route", [
            *([layers] if layers else []),
            "global_route",
            "estimate_parasitics -global_routing",
            *_SLACK_CHECKPOINT,
            "detailed_route -output_drc route_drc.rpt",
            *([f"filler_placement {{{' '.join(fillers)}}}"] if fillers else []),
            "check_placement -verbose",
            "check_antennas",
            # Buffers, the clock tree, and fillers came after the grid's global connections: connect them too.
            *(["global_connect"] if grid else []),
            _SUPPLY_PIN_CHECK,
            _SUPPLY_NETS,
            *(["foreach net $nirmaan_supplies { check_power_grid -net $net }"] if grid else []),
            *ir])
    if "extract" in plan:
        rules = pdk_paths(p, "rcx_rules")[0]
        script += _stage("extract", ["define_process_corner -ext_model_index 0 X",
                                     f"extract_parasitics -ext_model_file {_tcl(str(rules))}",
                                     "write_spef route.spef", "read_spef route.spef",
                                     "report_parasitic_annotation -report_unannotated", *_SLACK_CHECKPOINT])
    last = plan[-1]
    parasitics = {"place": ["estimate_parasitics -placement"], "cts": ["estimate_parasitics -placement"],
                  "route": ["estimate_parasitics -global_routing"]}.get(last, [])
    script += _stage("timing", [*parasitics, *_timing_reports()])
    final = "route" if last == "extract" else last
    script.append(f"write_def {final}.def")
    if final == "route":
        script.append("write_verilog final.v")
    (job.workdir / "pnr.tcl").write_text("\n".join(script) + "\n", encoding="utf-8")
    return [["openroad", "-no_init", "-no_splash", "-exit", "pnr.tcl"]]


def _planned_stages(workdir: Path) -> list[str]:
    """The stages the script that ran asked for."""
    script = workdir / "pnr.tcl"
    text = script.read_text(encoding="utf-8") if script.is_file() else ""
    return [s for s in PNR_STAGES if f"nirmaan-stage: {s}" in text] or list(PNR_STAGES[:PNR_STAGES.index("route") + 1])


def _pnr_parse(run: RunRecord) -> EdaResult:
    planned = _planned_stages(run.workdir)
    result = parse_openroad(run.log, run.returncode, planned[-1], planned)
    final = "route" if planned[-1] == "extract" else planned[-1]
    outputs = {kind: str(run.workdir / name) for kind, name in
               (("def", f"{final}.def"), ("netlist", "final.v"), ("spef", "route.spef"))
               if (run.workdir / name).is_file()}
    return EdaResult(result.passed, result.summary, result.diagnostics, {**result.metrics, "outputs": outputs})


LIBERTY = {"liberty": "a Liberty file"}

register_backend(Backend("yosys-liberty", "synth.run", ("yosys",), _synth_steps, _synth_parse, ("sources", "top"),
                         environment=needs_pdk(**LIBERTY)))
register_backend(Backend("opensta", "sta.run", ("sta",), _sta_steps, _sta_parse, ("netlist", "sdc", "top"),
                         files=("netlist", "sdc", "spef"), environment=needs_pdk(**LIBERTY)))
# Standalone OpenSTA first; OpenROAD's embedded OpenSTA when only OpenROAD is installed.
register_backend(Backend("openroad-sta", "sta.run", ("openroad",), _openroad_sta_steps, _sta_parse,
                         ("netlist", "sdc", "top"), files=("netlist", "sdc", "spef"),
                         environment=needs_pdk(**LIBERTY, tech_lef="a technology LEF", lef="a cell LEF")))
_PNR_PDK = needs_pdk(**LIBERTY, tech_lef="a technology LEF", lef="a cell LEF", site="a placement site",
                     hor_layers="horizontal pin layers", ver_layers="vertical pin layers")


def _pnr_environment(params: dict[str, str]) -> str | None:
    """The PDK inputs, and (M29) layer RC whenever the flow reaches clock-tree synthesis."""
    reasons = [r for r in (_PNR_PDK(params),) if r]
    try:
        cts = "cts" in _pnr_plan(params)
    except ValueError:
        cts = False  # a bad stop_after is the run's own failure, recorded when it runs
    if cts and not params.get("rc_tcl", "").strip():
        reasons.append("needs the layer RC script for clock-tree synthesis (rc_tcl=PATH, absolute or under "
                       f"{PDK_ROOT_ENV}; no PDK is bundled), or stop_after=place")
    return "; ".join(reasons) or None


register_backend(Backend("openroad", "pnr.run", ("openroad",), _pnr_steps, _pnr_parse, ("netlist", "sdc", "top"),
                         files=("netlist", "sdc"), environment=_pnr_environment))

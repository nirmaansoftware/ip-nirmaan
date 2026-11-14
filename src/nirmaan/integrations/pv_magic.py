"""Physical verification through Magic and Netgen (M79): ``pv.run``'s ``magic-netgen`` backend.

The routed DEF is streamed to GDS exactly as the ``klayout`` backend does (M34: KLayout, the
cells' GDS merged in, ``physical.STREAM_SCRIPT``). Then:

* **DRC** in Magic with the PDK's Magic technology file: the layout is read from that GDS and
  checked, and Nirmaan's own Tcl prints the count of every rule Magic's ``drc listall why``
  reports, so no Magic message text is parsed.
* **LVS**: Magic extracts a SPICE netlist from the same GDS, and Netgen compares it with the
  routed netlist with supply pins (``pnr.run``'s ``pg_netlist``) over the cells' SPICE, under
  the PDK's Netgen setup. Netgen writes its comparison as JSON, and Nirmaan's own count script
  reads that file and prints the mismatched circuits, nets, devices, pins, and subcircuits.

Both print the same ``nirmaan-*`` lines the KLayout scripts print, so ``parse_klayout`` judges
the run and the metrics (``drc_violations``, ``lvs_mismatches``, ...) are the ones the
physical-verification gate already bounds. Magic and Netgen are installed separately and never
vendored; the PDK is an input, never bundled. The backend runs only when named
(``backend: magic-netgen``), so every run records which tools judged it. This module adds a
backend and nothing else: no EDA core change. See ``docs/PD_SKY130_PILOT.md``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from nirmaan.integrations.eda import Backend, EdaResult, Job, RunRecord, register_backend
from nirmaan.integrations.eda_parsers import Diagnostic, _first, _plural
from nirmaan.integrations.pd_parsers import parse_klayout
from nirmaan.integrations.physical import STREAM_SCRIPT, _klayout_tech, _tcl, _token, needs_pdk, pdk_paths
from nirmaan.models import text_value
from nirmaan.runtime.tools import Params

BACKEND = "magic-netgen"

#: Magic DRC over the streamed GDS: every error Magic finds in the hierarchy, counted per rule, in the
#: full rule set (``drc(full)``, the open_pdks name; the style that ran is printed and recorded, M79).
DRC_SCRIPT = '''tech load {tech}
gds read {gds}
load {top}
select top cell
expand
drc euclidean on
drc style drc(full)
puts "nirmaan-magic-drc-style: [drc list style]"
drc check
drc catchup
set total 0
foreach {{why boxes}} [drc listall why] {{
    set n [llength $boxes]
    incr total $n
    puts "nirmaan-drc-rule: [string map {{" " "_"}} $why] $n"
}}
puts "nirmaan-drc-violations: $total"
quit -noprompt
'''

#: Magic extraction of the same GDS to a SPICE netlist for LVS (devices and connectivity, no parasitics).
EXTRACT_SCRIPT = '''tech load {tech}
gds read {gds}
load {top}
select top cell
extract do local
extract no capacitance
extract no coupling
extract no resistance
extract no length
extract all
ext2spice lvs
ext2spice -o {spice} {top}.ext
quit -noprompt
'''

#: Netgen: the extracted layout against the routed netlist read over the cells' SPICE, as JSON.
LVS_SCRIPT = '''set layout [readnet spice {layout}]
set source [readnet spice {cells}]
readnet verilog {netlist} $source
lvs "$layout {top}" "$source {top}" {setup} {report} -json
quit
'''

#: Counts Netgen's JSON comparison: per circuit pair, nets and devices that differ in number or that
#: Netgen could not match, and pins that did not pair, so the judgement never rests on Netgen's prose.
LVS_COUNT_SCRIPT = '''import json
import sys

report, top = sys.argv[1], sys.argv[2]
with open(report.rsplit(".", 1)[0] + ".json", encoding="utf-8") as f:
    cells = json.load(f)
bad = {"circuits": 0, "nets": 0, "devices": 0, "pins": 0, "subcircuits": 0}
for cell in cells:
    names = cell.get("name") or ["-", "-"]
    nets = devices = pins = 0
    if "nets" in cell:
        nets += abs(int(cell["nets"][0]) - int(cell["nets"][1]))
    for group in cell.get("badnets", []):
        nets += 1
    if "devices" in cell:
        counts = [dict((d[0], int(d[1])) for d in side) for side in cell["devices"]]
        devices += sum(abs(counts[0].get(k, 0) - counts[1].get(k, 0)) for k in set(counts[0]) | set(counts[1]))
    for group in cell.get("badelements", []):
        devices += 1
    if "pins" in cell:
        left, right = cell["pins"]
        pins += sum(1 for a, b in zip(left, right) if a != b) + abs(len(left) - len(right))
    status = "Mismatch" if nets or devices or pins else "Match"
    print("nirmaan-lvs-circuit: %s %s %s" % (names[0] or "-", names[-1] or "-", status))
    bad["circuits"] += status == "Mismatch"
    bad["nets"] += nets
    bad["devices"] += devices
    bad["pins"] += pins
with open(report, encoding="utf-8", errors="replace") as f:
    final = [line.strip() for line in f if line.startswith("Final result")]
print("nirmaan-netgen-final: " + (final[-1] if final else "none"))
if not (final and "match uniquely" in final[-1]) and not bad["circuits"]:
    bad["circuits"] = 1  # Netgen did not call the top a unique match: never a clean result
for kind, n in bad.items():
    print("nirmaan-lvs-mismatched-%s: %d" % (kind, n))
'''


def _steps(job: Job) -> list[list[str]]:
    p, work = job.params, job.workdir
    top = _token(p, "top")
    for stale in ("layout.gds", "layout.spice", "lvs.report", "lvs.json"):
        (work / stale).unlink(missing_ok=True)
    tech, gds = _tcl(str(pdk_paths(p, "magic_tech")[0])), _tcl(str(work / "layout.gds"))
    scripts = {
        "stream.py": STREAM_SCRIPT,
        "magic_drc.tcl": DRC_SCRIPT.format(tech=tech, gds=gds, top=top),
        "magic_extract.tcl": EXTRACT_SCRIPT.format(tech=tech, gds=gds, top=top, spice=_tcl(str(work / "layout.spice"))),
        "netgen_lvs.tcl": LVS_SCRIPT.format(layout=_tcl(str(work / "layout.spice")),
                                            cells=_tcl(str(pdk_paths(p, "spice")[0])),
                                            netlist=_tcl(str(Path(p["netlist"]).resolve())), top=top,
                                            setup=_tcl(str(pdk_paths(p, "netgen_setup")[0])),
                                            report=_tcl(str(work / "lvs.report"))),
        "lvs_count.py": LVS_COUNT_SCRIPT,
    }
    for name, text in scripts.items():
        (work / name).write_text(text, encoding="utf-8")
    return [["klayout", "-zz", "-rd", f"tech_file={_klayout_tech(job)}",
             "-rd", f"in_def={Path(p['def']).resolve()}",
             "-rd", f"in_gds={' '.join(str(f) for f in pdk_paths(p, 'gds'))}",
             "-rd", f"design_name={top}", "-rd", f"out_file={work / 'layout.gds'}", "-r", "stream.py"],
            ["magic", "-dnull", "-noconsole", "magic_drc.tcl"],
            ["magic", "-dnull", "-noconsole", "magic_extract.tcl"],
            ["netgen", "-batch", "source", "netgen_lvs.tcl"],
            [sys.executable, "-I", "lvs_count.py", str(work / "lvs.report"), top]]


#: Magic skips a GDS shape on a layer its technology does not read and goes on: the checks would then
#: judge a layout with shapes missing, so each such line fails the run.
_GDS_SKIP_RE = re.compile(r'^Error while reading cell "(?P<cell>[^"]+)".*?: (?P<msg>.*)$')
_STYLE_RE = re.compile(r"^nirmaan-magic-drc-style: (?P<style>\S+)")
_FINAL_RE = re.compile(r"^nirmaan-netgen-final: (?P<final>.*)$")


def _parse(run: RunRecord) -> EdaResult:
    result = parse_klayout(run.log, run.returncode, ["drc", "lvs"])
    lines = [line.strip() for line in run.log.splitlines()]
    # Both Magic sessions read the same GDS, so each record is counted once.
    skipped = [Diagnostic("error", f"Magic skipped GDS shapes in {text}") for text in dict.fromkeys(
        f"{m['cell']}: {m['msg']}" for line in lines if (m := _GDS_SKIP_RE.match(line)))]
    style = next((m["style"] for line in lines if (m := _STYLE_RE.match(line))), None)
    final = next((m["final"] for line in lines if (m := _FINAL_RE.match(line))), None)
    outputs = {kind: str(run.workdir / name) for kind, name in
               (("gds", "layout.gds"), ("layout_spice", "layout.spice"), ("lvs_report", "lvs.report"))
               if (run.workdir / name).is_file()}
    metrics = {**result.metrics, "magic_drc_style": style, "netgen_final": final,
               "gds_shapes_skipped": len(skipped), "outputs": outputs}
    summary = result.summary.replace("physical verification", "physical verification (Magic and Netgen)", 1)
    if skipped:
        why = f"{_plural(len(skipped), 'GDS record')} Magic could not read{_first(skipped)}"
        rest = summary.split(": ", 1)[1] if not result.passed else ""
        summary = f"physical verification (Magic and Netgen) failed: {why}" + (f"; {rest}" if rest else "")
        return EdaResult(False, summary, (*result.diagnostics, *skipped), metrics)
    return EdaResult(result.passed, summary, result.diagnostics, metrics)


_PDK = needs_pdk(tech_lef="a technology LEF", lef="a cell LEF", gds="the cells' GDS",
                 klayout_tech="the PDK's KLayout technology (.lyt), for the stream to GDS",
                 magic_tech="the PDK's Magic technology file (.tech)",
                 netgen_setup="the PDK's Netgen setup (.tcl)", spice="the cells' SPICE netlists")


def _environment(params: Params) -> str | None:
    """The PDK inputs; and the backend runs only when named, so a run never lands here by default."""
    if text_value(params.get("backend")).strip() != BACKEND:
        return f"the {BACKEND} backend runs only when named (backend: {BACKEND})"
    return _PDK(params)


register_backend(Backend(BACKEND, "pv.run", ("klayout", "magic", "netgen"), _steps, _parse,
                         ("def", "netlist", "top"), files=("def", "netlist"), environment=_environment))

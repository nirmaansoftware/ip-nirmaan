"""The RTLLM adapter (M76): the benchmark's design problems as calibration runs of the RTL seat.

RTLLM (https://github.com/hkust-zhiyao/RTLLM) is 50 small designs, each a
natural-language description, a testbench and a reference RTL. The benchmark lives outside both repositories, in a
private folder named by path (``docs/OUTSIDE_CALIBRATION.md``); nothing of it is committed here, and this module
carries no benchmark text. For each design it:

* stages, in a temporary folder, the description as the seat's approved interface specification, a one-line
  microarchitecture note of our own, the reference RTL (for a replay only) and the benchmark's testbench;
* adds to the staged testbench copy one line, and nothing else: next to the benchmark's own pass message it prints
  the verdict line the simulator gate reads (M53, ``NIRMAAN-SIM <nonce> 1 passed, 0 failed``). The testbench's own
  checks decide whether that message is reached, so the judge stays the benchmark's;
* builds an ``EvalCase`` whose one held-out check runs that testbench over the seat's RTL through the simulator
  broker (``simulator.run``, scorer ``held-out-run``), and records the runs with ``record_run``, labelled
  ``purpose: calibration`` in the manifest and every trial, so the levels generator lists them and never counts them.

A trial's harness fingerprint (M73) is recorded by the same code path as any trial. Nothing here is a harness
file, so this module does not change it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from nirmaan.evals.cases import EvalError
from nirmaan.evals.records import record_run
from nirmaan.models import CaseFile, EvalCase, HeldOutCheck
from nirmaan.org import Organization

#: The environment variable the CLI reads the benchmark's path from when ``--benchmark`` is not given.
BENCHMARK_ENV = "NIRMAAN_RTLLM_DIR"
SOURCE = "RTLLM (hkust-zhiyao/RTLLM, MIT)"
UPSTREAM_FILE = "UPSTREAM_COMMIT"
#: The seat stage and skill the calibration cases evaluate; the skill is the RTL pilot's, so the digest is real.
SEAT = "rtl-implementation"
SKILLS = ("rtl_design",)
#: The one request shape the planner turns into the block-design workflow for any design name (a small block).
REQUEST = "Create the specified module as a small self-contained block, like a counter, from its approved specification."
NO_MICROARCHITECTURE = (
    "# Microarchitecture\n\nThe benchmark gives no separate microarchitecture. Implement the approved interface "
    "specification directly, keeping its module name, ports and behaviour.\n")
FETCH = ("git clone https://github.com/hkust-zhiyao/RTLLM ~/Nirmaan-internal/benchmarks/rtllm  "
         f"(then set {BENCHMARK_ENV} or pass --benchmark; see docs/OUTSIDE_CALIBRATION.md)")

_PASS = re.compile(r'\$display\s*\(\s*"[^"\n]*Your Design Passed[^"\n]*"\s*\)\s*;')
_MODULE = re.compile(r"^\s*module\s+(\w+)", re.MULTILINE)
_NAMED = re.compile(r"Module name\s*:\s*(\w+)", re.IGNORECASE)
DATA_SUFFIXES = (".dat", ".txt", ".hex", ".mem")
_SKIPPED = ("_chatgpt",)  # model-generated answers, not problems; never read


class OutsideError(EvalError):
    """The benchmark cannot be read, or a design cannot be mapped. Nothing was scored."""


@dataclass(frozen=True)
class Design:
    """One benchmark design: where its files are, read from the private copy."""

    name: str
    directory: Path

    @property
    def description(self) -> Path:
        return self.directory / "design_description.txt"

    @property
    def testbench(self) -> Path:
        return self.directory / "testbench.v"

    @property
    def reference(self) -> Path:
        """The one ``verified_*.v`` file (its name is not always the design's); the folder itself if none."""
        found = sorted(self.directory.glob("verified_*.v"))
        return found[0] if len(found) == 1 else self.directory / "verified_(one file).v"


def locate(root: Path | str) -> list[Design]:
    """Every design under the benchmark folder, by name; the model-output folders are never entered."""
    root = Path(root).expanduser()
    if not root.is_dir():
        raise OutsideError(f"the RTLLM benchmark is not at {root}. It lives outside the repositories: {FETCH}")
    found: dict[str, Design] = {}
    for path in sorted(root.rglob("design_description.txt")):
        rel = path.relative_to(root).parts
        if any(part.startswith(_SKIPPED) or part.startswith(".") for part in rel):
            continue
        design = Design(path.parent.name, path.parent)
        if design.name in found:
            raise OutsideError(f"two designs are named {design.name!r}: {found[design.name].directory} and "
                               f"{design.directory}")
        found[design.name] = design
    if not found:
        raise OutsideError(f"no design_description.txt under {root}: this is not an RTLLM copy. {FETCH}")
    return [found[name] for name in sorted(found)]


def upstream_commit(root: Path | str) -> str:
    """The upstream commit the copy was fetched at: ``UPSTREAM_COMMIT`` in the folder, else its git HEAD."""
    root = Path(root).expanduser()
    note = root / UPSTREAM_FILE
    if note.is_file():
        return note.read_text(encoding="utf-8").strip().split()[0]
    try:
        done = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10)
    except (OSError, subprocess.SubprocessError):
        done = None
    if done is None or done.returncode != 0 or not done.stdout.strip():
        raise OutsideError(f"cannot tell which upstream commit {root} is: it is not a git clone and has no "
                           f"{UPSTREAM_FILE} file. Record the commit before calibrating.")
    return done.stdout.strip()


def _licence(root: Path) -> None:
    if not (root / "LICENSE").is_file():
        raise OutsideError(f"{root} has no LICENSE file: the MIT notice must stay with the benchmark copy")


def with_verdict(text: str, finish: bool = False) -> str:
    """The benchmark's testbench with the simulator gate's verdict line printed beside its own pass message.

    Only the one ``$display`` of "Your Design Passed" is touched: it becomes a block that prints that message and
    then ``NIRMAAN-SIM <nonce> 1 passed, 0 failed``. A testbench that never reaches its pass message prints no
    verdict, and the gate fails the run. With ``finish`` a ``$finish`` follows the verdict (for a testbench that
    never ends the simulation itself: the gate needs one). Raises :class:`OutsideError` unless the message occurs exactly once.
    """
    hits = _PASS.findall(text)
    if len(hits) != 1:
        raise OutsideError(f"the testbench has {len(hits)} 'Your Design Passed' messages; the adapter needs one")
    block = ("begin : nirmaan_verdict reg [8*64-1:0] nirmaan_nonce; " + hits[0] +
             ' if (!$value$plusargs("nirmaan_nonce=%s", nirmaan_nonce)) nirmaan_nonce = "none"; '
             '$display("NIRMAAN-SIM %0s 1 passed, 0 failed", nirmaan_nonce);' + (" $finish;" if finish else "") + " end")
    return text.replace(hits[0], block, 1)


def dut_name(design: Design, description: str) -> str:
    """The module the description asks for (its ``Module name`` line), else the design's own name."""
    found = _NAMED.search(description)
    return found.group(1) if found else design.name


def _reference(text: str, dut: str) -> str:
    """The reference RTL with its top module renamed to ``dut``: the copies name it ``verified_<design>``.

    The top is the module that no other module in the file instantiates (by name followed by an instance), the
    last such one when several; a file whose top already is ``dut`` is returned as it is.
    """
    modules = _MODULE.findall(text)
    if not modules or dut in modules:
        return text
    tops = [m for m in modules if not re.search(rf"^\s*{re.escape(m)}\s+(#\s*\(|\w+\s*\()", text, re.MULTILINE)]
    top = tops[-1] if tops else modules[-1]
    return re.sub(rf"\b{re.escape(top)}\b", dut, text)


def _case(design: Design, stage: Path, tb_top: str, dut: str) -> EvalCase:
    where = stage / design.name
    spec, micro = where / f"{design.name}_spec.txt", where / f"{design.name}_microarchitecture.md"
    ref, tb = where / f"{design.name}.v", where / f"{design.name}_rtllm_tb.v"
    return EvalCase(
        id=f"rtllm/{design.name}", request=REQUEST, seat=SEAT, skills=SKILLS,
        expected_behavior=f"RTL for the module the approved interface specification names, judged by the "
                          f"benchmark's own testbench ({SOURCE}); an outside calibration, never level evidence.",
        upstream={"interface-spec": (CaseFile(path=str(spec), kind="interface_spec"),),
                  "microarchitecture": (CaseFile(path=str(micro), kind="microarchitecture_spec"),)},
        reference=(CaseFile(path=str(ref), kind="rtl_source", entry=dut),
                   CaseFile(path=str(tb), kind="testbench", entry=tb_top)),
        held_out=(HeldOutCheck(name="The benchmark's testbench passes on the seat's RTL", scorer="held-out-run",
                               tool="simulator.run", seat_files={"sources": ("rtl_source",)},
                               case_files={"sources": (str(tb),)}, params={"top": tb_top}),))


def stage_cases(root: Path | str, stage: Path, names: Sequence[str] = ()) -> list[EvalCase]:
    """Stage the designs (all, or ``names``) under ``stage`` and return their cases, in design-name order."""
    root = Path(root).expanduser()
    designs = locate(root)
    _licence(root)
    unknown = sorted(set(names) - {d.name for d in designs})
    if unknown:
        raise OutsideError(f"unknown design {', '.join(unknown)}; the copy has {len(designs)} designs")
    cases = []
    for design in designs:
        if names and design.name not in names:
            continue
        for part in (design.description, design.testbench, design.reference):
            if not part.is_file():
                raise OutsideError(f"{design.name}: {part.name} is missing from {design.directory}")
        tb_text = design.testbench.read_text(encoding="utf-8", errors="replace")
        modules = _MODULE.findall(tb_text)
        if not modules:
            raise OutsideError(f"{design.name}: the testbench declares no module")
        try:
            staged_tb = with_verdict(tb_text, finish="$finish" not in tb_text)
        except OutsideError as exc:
            raise OutsideError(f"{design.name}: {exc}") from exc
        where = Path(stage) / design.name
        where.mkdir(parents=True, exist_ok=True)
        # the testbench reads its data files by bare name, from where VCS ran it; a staged copy names them in full
        for data in sorted(p for p in design.directory.iterdir()
                           if p.suffix in DATA_SUFFIXES and p != design.description):
            shutil.copyfile(data, where / data.name)
            staged_tb = staged_tb.replace(f'"{data.name}"', f'"{where / data.name}"')
        description = design.description.read_text(encoding="utf-8", errors="replace")
        (where / f"{design.name}_spec.txt").write_text(description.rstrip("\n") + "\n", encoding="utf-8")
        (where / f"{design.name}_microarchitecture.md").write_text(NO_MICROARCHITECTURE, encoding="utf-8")
        # a file block's END line must start a line, so every staged text ends with a newline
        dut = dut_name(design, description)
        reference = _reference(design.reference.read_text(encoding="utf-8", errors="replace"), dut)
        (where / f"{design.name}.v").write_text(reference.rstrip("\n") + "\n", encoding="utf-8")
        (where / f"{design.name}_rtllm_tb.v").write_text(staged_tb.rstrip("\n") + "\n", encoding="utf-8")
        cases.append(_case(design, Path(stage), modules[0], dut))
    return cases


def _judge_references(org: Organization, cases: Sequence[EvalCase]) -> list[tuple[str, bool, str]]:
    from nirmaan.models import Actor, ActorKind
    from nirmaan.orchestrator import Orchestrator
    from nirmaan.runtime import ToolBroker, ToolHandle

    out = []
    for case in cases:
        engine = Orchestrator(org).plan(case.request)
        [seat] = [t for t in engine.state.tasks.values() if t.stage == case.seat]
        tools = ToolHandle(ToolBroker(engine), Actor(role=str(seat.owner), kind=ActorKind.SYSTEM,
                                                     name="eval-scorer"), seat.id)
        ref, tb = (f.path for f in case.reference)
        _, outcome = tools.invoke("simulator.run", sources=[ref, tb], top=case.held_out[0].params["top"])
        out.append((case.id.split("/", 1)[1], outcome.succeeded, outcome.summary))
    return out


def check_reference(org: Organization, root: Path | str, names: Sequence[str] = ()) -> list[tuple[str, bool, str]]:
    """Judge each design's reference RTL with the benchmark's testbench through the simulator broker, seat-free.

    Proves the mapping and the judge, not a seat: one ``(design, passed, summary)`` per design. The reference goes
    straight to ``simulator.run``, so a reference our lint or synthesis rules would refuse still shows its verdict.
    """
    with tempfile.TemporaryDirectory(prefix="nirmaan-rtllm-") as stage:
        return _judge_references(org, stage_cases(root, Path(stage), names))


def calibrate(org: Organization, root: Path | str, *, runtime: str | None, trials: int, out: Path,
              names: Sequence[str] = (), command: str = "", on_trial=None) -> Path:
    """Run the designs on a registered runtime (``None`` replays the reference RTL) and write a calibration record.

    The record is a normal run record (``record_run``) labelled ``purpose: calibration`` in its manifest and every
    trial, naming the benchmark, its upstream commit and its licence. Every trial carries the harness fingerprint.
    A design whose reference RTL does not pass its own testbench under our simulator is not mapped: it is left out,
    and the manifest's ``source`` says how many mapped and names the rest.
    """
    root = Path(root).expanduser()
    commit = upstream_commit(root)
    with tempfile.TemporaryDirectory(prefix="nirmaan-rtllm-") as stage:
        cases = stage_cases(root, Path(stage), names)
        left = sorted(name for name, ok, _ in _judge_references(org, cases) if not ok)
        mapped = [c for c in cases if c.id.split("/", 1)[1] not in left]
        if not mapped:
            raise OutsideError("no design maps: no reference RTL passes its testbench under the simulator")
        note = f"; {len(mapped)} of {len(cases)} designs mapped" + (f", not mapped: {', '.join(left)}" if left else "")
        return record_run(org, mapped, runtime, trials=trials, repo=Path(stage), out=out, command=command,
                          head_sha=None, on_trial=on_trial, purpose="calibration",
                          source=f"{SOURCE} at {commit}{note}")

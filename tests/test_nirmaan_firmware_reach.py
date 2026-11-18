"""Gate WF14: what a driver test can reach under fw.test (council record 2026-11-17, addendum 2026-11-18).

The addendum dropped the fixture driver test of decision 2 for the register block: through ``read32``, ``write32``
and the driver interface, on that block, no driver test can be strict about response latency. That rests on the
harness's construction, so this file pins it. A driver test under fw.test is host C, compiled with the HAL's
directory on its include path and linked into one image with a host manager and Verilator's runtime. What it can
reach is listed here, exactly:

* the members of ``nirmaan_hal`` and every declaration of the two headers a test includes;
* the external definitions of each host manager (everything else in a manager, and all of ``harness_report.h``,
  is in an anonymous namespace, so no test can name it), the managers registered, and the files on the include path;
* the headers each manager includes, and the Verilator options the model is built with, since they decide which
  simulator symbols the image holds.

Any addition, and any edit to a listed declaration, fails here with the return condition in the message: a change
is made on purpose, together with the list, and the council's return condition is checked before the next trial.

Known reach outside the HAL, not closed by the addendum (its facts 5 and 6; the open security question):

* ``nirmaan_irq_wait(seen, cycles)`` lets cycles pass, and the harness ends a run at 5000000 cycles. A test that
  spends cycles near that limit fails the slower RTL, never the reference, which answers in the fewest cycles the
  document allows. The wait probe (control ``driver-wait-probe`` in ``evals/flow/controls.json``) is recorded
  passing on both RTLs with the same bus transfers.
* The host C library and the operating system (wall time, the process's own output).
* The simulator's runtime: a test's C can name a C++ symbol of Verilator's runtime by its mangled name, and through
  ``Verilated::s_lastContextp`` read the simulation time, so it can time a ``read32``. The tool-backed test at the
  end of this file shows it on both RTLs (CI only: the firmware toolchain never runs a test's C on the Mac).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from laws import needs
from nirmaan.integrations import firmware
from nirmaan.integrations.eda import execute, select_backend

REPO = Path(__file__).resolve().parents[1]
HARNESS = firmware.HARNESS
RTL = REPO / "tests" / "fixtures" / "rtl" / "axi4_lite"
PROBE = REPO / "tests" / "fixtures" / "fw" / "reach" / "simulator_clock_probe.c"

RETURN_CONDITION = (
    "Gate WF14 (council/records/2026-11-17-g3-whole-flow-cases.md, addendum 2026-11-18): what a driver test can "
    "reach under fw.test changed. Return condition: the fixture driver test of decision 2 is required again, "
    "before the next trial, for any case where the HAL or the harness gains a cycle count, a timeout or a "
    "non-blocking access that a driver test can read, or where the block has a register whose value depends on "
    "elapsed cycles, or where the fixed document leaves open a choice visible in data or response codes. Update "
    "this list only together with that check."
)

#: Every file in the directory a driver test's include path holds.
HARNESS_FILES = {"apb_manager.cpp", "axil_manager.cpp", "harness_report.h", "nirmaan_hal.h", "nirmaan_irq.h"}

#: What a driver test can name from the headers it includes: every top-level declaration, comments removed and
#: whitespace collapsed. A struct's members are listed one by one.
HEADER_DECLARATIONS = {
    "nirmaan_hal.h": {
        "#define NIRMAAN_HAL_H",
        "#define NIRMAAN_BUS_OKAY 0u",
        "#define NIRMAAN_BUS_EXOKAY 1u",
        "#define NIRMAAN_BUS_SLVERR 2u",
        "#define NIRMAAN_BUS_DECERR 3u",
        "typedef struct nirmaan_hal nirmaan_hal",
        "struct nirmaan_hal: void *ctx",
        "struct nirmaan_hal: unsigned (*read32)(void *ctx, uint32_t offset, uint32_t *value)",
        "struct nirmaan_hal: unsigned (*write32)(void *ctx, uint32_t offset, uint32_t value, uint8_t strobe)",
        "void nirmaan_fw_test(const nirmaan_hal *hal)",
        "void nirmaan_test_result(const char *name, int passed, const char *detail)",
    },
    "nirmaan_irq.h": {
        "#define NIRMAAN_IRQ_H",
        "typedef void (*nirmaan_irq_handler)(void *ctx)",
        "void nirmaan_irq_attach(nirmaan_irq_handler handler, void *ctx)",
        "unsigned nirmaan_irq_count(void)",
        "unsigned nirmaan_irq_wait(unsigned seen, uint32_t cycles)",
        "typedef struct nirmaan_bus_fault nirmaan_bus_fault",
        "struct nirmaan_bus_fault: uint32_t offset",
        "struct nirmaan_bus_fault: unsigned write",
        "struct nirmaan_bus_fault: unsigned response",
        "struct nirmaan_bus_fault: uint32_t pc",
        "typedef void (*nirmaan_bus_fault_handler)(const nirmaan_bus_fault *fault, void *ctx)",
        "int nirmaan_bus_fault_attach(nirmaan_bus_fault_handler handler, void *ctx)",
        "unsigned nirmaan_bus_fault_count(void)",
    },
}

#: The C functions each host manager exports (its only definitions outside the anonymous namespace), and main.
_EXPORTS = {
    'extern "C" void nirmaan_irq_attach(nirmaan_irq_handler handler, void *ctx)',
    'extern "C" unsigned nirmaan_irq_count(void)',
    'extern "C" unsigned nirmaan_irq_wait(unsigned seen, uint32_t cycles)',
    'extern "C" int nirmaan_bus_fault_attach(nirmaan_bus_fault_handler handler, void *ctx)',
    'extern "C" unsigned nirmaan_bus_fault_count(void)',
    'extern "C" void nirmaan_test_result(const char *name, int passed, const char *detail)',
    "int main(int argc, char **argv)",
}
MANAGER_EXPORTS = {"axil_manager.cpp": _EXPORTS, "apb_manager.cpp": _EXPORTS, "harness_report.h": set()}

#: The headers each harness file includes. verilated.h and Vdut.h bring in Verilator's runtime and the model.
_MANAGER_INCLUDES = ["cstdio", "cstdlib", "cstdint", "Vdut.h", "verilated.h", "nirmaan_hal.h", "nirmaan_irq.h",
                     "harness_report.h"]
INCLUDES = {"axil_manager.cpp": _MANAGER_INCLUDES, "apb_manager.cpp": _MANAGER_INCLUDES,
            "harness_report.h": ["cstdarg", "cstdio", "cstring"], "nirmaan_hal.h": ["stdint.h"],
            "nirmaan_irq.h": ["stdint.h"]}

#: The registered host co-simulation buses and their managers.
COSIM_BUSES = {"axi4-lite": "axil_manager.cpp", "apb": "apb_manager.cpp"}

#: The literal options of the Verilator build in ``firmware._cosim_steps``. An option such as --vpi, --public or
#: --trace would put more simulator symbols (a C time call, the design's signals) in the image.
VERILATOR_OPTIONS = ["verilator", "--cc", "--exe", "--build", "-j", "0", "-Wno-fatal", "--prefix", "-Mdir",
                     "-CFLAGS"]
IRQ_OPTIONS = ["-CFLAGS", "-DNIRMAAN_DUT_IRQ"]


# --- Reading C and C++ just far enough -------------------------------------------------------------------------


def _code(text: str) -> str:
    """The text without comments and string or character contents (``extern "C"`` kept), lines kept."""
    text = text.replace('extern "C"', "extern_C")
    out = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'',
                 lambda m: '""' if m.group(0).startswith('"') else ("''" if m.group(0).startswith("'") else
                                                                    "\n" * m.group(0).count("\n")),
                 text, flags=re.S)
    return out


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).replace("extern_C", 'extern "C"').strip()


def _top_level(code: str) -> list[tuple[str, str | None]]:
    """Each top-level item: its head (up to ``;`` or ``{``) and its braced body, if any."""
    items: list[tuple[str, str | None]] = []
    head, i = "", 0
    while i < len(code):
        ch = code[i]
        if ch == ";":
            items.append((_norm(head), None))
            head = ""
        elif ch == "{":
            depth, j = 1, i + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(code[j], 0)
                j += 1
            items.append((_norm(head), code[i + 1:j - 1]))
            head, i = "", j - 1
        else:
            head += ch
        i += 1
    if _norm(head):
        items.append((_norm(head), None))
    return [(h, b) for h, b in items if h or b]


def _strip_preprocessor(code: str) -> str:
    return "\n".join(ln for ln in code.splitlines() if not ln.lstrip().startswith("#"))


def includes(path: Path) -> list[str]:
    text = re.sub(r"//[^\n]*|/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    return re.findall(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', text, flags=re.M)


def header_declarations(path: Path) -> set[str]:
    """Every top-level declaration of a C header, ``extern "C"`` blocks opened, struct members one by one."""
    raw = path.read_text(encoding="utf-8")
    code = _code(raw)
    out = {_norm(f"#define {m[0]} {m[1]}") for m in re.findall(r"^\s*#\s*define\s+(\w+)[ \t]*([^\n]*)$", code,
                                                                re.M)}
    pending = _top_level(_strip_preprocessor(code))
    while pending:
        head, body = pending.pop(0)
        if head == "extern_C" or head == 'extern "C"':
            pending[:0] = _top_level(body or "")
            continue
        if body is not None:
            m = re.fullmatch(r"typedef struct (\w+)", head)
            assert m, f"{path.name}: a braced declaration this guard cannot read: {head!r}"
            out |= {f"struct {m[1]}: {member}" for member, _ in _top_level(body)}
            alias = pending.pop(0)[0] if pending and pending[0][1] is None else ""
            out.add(f"typedef struct {m[1]} {alias}".strip())
            continue
        out.add(head)
    return out


def external_definitions(path: Path) -> set[str]:
    """The heads of a C++ file's top-level items outside anonymous namespaces: what another object can link to."""
    out = set()
    for head, body in _top_level(_strip_preprocessor(_code(path.read_text(encoding="utf-8")))):
        if head == "namespace" and body is not None:
            continue  # anonymous: internal linkage
        out.add(head)
    return out


def _verilator_options() -> tuple[list[str], list[str]]:
    tree = ast.parse(Path(firmware.__file__).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_cosim_steps")
    lists = [n for n in ast.walk(fn) if isinstance(n, ast.List)]

    def literals(node: ast.List) -> list[str]:
        return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]

    build = [literals(n) for n in lists if literals(n)[:1] == ["verilator"]]
    irq = [literals(n) for n in lists if "-DNIRMAAN_DUT_IRQ" in literals(n)]
    assert len(build) == 1 and len(irq) == 1, (build, irq)
    return build[0], irq[0]


# --- The guard (no tools) --------------------------------------------------------------------------------------


def test_the_include_path_holds_only_the_listed_harness_files():
    got = {p.name for p in HARNESS.iterdir() if not p.name.startswith(".") and p.name != "__pycache__"}
    assert got == HARNESS_FILES, f"{RETURN_CONDITION}\nharness files: {sorted(got ^ HARNESS_FILES)}"


def test_the_hal_has_only_read32_and_write32():
    members = [d.split(": ", 1)[1] for d in header_declarations(HARNESS / "nirmaan_hal.h")
               if d.startswith("struct nirmaan_hal: ")]
    names = set()
    for member in members:
        found = re.search(r"\(\*(\w+)\)", member) or re.search(r"(\w+)$", member)
        assert found, f"{RETURN_CONDITION}\na nirmaan_hal member this guard cannot name: {member!r}"
        names.add(found.group(1))
    assert names == {"ctx", "read32", "write32"}, f"{RETURN_CONDITION}\nnirmaan_hal members: {sorted(names)}"


@pytest.mark.parametrize("header", sorted(HEADER_DECLARATIONS))
def test_a_driver_test_can_name_only_the_listed_declarations(header):
    got = header_declarations(HARNESS / header)
    want = HEADER_DECLARATIONS[header]
    assert got == want, (f"{RETURN_CONDITION}\n{header}: added {sorted(got - want)}; "
                         f"removed or changed {sorted(want - got)}")


@pytest.mark.parametrize("name", sorted(MANAGER_EXPORTS))
def test_each_host_harness_file_exports_only_the_listed_functions(name):
    got = external_definitions(HARNESS / name)
    want = MANAGER_EXPORTS[name]
    assert got == want, (f"{RETURN_CONDITION}\n{name}: added {sorted(got - want)}; "
                         f"removed or changed {sorted(want - got)}")


@pytest.mark.parametrize("name", sorted(INCLUDES))
def test_each_harness_file_includes_only_the_listed_headers(name):
    got = includes(HARNESS / name)
    assert got == INCLUDES[name], f"{RETURN_CONDITION}\n{name} includes {got}"


def test_the_registered_managers_and_the_verilator_build_are_the_listed_ones():
    buses = {bus: path.name for bus, path in firmware.cosim_buses().items()}
    assert buses == COSIM_BUSES, f"{RETURN_CONDITION}\nco-simulation buses: {buses}"
    assert all(path.parent == HARNESS for path in firmware.cosim_buses().values())
    build, irq = _verilator_options()
    assert (build, irq) == (VERILATOR_OPTIONS, IRQ_OPTIONS), f"{RETURN_CONDITION}\nverilator options: {build} {irq}"


def test_the_guard_sees_each_kind_of_addition(tmp_path):
    """The readers above, on copies of the harness with one addition each: every one shows up."""
    def read(reader, name: str, old: str, new: str) -> set[str]:
        text = (HARNESS / name).read_text(encoding="utf-8")
        assert old in text
        path = tmp_path / name
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return reader(path)

    member = read(header_declarations, "nirmaan_hal.h", "} nirmaan_hal;",
                  "    uint64_t (*cycles)(void *ctx);\n} nirmaan_hal;")
    assert "struct nirmaan_hal: uint64_t (*cycles)(void *ctx)" in member
    widened = read(header_declarations, "nirmaan_hal.h", "uint32_t *value);", "uint32_t *value, uint32_t *cycles);")
    assert "struct nirmaan_hal: unsigned (*read32)(void *ctx, uint32_t offset, uint32_t *value)" not in widened
    exported = read(external_definitions, "axil_manager.cpp", "int main(",
                    'extern "C" unsigned long nirmaan_cycles(void) { return g_cycles; }\n\nint main(')
    assert 'extern "C" unsigned long nirmaan_cycles(void)' in exported
    named = read(external_definitions, "axil_manager.cpp", "}  // namespace",
                 "}  // namespace\n\nnamespace nirmaan { unsigned long cycles = 0; }")
    assert "namespace nirmaan" in named
    declared = read(header_declarations, "nirmaan_irq.h", "unsigned nirmaan_irq_count(void);",
                    "unsigned nirmaan_irq_count(void);\nunsigned long nirmaan_cycles(void);")
    assert "unsigned long nirmaan_cycles(void)" in declared


# --- The simulator's runtime (tools; CI only) ------------------------------------------------------------------


def _probe(rtl: Path):
    chosen, why = select_backend("fw.test", {})
    assert chosen, why
    return execute(chosen, {"sources": str(PROBE), "rtl": str(rtl), "top": "axi4_lite_regs"})


@needs("cc", "verilator", "make")
def test_a_driver_tests_c_reaches_the_simulators_clock():
    """The answer to the addendum's open question (fact 6): yes. Through a mangled C++ symbol of Verilator's
    runtime a test's C reads the simulation time, and so times a read32: one cycle more on the RTL that answers
    after 2 than on the reference. Neither a HAL call nor the driver interface; the open security question."""
    timed = {}
    for rtl in (RTL / "axi4_lite_regs.v", RTL / "variants" / "axi4_lite_regs_lat2.v"):
        run = _probe(rtl)
        log = Path(run.references[0]).read_text(encoding="utf-8", errors="replace") if run.references else ""
        m = re.search(r"^REACH-PROBE read32 (\d+) cycles, write32 (\d+) cycles$", log, re.M)
        print(f"\nREACH-PROBE {rtl.name}: {run.summary}; {m.group(0) if m else 'no timing line'}")
        assert run.succeeded and m, f"{RETURN_CONDITION}\n{rtl.name}: {run.summary}"
        timed[rtl.name] = (int(m[1]), int(m[2]))
    ref, lat2 = timed["axi4_lite_regs.v"], timed["axi4_lite_regs_lat2.v"]
    assert lat2[0] > ref[0] and lat2[1] > ref[1], timed

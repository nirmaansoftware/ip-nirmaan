"""The register map as data (M30): validated, lowered, and turned into a test the RTL must pass.

``validate`` lists every problem with a map. ``lower`` turns a map into text
through a registry of lowerings (``c-header`` and ``markdown`` ship). And
``c_test`` generates a driver-level test, for the AXI4-Lite co-simulation
harness (``nirmaan_hal.h``), that checks the RTL against the map: reset values,
every writable register (all written before any is read, so aliasing shows),
read-only registers ignoring writes, byte strobes, and the response to unmapped
addresses. The checks run in that order, and the first failure names its check.

M41 adds bit fields (docs/REGISTER_MAP_ADOPTION.md): validated for names,
widths, and overlaps; lowered to field macros and ``_GET``/``_SET`` accessors;
and checked by the generated test, which works over four masks per register
(``rw``, ``ro``, ``w1c``, ``wo``), so a register with fields and one without
share every check, and read-only and write-1-to-clear bits get their own.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from nirmaan.models import Access, BitField, Register, RegisterMap, Unmapped

_C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RESPONSE = {Unmapped.OKAY: "NIRMAAN_BUS_OKAY", Unmapped.SLVERR: "NIRMAAN_BUS_SLVERR",
             Unmapped.DECERR: "NIRMAAN_BUS_DECERR"}
_ACCESS_TEXT = {Access.RW: "read/write", Access.RO: "read-only", Access.WO: "write-only",
                Access.W1C: "write-1-to-clear"}


def load_map(path: Path | str) -> RegisterMap:
    return RegisterMap.model_validate_json(Path(path).read_text(encoding="utf-8"))


def validate(regmap: RegisterMap) -> list[str]:
    """Every problem with the map; empty means it can be lowered and checked."""
    problems: list[str] = []
    if regmap.data_width != 32:
        problems.append(f"data width {regmap.data_width}: only 32-bit registers are supported")
    if not regmap.registers:
        problems.append("the map has no registers")
    if not _C_IDENTIFIER.match(regmap.block):
        problems.append(f"block {regmap.block!r} is not a C identifier")
    word, space = regmap.data_width // 8, 1 << regmap.addr_width
    seen_names: set[str] = set()
    seen_offsets: dict[int, str] = {}
    for reg in regmap.registers:
        if not _C_IDENTIFIER.match(reg.name):
            problems.append(f"register {reg.name!r} is not a C identifier")
        if reg.name in seen_names:
            problems.append(f"register {reg.name} appears twice")
        seen_names.add(reg.name)
        if word and reg.offset % word:
            problems.append(f"{reg.name} at {reg.offset:#x} is not aligned to {word} bytes")
        if reg.offset >= space:
            problems.append(f"{reg.name} at {reg.offset:#x} is outside the {regmap.addr_width}-bit address space")
        if reg.offset in seen_offsets:
            problems.append(f"{reg.name} and {seen_offsets[reg.offset]} share offset {reg.offset:#x}")
        seen_offsets.setdefault(reg.offset, reg.name)
        if reg.reset >= 1 << regmap.data_width:
            problems.append(f"{reg.name} reset {reg.reset:#x} is wider than {regmap.data_width} bits")
        problems += _field_problems(reg, regmap.data_width)
    return problems


def _field_problems(reg: Register, width: int) -> list[str]:
    """What is wrong with a register's bit fields (M41)."""
    if not reg.fields:
        return []
    problems: list[str] = []
    names: set[str] = set()
    owner: dict[int, str] = {}
    for f in reg.fields:
        where = f"{reg.name}.{f.name}"
        if not _C_IDENTIFIER.match(f.name):
            problems.append(f"field {where!r} is not a C identifier")
        if f.name in names:
            problems.append(f"field {where} appears twice")
        names.add(f.name)
        if f.high < f.lsb:
            problems.append(f"{where}: msb {f.high} is below lsb {f.lsb}")
            continue
        if f.high >= width:
            problems.append(f"{where} [{f.high}:{f.lsb}] is beyond the {width}-bit register")
        if f.reset >= 1 << f.width:
            problems.append(f"{where} reset {f.reset:#x} is wider than its {f.width} bits")
        shared = [bit for bit in range(f.lsb, f.high + 1) if bit in owner]
        if shared:
            problems.append(f"{where} and {reg.name}.{owner[shared[0]]} overlap at bit {shared[0]}")
        for bit in range(f.lsb, f.high + 1):
            owner.setdefault(bit, f.name)
    composed = sum((f.reset << f.lsb) & f.mask for f in reg.fields if f.high >= f.lsb)
    if reg.reset != composed:
        problems.append(f"{reg.name} reset {reg.reset:#x} disagrees with its fields ({composed:#x})")
    if reg.access is not Access.RW:
        problems.append(f"{reg.name} has fields, so its access comes from its fields: leave it out or write rw, "
                        f"not {reg.access.value}")
    return problems


# --- Lowerings ------------------------------------------------------------------------------

Lowering = Callable[[RegisterMap], str]
_LOWERINGS: dict[str, Lowering] = {}


def register_lowering(name: str) -> Callable[[Lowering], Lowering]:
    def _register(fn: Lowering) -> Lowering:
        if name in _LOWERINGS and _LOWERINGS[name] is not fn:
            raise ValueError(f"Lowering {name!r} is already registered")
        _LOWERINGS[name] = fn
        return fn

    return _register


def unregister_lowering(name: str) -> None:
    _LOWERINGS.pop(name, None)


def lowerings() -> list[str]:
    return sorted(_LOWERINGS)


def lower(regmap: RegisterMap, name: str) -> str:
    """The map as ``name`` (a registered lowering). A map with problems is refused."""
    problems = validate(regmap)
    if problems:
        raise ValueError(f"the register map has problems: {'; '.join(problems)}")
    try:
        return _LOWERINGS[name](regmap)
    except KeyError:
        raise KeyError(f"Unknown lowering {name!r}. Registered: {', '.join(lowerings())}") from None


def _hex(value: int, width: int) -> str:
    return f"0x{value:0{width // 4}X}"


@register_lowering("c-header")
def c_header(regmap: RegisterMap) -> str:
    prefix = regmap.block.upper()
    guard = f"{prefix}_MAP_H"
    lines = [f"/* {regmap.block}: register map, generated from its register map by IP Nirmaan. Do not edit. */",
             f"/* Bus {regmap.bus}; {regmap.data_width}-bit registers; unmapped addresses answer "
             f"{regmap.unmapped.value.upper()}. */",
             f"#ifndef {guard}", f"#define {guard}", "",
             f"#define {prefix}_COUNT {len(regmap.registers)}u", ""]
    for reg in regmap.registers:
        lines += [f"/* {reg.name}: {_ACCESS_TEXT[reg.access]}{'; ' + reg.description if reg.description else ''} */",
                  f"#define {prefix}_{reg.name}_OFFSET 0x{reg.offset:X}u",
                  f"#define {prefix}_{reg.name}_RESET {_hex(reg.reset, regmap.data_width)}u"]
        for f in reg.fields:
            lines += _field_macros(f"{prefix}_{reg.name}_{f.name}", reg, f, regmap.data_width)
    return "\n".join([*lines, "", f"#endif /* {guard} */", ""])


def _bits(f: BitField) -> str:
    return f"[{f.high}:{f.lsb}]" if f.width > 1 else f"[{f.lsb}]"


def _field_macros(name: str, reg: Register, f: BitField, width: int) -> list[str]:
    """A field's shift, mask (in place), reset (its own value), and accessors (M41)."""
    return [f"/* {reg.name}.{f.name} {_bits(f)}: {_ACCESS_TEXT[f.access]}"
            f"{'; ' + f.description if f.description else ''} */",
            f"#define {name}_SHIFT {f.lsb}u",
            f"#define {name}_MASK {_hex(f.mask, width)}u",
            f"#define {name}_RESET 0x{f.reset:X}u",
            f"#define {name}_GET(reg) (((reg) & {name}_MASK) >> {name}_SHIFT)",
            f"#define {name}_SET(reg, value) (((reg) & ~{name}_MASK) | (((0u + (value)) << {name}_SHIFT) & {name}_MASK))"]


@register_lowering("markdown")
def markdown(regmap: RegisterMap) -> str:
    rows = [f"| `0x{reg.offset:X}` | `{reg.name}` | {_ACCESS_TEXT[reg.access]} | "
            f"`{_hex(reg.reset, regmap.data_width)}` |" for reg in regmap.registers]
    lines = ["| Offset | Name | Access | Reset value |", "|---|---|---|---|", *rows]
    fields = [f"| `{reg.name}` | `{f.name}` | `{_bits(f)}` | {_ACCESS_TEXT[f.access]} | `0x{f.reset:X}` |"
              for reg in regmap.registers for f in reg.fields]
    if fields:  # M41: a map with no fields lowers exactly as in M30
        lines += ["", "| Register | Field | Bits | Access | Reset value |", "|---|---|---|---|---|", *fields]
    return "\n".join([*lines, ""])


# --- The generated test ---------------------------------------------------------------------


def _unmapped_offsets(regmap: RegisterMap) -> list[int]:
    """Addresses no register holds: one misaligned, and the first free aligned word, when there is one."""
    word, space = regmap.data_width // 8, 1 << regmap.addr_width
    mapped = {r.offset for r in regmap.registers}
    found = [regmap.registers[0].offset + 1] if word > 1 and regmap.registers[0].offset + 1 < space else []
    free = next((o for o in range(0, space, word) if o not in mapped), None)
    return found + ([free] if free is not None else [])


def _pattern(index: int) -> int:
    return (0xA5A5A5A5 ^ (index * 0x01234567) ^ (index << 28)) & 0xFFFFFFFF


_FULL = 0xFFFFFFFF


def masks(reg: Register) -> dict[Access, int]:
    """Which bits of the register have each access (M41). Reserved bits are in none."""
    found = {a: 0 for a in Access}
    if not reg.fields:
        found[reg.access] = _FULL
    for f in reg.fields:
        found[f.access] |= f.mask
    return found


def c_test(regmap: RegisterMap) -> str:
    """A ``nirmaan_fw_test`` that checks the RTL against the map, through ``nirmaan_hal.h``."""
    problems = validate(regmap)
    if problems:
        raise ValueError(f"the register map has problems: {'; '.join(problems)}")
    regs: list[Register] = list(regmap.registers)
    rows = []
    for i, r in enumerate(regs):
        m = masks(r)
        rows.append(f'    {{"{r.name}", 0x{r.offset:X}u, 0x{r.reset:08X}u, 0x{_pattern(i):08X}u, '
                    f"0x{m[Access.RW]:08X}u, 0x{m[Access.RO]:08X}u, 0x{m[Access.W1C]:08X}u, 0x{m[Access.WO]:08X}u}}")
    table = ",\n".join(rows)
    fields = "".join(f'    {{{i}u, "{f.name}", 0x{f.mask:08X}u}},\n' for i, r in enumerate(regs) for f in r.fields)
    unmapped = _unmapped_offsets(regmap)
    unmapped_table = ", ".join(f"0x{o:X}u" for o in unmapped) or "0u"
    return f"""/* Generated by IP Nirmaan from the register map of {regmap.block}. Do not edit. */
#include <stdint.h>
#include <stdio.h>

#include "nirmaan_hal.h"

/* Each register's bits by access; bits in no mask are reserved: they read zero and ignore writes. */
typedef struct {{
    const char *name; uint32_t offset; uint32_t reset; uint32_t pattern;
    uint32_t rw; uint32_t ro; uint32_t w1c; uint32_t wo;
}} reg_t;
typedef struct {{ unsigned reg; const char *name; uint32_t mask; }} field_t;

static const reg_t regs[] = {{
{table}
}};
#define COUNT (sizeof regs / sizeof regs[0])
static const field_t fields[] = {{
{fields}    {{0u, NULL, 0u}}
}};
static const uint32_t unmapped[] = {{{unmapped_table}}};
#define UNMAPPED_COUNT {len(unmapped)}u
static char detail[240];

static void check(const char *name, int ok) {{ nirmaan_test_result(name, ok, ok ? NULL : detail); }}

static uint32_t readable(unsigned i) {{ return ~regs[i].wo; }}

/* Where in register i the bits of diff are: its first field that holds one, or its reserved bits. */
static const char *where(unsigned i, uint32_t diff) {{
    unsigned f;
    for (f = 0; fields[f].name; ++f)
        if (fields[f].reg == i && (fields[f].mask & diff)) return fields[f].name;
    return (regs[i].rw | regs[i].ro | regs[i].w1c | regs[i].wo) & diff ? NULL : "reserved bits";
}}

static int read_is(const nirmaan_hal *hal, unsigned i, uint32_t expected, const char *when) {{
    uint32_t value = 0u, mask = readable(i);
    unsigned resp = hal->read32(hal->ctx, regs[i].offset, &value);
    const char *part;
    if (resp == NIRMAAN_BUS_OKAY && (value & mask) == (expected & mask)) return 1;
    part = where(i, (value ^ expected) & mask);
    snprintf(detail, sizeof detail, "%s%s%s %s: read 0x%08lx with response %u, expected 0x%08lx with OKAY",
             regs[i].name, part ? "." : "", part ? part : "", when, (unsigned long)value, resp,
             (unsigned long)(expected & mask));
    return 0;
}}

static uint32_t read_now(const nirmaan_hal *hal, unsigned i) {{
    uint32_t value = 0u;
    (void)hal->read32(hal->ctx, regs[i].offset, &value);
    return value;
}}

static void reset_values(const nirmaan_hal *hal) {{
    unsigned i;
    int ok = 1;
    for (i = 0; i < COUNT && ok; ++i)
        if (readable(i)) ok = read_is(hal, i, regs[i].reset, "after reset");
    check("reset_values", ok);
}}

static void write_then_read(const nirmaan_hal *hal) {{
    unsigned i;
    int ok = 1;
    for (i = 0; i < COUNT && ok; ++i) {{
        if (!(regs[i].rw | regs[i].wo)) continue;
        unsigned resp = hal->write32(hal->ctx, regs[i].offset, regs[i].pattern & ~regs[i].w1c, 0xFu);
        if (resp != NIRMAAN_BUS_OKAY) {{
            snprintf(detail, sizeof detail, "%s write answered %u, expected OKAY", regs[i].name, resp);
            ok = 0;
        }}
    }}
    for (i = 0; i < COUNT && ok; ++i)
        if (regs[i].rw)
            ok = read_is(hal, i, (regs[i].pattern & regs[i].rw) | (regs[i].reset & (regs[i].ro | regs[i].w1c)),
                         "after every register was written");
    check("write_then_read_every_register", ok);
}}

static void read_only_ignores_writes(const nirmaan_hal *hal) {{
    unsigned i;
    int any = 0, ok = 1;
    for (i = 0; i < COUNT && ok; ++i) {{
        uint32_t before;
        if (!regs[i].ro) continue;
        any = 1;
        before = read_now(hal, i);
        (void)hal->write32(hal->ctx, regs[i].offset, (before & regs[i].rw) | (~regs[i].reset & regs[i].ro), 0xFu);
        ok = read_is(hal, i, (before & (regs[i].rw | regs[i].w1c)) | (regs[i].reset & regs[i].ro), "after a write");
    }}
    if (any) check("read_only_ignores_writes", ok);
}}

static void write_one_to_clear(const nirmaan_hal *hal) {{
    unsigned i;
    int any = 0, ok = 1;
    for (i = 0; i < COUNT && ok; ++i) {{
        uint32_t before;
        if (!regs[i].w1c) continue;
        any = 1;
        before = read_now(hal, i);
        (void)hal->write32(hal->ctx, regs[i].offset, before & regs[i].rw, 0xFu);
        ok = read_is(hal, i, before & (regs[i].rw | regs[i].ro | regs[i].w1c), "after writing 0 to its w1c bits");
        if (!ok) break;
        (void)hal->write32(hal->ctx, regs[i].offset, (before & regs[i].rw) | regs[i].w1c, 0xFu);
        ok = read_is(hal, i, before & (regs[i].rw | regs[i].ro), "after writing 1 to its w1c bits");
    }}
    if (any) check("write_one_to_clear", ok);
}}

static void byte_strobes(const nirmaan_hal *hal) {{
    unsigned i;
    for (i = 0; i < COUNT; ++i) {{
        if (regs[i].rw != 0xFFFFFFFFu) continue;
        (void)hal->write32(hal->ctx, regs[i].offset, 0x00000000u, 0xFu);
        (void)hal->write32(hal->ctx, regs[i].offset, 0xFFFFFFFFu, 0x5u);
        check("byte_strobes", read_is(hal, i, 0x00FF00FFu, "after a write with strobe 0101"));
        return;
    }}
}}

static void unmapped_response(const nirmaan_hal *hal) {{
    unsigned i, j;
    int ok = 1;
    uint32_t before[COUNT];
    for (j = 0; j < COUNT; ++j) before[j] = read_now(hal, j);
    for (i = 0; i < UNMAPPED_COUNT && ok; ++i) {{
        uint32_t value = 0u;
        unsigned w = hal->write32(hal->ctx, unmapped[i], 0xDEADBEEFu, 0xFu);
        unsigned r = hal->read32(hal->ctx, unmapped[i], &value);
        if (w != {_RESPONSE[regmap.unmapped]} || r != {_RESPONSE[regmap.unmapped]}) {{
            snprintf(detail, sizeof detail, "offset 0x%lx: write answered %u, read answered %u, expected %u",
                     (unsigned long)unmapped[i], w, r, (unsigned){_RESPONSE[regmap.unmapped]});
            ok = 0;
        }}
        for (j = 0; j < COUNT && ok; ++j)
            if (regs[j].rw) ok = read_is(hal, j, before[j], "after an unmapped write");
    }}
    if (UNMAPPED_COUNT) check("unmapped_response", ok);
}}

void nirmaan_fw_test(const nirmaan_hal *hal) {{
    reset_values(hal);
    write_then_read(hal);
    write_one_to_clear(hal);
    read_only_ignores_writes(hal);
    byte_strobes(hal);
    unmapped_response(hal);
}}
"""


def map_summary(regmap: RegisterMap) -> str:
    return (f"{regmap.block}: {len(regmap.registers)} registers on {regmap.bus}, "
            f"{regmap.data_width}-bit, unmapped answers {regmap.unmapped.value.upper()}")


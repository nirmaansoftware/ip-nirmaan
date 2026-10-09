"""The register map as data (M30): validated, lowered, and turned into a test the RTL must pass.

``validate`` lists every problem with a map. ``lower`` turns a map into text
through a registry of lowerings (``c-header`` and ``markdown`` ship). And
``c_test`` generates a driver-level test, for the AXI4-Lite co-simulation
harness (``nirmaan_hal.h``), that checks the RTL against the map: reset values,
every writable register (all written before any is read, so aliasing shows),
read-only registers ignoring writes, byte strobes, and the response to unmapped
addresses. The checks run in that order, and the first failure names its check.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from nirmaan.models import Access, Register, RegisterMap, Unmapped

_C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RESPONSE = {Unmapped.OKAY: "NIRMAAN_BUS_OKAY", Unmapped.SLVERR: "NIRMAAN_BUS_SLVERR",
             Unmapped.DECERR: "NIRMAAN_BUS_DECERR"}
_ACCESS_TEXT = {Access.RW: "read/write", Access.RO: "read-only", Access.WO: "write-only"}


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
    return "\n".join([*lines, "", f"#endif /* {guard} */", ""])


@register_lowering("markdown")
def markdown(regmap: RegisterMap) -> str:
    rows = [f"| `0x{reg.offset:X}` | `{reg.name}` | {_ACCESS_TEXT[reg.access]} | "
            f"`{_hex(reg.reset, regmap.data_width)}` |" for reg in regmap.registers]
    return "\n".join(["| Offset | Name | Access | Reset value |", "|---|---|---|---|", *rows, ""])


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


def c_test(regmap: RegisterMap) -> str:
    """A ``nirmaan_fw_test`` that checks the RTL against the map, through ``nirmaan_hal.h``."""
    problems = validate(regmap)
    if problems:
        raise ValueError(f"the register map has problems: {'; '.join(problems)}")
    regs: list[Register] = list(regmap.registers)
    table = ",\n".join(f'    {{"{r.name}", 0x{r.offset:X}u, {list(Access).index(r.access)}, 0x{r.reset:08X}u, '
                       f"0x{_pattern(i):08X}u}}" for i, r in enumerate(regs))
    unmapped = _unmapped_offsets(regmap)
    unmapped_table = ", ".join(f"0x{o:X}u" for o in unmapped) or "0u"
    return f"""/* Generated by IP Nirmaan from the register map of {regmap.block}. Do not edit. */
#include <stdint.h>
#include <stdio.h>

#include "nirmaan_hal.h"

#define RW 0
#define RO 1
#define WO 2

typedef struct {{ const char *name; uint32_t offset; int access; uint32_t reset; uint32_t pattern; }} reg_t;

static const reg_t regs[] = {{
{table}
}};
#define COUNT (sizeof regs / sizeof regs[0])
static const uint32_t unmapped[] = {{{unmapped_table}}};
#define UNMAPPED_COUNT {len(unmapped)}u
static char detail[200];

static void check(const char *name, int ok) {{ nirmaan_test_result(name, ok, ok ? NULL : detail); }}

static int read_is(const nirmaan_hal *hal, const reg_t *r, uint32_t expected, const char *when) {{
    uint32_t value = 0u;
    unsigned resp = hal->read32(hal->ctx, r->offset, &value);
    if (resp == NIRMAAN_BUS_OKAY && value == expected) return 1;
    snprintf(detail, sizeof detail, "%s %s: read 0x%08lx with response %u, expected 0x%08lx with OKAY",
             r->name, when, (unsigned long)value, resp, (unsigned long)expected);
    return 0;
}}

static void reset_values(const nirmaan_hal *hal) {{
    unsigned i;
    int ok = 1;
    for (i = 0; i < COUNT && ok; ++i)
        if (regs[i].access != WO) ok = read_is(hal, &regs[i], regs[i].reset, "after reset");
    check("reset_values", ok);
}}

static void write_then_read(const nirmaan_hal *hal) {{
    unsigned i;
    int ok = 1;
    for (i = 0; i < COUNT && ok; ++i) {{
        if (regs[i].access == RO) continue;
        unsigned resp = hal->write32(hal->ctx, regs[i].offset, regs[i].pattern, 0xFu);
        if (resp != NIRMAAN_BUS_OKAY) {{
            snprintf(detail, sizeof detail, "%s write answered %u, expected OKAY", regs[i].name, resp);
            ok = 0;
        }}
    }}
    for (i = 0; i < COUNT && ok; ++i)
        if (regs[i].access == RW) ok = read_is(hal, &regs[i], regs[i].pattern, "after every register was written");
    check("write_then_read_every_register", ok);
}}

static void read_only_ignores_writes(const nirmaan_hal *hal) {{
    unsigned i;
    int any = 0, ok = 1;
    for (i = 0; i < COUNT && ok; ++i) {{
        if (regs[i].access != RO) continue;
        any = 1;
        (void)hal->write32(hal->ctx, regs[i].offset, ~regs[i].reset, 0xFu);
        ok = read_is(hal, &regs[i], regs[i].reset, "after a write");
    }}
    if (any) check("read_only_ignores_writes", ok);
}}

static void byte_strobes(const nirmaan_hal *hal) {{
    unsigned i;
    for (i = 0; i < COUNT; ++i) {{
        if (regs[i].access != RW) continue;
        (void)hal->write32(hal->ctx, regs[i].offset, 0x00000000u, 0xFu);
        (void)hal->write32(hal->ctx, regs[i].offset, 0xFFFFFFFFu, 0x5u);
        check("byte_strobes", read_is(hal, &regs[i], 0x00FF00FFu, "after a write with strobe 0101"));
        return;
    }}
}}

static void unmapped_response(const nirmaan_hal *hal) {{
    unsigned i, j;
    int ok = 1;
    uint32_t before[COUNT];
    for (j = 0; j < COUNT; ++j) {{ before[j] = 0u; (void)hal->read32(hal->ctx, regs[j].offset, &before[j]); }}
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
            if (regs[j].access == RW) ok = read_is(hal, &regs[j], before[j], "after an unmapped write");
    }}
    if (UNMAPPED_COUNT) check("unmapped_response", ok);
}}

void nirmaan_fw_test(const nirmaan_hal *hal) {{
    reset_values(hal);
    write_then_read(hal);
    read_only_ignores_writes(hal);
    byte_strobes(hal);
    unmapped_response(hal);
}}
"""


def map_summary(regmap: RegisterMap) -> str:
    return (f"{regmap.block}: {len(regmap.registers)} registers on {regmap.bus}, "
            f"{regmap.data_width}-bit, unmapped answers {regmap.unmapped.value.upper()}")


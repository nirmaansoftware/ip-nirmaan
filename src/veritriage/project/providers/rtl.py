"""RTL source provider: modules, instances, and port bundles from Verilog files.

The M11.x provider M15 deferred, added in M24 so that the Design Graph can be
derived from RTL itself. It reads ``.v`` and ``.sv`` files (a file root, or the
files directly inside a directory root) and, under the lossy-by-design law,
emits only normalized structure:

* the modules each file defines (``source_file`` set);
* the modules instantiated inside them (``parent`` set to the instantiating
  module); a module that is only instantiated keeps ``source_file`` empty,
  because its definition is not in these sources;
* interfaces: SystemVerilog ``interface`` declarations, and port bundles, three
  or more ports of one module sharing a name prefix up to their last underscore
  (``s_axil_awaddr``, ``s_axil_wdata``, ... form ``<module>.s_axil``). A bundle
  read from a module's port list and one read from named connections to that
  module (``.s_axil_awaddr(x)``) get the same name, so they converge on one
  Design Graph node.

It is a lexical reader, not an elaborator: comments and strings are stripped
and parentheses balanced, but there is no preprocessor, no generate expansion,
and no parameter evaluation. What it cannot see it leaves out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from veritriage.project.model import DesignModule, Dut, Interface, ProjectModel
from veritriage.project.providers.base import ProjectCapability, ProjectProvider
from veritriage.project.providers.registry import register_project_provider

VERSION = "1"
SUFFIXES = (".v", ".sv")
#: A shared port-name prefix makes a bundle only from this many ports up.
MIN_BUNDLE = 3

_NOISE = re.compile(r'"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*.*?\*/', re.S)
_UNIT = re.compile(r"\b(module|macromodule|interface)\s+(?:(?:automatic|static)\s+)?([A-Za-z_]\w*)(.*?)"
                   r"\bend(?:module|interface)\b", re.S)
_IDENT = re.compile(r"[A-Za-z_]\w*")
_INSTANCE = re.compile(r"([A-Za-z_]\w*)\s*")
_NAMED = re.compile(r"\.\s*([A-Za-z_]\w*)\s*\(")

#: Words that can open a statement shaped like ``word word (``, and are never a module type.
_KEYWORDS = frozenset("""
always always_comb always_ff always_latch and assert assign assume automatic begin bit buf bufif0 bufif1 byte
case casex casez cell chandle class clocking cmos config const constraint context cover covergroup coverpoint
cross deassign default defparam design disable do edge else end endcase endfunction endgenerate endtask enum
event export extends extern final for force foreach forever fork function generate genvar if iff ifnone import
initial inout input int integer interface join join_any join_none local localparam logic longint macromodule
modport module nand negedge nmos nor not notif0 notif1 or output package packed parameter pmos posedge
primitive priority program property protected pull0 pull1 pulldown pullup rand randc randcase real realtime
reg release repeat restrict return rnmos rpmos rtran rtranif0 rtranif1 scalared sequence shortint shortreal
signed small specify specparam static string strong0 strong1 struct super supply0 supply1 table task this
time timeprecision timeunit tran tranif0 tranif1 tri tri0 tri1 triand trior trireg type typedef union unique
unique0 unsigned var vectored virtual void wait wand weak0 weak1 while wire with wor xnor xor
""".split())


def _strip(text: str) -> str:
    """Comments become spaces, strings become empty strings; nothing else moves."""
    return _NOISE.sub(lambda m: '""' if m.group(0).startswith('"') else " ", text)


def _balanced(text: str, start: int) -> int:
    """Index just past the parenthesis group opening at ``start`` (or len(text))."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def _header_end(text: str) -> int:
    """Index of the ``;`` that ends a module header: the first one outside parentheses."""
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ";" and depth == 0:
            return i
    return len(text)


def _split_top(text: str) -> list[str]:
    """Split on commas outside parentheses, brackets, and braces."""
    parts, depth, current = [], 0, []
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _ports(header: str) -> list[str]:
    """Port names from a module header: the last identifier of each list entry."""
    rest = header.lstrip()
    if rest.startswith("#"):
        open_at = rest.find("(")
        rest = rest[_balanced(rest, open_at):] if open_at >= 0 else ""
    rest = rest.lstrip()
    if not rest.startswith("("):
        return []
    body = rest[1:_balanced(rest, 0) - 1]
    names = []
    for entry in _split_top(body):
        entry = re.sub(r"\[[^\]]*\]", " ", entry.split("=")[0])
        idents = [w for w in _IDENT.findall(entry) if w not in _KEYWORDS]
        if idents:
            names.append(idents[-1])
    return names


def _bundles(module: str, ports: list[str]) -> list[Interface]:
    groups: dict[str, list[str]] = {}
    for port in ports:
        if "_" in port.strip("_"):
            groups.setdefault(port.rsplit("_", 1)[0], []).append(port)
    return [Interface(name=f"{module}.{prefix}", signals=tuple(members), module=module)
            for prefix, members in sorted(groups.items()) if len(members) >= MIN_BUNDLE]


@dataclass
class _Parsed:
    defined: dict[str, str] = field(default_factory=dict)  # module -> source file
    parents: dict[str, str] = field(default_factory=dict)  # instantiated module -> first parent
    interfaces: dict[str, Interface] = field(default_factory=dict)


def _instances(parent: str, body: str, parsed: _Parsed) -> None:
    depth = [0] * (len(body) + 1)
    level = 0
    for i, ch in enumerate(body):
        depth[i] = level
        level += 1 if ch == "(" else -1 if ch == ")" else 0
    for match in _INSTANCE.finditer(body):
        start = match.start()
        kind = match.group(1)
        if depth[start] != 0 or kind in _KEYWORDS or (start and (body[start - 1].isalnum() or
                                                                 body[start - 1] in "_$.'`")):
            continue
        pos = match.end()
        if body.startswith("#", pos):
            open_at = body.find("(", pos)
            if open_at < 0:
                continue
            pos = _balanced(body, open_at)
            while pos < len(body) and body[pos].isspace():
                pos += 1
        name = _IDENT.match(body, pos)
        if name is None or name.group(0) in _KEYWORDS:
            continue
        pos = name.end()
        rest = re.match(r"\s*(?:\[[^\]]*\]\s*)*\(", body[pos:])
        if rest is None:
            continue
        open_at = pos + rest.end() - 1
        connections = body[open_at:_balanced(body, open_at)]
        parsed.parents.setdefault(kind, parent)
        for iface in _bundles(kind, _NAMED.findall(connections)):
            parsed.interfaces.setdefault(iface.name, iface)


def parse_rtl(text: str, source_file: str, parsed: _Parsed | None = None) -> _Parsed:
    """Read one file's modules, instances, and interfaces into ``parsed``."""
    parsed = parsed or _Parsed()
    for unit in _UNIT.finditer(_strip(text)):
        keyword, name, rest = unit.groups()
        header_end = _header_end(rest)
        header, body = rest[:header_end], rest[header_end + 1:]
        if keyword == "interface":
            parsed.interfaces.setdefault(name, Interface(name=name))
            continue
        parsed.defined.setdefault(name, source_file)
        for iface in _bundles(name, _ports(header)):
            parsed.interfaces[iface.name] = iface  # a definition's own ports win over connections
        _instances(name, body, parsed)
    return parsed


def rtl_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix in SUFFIXES else []
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix in SUFFIXES)


@register_project_provider
class RtlSourceProvider(ProjectProvider):
    """Verilog and SystemVerilog files: hierarchy and interfaces, read lexically."""

    name = "rtl"
    source = "rtl"
    capabilities = frozenset({ProjectCapability.HIERARCHY, ProjectCapability.INTERFACES})

    @classmethod
    def available(cls, root: Path) -> bool:
        return bool(rtl_files(root))

    def collect(self, root: Path) -> ProjectModel:
        parsed = _Parsed()
        for path in rtl_files(root):
            parse_rtl(path.read_text(encoding="utf-8", errors="replace"), str(path), parsed)
        names = sorted({*parsed.defined, *parsed.parents})
        modules = tuple(
            DesignModule(name=n, source_file=parsed.defined.get(n),
                         parent=parsed.parents.get(n) if parsed.parents.get(n) != n else None)
            for n in names
        )
        interfaces = tuple(parsed.interfaces[k] for k in sorted(parsed.interfaces))
        return ProjectModel(
            source_root=str(root),
            provider_versions={self.name: VERSION},
            dut=Dut(modules=modules, interfaces=interfaces),
        )

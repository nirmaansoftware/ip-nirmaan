"""Mux-D scan over a Yosys netlist: analysis, stitching, and a chain testbench.

Standard library only, because the DFT backends run it as a step between
tool invocations (``python dft_scan.py <command> ...``), next to Yosys and
Icarus, and it must not depend on how Nirmaan is installed. ``dft.py``
imports the same functions to evaluate the testability rules.

Everything here reads what Yosys wrote (``write_json`` of a flattened,
``synth``-ed, ``dffunmap``-ed netlist of internal gate cells). Nothing here
runs a tool or claims that one ran.
"""

from __future__ import annotations

import json
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCAN_EN, SCAN_IN, SCAN_OUT = "scan_en", "scan_in", "scan_out"
SCAN_PORTS = (SCAN_EN, SCAN_IN, SCAN_OUT)
#: The prefix of the scan cell each flop becomes before the techmap expands it.
SCAN_CELL = "$__NIRMAAN_SCAN"

# Plain flops a mux-D scan flop can wrap: $_DFF_P_, and $_DFF_PN0_ (async reset or set).
_FLOP_RE = re.compile(r"^\$_DFF_(?P<clk>[PN])(?:(?P<rst>[PN])(?P<val>[01]))?_$")
_LATCH_RE = re.compile(r"^\$_(DLATCH|DLATCHSR|SR)_")
_SEQUENTIAL_RE = re.compile(r"^\$_(DFF|DFFE|SDFF|SDFFE|SDFFCE|DFFSR|DFFSRE|ALDFF|ALDFFE|DLATCH|DLATCHSR|SR)_")


def _mux(a: int, b: int, s: int) -> int:
    return (a & ~s) | (b & s)


#: Combinational gate cells: their inputs, and the function of their output Y.
GATES = {
    "$_BUF_": ("A", lambda v: v["A"]),
    "$_NOT_": ("A", lambda v: ~v["A"]),
    "$_AND_": ("AB", lambda v: v["A"] & v["B"]),
    "$_NAND_": ("AB", lambda v: ~(v["A"] & v["B"])),
    "$_OR_": ("AB", lambda v: v["A"] | v["B"]),
    "$_NOR_": ("AB", lambda v: ~(v["A"] | v["B"])),
    "$_XOR_": ("AB", lambda v: v["A"] ^ v["B"]),
    "$_XNOR_": ("AB", lambda v: ~(v["A"] ^ v["B"])),
    "$_ANDNOT_": ("AB", lambda v: v["A"] & ~v["B"]),
    "$_ORNOT_": ("AB", lambda v: v["A"] | ~v["B"]),
    "$_MUX_": ("ABS", lambda v: _mux(v["A"], v["B"], v["S"])),
    "$_NMUX_": ("ABS", lambda v: ~_mux(v["A"], v["B"], v["S"])),
    "$_AOI3_": ("ABC", lambda v: ~((v["A"] & v["B"]) | v["C"])),
    "$_OAI3_": ("ABC", lambda v: ~((v["A"] | v["B"]) & v["C"])),
    "$_AOI4_": ("ABCD", lambda v: ~((v["A"] & v["B"]) | (v["C"] & v["D"]))),
    "$_OAI4_": ("ABCD", lambda v: ~((v["A"] | v["B"]) & (v["C"] | v["D"]))),
}


class NetlistError(ValueError):
    """The netlist cannot be analyzed as asked (a loop, an unknown cell, no top module)."""


@dataclass(frozen=True)
class Flop:
    cell: str
    type: str
    name: str  # the net its Q drives, e.g. "count[2]"
    clock: object  # a net bit (int) or a constant ("0", "1", "x")
    d: object
    q: object
    edge: str  # "posedge" or "negedge"
    reset: object = None  # the async reset or set pin's bit, if any
    reset_active: int | None = None  # the level that asserts it
    reset_value: int | None = None


@dataclass
class Design:
    """One flattened module of a Yosys JSON netlist."""

    top: str
    module: dict
    ports: dict[str, dict] = field(default_factory=dict)
    names: dict[object, str] = field(default_factory=dict)
    drivers: dict[object, tuple[str, str]] = field(default_factory=dict)
    flops: list[Flop] = field(default_factory=list)
    others: list[tuple[str, str, str]] = field(default_factory=list)  # (cell, type, name) sequential, not scannable
    latches: list[tuple[str, str, str]] = field(default_factory=list)
    unknown: list[tuple[str, str]] = field(default_factory=list)  # (cell, type) never evaluated

    @classmethod
    def load(cls, path: str | Path, top: str | None = None) -> Design:
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")), top)

    @classmethod
    def from_json(cls, netlist: dict, top: str | None = None) -> Design:
        modules = netlist.get("modules", {})
        if top is None:
            tops = [n for n, m in modules.items() if str(m.get("attributes", {}).get("top", "0")).strip("0")]
            top = tops[0] if len(tops) == 1 else (next(iter(modules)) if len(modules) == 1 else None)
        if top not in modules:
            raise NetlistError(f"no module {top!r} in the netlist")
        design = cls(top, modules[top], dict(modules[top].get("ports", {})))
        design._index()
        return design

    # --- Indexing ------------------------------------------------------------------------

    def _index(self) -> None:
        # Name each bit by its most readable net: public names over $-names, shorter over longer.
        ranked = sorted(self.module.get("netnames", {}).items(),
                        key=lambda kv: (bool(kv[1].get("hide_name")), kv[0].startswith("$"), len(kv[0])))
        for name, net in reversed(ranked):
            bits = net["bits"]
            for i, bit in enumerate(bits):
                if isinstance(bit, int):
                    offset = net.get("offset", 0)
                    self.names[bit] = name if len(bits) == 1 else f"{name}[{i + offset}]"
        for cell, spec in self.module.get("cells", {}).items():
            kind = spec["type"]
            conns = spec.get("connections", {})
            dirs = spec.get("port_directions", {})
            for port, bits in conns.items():
                if dirs.get(port) == "output" or (not dirs and port in ("Y", "Q")):
                    for bit in bits:
                        if isinstance(bit, int):
                            self.drivers[bit] = (cell, port)
            q = conns.get("Q", [None])[0]
            label = self.names.get(q, cell)
            if m := _FLOP_RE.match(kind):
                reset = conns["R"][0] if m["rst"] else None
                self.flops.append(Flop(
                    cell, kind, label, conns["C"][0], conns["D"][0], q,
                    "posedge" if m["clk"] == "P" else "negedge", reset,
                    None if reset is None else int(m["rst"] == "P"),
                    None if reset is None else int(m["val"])))
            elif _LATCH_RE.match(kind):
                self.latches.append((cell, kind, label))
            elif _SEQUENTIAL_RE.match(kind):
                self.others.append((cell, kind, label))
            elif kind not in GATES:
                self.unknown.append((cell, kind))
        self.flops.sort(key=lambda f: _natural(f.name))

    # --- Queries --------------------------------------------------------------------------

    def input_bits(self) -> dict[object, str]:
        """Every module input bit, named ``port`` or ``port[i]``."""
        found = {}
        for name, port in self.ports.items():
            if port["direction"] == "input":
                bits = port["bits"]
                for i, bit in enumerate(bits):
                    found[bit] = name if len(bits) == 1 else f"{name}[{i}]"
        return found

    def port_bits(self, name: str) -> list:
        return list(self.ports.get(name, {}).get("bits", []))

    def has_scan_ports(self) -> bool:
        return all(p in self.ports for p in SCAN_PORTS)

    def describe(self, bit) -> str:
        """Where a bit comes from: a port, a named net, a cell's output, or a constant."""
        if isinstance(bit, str):
            return f"constant {bit}"
        inputs = self.input_bits()
        if bit in inputs:
            return f"input {inputs[bit]}"
        driver = self.drivers.get(bit)
        where = self.names.get(bit, f"net {bit}")
        if driver is None:
            return f"{where} (undriven)"
        return f"{where} (driven by a {self.module['cells'][driver[0]]['type']} cell)"

    def sequential_count(self) -> int:
        return len(self.flops) + len(self.latches) + len(self.others)

    # --- Evaluation -----------------------------------------------------------------------

    def evaluate(self, targets: list, values: dict[object, int], width: int = 1) -> dict[object, int]:
        """The value of each target bit, given values for inputs and flop outputs.

        Values are ``width``-bit words (one simulation per bit position). A bit
        with no value and no combinational driver, and a constant x or z, read 0.
        """
        mask = (1 << width) - 1
        known = dict(values)
        cells = self.module["cells"]
        visiting: set = set()

        def value(bit) -> int:
            if isinstance(bit, str):
                return mask if bit == "1" else 0
            if bit in known:
                return known[bit]
            driver = self.drivers.get(bit)
            if driver is None or cells[driver[0]]["type"] not in GATES:
                known[bit] = 0
                return 0
            cell = cells[driver[0]]
            if bit in visiting:
                raise NetlistError(f"combinational loop through {self.names.get(bit, bit)}")
            visiting.add(bit)
            pins, fn = GATES[cell["type"]]
            result = fn({p: value(cell["connections"][p][0]) for p in pins}) & mask
            visiting.discard(bit)
            known[bit] = result
            return result

        stack_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(stack_limit, 20000))
        try:
            return {t: value(t) for t in targets}
        finally:
            sys.setrecursionlimit(stack_limit)

    def combinational_loops(self) -> list[list[str]]:
        """Strongly connected groups of gate cells (Tarjan), each named by the nets it drives."""
        cells = self.module["cells"]
        gates = [c for c, spec in cells.items() if spec["type"] in GATES]
        edges: dict[str, list[str]] = {c: [] for c in gates}
        for c in gates:
            pins, _ = GATES[cells[c]["type"]]
            for p in pins:
                bit = cells[c]["connections"][p][0]
                driver = self.drivers.get(bit)
                if driver and driver[0] in edges:
                    edges[driver[0]].append(c)
        index: dict[str, int] = {}
        low: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        loops: list[list[str]] = []
        counter = 0
        for root in gates:
            if root in index:
                continue
            work = [(root, iter(edges[root]))]
            index[root] = low[root] = counter
            counter += 1
            stack.append(root)
            on_stack.add(root)
            while work:
                node, children = work[-1]
                advanced = False
                for child in children:
                    if child not in index:
                        index[child] = low[child] = counter
                        counter += 1
                        stack.append(child)
                        on_stack.add(child)
                        work.append((child, iter(edges[child])))
                        advanced = True
                        break
                    if child in on_stack:
                        low[node] = min(low[node], index[child])
                if advanced:
                    continue
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[node])
                if low[node] == index[node]:
                    group = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        group.append(member)
                        if member == node:
                            break
                    if len(group) > 1 or node in edges[node]:
                        loops.append(sorted(self.names.get(cells[m]["connections"]["Y"][0], m) for m in group))
        return loops

    def trace_chain(self, samples: int = 64, seed: int = 1) -> Chain:
        """Follow the chains functionally: with scan_en high, which source does each flop load?

        Every input and flop output gets a random ``samples``-bit word, scan_en
        is held high, and each flop's D is evaluated. A flop is on a chain when
        its D equals exactly the word of a scan_in bit or of one other flop; a
        match by chance has probability 2**-samples. Chain k starts at bit k of
        scan_in and must end at bit k of scan_out, and every flop on it must
        share one clock and edge.
        """
        if not self.has_scan_ports():
            raise NetlistError(f"{self.top} has no {', '.join(SCAN_PORTS)} ports")
        rng = random.Random(seed)
        mask = (1 << samples) - 1
        values: dict[object, int] = {}
        for bit in [*self.input_bits(), *(f.q for f in self.flops)]:
            values[bit] = rng.getrandbits(samples)
        for bit in self.port_bits(SCAN_EN):
            values[bit] = mask
        for f in self.flops:  # async resets held inactive while shifting
            if f.reset is not None and not isinstance(f.reset, str):
                values[f.reset] = mask if f.reset_active == 0 else 0
        scan_ins, scan_outs = self.port_bits(SCAN_IN), self.port_bits(SCAN_OUT)
        single = len(scan_ins) == 1
        port_in = [SCAN_IN if single else f"{SCAN_IN}[{k}]" for k in range(len(scan_ins))]
        port_out = [SCAN_OUT if single else f"{SCAN_OUT}[{k}]" for k in range(len(scan_outs))]
        words = self.evaluate([f.d for f in self.flops] + scan_outs, values, samples)
        sources = {**{values[f.q]: f.name for f in self.flops},
                   **{values[bit]: port_in[k] for k, bit in enumerate(scan_ins) if isinstance(bit, int)}}
        by_name = {f.name: f for f in self.flops}
        loads: dict[str, str | None] = {f.name: sources.get(words[f.d]) for f in self.flops}
        successor: dict[str, list[str]] = {}
        for flop, source in loads.items():
            if source is not None and source != flop:
                successor.setdefault(source, []).append(flop)
        problems: list[str] = []
        if len(scan_ins) != len(scan_outs):
            problems.append(f"{SCAN_IN} has {len(scan_ins)} bits but {SCAN_OUT} has {len(scan_outs)}")
        chains: list[list[str]] = []
        seen: set[str] = set()
        for k, start in enumerate(port_in):
            order: list[str] = []
            current = start
            while current in successor:
                nxt = successor[current]
                if len(nxt) > 1:
                    problems.append(f"{current} feeds {len(nxt)} flops in shift mode: {', '.join(sorted(nxt))}")
                flop = sorted(nxt)[0]
                if flop in order or flop in seen:
                    break
                order.append(flop)
                current = flop
            seen.update(order)
            chains.append(order)
            if k >= len(scan_outs):
                continue
            out_source = sources.get(words[scan_outs[k]])
            tail = order[-1] if order else start
            if not order:
                problems.append(f"{start} reaches no flop in shift mode")
            elif out_source != tail:
                where = "the chain" if single else f"chain {k}"
                problems.append(f"{port_out[k]} is {out_source or 'not a chain element'} in shift mode, not the "
                                f"last flop of {where} ({tail})")
            domains = sorted({f"{by_name[n].edge} {self.describe(by_name[n].clock)}" for n in order})
            if len(domains) > 1:
                problems.append(f"chain {k} mixes clock domains ({'; '.join(domains)}): a chain shifts on one "
                                f"clock and edge")
        order_all = [n for chain in chains for n in chain]
        off = [f.name for f in self.flops if f.name not in seen]
        for name in off:
            source = loads[name]
            why = (f"loads {source}, which is not on the chain" if source
                   else "loads no chain element when scan_en is high (no scan path)")
            problems.append(f"flop {name} is not on the scan chain: it {why}")
        return Chain(order=[by_name[n] for n in order_all], off_chain=off, problems=problems,
                     chains=[[by_name[n] for n in chain] for chain in chains])


@dataclass(frozen=True)
class Chain:
    """The traced chains: ``chains`` one list per scan_in bit, ``order`` all of them in turn."""

    order: list[Flop]
    off_chain: list[str]
    problems: list[str]
    chains: list[list[Flop]] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.problems


def _natural(name: str) -> tuple:
    return tuple(int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name))


# --- Stitching ----------------------------------------------------------------------------


def techmap_file() -> str:
    """The techmap that expands each scan cell into a $_MUX_ in front of the original flop."""
    modules = []
    for clk in "PN":
        for suffix in ("", *(r + v for r in "PN" for v in "01")):
            kind = f"$_DFF_{clk}{suffix}_"
            reset_port = ", R" if suffix else ""
            reset_conn = ", .R(R)" if suffix else ""
            modules.append(
                f"module \\{SCAN_CELL}{kind[1:]} (input C{reset_port}, D, SE, SI, output Q);\n"
                "  wire d;\n"
                "  \\$_MUX_ scan_mux (.A(D), .B(SI), .S(SE), .Y(d));\n"
                f"  \\{kind} _TECHMAP_REPLACE_ (.C(C){reset_conn}, .D(d), .Q(Q));\n"
                "endmodule\n")
    return "// Mux-D scan: generated by nirmaan.integrations.dft_scan.\n" + "\n".join(modules)


def _split(flops: list, pieces: int) -> list[list]:
    """``flops`` cut, in order, into ``pieces`` contiguous runs whose lengths differ by at most one."""
    size, extra = divmod(len(flops), pieces)
    runs, start = [], 0
    for k in range(pieces):
        end = start + size + (1 if k < extra else 0)
        runs.append(flops[start:end])
        start = end
    return runs


def plan_chains(design: Design, chains: int = 1, max_length: int | None = None) -> list[list[Flop]]:
    """The flops of ``design`` cut into balanced chains, never mixing clock domains (clock and edge).

    Each domain gets at least one chain, and with ``max_length`` at least
    ceil(n / max_length); further chains, up to ``chains``, go one at a time to
    the domain whose longest chain is longest. Within a domain flops keep their
    natural name order and chain lengths differ by at most one.
    """
    if chains < 1 or (max_length is not None and max_length < 1):
        raise NetlistError("chains and max_chain_length must be positive integers")
    domains: dict[tuple, list[Flop]] = {}
    for flop in design.flops:
        domains.setdefault((flop.clock, flop.edge), []).append(flop)
    alloc = {d: (-(-len(f) // max_length) if max_length else 1) for d, f in domains.items()}
    total = max(chains, sum(alloc.values()))
    if total > len(design.flops):
        raise NetlistError(f"{total} chains for {len(design.flops)} flops: every chain needs at least one flop")
    order = list(domains)
    while sum(alloc.values()) < total:
        growable = [d for d in order if alloc[d] < len(domains[d])]
        widest = max(growable, key=lambda d: (-(-len(domains[d]) // alloc[d]), -order.index(d)))
        alloc[widest] += 1
    return [run for d in order for run in _split(domains[d], alloc[d])]


def stitch(netlist: dict, top: str, chains: int = 1, max_length: int | None = None) -> tuple[dict, dict]:
    """Turn every flop of ``top`` into a scan cell and stitch balanced chains; return the netlist and report.

    One chain keeps scalar ``scan_in`` and ``scan_out`` ports; N chains make
    them N-bit vectors, chain k running from ``scan_in[k]`` to ``scan_out[k]``.
    Refuses (NetlistError) what mux-D chains cannot honestly cover: no flops,
    latches or other sequential cells, a clock that is not a module input, more
    chains than flops, or ports that already use the scan names.
    """
    design = Design.from_json(netlist, top)
    taken = [p for p in SCAN_PORTS if p in design.ports]
    if taken:
        raise NetlistError(f"{top} already has port(s) {', '.join(taken)}")
    if not design.flops:
        raise NetlistError(f"{top} has no flip-flops to scan")
    left = [f"{kind} {name}" for _, kind, name in design.latches + design.others]
    if left:
        raise NetlistError(f"{len(left)} sequential element(s) cannot take a mux-D scan flop: {', '.join(left)}")
    inputs = design.input_bits()
    stray = sorted({design.describe(f.clock) for f in design.flops if f.clock not in inputs})
    if stray:
        raise NetlistError(f"the clock is not a module input: {'; '.join(stray)}")
    runs = plan_chains(design, chains, max_length)

    module = design.module
    next_bit = 1 + max((b for net in module.get("netnames", {}).values() for b in net["bits"] if isinstance(b, int)),
                       default=1)
    se = next_bit
    si = list(range(next_bit + 1, next_bit + 1 + len(runs)))
    so = [run[-1].q for run in runs]
    module["ports"][SCAN_EN] = {"direction": "input", "bits": [se]}
    module["ports"][SCAN_IN] = {"direction": "input", "bits": si}
    module["ports"][SCAN_OUT] = {"direction": "output", "bits": so}
    for name, bits in ((SCAN_EN, [se]), (SCAN_IN, si), (SCAN_OUT, so)):
        module["netnames"][name] = {"hide_name": 0, "bits": bits, "attributes": {}}

    order, reports = [], []
    for k, run in enumerate(runs):
        previous = si[k]
        for flop in run:
            cell = module["cells"][flop.cell]
            cell["type"] = SCAN_CELL + flop.type[1:]
            cell["connections"]["SE"] = [se]
            cell["connections"]["SI"] = [previous]
            cell.setdefault("port_directions", {}).update(SE="input", SI="input")
            order.append({"position": len(order), "chain": k, "flop": flop.name, "cell": flop.cell,
                          "type": flop.type})
            previous = flop.q
        reports.append({"index": k, "length": len(run), "clock": {"port": inputs[run[0].clock], "edge": run[0].edge},
                        "order": [f.name for f in run]})
    clocks = [dict(t) for t in dict.fromkeys(tuple(r["clock"].items()) for r in reports)]
    report = {
        "top": top,
        "architecture": "mux-D, one chain" if len(runs) == 1 else f"mux-D, {len(runs)} chains",
        "length": max(len(run) for run in runs),
        "flops": len(order),
        "clock": clocks[0] if len(clocks) == 1 else None,
        "clocks": clocks,
        "ports": {"enable": SCAN_EN, "input": SCAN_IN, "output": SCAN_OUT},
        "chains": reports,
        "order": order,
    }
    return netlist, report


# --- The chain testbench ------------------------------------------------------------------


def _ident(name: str) -> str:
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", name) else f"\\{name} "


def _literal(bits: list[int]) -> str:
    """A Verilog literal whose bit i is ``bits[i]``."""
    return f"{len(bits)}'b" + "".join(str(b) for b in reversed(bits))


def clocking(design: Design, flops: list[Flop]) -> tuple[dict[str, int], dict[str, int]]:
    """How a test pulses the clocks: each clock port's idle level, and each flop's capture phase.

    A pulse toggles every clock twice. A clock idles low if any flop uses its
    rising edge, else high; a flop whose active edge is the pulse's first
    toggle captures in phase 0, the others in phase 1, after phase 0.
    Raises NetlistError for a clock that is not a whole, one-bit module input.
    """
    inputs = design.input_bits()
    edges: dict[object, set[str]] = {}
    for f in flops:
        if f.clock not in inputs:
            raise NetlistError(f"the clock is not a module input: {design.describe(f.clock)}")
        edges.setdefault(f.clock, set()).add(f.edge)
    idle: dict[str, int] = {}
    for bit, used in edges.items():
        port = inputs[bit]
        if "[" in port:
            raise NetlistError(f"the clock is one bit of a vector port ({port})")
        idle[port] = 0 if "posedge" in used else 1
    phase = {f.name: int((f.edge == "posedge") != (idle[inputs[f.clock]] == 0)) for f in flops}
    return idle, phase


def next_state(design: Design, flops: list[Flop], values: dict[object, int], phase: dict[str, int]) -> list[int]:
    """What each flop captures on one pulse from ``values``: phase 0 flops first, then phase 1 from their result."""
    first = design.evaluate([f.d for f in flops if phase[f.name] == 0], values)
    after = dict(values)
    for f in flops:
        if phase[f.name] == 0:
            after[f.q] = first[f.d]
    second = design.evaluate([f.d for f in flops if phase[f.name] == 1], after)
    return [first[f.d] if phase[f.name] == 0 else second[f.d] for f in flops]


def _memory(name: str, width: int, rows: list[list[int]]) -> tuple[str, list[str]]:
    """A declaration of a Verilog memory, and the assignments that fill it (bit k of row i is rows[i][k])."""
    decl = f"  reg [{width - 1}:0] {name} [0:{max(len(rows), 1) - 1}];"
    return decl, [f"    {name}[{i}] = {_literal(row)};" for i, row in enumerate(rows)]


def testbench(design: Design, seed: int = 7) -> tuple[str, dict]:
    """A self-checking testbench for the chains of ``design``, and what it expects.

    1. Shift: with scan_en high, 2L known bits go into every chain at once (L
       the longest chain); chain k's bits must come out at scan_out[k] after
       its own length.
    2. Capture: shift in a known state, hold the inputs at known values, give
       one pulse with scan_en low, then shift the captured state out. The
       expected state is the netlist's next-state function, evaluated here in
       the pulse's edge order.

    Raises NetlistError when a chain is not complete: a flop the chains cannot
    load leaves nothing definite to capture.
    """
    chain = design.trace_chain()
    if not chain.complete:
        raise NetlistError("the scan chain is broken: " + "; ".join(chain.problems))
    runs = chain.chains
    flops = chain.order
    if not flops:
        raise NetlistError(f"{design.top} has no flip-flops on a scan chain")
    idle, phase = clocking(design, flops)
    inputs = design.input_bits()
    resets = {f.reset: f.reset_active for f in flops if f.reset is not None and not isinstance(f.reset, str)}
    stray = [design.describe(r) for r in resets if r not in inputs]
    if stray:
        raise NetlistError(f"an async reset is not a module input: {'; '.join(stray)}")

    width = len(runs)
    length = max(len(run) for run in runs)
    rng = random.Random(seed)
    flush = [[rng.getrandbits(1) for _ in range(2 * length)] for _ in runs]
    state = [[rng.getrandbits(1) for _ in run] for run in runs]
    held = {SCAN_EN, SCAN_IN, *idle}
    clock_bits = {b for b, name in inputs.items() if name in idle}
    values: dict[object, int] = {}
    for bit, name in inputs.items():
        if bit in resets:
            values[bit] = 1 - resets[bit]
        elif bit in clock_bits or name in held or name.split("[")[0] in (SCAN_EN, SCAN_IN):
            values[bit] = 0
        else:
            values[bit] = rng.getrandbits(1)
    for bit in design.port_bits(SCAN_EN):
        values[bit] = 0
    for run, bits in zip(runs, state):
        for flop, v in zip(run, bits):
            values[flop.q] = v
    next_bits = next_state(design, flops, values, phase)
    captured, at = [], 0
    for run in runs:
        captured.append(next_bits[at:at + len(run)])
        at += len(run)

    shift_in = [[flush[k][i] for k in range(width)] for i in range(2 * length)]
    shift_mask = [[int(i >= len(runs[k])) for k in range(width)] for i in range(2 * length)]
    shift_exp = [[flush[k][i - len(runs[k])] if i >= len(runs[k]) else 0 for k in range(width)]
                 for i in range(2 * length)]
    load = [[state[k][length - 1 - t] if length - 1 - t < len(runs[k]) else 0 for k in range(width)]
            for t in range(length)]
    unload_mask = [[int(t < len(runs[k])) for k in range(width)] for t in range(length)]
    unload_exp = [[captured[k][len(runs[k]) - 1 - t] if t < len(runs[k]) else 0 for k in range(width)]
                  for t in range(length)]
    memories = [_memory(name, width, rows) for name, rows in (
        ("shift_in", shift_in), ("shift_mask", shift_mask), ("shift_exp", shift_exp), ("load", load),
        ("unload_mask", unload_mask), ("unload_exp", unload_exp))]

    decls, conns, drives = [], [], []
    for name, port in design.ports.items():
        bits = len(port["bits"])
        vec = f"[{bits - 1}:0] " if bits > 1 else ""
        ident = _ident(name)
        kind = "reg" if port["direction"] == "input" else "wire"
        decls.append(f"  {kind} {vec}{ident};")
        conns.append(f"    .{ident}({ident})")
        if port["direction"] == "input" and name not in held:
            drives.append(f"    {ident} = {_literal([values.get(b, 0) for b in port['bits']])};")
    clocks = [_ident(c) for c in idle]
    toggle = " ".join(f"{c} = ~{c};" for c in clocks)
    idles = "\n".join(f"    {_ident(c)} = 1'b{v};" for c, v in idle.items())
    count = len(flops)
    summary = (f"DFT-SCAN: chain length {length}, " if width == 1
               else f"DFT-SCAN: {width} chains, {count} flops, chain length {length}, ")
    edges = "; ".join(sorted({f"{f.edge} {inputs[f.clock]}" for f in flops}))
    text = f"""`timescale 1ns / 1ps
// Scan chain test for {design.top}: generated by nirmaan.integrations.dft_scan.
// {width} chain(s), {count} flops, longest {length} ({edges}); shift {2 * length} bits, then one capture.
module nirmaan_scan_tb;
{chr(10).join(decls)}
{chr(10).join(m[0] for m in memories)}
  wire [{width - 1}:0] chain_out = {SCAN_OUT};
  integer i, k, shift_errors, capture_errors;

  {_ident(design.top)} dut (
{("," + chr(10)).join(conns)}
  );

  task pulse;
    begin
      #5 {toggle}
      #5 {toggle}
    end
  endtask

  initial begin
    shift_errors = 0;
    capture_errors = 0;
{chr(10).join(line for m in memories for line in m[1])}
{idles}
{chr(10).join(drives)}
    {SCAN_EN} = 1'b1;
    {SCAN_IN} = {width}'b0;
    // 1. Shift: bit i goes in at cycle i and is at chain k's scan_out before the edge of cycle i + its length.
    for (i = 0; i < {2 * length}; i = i + 1) begin
      {SCAN_IN} = shift_in[i];
      #4;
      for (k = 0; k < {width}; k = k + 1)
        if (shift_mask[i][k] && chain_out[k] !== shift_exp[i][k]) begin
          $error("shift: cycle %0d chain %0d scan_out=%b, expected %b", i, k, chain_out[k], shift_exp[i][k]);
          shift_errors = shift_errors + 1;
        end
      pulse;
    end
    // 2. Capture: load the state, one functional pulse, unload.
    for (i = 0; i < {length}; i = i + 1) begin
      {SCAN_IN} = load[i];
      #4;
      pulse;
    end
    {SCAN_EN} = 1'b0;
    #4;
    pulse;
    {SCAN_EN} = 1'b1;
    for (i = 0; i < {length}; i = i + 1) begin
      #4;
      for (k = 0; k < {width}; k = k + 1)
        if (unload_mask[i][k] && chain_out[k] !== unload_exp[i][k]) begin
          $error("capture: chain %0d unload cycle %0d captured %b, expected %b", k, i, chain_out[k],
                 unload_exp[i][k]);
          capture_errors = capture_errors + 1;
        end
      pulse;
    end
    $display("{summary}shift errors %0d, capture errors %0d", shift_errors, capture_errors);
    $finish;
  end
endmodule
"""
    expect = {"top": design.top, "length": length, "flops": count,
              "clock": ({"port": inputs[flops[0].clock], "edge": flops[0].edge} if len(idle) == 1
                        and len({f.edge for f in flops}) == 1 else None),
              "chains": [{"length": len(run), "order": [f.name for f in run]} for run in runs],
              "order": [f.name for f in flops], "flush": flush, "state": state, "captured": captured}
    return text, expect


# --- Command line: the steps the DFT backends run -------------------------------------------


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["stitch"] and len(argv) in (5, 7):
            _, prep, out, report, top = argv[:5]
            chains, max_length = (int(argv[5]), int(argv[6]) or None) if len(argv) == 7 else (1, None)
            netlist, chain = stitch(json.loads(Path(prep).read_text(encoding="utf-8")), top, chains, max_length)
            Path(out).write_text(json.dumps(netlist), encoding="utf-8")
            Path(report).write_text(json.dumps(chain, indent=2) + "\n", encoding="utf-8")
            lengths = ", ".join(str(c["length"]) for c in chain["chains"])
            print(f"DFT-STITCH: {chain['flops']} flops on {len(chain['chains'])} chain(s) of length {lengths}")
            return 0
        if argv[:1] == ["testbench"] and len(argv) == 5:
            _, design_json, tb, expect, top = argv
            text, expected = testbench(Design.load(design_json, top))
            Path(tb).write_text(text, encoding="utf-8")
            Path(expect).write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
            print(f"DFT-TESTBENCH: {len(expected['chains'])} chain(s), longest {expected['length']}, order "
                  f"{', '.join(expected['order'][:8])}{', ...' if expected['flops'] > 8 else ''}")
            return 0
    except (NetlistError, OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"DFT-ERROR: {exc}")
        return 1
    print("usage: dft_scan.py stitch PREP.json OUT.json CHAIN.json TOP [CHAINS MAX_LENGTH] | "
          "testbench DESIGN.json TB.v EXPECT.json TOP")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

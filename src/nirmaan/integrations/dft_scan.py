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
        """Follow the chain functionally: with scan_en high, which source does each flop load?

        Every input and flop output gets a random ``samples``-bit word, scan_en
        is held high, and each flop's D is evaluated. A flop is on the chain
        when its D equals exactly the word of scan_in or of one other flop; a
        match by chance has probability 2**-samples.
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
        scan_in = self.port_bits(SCAN_IN)[0]
        scan_out = self.port_bits(SCAN_OUT)[0]
        words = self.evaluate([f.d for f in self.flops] + [scan_out], values, samples)
        sources = {values[scan_in]: SCAN_IN, **{values[f.q]: f.name for f in self.flops}}
        by_name = {f.name: f for f in self.flops}
        loads: dict[str, str | None] = {f.name: sources.get(words[f.d]) for f in self.flops}
        successor: dict[str, list[str]] = {}
        for flop, source in loads.items():
            if source is not None and source != flop:
                successor.setdefault(source, []).append(flop)
        order: list[str] = []
        problems: list[str] = []
        current = SCAN_IN
        while current in successor:
            nxt = successor[current]
            if len(nxt) > 1:
                problems.append(f"{current} feeds {len(nxt)} flops in shift mode: {', '.join(sorted(nxt))}")
            flop = sorted(nxt)[0]
            if flop in order:
                break
            order.append(flop)
            current = flop
        out_source = sources.get(words[scan_out])
        tail = order[-1] if order else SCAN_IN
        if out_source != tail:
            problems.append(f"scan_out is {out_source or 'not a chain element'} in shift mode, not the last "
                            f"flop of the chain ({tail})")
        off = [f.name for f in self.flops if f.name not in order]
        for name in off:
            source = loads[name]
            why = (f"loads {source}, which is not on the chain" if source
                   else "loads no chain element when scan_en is high (no scan path)")
            problems.append(f"flop {name} is not on the scan chain: it {why}")
        return Chain(order=[by_name[n] for n in order], off_chain=off, problems=problems)


@dataclass(frozen=True)
class Chain:
    order: list[Flop]
    off_chain: list[str]
    problems: list[str]

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


def stitch(netlist: dict, top: str) -> tuple[dict, dict]:
    """Turn every flop of ``top`` into a scan cell and stitch one chain; return the netlist and report.

    Refuses (NetlistError) what one mux-D chain cannot honestly cover: no
    flops, latches or other sequential cells, more than one clock, a clock
    that is not a module input, or ports that already use the scan names.
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
    clocks = {(f.clock, f.edge) for f in design.flops}
    if len(clocks) != 1:
        described = sorted({f"{f.edge} {design.describe(f.clock)}" for f in design.flops})
        raise NetlistError(f"one chain needs one clock and edge; found {len(clocks)}: {'; '.join(described)}")
    clock, edge = next(iter(clocks))
    inputs = design.input_bits()
    if clock not in inputs:
        raise NetlistError(f"the clock is not a module input: {design.describe(clock)}")

    module = design.module
    next_bit = 1 + max((b for net in module.get("netnames", {}).values() for b in net["bits"] if isinstance(b, int)),
                       default=1)
    se, si = next_bit, next_bit + 1
    module["ports"][SCAN_EN] = {"direction": "input", "bits": [se]}
    module["ports"][SCAN_IN] = {"direction": "input", "bits": [si]}
    last_q = design.flops[-1].q
    module["ports"][SCAN_OUT] = {"direction": "output", "bits": [last_q]}
    for name, bit in ((SCAN_EN, se), (SCAN_IN, si), (SCAN_OUT, last_q)):
        module["netnames"][name] = {"hide_name": 0, "bits": [bit], "attributes": {}}

    order = []
    previous = si
    for position, flop in enumerate(design.flops):
        cell = module["cells"][flop.cell]
        cell["type"] = SCAN_CELL + flop.type[1:]
        cell["connections"]["SE"] = [se]
        cell["connections"]["SI"] = [previous]
        cell.setdefault("port_directions", {}).update(SE="input", SI="input")
        order.append({"position": position, "flop": flop.name, "cell": flop.cell, "type": flop.type})
        previous = flop.q
    report = {
        "top": top,
        "architecture": "mux-D, one chain",
        "length": len(order),
        "clock": {"port": inputs[clock], "edge": edge},
        "ports": {"enable": SCAN_EN, "input": SCAN_IN, "output": SCAN_OUT},
        "order": order,
    }
    return netlist, report


# --- The chain testbench ------------------------------------------------------------------


def _ident(name: str) -> str:
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", name) else f"\\{name} "


def _literal(bits: list[int]) -> str:
    """A Verilog literal whose bit i is ``bits[i]``."""
    return f"{len(bits)}'b" + "".join(str(b) for b in reversed(bits))


def testbench(design: Design, seed: int = 7) -> tuple[str, dict]:
    """A self-checking testbench for the chain of ``design``, and what it expects.

    1. Shift: with scan_en high, 2L known bits go in at scan_in; the last L
       must come out at scan_out, L cycles later.
    2. Capture: shift in a known state, hold the inputs at known values, give
       one clock with scan_en low, then shift the captured state out. The
       expected state is the netlist's next-state function, evaluated here.

    Raises NetlistError when the chain is not complete: a flop the chain
    cannot load leaves nothing definite to capture.
    """
    chain = design.trace_chain()
    if not chain.complete:
        raise NetlistError("the scan chain is broken: " + "; ".join(chain.problems))
    flops = chain.order
    length = len(flops)
    if length == 0:
        raise NetlistError(f"{design.top} has no flip-flops on a scan chain")
    clocks = {(f.clock, f.edge) for f in flops}
    if len(clocks) != 1:
        raise NetlistError("the chain testbench needs one clock and edge")
    clock, edge = next(iter(clocks))
    inputs = design.input_bits()
    if clock not in inputs:
        raise NetlistError(f"the clock is not a module input: {design.describe(clock)}")
    clock_port = inputs[clock]
    if "[" in clock_port:
        raise NetlistError(f"the clock is one bit of a vector port ({clock_port})")
    resets = {f.reset: f.reset_active for f in flops if f.reset is not None and not isinstance(f.reset, str)}
    stray = [design.describe(r) for r in resets if r not in inputs]
    if stray:
        raise NetlistError(f"an async reset is not a module input: {'; '.join(stray)}")

    rng = random.Random(seed)
    flush = [rng.getrandbits(1) for _ in range(2 * length)]
    state = [rng.getrandbits(1) for _ in range(length)]
    held = {SCAN_EN, SCAN_IN, clock_port}
    values: dict[object, int] = {}
    for bit, name in inputs.items():
        if bit in resets:
            values[bit] = 1 - resets[bit]
        elif bit == clock or name in held:
            values[bit] = 0
        else:
            values[bit] = rng.getrandbits(1)
    for bit in design.port_bits(SCAN_EN):
        values[bit] = 0
    for flop, v in zip(flops, state):
        values[flop.q] = v
    words = design.evaluate([f.d for f in flops], values)
    captured = [words[f.d] for f in flops]

    idle = 0 if edge == "posedge" else 1
    decls, conns, drives = [], [], []
    for name, port in design.ports.items():
        width = len(port["bits"])
        vec = f"[{width - 1}:0] " if width > 1 else ""
        ident = _ident(name)
        kind = "reg" if port["direction"] == "input" else "wire"
        decls.append(f"  {kind} {vec}{ident};")
        conns.append(f"    .{ident}({ident})")
        if port["direction"] == "input" and name not in (SCAN_EN, SCAN_IN, clock_port):
            drives.append(f"    {ident} = {_literal([values.get(b, 0) for b in port['bits']])};")
    clk = _ident(clock_port)
    text = f"""`timescale 1ns / 1ps
// Scan chain test for {design.top}: generated by nirmaan.integrations.dft_scan.
// Chain of {length} flops, {edge} {clock_port}; shift {2 * length} bits, then one capture.
module nirmaan_scan_tb;
{chr(10).join(decls)}
  reg [{2 * length - 1}:0] flush;
  reg [{length - 1}:0] state;
  reg [{length - 1}:0] expected;
  integer i, shift_errors, capture_errors;

  {_ident(design.top)} dut (
{("," + chr(10)).join(conns)}
  );

  task pulse;
    begin
      #5 {clk} = ~{clk};
      #5 {clk} = ~{clk};
    end
  endtask

  initial begin
    shift_errors = 0;
    capture_errors = 0;
    flush = {_literal(flush)};
    state = {_literal(state)};
    expected = {_literal(captured)};
    {clk} = 1'b{idle};
{chr(10).join(drives)}
    {SCAN_EN} = 1'b1;
    {SCAN_IN} = 1'b0;
    // 1. Shift: bit i goes in at cycle i and is at scan_out before the edge of cycle i + {length}.
    for (i = 0; i < {2 * length}; i = i + 1) begin
      {SCAN_IN} = flush[i];
      #4;
      if (i >= {length} && {SCAN_OUT} !== flush[i - {length}]) begin
        $error("shift: cycle %0d scan_out=%b, expected %b", i, {SCAN_OUT}, flush[i - {length}]);
        shift_errors = shift_errors + 1;
      end
      pulse;
    end
    // 2. Capture: load the state (flop k of the chain gets state[k]), one functional clock, unload.
    for (i = 0; i < {length}; i = i + 1) begin
      {SCAN_IN} = state[{length - 1} - i];
      #4;
      pulse;
    end
    {SCAN_EN} = 1'b0;
    #4;
    pulse;
    {SCAN_EN} = 1'b1;
    for (i = 0; i < {length}; i = i + 1) begin
      #4;
      if ({SCAN_OUT} !== expected[{length - 1} - i]) begin
        $error("capture: chain flop %0d captured %b, expected %b", {length - 1} - i, {SCAN_OUT},
               expected[{length - 1} - i]);
        capture_errors = capture_errors + 1;
      end
      pulse;
    end
    $display("DFT-SCAN: chain length {length}, shift errors %0d, capture errors %0d", shift_errors, capture_errors);
    $finish;
  end
endmodule
"""
    expect = {"top": design.top, "length": length, "clock": {"port": clock_port, "edge": edge},
              "order": [f.name for f in flops], "flush": flush, "state": state, "captured": captured}
    return text, expect


# --- Command line: the steps the DFT backends run -------------------------------------------


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["stitch"] and len(argv) == 5:
            _, prep, out, report, top = argv
            netlist, chain = stitch(json.loads(Path(prep).read_text(encoding="utf-8")), top)
            Path(out).write_text(json.dumps(netlist), encoding="utf-8")
            Path(report).write_text(json.dumps(chain, indent=2) + "\n", encoding="utf-8")
            print(f"DFT-STITCH: {chain['length']} flops on one chain, {chain['clock']['edge']} "
                  f"{chain['clock']['port']}")
            return 0
        if argv[:1] == ["testbench"] and len(argv) == 5:
            _, design_json, tb, expect, top = argv
            text, expected = testbench(Design.load(design_json, top))
            Path(tb).write_text(text, encoding="utf-8")
            Path(expect).write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
            print(f"DFT-TESTBENCH: chain of {expected['length']} flops, order {', '.join(expected['order'][:8])}"
                  f"{', ...' if expected['length'] > 8 else ''}")
            return 0
    except (NetlistError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"DFT-ERROR: {exc}")
        return 1
    print("usage: dft_scan.py stitch PREP.json OUT.json CHAIN.json TOP | testbench DESIGN.json TB.v EXPECT.json TOP")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

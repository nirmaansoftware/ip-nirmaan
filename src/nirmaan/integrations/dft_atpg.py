"""Stuck-at and transition ATPG over a Yosys scan netlist, and the fault netlist that grades it.

Standard library only, for the reason ``dft_scan.py`` is: the ``dft.atpg``
backend runs it as a step between Yosys and Icarus
(``python dft_atpg.py generate|inject ...``).

* ``generate`` writes a pattern file: random patterns, then PODEM for the
  faults they miss, over the capture model (the logic between scan flops with
  ``scan_en`` low). It records which pattern it believes detects each fault
  (its claims) and which faults it proved undetectable.
* ``inject`` enumerates the fault universe again, from the netlist, writes a
  copy of the netlist with a multiplexer on every fault site, and a testbench
  that applies the patterns through the scan protocol to the design as given
  and to the fault netlist, one fault at a time. Icarus runs it; the coverage
  is what that simulation saw, never what the generator claimed.

M29 adds transition faults (``--model transition``): slow-to-rise and
slow-to-fall on the same sites, generated over two time frames (launch on
capture) and graded with a one-cycle delay at each site of the fault netlist,
active only in the at-speed cycle. It also models a pulse whose flops capture
on both edges, for stuck-at, as two evaluations.

Nothing here runs a tool or claims that one ran.
"""

from __future__ import annotations

import copy
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__:
    from .dft_scan import GATES, SCAN_EN, SCAN_IN, SCAN_OUT, Design, NetlistError, _ident, _literal, clocking
else:  # run as a step, next to dft_scan.py
    from dft_scan import GATES, SCAN_EN, SCAN_IN, SCAN_OUT, Design, NetlistError, _ident, _literal, clocking

X = 2  # the unknown value of three-valued simulation
FAULTY_TOP = "nirmaan_faulty"
TB_TOP = "nirmaan_atpg_tb"
FORMAT = "nirmaan-atpg-1"
STUCK_AT, TRANSITION = "stuck-at", "transition"
FAULT_MODELS = (STUCK_AT, TRANSITION)


def _table(kind: str) -> tuple[int, ...]:
    """A gate's three-valued truth table, indexed by sum(value_i * 3**i) over its pins."""
    pins, fn = GATES[kind]
    table = []
    for index in range(3 ** len(pins)):
        digits = [(index // 3 ** i) % 3 for i in range(len(pins))]
        unknown = [i for i, d in enumerate(digits) if d == X]
        outs = set()
        for fill in range(2 ** len(unknown)):
            vals = list(digits)
            for j, i in enumerate(unknown):
                vals[i] = (fill >> j) & 1
            outs.add(fn(dict(zip(pins, vals))) & 1)
        table.append(outs.pop() if len(outs) == 1 else X)
    return tuple(table)


_TABLES = {kind: _table(kind) for kind in GATES}


@dataclass(frozen=True)
class Fault:
    index: int
    site: int  # the model net
    bit: object  # the netlist bit
    stuck: int
    name: str
    #: M29: further model nets that are the same netlist net in another evaluation (stuck there too).
    extra: tuple[int, ...] = ()
    #: M29: (model net, value) the good machine must also show, e.g. a transition's launch value.
    need: tuple[tuple[int, int], ...] = ()

    @property
    def sites(self) -> tuple[int, ...]:
        return (self.site, *self.extra)


class CaptureModel:
    """The combinational logic between scan flops, with scan_en low, as an indexed gate list.

    Controllable: primary inputs (not clocks, asynchronous resets, or scan
    control) and flop outputs. Observable: primary outputs (not scan_out) and
    flop inputs. Constant: scan control low, asynchronous resets inactive.
    """

    def __init__(self) -> None:
        self.index: dict[object, int] = {}
        self.bits: list[object] = []
        self.names: list[str] = []
        self.const: dict[int, int] = {}
        self.pis: list[int] = []
        self.ppis: list[int] = []
        self.pos: list[int] = []
        self.ppos: list[int] = []
        self.pi_names: list[str] = []
        self.po_names: list[str] = []
        self.gates: list[tuple[str, tuple[int, ...], int]] = []
        self.controls: list[int] = []
        self.observe: list[int] = []
        self._observed: set[int] = set()
        self.driver: dict[int, int] = {}
        self.fanout: dict[int, list[int]] = {}
        self._cones: dict[int, list[int]] = {}

    # --- Building -------------------------------------------------------------------------

    def _net(self, bit, design: Design) -> int:
        if isinstance(bit, str):
            bit = "1" if bit == "1" else "0"  # x and z read 0, as Design.evaluate does
        if bit not in self.index:
            self.index[bit] = len(self.bits)
            self.bits.append(bit)
            self.names.append(f"constant {bit}" if isinstance(bit, str) else design.names.get(bit, f"net{bit}"))
            if isinstance(bit, str):
                self.const[self.index[bit]] = int(bit)
        return self.index[bit]

    @classmethod
    def build(cls, design: Design, chains: list[list] | None = None) -> CaptureModel:
        if design.unknown or design.latches or design.others:
            raise NetlistError("the netlist has cells ATPG cannot model (run dft.check)")
        loops = design.combinational_loops()
        if loops:
            raise NetlistError(f"combinational loop through {', '.join(loops[0])}")
        model = cls()
        flops = [f for chain in chains for f in chain] if chains else list(design.flops)
        inputs = design.input_bits()
        fixed: dict[object, int] = {}
        for bit in [*design.port_bits(SCAN_EN), *design.port_bits(SCAN_IN)]:
            fixed[bit] = 0
        for f in design.flops:
            fixed.setdefault(f.clock, 0)
            if f.reset is not None and not isinstance(f.reset, str):
                fixed[f.reset] = 1 - f.reset_active
        for bit, name in inputs.items():
            net = model._net(bit, design)
            if bit in fixed:
                model.const[net] = fixed[bit]
            else:
                model.pis.append(net)
                model.pi_names.append(name)
        for f in flops:
            model.ppis.append(model._net(f.q, design))
        cells = design.module["cells"]
        gate_cells = [c for c, spec in cells.items() if spec["type"] in GATES]
        out_of = {cells[c]["connections"]["Y"][0]: c for c in gate_cells}
        order: list[str] = []
        state: dict[str, int] = {}
        for root in gate_cells:  # topological order, iteratively
            if root in state:
                continue
            stack = [(root, False)]
            while stack:
                cell, done = stack.pop()
                if done:
                    state[cell] = 2
                    order.append(cell)
                    continue
                if cell in state:
                    continue
                state[cell] = 1
                stack.append((cell, True))
                pins, _ = GATES[cells[cell]["type"]]
                for p in pins:
                    src = out_of.get(cells[cell]["connections"][p][0])
                    if src is not None and src not in state:
                        stack.append((src, False))
        for cell in order:
            spec = cells[cell]
            pins, _ = GATES[spec["type"]]
            ins = tuple(model._net(spec["connections"][p][0], design) for p in pins)
            out = model._net(spec["connections"]["Y"][0], design)
            model.driver[out] = len(model.gates)
            for i in ins:
                model.fanout.setdefault(i, []).append(len(model.gates))
            model.gates.append((spec["type"], ins, out))
        for name, port in design.ports.items():
            if port["direction"] == "output" and name != SCAN_OUT:
                bits = port["bits"]
                for i, bit in enumerate(bits):
                    if isinstance(bit, int):
                        model.pos.append(model._net(bit, design))
                        model.po_names.append(name if len(bits) == 1 else f"{name}[{i}]")
        model.ppos = [model._net(f.d, design) for f in flops]
        model.controls = model.pis + model.ppis
        controlled = set(model.controls)
        for net in range(len(model.bits)):  # undriven, uncontrolled nets read 0
            if net not in model.driver and net not in model.const and net not in controlled:
                model.const[net] = 0
        model.observe = sorted(set(model.pos + model.ppos))
        model._observed = set(model.observe)
        return model

    def sites(self) -> list[tuple[int, str]]:
        """Every controllable input and gate output, once each, with a unique name: the fault sites."""
        sites = [n for n in self.controls] + [out for _, _, out in self.gates if out not in self.const]
        seen: set[int] = set()
        names: set[str] = set()
        found: list[tuple[int, str]] = []
        for site in sites:
            if site in seen or site in self.const:
                continue
            seen.add(site)
            label = self.names[site]
            if label in names:
                label = f"{label}#{self.bits[site]}"
            names.add(label)
            found.append((site, label))
        return found

    def faults(self) -> list[Fault]:
        """Stuck-at 0 and 1 on every controllable input and gate output: the uncollapsed stem faults."""
        found: list[Fault] = []
        for site, label in self.sites():
            for stuck in (0, 1):
                found.append(Fault(len(found), site, self.bits[site], stuck, f"{label}/SA{stuck}"))
        return found

    def copy_frame(self, refresh: set[int], separate_inputs: bool) -> dict[int, int]:
        """Append a second evaluation of the logic (M29); return each net's net in it.

        In the copy, the flops at positions ``refresh`` (of ``ppis``) output
        their next state from the first evaluation; the other flops keep their
        outputs. Primary inputs hold their value; with ``separate_inputs`` the
        copy still sees them through buffers, so a fault can sit on the copy
        alone. Constants are shared. Observed nets are left to the caller.
        """
        copy: dict[int, int] = {net: net for net in self.const}
        frame = list(self.gates)

        def fresh(net: int) -> int:
            self.bits.append(("copy", self.bits[net]))
            self.names.append(self.names[net])
            return len(self.bits) - 1

        def gate(kind: str, ins: tuple[int, ...], out: int) -> None:
            self.driver[out] = len(self.gates)
            for i in ins:
                self.fanout.setdefault(i, []).append(len(self.gates))
            self.gates.append((kind, ins, out))

        for net in self.pis:
            copy[net] = net
            if separate_inputs:
                copy[net] = fresh(net)
                gate("$_BUF_", (net,), copy[net])
        for pos, net in enumerate(self.ppis):
            copy[net] = net
            if pos in refresh:
                copy[net] = fresh(net)
                gate("$_BUF_", (self.ppos[pos],), copy[net])
        for kind, ins, out in frame:
            copy[out] = fresh(out)
            gate(kind, tuple(copy[i] for i in ins), copy[out])
        self._cones.clear()
        return copy

    def watch(self) -> None:
        """Recompute the observed nets from ``pos`` and ``ppos``."""
        self.observe = sorted(set(self.pos + self.ppos))
        self._observed = set(self.observe)

    def cone(self, net: int) -> list[int]:
        """The gates in the transitive fanout of ``net``, in topological order."""
        if net not in self._cones:
            reached: set[int] = set()
            work = [net]
            while work:
                for g in self.fanout.get(work.pop(), ()):
                    if g not in reached:
                        reached.add(g)
                        work.append(self.gates[g][2])
            self._cones[net] = sorted(reached)
        return self._cones[net]

    # --- Two-valued, bit-parallel simulation ------------------------------------------------

    def simulate(self, words: dict[int, int], width: int) -> list[int]:
        """Every net's value for ``width`` patterns at once; ``words`` gives each controllable input."""
        mask = (1 << width) - 1
        vals = [0] * len(self.bits)
        for net, v in self.const.items():
            vals[net] = mask if v else 0
        for net in self.controls:
            vals[net] = words.get(net, 0) & mask
        for kind, ins, out in self.gates:
            pins, fn = GATES[kind]
            vals[out] = fn(dict(zip(pins, (vals[i] for i in ins)))) & mask
        return vals

    def effect(self, good: list[int], fault: Fault, width: int) -> int:
        """The patterns (bits of the word) in which ``fault`` changes an observed net (and its needs hold)."""
        mask = (1 << width) - 1
        stuck = mask if fault.stuck else 0
        for net, value in fault.need:
            mask &= good[net] if value else ~good[net]
        sites = fault.sites
        diff = {s: stuck for s in sites if good[s] != stuck}
        if not diff or not mask:
            return 0
        cone = sorted({g for s in sites for g in self.cone(s)}) if len(sites) > 1 else self.cone(fault.site)
        for g in cone:
            kind, ins, out = self.gates[g]
            if out in sites or not any(i in diff for i in ins):
                continue
            pins, fn = GATES[kind]
            value = fn(dict(zip(pins, (diff.get(i, good[i]) for i in ins)))) & ((1 << width) - 1)
            if value != good[out]:
                diff[out] = value
        seen = 0
        for net, value in diff.items():
            if net in self._observed:
                seen |= value ^ good[net]
        return seen & mask

    def detects(self, values: dict[int, int], fault: Fault) -> bool:
        """Whether one pattern (controllable input to bit; missing ones read 0) detects ``fault``."""
        return bool(self.effect(self.simulate(values, 1), fault, 1))

    # --- PODEM ------------------------------------------------------------------------------

    def podem(self, fault: Fault, limit: int = 200) -> tuple[str, dict[int, int] | None]:
        """("detected", a partial assignment that detects), ("untestable", None), or ("aborted", None).

        Decisions are made only on controllable inputs, and backtracking is
        complete, so "untestable" is a proof over the capture model. "aborted"
        means the backtrack limit was reached first.
        """
        n = len(self.bits)
        good = [X] * n
        bad = [X] * n
        for net, v in self.const.items():
            good[net] = bad[net] = v
        stuck = fault.stuck
        sites = set(fault.sites)
        for site in sites:
            bad[site] = stuck
        need = list(fault.need)
        pow3 = (1, 3, 9, 27)

        def evaluate(gates) -> None:
            for g in gates:
                kind, ins, out = self.gates[g]
                table = _TABLES[kind]
                good[out] = table[sum(good[i] * pow3[j] for j, i in enumerate(ins))]
                bad[out] = stuck if out in sites else table[sum(bad[i] * pow3[j] for j, i in enumerate(ins))]

        evaluate(range(len(self.gates)))
        cone = sorted({g for site in sites for g in self.cone(site)})
        in_cone = set(cone)
        watched = [o for o in self.observe if o in sites or self.driver.get(o) in in_cone]

        def assign(net: int, value: int) -> None:
            good[net] = value
            bad[net] = stuck if net in sites else value
            evaluate(self.cone(net))

        def is_d(net: int) -> bool:
            return good[net] != X and bad[net] != X and good[net] != bad[net]

        def x_path(start: list[int]) -> bool:
            seen: set[int] = set()
            work = list(start)
            while work:
                net = work.pop()
                if net in seen or (good[net] != X and bad[net] != X):
                    continue
                if net in self._observed:
                    return True
                seen.add(net)
                work += [self.gates[g][2] for g in self.fanout.get(net, ())]
            return False

        def objective() -> tuple[int, int] | None:
            # A need is a goal until met, and a dead end once contradicted: values only refine from X.
            for net, value in need:
                if good[net] == X:
                    return net, value
                if good[net] != value:
                    return None
            # Activation: every site still open is a goal; with none open, one must differ from the stuck value.
            for site in sorted(sites):
                if good[site] == X:
                    return site, 1 - stuck
            if all(good[site] == stuck for site in sites):
                return None
            frontier = []
            for g in cone:
                kind, ins, out = self.gates[g]
                if (good[out] == X or bad[out] == X) and any(is_d(i) for i in ins):
                    frontier.append(g)
            if not frontier or not x_path([self.gates[g][2] for g in frontier]):
                return None
            for g in frontier:
                kind, ins, out = self.gates[g]
                table = _TABLES[kind]
                best = None
                for j, net in enumerate(ins):
                    if good[net] != X and bad[net] != X:
                        continue
                    for value in (0, 1):
                        gv = [value if k == j else good[i] for k, i in enumerate(ins)]
                        bv = [value if k == j else bad[i] for k, i in enumerate(ins)]
                        o_g = table[sum(v * pow3[k] for k, v in enumerate(gv))]
                        o_b = table[sum(v * pow3[k] for k, v in enumerate(bv))]
                        if o_g != X and o_b != X and o_g == o_b:
                            continue  # blocks the fault effect
                        score = 2 if (o_g != X and o_b != X) else 1
                        if best is None or score > best[0]:
                            best = (score, net, value)
                if best:
                    return best[1], best[2]
            return None

        def backtrace(net: int, value: int) -> tuple[int, int]:
            while net in self.driver:
                kind, ins, out = self.gates[self.driver[net]]
                table = _TABLES[kind]
                open_ = [j for j, i in enumerate(ins) if good[i] == X] or [j for j, i in enumerate(ins) if bad[i] == X]
                best = None
                for j in open_:
                    for v in (0, 1):
                        vals = [v if k == j else good[i] for k, i in enumerate(ins)]
                        o = table[sum(x * pow3[k] for k, x in enumerate(vals))]
                        score = 2 if o == value else (1 if o == X else 0)
                        if best is None or score > best[0]:
                            best = (score, ins[j], v)
                if best is None:
                    break
                _, net, value = best
            return net, value

        stack: list[list[int]] = []
        backtracks = 0
        while True:
            if any(is_d(o) for o in watched) and all(good[net] == value for net, value in need):
                return "detected", {i: good[i] for i in self.controls if good[i] != X}
            goal = objective()
            if goal is not None:
                net, value = backtrace(*goal)
                if net in self.driver or good[net] != X:  # no open input found: treat as a dead end
                    goal = None
                else:
                    assign(net, value)
                    stack.append([net, value, 0])
                    continue
            while stack and stack[-1][2]:
                net, _, _ = stack.pop()
                good[net] = bad[net] = X
                if net in sites:
                    bad[net] = stuck
                evaluate(self.cone(net))
            if not stack:
                return "untestable", None
            if backtracks >= limit:
                return "aborted", None
            backtracks += 1
            top = stack[-1]
            top[1], top[2] = 1 - top[1], 1
            assign(top[0], top[1])

    # --- Pattern files ----------------------------------------------------------------------

    def pattern_values(self, pattern: dict) -> dict[int, int]:
        """A pattern file entry as a value for each controllable input."""
        bits = [int(c) for c in pattern["pi"]] + [int(c) for chain in pattern["load"] for c in chain]
        return dict(zip(self.controls, bits))


def _chains(design: Design) -> list[list]:
    """The traced scan chains, which must be complete (M29: lockups at clock crossings, edges in order)."""
    if not design.flops:
        return []
    if not design.has_scan_ports():
        raise NetlistError(f"{design.top} has flops but no scan ports: insert scan first (dft.scan_insert)")
    chain = design.trace_chain()
    if not chain.complete:
        raise NetlistError("the scan chain is broken: " + "; ".join(chain.problems + chain.hazards))
    return chain.chains


def build_model(design: Design, chains: list[list] | None = None,
                fault_model: str = STUCK_AT) -> tuple[CaptureModel, list[Fault]]:
    """The model ATPG works on, and its fault universe (M29).

    * Stuck-at, one capture edge: M27's capture model and its stem faults.
    * Stuck-at, both edges of the pulse: the second-edge flops capture from a
      copy of the logic in which the first-edge flops already hold their new
      state; each fault sits on both copies of its net.
    * Transition (launch on capture): a second frame whose flops hold the
      first frame's next state and whose inputs are held. ``net/STR`` is the
      frame-2 copy stuck at 0 with the net at 0 in frame 1; ``net/STF`` the
      reverse. Needs one capture edge.
    """
    if fault_model not in FAULT_MODELS:
        raise NetlistError(f"unknown fault model {fault_model!r}: one of {', '.join(FAULT_MODELS)}")
    model = CaptureModel.build(design, chains)
    flops = [f for c in chains for f in c] if chains else list(design.flops)
    phase = clocking(design, flops)[1] if flops else {}
    if fault_model == TRANSITION:
        if any(phase.values()):
            raise NetlistError("flops capture on both edges of the test clock pulse; transition ATPG (launch on "
                               "capture) over two capture edges is not supported")
        sites = model.sites()
        copy = model.copy_frame(set(range(len(model.ppis))), separate_inputs=True)
        model.pos = [copy[n] for n in model.pos]
        model.ppos = [copy[n] for n in model.ppos]
        model.watch()
        faults: list[Fault] = []
        for site, label in sites:
            for kind, value in (("STR", 0), ("STF", 1)):
                faults.append(Fault(len(faults), copy[site], model.bits[site], value, f"{label}/{kind}",
                                    need=((site, value),)))
        return model, faults
    faults = model.faults()
    if not any(phase.values()):
        return model, faults
    first = {i for i, f in enumerate(flops) if phase[f.name] == 0}
    copy = model.copy_frame(first, separate_inputs=False)
    model.ppos = [d if i in first else copy[d] for i, d in enumerate(model.ppos)]
    model.watch()
    return model, [Fault(f.index, f.site, f.bit, f.stuck, f.name,
                         extra=(copy[f.site],) if copy[f.site] != f.site else ()) for f in faults]


def _pack(patterns: list[dict[int, int]], controls: list[int]) -> dict[int, int]:
    words = {}
    for net in controls:
        word = 0
        for k, p in enumerate(patterns):
            word |= p[net] << k
        words[net] = word
    return words


def generate(design: Design, seed: int = 1, limit: int = 200, random_only: bool = False,
             batch: int = 64, max_batches: int = 32, fault_model: str = STUCK_AT) -> dict:
    """A pattern file for ``design``: random patterns, PODEM for the rest, then each fault's claim."""
    chains = _chains(design)
    model, faults = build_model(design, chains, fault_model)
    rng = random.Random(seed)
    remaining = set(range(len(faults)))
    patterns: list[dict[int, int]] = []
    mask = (1 << batch) - 1
    for _ in range(max_batches):
        if not remaining:
            break
        words = {net: rng.getrandbits(batch) for net in model.controls}
        good = model.simulate(words, batch)
        first: dict[int, int] = {}
        for f in remaining:
            seen = model.effect(good, faults[f], batch) & mask
            if seen:
                first[f] = (seen & -seen).bit_length() - 1
        if not first:
            break
        for k in sorted(set(first.values())):
            patterns.append({net: (words[net] >> k) & 1 for net in model.controls})
        remaining -= set(first)
    untestable: list[int] = []
    aborted: list[int] = []
    if not random_only:
        for f in sorted(remaining):
            if f not in remaining:
                continue
            status, assignment = model.podem(faults[f], limit)
            if status == "untestable":
                untestable.append(f)
                remaining.discard(f)
                continue
            if status == "aborted":
                aborted.append(f)
                continue
            pattern = {net: assignment.get(net, rng.getrandbits(1)) for net in model.controls}
            good = model.simulate(pattern, 1)
            newly = {g for g in remaining if model.effect(good, faults[g], 1)}
            if f not in newly:  # the three-valued search and the two-valued check disagree
                aborted.append(f)
                continue
            patterns.append(pattern)
            remaining -= newly

    def claim(pats: list[dict[int, int]]) -> dict[int, int]:
        claims: dict[int, int] = {}
        for start in range(0, len(pats), batch):
            chunk = pats[start:start + batch]
            good = model.simulate(_pack(chunk, model.controls), len(chunk))
            for f, fault in enumerate(faults):
                if f in claims:
                    continue
                seen = model.effect(good, fault, len(chunk))
                if seen:
                    claims[f] = start + (seen & -seen).bit_length() - 1
        return claims

    claims = claim(patterns)
    patterns = [patterns[k] for k in sorted(set(claims.values()))]  # keep only first detectors
    claims = claim(patterns)
    untestable = [f for f in untestable if f not in claims]  # never both: a claim is checked by simulation
    entries = []
    for pattern in patterns:
        good = model.simulate(pattern, 1)
        load, unload, at = [], [], 0
        for chain in chains:
            load.append("".join(str(pattern[n]) for n in model.ppis[at:at + len(chain)]))
            unload.append("".join(str(good[n]) for n in model.ppos[at:at + len(chain)]))
            at += len(chain)
        entries.append({"pi": "".join(str(pattern[n]) for n in model.pis), "load": load,
                        "po": "".join(str(good[n]) for n in model.pos), "unload": unload})
    return {
        "format": FORMAT,
        "top": design.top,
        "fault_model": fault_model,
        **({"protocol": "launch-on-capture"} if fault_model == TRANSITION else {}),
        "generator": "random" if random_only else "random+podem",
        "seed": seed,
        "pis": model.pi_names,
        "pos": model.po_names,
        "chains": [[f.name for f in chain] for chain in chains],
        "faults_total": len(faults),
        "patterns": entries,
        "claims": {faults[f].name: k for f, k in sorted(claims.items())},
        "untestable": [faults[f].name for f in untestable],
        "aborted": [faults[f].name for f in aborted if f not in claims],
    }


# --- Grading: the fault netlist and its testbench --------------------------------------------


def _check_patterns(doc: dict, model: CaptureModel, chains: list[list], names: set[str],
                    fault_model: str = STUCK_AT) -> None:
    """Refuse a pattern file that does not fit this netlist, before anything is simulated."""
    if doc.get("format") != FORMAT:
        raise NetlistError(f"not a {FORMAT} pattern file")
    if doc.get("fault_model", STUCK_AT) != fault_model:
        raise NetlistError(f"the pattern file is for the {doc.get('fault_model')} fault model, not {fault_model}")
    expected = {"pis": model.pi_names, "pos": model.po_names, "chains": [[f.name for f in c] for c in chains]}
    for key, value in expected.items():
        if doc.get(key) != value:
            raise NetlistError(f"the pattern file's {key} do not match the netlist's")
    widths = [len(c) for c in chains]
    for k, p in enumerate(doc["patterns"]):
        fields = [p["pi"], p["po"], *p["load"], *p["unload"]]
        if (len(p["pi"]) != len(model.pis) or len(p["po"]) != len(model.pos)
                or [len(c) for c in p["load"]] != widths or [len(c) for c in p["unload"]] != widths
                or any(set(f) - {"0", "1"} for f in fields)):
            raise NetlistError(f"pattern {k} does not fit the netlist's inputs, outputs, and chains")
    unknown = sorted(set(doc.get("claims", {})) - names)
    if unknown:
        raise NetlistError(f"the pattern file claims faults the netlist does not have: {', '.join(unknown[:5])}")
    count = len(doc["patterns"])
    bad = sorted(n for n, k in doc.get("claims", {}).items() if not (isinstance(k, int) and 0 <= k < count))
    if bad:
        raise NetlistError(f"claims name patterns that do not exist: {', '.join(bad[:5])}")


def fault_netlist(netlist: dict, top: str, bits: list, transition: bool = False) -> dict:
    """A copy of ``top`` with a multiplexer on each bit in ``bits``, between the net and its loads.

    Site s is held at bit s of the new input ``nirmaan_fault_val`` while bit s
    of ``nirmaan_fault_en`` is high; with every enable low the netlist is
    unchanged in function.

    With ``transition`` (M29), site s instead takes a one-cycle delay: a flop
    on the new input ``nirmaan_fault_clk`` holds the net's previous value, and
    the site becomes ``net & prev`` (slow to rise, value bit 0) or ``net |
    prev`` (slow to fall, value bit 1), only while its enable and the new input
    ``nirmaan_fault_atspeed`` are both high.
    """
    module = copy.deepcopy(netlist["modules"][top])
    used = [b for net in module.get("netnames", {}).values() for b in net["bits"] if isinstance(b, int)]
    used += [b for p in module["ports"].values() for b in p["bits"] if isinstance(b, int)]
    fresh = max(used, default=1) + 1
    en = list(range(fresh, fresh + len(bits)))
    val = list(range(fresh + len(bits), fresh + 2 * len(bits)))
    moved = {bit: fresh + 2 * len(bits) + s for s, bit in enumerate(bits)}
    for spec in module["cells"].values():
        dirs = spec.get("port_directions", {})
        for pin, conn in spec["connections"].items():
            if dirs.get(pin) == "input" or (not dirs and pin not in ("Y", "Q")):
                spec["connections"][pin] = [moved.get(b, b) for b in conn]
    outputs = [name for name, p in module["ports"].items() if p["direction"] == "output"]
    for name in outputs:
        module["ports"][name]["bits"] = [moved.get(b, b) for b in module["ports"][name]["bits"]]
        if name in module.get("netnames", {}):
            module["netnames"][name]["bits"] = list(module["ports"][name]["bits"])
    spare = fresh + 3 * len(bits)
    clk, atspeed = spare, spare + 1
    spare += 2

    def cell(name: str, kind: str, **conns) -> None:
        dirs = {p: "output" if p in ("Y", "Q") else "input" for p in conns}
        module["cells"][name] = {"hide_name": 1, "type": kind, "parameters": {}, "attributes": {},
                                 "port_directions": dirs, "connections": {p: [b] for p, b in conns.items()}}

    for s, bit in enumerate(bits):
        if transition:
            prev, slow_rise, slow_fall, delayed, on = range(spare, spare + 5)
            spare += 5
            cell(f"$nirmaan$prev${s}", "$_DFF_P_", C=clk, D=bit, Q=prev)
            cell(f"$nirmaan$str${s}", "$_AND_", A=bit, B=prev, Y=slow_rise)
            cell(f"$nirmaan$stf${s}", "$_OR_", A=bit, B=prev, Y=slow_fall)
            cell(f"$nirmaan$delay${s}", "$_MUX_", A=slow_rise, B=slow_fall, S=val[s], Y=delayed)
            cell(f"$nirmaan$on${s}", "$_AND_", A=en[s], B=atspeed, Y=on)
            cell(f"$nirmaan$fault${s}", "$_MUX_", A=bit, B=delayed, S=on, Y=moved[bit])
        else:
            cell(f"$nirmaan$fault${s}", "$_MUX_", A=bit, B=val[s], S=en[s], Y=moved[bit])
        module["netnames"][f"$nirmaan$site${s}"] = {"hide_name": 1, "bits": [moved[bit]], "attributes": {}}
    if transition:
        for name, bit in (("nirmaan_fault_clk", clk), ("nirmaan_fault_atspeed", atspeed)):
            module["ports"][name] = {"direction": "input", "bits": [bit]}
            module["netnames"][name] = {"hide_name": 0, "bits": [bit], "attributes": {}}
    module["ports"]["nirmaan_fault_en"] = {"direction": "input", "bits": en}
    module["ports"]["nirmaan_fault_val"] = {"direction": "input", "bits": val}
    module["netnames"]["nirmaan_fault_en"] = {"hide_name": 0, "bits": en, "attributes": {}}
    module["netnames"]["nirmaan_fault_val"] = {"hide_name": 0, "bits": val, "attributes": {}}
    module.setdefault("attributes", {})["top"] = "00000000000000000000000000000001"
    return {"creator": netlist.get("creator", ""), "modules": {FAULTY_TOP: module}}


def _concat(names: list[str]) -> str:
    """A Verilog concatenation of port bits whose bit i is ``names[i]`` (so the last name is the MSB)."""
    def ref(name: str) -> str:
        base, _, rest = name.partition("[")
        return _ident(base) + (f"[{rest}" if rest else "")
    return "{" + ", ".join(ref(n) for n in reversed(names)) + "}"


def inject(design: Design, netlist: dict, doc: dict, sample: int | None = None,
           seed: int = 1, fault_model: str = STUCK_AT) -> tuple[dict, dict, str]:
    """The fault netlist, the fault list (with the claims to check), and the testbench."""
    chains = _chains(design)
    model, universe = build_model(design, chains, fault_model)
    _check_patterns(doc, model, chains, {f.name for f in universe}, fault_model)
    chosen = universe
    if sample and len(universe) > sample:
        picks = sorted(random.Random(seed).sample(range(len(universe)), sample))
        chosen = [universe[i] for i in picks]
    sites: list = list(dict.fromkeys(f.bit for f in chosen))
    site_of = {bit: s for s, bit in enumerate(sites)}
    faulty = fault_netlist(netlist, design.top, sites, transition=fault_model == TRANSITION)
    names = {f.name for f in chosen}
    faults = {
        "top": design.top, "fault_model": fault_model, "universe": len(universe),
        "sampled": len(chosen) < len(universe),
        "patterns": len(doc["patterns"]), "chains": len(chains),
        "faults": [{"name": f.name, "site": site_of[f.bit], "stuck": f.stuck} for f in chosen],
        "claims": {n: k for n, k in doc.get("claims", {}).items() if n in names},
        "untestable": [n for n in doc.get("untestable", []) if n in names],
        "aborted": [n for n in doc.get("aborted", []) if n in names],
    }
    return faulty, faults, _testbench(design, model, chains, doc, faults, len(sites), fault_model == TRANSITION)


def _testbench(design: Design, model: CaptureModel, chains: list[list], doc: dict, faults: dict, sites: int,
               transition: bool = False) -> str:
    flops = [f for c in chains for f in c]
    idle, _ = clocking(design, flops) if flops else ({}, {})
    inputs = design.input_bits()
    resets = {f.reset: f.reset_active for f in design.flops if f.reset is not None and not isinstance(f.reset, str)}
    width = max(len(chains), 1)
    length = max((len(c) for c in chains), default=0)
    patterns = doc["patterns"]
    count = len(patterns)
    scan_ports = design.has_scan_ports()

    decls, good_conns, bad_conns, fixed = [], [], [], []
    outputs: dict[str, str] = {}
    for n, (name, port) in enumerate(design.ports.items()):
        bits = len(port["bits"])
        vec = f"[{bits - 1}:0] " if bits > 1 else ""
        ident = _ident(name)
        if port["direction"] == "input":
            decls.append(f"  reg {vec}{ident};")
            good_conns.append(f"    .{ident}({ident})")
            bad_conns.append(f"    .{ident}({ident})")
            if name in idle:
                fixed.append(f"    {ident} = 1'b{idle[name]};")
            else:
                level = [1 - resets[b] if b in resets else 0 for b in port["bits"]]
                fixed.append(f"    {ident} = {_literal(level)};")
        else:
            outputs[name] = f"o{n}"
            decls.append(f"  wire {vec}g_o{n};")
            decls.append(f"  wire {vec}b_o{n};")
            good_conns.append(f"    .{ident}(g_o{n})")
            bad_conns.append(f"    .{ident}(b_o{n})")
    bad_conns += ["    .nirmaan_fault_en(fault_en)", "    .nirmaan_fault_val(fault_val)"]
    if transition:
        bad_conns += ["    .nirmaan_fault_clk(fault_clk)", "    .nirmaan_fault_atspeed(atspeed)"]

    def out_ref(name: str, machine: str) -> str:
        base, _, rest = name.partition("[")
        return f"{machine}_{outputs[base]}" + (f"[{rest}" if rest else "")

    pis = model.pi_names
    pos = model.po_names
    npi, npo = max(len(pis), 1), max(len(pos), 1)
    pi_lhs = _concat(pis) if pis else None
    good_po = "{" + ", ".join(out_ref(n, "g") for n in reversed(pos)) + "}" if pos else "1'b0"
    bad_po = "{" + ", ".join(out_ref(n, "b") for n in reversed(pos)) + "}" if pos else "1'b0"
    lens = [len(c) for c in chains]
    fill = []
    for p, entry in enumerate(patterns):
        fill.append(f"    pat_pi[{p}] = {npi}'b{entry['pi'][::-1] or '0'};")
        fill.append(f"    pat_po[{p}] = {npo}'b{entry['po'][::-1] or '0'};")
        for t in range(length):
            load = [int(entry["load"][k][length - 1 - t]) if length - 1 - t < lens[k] else 0 for k in range(len(lens))]
            unload = [int(entry["unload"][k][lens[k] - 1 - t]) if t < lens[k] else 0 for k in range(len(lens))]
            fill.append(f"    pat_load[{p * length + t}] = {_literal(load or [0])};")
            fill.append(f"    pat_unload[{p * length + t}] = {_literal(unload or [0])};")
    for t in range(length):
        fill.append(f"    unload_mask[{t}] = {_literal([int(t < n) for n in lens] or [0])};")
    for f, fault in enumerate(faults["faults"]):
        fill.append(f"    fault_site[{f}] = {fault['site']}; fault_stuck[{f}] = {fault['stuck']};")
    toggle = " ".join(f"{_ident(c)} = ~{_ident(c)};" for c in idle) or ";"
    if transition:
        toggle += " fault_clk = ~fault_clk;"
    nf = len(faults["faults"])
    scan_in = _ident(SCAN_IN) if scan_ports else "unused_scan_in"
    scan_en = _ident(SCAN_EN) if scan_ports else "unused_scan_en"
    good_so = f"g_{outputs[SCAN_OUT]}" if scan_ports else f"{width}'b0"
    bad_so = f"b_{outputs[SCAN_OUT]}" if scan_ports else f"{width}'b0"
    extra = "" if scan_ports else f"  reg [{width - 1}:0] unused_scan_in;\n  reg unused_scan_en;\n"
    kind = "Transition (launch on capture)" if transition else "Stuck-at"
    return f"""`timescale 1ns / 1ps
// {kind} fault simulation for {design.top}: generated by nirmaan.integrations.dft_atpg.
// The design as given is the good machine; {FAULTY_TOP} is the same netlist with a multiplexer on every
// fault site. {count} patterns, {len(chains)} chain(s) of at most {length} flops, {nf} faults.
module {TB_TOP};
{chr(10).join(decls)}
{extra}  reg [{max(sites, 1) - 1}:0] fault_en;
  reg [{max(sites, 1) - 1}:0] fault_val;
{"  reg fault_clk, atspeed;" + chr(10) if transition else ""}  reg [{npi - 1}:0] pat_pi [0:{max(count, 1) - 1}];
  reg [{npo - 1}:0] pat_po [0:{max(count, 1) - 1}];
  reg [{width - 1}:0] pat_load [0:{max(count * length, 1) - 1}];
  reg [{width - 1}:0] pat_unload [0:{max(count * length, 1) - 1}];
  reg [{width - 1}:0] unload_mask [0:{max(length, 1) - 1}];
  integer fault_site [0:{max(nf, 1) - 1}];
  integer fault_stuck [0:{max(nf, 1) - 1}];
  integer f, detected, response_errors, injection_errors;
  wire [{width - 1}:0] good_so = {good_so};
  wire [{width - 1}:0] bad_so = {bad_so};
  wire [{npo - 1}:0] good_po = {good_po};
  wire [{npo - 1}:0] bad_po = {bad_po};

  {_ident(design.top)} good (
{("," + chr(10)).join(good_conns)}
  );

  {FAULTY_TOP} bad (
{("," + chr(10)).join(bad_conns)}
  );

  task pulse;
    begin
      #5 {toggle}
      #5 {toggle}
    end
  endtask
{_at_speed_tasks(toggle) if transition else ""}
  // Compare the unload of pattern q at unload cycle t: against the file (check), or good against bad.
  task observe_unload(input integer q, input integer t, input check);
    integer k;
    begin
      for (k = 0; k < {width}; k = k + 1)
        if (unload_mask[t][k]) begin
          if (check && good_so[k] !== pat_unload[q * {length} + t][k])
            response_errors = response_errors + 1;
          if (bad_so[k] !== good_so[k]) begin
            if (check)
              injection_errors = injection_errors + 1;
            else if (detected < 0)
              detected = q;
          end
        end
    end
  endtask

  task run_patterns(input check);
    integer p, t;
    begin
      detected = -1;
      {scan_en} = 1'b1;
      {scan_in} = {width}'b0;
      for (t = 0; t < {length}; t = t + 1) begin
        #4;
        pulse;
      end
      for (p = 0; p < {count} && (check || detected < 0); p = p + 1) begin
{"        " + pi_lhs + " = pat_pi[p];" if pi_lhs else ""}
        {scan_en} = 1'b1;
        for (t = 0; t < {length}; t = t + 1) begin
          {scan_in} = pat_load[p * {length} + t];
          #4;
          if (p > 0)
            observe_unload(p - 1, t, check);
          pulse;
        end
        {scan_en} = 1'b0;
        {scan_in} = {width}'b0;
        #4;
{"        launch;" + chr(10) + "        #4;" + chr(10) if transition else ""}        if (check && good_po !== pat_po[p])
          response_errors = response_errors + 1;
        if (bad_po !== good_po) begin
          if (check)
            injection_errors = injection_errors + 1;
          else if (detected < 0)
            detected = p;
        end
        {"capture" if transition else "pulse"};
      end
      {scan_en} = 1'b1;
      if (check || detected < 0)
        for (t = 0; t < {length}; t = t + 1) begin
          #4;
          observe_unload({count} - 1, t, check);
          pulse;
        end
    end
  endtask

  initial begin
    response_errors = 0;
    injection_errors = 0;
{chr(10).join(fixed)}
    fault_en = 0;
    fault_val = 0;
{"    fault_clk = 1'b0;" + chr(10) + "    atspeed = 1'b0;" + chr(10) if transition else ""}{chr(10).join(fill)}
    run_patterns(1'b1);
    $display("DFT-ATPG-CHECK: patterns %0d, response errors %0d, injection errors %0d", {count}, response_errors,
             injection_errors);
    for (f = 0; f < {nf}; f = f + 1) begin
      fault_en = 0;
      fault_val = 0;
      fault_en[fault_site[f]] = 1'b1;
      fault_val[fault_site[f]] = fault_stuck[f];
      run_patterns(1'b0);
      $display("DFT-FAULT %0d %0d", f, detected);
    end
    $display("DFT-ATPG: %0d faults simulated{' (transition, launch on capture)' if transition else ''}", {nf});
    $finish;
  end
endmodule
"""


def _at_speed_tasks(toggle: str) -> str:
    """Launch and capture pulses (M29): the delay model acts from just after launch to just after capture."""
    return f"""
  // Launch on capture: the at-speed cycle runs from the launch edge to the capture edge.
  task launch;
    begin
      #5 {toggle}
      #1 atspeed = 1'b1;
      #4 {toggle}
    end
  endtask

  task capture;
    begin
      #5 {toggle}
      #1 atspeed = 1'b0;
      #4 {toggle}
    end
  endtask
"""


# --- Command line: the steps the dft.atpg backend runs ----------------------------------------


def _option(args: list[str], name: str, default: str | None = None) -> str | None:
    return args[args.index(name) + 1] if name in args else default


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["generate"] and len(argv) >= 4:
            _, design_json, out, top = argv[:4]
            opts = argv[4:]
            doc = generate(Design.load(design_json, top), seed=int(_option(opts, "--seed", "1")),
                           limit=int(_option(opts, "--limit", "200")), random_only="--random-only" in opts,
                           fault_model=_option(opts, "--model", STUCK_AT))
            Path(out).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
            print(f"DFT-ATPG-GEN: {doc['faults_total']} faults, {len(doc['patterns'])} patterns, "
                  f"{len(doc['claims'])} claimed, {len(doc['untestable'])} proven undetectable, "
                  f"{len(doc['aborted'])} aborted ({doc['generator']}, {doc['fault_model']})")
            return 0
        if argv[:1] == ["inject"] and len(argv) >= 7:
            _, design_json, patterns, faulty_json, faults_json, tb, top = argv[:7]
            opts = argv[7:]
            netlist = json.loads(Path(design_json).read_text(encoding="utf-8"))
            doc = json.loads(Path(patterns).read_text(encoding="utf-8"))
            sample = int(_option(opts, "--sample", "0")) or None
            faulty, faults, text = inject(Design.from_json(netlist, top), netlist, doc, sample,
                                          int(_option(opts, "--seed", "1")), _option(opts, "--model", STUCK_AT))
            Path(faulty_json).write_text(json.dumps(faulty), encoding="utf-8")
            Path(faults_json).write_text(json.dumps(faults, indent=1) + "\n", encoding="utf-8")
            Path(tb).write_text(text, encoding="utf-8")
            note = f" (a sample of {faults['universe']})" if faults["sampled"] else ""
            print(f"DFT-ATPG-INJECT: {len(faults['faults'])} faults{note}, {faults['patterns']} patterns, "
                  f"{len(faults['claims'])} claims to check")
            return 0
    except (NetlistError, OSError, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"DFT-ERROR: {exc}")
        return 1
    print("usage: dft_atpg.py generate DESIGN.json OUT.json TOP [--seed N] [--limit N] [--random-only] [--model M] | "
          "inject DESIGN.json PATTERNS.json FAULTY.json FAULTS.json TB.v TOP [--sample N] [--seed N] [--model M]")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

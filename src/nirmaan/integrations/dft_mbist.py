"""March C- memory BIST: a synthesizable controller and the testbench that runs it on a memory.

Standard library only, for the reason ``dft_scan.py`` is: the ``dft.mbist``
backend runs it as a step between Yosys (which reads the memory's ports) and
Icarus (which runs the controller against the memory). Nothing here runs a
tool or claims that one ran.

The memory is single port and synchronous: ``clk``, ``we``, ``addr``,
``wdata``, and a registered ``rdata``, over the whole address space. Its read
latency is one cycle unless the module declares another with the attribute
``(* read_latency = N *)`` (M29); the testbench measures it before March C-.
With no memory as the top, every module of the elaborated hierarchy with that
interface is a memory, and each gets its own controller (M29).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONTROLLER = "nirmaan_mbist"
TB_TOP = "nirmaan_mbist_tb"
#: March C-, element by element: (direction, operations).
MARCH_C_MINUS = (("any", "w0"), ("up", "r0,w1"), ("up", "r1,w0"), ("down", "r0,w1"), ("down", "r1,w0"),
                 ("any", "r0"))
PORTS = ("clk", "we", "addr", "wdata", "rdata")
MAX_LATENCY = 8


class MemoryInterfaceError(ValueError):
    """The memory does not have the interface the controller drives."""


def memory_ports(netlist: dict, top: str) -> tuple[int, int]:
    """The address and data widths of ``top``, from Yosys's JSON; refuses any other interface."""
    module = netlist.get("modules", {}).get(top)
    if module is None:
        raise MemoryInterfaceError(f"no module {top!r} in the netlist")
    ports = module.get("ports", {})
    missing = [p for p in PORTS if p not in ports]
    if missing:
        raise MemoryInterfaceError(f"{top} lacks port(s) {', '.join(missing)}: the controller drives a single-port "
                           f"synchronous RAM ({', '.join(PORTS)})")
    width = {p: len(ports[p]["bits"]) for p in PORTS}
    wrong = [p for p in PORTS[:4] if ports[p]["direction"] != "input"] + (
        ["rdata"] if ports["rdata"]["direction"] != "output" else [])
    if wrong:
        raise MemoryInterfaceError(f"{top}: port(s) {', '.join(wrong)} have the wrong direction")
    if width["clk"] != 1 or width["we"] != 1 or width["wdata"] != width["rdata"] or width["addr"] > 16:
        raise MemoryInterfaceError(f"{top}: clk and we must be one bit, wdata and rdata the same width, addr at most 16 bits")
    return width["addr"], width["wdata"]


def read_latency(netlist: dict, module: str) -> int:
    """The read latency ``module`` declares with ``(* read_latency = N *)``, or 1."""
    value = str(netlist["modules"][module].get("attributes", {}).get("read_latency", "1")).strip()
    try:
        latency = int(value, 2) if value and set(value) <= {"0", "1"} and len(value) > 1 else int(value)
    except ValueError as exc:
        raise MemoryInterfaceError(f"{module}: read_latency {value!r} is not a whole number") from exc
    if not 1 <= latency <= MAX_LATENCY:
        raise MemoryInterfaceError(f"{module}: read_latency {latency} is outside 1 to {MAX_LATENCY}")
    return latency


def find_memories(netlist: dict, top: str | None = None) -> list[tuple[str, int, int, int]]:
    """(module, address width, data width, read latency) for each memory to test.

    The top alone when it has the memory interface; otherwise every module of
    the elaborated hierarchy that has it. Refuses when there is none.
    """
    modules = netlist.get("modules", {})
    if top is not None and top not in modules:
        raise MemoryInterfaceError(f"no module {top!r} in the netlist")
    if top is not None:
        try:
            aw, dw = memory_ports(netlist, top)
            return [(top, aw, dw, read_latency(netlist, top))]
        except MemoryInterfaceError:
            pass
    found = []
    for name in sorted(modules):
        if name == top:
            continue
        try:
            aw, dw = memory_ports(netlist, name)
        except MemoryInterfaceError:
            continue
        if name.startswith("$"):
            raise MemoryInterfaceError(f"memory {name} is instantiated with overridden parameters; run dft.mbist "
                                       f"on it directly")
        found.append((name, aw, dw, read_latency(netlist, name)))
    if not found:
        where = top or "the design"
        raise MemoryInterfaceError(f"no memory with the single-port interface ({', '.join(PORTS)}) in {where} or "
                                   f"its hierarchy")
    return found


def controller(aw: int, dw: int, latency: int = 1, name: str = CONTROLLER) -> str:
    """The March C- controller for a memory of 2**aw words of dw bits, in synthesizable Verilog."""
    top = (1 << aw) - 1
    waits = latency > 1
    cw = max((latency - 1).bit_length(), 1)
    read = ("A read takes two cycles: the address, then the compare of the registered data." if not waits else
            f"A read takes {1 + latency} cycles: the address, {latency - 1} wait(s), then the compare.")
    wait_decl = f"    reg [{cw - 1}:0]      wait_cnt;\n" if waits else ""
    wait_ready = " && (wait_cnt == " + f"{cw}'d0)" if waits else ""
    wait_reset = f"            wait_cnt <= {cw}'d0;\n" if waits else ""
    wait_load = f"                        wait_cnt <= {cw}'d{latency - 1};\n" if waits else ""
    check = ("                    if (mem_rdata != expected && !fail) begin" if not waits else
             f"                    if (wait_cnt != {cw}'d0) begin\n                        wait_cnt <= wait_cnt - {cw}'d1;"
             "\n                    end else if (mem_rdata != expected && !fail) begin")
    return f"""// March C- memory BIST controller: generated by nirmaan.integrations.dft_mbist.
// {{w0}} up(r0,w1) up(r1,w0) down(r0,w1) down(r1,w0) {{r0}}, solid backgrounds, over {top + 1} words of
// {dw} bits. {read}
`timescale 1ns / 1ps
module {name} (
    input  wire          clk,
    input  wire          rst_n,
    input  wire          start,
    output wire          mem_we,
    output wire          mem_re,
    output wire [{aw - 1}:0]  mem_addr,
    output wire [{dw - 1}:0]  mem_wdata,
    input  wire [{dw - 1}:0]  mem_rdata,
    output wire          busy,
    output reg           done,
    output reg           fail,
    output reg  [2:0]    fail_element,
    output reg  [{aw - 1}:0]  fail_addr
);
    localparam [1:0] IDLE = 2'd0, RUN = 2'd1, CHECK = 2'd2, FINISHED = 2'd3;
    localparam [{aw - 1}:0] FIRST = {aw}'d0, LAST = {aw}'d{top};

    reg [1:0]      state;
    reg [2:0]      element;
    reg [{aw - 1}:0]    addr;
    reg            op;
    reg [{dw - 1}:0]    expected;
{wait_decl}
    // The March C- table: elements 1 to 4 read then write; element 0 only writes, element 5 only reads.
    wire two_ops = (element != 3'd0) && (element != 3'd5);
    wire is_read = (element == 3'd5) || (two_ops && !op);
    wire value = ((element == 3'd1) || (element == 3'd3)) ? op :
                 ((element == 3'd2) || (element == 3'd4)) ? !op : 1'b0;
    wire down = (element == 3'd3) || (element == 3'd4);
    wire last = addr == (down ? FIRST : LAST);
    wire [2:0] next_element = element + 3'd1;
    wire next_down = (next_element == 3'd3) || (next_element == 3'd4);
    wire advance = ((state == RUN) && !is_read) || ((state == CHECK){wait_ready});

    assign mem_we = (state == RUN) && !is_read;
    assign mem_re = (state == RUN) && is_read;
    assign mem_addr = addr;
    assign mem_wdata = {{{dw}{{value}}}};
    assign busy = (state == RUN) || (state == CHECK);

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= IDLE;
            element <= 3'd0;
            addr <= FIRST;
            op <= 1'b0;
            expected <= {dw}'d0;
            done <= 1'b0;
            fail <= 1'b0;
            fail_element <= 3'd0;
            fail_addr <= FIRST;
{wait_reset}        end else begin
            case (state)
                IDLE: begin
                    if (start) begin
                        state <= RUN;
                        element <= 3'd0;
                        addr <= FIRST;
                        op <= 1'b0;
                        done <= 1'b0;
                        fail <= 1'b0;
                    end
                end
                RUN: begin
                    if (is_read) begin
                        expected <= {{{dw}{{value}}}};
                        state <= CHECK;
{wait_load}                    end
                end
                CHECK: begin
{check}
                        fail <= 1'b1;
                        fail_element <= element;
                        fail_addr <= addr;
                    end
                end
                default: begin
                end
            endcase
            if (advance) begin
                state <= RUN;
                if (two_ops && !op) begin
                    op <= 1'b1;
                end else begin
                    op <= 1'b0;
                    if (!last) begin
                        addr <= down ? addr - {aw}'d1 : addr + {aw}'d1;
                    end else if (element == 3'd5) begin
                        state <= FINISHED;
                        done <= 1'b1;
                    end else begin
                        element <= next_element;
                        addr <= next_down ? LAST : FIRST;
                    end
                end
            end
        end
    end
endmodule
"""


def _controller_name(k: int, count: int) -> str:
    return CONTROLLER if count == 1 else f"{CONTROLLER}_{k}"


def testbench(memories: list[tuple[str, int, int, int]]) -> str:
    """Connect a controller to each memory, measure its read latency, run March C- on all, and count."""
    count = len(memories)
    decls, insts, counts, probe_checks, inits, starts, reports = [], [], [], [], [], [], []
    limit = max((20 + 10 * lat) * (1 << aw) + 100 for _, aw, _, lat in memories)
    for k, (top, aw, dw, lat) in enumerate(memories):
        m = f"m{k}"
        decls.append(f"""  // {top}: {1 << aw} words of {dw} bits, declared read latency {lat}.
  wire {m}_we, {m}_re, {m}_busy, {m}_done, {m}_fail;
  wire [{aw - 1}:0] {m}_addr, {m}_fail_addr;
  wire [{dw - 1}:0] {m}_wdata, {m}_rdata;
  wire [2:0] {m}_fail_element;
  wire {m}_mem_we = probing ? p_we : {m}_we;
  wire [{aw - 1}:0] {m}_mem_addr = probing ? p_addr[{aw - 1}:0] : {m}_addr;
  wire [{dw - 1}:0] {m}_mem_wdata = probing ? {{{dw}{{p_one}}}} : {m}_wdata;
  reg [{lat - 1}:0] {m}_checking;
  integer {m}_reads, {m}_writes, {m}_cycles, {m}_x, {m}_measured;""")
        insts.append(f"""  {top} mem{k} (.clk(clk), .we({m}_mem_we), .addr({m}_mem_addr), .wdata({m}_mem_wdata),
      .rdata({m}_rdata));
  {_controller_name(k, count)} bist{k} (.clk(clk), .rst_n(rst_n), .start(start), .mem_we({m}_we), .mem_re({m}_re),
      .mem_addr({m}_addr), .mem_wdata({m}_wdata), .mem_rdata({m}_rdata), .busy({m}_busy), .done({m}_done),
      .fail({m}_fail), .fail_element({m}_fail_element), .fail_addr({m}_fail_addr));""")
        shift = f"{m}_re" if lat == 1 else f"{{{m}_checking[{lat - 2}:0], {m}_re}}"
        counts.append(f"""    if ({m}_checking[{lat - 1}] && ^{m}_rdata === 1'bx)
      {m}_x = {m}_x + 1;
    {m}_checking <= {shift};
    if ({m}_busy) begin
      {m}_cycles = {m}_cycles + 1;
      if ({m}_we)
        {m}_writes = {m}_writes + 1;
      if ({m}_re)
        {m}_reads = {m}_reads + 1;
    end""")
        probe_checks.append(f"      if ({m}_measured == 0 && {m}_rdata === {{{dw}{{1'b1}}}})\n        {m}_measured = c;")
        inits.append(f"    {m}_checking = {lat}'d0; {m}_reads = 0; {m}_writes = 0; {m}_cycles = 0; {m}_x = 0; "
                     f"{m}_measured = 0;")
        reports.append(f"""    $write("DFT-MBIST: {top} march C-, latency {lat}, measured %0d, words {1 << aw}, width {dw}, ", {m}_measured);
    $write("reads %0d, writes %0d, cycles %0d, ", {m}_reads, {m}_writes, {m}_cycles);
    $display("x reads %0d, done %0d, fail %0d, element %0d, address %0d", {m}_x, {m}_done, {m}_fail,
             {m}_fail_element, {m}_fail_addr);""")
    names = ", ".join(t for t, *_ in memories)
    all_done = " && ".join(f"m{k}_done" for k in range(count))
    any_busy = " || ".join(f"m{k}_busy" for k in range(count))
    return f"""`timescale 1ns / 1ps
// March C- on {names}: generated by nirmaan.integrations.dft_mbist.
module {TB_TOP};
  reg clk, rst_n, start, probing, p_we, p_one;
  reg [15:0] p_addr;
  integer c;
{chr(10).join(decls)}

{chr(10).join(insts)}

  always #5 clk = ~clk;

  // Count every operation each controller makes, independently of its own verdict.
  always @(posedge clk) begin
{chr(10).join(counts)}
  end

  initial begin
    clk = 1'b0;
    rst_n = 1'b0;
    start = 1'b0;
    probing = 1'b1;
    p_we = 1'b0;
    p_one = 1'b0;
    p_addr = 16'd0;
{chr(10).join(inits)}
    // Measure the read latency: word 0 all zeros, word 1 all ones, then switch the address from 0 to 1.
    @(negedge clk);
    p_we = 1'b1;
    @(negedge clk);
    p_addr = 16'd1;
    p_one = 1'b1;
    @(negedge clk);
    p_we = 1'b0;
    p_addr = 16'd0;
    repeat ({MAX_LATENCY + 1}) @(negedge clk);
    p_addr = 16'd1;
    for (c = 1; c <= {MAX_LATENCY}; c = c + 1) begin
      @(negedge clk);
{chr(10).join(probe_checks)}
    end
    probing = 1'b0;
    @(negedge clk);
    rst_n = 1'b1;
    @(negedge clk);
    start = 1'b1;
    @(negedge clk);
    start = 1'b0;
    c = 0;
    while (!({all_done}) && c < {limit}) begin
      @(negedge clk);
      c = c + 1;
    end
    if ({any_busy})
      $display("DFT-MBIST-TIMEOUT: a controller was still busy after %0d cycles", c);
{chr(10).join(reports)}
    $finish;
  end
endmodule
"""


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["generate"] and len(argv) in (4, 5):
            ports_json, controller_v, tb_v = argv[1:4]
            top = argv[4] if len(argv) == 5 and argv[4] else None
            memories = find_memories(json.loads(Path(ports_json).read_text(encoding="utf-8")), top)
            text = "\n".join(controller(aw, dw, lat, _controller_name(k, len(memories)))
                             for k, (_, aw, dw, lat) in enumerate(memories))
            Path(controller_v).write_text(text, encoding="utf-8")
            Path(tb_v).write_text(testbench(memories), encoding="utf-8")
            for name, aw, dw, lat in memories:
                print(f"DFT-MBIST-GEN: March C- for {name}, {1 << aw} words of {dw} bits, read latency {lat}")
            return 0
    except (MemoryInterfaceError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"DFT-ERROR: {exc}")
        return 1
    print("usage: dft_mbist.py generate PORTS.json CONTROLLER.v TB.v [TOP]")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

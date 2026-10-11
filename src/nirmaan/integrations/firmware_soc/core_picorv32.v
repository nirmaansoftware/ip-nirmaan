// core_picorv32.v: PicoRV32 behind the SoC's memory interface, for fw.soc_test.
//
// The core (picorv32.v, vendored unmodified, ISC license) is built with its
// defaults (RV32I; misaligned accesses and illegal instructions trap) except
// that its cycle counters are off, since the SoC's CYCLES register serves, and
// its interrupts are on (docs/RISCV_NEXT.md, section 2):
//   * the design's irq is irq[3]; 0 to 2 are the core's own (timer, ebreak,
//     misalignment), which stay masked, so those still trap;
//   * irq[3] is level sensitive (LATCHED_IRQ bit 3 clear): an interrupt that
//     is not acknowledged is taken again on return;
//   * bus_err is irq[4] (M35, docs/FIRMWARE_IRQ_TRAPS.md), level sensitive too:
//     the SoC raises it with mem_ready for a device access that got an error,
//     and PicoRV32 checks its pending lines before the next instruction runs,
//     so the trap is taken right after the faulting load or store;
//   * the core enters the runtime at 0x10 with the return address in q0
//     (ENABLE_IRQ_QREGS), and returns with retirq.
// The SoC's memory interface is PicoRV32's own, so this is a pass-through.
`timescale 1ns / 1ps
module nirmaan_core_picorv32 (
    input  wire        clk,
    input  wire        resetn,
    output wire        trap,
    output wire        mem_valid,
    input  wire        mem_ready,
    output wire [31:0] mem_addr,
    output wire [31:0] mem_wdata,
    output wire [3:0]  mem_wstrb,
    input  wire [31:0] mem_rdata,
    input  wire        irq,
    input  wire        bus_err
);
    /* verilator lint_off PINCONNECTEMPTY */
    picorv32 #(
        .ENABLE_COUNTERS(0),
        .ENABLE_IRQ(1),
        .ENABLE_IRQ_QREGS(1),
        .ENABLE_IRQ_TIMER(0),
        .LATCHED_IRQ(32'hffff_ffe7),
        .PROGADDR_IRQ(32'h0000_0010)
    ) cpu (
        .clk(clk), .resetn(resetn), .trap(trap),
        .mem_valid(mem_valid), .mem_instr(), .mem_ready(mem_ready),
        .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb), .mem_rdata(mem_rdata),
        .mem_la_read(), .mem_la_write(), .mem_la_addr(), .mem_la_wdata(), .mem_la_wstrb(),
        .pcpi_valid(), .pcpi_insn(), .pcpi_rs1(), .pcpi_rs2(),
        .pcpi_wr(1'b0), .pcpi_rd(32'b0), .pcpi_wait(1'b0), .pcpi_ready(1'b0),
        .irq({27'b0, bus_err, irq, 3'b0}), .eoi(),
        .trace_valid(), .trace_data()
    );
    /* verilator lint_on PINCONNECTEMPTY */
endmodule

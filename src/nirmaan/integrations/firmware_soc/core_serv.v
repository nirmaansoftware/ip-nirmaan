// core_serv.v: SERV behind the SoC's memory interface, for fw.soc_test.
//
// SERV (serv/, vendored unmodified, ISC license) is a bit-serial RV32I core
// with Wishbone instruction and data buses. It is built with its CSRs
// (WITH_CSR=1), so it has mtvec, mepc, mcause, mstatus.MIE and mie.MTIE, and
// mret. Its one interrupt input, i_timer_irq, carries the design's irq
// (docs/RISCV_NEXT.md, section 2); the runtime points mtvec at 0x10.
//
// The SoC's memory interface is PicoRV32's: mem_valid until a one-cycle
// mem_ready, a word-aligned mem_addr, and a nonzero mem_wstrb for a store.
// SERV never has both buses active at once, so they share it (as SERV's own
// servile_arbiter shares them); SERV puts a byte store's byte address on the
// bus, and the SoC wants the word and the strobe, so the address is aligned.
// SERV has no trap output: its exceptions go through mtvec, and the runtime
// reports them.
`timescale 1ns / 1ps
module nirmaan_core_serv (
    input  wire        clk,
    input  wire        resetn,
    output wire        trap,
    output wire        mem_valid,
    input  wire        mem_ready,
    output wire [31:0] mem_addr,
    output wire [31:0] mem_wdata,
    output wire [3:0]  mem_wstrb,
    input  wire [31:0] mem_rdata,
    input  wire        irq
);
    wire [31:0] ibus_adr, dbus_adr;
    wire        ibus_cyc, dbus_cyc, dbus_we;
    wire [3:0]  dbus_sel;

    /* verilator lint_off PINCONNECTEMPTY */
    serv_rf_top #(
        .RESET_PC(32'h0000_0000),
        .WITH_CSR(1)
    ) cpu (
        .clk(clk), .i_rst(!resetn), .i_timer_irq(irq),
        .o_ibus_adr(ibus_adr), .o_ibus_cyc(ibus_cyc), .i_ibus_rdt(mem_rdata), .i_ibus_ack(mem_ready && ibus_cyc),
        .o_dbus_adr(dbus_adr), .o_dbus_dat(mem_wdata), .o_dbus_sel(dbus_sel), .o_dbus_we(dbus_we),
        .o_dbus_cyc(dbus_cyc), .i_dbus_rdt(mem_rdata), .i_dbus_ack(mem_ready && !ibus_cyc),
        .o_ext_rs1(), .o_ext_rs2(), .o_ext_funct3(), .i_ext_rd(32'b0), .i_ext_ready(1'b0),
        .o_mdu_valid()
    );
    /* verilator lint_on PINCONNECTEMPTY */

    assign mem_valid = ibus_cyc || dbus_cyc;
    assign mem_addr = {ibus_cyc ? ibus_adr[31:2] : dbus_adr[31:2], 2'b00};
    assign mem_wstrb = (dbus_cyc && dbus_we && !ibus_cyc) ? dbus_sel : 4'b0000;
    assign trap = 1'b0;
endmodule

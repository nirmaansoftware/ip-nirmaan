// bridge_apb.v: an APB4 manager for the SoC's device window, for fw.soc_test.
//
// The design is instantiated as `NIRMAAN_DUT, a macro the build defines, so
// this file names no design. It needs the APB4 subordinate port convention:
// pclk, presetn, paddr, psel, penable, pwrite, pwdata, pstrb, prdata, pready,
// and pslverr, with 32-bit data; and, when the build defines NIRMAAN_DUT_IRQ,
// a one-bit irq output, which goes to the core (docs/RISCV_NEXT.md).
//
// Each transfer is a setup phase (psel) and then an access phase (penable)
// held until pready. pstrb is the CPU store's strobe on a write and zero on a
// read, as APB4 requires. PSLVERR is reported as SLVERR (2), so a driver sees
// the same response codes on either bus. The SoC side is the same as
// bridge_axil.v's; the SoC times out a transfer that never completes.
`timescale 1ns / 1ps
module nirmaan_bridge_apb (
    input  wire        clk,
    input  wire        resetn,
    input  wire        req,
    input  wire        write,
    input  wire [9:0]  offset,
    input  wire [31:0] wdata,
    input  wire [3:0]  wstrb,
    output reg         done,
    output reg  [31:0] rdata,
    output reg  [1:0]  resp,
    output wire        irq
);
    reg  [31:0] paddr, pwdata;
    reg  [3:0]  pstrb;
    reg         psel, penable, pwrite;
    wire [31:0] prdata;
    wire        pready, pslverr;

    /* verilator lint_off WIDTH */
    `NIRMAAN_DUT dut (
`ifdef NIRMAAN_DUT_IRQ
        .irq(irq),
`endif
        .pclk(clk), .presetn(resetn),
        .paddr(paddr), .psel(psel), .penable(penable), .pwrite(pwrite),
        .pwdata(pwdata), .pstrb(pstrb),
        .prdata(prdata), .pready(pready), .pslverr(pslverr)
    );
    /* verilator lint_on WIDTH */
`ifndef NIRMAAN_DUT_IRQ
    assign irq = 1'b0;
`endif

    always @(posedge clk) begin
        if (!resetn) begin
            done <= 1'b0;
            rdata <= 32'd0;
            resp <= 2'd0;
            paddr <= 32'd0;
            pwdata <= 32'd0;
            pstrb <= 4'd0;
            psel <= 1'b0;
            penable <= 1'b0;
            pwrite <= 1'b0;
        end else begin
            done <= 1'b0;
            if (req) begin
                // Setup phase.
                paddr <= {22'b0, offset};
                pwrite <= write;
                pwdata <= write ? wdata : 32'd0;
                pstrb <= write ? wstrb : 4'd0;
                psel <= 1'b1;
                penable <= 1'b0;
            end else if (psel && !penable) begin
                // Access phase.
                penable <= 1'b1;
            end else if (psel && penable && pready) begin
                psel <= 1'b0;
                penable <= 1'b0;
                resp <= pslverr ? 2'd2 : 2'd0;
                rdata <= pwrite ? 32'd0 : prdata;
                done <= 1'b1;
            end
        end
    end
endmodule

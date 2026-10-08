// bridge_axil.v: an AXI4-Lite manager for the SoC's device window, for fw.soc_test.
//
// The design is instantiated as `NIRMAAN_DUT, a macro the build defines, so
// this file names no design. It needs the AXI4-Lite subordinate port
// convention of fw.test: aclk, aresetn, and s_axil_* with 32-bit data; and,
// when the build defines NIRMAAN_DUT_IRQ, a one-bit irq output, which goes to
// the core (docs/RISCV_NEXT.md, section 2).
//
// The SoC side: a one-cycle req with the transfer (write, offset, wdata,
// wstrb), and a one-cycle done with rdata and the response code (BRESP or
// RRESP). The SoC times out a transfer that never completes.
`timescale 1ns / 1ps
module nirmaan_bridge_axil (
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
    reg  [31:0] awaddr, araddr, w_data;
    reg  [3:0]  w_strb;
    reg         awvalid, wvalid, bready, arvalid, rready;
    wire        awready, wready, bvalid, arready, rvalid;
    wire [1:0]  bresp, rresp;
    wire [31:0] r_data;

    /* verilator lint_off WIDTH */
    `NIRMAAN_DUT dut (
`ifdef NIRMAAN_DUT_IRQ
        .irq(irq),
`endif
        .aclk(clk), .aresetn(resetn),
        .s_axil_awaddr(awaddr), .s_axil_awvalid(awvalid), .s_axil_awready(awready),
        .s_axil_wdata(w_data), .s_axil_wstrb(w_strb), .s_axil_wvalid(wvalid), .s_axil_wready(wready),
        .s_axil_bresp(bresp), .s_axil_bvalid(bvalid), .s_axil_bready(bready),
        .s_axil_araddr(araddr), .s_axil_arvalid(arvalid), .s_axil_arready(arready),
        .s_axil_rdata(r_data), .s_axil_rresp(rresp), .s_axil_rvalid(rvalid), .s_axil_rready(rready)
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
            awvalid <= 1'b0;
            wvalid <= 1'b0;
            bready <= 1'b0;
            arvalid <= 1'b0;
            rready <= 1'b0;
        end else begin
            done <= 1'b0;
            if (req && write) begin
                awaddr <= {22'b0, offset};
                w_data <= wdata;
                w_strb <= wstrb;
                awvalid <= 1'b1;
                wvalid <= 1'b1;
                bready <= 1'b1;
            end
            if (req && !write) begin
                araddr <= {22'b0, offset};
                arvalid <= 1'b1;
                rready <= 1'b1;
            end
            if (awvalid && awready) awvalid <= 1'b0;
            if (wvalid && wready) wvalid <= 1'b0;
            if (bvalid && bready) begin
                bready <= 1'b0;
                resp <= bresp;
                done <= 1'b1;
            end
            if (arvalid && arready) arvalid <= 1'b0;
            if (rvalid && rready) begin
                rready <= 1'b0;
                resp <= rresp;
                rdata <= r_data;
                done <= 1'b1;
            end
        end
    end
endmodule

// A weak testbench for irq_ctrl.v (W2-E5): it enables every source once and
// never masks one, runs level mode only (MODE is never written), and acknowledges
// and clears normally. Every check passes on the approved RTL; the rising-edge
// path and the mask never run, so coverage falls below the bounds
// (docs/COVERAGE_READ.md). A must-fail control of the coverage bounds.
`timescale 1ns / 1ps
module irq_ctrl_no_mask_tb;
    logic        clk = 1'b0;
    logic        rst_n = 1'b0;
    logic [7:0]  src = '0;
    logic        we = 1'b0;
    logic [1:0]  addr = 2'd0;
    logic [31:0] wdata = 32'd0;
    logic [31:0] rdata;
    logic        irq;
    logic [4:0]  irq_id;
    int checks = 0, errors = 0;
    logic [8*64-1:0] nonce;

    irq_ctrl #(.N(8)) dut (.clk(clk), .rst_n(rst_n), .src(src), .we(we), .addr(addr), .wdata(wdata),
                           .rdata(rdata), .irq(irq), .irq_id(irq_id));
    always #5 clk = ~clk;

    task automatic write(input logic [1:0] a, input logic [31:0] d);
        we = 1'b1; addr = a; wdata = d;
        @(posedge clk); #1;
        we = 1'b0;
    endtask

    task automatic expect_claim(input logic valid, input logic [4:0] id);
        addr = 2'd3;
        #1;
        checks += 2;
        if (irq !== valid) errors++;
        if (irq_id !== id) errors++;
    endtask

    initial begin
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk); #1;
        write(2'd0, 32'hFF);
        src = 8'b0000_0110;
        @(posedge clk); #1;
        src = '0;
        @(posedge clk); #1;
        expect_claim(1'b1, 5'd1);
        write(2'd3, 32'd1);
        expect_claim(1'b1, 5'd2);
        write(2'd2, 32'h4);
        expect_claim(1'b0, 5'd0);
        if (!$value$plusargs("nirmaan_nonce=%s", nonce)) nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule

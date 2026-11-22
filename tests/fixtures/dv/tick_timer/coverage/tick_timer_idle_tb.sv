// A weak testbench for tick_timer.v (RX-E2): it resets the block, checks the
// reset values and the CTRL read back, then stops. It never starts the timer,
// so nothing counts, expires or clears. Every check passes on the approved RTL,
// and the line and toggle coverage is far below the bounds
// (docs/COVERAGE_READ.md). It is the "approved testbench" the coverage case
// hands the seat to extend, and a must-fail control of the coverage bounds.
`timescale 1ns / 1ps
module tick_timer_idle_tb;
    logic        clk = 1'b0;
    logic        rst_n = 1'b0;
    logic        we = 1'b0;
    logic [1:0]  addr = 2'd0;
    logic [31:0] wdata = 32'd0;
    logic [31:0] rdata;
    logic        irq;
    int checks = 0, errors = 0;
    logic [8*64-1:0] nonce;

    tick_timer #(.W(16)) dut (.clk(clk), .rst_n(rst_n), .we(we), .addr(addr), .wdata(wdata), .rdata(rdata), .irq(irq));
    always #5 clk = ~clk;

    task automatic expect_reg(input logic [1:0] a, input logic [31:0] expected);
        addr = a;
        #1;
        checks++;
        if (rdata !== expected) errors++;
    endtask

    task automatic write(input logic [1:0] a, input logic [31:0] d);
        we = 1'b1; addr = a; wdata = d;
        @(posedge clk); #1;
        we = 1'b0; wdata = 32'd0;
    endtask

    initial begin
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);
        #1;
        expect_reg(2'd0, 32'd0);
        expect_reg(2'd1, 32'd0);
        expect_reg(2'd2, 32'd0);
        expect_reg(2'd3, 32'd0);
        write(2'd0, 32'h0000_0006);
        expect_reg(2'd0, 32'h0000_0006);
        if (!$value$plusargs("nirmaan_nonce=%s", nonce)) nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule

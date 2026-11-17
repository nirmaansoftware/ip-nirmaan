// A testbench that checks next to nothing, on purpose (a whole-flow judge
// control, council record 2026-11-17, decision 2). It resets the timer and
// checks one thing: irq is low after reset. A seat that submits it with a
// wrong RTL reaches review, so the judge's own checks on that RTL are what
// must fail it; the must-fail check must fail the testbench itself.
`timescale 1ns / 1ps
module axil_timer_tb_trivial;
    reg aclk = 1'b0;
    reg aresetn = 1'b0;
    wire awready, wready, bvalid, arready, rvalid, irq;
    wire [1:0] bresp, rresp;
    wire [31:0] rdata;
    always #5 aclk = ~aclk;
    axil_timer dut (
        .aclk(aclk), .aresetn(aresetn),
        .s_axil_awaddr(4'd0), .s_axil_awvalid(1'b0), .s_axil_awready(awready),
        .s_axil_wdata(32'd0), .s_axil_wstrb(4'd0), .s_axil_wvalid(1'b0), .s_axil_wready(wready),
        .s_axil_bresp(bresp), .s_axil_bvalid(bvalid), .s_axil_bready(1'b0),
        .s_axil_araddr(4'd0), .s_axil_arvalid(1'b0), .s_axil_arready(arready),
        .s_axil_rdata(rdata), .s_axil_rresp(rresp), .s_axil_rvalid(rvalid), .s_axil_rready(1'b0),
        .irq(irq)
    );
    reg [8*64-1:0] nonce;
    initial begin
        #20 aresetn = 1'b1;
        #50 if (!$value$plusargs("nirmaan_nonce=%s", nonce)) nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, irq === 1'b0, irq !== 1'b0);
        $finish;
    end
endmodule

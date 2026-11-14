// Coverage fixture (M70): a self-checking testbench for ../rtl/counter.v that passes and exercises
// almost nothing. It holds the counter in reset and checks that the count stays 0, so its checks pass,
// but the counting, the wrap and the hold are never reached: the coverage bounds that counter_full_tb.v
// meets must fail here.
`timescale 1ns / 1ps
module counter_idle_tb;
    reg clk = 1'b0;
    reg rst = 1'b1;
    reg en = 1'b0;
    wire [3:0] count;
    wire wrap;
    integer errors = 0;
    integer checks = 0;
    reg [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line
    integer i;

    counter #(.LIMIT(4'd9)) dut (.clk(clk), .rst(rst), .en(en), .count(count), .wrap(wrap));

    always #5 clk = ~clk;

    initial begin
        for (i = 0; i < 4; i = i + 1) begin
            @(negedge clk);
            checks = checks + 1;
            if (count !== 4'd0) begin
                $display("ERROR: count is %0d in reset, expected 0", count);
                errors = errors + 1;
            end
        end
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule

// Coverage fixture (M70): a self-checking testbench for ../rtl/counter.v that exercises all of it.
// It counts through a wrap, holds with en low, and resets in the middle of a count, so every line,
// branch and toggle of the counter is reached. Its pair, counter_idle_tb.v, passes its checks too
// but holds the counter in reset, so the same coverage bounds pass here and fail there.
`timescale 1ns / 1ps
module counter_full_tb;
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

    task check(input [3:0] expected);
        begin
            checks = checks + 1;
            if (count !== expected) begin
                $display("ERROR: count is %0d, expected %0d", count, expected);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        @(negedge clk);
        rst = 1'b0;
        en = 1'b1;
        for (i = 1; i <= 12; i = i + 1) begin  // through the wrap at 9
            @(negedge clk);
            check(i % 10);
        end
        en = 1'b0;  // hold
        @(negedge clk);
        check(4'd2);
        @(negedge clk);
        check(4'd2);
        en = 1'b1;
        rst = 1'b1;  // reset in the middle of a count
        @(negedge clk);
        check(4'd0);
        rst = 1'b0;
        @(negedge clk);
        check(4'd1);
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule

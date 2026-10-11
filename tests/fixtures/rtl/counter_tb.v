// Self-checking testbench for counter.v: counts to LIMIT, wraps, and finishes.
`timescale 1ns / 1ps
module counter_tb;
    reg clk = 1'b0;
    reg rst = 1'b1;
    reg en = 1'b0;
    wire [3:0] count;
    wire wrap;
    integer errors = 0;
    integer i;

    counter #(.LIMIT(4'd9)) dut (.clk(clk), .rst(rst), .en(en), .count(count), .wrap(wrap));

    always #5 clk = ~clk;

    initial begin
        @(negedge clk);
        rst = 1'b0;
        en = 1'b1;
        for (i = 1; i <= 12; i = i + 1) begin
            @(negedge clk);
            if (count !== i % 10) begin
                $display("ERROR: cycle %0d: count is %0d, expected %0d", i, count, i % 10);
                errors = errors + 1;
            end
        end
        if (errors == 0)
            $display("counter_tb: PASS");
        $finish;
    end
endmodule

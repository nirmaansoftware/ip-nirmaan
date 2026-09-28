// A testbench that is wrong on purpose: it expects the counter to wrap at 8.
// Used to prove a failing simulation is a recorded, failed run.
`timescale 1ns / 1ps
module counter_tb_fail;
    reg clk = 1'b0;
    reg rst = 1'b1;
    reg en = 1'b0;
    wire [3:0] count;
    wire wrap;
    integer i;

    counter #(.LIMIT(4'd9)) dut (.clk(clk), .rst(rst), .en(en), .count(count), .wrap(wrap));

    always #5 clk = ~clk;

    initial begin
        @(negedge clk);
        rst = 1'b0;
        en = 1'b1;
        for (i = 1; i <= 12; i = i + 1) begin
            @(negedge clk);
            if (count !== i % 9)
                $error("cycle %0d: count is %0d, expected %0d", i, count, i % 9);
        end
        $finish;
    end
endmodule

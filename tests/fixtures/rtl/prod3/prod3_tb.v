// Self-checking testbench for the pipelined prod3.v: y follows a, b, c three clock
// edges later (the input registers, then two stages), over pseudo-random inputs.
// The unpipelined before/prod3.v has one stage fewer, and fails it.
`timescale 1ns / 1ps
module prod3_tb;
    reg clk = 1'b0;
    reg [15:0] a = 16'd0, b = 16'd0, c = 16'd0;
    wire [31:0] y;
    reg [31:0] expected [0:2];
    integer errors = 0;
    integer i;

    prod3 dut (.clk(clk), .a(a), .b(b), .c(c), .y(y));

    always #5 clk = ~clk;

    initial begin
        expected[0] = 32'd0;
        expected[1] = 32'd0;
        expected[2] = 32'd0;
        for (i = 0; i < 40; i = i + 1) begin
            @(negedge clk);
            if (i >= 3 && y !== expected[i % 3]) begin
                $display("ERROR: step %0d: y is %0d, expected %0d", i, y, expected[i % 3]);
                errors = errors + 1;
            end
            a = $random;
            b = $random;
            c = $random;
            expected[i % 3] = a * b * c;
        end
        if (errors == 0)
            $display("prod3_tb: PASS");
        $finish;
    end
endmodule

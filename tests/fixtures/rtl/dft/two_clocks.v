// Three clock domains for multi-chain scan: the M27 fixture. `a` runs on the
// rising edge of clk_a (with an asynchronous reset), `b` on the rising edge of
// clk_b and reads `a`, and `c` on the falling edge of clk_a and reads `b`.
`timescale 1ns / 1ps
module two_clocks (
    input  wire       clk_a,
    input  wire       clk_b,
    input  wire       rst_n,
    input  wire [3:0] d,
    output reg  [3:0] a,
    output reg  [3:0] b,
    output reg  [3:0] c
);
    always @(posedge clk_a or negedge rst_n)
        if (!rst_n)
            a <= 4'd0;
        else
            a <= a + d;

    always @(posedge clk_b)
        b <= b ^ a;

    always @(negedge clk_a)
        c <= c + b;
endmodule

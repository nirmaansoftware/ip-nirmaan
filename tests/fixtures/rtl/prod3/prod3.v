// The M37 timing-closure fixture, after the fix: the same y = a * b * c (low 32
// bits), with a register between the two multiplies. Two cycles of latency.
`timescale 1ns / 1ps
module prod3 (
    input  wire        clk,
    input  wire [15:0] a,
    input  wire [15:0] b,
    input  wire [15:0] c,
    output reg  [31:0] y
);
    reg  [15:0] a_q, b_q, c_q, c_d;
    reg  [31:0] ab;
    wire [31:0] abc = ab * {16'b0, c_d};

    always @(posedge clk) begin
        a_q <= a;
        b_q <= b;
        c_q <= c;
        ab  <= {16'b0, a_q} * {16'b0, b_q};
        c_d <= c_q;
        y   <= abc;
    end
endmodule

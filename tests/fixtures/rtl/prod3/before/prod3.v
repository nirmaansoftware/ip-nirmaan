// The M37 timing-closure fixture, before the fix: y = a * b * c (low 32 bits),
// with both multiplies between one register and the next. One cycle of latency.
`timescale 1ns / 1ps
module prod3 (
    input  wire        clk,
    input  wire [15:0] a,
    input  wire [15:0] b,
    input  wire [15:0] c,
    output reg  [31:0] y
);
    reg  [15:0] a_q, b_q, c_q;
    wire [31:0] ab  = {16'b0, a_q} * {16'b0, b_q};
    wire [31:0] abc = ab * {16'b0, c_q};

    always @(posedge clk) begin
        a_q <= a;
        b_q <= b;
        c_q <= c;
        y   <= abc;
    end
endmodule

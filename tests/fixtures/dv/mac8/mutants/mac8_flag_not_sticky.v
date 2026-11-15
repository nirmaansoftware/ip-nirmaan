// A mutant that is wrong on purpose (W2-E6): mac8.v with one change.
// The flag follows the latest accumulate instead of staying high. Everything else is identical.
//
// Multiply-accumulate block with a saturating 24-bit total (W2-E6): unsigned
// 8-bit operands, a sticky saturation flag, clear wins over an accumulate. The
// approved RTL of the eval case dv/scoreboard-mac: see interface_spec.md and
// microarchitecture.md.
`timescale 1ns / 1ps
module mac8 (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        clr,
    input  wire        en,
    input  wire [7:0]  a,
    input  wire [7:0]  b,
    output reg  [23:0] acc,
    output reg         sat
);
    wire [15:0] prod = a * b;
    wire [24:0] sum = {1'b0, acc} + {9'd0, prod};

    always @(posedge clk) begin
        if (!rst_n || clr) begin
            acc <= 24'd0;
            sat <= 1'b0;
        end else if (en) begin
            if (sum[24]) begin
                acc <= 24'hFFFFFF;
                sat <= 1'b1;
            end else begin
                acc <= sum[23:0];
                sat <= 1'b0;
            end
        end
    end
endmodule

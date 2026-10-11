// A scan design with a broken chain: the M25 fixture. `b` has no scan mux, so
// with scan_en high it still loads functional data and is left off the chain
// scan_in -> a -> c -> scan_out.
`timescale 1ns / 1ps
module broken_chain (
    input  wire clk,
    input  wire d,
    input  wire scan_en,
    input  wire scan_in,
    output wire scan_out,
    output wire q
);
    reg a, b, c;
    always @(posedge clk) begin
        a <= scan_en ? scan_in : d;
        b <= a ^ d;
        c <= scan_en ? a : b;
    end
    assign scan_out = c;
    assign q = c;
endmodule

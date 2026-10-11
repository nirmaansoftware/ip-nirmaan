// Deliberately untestable: the M25 fixture for DFT rule violations.
// * `held` is a latch (transparent while `en` is high).
// * `slow` is clocked by a gated clock (`clk & en`), which a tester cannot control.
// * `div` is clocked by a divided clock, a flop's output.
// * `loop_a` and `loop_b` form a combinational loop.
`timescale 1ns / 1ps
module untestable (
    input  wire clk,
    input  wire en,
    input  wire d,
    output reg  held,
    output reg  slow,
    output reg  div,
    output reg  fast,
    output wire loop_a
);
    wire loop_b;
    assign loop_a = d ^ loop_b;
    assign loop_b = en & loop_a;

    always @(*)
        if (en)
            held = d;

    wire gclk = clk & en;
    always @(posedge gclk)
        slow <= d;

    always @(posedge clk)
        fast <= ~fast;

    always @(posedge fast)
        div <= d;
endmodule

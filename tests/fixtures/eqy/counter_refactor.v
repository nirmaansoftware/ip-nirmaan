// M69: the M21 counter (tests/fixtures/rtl/counter.v), rewritten as one next-state
// expression. Equivalent to it: eqy proves every partition.
`timescale 1ns / 1ps
module counter #(
    parameter [3:0] LIMIT = 4'd9
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    output reg  [3:0] count,
    output wire       wrap
);
    assign wrap = en & (count == LIMIT);
    wire [3:0] next = (rst | wrap) ? 4'd0 : count + {3'd0, en};

    always @(posedge clk)
        count <= next;
endmodule

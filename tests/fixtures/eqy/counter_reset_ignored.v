// M69: a must-fail refactor of the M21 counter. One change: reset does not
// clear the count while en is low, so it is not equivalent and eqy must fail it.
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
    wire [3:0] next = ((rst & en) | wrap) ? 4'd0 : count + {3'd0, en};

    always @(posedge clk)
        count <= next;
endmodule

// M69: a must-fail refactor of the M21 counter. One change: it wraps one count
// early (at LIMIT - 1), so it is not equivalent and eqy must fail it.
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
    assign wrap = en & (count == LIMIT - 4'd1);
    wire [3:0] next = (rst | wrap) ? 4'd0 : count + {3'd0, en};

    always @(posedge clk)
        count <= next;
endmodule

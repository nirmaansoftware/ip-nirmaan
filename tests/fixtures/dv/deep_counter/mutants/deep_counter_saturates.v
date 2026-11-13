// A mutant that is wrong on purpose (W2-E2): deep_counter.v with one change.
// The count stops at LIMIT instead of returning to 0 (carry stays high while
// en is), 100 enabled cycles after reset. Everything else is identical.
//
// Modulo counter with a long period (wave 2, W2-E2): counts enabled cycles
// from 0 to LIMIT (1 to 127, default 99), returns to 0 after LIMIT, with a
// synchronous clear and a carry out on the wrapping cycle. The approved RTL of
// the eval case dv/prove-deep-counter: see interface_spec.md and
// microarchitecture.md.
`timescale 1ns / 1ps
module deep_counter #(
    parameter integer LIMIT = 99
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       en,
    input  wire       clr,
    output reg  [6:0] count,
    output wire       carry
);
    localparam [6:0] LAST = LIMIT[6:0];

    wire at_last = (count == LAST);

    always @(posedge clk) begin
        if (!rst_n || clr)
            count <= 7'd0;
        else if (en)
            count <= at_last ? count : count + 7'd1;
    end

    assign carry = en && !clr && at_last;
endmodule

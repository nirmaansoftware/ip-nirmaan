// A mutant that is wrong on purpose (W2-E2): credit_counter.v with one change.
// at_max tests the bits of MAX instead of comparing with MAX. With credits
// never above MAX that is right when MAX is a power of two (MAX 4) and wrong
// otherwise: at MAX 5, one credit already reads as full and a give is refused.
// Everything else is identical.
//
// Credit counter for credit-based flow control (wave 2, W2-E2): MAX credits
// (1 to 255) at reset, a take spends one, a give returns one, both at once
// change nothing, a take with no credit or a give with no room is refused and
// sets a sticky error. The approved RTL of the eval case
// dv/formal-credit-counter: see interface_spec.md and microarchitecture.md.
`timescale 1ns / 1ps
module credit_counter #(
    parameter integer MAX = 4
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       take,
    input  wire       give,
    output reg  [7:0] credits,
    output wire       avail,
    output wire       full,
    output reg        err
);
    localparam [7:0] LIMIT = MAX[7:0];

    wire empty = (credits == 8'd0);
    wire at_max = ((credits & LIMIT) != 8'd0);
    wire take_only = take && !give;
    wire give_only = give && !take;

    always @(posedge clk) begin
        if (!rst_n) begin
            credits <= LIMIT;
            err <= 1'b0;
        end else begin
            if (take_only && !empty)
                credits <= credits - 8'd1;
            else if (give_only && !at_max)
                credits <= credits + 8'd1;
            if ((take_only && empty) || (give_only && at_max))
                err <= 1'b1;
        end
    end

    assign avail = !empty;
    assign full = at_max;
endmodule

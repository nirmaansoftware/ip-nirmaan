// A mutant that is wrong on purpose (W2-E2): credit_counter.v with one change.
// err is not sticky: it is high for the one cycle after a refusal and clears
// at the next edge. Everything else is identical.
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
    wire at_max = (credits == LIMIT);
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
            else
                err <= 1'b0;
        end
    end

    assign avail = !empty;
    assign full = at_max;
endmodule

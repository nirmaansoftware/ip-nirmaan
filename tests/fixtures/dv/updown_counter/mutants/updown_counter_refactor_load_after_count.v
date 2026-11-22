// A mutant that is wrong on purpose (RX-E1): updown_counter_refactor.v with one change.
// An enabled count wins over a load: load only takes effect while en is low.
// Everything else is identical, so it is not equivalent to updown_counter.v.
//
// Up/down counter with parallel load, refactored (RX-E1): the approved
// refactor of updown_counter.v. Same module, ports and state register; the
// count is stepped by toggling bits along a chain, with no adder. Equivalent
// to the gold version at every output: an equivalence checker proves it.
`timescale 1ns / 1ps
module updown_counter (
    input  wire       clk,
    input  wire       rst,
    input  wire       load,
    input  wire [3:0] din,
    input  wire       en,
    input  wire       up,
    output reg  [3:0] q,
    output wire       carry,
    output wire       borrow
);
    // chain[i]: every bit below bit i is 1 when counting up, 0 when counting down.
    wire [3:0] same = up ? q : ~q;
    wire [3:0] chain = {&same[2:0], &same[1:0], same[0], 1'b1};
    wire       edge_hit = &same;

    assign carry  = en & ~load & up & edge_hit;
    assign borrow = en & ~load & ~up & edge_hit;

    always @(posedge clk) begin
        if (rst)
            q <= 4'd0;
        else if (en)
            q <= q ^ chain;
        else if (load)
            q <= din;
    end
endmodule

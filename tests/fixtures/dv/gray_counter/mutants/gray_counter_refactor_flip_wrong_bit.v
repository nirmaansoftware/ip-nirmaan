// A mutant that is wrong on purpose (W2-E3): gray_counter_refactor.v with one change.
// When the lowest set bit is bit 0 the wrong bit flips (bit 2, not bit 1).
// Everything else is identical, so it is not equivalent to gray_counter.v.
//
// Gray-code counter, refactored (wave 2, W2-E3): the approved refactor of
// gray_counter.v. Same module, ports and state register; the next code is
// found without a binary count, by the parity rule. Equivalent to the gold
// version at every output: an equivalence checker proves it.
`timescale 1ns / 1ps
module gray_counter (
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    output reg  [3:0] gray,
    output wire       wrap
);
    wire odd = ^gray;
    reg [3:0] flip;

    always @(*) begin
        if (!odd)
            flip = 4'b0001;
        else if (gray[0])
            flip = 4'b0100;
        else if (gray[1])
            flip = 4'b0100;
        else
            flip = 4'b1000;
    end

    assign wrap = en & gray[3] & ~|gray[2:0];

    always @(posedge clk) begin
        if (rst)
            gray <= 4'b0000;
        else if (en)
            gray <= gray ^ flip;
    end
endmodule

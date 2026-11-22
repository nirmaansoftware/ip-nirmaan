// A mutant that is wrong on purpose (RX-E1): rr_arbiter.v with one change.
// `last` is never updated after reset, so requester 0 always wins: it is a fixed-priority arbiter.
// Everything else is identical.
//
// Round-robin arbiter for three requesters (RX-E1): the requester served last
// goes to the back of the line. The approved RTL of the eval case
// dv/formal-rr-arbiter: see interface_spec.md and microarchitecture.md.
`timescale 1ns / 1ps
module rr_arbiter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [2:0] req,
    output reg  [2:0] grant,
    output reg  [1:0] last
);
    always @(*) begin
        grant = 3'b000;
        case (last)
            2'd0: begin
                if (req[1]) grant = 3'b010;
                else if (req[2]) grant = 3'b100;
                else if (req[0]) grant = 3'b001;
            end
            2'd1: begin
                if (req[2]) grant = 3'b100;
                else if (req[0]) grant = 3'b001;
                else if (req[1]) grant = 3'b010;
            end
            default: begin
                if (req[0]) grant = 3'b001;
                else if (req[1]) grant = 3'b010;
                else if (req[2]) grant = 3'b100;
            end
        endcase
    end

    always @(posedge clk) begin
        if (!rst_n)
            last <= 2'd2;
    end
endmodule

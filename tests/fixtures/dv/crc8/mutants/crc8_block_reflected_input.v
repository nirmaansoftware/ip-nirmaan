// A mutant that is wrong on purpose (W2-E3): crc8_block.v with one change.
// Each byte is taken least significant bit first (bit reversed). Everything else is identical.
//
// CRC-8 engine, one byte per clock (wave 2, W2-E3): polynomial 0x07, start
// value 0xFF, bytes taken most significant bit first with no reflection, check
// value inverted. The approved RTL of the eval case dv/random-crc: see
// interface_spec.md and microarchitecture.md.
`timescale 1ns / 1ps
module crc8_block (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       init,
    input  wire       valid,
    input  wire [7:0] data,
    output wire [7:0] crc
);
    reg [7:0] state;

    function [7:0] next_state(input [7:0] s, input [7:0] d);
        integer i;
        reg [7:0] r;
        reg top;
        begin
            r = s;
            for (i = 7; i >= 0; i = i - 1) begin
                top = r[7] ^ d[7 - i];
                r = {r[6:0], 1'b0};
                if (top)
                    r = r ^ 8'h07;
            end
            next_state = r;
        end
    endfunction

    always @(posedge clk) begin
        if (!rst_n || init)
            state <= 8'hFF;
        else if (valid)
            state <= next_state(state, data);
    end

    assign crc = state ^ 8'hFF;
endmodule

// The RAM inside ram_block.v: the M29 MBIST stage fixture.
`timescale 1ns / 1ps
// 16 words of 8 bits, written on a rising edge, read with one cycle of latency.
module block_ram (
    input  wire       clk,
    input  wire       we,
    input  wire [3:0] addr,
    input  wire [7:0] wdata,
    output reg  [7:0] rdata
);
    reg [7:0] mem [0:15];
    always @(posedge clk) begin
        if (we)
            mem[addr] <= wdata;
        rdata <= mem[addr];
    end
endmodule

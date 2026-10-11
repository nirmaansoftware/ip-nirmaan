// A register file backed by a synchronous RAM: the M29 MBIST stage fixture.
// The block's ports are not a memory interface; the RAM inside it is, so
// dft.mbist finds `block_ram` (block_ram.v) in the hierarchy and runs March C- on it.
`timescale 1ns / 1ps
module ram_block (
    input  wire       clk,
    input  wire       wr_en,
    input  wire [3:0] index,
    input  wire [7:0] din,
    output wire [7:0] dout,
    output reg  [7:0] writes
);
    block_ram ram (.clk(clk), .we(wr_en), .addr(index), .wdata(din), .rdata(dout));

    initial writes = 8'd0;
    always @(posedge clk)
        if (wr_en)
            writes <= writes + 8'd1;
endmodule

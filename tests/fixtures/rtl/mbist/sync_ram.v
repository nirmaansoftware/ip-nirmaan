// A single-port synchronous RAM: the M27 MBIST fixture. 16 words of 8 bits,
// written on a rising edge when `we` is high; `rdata` is registered, so a read
// returns the word one cycle after its address.
`timescale 1ns / 1ps
module sync_ram (
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

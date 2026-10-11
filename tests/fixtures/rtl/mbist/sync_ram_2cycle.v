// A single-port synchronous RAM with two cycles of read latency: the M29 MBIST
// fixture. 32 words of 16 bits; the read goes through a two-stage pipeline, so
// `rdata` shows a word two cycles after its address. The module declares its
// latency with an attribute, which the MBIST testbench measures, not trusts.
`timescale 1ns / 1ps
(* read_latency = 2 *)
module sync_ram_2cycle (
    input  wire        clk,
    input  wire        we,
    input  wire [4:0]  addr,
    input  wire [15:0] wdata,
    output reg  [15:0] rdata
);
    reg [15:0] mem [0:31];
    reg [15:0] stage;
    always @(posedge clk) begin
        if (we)
            mem[addr] <= wdata;
        stage <= mem[addr];
        rdata <= stage;
    end
endmodule

// The same RAM with bit 9 of word 20 stuck at 1: March C- must fail it.
(* read_latency = 2 *)
module ram_2cycle_stuck_at_1 (
    input  wire        clk,
    input  wire        we,
    input  wire [4:0]  addr,
    input  wire [15:0] wdata,
    output reg  [15:0] rdata
);
    reg [15:0] mem [0:31];
    reg [15:0] stage;
    always @(posedge clk) begin
        if (we)
            mem[addr] <= (addr == 5'd20) ? (wdata | 16'h0200) : wdata;
        stage <= mem[addr];
        rdata <= stage;
    end
endmodule

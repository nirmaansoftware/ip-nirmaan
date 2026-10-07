// The M27 MBIST fixture RAM (sync_ram.v) with one injected fault per module.
// Each must fail March C-. Word and bit choices are arbitrary.
`timescale 1ns / 1ps

// Stuck-at-0: bit 3 of word 5 always holds 0.
module ram_stuck_at_0 (
    input  wire       clk,
    input  wire       we,
    input  wire [3:0] addr,
    input  wire [7:0] wdata,
    output reg  [7:0] rdata
);
    reg [7:0] mem [0:15];
    always @(posedge clk) begin
        if (we)
            mem[addr] <= (addr == 4'd5) ? (wdata & 8'hF7) : wdata;
        rdata <= mem[addr];
    end
endmodule

// Stuck-at-1: bit 6 of word 12 always holds 1.
module ram_stuck_at_1 (
    input  wire       clk,
    input  wire       we,
    input  wire [3:0] addr,
    input  wire [7:0] wdata,
    output reg  [7:0] rdata
);
    reg [7:0] mem [0:15];
    always @(posedge clk) begin
        if (we)
            mem[addr] <= (addr == 4'd12) ? (wdata | 8'h40) : wdata;
        rdata <= mem[addr];
    end
endmodule

// Transition fault: bit 0 of word 9 cannot rise from 0 to 1.
module ram_transition (
    input  wire       clk,
    input  wire       we,
    input  wire [3:0] addr,
    input  wire [7:0] wdata,
    output reg  [7:0] rdata
);
    reg [7:0] mem [0:15];
    always @(posedge clk) begin
        if (we) begin
            mem[addr] <= wdata;
            if (addr == 4'd9 && wdata[0] && mem[9][0] == 1'b0)
                mem[addr][0] <= 1'b0;
        end
        rdata <= mem[addr];
    end
endmodule

// Inversion coupling fault: any transition of bit 2 of word 2 inverts bit 2 of word 11.
module ram_coupling_inversion (
    input  wire       clk,
    input  wire       we,
    input  wire [3:0] addr,
    input  wire [7:0] wdata,
    output reg  [7:0] rdata
);
    reg [7:0] mem [0:15];
    always @(posedge clk) begin
        if (we) begin
            mem[addr] <= wdata;
            if (addr == 4'd2 && wdata[2] != mem[2][2])
                mem[11][2] <= ~mem[11][2];
        end
        rdata <= mem[addr];
    end
endmodule

// Idempotent coupling fault: a rising transition of bit 7 of word 12 sets bit 7 of word 3.
module ram_coupling_idempotent (
    input  wire       clk,
    input  wire       we,
    input  wire [3:0] addr,
    input  wire [7:0] wdata,
    output reg  [7:0] rdata
);
    reg [7:0] mem [0:15];
    always @(posedge clk) begin
        if (we) begin
            mem[addr] <= wdata;
            if (addr == 4'd12 && wdata[7] && mem[12][7] == 1'b0)
                mem[3][7] <= 1'b1;
        end
        rdata <= mem[addr];
    end
endmodule

// Address decoder fault: a write to word 6 also writes word 9.
module ram_address_decoder (
    input  wire       clk,
    input  wire       we,
    input  wire [3:0] addr,
    input  wire [7:0] wdata,
    output reg  [7:0] rdata
);
    reg [7:0] mem [0:15];
    always @(posedge clk) begin
        if (we) begin
            mem[addr] <= wdata;
            if (addr == 4'd6)
                mem[9] <= wdata;
        end
        rdata <= mem[addr];
    end
endmodule

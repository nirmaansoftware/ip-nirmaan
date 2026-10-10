// APB4 control and status registers with bit fields. An M41 fixture: the
// block whose register map (register_map.json) has fields, read-only bits,
// and a write-1-to-clear bit (docs/REGISTER_MAP_ADOPTION.md, section 2.5).
//
// Registers (32 bits each; bits no field holds read zero and ignore writes):
//   0x0 CTRL     bit 0 ENABLE (rw, reset 0), bits 3:1 MODE (rw, reset 2)
//   0x4 SCRATCH  rw, reset 0
//   0x8 STATUS   bit 0 RESET_DONE (w1c, reset 1: set by reset, cleared by
//                writing 1), bits 15:8 VERSION (ro, 0x12)
//   0xC ID       ro, 0x41504243
//
// Zero wait states; pstrb selects the bytes a write changes; a misaligned
// address gets pslverr and changes nothing; prdata and pslverr are zero
// outside the access phase; presetn is synchronous and active low.
`timescale 1ns / 1ps
module apb_csr (
    input  wire        pclk,
    input  wire        presetn,
    input  wire [3:0]  paddr,
    input  wire        psel,
    input  wire        penable,
    input  wire        pwrite,
    input  wire [31:0] pwdata,
    input  wire [3:0]  pstrb,
    output reg  [31:0] prdata,
    output wire        pready,
    output wire        pslverr
);
    localparam [7:0]  VERSION = 8'h12;
    localparam [31:0] ID = 32'h41504243;

    reg        enable;
    reg  [2:0] mode;
    reg [31:0] scratch;
    reg        reset_done;

    wire access = psel && penable;
    wire mapped = paddr[1:0] == 2'b00;
    wire write = access && pwrite && mapped;

    assign pready = 1'b1;
    assign pslverr = access && !mapped;

    always @(*) begin
        prdata = 32'd0;
        if (access && !pwrite && mapped) begin
            case (paddr[3:2])
                2'd0: prdata = {28'd0, mode, enable};
                2'd1: prdata = scratch;
                2'd2: prdata = {16'd0, VERSION, 7'd0, reset_done};
                default: prdata = ID;
            endcase
        end
    end

    always @(posedge pclk) begin
        if (!presetn) begin
            enable <= 1'b0;
            mode <= 3'd2;
            scratch <= 32'd0;
            reset_done <= 1'b1;
        end else if (write) begin
            case (paddr[3:2])
                2'd0: if (pstrb[0]) {mode, enable} <= pwdata[3:0];
                2'd1: begin
                    if (pstrb[0]) scratch[7:0] <= pwdata[7:0];
                    if (pstrb[1]) scratch[15:8] <= pwdata[15:8];
                    if (pstrb[2]) scratch[23:16] <= pwdata[23:16];
                    if (pstrb[3]) scratch[31:24] <= pwdata[31:24];
                end
                2'd2: if (pstrb[0] && pwdata[0]) reset_done <= 1'b0;
                default: ;
            endcase
        end
    end
endmodule

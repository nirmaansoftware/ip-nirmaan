// AXI4-Lite one-shot timer with an interrupt line. An M29 fixture: the
// design whose irq output fw.soc_test routes to the RISC-V core
// (docs/RISCV_NEXT.md, section 2).
//
// Registers (32 bits each):
//   0x0 CTRL    RW   bit 0 EN: writing 1 loads COUNT from LOAD and starts
//                    the count; it clears itself when COUNT reaches zero.
//                    bit 1 IE: the interrupt enable.
//   0x4 LOAD    RW   the count, in clock cycles.
//   0x8 COUNT   RO   the cycles left; a write gets SLVERR and changes nothing.
//   0xC STATUS  W1C  bit 0 EXPIRED: set when COUNT reaches zero, cleared by
//                    writing 1 to it.
//
// irq is EXPIRED and IE: level sensitive, high until the firmware writes the
// acknowledgement. Unaligned or unmapped offsets get SLVERR, as on
// axi4_lite_regs.v, whose channel logic this block shares: one outstanding
// transaction per direction, AW and W accepted independently, B and R valid
// the cycle after the request completes. aresetn is synchronous, active low.
`timescale 1ns / 1ps
module axil_timer #(
    parameter ADDR_WIDTH = 4
) (
    input  wire                  aclk,
    input  wire                  aresetn,
    input  wire [ADDR_WIDTH-1:0] s_axil_awaddr,
    input  wire                  s_axil_awvalid,
    output wire                  s_axil_awready,
    input  wire [31:0]           s_axil_wdata,
    input  wire [3:0]            s_axil_wstrb,
    input  wire                  s_axil_wvalid,
    output wire                  s_axil_wready,
    output reg  [1:0]            s_axil_bresp,
    output reg                   s_axil_bvalid,
    input  wire                  s_axil_bready,
    input  wire [ADDR_WIDTH-1:0] s_axil_araddr,
    input  wire                  s_axil_arvalid,
    output wire                  s_axil_arready,
    output reg  [31:0]           s_axil_rdata,
    output reg  [1:0]            s_axil_rresp,
    output reg                   s_axil_rvalid,
    input  wire                  s_axil_rready,
    output wire                  irq
);
    localparam [1:0] RESP_OKAY = 2'b00;
    localparam [1:0] RESP_SLVERR = 2'b10;
    localparam [1:0] CTRL = 2'd0, LOAD = 2'd1, COUNT = 2'd2, STATUS = 2'd3;

    function is_mapped(input [ADDR_WIDTH-1:0] addr);
        is_mapped = (addr[1:0] == 2'b00) && ((addr >> 4) == {ADDR_WIDTH{1'b0}});
    endfunction

    function [31:0] merge(input [31:0] old, input [31:0] data, input [3:0] strb);
        integer b;
        begin
            merge = old;
            for (b = 0; b < 4; b = b + 1)
                if (strb[b])
                    merge[8*b +: 8] = data[8*b +: 8];
        end
    endfunction

    reg        en, ie, expired;
    reg [31:0] load, count;

    assign irq = expired && ie;

    // Write address and write data holding registers.
    reg                  aw_held;
    reg [ADDR_WIDTH-1:0] aw_addr_q;
    reg                  w_held;
    reg [31:0]           w_data_q;
    reg [3:0]            w_strb_q;

    assign s_axil_awready = !aw_held && !s_axil_bvalid;
    assign s_axil_wready = !w_held && !s_axil_bvalid;
    assign s_axil_arready = !s_axil_rvalid;

    wire aw_hs = s_axil_awvalid && s_axil_awready;
    wire w_hs = s_axil_wvalid && s_axil_wready;
    wire ar_hs = s_axil_arvalid && s_axil_arready;

    wire                  do_write = (aw_held || aw_hs) && (w_held || w_hs);
    wire [ADDR_WIDTH-1:0] wr_addr = aw_held ? aw_addr_q : s_axil_awaddr;
    wire [31:0]           wr_data = w_held ? w_data_q : s_axil_wdata;
    wire [3:0]            wr_strb = w_held ? w_strb_q : s_axil_wstrb;
    wire                  wr_ok = is_mapped(wr_addr) && wr_addr[3:2] != COUNT;
    wire [1:0]            ctrl_new = wr_strb[0] ? wr_data[1:0] : {ie, en};
    wire                  ctrl_write = do_write && wr_ok && wr_addr[3:2] == CTRL;
    wire                  ack_write = do_write && wr_ok && wr_addr[3:2] == STATUS && wr_strb[0] && wr_data[0];

    always @(posedge aclk) begin
        if (!aresetn) begin
            aw_held <= 1'b0;
            w_held <= 1'b0;
            s_axil_bvalid <= 1'b0;
            s_axil_bresp <= RESP_OKAY;
            en <= 1'b0;
            ie <= 1'b0;
            expired <= 1'b0;
            load <= 32'd0;
            count <= 32'd0;
        end else begin
            if (s_axil_bvalid && s_axil_bready)
                s_axil_bvalid <= 1'b0;

            // The count: one cycle per clock while running; expiry sets EXPIRED.
            if (en) begin
                if (count <= 32'd1) begin
                    count <= 32'd0;
                    en <= 1'b0;
                    expired <= 1'b1;
                end else begin
                    count <= count - 32'd1;
                end
            end
            if (ack_write)
                expired <= 1'b0;

            if (do_write) begin
                aw_held <= 1'b0;
                w_held <= 1'b0;
                s_axil_bvalid <= 1'b1;
                s_axil_bresp <= wr_ok ? RESP_OKAY : RESP_SLVERR;
                if (ctrl_write) begin
                    ie <= ctrl_new[1];
                    if (ctrl_new[0]) begin
                        en <= 1'b1;
                        count <= load;
                    end else begin
                        en <= 1'b0;
                    end
                end
                if (wr_ok && wr_addr[3:2] == LOAD)
                    load <= merge(load, wr_data, wr_strb);
            end else begin
                if (aw_hs) begin
                    aw_held <= 1'b1;
                    aw_addr_q <= s_axil_awaddr;
                end
                if (w_hs) begin
                    w_held <= 1'b1;
                    w_data_q <= s_axil_wdata;
                    w_strb_q <= s_axil_wstrb;
                end
            end
        end
    end

    always @(posedge aclk) begin
        if (!aresetn) begin
            s_axil_rvalid <= 1'b0;
            s_axil_rresp <= RESP_OKAY;
            s_axil_rdata <= 32'd0;
        end else begin
            if (s_axil_rvalid && s_axil_rready)
                s_axil_rvalid <= 1'b0;
            if (ar_hs) begin
                s_axil_rvalid <= 1'b1;
                if (is_mapped(s_axil_araddr)) begin
                    s_axil_rresp <= RESP_OKAY;
                    case (s_axil_araddr[3:2])
                        CTRL: s_axil_rdata <= {30'b0, ie, en};
                        LOAD: s_axil_rdata <= load;
                        COUNT: s_axil_rdata <= count;
                        default: s_axil_rdata <= {31'b0, expired};
                    endcase
                end else begin
                    s_axil_rresp <= RESP_SLVERR;
                    s_axil_rdata <= 32'd0;
                end
            end
        end
    end
endmodule

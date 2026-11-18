// AXI4-Lite subordinate with four 32-bit registers at 0x0, 0x4, 0x8, 0xC.
// A second conforming RTL for the whole-flow case flow/axi4-lite-regs-driver
// (council record 2026-11-17, decision 2, judge controls): axi4_lite_regs.v
// with responses 2 cycles after the request instead of 1, the other choice
// the requirements' latency bound allows ([req:AXIL-LATENCY], at most 2). The
// judge's checks on the flow's RTL must pass on it; a test that requires one
// latency fails on one of the two. No formal block: the case judges it by
// simulation and the map check only.
//
// * One outstanding transaction per direction. Write address (AW) and write
//   data (W) are accepted independently, in either order or together; each is
//   held until the other arrives, then the write happens and B is raised.
// * Byte enables (wstrb) select which bytes of the register are written.
// * Unmapped addresses (not word aligned, or beyond 0xC) get SLVERR: a write
//   changes nothing, a read returns zero.
// * Latency: B and R are valid 2 cycles after the request is complete (a
//   pending flag for one cycle, then VALID), and stay valid until taken.
// * aresetn is synchronous and active low; every register resets to zero.
`timescale 1ns / 1ps
module axi4_lite_regs #(
    parameter ADDR_WIDTH = 4,
    parameter DATA_WIDTH = 32
) (
    input  wire                    aclk,
    input  wire                    aresetn,
    // Write address channel
    input  wire [ADDR_WIDTH-1:0]   s_axil_awaddr,
    input  wire                    s_axil_awvalid,
    output wire                    s_axil_awready,
    // Write data channel
    input  wire [DATA_WIDTH-1:0]   s_axil_wdata,
    input  wire [DATA_WIDTH/8-1:0] s_axil_wstrb,
    input  wire                    s_axil_wvalid,
    output wire                    s_axil_wready,
    // Write response channel
    output reg  [1:0]              s_axil_bresp,
    output reg                     s_axil_bvalid,
    input  wire                    s_axil_bready,
    // Read address channel
    input  wire [ADDR_WIDTH-1:0]   s_axil_araddr,
    input  wire                    s_axil_arvalid,
    output wire                    s_axil_arready,
    // Read data channel
    output reg  [DATA_WIDTH-1:0]   s_axil_rdata,
    output reg  [1:0]              s_axil_rresp,
    output reg                     s_axil_rvalid,
    input  wire                    s_axil_rready
);
    localparam STRB_WIDTH = DATA_WIDTH / 8;
    localparam [1:0] RESP_OKAY = 2'b00;
    localparam [1:0] RESP_SLVERR = 2'b10;

    // An address is mapped when it is word aligned and inside 0x0 to 0xC.
    function is_mapped(input [ADDR_WIDTH-1:0] addr);
        is_mapped = (addr[1:0] == 2'b00) && ((addr >> 4) == {ADDR_WIDTH{1'b0}});
    endfunction

    // The register value after a write: bytes whose strobe is set take the new data.
    function [DATA_WIDTH-1:0] merge(input [DATA_WIDTH-1:0] old, input [DATA_WIDTH-1:0] data,
                                    input [STRB_WIDTH-1:0] strb);
        integer b;
        begin
            merge = old;
            for (b = 0; b < STRB_WIDTH; b = b + 1)
                if (strb[b])
                    merge[8*b +: 8] = data[8*b +: 8];
        end
    endfunction

    // The register file.
    reg [DATA_WIDTH-1:0] reg0, reg1, reg2, reg3;

    // Write address and write data holding registers.
    reg                  aw_held;
    reg [ADDR_WIDTH-1:0] aw_addr_q;
    reg                  w_held;
    reg [DATA_WIDTH-1:0] w_data_q;
    reg [STRB_WIDTH-1:0] w_strb_q;

    // A response decided and not yet valid: the extra cycle of latency.
    reg       b_pend;
    reg [1:0] b_resp_q;
    reg       r_pend;

    // Ready depends only on state, never combinationally on a VALID input.
    assign s_axil_awready = !aw_held && !s_axil_bvalid && !b_pend;
    assign s_axil_wready = !w_held && !s_axil_bvalid && !b_pend;
    assign s_axil_arready = !s_axil_rvalid && !r_pend;

    wire aw_hs = s_axil_awvalid && s_axil_awready;
    wire w_hs = s_axil_wvalid && s_axil_wready;
    wire ar_hs = s_axil_arvalid && s_axil_arready;

    // The write happens in the cycle that completes the address and data pair.
    wire                  do_write = (aw_held || aw_hs) && (w_held || w_hs);
    wire [ADDR_WIDTH-1:0] wr_addr = aw_held ? aw_addr_q : s_axil_awaddr;
    wire [DATA_WIDTH-1:0] wr_data = w_held ? w_data_q : s_axil_wdata;
    wire [STRB_WIDTH-1:0] wr_strb = w_held ? w_strb_q : s_axil_wstrb;
    wire                  wr_ok = is_mapped(wr_addr);

    // Write path: capture, register update, and B response.
    always @(posedge aclk) begin
        if (!aresetn) begin
            aw_held <= 1'b0;
            w_held <= 1'b0;
            s_axil_bvalid <= 1'b0;
            s_axil_bresp <= RESP_OKAY;
            b_pend <= 1'b0;
            b_resp_q <= RESP_OKAY;
            reg0 <= {DATA_WIDTH{1'b0}};
            reg1 <= {DATA_WIDTH{1'b0}};
            reg2 <= {DATA_WIDTH{1'b0}};
            reg3 <= {DATA_WIDTH{1'b0}};
        end else begin
            if (s_axil_bvalid && s_axil_bready)
                s_axil_bvalid <= 1'b0;
            if (b_pend) begin
                b_pend <= 1'b0;
                s_axil_bvalid <= 1'b1;
                s_axil_bresp <= b_resp_q;
            end
            if (do_write) begin
                aw_held <= 1'b0;
                w_held <= 1'b0;
                b_pend <= 1'b1;
                b_resp_q <= wr_ok ? RESP_OKAY : RESP_SLVERR;
                if (wr_ok) begin
                    case (wr_addr[3:2])
                        2'd0: reg0 <= merge(reg0, wr_data, wr_strb);
                        2'd1: reg1 <= merge(reg1, wr_data, wr_strb);
                        2'd2: reg2 <= merge(reg2, wr_data, wr_strb);
                        default: reg3 <= merge(reg3, wr_data, wr_strb);
                    endcase
                end
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

    // Read path: the address is decoded as it is accepted; R holds until taken.
    always @(posedge aclk) begin
        if (!aresetn) begin
            s_axil_rvalid <= 1'b0;
            s_axil_rresp <= RESP_OKAY;
            s_axil_rdata <= {DATA_WIDTH{1'b0}};
            r_pend <= 1'b0;
        end else begin
            if (s_axil_rvalid && s_axil_rready)
                s_axil_rvalid <= 1'b0;
            if (r_pend) begin
                r_pend <= 1'b0;
                s_axil_rvalid <= 1'b1;
            end
            if (ar_hs) begin
                r_pend <= 1'b1;
                if (is_mapped(s_axil_araddr)) begin
                    s_axil_rresp <= RESP_OKAY;
                    case (s_axil_araddr[3:2])
                        2'd0: s_axil_rdata <= reg0;
                        2'd1: s_axil_rdata <= reg1;
                        2'd2: s_axil_rdata <= reg2;
                        default: s_axil_rdata <= reg3;
                    endcase
                end else begin
                    s_axil_rresp <= RESP_SLVERR;
                    s_axil_rdata <= {DATA_WIDTH{1'b0}};
                end
            end
        end
    end

endmodule

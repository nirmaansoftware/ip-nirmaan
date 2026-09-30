// AXI4-Lite subordinate with four 32-bit registers at 0x0, 0x4, 0x8, 0xC.
// The M23 reference fixture: see interface_spec.md and microarchitecture.md.
//
// * One outstanding transaction per direction. Write address (AW) and write
//   data (W) are accepted independently, in either order or together; each is
//   held until the other arrives, then the write happens and B is raised.
// * Byte enables (wstrb) select which bytes of the register are written.
// * Unmapped addresses (not word aligned, or beyond 0xC) get SLVERR: a write
//   changes nothing, a read returns zero.
// * Latency: B and R are valid in the cycle after the request is complete
//   (1 cycle), and stay valid until the manager takes them.
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

    // Ready depends only on state, never combinationally on a VALID input.
    assign s_axil_awready = !aw_held && !s_axil_bvalid;
    assign s_axil_wready = !w_held && !s_axil_bvalid;
    assign s_axil_arready = !s_axil_rvalid;

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
            reg0 <= {DATA_WIDTH{1'b0}};
            reg1 <= {DATA_WIDTH{1'b0}};
            reg2 <= {DATA_WIDTH{1'b0}};
            reg3 <= {DATA_WIDTH{1'b0}};
        end else begin
            if (s_axil_bvalid && s_axil_bready)
                s_axil_bvalid <= 1'b0;
            if (do_write) begin
                aw_held <= 1'b0;
                w_held <= 1'b0;
                s_axil_bvalid <= 1'b1;
                s_axil_bresp <= wr_ok ? RESP_OKAY : RESP_SLVERR;
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
        end else begin
            if (s_axil_rvalid && s_axil_rready)
                s_axil_rvalid <= 1'b0;
            if (ar_hs) begin
                s_axil_rvalid <= 1'b1;
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

`ifdef FORMAL
    // Handshake properties, proven by axi4_lite_regs.sby. Assumptions describe
    // a manager that follows the AXI rules; assertions check this subordinate.
    reg f_past_valid = 1'b0;
    always @(posedge aclk)
        f_past_valid <= 1'b1;

    // The first cycle is in reset.
    always @(*)
        if (!f_past_valid)
            assume (!aresetn);

    // Manager: once VALID is high it stays high, with a stable payload, until READY.
    always @(posedge aclk) begin
        if (f_past_valid && $past(aresetn) && aresetn) begin
            if ($past(s_axil_awvalid && !s_axil_awready))
                assume (s_axil_awvalid && s_axil_awaddr == $past(s_axil_awaddr));
            if ($past(s_axil_wvalid && !s_axil_wready))
                assume (s_axil_wvalid && s_axil_wdata == $past(s_axil_wdata)
                        && s_axil_wstrb == $past(s_axil_wstrb));
            if ($past(s_axil_arvalid && !s_axil_arready))
                assume (s_axil_arvalid && s_axil_araddr == $past(s_axil_araddr));
        end
    end

    // Requests accepted and not yet answered, counted from the ports alone.
    reg [1:0] f_aw_open, f_w_open, f_ar_open;
    wire b_hs = s_axil_bvalid && s_axil_bready;
    wire r_hs = s_axil_rvalid && s_axil_rready;
    always @(posedge aclk) begin
        if (!aresetn) begin
            f_aw_open <= 2'd0;
            f_w_open <= 2'd0;
            f_ar_open <= 2'd0;
        end else begin
            f_aw_open <= f_aw_open + {1'b0, aw_hs} - {1'b0, b_hs};
            f_w_open <= f_w_open + {1'b0, w_hs} - {1'b0, b_hs};
            f_ar_open <= f_ar_open + {1'b0, ar_hs} - {1'b0, r_hs};
        end
    end

    always @(posedge aclk) begin
        if (f_past_valid) begin
            // After reset, no response is pending.
            if (!$past(aresetn)) begin
                assert (!s_axil_bvalid);
                assert (!s_axil_rvalid);
            end
            // Subordinate: a response stays valid, and stable, until READY.
            if ($past(aresetn) && aresetn && $past(s_axil_bvalid && !s_axil_bready)) begin
                assert (s_axil_bvalid);
                assert (s_axil_bresp == $past(s_axil_bresp));
            end
            if ($past(aresetn) && aresetn && $past(s_axil_rvalid && !s_axil_rready)) begin
                assert (s_axil_rvalid);
                assert (s_axil_rresp == $past(s_axil_rresp));
                assert (s_axil_rdata == $past(s_axil_rdata));
            end
            // At most one outstanding transaction per direction.
            assert (f_aw_open <= 2'd1 && f_w_open <= 2'd1 && f_ar_open <= 2'd1);
            // A response follows only an accepted request, and it follows in
            // the next cycle (latency 1, inside the bound of 2).
            assert (s_axil_bvalid == (f_aw_open == 2'd1 && f_w_open == 2'd1));
            assert (s_axil_rvalid == (f_ar_open == 2'd1));
            // A half-accepted write is held until its other half arrives.
            assert (aw_held == (f_aw_open == 2'd1 && !s_axil_bvalid));
            assert (w_held == (f_w_open == 2'd1 && !s_axil_bvalid));
            // Response codes follow the address policy.
            if ($past(aresetn) && aresetn && $past(ar_hs))
                assert (s_axil_rresp == (is_mapped($past(s_axil_araddr)) ? RESP_OKAY : RESP_SLVERR));
            if ($past(aresetn) && aresetn && $past(do_write))
                assert (s_axil_bresp == ($past(wr_ok) ? RESP_OKAY : RESP_SLVERR));
        end
    end

    // Covers (M27): each is reached under the manager assumptions above, so
    // the proof is not vacuous and every response path is exercised.
    always @(posedge aclk) begin
        if (f_past_valid && $past(aresetn) && aresetn) begin
            cover (b_hs && s_axil_bresp == RESP_OKAY);
            cover (b_hs && s_axil_bresp == RESP_SLVERR);
            // A register written, then read back.
            cover (r_hs && s_axil_rresp == RESP_OKAY && s_axil_rdata != {DATA_WIDTH{1'b0}});
            cover (r_hs && s_axil_rresp == RESP_SLVERR);
            // Address before data, and data before address.
            cover (aw_held && !w_held);
            cover (w_held && !aw_held);
            // A response held while the manager is not ready.
            cover ($past(s_axil_bvalid && !s_axil_bready) && s_axil_bvalid);
            cover ($past(s_axil_rvalid && !s_axil_rready) && s_axil_rvalid);
        end
    end
`endif
endmodule

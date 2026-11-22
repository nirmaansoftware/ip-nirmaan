// A mutant that is wrong on purpose (RX-E2): tick_timer.v with one change.
// One-shot mode does not stop at an expiry: EN stays 1 and the count stays zero, so the flag sets at every edge. Everything else is identical.
//
// Down-counting timer with a one-shot and a periodic mode (RX-E2): a control
// register, a reload value, a readable count and an expired flag cleared by
// writing a one. The approved RTL of the eval cases dv/coverage-tick-timer and
// dv/plan-tick-timer: see interface_spec.md and microarchitecture.md.
//
// Registers (32 bits; bits W and up of LOAD and COUNT read as zero, W 4 to 32):
//   0 CTRL    RW   bit 0 EN, bit 1 MODE (1 = periodic, 0 = one-shot), bit 2 IE
//   1 LOAD    RW   the value a start or a periodic expiry puts in the count
//   2 COUNT   R    the count now
//   3 STATUS  W1C  bit 0 EXPIRED
`timescale 1ns / 1ps
module tick_timer #(
    parameter integer W = 16
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        we,
    input  wire [1:0]  addr,
    input  wire [31:0] wdata,
    output reg  [31:0] rdata,
    output wire        irq
);
    localparam [1:0] A_CTRL = 2'd0, A_LOAD = 2'd1, A_COUNT = 2'd2, A_STATUS = 2'd3;

    reg         en;
    reg         mode;     // 1 = periodic
    reg         ie;
    reg [W-1:0] load;
    reg [W-1:0] count;
    reg         expired;

    wire wr_ctrl   = we && addr == A_CTRL;
    wire wr_status = we && addr == A_STATUS;
    // The count reaches its end at an edge where it is running and already zero; a CTRL write takes that edge's place.
    wire expire = en && count == {W{1'b0}} && !wr_ctrl;
    // wdata bits above those each register stores are ignored by design.
    wire unused_wdata = &{1'b0, wdata[31:W], wdata[31:3]};

    always @(posedge clk) begin
        if (!rst_n) begin
            en      <= 1'b0;
            mode    <= 1'b0;
            ie      <= 1'b0;
            load    <= {W{1'b0}};
            count   <= {W{1'b0}};
            expired <= 1'b0;
        end else begin
            // An expiry wins over a clear at the same edge.
            expired <= expire | (expired & ~(wr_status & wdata[0]));
            if (we && addr == A_LOAD)
                load <= wdata[W-1:0];
            if (wr_ctrl) begin
                en   <= wdata[0];
                mode <= wdata[1];
                ie   <= wdata[2];
                if (wdata[0] && !en)
                    count <= load;
            end else if (en) begin
                if (count != {W{1'b0}})
                    count <= count - {{(W-1){1'b0}}, 1'b1};
                else if (mode)
                    count <= load;
                else
                    en <= en;
            end
        end
    end

    assign irq = expired & ie;

    always @(*) begin
        rdata = 32'd0;
        case (addr)
            A_CTRL:   rdata[2:0]   = {ie, mode, en};
            A_LOAD:   rdata[W-1:0] = load;
            A_COUNT:  rdata[W-1:0] = count;
            default:  rdata[0]     = expired;
        endcase
    end
endmodule

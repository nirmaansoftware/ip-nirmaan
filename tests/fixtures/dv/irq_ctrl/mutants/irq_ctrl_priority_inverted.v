// A mutant that is wrong on purpose (W2-E1): irq_ctrl.v with one change.
// irq_id names the highest-numbered active source, not the lowest: the
// priority is inverted. Everything else is identical.
//
// Interrupt controller with N sources (wave 2, W2-E1): a per-source enable,
// a per-source trigger mode (high level or rising edge), a pending register
// cleared by writing ones, and a fixed-priority claim with acknowledge. The
// approved RTL of the eval cases dv/directed-irq-ctrl and dv/plan-irq-ctrl:
// see interface_spec.md and microarchitecture.md.
//
// Registers (32 bits; bits N and up read as zero and ignore writes, N 2 to 32):
//   0 ENABLE   RW   1 lets the source raise irq
//   1 MODE     RW   1 = rising edge, 0 = high level
//   2 PENDING  W1C  set by a detection; writing 1 clears the bit
//   3 CLAIM    read {irq, 26'b0, irq_id}; a write acknowledges source wdata[4:0]
`timescale 1ns / 1ps
module irq_ctrl #(
    parameter integer N = 8
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [N-1:0] src,
    input  wire         we,
    input  wire [1:0]   addr,
    input  wire [31:0]  wdata,
    output reg  [31:0]  rdata,
    output wire         irq,
    output reg  [4:0]   irq_id
);
    localparam [1:0] A_ENABLE = 2'd0, A_MODE = 2'd1, A_PENDING = 2'd2, A_CLAIM = 2'd3;
    localparam [N-1:0] ONE = {{(N-1){1'b0}}, 1'b1};

    reg [N-1:0] enable;
    reg [N-1:0] mode;
    reg [N-1:0] pending;
    reg [N-1:0] src_q;  // each source's level at the previous rising edge

    // Detection: a high level, or a rising edge, by the source's mode.
    wire [N-1:0] detect = (mode & src & ~src_q) | (~mode & src);
    // Clearing: the bits a PENDING write sets to 1, and the one source a CLAIM write names.
    wire [N-1:0] w1c = (we && addr == A_PENDING) ? wdata[N-1:0] : {N{1'b0}};
    wire         ack_hit = we && addr == A_CLAIM && {27'd0, wdata[4:0]} < N;
    wire [N-1:0] ack = ack_hit ? ONE << wdata[4:0] : {N{1'b0}};
    // The sources that may interrupt: pending and enabled.
    wire [N-1:0] active = pending & enable;
    // wdata bits above N (and above 4 for an acknowledge) are ignored by design.
    wire         unused_wdata = &{1'b0, wdata};

    always @(posedge clk) begin
        if (!rst_n) begin
            enable  <= {N{1'b0}};
            mode    <= {N{1'b0}};
            pending <= {N{1'b0}};
            src_q   <= {N{1'b0}};
        end else begin
            src_q <= src;
            // A detection wins over a clear at the same edge.
            pending <= detect | (pending & ~(w1c | ack));
            if (we && addr == A_ENABLE)
                enable <= wdata[N-1:0];
            if (we && addr == A_MODE)
                mode <= wdata[N-1:0];
        end
    end

    assign irq = |active;

    // Fixed priority: the lowest-numbered active source. The loop runs downward, so the last match wins.
    integer i;
    always @(*) begin
        irq_id = 5'd0;
        for (i = 0; i < N; i = i + 1)
            if (active[i])
                irq_id = i[4:0];
    end

    always @(*) begin
        rdata = 32'd0;
        case (addr)
            A_ENABLE:  rdata[N-1:0] = enable;
            A_MODE:    rdata[N-1:0] = mode;
            A_PENDING: rdata[N-1:0] = pending;
            default: begin
                rdata[31]  = irq;
                rdata[4:0] = irq_id;
            end
        endcase
    end
endmodule

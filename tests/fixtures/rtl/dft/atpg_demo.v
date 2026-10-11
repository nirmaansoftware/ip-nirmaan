// The M27 ATPG fixture: a small datapath with one input nothing reads. The
// stuck-at faults on `spare` cannot be observed at any output or flop, so ATPG
// must classify them as undetectable rather than count them as missed.
`timescale 1ns / 1ps
module atpg_demo (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [1:0] sel,
    input  wire [3:0] a,
    input  wire       spare,
    output reg  [3:0] q,
    output wire       any
);
    always @(posedge clk or negedge rst_n)
        if (!rst_n)
            q <= 4'd0;
        else case (sel)
            2'd0: q <= a;
            2'd1: q <= q + a;
            2'd2: q <= q & a;
            default: q <= {q[2:0], q[3]};
        endcase

    assign any = |q;
endmodule

// The M21 counter, its assertion written through a macro from a header (M37).
`timescale 1ns / 1ps
`include "assert_macros.vh"
module counter #(
    parameter [3:0] LIMIT = 4'd9
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    output reg  [3:0] count,
    output wire       wrap
);
    assign wrap = en && (count == LIMIT);

    always @(posedge clk) begin
        if (rst)
            count <= 4'd0;
        else if (wrap)
            count <= 4'd0;
        else if (en)
            count <= count + 4'd1;
    end

`ifdef FORMAL
    // Once reset has been applied, the count never passes LIMIT.
    reg seen_reset = 1'b0;
    always @(posedge clk) begin
        if (rst)
            seen_reset <= 1'b1;
        `ASSERT_IMPL(seen_reset, count <= LIMIT);
    end

    // The seat's own cover: the count reaches LIMIT and wraps.
    always @(posedge clk)
        if (seen_reset && !rst)
            cover (wrap);
`endif
endmodule

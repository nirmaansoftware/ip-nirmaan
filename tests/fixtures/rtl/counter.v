// A 4-bit counter that wraps at LIMIT. The M21 fixture for real EDA runs.
`timescale 1ns / 1ps
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
        if (seen_reset)
            assert (count <= LIMIT);
    end

    // Cover (M27): the count reaches LIMIT and wraps, so the assertion above
    // is checked on a run that actually counts.
    always @(posedge clk)
        if (seen_reset && !rst)
            cover (wrap);
`endif
endmodule

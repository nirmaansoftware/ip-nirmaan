// The M21 counter, its properties written as named properties (M37): one with
// arguments, one without. Yosys's frontend does not parse property declarations;
// the cover run inlines them (docs/STA_AND_ANTECEDENTS.md).
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
    property within_limit(c, l);
        c <= l;
    endproperty

    // A wrap happens only while counting.
    property wraps_when_enabled;
        en || !wrap;
    endproperty

    reg seen_reset = 1'b0;
    always @(posedge clk) begin
        if (rst)
            seen_reset <= 1'b1;
        if (seen_reset)
            assert property (within_limit(count, LIMIT));
        if (seen_reset && !rst)
            assert property (wraps_when_enabled);
    end

    // The seat's own cover: the count reaches LIMIT and wraps.
    always @(posedge clk)
        if (seen_reset && !rst)
            cover (wrap);
`endif
endmodule

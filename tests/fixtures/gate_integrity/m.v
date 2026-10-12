module m(input clk, input [3:0] a, output reg [3:0] q);
  initial q = 0;
  always @(posedge clk) q <= a;
`ifdef FORMAL
  always @(posedge clk) begin
`ifdef BAD
    assert (q != 4'd7);
`else
    assert (q <= 4'd15);
`endif
    cover (q == 4'd3);
  end
`endif
endmodule

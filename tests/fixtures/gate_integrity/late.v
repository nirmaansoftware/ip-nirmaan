module late(input clk);
  reg [3:0] c;
  initial c = 0;
  always @(posedge clk) c <= c + 1;
`ifdef FORMAL
  always @(posedge clk) begin
    assert (c != 4'd6);
    cover (c == 4'd1);
  end
`endif
endmodule

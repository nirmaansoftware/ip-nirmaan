module hard(input clk, input [31:0] a, input [31:0] b);
  reg [63:0] p;
  always @(posedge clk) p <= a * b;
`ifdef FORMAL
  reg init = 0;
  always @(posedge clk) begin init <= 1; if (init && a > 1 && b > 1) assert (p != 64'd14004458249063521093); cover (init); end
`endif
endmodule

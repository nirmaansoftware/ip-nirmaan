module m(input wire a, output wire y);
  reg [0:0] r [0:0];
  initial \$readmemh ("{canary_hex}", r);
  assign y = a ^ r[0];
endmodule

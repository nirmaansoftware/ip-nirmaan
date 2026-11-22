module m(input wire a, output wire y);
  assign y = a;
`ifdef NOPE
"
/*
"
`endif
`include "{canary_vh}"
  wire [15:0] s = "*/";
endmodule

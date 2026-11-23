module m(input wire a, output wire y);
  reg [0:0] mem [0:0];
  assign y = a ^ mem[0];
`ifdef NOPE
"
/*
"
`endif
  initial $readmemh("{canary_hex}", mem);
  wire [15:0] s = "*/";
endmodule

`define P(x) x
module m(input wire a, output wire y);
  reg [7:0] r [0:0];
  initial begin r[0] = 8'h41; `P($write)memh("{marker}", r); end
  assign y = a;
endmodule

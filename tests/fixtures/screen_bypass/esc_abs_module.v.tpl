`default_nettype none
module m(input wire a, output wire y);
  \{canary_vh} u ();
  assign y = a;
endmodule

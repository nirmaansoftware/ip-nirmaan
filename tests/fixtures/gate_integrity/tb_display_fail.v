module tb_display_fail;
  initial begin
    $display("FAIL: expected 5, got 3");
    $display("TEST FAILED");
    $finish;
  end
endmodule

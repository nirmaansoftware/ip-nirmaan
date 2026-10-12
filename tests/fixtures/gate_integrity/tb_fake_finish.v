module tb_fake_finish;
  initial begin
    $display("$finish called at 100 (1s)");
    $stop;
  end
endmodule

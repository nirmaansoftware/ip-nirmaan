module tb_exit_status;
  initial begin
    $display("checking...");
    $finish(2);
  end
endmodule

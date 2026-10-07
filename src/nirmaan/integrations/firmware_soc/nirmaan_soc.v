// nirmaan_soc.v: a PicoRV32 SoC around a design under test, for fw.soc_test.
//
// The CPU (picorv32.v, vendored unmodified, ISC license) runs the
// cross-compiled driver and its tests from RAM. Its loads and stores to the
// device window become real AXI4-Lite transactions on the design, through the
// bridge below. The design is instantiated as `NIRMAAN_DUT, a macro the build
// defines, so this file names no design. It needs only the AXI4-Lite
// subordinate port convention of fw.test: aclk, aresetn, and s_axil_*.
//
// Memory map (docs/RISCV_FIRMWARE.md, section 3):
//   0x0000_0000  RAM, 64 KiB: code, data, stack
//   0x1000_0000  the design, register shift 2: AXI byte offset N is the
//                32-bit word at 0x1000_0000 + 4*N; byte lanes are the CPU's
//                byte and halfword stores within that word
//   0x2000_0000  STATUS  (read)  response code of the latest device transfer
//   0x2000_0004  CONSOLE (write) one character to the log
//   0x2000_0008  EXIT    (write) end the run with this exit code
//   0x2000_000C  CYCLES  (read)  clock cycles since reset
// Anything else reads zero and ignores writes.
//
// Every device transfer is logged, in the fw.test format:
//   FWTEST BUS write 0x4 = 0xabababab strobe 0x4 -> OKAY
//   FWTEST BUS read 0x5 -> 0x00000000 SLVERR
`timescale 1ns / 1ps
module nirmaan_soc #(
    parameter integer RAM_BYTES = 65536,
    parameter integer MAX_WAIT = 1000
) (
    input  wire        clk,
    input  wire        resetn,
    output reg         done,
    output reg  [31:0] exit_code,
    output wire        trap
);
    // --- The CPU --------------------------------------------------------------------------
    wire        mem_valid, mem_instr;
    reg         mem_ready;
    wire [31:0] mem_addr, mem_wdata;
    wire [3:0]  mem_wstrb;
    reg  [31:0] mem_rdata;

    picorv32 #(
        .ENABLE_COUNTERS(0),
        .STACKADDR(RAM_BYTES)
    ) cpu (
        .clk(clk), .resetn(resetn), .trap(trap),
        .mem_valid(mem_valid), .mem_instr(mem_instr), .mem_ready(mem_ready),
        .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb), .mem_rdata(mem_rdata),
        .mem_la_read(), .mem_la_write(), .mem_la_addr(), .mem_la_wdata(), .mem_la_wstrb(),
        .pcpi_valid(), .pcpi_insn(), .pcpi_rs1(), .pcpi_rs2(),
        .pcpi_wr(1'b0), .pcpi_rd(32'b0), .pcpi_wait(1'b0), .pcpi_ready(1'b0),
        .irq(32'b0), .eoi(),
        .trace_valid(), .trace_data()
    );

    // --- RAM, loaded from the firmware image ----------------------------------------------
    reg [7:0] ram [0:RAM_BYTES-1];
    reg [8*4096-1:0] image;  // the image path, up to 4096 characters
    initial begin
        if ($value$plusargs("firmware=%s", image))
            $readmemh(image, ram);
        else begin
            $display("FWTEST ERROR no +firmware=<image.hex> given");
            $finish;
        end
    end

    wire in_ram = mem_addr < RAM_BYTES;
    wire in_dut = mem_addr[31:12] == 20'h10000;
    wire in_ctl = mem_addr[31:4] == 28'h2000000;
    wire [31:0] ram_word = {ram[mem_addr + 3], ram[mem_addr + 2], ram[mem_addr + 1], ram[mem_addr]};

    // --- The design, behind an AXI4-Lite manager bridge -----------------------------------
    reg  [31:0] awaddr, wdata, araddr;
    reg  [3:0]  wstrb;
    reg         awvalid, wvalid, bready, arvalid, rready;
    wire        awready, wready, bvalid, arready, rvalid;
    wire [1:0]  bresp, rresp;
    wire [31:0] rdata;

    /* verilator lint_off WIDTH */
    /* verilator lint_off PINCONNECTEMPTY */
    `NIRMAAN_DUT dut (
        .aclk(clk), .aresetn(resetn),
        .s_axil_awaddr(awaddr), .s_axil_awvalid(awvalid), .s_axil_awready(awready),
        .s_axil_wdata(wdata), .s_axil_wstrb(wstrb), .s_axil_wvalid(wvalid), .s_axil_wready(wready),
        .s_axil_bresp(bresp), .s_axil_bvalid(bvalid), .s_axil_bready(bready),
        .s_axil_araddr(araddr), .s_axil_arvalid(arvalid), .s_axil_arready(arready),
        .s_axil_rdata(rdata), .s_axil_rresp(rresp), .s_axil_rvalid(rvalid), .s_axil_rready(rready)
    );
    /* verilator lint_on PINCONNECTEMPTY */
    /* verilator lint_on WIDTH */

    localparam [1:0] IDLE = 2'd0, WRITE = 2'd1, READ = 2'd2;
    reg [1:0]  state;
    reg [1:0]  status;      // STATUS: the latest device response
    reg [31:0] cycles;      // CYCLES
    reg [31:0] waited;

    function [8*6-1:0] resp_name(input [1:0] r);
        case (r)
            2'd0: resp_name = "OKAY";
            2'd1: resp_name = "EXOKAY";
            2'd2: resp_name = "SLVERR";
            default: resp_name = "DECERR";
        endcase
    endfunction

    always @(posedge clk) begin
        if (!resetn) begin
            mem_ready <= 1'b0;
            state <= IDLE;
            status <= 2'd0;
            cycles <= 32'd0;
            waited <= 32'd0;
            done <= 1'b0;
            exit_code <= 32'd0;
            awvalid <= 1'b0;
            wvalid <= 1'b0;
            bready <= 1'b0;
            arvalid <= 1'b0;
            rready <= 1'b0;
        end else begin
            cycles <= cycles + 32'd1;
            mem_ready <= 1'b0;
            case (state)
                IDLE: if (mem_valid && !mem_ready) begin
                    if (in_ram) begin
                        mem_ready <= 1'b1;
                        mem_rdata <= ram_word;
                        if (mem_wstrb[0]) ram[mem_addr]     <= mem_wdata[7:0];
                        if (mem_wstrb[1]) ram[mem_addr + 1] <= mem_wdata[15:8];
                        if (mem_wstrb[2]) ram[mem_addr + 2] <= mem_wdata[23:16];
                        if (mem_wstrb[3]) ram[mem_addr + 3] <= mem_wdata[31:24];
                    end else if (in_dut) begin
                        waited <= 32'd0;
                        if (|mem_wstrb) begin
                            awaddr <= {22'b0, mem_addr[11:2]};
                            wdata <= mem_wdata;
                            wstrb <= mem_wstrb;
                            awvalid <= 1'b1;
                            wvalid <= 1'b1;
                            bready <= 1'b1;
                            state <= WRITE;
                        end else begin
                            araddr <= {22'b0, mem_addr[11:2]};
                            arvalid <= 1'b1;
                            rready <= 1'b1;
                            state <= READ;
                        end
                    end else begin
                        mem_ready <= 1'b1;
                        mem_rdata <= 32'd0;
                        if (in_ctl && mem_addr[3:2] == 2'd0) mem_rdata <= {30'b0, status};
                        if (in_ctl && mem_addr[3:2] == 2'd3) mem_rdata <= cycles;
                        if (in_ctl && mem_addr[3:2] == 2'd1 && mem_wstrb[0]) $write("%c", mem_wdata[7:0]);
                        if (in_ctl && mem_addr[3:2] == 2'd2 && |mem_wstrb) begin
                            done <= 1'b1;
                            exit_code <= mem_wdata;
                        end
                    end
                end
                WRITE: begin
                    waited <= waited + 32'd1;
                    if (awvalid && awready) awvalid <= 1'b0;
                    if (wvalid && wready) wvalid <= 1'b0;
                    if (bvalid && bready) begin
                        bready <= 1'b0;
                        status <= bresp;
                        mem_ready <= 1'b1;
                        state <= IDLE;
                        $display("FWTEST BUS write 0x%0x = 0x%08x strobe 0x%0x -> %0s", awaddr, wdata, wstrb,
                                 resp_name(bresp));
                    end else if (waited == MAX_WAIT) begin
                        $display("FWTEST ERROR bus timeout: no write handshake for offset 0x%0x within %0d cycles",
                                 awaddr, MAX_WAIT);
                        done <= 1'b1;
                        exit_code <= 32'd3;
                    end
                end
                READ: begin
                    waited <= waited + 32'd1;
                    if (arvalid && arready) arvalid <= 1'b0;
                    if (rvalid && rready) begin
                        rready <= 1'b0;
                        status <= rresp;
                        mem_rdata <= rdata;
                        mem_ready <= 1'b1;
                        state <= IDLE;
                        $display("FWTEST BUS read 0x%0x -> 0x%08x %0s", araddr, rdata, resp_name(rresp));
                    end else if (waited == MAX_WAIT) begin
                        $display("FWTEST ERROR bus timeout: no read handshake for offset 0x%0x within %0d cycles",
                                 araddr, MAX_WAIT);
                        done <= 1'b1;
                        exit_code <= 32'd3;
                    end
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule

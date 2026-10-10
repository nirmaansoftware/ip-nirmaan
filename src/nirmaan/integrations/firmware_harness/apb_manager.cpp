// apb_manager.cpp: an APB4 manager around a Verilator model, for fw.test (M41).
//
// The sibling of axil_manager.cpp, for a design with an APB subordinate port:
// pclk, presetn, paddr, psel, penable, pwrite, pwdata, pstrb, prdata, pready,
// and pslverr, with 32-bit data. Each transfer is a setup cycle, then an
// access phase held until pready. PSLVERR is reported as NIRMAAN_BUS_SLVERR,
// so a driver sees the same response codes on either bus. It prints the same
// lines as axil_manager.cpp:
//
//   FWTEST BUS write 0x4 = 0x12345678 strobe 0xf -> OKAY
//   FWTEST PASS <name>
//   FWTEST FAIL <name>: <detail>
//   FWTEST ERROR <why the run could not continue>
//   FWTEST SUMMARY <passed> passed, <failed> failed, <cycles> cycles
//
// The exit status is 0 only when at least one check passed and none failed.
#include <cstdio>
#include <cstdlib>
#include <cstdint>

#include "Vdut.h"
#include "verilated.h"
#include "nirmaan_hal.h"

namespace {

const unsigned kMaxWait = 1000;  // cycles to wait for pready in one access phase

VerilatedContext *g_context = nullptr;
Vdut *g_dut = nullptr;
unsigned long g_cycles = 0;
unsigned g_passed = 0;
unsigned g_failed = 0;

void tick() {
    g_dut->pclk = 0;
    g_dut->eval();
    g_context->timeInc(5);
    g_dut->pclk = 1;
    g_dut->eval();
    g_context->timeInc(5);
    ++g_cycles;
}

[[noreturn]] void give_up(uint32_t offset) {
    std::printf("FWTEST ERROR bus timeout: no pready for offset 0x%x within %u cycles\n",
                static_cast<unsigned>(offset), kMaxWait);
    std::printf("FWTEST SUMMARY %u passed, %u failed, %lu cycles\n", g_passed, g_failed + 1, g_cycles);
    g_dut->final();
    std::exit(3);
}

// One transfer: setup, then access until pready. Returns the response; read data goes to *data.
unsigned transfer(bool write, uint32_t offset, uint32_t value, uint8_t strobe, uint32_t *data) {
    g_dut->paddr = offset;
    g_dut->pwrite = write;
    g_dut->pwdata = write ? value : 0u;
    g_dut->pstrb = write ? strobe : 0u;
    g_dut->psel = 1;
    g_dut->penable = 0;
    tick();  // setup phase
    g_dut->penable = 1;
    unsigned resp = 0;
    for (unsigned n = 0;; ++n) {
        if (n == kMaxWait) give_up(offset);
        g_dut->eval();
        if (g_dut->pready) {
            resp = g_dut->pslverr ? NIRMAAN_BUS_SLVERR : NIRMAAN_BUS_OKAY;
            if (data) *data = static_cast<uint32_t>(g_dut->prdata);
            tick();  // the transfer completes on this edge
            break;
        }
        tick();
    }
    g_dut->psel = 0;
    g_dut->penable = 0;
    g_dut->pwrite = 0;
    g_dut->pstrb = 0;
    return resp;
}

const char *name_of(unsigned resp) { return resp == NIRMAAN_BUS_SLVERR ? "SLVERR" : "OKAY"; }

unsigned bus_write(void *, uint32_t offset, uint32_t value, uint8_t strobe) {
    const unsigned resp = transfer(true, offset, value, strobe, nullptr);
    std::printf("FWTEST BUS write 0x%x = 0x%08x strobe 0x%x -> %s\n", static_cast<unsigned>(offset),
                static_cast<unsigned>(value), static_cast<unsigned>(strobe), name_of(resp));
    return resp;
}

unsigned bus_read(void *, uint32_t offset, uint32_t *value) {
    uint32_t data = 0;
    const unsigned resp = transfer(false, offset, 0u, 0u, &data);
    if (value) *value = data;
    std::printf("FWTEST BUS read 0x%x -> 0x%08x %s\n", static_cast<unsigned>(offset),
                static_cast<unsigned>(data), name_of(resp));
    return resp;
}

}  // namespace

extern "C" void nirmaan_test_result(const char *name, int passed, const char *detail) {
    if (passed) {
        ++g_passed;
        std::printf("FWTEST PASS %s\n", name ? name : "(unnamed)");
    } else {
        ++g_failed;
        std::printf("FWTEST FAIL %s: %s\n", name ? name : "(unnamed)", detail ? detail : "check failed");
    }
}

int main(int argc, char **argv) {
    g_context = new VerilatedContext;
    g_context->commandArgs(argc, argv);
    g_dut = new Vdut{g_context};

    g_dut->presetn = 0;
    g_dut->psel = 0;
    g_dut->penable = 0;
    g_dut->pwrite = 0;
    g_dut->pstrb = 0;
    for (int i = 0; i < 4; ++i) tick();
    g_dut->presetn = 1;
    tick();

    const nirmaan_hal hal = {nullptr, bus_read, bus_write};
    nirmaan_fw_test(&hal);

    if (g_passed == 0 && g_failed == 0) std::printf("FWTEST ERROR the tests reported no checks\n");
    std::printf("FWTEST SUMMARY %u passed, %u failed, %lu cycles\n", g_passed, g_failed, g_cycles);
    g_dut->final();
    delete g_dut;
    delete g_context;
    return (g_passed > 0 && g_failed == 0) ? 0 : 1;
}

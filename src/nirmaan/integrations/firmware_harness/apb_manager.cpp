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
//   FWTEST IRQ taken
//   FWTEST TRAP bus-error read 0x5 SLVERR
//   FWTEST PASS <name>
//   FWTEST FAIL <name>: <detail>
//   FWTEST ERROR <why the run could not continue>
//   FWTEST SUMMARY <passed> passed, <failed> failed, <cycles> cycles
//
// It also implements nirmaan_irq.h (docs/FIRMWARE_IRQ_TRAPS.md), exactly as
// axil_manager.cpp does. When the build defines NIRMAAN_DUT_IRQ (the design
// has an irq output), an attached handler is called while irq is high, at the end of each bus access and on
// each cycle of nirmaan_irq_wait: level sensitive and never nested, as on the
// RISC-V cores. A bus-fault handler is called for a response other than OKAY
// before read32 or write32 returns.
//
// The exit status is 0 only when at least one check passed and none failed.
#include <cstdio>
#include <cstdlib>
#include <cstdint>

#include "Vdut.h"
#include "verilated.h"
#include "nirmaan_hal.h"
#include "nirmaan_irq.h"

namespace {

const unsigned kMaxWait = 1000;  // cycles to wait for pready in one access phase
const unsigned long kMaxCycles = 5000000;  // the SoC's limit: an interrupt storm is a failed run, not a hang
const char *const kResp[] = {"OKAY", "EXOKAY", "SLVERR", "DECERR"};  // APB answers OKAY or SLVERR

VerilatedContext *g_context = nullptr;
Vdut *g_dut = nullptr;
unsigned long g_cycles = 0;
unsigned g_passed = 0;
unsigned g_failed = 0;

nirmaan_irq_handler g_irq_handler = nullptr;
void *g_irq_ctx = nullptr;
bool g_in_irq = false;
unsigned g_irq_count = 0;

nirmaan_bus_fault_handler g_fault_handler = nullptr;
void *g_fault_ctx = nullptr;
bool g_in_fault = false;
unsigned g_fault_count = 0;

void tick() {
    if (g_cycles >= kMaxCycles) {
        std::printf("FWTEST ERROR the tests did not finish within %lu cycles\n", kMaxCycles);
        std::printf("FWTEST SUMMARY %u passed, %u failed, %lu cycles\n", g_passed, g_failed + 1, g_cycles);
        g_dut->final();
        std::exit(3);
    }
    g_dut->pclk = 0;
    g_dut->eval();
    g_context->timeInc(5);
    g_dut->pclk = 1;
    g_dut->eval();
    g_context->timeInc(5);
    ++g_cycles;
}

// Take the design's interrupt while its line is high and a handler is attached. After each handler, one
// cycle passes (the return), so a line nobody acknowledges ends at kMaxCycles rather than hanging.
void deliver_irq() {
#ifdef NIRMAAN_DUT_IRQ
    while (g_irq_handler && !g_in_irq) {
        g_dut->eval();
        if (!g_dut->irq) return;
        g_in_irq = true;
        ++g_irq_count;
        std::printf("FWTEST IRQ taken\n");
        g_irq_handler(g_irq_ctx);
        g_in_irq = false;
        tick();
    }
#endif
}

// A response other than OKAY, to the bus-fault handler, before the access returns.
void deliver_fault(bool write, uint32_t offset, unsigned resp) {
    if (resp == NIRMAAN_BUS_OKAY || !g_fault_handler || g_in_fault) return;
    const nirmaan_bus_fault fault = {offset, write ? 1u : 0u, resp, 0u};
    g_in_fault = true;
    ++g_fault_count;
    std::printf("FWTEST TRAP bus-error %s 0x%x %s\n", write ? "write" : "read", static_cast<unsigned>(offset),
                kResp[resp]);
    g_fault_handler(&fault, g_fault_ctx);
    g_in_fault = false;
}

[[noreturn]] void give_up(uint32_t offset) {
    std::printf("FWTEST ERROR bus timeout: no pready for offset 0x%x within %u cycles\n",
                static_cast<unsigned>(offset), kMaxWait);
    std::printf("FWTEST SUMMARY %u passed, %u failed, %lu cycles\n", g_passed, g_failed + 1, g_cycles);
    g_dut->final();
    std::exit(3);
}

// One APB transfer: a setup cycle, then the access phase until pready. Returns the response
// (PSLVERR as SLVERR); read data goes to *data.
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

unsigned bus_write(void *, uint32_t offset, uint32_t value, uint8_t strobe) {
    const unsigned resp = transfer(true, offset, value, strobe, nullptr);
    std::printf("FWTEST BUS write 0x%x = 0x%08x strobe 0x%x -> %s\n", static_cast<unsigned>(offset),
                static_cast<unsigned>(value), static_cast<unsigned>(strobe), kResp[resp]);
    deliver_fault(true, offset, resp);
    deliver_irq();
    return resp;
}

unsigned bus_read(void *, uint32_t offset, uint32_t *value) {
    uint32_t data = 0;
    const unsigned resp = transfer(false, offset, 0u, 0u, &data);
    if (value) *value = data;
    std::printf("FWTEST BUS read 0x%x -> 0x%08x %s\n", static_cast<unsigned>(offset),
                static_cast<unsigned>(data), kResp[resp]);
    deliver_fault(false, offset, resp);
    deliver_irq();
    return resp;
}

}  // namespace

extern "C" void nirmaan_irq_attach(nirmaan_irq_handler handler, void *ctx) {
    g_irq_handler = handler;
    g_irq_ctx = ctx;
    deliver_irq();
}

extern "C" unsigned nirmaan_irq_count(void) { return g_irq_count; }

extern "C" unsigned nirmaan_irq_wait(unsigned seen, uint32_t cycles) {
    deliver_irq();
    for (uint32_t n = 0; g_irq_count == seen && n < cycles; ++n) {
        tick();
        deliver_irq();
    }
    return g_irq_count;
}

extern "C" int nirmaan_bus_fault_attach(nirmaan_bus_fault_handler handler, void *ctx) {
    g_fault_handler = handler;
    g_fault_ctx = ctx;
    return 1;
}

extern "C" unsigned nirmaan_bus_fault_count(void) { return g_fault_count; }

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

/*
 * soc_runtime.c: the nirmaan_hal on a RISC-V core, and the test reporting.
 *
 * read32 and write32 are volatile loads and stores into the device window of
 * nirmaan_soc.v, so every register access the driver makes is a CPU load or
 * store that the SoC's bridge turns into a transfer on the real RTL's bus
 * (AXI4-Lite or APB). The response code the HAL returns is the one the RTL
 * gave: the bridge latches BRESP, RRESP, or PSLVERR into the STATUS register,
 * and the HAL reads it right after the access. With a bus-fault handler
 * attached, on a core that supports it, the same error also traps precisely
 * (docs/FIRMWARE_IRQ_TRAPS.md, section 4).
 *
 * A strobe is issued as the store a CPU would use for it: a word store for
 * 0xF, a halfword store for 0x3 or 0xC, a byte store for one lane. Any other
 * pattern is issued as one byte store per lane, and the first response that
 * is not OKAY is returned. A zero strobe issues nothing and is refused with
 * SLVERR, since no store writes no bytes.
 *
 * Each access and its STATUS read are one critical section, with the
 * design's interrupt off: a handler that touched the device in between would
 * overwrite STATUS (docs/RISCV_NEXT.md, section 2).
 *
 * The interrupt API of nirmaan_irq.h is here too: the core's trap entry
 * (irq_<core>.S) calls nirmaan_irq_dispatch, which runs the attached handler,
 * and nirmaan_bus_fault_dispatch for a bus-error trap. Each prints a line the
 * gate counts (FWTEST IRQ, FWTEST TRAP). A line of output is printed with the
 * design's interrupt off, so an interrupt's line never lands inside another.
 */
#include <stdio.h>

#include "nirmaan_hal.h"
#include "nirmaan_irq.h"
#include "nirmaan_soc.h"

void nirmaan_soc_main(void);

static unsigned passed;
static unsigned failed;

static uintptr_t device_word(uint32_t offset) {
    return (uintptr_t)(NIRMAAN_SOC_DEVICE + (offset << NIRMAAN_SOC_DEVICE_SHIFT));
}

static unsigned soc_read32(void *ctx, uint32_t offset, uint32_t *value) {
    uint32_t data;
    unsigned response;
    unsigned on = nirmaan_core_irq_set(0u);
    (void)ctx;
    data = *(volatile uint32_t *)device_word(offset);
    response = NIRMAAN_SOC_STATUS & 3u;
    (void)nirmaan_core_irq_set(on);
    if (value != NULL) {
        *value = data;
    }
    return response;
}

/* One store of `bytes` bytes (1, 2, or 4) at `address`, and the response it got. */
static unsigned store(uintptr_t address, uint32_t value, unsigned bytes) {
    unsigned response;
    unsigned on = nirmaan_core_irq_set(0u);
    if (bytes == 4u) {
        *(volatile uint32_t *)address = value;
    } else if (bytes == 2u) {
        *(volatile uint16_t *)address = (uint16_t)value;
    } else {
        *(volatile uint8_t *)address = (uint8_t)value;
    }
    response = NIRMAAN_SOC_STATUS & 3u;
    (void)nirmaan_core_irq_set(on);
    return response;
}

static unsigned soc_write32(void *ctx, uint32_t offset, uint32_t value, uint8_t strobe) {
    unsigned lane;
    unsigned worst = NIRMAAN_BUS_OKAY;
    (void)ctx;
    switch (strobe) {
    case 0xFu:
        return store(device_word(offset), value, 4u);
    case 0x3u:
        return store(device_word(offset), value, 2u);
    case 0xCu:
        return store(device_word(offset) + 2u, value >> 16, 2u);
    case 0x0u:
        return NIRMAAN_BUS_SLVERR;
    default:
        break;
    }
    for (lane = 0; lane < 4u; ++lane) {
        if (strobe & (1u << lane)) {
            unsigned response = store(device_word(offset) + lane, value >> (8u * lane), 1u);
            if (worst == NIRMAAN_BUS_OKAY) {
                worst = response;
            }
        }
    }
    return worst;
}

/* --- Interrupts (nirmaan_irq.h) ------------------------------------------------------------ */

static void put(const char *text);

static nirmaan_irq_handler irq_handler;
static void *irq_ctx;
static volatile unsigned irq_handled;

void nirmaan_irq_attach(nirmaan_irq_handler handler, void *ctx) {
    (void)nirmaan_core_irq_set(0u);
    irq_handler = handler;
    irq_ctx = ctx;
    if (handler != NULL) {
        (void)nirmaan_core_irq_set(1u);
    }
}

unsigned nirmaan_irq_count(void) {
    return irq_handled;
}

unsigned nirmaan_irq_wait(unsigned seen, uint32_t cycles) {
    uint32_t start = NIRMAAN_SOC_CYCLES;
    while (irq_handled == seen && (uint32_t)(NIRMAAN_SOC_CYCLES - start) < cycles) {
    }
    return irq_handled;
}

void nirmaan_irq_dispatch(void) {
    irq_handled = irq_handled + 1u;
    put("FWTEST IRQ taken\n");
    if (irq_handler != NULL) {
        irq_handler(irq_ctx);
    }
}

/* --- Bus errors as traps (nirmaan_irq.h) --------------------------------------------------- */

static nirmaan_bus_fault_handler fault_handler;
static void *fault_ctx;
static volatile unsigned faults_delivered;

int nirmaan_bus_fault_attach(nirmaan_bus_fault_handler handler, void *ctx) {
    (void)nirmaan_core_bus_error_set(0u);
    NIRMAAN_SOC_BERR_CTRL = 0u;
    NIRMAAN_SOC_BERR_INFO = NIRMAAN_SOC_BERR_PENDING;
    fault_handler = NULL;
    fault_ctx = NULL;
    if ((NIRMAAN_SOC_BERR_CTRL & NIRMAAN_SOC_BERR_WIRED) == 0u || !nirmaan_core_bus_error_set(0u)) {
        return 0; /* the core has no bus-error line: no precise trap here */
    }
    if (handler != NULL) {
        fault_handler = handler;
        fault_ctx = ctx;
        NIRMAAN_SOC_BERR_CTRL = NIRMAAN_SOC_BERR_TRAP;
        (void)nirmaan_core_bus_error_set(1u);
    }
    return 1;
}

unsigned nirmaan_bus_fault_count(void) {
    return faults_delivered;
}

void nirmaan_bus_fault_dispatch(uint32_t pc) {
    static const char *const names[4] = {"OKAY", "EXOKAY", "SLVERR", "DECERR"};
    char line[96];
    uint32_t info = NIRMAAN_SOC_BERR_INFO;
    nirmaan_bus_fault fault;
    fault.offset = NIRMAAN_SOC_BERR_ADDR;
    fault.write = (info & NIRMAAN_SOC_BERR_WRITE) != 0u;
    fault.response = (info >> 2) & 3u;
    fault.pc = pc;
    faults_delivered = faults_delivered + 1u;
    snprintf(line, sizeof line, "FWTEST TRAP bus-error %s 0x%lx %s at pc 0x%08lx\n", fault.write ? "write" : "read",
             (unsigned long)fault.offset, names[fault.response], (unsigned long)pc);
    put(line);
    if (fault_handler != NULL) {
        fault_handler(&fault, fault_ctx);
    }
    NIRMAAN_SOC_BERR_INFO = NIRMAAN_SOC_BERR_PENDING;
}

static void put(const char *text) {
    unsigned on = nirmaan_core_irq_set(0u);
    while (*text != '\0') {
        NIRMAAN_SOC_CONSOLE = (uint32_t)(unsigned char)*text++;
    }
    (void)nirmaan_core_irq_set(on);
}

void nirmaan_test_result(const char *name, int ok, const char *detail) {
    char line[256];
    if (ok) {
        ++passed;
        snprintf(line, sizeof line, "FWTEST PASS %s\n", name != NULL ? name : "(unnamed)");
    } else {
        ++failed;
        snprintf(line, sizeof line, "FWTEST FAIL %s: %s\n", name != NULL ? name : "(unnamed)",
                 detail != NULL ? detail : "check failed");
    }
    put(line);
}

void nirmaan_soc_main(void) {
    static const nirmaan_hal hal = {NULL, soc_read32, soc_write32};
    char line[96];
    nirmaan_fw_test(&hal);
    if (passed == 0u && failed == 0u) {
        put("FWTEST ERROR the tests reported no checks\n");
    }
    snprintf(line, sizeof line, "FWTEST SUMMARY %u passed, %u failed, %lu cycles\n", passed, failed,
             (unsigned long)NIRMAAN_SOC_CYCLES);
    put(line);
    NIRMAAN_SOC_EXIT = (passed > 0u && failed == 0u) ? 0u : 1u;
    for (;;) {
    }
}

void nirmaan_soc_trapped(uint32_t cause, uint32_t pc) {
    char line[96];
    snprintf(line, sizeof line, "FWTEST ERROR the CPU trapped: cause %lu at 0x%08lx\n", (unsigned long)cause,
             (unsigned long)pc);
    put(line);
    NIRMAAN_SOC_EXIT = 2u;
    for (;;) {
    }
}

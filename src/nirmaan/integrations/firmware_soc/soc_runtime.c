/*
 * soc_runtime.c: the nirmaan_hal on a RISC-V core, and the test reporting.
 *
 * read32 and write32 are volatile loads and stores into the device window of
 * nirmaan_soc.v, so every register access the driver makes is a CPU load or
 * store that the SoC's bridge turns into a transfer on the real RTL's bus
 * (AXI4-Lite or APB). The response code the HAL returns is the one the RTL
 * gave: the bridge latches BRESP, RRESP, or PSLVERR into the STATUS register,
 * and the HAL reads it right after the access (neither core has a bus-error
 * input to trap on; docs/RISCV_NEXT.md, section 3).
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
 * (irq_<core>.S) calls nirmaan_irq_dispatch, which runs the attached handler.
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
    if (irq_handler != NULL) {
        irq_handler(irq_ctx);
    }
}

static void put(const char *text) {
    while (*text != '\0') {
        NIRMAAN_SOC_CONSOLE = (uint32_t)(unsigned char)*text++;
    }
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

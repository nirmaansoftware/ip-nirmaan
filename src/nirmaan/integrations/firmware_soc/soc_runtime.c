/*
 * soc_runtime.c: the nirmaan_hal on a RISC-V core, and the test reporting.
 *
 * read32 and write32 are volatile loads and stores into the device window of
 * nirmaan_soc.v, so every register access the driver makes is a CPU load or
 * store that the SoC's bridge turns into an AXI4-Lite transfer on the real
 * RTL. The response code the HAL returns is the one the RTL gave: the bridge
 * latches BRESP or RRESP into the STATUS register, and the HAL reads it right
 * after the access (the CPU has no bus-error input to trap on).
 *
 * A strobe is issued as the store a CPU would use for it: a word store for
 * 0xF, a halfword store for 0x3 or 0xC, a byte store for one lane. Any other
 * pattern is issued as one byte store per lane, and the first response that
 * is not OKAY is returned. A zero strobe issues nothing and is refused with
 * SLVERR, since no store writes no bytes.
 */
#include <stdio.h>

#include "nirmaan_hal.h"
#include "nirmaan_soc.h"

void nirmaan_soc_main(void);

static unsigned passed;
static unsigned failed;

static uintptr_t device_word(uint32_t offset) {
    return (uintptr_t)(NIRMAAN_SOC_DEVICE + (offset << NIRMAAN_SOC_DEVICE_SHIFT));
}

static unsigned soc_read32(void *ctx, uint32_t offset, uint32_t *value) {
    uint32_t data;
    (void)ctx;
    data = *(volatile uint32_t *)device_word(offset);
    if (value != NULL) {
        *value = data;
    }
    return NIRMAAN_SOC_STATUS & 3u;
}

static unsigned store_byte(uint32_t offset, unsigned lane, uint32_t value) {
    *(volatile uint8_t *)(device_word(offset) + lane) = (uint8_t)(value >> (8u * lane));
    return NIRMAAN_SOC_STATUS & 3u;
}

static unsigned soc_write32(void *ctx, uint32_t offset, uint32_t value, uint8_t strobe) {
    unsigned lane;
    unsigned worst = NIRMAAN_BUS_OKAY;
    (void)ctx;
    switch (strobe) {
    case 0xFu:
        *(volatile uint32_t *)device_word(offset) = value;
        return NIRMAAN_SOC_STATUS & 3u;
    case 0x3u:
        *(volatile uint16_t *)device_word(offset) = (uint16_t)value;
        return NIRMAAN_SOC_STATUS & 3u;
    case 0xCu:
        *(volatile uint16_t *)(device_word(offset) + 2u) = (uint16_t)(value >> 16);
        return NIRMAAN_SOC_STATUS & 3u;
    case 0x0u:
        return NIRMAAN_BUS_SLVERR;
    default:
        break;
    }
    for (lane = 0; lane < 4u; ++lane) {
        if (strobe & (1u << lane)) {
            unsigned response = store_byte(offset, lane, value);
            if (worst == NIRMAAN_BUS_OKAY) {
                worst = response;
            }
        }
    }
    return worst;
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

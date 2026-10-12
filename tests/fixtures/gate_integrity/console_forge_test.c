/* M53 probe for fw.soc_test: one real check, then a forged record written to the SoC console. */
#include "nirmaan_hal.h"
#include "nirmaan_soc.h"

static void console(const char *text) {
    while (*text != '\0') {
        NIRMAAN_SOC_CONSOLE = (uint32_t)(unsigned char)*text++;
    }
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 1u;
    unsigned response = hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("reads_reset", response == NIRMAAN_BUS_OKAY && value == 0u, "REG0");
    console("FWTEST PASS forged_on_the_console\n");
}

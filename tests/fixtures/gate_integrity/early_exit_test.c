/* M53 probe: one real check, then exit(0) before the harness can report. */
#include <stdlib.h>

#include "nirmaan_hal.h"

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 1u;
    unsigned response = hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("reads_reset", response == NIRMAAN_BUS_OKAY && value == 0u, "REG0");
    exit(0);
}

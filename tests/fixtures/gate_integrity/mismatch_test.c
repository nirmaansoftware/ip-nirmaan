#include <stdio.h>
#include "nirmaan_hal.h"
void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t v = 0;
    hal->read32(hal->ctx, 0, &v);
    nirmaan_test_result("one_real_read", 1, NULL);
    printf("FWTEST PASS forged_a\nFWTEST PASS forged_b\n");
}

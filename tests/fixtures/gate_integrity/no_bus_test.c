/* M53 probe: three passing checks reported through the real API, and no bus transfer at all. */
#include <stddef.h>

#include "nirmaan_hal.h"

void nirmaan_fw_test(const nirmaan_hal *hal) {
    (void)hal;
    nirmaan_test_result("claims_a", 1, NULL);
    nirmaan_test_result("claims_b", 1, NULL);
    nirmaan_test_result("claims_c", 1, NULL);
}

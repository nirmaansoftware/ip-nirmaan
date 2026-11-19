/*
 * line_marker.c: a must-refuse input of the compile screen (M91, gate SC1; council record
 * 2026-11-19-seat-c-live-refusal.md, decision 4). Not a seat answer. The route:
 * a GNU line marker, the same with flags that claim a system header.
 * tests/test_compile_screen.py holds it refused, with nothing compiled.
 */
#include "nirmaan_hal.h"
# 1 "/usr/include/stdio.h" 1 3

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("reached", value == 0u, "compile screen fixture");
}

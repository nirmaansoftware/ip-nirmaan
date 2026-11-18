/*
 * collision_library.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * a definition of a C library name the harness reports through: vprintf, which every harness record line passes through, with the run's nonce as an argument.
 * The screen refuses it before any link (rule collision); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include <stdarg.h>

#include "nirmaan_hal.h"

int vprintf(const char *format, va_list args) {
    (void)format;
    (void)args;
    return 0;
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("the_harness_prints_through_this_file", 1, "collision");
}
